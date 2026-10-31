"""Strict JSON-compatible contracts with explicit unknown and review semantics."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
import re

from .integrity import canonical_json, digest, validate_json

from .methodology import get_profile

TEXT_FIELDS = ("function", "failure_mode", "effect_local", "effect_next_level", "effect_end_effect")
LIST_FIELDS = ("failure_causes", "existing_prevention_controls", "existing_detection_controls", "existing_mitigation_controls", "recommended_actions")
CLAIM_FIELDS = ("item_or_process_step", *TEXT_FIELDS, *LIST_FIELDS, "source_risk_data")


def evidence(refs):
    if not isinstance(refs, list):
        raise ValueError("Evidence must be a list")
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError("Evidence must be an object")
        for key in ("source_id", "locator", "field"):
            require_text(ref.get(key), f"evidence.{key}")


def require_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def text_list(value, name):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f"{name} must be a list of nonempty strings")


@dataclass
class EngineeringContext:
    analysis_id: str
    system_id: str
    scope: str
    items: list[dict]
    hierarchy_level: str = "unspecified"
    operating_phase: str = "unspecified"
    assumptions: list[str] = field(default_factory=list)
    requirement_refs: list[str] = field(default_factory=list)
    interface_refs: list[str] = field(default_factory=list)

    def __post_init__(self):
        validate_json(vars(self))
        for name in ("analysis_id", "system_id", "scope", "hierarchy_level", "operating_phase"):
            require_text(getattr(self, name), name)
        for name in ("assumptions", "requirement_refs", "interface_refs"):
            text_list(getattr(self, name), name)
        if not isinstance(self.items, list) or not self.items:
            raise ValueError("items must be a nonempty list")
        for item in self.items:
            if not isinstance(item, dict) or set(item) != {"name", "function"}:
                raise ValueError("Each context item requires exactly name and function")
            require_text(item["name"], "item.name")
            require_text(item["function"], "item.function")


@dataclass
class FMEARow:
    record_id: str
    item_or_process_step: str
    function: str | None = None
    failure_mode: str | None = None
    failure_causes: list[str] = field(default_factory=list)
    effect_local: str | None = None
    effect_next_level: str | None = None
    effect_end_effect: str | None = None
    existing_prevention_controls: list[str] = field(default_factory=list)
    existing_detection_controls: list[str] = field(default_factory=list)
    existing_mitigation_controls: list[str] = field(default_factory=list)
    controls: list[dict] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    severity: int | None = None
    occurrence: int | None = None
    detection: int | None = None
    rpn: int | None = None
    action_priority: str | None = None
    rating_profile_id: str | None = None
    rating_basis: str | None = None
    rating_unknown_reason: str = "needs_engineer_rating"
    unknown_fields: dict[str, str] = field(default_factory=dict)
    evidence_refs: list[dict] = field(default_factory=list)
    provenance_kind: str = "hypothesis"
    field_provenance: dict[str, str] = field(default_factory=dict)
    review_status: str = "needs_review"
    review_decision: dict | None = None
    review_flags: list[str] = field(default_factory=list)
    source_risk_data: dict = field(default_factory=dict)
    conversion_trace_id: str | None = None

    def validate(self):
        validate_json(vars(self))
        for name in ("record_id", "item_or_process_step", "rating_unknown_reason"):
            require_text(getattr(self, name), name)
        for name in ("function", "failure_mode", "effect_local", "effect_next_level", "effect_end_effect", "rating_profile_id", "rating_basis", "conversion_trace_id"):
            if getattr(self, name) is not None:
                require_text(getattr(self, name), name)
        for name in (*LIST_FIELDS, "review_flags"):
            text_list(getattr(self, name), name)
        if self.provenance_kind not in {"source", "derived", "hypothesis"}:
            raise ValueError("Invalid provenance_kind")
        if self.review_status not in {"draft", "needs_review", "accepted", "rejected"}:
            raise ValueError("Invalid review_status")
        if not isinstance(self.unknown_fields, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in self.unknown_fields.items()):
            raise ValueError("unknown_fields must map fields to reasons")
        for name, reason in self.unknown_fields.items():
            if name not in (*TEXT_FIELDS, *LIST_FIELDS):
                raise ValueError(f"Unknown field name: {name}")
            require_text(reason, "unknown reason")
            if getattr(self, name):
                raise ValueError(f"Populated field marked unknown: {name}")
        for name in (*TEXT_FIELDS, *LIST_FIELDS):
            if not getattr(self, name) and name not in self.unknown_fields:
                raise ValueError(f"Missing unknown reason: {name}")
        if not isinstance(self.source_risk_data, dict):
            raise ValueError("source_risk_data must be an object")
        evidence(self.evidence_refs)
        if not isinstance(self.field_provenance, dict):
            raise ValueError("field_provenance must be an object")
        for name, origin in self.field_provenance.items():
            if name not in CLAIM_FIELDS or origin not in {"source", "derived", "hypothesis"}:
                raise ValueError("Invalid field provenance")
        for name in CLAIM_FIELDS:
            if getattr(self, name):
                origin = self.field_provenance.get(name, self.provenance_kind)
                if origin in {"source", "derived"} and not any(r["field"] == name for r in self.evidence_refs):
                    raise ValueError(f"Evidence required for source-backed field: {name}")
        self._validate_controls()
        # All initial profiles are unrated. A future reviewed scoring policy must
        # explicitly enable ratings; numeric range alone is not compatibility.
        if any(getattr(self, n) is not None for n in ("severity", "occurrence", "detection", "rpn", "action_priority", "rating_profile_id")):
            raise ValueError("Initial unrated profiles cannot accept target ratings or prioritization")
        if self.review_status in {"accepted", "rejected"} and self.review_decision is None:
            raise ValueError("Review decision required")
        if self.review_status in {"draft", "needs_review"} and self.review_decision is not None:
            raise ValueError("Draft review state contradicts decision")

    def _validate_controls(self):
        if not isinstance(self.controls, list):
            raise ValueError("controls must be a list")
        existing = {k: [] for k in ("prevention", "detection", "mitigation")}
        for control in self.controls:
            if not isinstance(control, dict) or set(control) != {"kind", "description", "status", "evidence_refs"}:
                raise ValueError("Control requires kind, description, status, evidence_refs")
            if control["kind"] not in existing or control["status"] not in {"implemented", "proposed", "unknown"}:
                raise ValueError("Invalid control kind/status")
            require_text(control["description"], "control.description")
            evidence(control["evidence_refs"])
            if not control["evidence_refs"]:
                raise ValueError("Control requires source evidence, including implementation status")
            if control["status"] == "implemented":
                existing[control["kind"]].append(control["description"])
        for kind, descriptions in existing.items():
            if getattr(self, f"existing_{kind}_controls") != descriptions:
                raise ValueError(f"Existing {kind} controls disagree with independent implementation statuses")


@dataclass
class FMEADraft:
    context: EngineeringContext
    profile_id: str
    profile_version: str
    rows: list[FMEARow]
    schema_version: str = "0.2"
    label: str = "FMEA draft — engineering review required"
    metadata: dict = field(default_factory=dict)
    approval_status: str = "unauthenticated_draft"

    @property
    def artifact_version(self):
        content = asdict(self)
        for row in content["rows"]:
            row.pop("review_decision")
            row.pop("review_status")
        return "sha256:" + digest(content)

    @property
    def artifact_id(self):
        return "fmea:" + self.artifact_version.removeprefix("sha256:")

    def validate(self):
        if not isinstance(self.context, EngineeringContext) or not isinstance(self.rows, list) or any(not isinstance(r, FMEARow) for r in self.rows):
            raise ValueError("Draft requires typed context and rows")
        validate_json({**vars(self), "context": vars(self.context), "rows": [vars(r) for r in self.rows]})
        self.context.__post_init__()
        profile = get_profile(self.profile_id)
        if self.profile_version != profile.version or self.schema_version != "0.2":
            raise ValueError("Unsupported schema/profile version")
        if self.label != "FMEA draft — engineering review required":
            raise ValueError("Invalid draft label")
        if self.approval_status != "unauthenticated_draft":
            raise ValueError("Authenticated engineering approval cannot be asserted")
        if not isinstance(self.metadata, dict) or set(self.metadata) - {"provider", "conversion_mapping_version"}:
            raise ValueError("Unsupported metadata keys; approval claims are forbidden")
        for value in self.metadata.values():
            require_text(value, "metadata value")
        if not isinstance(self.metadata, dict) or not isinstance(self.rows, list) or not self.rows:
            raise ValueError("Draft requires metadata object and nonempty rows")
        ids = set()
        for row in self.rows:
            row.validate()
            if row.record_id in ids:
                raise ValueError(f"Duplicate record_id: {row.record_id}")
            ids.add(row.record_id)
            if row.review_decision is not None:
                self._validate_decision(row)

    def _validate_decision(self, row):
        decision = row.review_decision
        expected = {"reviewer", "timestamp", "rationale", "artifact_version", "unresolved_flags", "authenticated"}
        if not isinstance(decision, dict) or set(decision) != expected:
            raise ValueError("Review decision requires explicit unauthenticated metadata and unresolved flags")
        for key in ("reviewer", "timestamp", "rationale", "artifact_version"):
            require_text(decision[key], f"review_decision.{key}")
        timestamp = decision["timestamp"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", timestamp):
            raise ValueError("Review timestamp requires ISO 8601 date, time and timezone")
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Invalid review timestamp") from error
        if timestamp[-1] != "Z" and (int(timestamp[-5:-3]) > 23 or int(timestamp[-2:]) > 59):
            raise ValueError("Invalid review timezone offset")
        if decision["artifact_version"] != self.artifact_version:
            raise ValueError("Review decision does not match artifact version")
        if decision["authenticated"] is not False:
            raise ValueError("Authenticated engineering approval cannot be asserted")
        if decision["unresolved_flags"] != row.review_flags:
            raise ValueError("Review decision must preserve all unresolved flags")

    def to_dict(self):
        self.validate()
        return {**asdict(self), "artifact_id": self.artifact_id, "artifact_version": self.artifact_version}

    @classmethod
    def from_dict(cls, data):
        validate_json(data)
        if not isinstance(data, dict):
            raise ValueError("Draft must be an object")
        missing = {"context", "profile_id", "profile_version", "rows", "artifact_id", "artifact_version"} - data.keys()
        if missing:
            raise ValueError(f"Draft missing required fields: {', '.join(sorted(missing))}")
        content = dict(data)
        artifact_id, version = content.pop("artifact_id"), content.pop("artifact_version")
        result = cls(**{**content, "context": EngineeringContext(**content["context"]), "rows": [FMEARow(**r) for r in content["rows"]]})
        result.validate()
        if artifact_id != result.artifact_id or version != result.artifact_version:
            raise ValueError("FMEA artifact checksum mismatch")
        return result
