"""Validate financial input records without reading engineering reference answers."""
from datetime import datetime
import json
import math
from pathlib import Path

# Stage names and minutes are explicit so waiting is never silently billed as labor.
STAGES = {"initial_development", "preparation", "generation_supervision", "engineering_review",
          "correction", "peer_review", "approval", "failure_recovery", "skill_maintenance"}
METHODS = {"manual", "ai_assisted"}
IDENTITY = ("experiment_id", "system_id", "input_hash", "workflow", "skill_version", "skill_hash",
            "model", "configuration_id", "scope_id", "criteria_id")
LABOR_FIELDS = (*IDENTITY, "case_id", "engineer_id", "stage", "active_engineering_minutes",
                "passive_waiting_minutes", "rework_minutes", "review_minutes", "started_at", "finished_at",
                "method", "approval_status", "notes", "evidence_source")
QUALITY_FIELDS = (*IDENTITY, "case_id", "method", "reviewer_id", "independent_review", "decision",
                  "missing_modes", "unsupported_modes", "unit_expansion_corrections", "technical_corrections",
                  "unsupported_assumptions", "rating_corrections", "evidence_source")


def number(value, name, nullable=False):
    """Return a finite nonnegative number; a blank is missing, never zero."""
    # Reject booleans and nonfinite values before they enter financial arithmetic.
    if nullable and (value is None or value == ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name}: boolean is not a numeric measurement")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: expected a number") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name}: expected a finite nonnegative number")
    return result


def read_json(path):
    """Reject duplicate keys and nonfinite JSON rather than silently repairing data."""
    def unique(pairs):
        # A duplicate field could otherwise replace an invoice or acceptance decision.
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Nonfinite JSON number: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=invalid)


def validate_records(rows, kind):
    """Validate labor or aggregate quality rows; return typed copies, not mutations."""
    # Required identifiers keep systems, prompt versions and quality conditions separate.
    if kind not in {"labor", "quality"}:
        raise ValueError("Unknown record kind")
    fields = LABOR_FIELDS if kind == "labor" else QUALITY_FIELDS
    result, seen = [], set()
    for source in rows:
        if set(fields) - source.keys():
            raise ValueError(f"Missing {kind} columns: {sorted(set(fields) - source.keys())}")
        row = dict(source)
        if any(value is None for value in row.values()):
            raise ValueError("Missing record values; use explicit blank strings for optional fields")
        for name in (*IDENTITY, "case_id", "method", "evidence_source"):
            if not str(row[name]).strip():
                raise ValueError(f"Blank {name}; use 'not_applicable' for manual skill/model fields")
        if row["method"] not in METHODS:
            raise ValueError("Unknown development method")
        if kind == "labor":
            # The three active buckets are mutually exclusive; passive minutes are separate.
            if row["stage"] not in STAGES or not row["engineer_id"].strip():
                raise ValueError("Invalid labor stage or engineer identity")
            for name in ("active_engineering_minutes", "passive_waiting_minutes", "rework_minutes", "review_minutes"):
                row[name] = number(row[name], name)
            start, end = row["started_at"], row["finished_at"]
            if bool(start) != bool(end):
                raise ValueError("Provide both timestamps or neither")
            if start:
                a, b = (datetime.fromisoformat(x.replace("Z", "+00:00")) for x in (start, end))
                if a.utcoffset() is None or b.utcoffset() is None or b < a:
                    raise ValueError("Timestamps require zones and ordered endpoints")
                minutes = (b - a).total_seconds() / 60
                if sum(row[n] for n in ("active_engineering_minutes", "rework_minutes", "review_minutes",
                                        "passive_waiting_minutes")) > minutes + 0.02:
                    raise ValueError("Recorded minutes exceed the stage's elapsed interval")
            # Repeated rows are usually an accidental second import, not extra labor.
            key = tuple(str(row[n]) for n in fields)
        else:
            # Accept only independently reviewed decisions, and never treat generation success as acceptance.
            if row["decision"] not in {"accepted", "rejected", "pending"}:
                raise ValueError("Invalid quality decision")
            if row["independent_review"] not in {"true", "false"}:
                raise ValueError("independent_review must be true or false")
            if row["decision"] != "pending" and (not row["reviewer_id"] or row["independent_review"] != "true"):
                raise ValueError("A decided quality record requires independent reviewer evidence")
            for name in ("missing_modes", "unsupported_modes", "unit_expansion_corrections", "technical_corrections",
                         "unsupported_assumptions", "rating_corrections"):
                row[name] = number(row[name], name, nullable=True)
                if row[name] is not None and row[name] != int(row[name]):
                    raise ValueError("Quality correction counts must be integers")
            key = tuple(row[n] for n in (*IDENTITY, "case_id", "method"))
        if key in seen:
            raise ValueError(f"Duplicate {kind} record")
        seen.add(key)
        result.append(row)
    return result
