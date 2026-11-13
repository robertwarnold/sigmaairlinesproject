"""Provider-independent execution receipts; no financial assumptions or network calls."""
from datetime import datetime, timezone
import hashlib
import csv
from collections import Counter
import os
import re
import time
import uuid
import json
from pathlib import Path


def utc_now():
    """Return a zoned UTC event timestamp; elapsed clocks are recorded separately."""
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    """Bind an artifact to its exact bytes, without interpreting engineering content."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_receipt(path, record, artifacts, stream=None):
    """Create a structured sidecar once; pricing remains unavailable until analysis."""
    artifacts = tuple(artifacts)
    # Separate timing/usage from FMEA rows; unknown billing is explicitly not zero.
    record["metadata_schema"] = "fmea-execution-1"
    if record.get("configuration", {}).get("response_schema") and "response_schema_sha256" not in record:
        # Initial receipt publication happens before the SDK's in-place schema serialization.
        record["response_schema_sha256"] = hashlib.sha256(json.dumps(record["configuration"]["response_schema"],sort_keys=True).encode()).hexdigest()
    # New fields extend the established receipt; unknown billing/acceptance never becomes zero/accepted.
    record.setdefault("retry_number", 0)
    record.setdefault("retry_wait_seconds", 0)
    record.setdefault("http_status", None)
    record.setdefault("invoice_expense_usd", None)
    record.setdefault("billing_status", "unknown_no_invoice")
    record.setdefault("engineering_review_status", "unreviewed")
    if record.get("workflow", "standalone_gemini").startswith("standalone"):
        csv_paths = [Path(p) for p in artifacts if Path(p).suffix == ".csv" and Path(p).is_file()]
        if csv_paths and record.get("status") == "success":
            try:
                record["fmea_metrics"] = characterize_csv(csv_paths[0])
            except Exception as error:
                record["fmea_metrics"] = {"schema_valid": False, "validation_error_type": type(error).__name__}
        elif record.get("status") != "running":
            record["fmea_metrics"] = {"schema_valid": False, "observation_available": False}

    record["estimated_api_expense_usd"] = None
    record["pricing_source"] = None
    record["pricing_status"] = "deferred_to_offline_financial_analysis_or_invoice"
    record["artifacts"] = {Path(p).name: {"sha256": file_hash(p), "bytes": Path(p).stat().st_size}
                           for p in artifacts if Path(p).is_file()}
    if stream is not None:
        # A generator may reserve its receipt before the request to prevent races.
        stream.seek(0)
        stream.truncate()
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
    else:
        with Path(path).open("x", encoding="utf-8", newline="\n") as destination:
            json.dump(record, destination, indent=2, allow_nan=False)
            destination.write("\n")


def characterize_csv(path):
    """Validate standalone/legacy CSVs using the existing v2 parser and derive provisional aggregates."""
    # Import only the parser, never a provider client; canonical unrated worksheets are excluded by callers.
    from fmea_generator import CSV_FIELDS, FIELDS, RATINGS, parse_fmea
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        historical = CSV_FIELDS[:4] + ["generation_minutes"] + CSV_FIELDS[4:]
        if reader.fieldnames not in (CSV_FIELDS, historical):
            raise ValueError("Unexpected standalone FMEA CSV headers")
        source = list(reader)
    if not source or any(None in row or None in row.values() for row in source):
        raise ValueError("Empty/malformed standalone FMEA CSV")
    rows = parse_fmea(json.dumps([{f: int(r[f]) if f in RATINGS else r[f] for f in FIELDS} for r in source]))
    if any(int(raw["RPN"]) != row["RPN"] for raw, row in zip(source, rows)):
        raise ValueError("CSV RPN does not match S*O*D")
    counts = Counter(r["component"] for r in rows)
    duplicates = Counter(tuple(re.sub(r"\s+", " ", r[f].strip().casefold()) for f in ("component", "failure_mode", "cause")) for r in rows)
    return {"schema_valid": True, "observation_available": True, "row_count": len(rows),
        "distinct_component_count": len(counts), "failure_modes_per_component": dict(counts),
        "potential_duplicate_rows": sum(n - 1 for n in duplicates.values()),
        "rating_distributions": {f: dict(Counter(str(r[f]) for r in rows)) for f in (*RATINGS, "RPN")},
        "component_coverage": None, "component_coverage_basis": "No validated denominator supplied",
        "ratings_status": "provisional_unreviewed", "engineering_review_status": "unreviewed"}


def failure_metadata(error):
    """Capture verified HTTP status and typed transport failures without retaining secret-bearing messages."""
    code = None
    # Checking the SDK's type hierarchy prevents an arbitrary '503' exception string authorizing classification.
    if any(t.__module__ == "google.genai.errors" and t.__name__ == "APIError" for t in type(error).__mro__):
        value = getattr(error, "code", None)
        code = value if isinstance(value, int) and not isinstance(value, bool) else None
    transport = type(error).__module__.startswith("httpx") and type(error).__name__ in ("RemoteProtocolError", "ReadTimeout", "ConnectTimeout", "ConnectError")
    classification = "provider_unavailable_503" if code == 503 else "provider_quota_429" if code == 429 else "provider_http_error" if code is not None else "provider_transport_failure" if transport else None
    result = {"http_status": code, "provider_error_classification": classification}
    if classification:
        result["failure_classification"] = classification
    if code == 429 and "generate_content_free_tier_requests" in str(error):
        result["provider_billing_tier_evidence"] = "free_tier_quota_reported"
    return result


def automatic_report(receipt_path):
    """Run offline reporting after a finalized standalone receipt; failures cannot alter generation status."""
    receipt_path = Path(receipt_path)
    status_path = receipt_path / "reporting_status.json" if receipt_path.is_dir() else receipt_path.with_name(receipt_path.stem.replace("_execution", "") + "_reporting.json")
    mode = os.getenv("SIGMA_FMEA_AUTOREPORT", "on").lower()
    status = {"receipt": str(receipt_path), "generation_outcome_unchanged": True, "started_at": utc_now()}
    if mode == "off":
        # Explicit opt-out leaves only the established execution artifacts, useful for SDK-only clients/tests.
        return {**status,"status":"disabled_explicitly"}
    start = time.perf_counter()
    try:
        if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
            status["status"] = "deferred_to_offline_actions_job"
        else:
            from analysis.experiments.report import post_generation
            output = post_generation(receipt_path)
            status.update(status="complete", report=str(output))
    except Exception as error:
        # Keep an actionable type and reporting incident separate from the provider receipt and exception.
        status.update(status="failed", error_type=type(error).__name__, action="Run python -m analysis.experiments report --source <receipt-directory> to diagnose")
        print(f"[REPORTING] {type(error).__name__}; generation outcome preserved. See {status_path}", flush=True)
    finally:
        status.update(finished_at=utc_now(), elapsed_seconds=time.perf_counter()-start)
        try:
            temporary=status_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
            temporary.replace(status_path)
        except OSError:
            print("[REPORTING] Could not persist reporting status; generation outcome preserved",flush=True)
    return status


def campaign_identity(explicit=None):
    """Preserve supplied experiment IDs; otherwise name one local/Actions execution without changing its request."""
    if explicit:return str(explicit)
    if os.getenv("FMEA_CAMPAIGN_ID"):return os.environ["FMEA_CAMPAIGN_ID"]
    if os.getenv("GITHUB_RUN_ID"):return "github-"+os.environ["GITHUB_RUN_ID"]
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-standalone-"+uuid.uuid4().hex[:8]
