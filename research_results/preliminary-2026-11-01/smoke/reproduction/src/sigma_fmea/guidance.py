"""Small allowlisted guidance corpus. Never searches benchmarks or test fixtures."""
from copy import deepcopy
from .integrity import digest

GUIDANCE_VERSION = "public-guidance-1"
GUIDANCE = [
    {"guidance_id": "asq-workflow", "source_id": "asq", "source_url": "https://asq.org/quality-resources/fmea", "locator": "FMEA procedure", "verification": "public_overview", "profiles": ["general", "dfmea", "pfmea", "aerospace"], "summary": "Organize analysis around intended functions, possible failures, causes, consequences, current controls, and improvement actions. Revisit the analysis when knowledge changes."},
    {"guidance_id": "nasa-effects", "source_id": "nasa-gsfc", "source_url": "https://standards.nasa.gov/node/12367", "locator": "GSFC-HDBK-8004 sections 4.3–4.4", "verification": "reviewed_public_guidance_summary", "profiles": ["general", "dfmea", "pfmea", "aerospace"], "summary": "Keep analysis scope, decomposition level, operating phase and assumptions explicit. Distinguish effects on the item, the next level, and the complete system. Keep detection, prevention, and consequence mitigation distinct."},
    {"guidance_id": "team-unknowns", "source_id": "sigma-team-policy", "source_url": None, "locator": "research prototype policy 1", "verification": "team_policy_not_external_standard", "profiles": ["general", "dfmea", "pfmea", "aerospace"], "summary": "Treat model-generated causes and effects as hypotheses. Leave unsupported content unknown. Never invent implemented controls, frequencies, risk scores, requirements, citations or approval. Consider loss, degradation, intermittent and unintended behavior when applicable."},
]


def retrieve(profile_id, condition):
    if condition not in {"baseline", "improved"}:
        raise ValueError("Condition must be baseline or improved")
    selected = [] if condition == "baseline" else [deepcopy(g) for g in GUIDANCE if profile_id in g["profiles"]]
    return {"version": GUIDANCE_VERSION, "items": selected, "sha256": digest(selected)}
