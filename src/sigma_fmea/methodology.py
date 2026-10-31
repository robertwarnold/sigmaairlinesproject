"""Versioned team profiles; bibliographic references do not imply compliance."""
from dataclasses import dataclass, asdict


SOURCES = [
    {"source_id": "iec-60812", "title": "IEC 60812:2018", "publisher": "IEC", "edition": "2018", "url": "https://webstore.iec.ch/en/publication/26359", "access": "licensed_text_not_verified", "verification": "bibliography_only", "locator": None},
    {"source_id": "aiag-vda", "title": "AIAG–VDA FMEA Handbook", "publisher": "AIAG/VDA", "edition": "2019; printing and errata require verification", "url": "https://www.aiag.org/training-and-resources/manuals/details/FMEAAV-1", "access": "licensed_text_not_verified", "verification": "bibliography_only", "locator": None},
    {"source_id": "sae-j1739", "title": "SAE J1739", "publisher": "SAE", "edition": "J1739_202605; applicability requires review", "url": "https://doi.org/10.4271/J1739_202605", "access": "licensed_text_not_verified", "verification": "bibliography_only", "locator": None},
    {"source_id": "asq", "title": "Failure Mode and Effects Analysis", "publisher": "ASQ", "edition": "undated public overview", "url": "https://asq.org/quality-resources/fmea", "access": "public_reading; redistribution_not_assumed", "verification": "public_overview", "locator": "FMEA procedure"},
    {"source_id": "nasa-gsfc", "title": "GSFC-HDBK-8004", "publisher": "NASA GSFC", "edition": "2024-08-20 baseline", "url": "https://standards.nasa.gov/node/12367", "access": "public_guidance", "verification": "local_text_review; tables_require_visual_verification", "locator": "4.3, 4.4, Appendix C"},
]


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


PROFILES = {
    "general": Profile("general", "General FMEA"),
    "dfmea": Profile("dfmea", "DFMEA"),
    "pfmea": Profile("pfmea", "PFMEA"),
    "aerospace": Profile("aerospace", "Aerospace FMEA", sources=("asq", "nasa-gsfc")),
}


def get_profile(profile_id: str) -> Profile:
    try:
        return PROFILES[profile_id]
    except (KeyError, TypeError):
        raise ValueError(f"Unknown methodology profile: {profile_id}") from None


def registry() -> dict:
    return {"sources": SOURCES, "profiles": [asdict(p) for p in PROFILES.values()]}
