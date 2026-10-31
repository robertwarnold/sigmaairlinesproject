"""Versioned team profiles; bibliographic references do not imply compliance."""
from dataclasses import dataclass, asdict
from copy import deepcopy


SOURCES = [
    {"source_id": "iec-60812", "title": "IEC 60812:2018", "publisher": "IEC", "edition": "2018", "url": "https://webstore.iec.ch/en/publication/26359", "access": "licensed_text_not_verified", "verification": "bibliography_only", "locator": None},
    {"source_id": "aiag-vda", "title": "AIAG–VDA FMEA Handbook", "publisher": "AIAG/VDA", "edition": "2019; printing and errata require verification", "url": "https://www.aiag.org/training-and-resources/manuals/details/FMEAAV-1", "access": "licensed_text_not_verified", "verification": "bibliography_only", "locator": None},
    {"source_id": "sae-j1739", "title": "SAE J1739", "publisher": "SAE", "edition": "J1739_202605; applicability requires review", "url": "https://doi.org/10.4271/J1739_202605", "access": "licensed_text_not_verified", "verification": "bibliography_only", "locator": None},
    {"source_id": "asq", "title": "Failure Mode and Effects Analysis", "publisher": "ASQ", "edition": "undated public overview", "url": "https://asq.org/quality-resources/fmea", "access": "public_reading; redistribution_not_assumed", "verification": "public_overview", "locator": "FMEA procedure"},
    {"source_id": "nasa-gsfc", "title": "GSFC-HDBK-8004", "publisher": "NASA GSFC", "edition": "2024-08-20 baseline", "url": "https://standards.nasa.gov/node/12367", "access": "public_guidance", "verification": "local_text_review; tables_require_visual_verification", "locator": "4.3, 4.4, Appendix C"},
]

# Source metadata only; fixture answers are never loaded by the generation package.
SOURCES.append({
    "source_id": "NASA-CR-2019-220217", "title": "Hazards Analysis and FMECA of Four Concept Vehicle Propulsion Systems",
    "publisher": "NASA Glenn / Boeing", "edition": "June 2019",
    "url": "https://ntrs.nasa.gov/citations/20190026443",
    "access": "public; NTRS catalog states Public Use Permitted",
    "verification": "two selected rows visually compared by agent; independent engineering review pending",
    "locator": "section 8.1; Table B-1, printed B-1, rows 1A1/1B1",
    "source_type": "conversion_validation_candidate", "allowed_role": "conversion_validation_only",
    "generation_use": "prohibited_for_this_evaluation_case", "verified_on": "2026-10-31",
})


@dataclass(frozen=True)
class Profile:
    profile_id: str
    analysis_type: str
    version: str = "0.2"
    verification_status: str = "preliminary_unverified_team_policy"
    rule_origin: str = "team_policy"
    rating_policy: str = "unrated"
    sources: tuple[str, ...] = ("asq",)
    compliance_claim: bool = False
    workflow_steps: tuple[str, ...] = ()
    context_requirements: tuple[str, ...] = ()
    review_questions: tuple[str, ...] = ()
    mock_mode_prefix: str = "Loss of function"


LEGACY_PROFILES = {
    "general": Profile("general", "General FMEA"),
    "dfmea": Profile("dfmea", "DFMEA"),
    "pfmea": Profile("pfmea", "PFMEA"),
    "aerospace": Profile("aerospace", "Aerospace FMEA", sources=("asq", "nasa-gsfc")),
}

# Explicit team policies, not transcriptions of licensed methodology requirements.
PROFILES = {
    "general": Profile("general", "General FMEA", version="0.3",
        workflow_steps=("Define scope", "List functions", "Identify failures and effects", "Review evidence and actions"),
        context_requirements=("hierarchy_level",),
        review_questions=("Is the analysis boundary explicit?", "Are absent controls distinguished from unknown controls?")),
    "dfmea": Profile("dfmea", "DFMEA", version="0.3",
        workflow_steps=("Define design boundary and interfaces", "Link design functions to requirements", "Review design failure mechanisms", "Review design prevention and verification controls"),
        context_requirements=("hierarchy_level", "requirement_refs", "interface_refs"),
        review_questions=("Which design requirement is not met?", "Which interface propagates the effect?", "Is a control design prevention, verification, or consequence mitigation?"),
        mock_mode_prefix="Design fails to deliver function"),
    "pfmea": Profile("pfmea", "PFMEA", version="0.3",
        workflow_steps=("Define process sequence", "Identify each step's intended output", "Review process-step errors", "Review process prevention and detection controls"),
        context_requirements=("operating_phase", "requirement_refs", "assumptions"),
        review_questions=("Are items actual process steps in the intended order?", "What output should each step produce?", "Which controls act before or after the process error?"),
        mock_mode_prefix="Process step fails to achieve output"),
    "aerospace": Profile("aerospace", "Aerospace FMEA", version="0.3", sources=("asq", "nasa-gsfc"),
        workflow_steps=("Define mission phase and system hierarchy", "Identify functional and interface failures", "Trace local, next-level and mission effects", "Review detection, recovery and mitigation assumptions"),
        context_requirements=("hierarchy_level", "operating_phase", "interface_refs", "assumptions"),
        review_questions=("Which mission phase is affected?", "Are local, next-level and mission effects distinct?", "Are recovery assumptions evidenced rather than treated as prevention?"),
        mock_mode_prefix="Loss of mission function"),
}


def get_profile(profile_id: str, version: str | None = None) -> Profile:
    try:
        profile = (LEGACY_PROFILES if version == "0.2" else PROFILES)[profile_id]
        if version is not None and profile.version != version:
            raise KeyError(version)
        return profile
    except (KeyError, TypeError):
        raise ValueError(f"Unknown methodology profile/version: {profile_id}/{version}") from None


def scope_assessment(context, profile):
    """Missing evidence becomes a review flag; never fill scope from model guesses."""
    gaps = [name for name in profile.context_requirements if not getattr(context, name) or getattr(context, name) == "unspecified"]
    return {"profile_id": profile.profile_id, "profile_version": profile.version,
            "rule_origin": profile.rule_origin, "verification_status": profile.verification_status,
            "missing_context": gaps,
            "review_flags": [f"{profile.profile_id}_scope_missing_{name}" for name in gaps],
            "workflow_steps": list(profile.workflow_steps), "review_questions": list(profile.review_questions)}


def registry() -> dict:
    return {"sources": deepcopy(SOURCES), "profiles": [asdict(p) for p in PROFILES.values()],
            "supported_legacy_profile_versions": ["0.2"]}
