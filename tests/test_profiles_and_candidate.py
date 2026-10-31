import copy
from pathlib import Path
import tempfile
import unittest

from sigma_fmea.conversion import convert, verify_report
from sigma_fmea.export import export, verify_bundle
from sigma_fmea.integrity import load_json, digest
from sigma_fmea.methodology import get_profile, registry, scope_assessment
from sigma_fmea.models import EngineeringContext
from sigma_fmea.providers import generate, MockProvider

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.context = EngineeringContext(**load_json(ROOT / "examples/context.json"))

    def test_profiles_have_distinct_scope_workflow_and_mock_hypotheses(self):
        profiles = [get_profile(n) for n in ("general", "dfmea", "pfmea", "aerospace")]
        self.assertEqual(len({p.workflow_steps for p in profiles}), 4)
        self.assertEqual(len({p.context_requirements for p in profiles}), 4)
        self.assertEqual(len({generate(self.context, p, MockProvider()).rows[0].failure_mode for p in profiles}), 4)
        for profile in profiles:
            self.assertFalse(profile.compliance_claim)
            self.assertEqual(profile.rating_policy, "unrated")
            self.assertEqual(profile.verification_status, "preliminary_unverified_team_policy")

    def test_missing_profile_context_is_flagged_not_filled(self):
        profile = get_profile("dfmea")
        assessment = scope_assessment(self.context, profile)
        self.assertEqual(assessment["missing_context"], ["requirement_refs", "interface_refs"])
        draft = generate(self.context, profile, MockProvider())
        self.assertEqual(draft.context.requirement_refs, [])
        self.assertTrue(set(assessment["review_flags"]).issubset(draft.rows[0].review_flags))
        draft.rows[0].review_flags.remove(assessment["review_flags"][0])
        with self.assertRaisesRegex(ValueError, "scope review flags"):
            draft.validate()

    def test_present_profile_context_clears_only_scope_gaps(self):
        self.context.requirement_refs = ["team-requirement-1"]
        self.context.interface_refs = ["team-interface-1"]
        profile = get_profile("dfmea")
        self.assertEqual(scope_assessment(self.context, profile)["missing_context"], [])
        draft = generate(self.context, profile, MockProvider())
        self.assertIn("mock_hypothesis_not_engineering_evidence", draft.rows[0].review_flags)
        self.assertIsNone(draft.rows[0].severity)

    def test_legacy_profile_bundle_still_validates(self):
        legacy = get_profile("general", "0.2")
        draft = generate(self.context, legacy, MockProvider())
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "legacy"
            export(draft, output)
            self.assertEqual(verify_bundle(output).profile_version, "0.2")
        with self.assertRaises(ValueError):
            get_profile("general", "unverified-version")

    def test_registry_cannot_be_mutated_through_export(self):
        result = registry()
        result["sources"][0]["title"] = "changed"
        self.assertNotEqual(registry()["sources"][0]["title"], "changed")


class NASACandidateTests(unittest.TestCase):
    def test_two_row_source_candidate_is_loss_aware_not_approved(self):
        context = EngineeringContext(**load_json(ROOT / "tests/fixtures/nasa_2019_context.json"))
        source = load_json(ROOT / "tests/fixtures/nasa_2019_candidate.json")
        manifest = load_json(ROOT / "tests/fixtures/nasa_2019_candidate_manifest.json")
        self.assertEqual(digest(source), manifest["fixture_canonical_sha256"])
        self.assertEqual(manifest["benchmark_status"], "not_approved_ground_truth")
        draft, report = convert(source, context, get_profile("aerospace"))
        self.assertEqual(len(draft.rows), 2)
        for row, record, original in zip(draft.rows, report["records"], source):
            for source_field, target_field in (("function", "function"), ("failure_mode", "failure_mode"), ("causes", "failure_causes"), ("local_effect", "effect_local"), ("next_level_effect", "effect_next_level"), ("end_effect", "effect_end_effect")):
                self.assertEqual(getattr(row, target_field), original[source_field])
            for field in ("criticality", "criticality_units", "failure_rate", "failure_rate_units", "severity", "alpha", "beta", "mission_time", "mission_time_units"):
                self.assertEqual(row.source_risk_data[field], original[field])
            self.assertTrue(all(getattr(row, n) is None for n in ("severity", "occurrence", "detection", "rpn")))
            self.assertEqual(row.existing_prevention_controls, [])
            self.assertEqual(row.existing_detection_controls, [])
            self.assertEqual(row.existing_mitigation_controls, [])
            self.assertEqual(row.recommended_actions, [])
            self.assertEqual([c["kind"] for c in row.controls], ["detection", "mitigation"])
            self.assertTrue(all(c["status"] == "unknown" for c in row.controls))
            self.assertEqual(row.review_status, "needs_review")
            self.assertIn("candidate_not_reviewed_benchmark", row.review_flags)
            self.assertIn("aerospace_scope_missing_interface_refs", row.review_flags)
            self.assertIn("source_mission_phase", record["unmapped_fields"])
            self.assertEqual(record["original_record"], original)
        self.assertEqual(draft.rows[0].source_risk_data["criticality"], "3.20E-07")
        self.assertEqual(draft.rows[1].source_risk_data["criticality"], "6.00E-08")
        verify_report(draft, report)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "candidate"
            export(draft, output, report)
            self.assertEqual(verify_bundle(output).approval_status, "unauthenticated_draft")
