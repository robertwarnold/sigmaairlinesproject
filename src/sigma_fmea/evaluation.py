"""Deterministic research metrics. Completeness is not engineering correctness."""
from datetime import datetime
import re
from .integrity import digest, validate_json

RUBRIC_VERSION = "content-completeness-1"
CONTENT_FIELDS = ("item_or_process_step", "function", "failure_mode", "failure_causes", "effect_local", "effect_next_level", "effect_end_effect", "recommended_actions")
UNKNOWN = {"unknown", "not provided", "not in source", "not applicable", "n/a", "none", "tbd", "unspecified"}


def normalize(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def populated(value):
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().casefold() not in UNKNOWN
    if isinstance(value, list):
        return any(populated(item) for item in value)
    return False


def reference_coverage(draft, reference):
    unavailable = {"missed_failure_modes_pct": None, "reference_mode_count": None, "matched_reference_modes": None,
                   "coverage_status": "no_reviewed_reference", "reference_sha256": None, "matching_rule": "exact_normalized_item_and_mode_or_reviewed_alias; one_to_one"}
    if reference is None:
        return unavailable
    validate_json(reference)
    unavailable["reference_sha256"] = digest(reference)
    if reference.get("review_status") != "reviewed":
        unavailable["coverage_status"] = "reference_unreviewed_not_ground_truth"
        return unavailable
    for key in ("system_id", "reviewer", "reviewed_on", "scope", "reference_version"):
        if not isinstance(reference.get(key), str) or not reference[key].strip():
            raise ValueError(f"Reviewed reference requires {key}")
    datetime.fromisoformat(reference["reviewed_on"])
    if reference["system_id"] != draft.context.system_id:
        raise ValueError("Reference system differs from generated system")
    modes = reference.get("modes")
    if not isinstance(modes, list) or not modes:
        raise ValueError("Reviewed reference requires eligible modes; zero denominator is not a score")
    ids, adjacency = set(), []
    for mode in modes:
        for key in ("reference_id", "item", "mode"):
            if not isinstance(mode.get(key), str) or not mode[key].strip():
                raise ValueError(f"Reference mode requires {key}")
        if mode["reference_id"] in ids:
            raise ValueError("Duplicate reference mode ID")
        ids.add(mode["reference_id"])
        aliases = mode.get("accepted_aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
            raise ValueError("accepted_aliases requires reviewed nonempty strings")
        accepted = {normalize(s) for s in [mode["mode"], *aliases]}
        adjacency.append([i for i, row in enumerate(draft.rows) if normalize(row.item_or_process_step) == normalize(mode["item"]) and row.failure_mode and normalize(row.failure_mode) in accepted])
    # Maximum bipartite match: one generated row cannot satisfy several references.
    occupied = {}
    def match(reference_index, seen):
        for row_index in adjacency[reference_index]:
            if row_index not in seen:
                seen.add(row_index)
                if row_index not in occupied or match(occupied[row_index], seen):
                    occupied[row_index] = reference_index
                    return True
        return False
    count = sum(match(i, set()) for i in range(len(modes)))
    return {**unavailable, "missed_failure_modes_pct": 100 * (len(modes) - count) / len(modes),
            "reference_mode_count": len(modes), "matched_reference_modes": count,
            "coverage_status": "reviewed_reference_exact_matching; semantic_adjudication_not_performed"}


def evaluate(draft, reference=None):
    draft.validate()
    filled = sum(populated(getattr(row, name)) for row in draft.rows for name in CONTENT_FIELDS)
    denominator = len(draft.rows) * len(CONTENT_FIELDS)
    flags = [flag for row in draft.rows for flag in row.review_flags]
    return {"rubric_version": RUBRIC_VERSION, "artifact_id": draft.artifact_id,
            "structural_completeness_pct": 100 * filled / denominator,
            "completed_content_cells": filled, "eligible_content_cells": denominator,
            "completeness_fields": list(CONTENT_FIELDS), "schema_valid": True,
            "generated_failure_modes": sum(populated(row.failure_mode) for row in draft.rows),
            "generated_rows": len(draft.rows), "validation_errors": [], "validation_error_count": 0,
            "unresolved_review_flag_count": len(flags), "unique_review_flags": sorted(set(flags)),
            "unknown_field_count": sum(len(row.unknown_fields) for row in draft.rows),
            "rating_evaluation": "not_applicable; selected profiles are unrated",
            **reference_coverage(draft, reference)}
