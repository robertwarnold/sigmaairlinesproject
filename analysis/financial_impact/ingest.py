"""Read execution metadata and private aggregate logs, never raw FMEA answers."""
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from .cost_model import select_price, token_cost
from .data_schema import LABOR_FIELDS, QUALITY_FIELDS, number, read_json, validate_records


def sha256(path):
    """Hash exact input bytes for reproducible provenance."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configuration_id(settings):
    """Create a stable settings identity so incompatible conditions stay separate."""
    return hashlib.sha256(json.dumps(settings, sort_keys=True, allow_nan=False).encode()).hexdigest()


def read_log(path, kind):
    """Read a header-only template as no observations; reject malformed CSV records."""
    if path is None:
        return []
    # DictReader exposes extra cells as a None key; short rows have None values.
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Missing or duplicate CSV headers")
        expected = LABOR_FIELDS if kind == "labor" else QUALITY_FIELDS
        if set(expected) - set(reader.fieldnames):
            raise ValueError("Missing required CSV headers")
        rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError("Malformed CSV row width")
    return validate_records(rows, kind)


def import_attempts(path, assumptions, tier="standard_paid", arrangement="pay_as_you_go", invoices=None):
    """Import a legacy replicate manifest, a canonical state, or standardized sidecar."""
    source = Path(path)
    document = read_json(source)
    invoices = invoices or {}
    if document.get("financial_schema") == "reconciled-campaign-1":
        # Embedded immutable receipts retain separate original and recovery identities.
        import tempfile
        records = []
        with tempfile.TemporaryDirectory() as temporary:
            for index, receipt in enumerate(document["attempts"]):
                sidecar = Path(temporary) / f"{index}.json"
                sidecar.write_text(json.dumps(receipt), encoding="utf-8")
                records.extend(import_attempts(sidecar, assumptions, tier, arrangement, invoices))
        identities = [(r["experiment_id"], r["attempt_id"]) for r in records]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate reconciled attempt")
        for record in records:
            record["metadata_sha256"] = sha256(source)
            effective = document["effective_results"].get(record["system_id"], {})
            record["effective_result"] = effective.get("effective_attempt_id") == record["attempt_id"]
        return records
    # Normalize supported metadata formats without reading raw outputs or reference files.
    if "plan" in document and isinstance(document.get("runs"), list):
        plan = document["plan"]
        experiment = plan["batch_id"]
        workflow = "standalone_gemini"
        raw_runs = document["runs"]
    elif document.get("metadata_schema") == "fmea-execution-1":
        plan = document
        experiment = document["experiment_id"]
        workflow = document.get("workflow", "standalone_gemini")
        raw_runs = [document]
    elif "state" in document and "settings" in document:
        # Canonical prompt conditions never share a financial pool with standalone v2.
        state = document
        plan = {"system_id": state["system_id"], "system_sha256": state.get("input_sha256"),
                "prompt_version": state["prompt_version"], "skill_sha256": state.get("prompt_sha256"),
                "model": state["settings"].get("model"), **state["settings"]}
        experiment = state.get("plan_sha256") or str(source.parent.parent)
        workflow = "canonical_research:" + state["condition"]
        raw_runs = [{**state, "run_number": source.parent.name, "status": state["state"],
                     "duration_seconds": state.get("generation_seconds"),
                     "execution": {"usage_metadata": None, "model_version": state.get("actual_model")}}]
        # Canonical legacy usage is left unavailable unless Gemini counts are explicit.
        usage = state.get("usage")
        if usage and isinstance(usage.get("raw"), dict):
            raw_runs[0]["execution"]["usage_metadata"] = {
                "prompt_token_count": usage.get("input_tokens"),
                "candidates_token_count": usage.get("output_tokens"),
                "thoughts_token_count": usage.get("reasoning_tokens")}
    else:
        raise ValueError("Unsupported execution metadata format; supply manifest.json, state.json or execution sidecar")
    result, seen = [], set()
    for run in raw_runs:
        # A not-attempted plan slot has no generation expense or elapsed observation.
        status = run.get("status")
        if status == "not_attempted":
            continue
        execution = run.get("execution", {})
        # Failed standardized receipts may have usage at top level; canonical Gemini uses explicit names.
        attempt_id = str(run.get("attempt_id", run.get("run_number", "")))
        if not attempt_id or attempt_id in seen or not status:
            raise ValueError("Missing/duplicate attempt identity or status")
        seen.add(attempt_id)
        started = run.get("started_at")
        if not started:
            raise ValueError("Attempt lacks its observation date")
        observed_at = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if observed_at.utcoffset() is None:
            raise ValueError("Attempt timestamp requires a timezone")
        settings = run.get("configuration") or {k: plan.get(k) for k in (
            "temperature", "max_output_tokens", "response_mime_type", "response_schema_sha256", "retry_attempts")}
        usage = execution.get("usage_metadata", run.get("usage_metadata"))
        if usage and "input_tokens" in usage:
            usage = {"prompt_token_count": usage.get("input_tokens"),
                     "candidates_token_count": usage.get("output_tokens"),
                     "thoughts_token_count": usage.get("reasoning_tokens")}
        model = run.get("model", plan.get("model"))
        invoice = invoices.get(f"{experiment}/{attempt_id}")
        try:
            price = select_price(assumptions["pricing"], model, started, tier, arrangement)
            expense = token_cost(usage, price, invoice)
            price_source = price["source_id"]
        except ValueError:
            # Missing tariffs are explicit; malformed usage still raises when a tariff exists.
            if any(p["model"] == model and p["tier"] == tier and p["billing_arrangement"] == arrangement
                   and p["effective_from"] <= started[:10] <= p["effective_through"] for p in assumptions["pricing"]):
                raise
            expense = token_cost(None, {}, invoice)
            price_source = None
        duration = number(run.get("duration_seconds", run.get("total_elapsed_seconds")), "duration", nullable=True)
        if any(not run.get(k, plan.get(k)) for k in ("system_id", "prompt_version", "model")):
            raise ValueError("Missing system, skill version or model identity")
        result.append({"experiment_id": experiment, "attempt_id": attempt_id,
            "system_id": run.get("system_id", plan.get("system_id")),
            "input_hash": run.get("system_sha256", plan.get("system_sha256")),
            "skill_version": run.get("prompt_version", plan.get("prompt_version")),
            "skill_hash": run.get("skill_sha256", plan.get("skill_sha256")), "workflow": workflow,
            "model": model, "configuration": settings, "configuration_id": configuration_id(settings),
            "actual_model": execution.get("model_version", run.get("actual_model")),
            "started_at": started, "finished_at": run.get("finished_at"), "status": status,
            "failure_type": run.get("error_type", run.get("failure_classification")),
            "duration_seconds": duration, "api_request_seconds": execution.get("generation_seconds", run.get("api_request_seconds")),
            "parsing_validation_seconds": run.get("parsing_validation_seconds"),
            "usage": usage, "row_count": run.get("row_count"), "acceptance": "not_evaluated",
            "cost_usd": expense["usd"], "cost_basis": expense["basis"],
            "billing_uncertain": expense["billing_uncertain"], "pricing_source": price_source,
            "tier": tier, "billing_arrangement": arrangement, "metadata_sha256": sha256(source)})
    return result
