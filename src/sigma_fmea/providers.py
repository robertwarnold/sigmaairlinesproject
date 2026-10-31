"""Provider boundary shared by future local/cloud adapters."""
from typing import Protocol
from .models import EngineeringContext, FMEARow
from copy import deepcopy
from .methodology import Profile, scope_assessment


class Provider(Protocol):
    provider_id: str

    def generate(self, context: EngineeringContext, profile: Profile) -> list[FMEARow]: ...


class MockProvider:
    provider_id = "mock-v0.1"

    def generate(self, context: EngineeringContext, profile: Profile) -> list[FMEARow]:
        return [FMEARow(
            record_id=f"mock-{i}", item_or_process_step=item["name"],
            function=item["function"],
            failure_mode=f"{profile.mock_mode_prefix}: {item['function']}",
            unknown_fields={n: "not_in_context" for n in ("effect_local", "effect_next_level", "effect_end_effect", "failure_causes", "existing_prevention_controls", "existing_detection_controls", "existing_mitigation_controls", "recommended_actions")},
            field_provenance={"item_or_process_step": "source", "function": "source", "failure_mode": "hypothesis"},
            evidence_refs=[{"source_id": context.system_id, "locator": f"context.items[{i-1}]", "field": name} for name in ("item_or_process_step", "function")],
            review_flags=["mock_hypothesis_not_engineering_evidence", "effects_causes_controls_and_ratings_require_review", *scope_assessment(context, profile)["review_flags"]],
        ) for i, item in enumerate(context.items, 1)]


def generate(context: EngineeringContext, profile: Profile, provider: Provider):
    from .models import FMEADraft
    draft = FMEADraft(deepcopy(context), profile.profile_id, profile.version,
                      provider.generate(deepcopy(context), profile), metadata={"provider": provider.provider_id})
    if any(r.review_status not in {"draft", "needs_review"} or r.review_decision is not None for r in draft.rows):
        raise ValueError("Providers cannot create engineering approval decisions")
    draft.validate()
    return draft
