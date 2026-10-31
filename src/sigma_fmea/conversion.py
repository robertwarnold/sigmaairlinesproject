"""Deterministic mapping with detached source snapshots and verifiable reports."""
from copy import deepcopy
import csv
from pathlib import Path

from .integrity import canonical_json, digest, load_json, normalize_header, strict_loads, validate_json
from .models import FMEARow, FMEADraft, TEXT_FIELDS, LIST_FIELDS, require_text, evidence, text_list

MAPPING_VERSION = "0.2"
MAPPING = {
    "item": "item_or_process_step", "function": "function", "failure_mode": "failure_mode",
    "causes": "failure_causes", "local_effect": "effect_local",
    "next_level_effect": "effect_next_level", "end_effect": "effect_end_effect",
    "proposed_mitigations": "recommended_actions",
}
RISK_FIELDS = {"criticality", "severity", "occurrence", "likelihood", "detection", "detection_prevention", "rpn", "failure_probability", "risk_scheme", "critical_item",
               "criticality_units", "severity_units", "occurrence_units", "likelihood_units", "detection_units", "rpn_units", "failure_probability_units", "failure_rate", "failure_rate_units", "alpha", "beta", "mission_time", "mission_time_units", "risk_units"}


def import_records(path):
    path = Path(path)
    if path.suffix.lower() == ".json":
        records = load_json(path)
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            try:
                raw_headers = next(reader)
                headers = [normalize_header(h) for h in raw_headers]
                if not headers or any(not h for h in headers):
                    raise ValueError("Blank CSV header")
                if len(set(headers)) != len(headers):
                    raise ValueError("Duplicate CSV header after normalization")
                records = []
                for row in reader:
                    if len(row) != len(headers):
                        raise ValueError(f"CSV row width mismatch at line {reader.line_num}")
                    record = dict(zip(headers, row))
                    # Header spellings remain recoverable; cell contents are never coerced.
                    if "_csv_headers" in record:
                        raise ValueError("Reserved CSV header: _csv_headers")
                    record["_csv_headers"] = raw_headers
                    records.append(record)
            except StopIteration:
                raise ValueError("Empty CSV input") from None
            except csv.Error as error:
                raise ValueError(f"Malformed CSV: {error}") from error
    else:
        raise ValueError("FMECA import requires .json or .csv")
    validate_json(records)
    if not isinstance(records, list) or not records or any(not isinstance(r, dict) for r in records):
        raise ValueError("FMECA input must contain a nonempty list of records")
    return records


def _convert_record(source, index):
    for key in ("source_id", "source_locator", "source_edition", "item"):
        require_text(source.get(key), key)
    snapshot = canonical_json(source)  # immutable string, independent of caller objects
    source = strict_loads(snapshot)
    trace_id = f"conversion-{index}-{digest(source)[:12]}"
    values, traces, refs = {}, [], []
    consumed = {"source_id", "source_locator", "source_edition", "review_flags"}
    text_list(source.get("review_flags", []), "source.review_flags")
    flags = list(source.get("review_flags", []))
    flags.append("source_scope_hierarchy_phase_and_risk_definitions_require_review")

    def ref(destination, locator=None):
        return {"source_id": source["source_id"], "locator": locator or source["source_locator"],
                "edition": source["source_edition"], "field": destination}

    for key, destination in MAPPING.items():
        value = source.get(key)
        consumed.add(key)
        status = "unavailable" if value is None or value == "" or value == [] else "direct"
        if status == "direct":
            if destination in LIST_FIELDS and isinstance(value, str):
                value, status = [value], "normalized"
            values[destination] = value
            refs.append(ref(destination))
        traces.append({"source_field": key, "target_field": destination, "status": status})

    controls = []
    # Legacy free-text control columns are retained, but never inherit a shared status.
    for kind in ("prevention", "detection", "mitigation"):
        key = f"{kind}_controls"
        legacy = source.get(key)
        if legacy:
            entries = [legacy] if isinstance(legacy, str) else legacy
            text_list(entries, key)
            controls.extend({"kind": kind, "description": item, "status": "unknown", "evidence_refs": [ref(key)]} for item in entries)
            consumed.add(key)
            flags.append(f"{key}_implementation_unconfirmed")
            traces.append({"source_field": key, "target_field": "controls", "status": "normalized", "reason": "legacy_shared_status_ignored; implementation_unknown"})
    if source.get("controls") not in (None, ""):
        structured_controls = source["controls"]
        if isinstance(structured_controls, str):
            structured_controls = strict_loads(structured_controls)
        if not isinstance(structured_controls, list):
            raise ValueError("Source controls must be a list")
        controls.extend(deepcopy(structured_controls))
        consumed.add("controls")
        traces.append({"source_field": "controls", "target_field": "controls", "status": "normalized" if isinstance(source["controls"], str) else "direct"})
    # Row validation enforces shape/status/evidence. Check before indexing malformed data.
    for control in controls:
        if not isinstance(control, dict) or set(control) != {"kind", "description", "status", "evidence_refs"}:
            raise ValueError("Control requires kind, description, status, evidence_refs")
        if control["kind"] not in {"prevention", "detection", "mitigation"} or control["status"] not in {"implemented", "proposed", "unknown"}:
            raise ValueError("Invalid control kind/status")
        require_text(control["description"], "control.description")
        evidence(control["evidence_refs"])
        if not control["evidence_refs"]:
            raise ValueError("Control requires evidence for implementation status")
        if control["status"] != "implemented":
            flags.append(f"{control['kind']}_control_{control['status']}")
    for kind in ("prevention", "detection", "mitigation"):
        destination = f"existing_{kind}_controls"
        values[destination] = [c["description"] for c in controls if c["kind"] == kind and c["status"] == "implemented"]
        if values[destination]:
            refs.append(ref(destination))
        traces.append({"source_field": "controls", "target_field": destination, "status": "normalized" if values[destination] else "unavailable", "reason": "only_individually_implemented_controls"})

    risk = {k: source[k] for k in sorted(RISK_FIELDS) if k in source}
    if risk:
        refs.append(ref("source_risk_data"))
        flags.append("source_ratings_not_crosswalked")
    for key in risk:
        traces.append({"source_field": key, "target_field": f"source_risk_data.{key}", "status": "direct", "reason": "source_scheme_only; no_target_rating_equivalence"})
    consumed.update(risk)
    unmapped = {k: v for k, v in source.items() if k not in consumed}
    if unmapped:
        flags.append("unmapped_source_fields")
    for destination in ("severity", "occurrence", "detection", "rpn", "action_priority"):
        traces.append({"source_field": None, "target_field": destination, "status": "unavailable", "reason": "no_reviewed_crosswalk; target_profile_unrated"})
    unknown = {n: "not_in_source_or_ambiguous" for n in (*TEXT_FIELDS, *LIST_FIELDS) if not values.get(n)}
    row = FMEARow(record_id=f"converted-{index}", **values, controls=controls,
                  unknown_fields=unknown, source_risk_data=risk, provenance_kind="source",
                  conversion_trace_id=trace_id, review_flags=list(dict.fromkeys(flags)),
                  rating_unknown_reason="no_reviewed_crosswalk", evidence_refs=refs)
    row.validate()
    record = {"trace_id": trace_id, "source_sha256": digest(source), "source_snapshot_json": snapshot,
              "original_record": strict_loads(snapshot), "fields": traces,
              "unmapped_fields": unmapped, "review_flags": list(row.review_flags)}
    return row, record


def convert(records, context, profile):
    validate_json(records)
    if not isinstance(records, list) or not records or any(not isinstance(r, dict) for r in records):
        raise ValueError("Source records must be a nonempty list of objects")
    rows, reports = [], []
    for index, source in enumerate(records, 1):
        row, record = _convert_record(source, index)
        rows.append(row)
        reports.append(record)
    draft = FMEADraft(deepcopy(context), profile.profile_id, profile.version, rows,
                      metadata={"conversion_mapping_version": MAPPING_VERSION})
    report = {"mapping_version": MAPPING_VERSION, "artifact_id": draft.artifact_id,
              "artifact_version": draft.artifact_version, "records": reports}
    verify_report(draft, report)
    return draft, report


def verify_report(draft, report):
    """Recompute mappings and source hashes; reject edited or unrelated sidecars."""
    draft.validate()
    validate_json(report)
    if not isinstance(report, dict) or report.get("mapping_version") != MAPPING_VERSION or draft.metadata.get("conversion_mapping_version") != MAPPING_VERSION:
        raise ValueError("Conversion mapping version mismatch")
    if report.get("artifact_id") != draft.artifact_id or report.get("artifact_version") != draft.artifact_version:
        raise ValueError("Conversion report artifact mismatch")
    if not isinstance(report.get("records"), list) or len(report["records"]) != len(draft.rows):
        raise ValueError("Conversion report row count mismatch")
    for index, (row, record) in enumerate(zip(draft.rows, report["records"]), 1):
        snapshot = record.get("source_snapshot_json")
        require_text(snapshot, "source snapshot")
        source = strict_loads(snapshot)
        if snapshot != canonical_json(source) or digest(source) != record.get("source_sha256") or canonical_json(record.get("original_record")) != snapshot:
            raise ValueError("Preserved source checksum mismatch")
        expected_row, expected_record = _convert_record(source, index)
        if record != expected_record:
            raise ValueError("Conversion report differs from verified mapping")
        actual = deepcopy(row.__dict__)
        expected = deepcopy(expected_row.__dict__)
        # Unauthenticated review may change status/decision, but no engineering content or flags.
        for name in ("review_status", "review_decision"):
            actual.pop(name)
            expected.pop(name)
        if actual != expected:
            raise ValueError("Converted row differs from preserved source mapping")
