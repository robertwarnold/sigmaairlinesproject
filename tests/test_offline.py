import copy
from contextlib import redirect_stderr
import csv
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from sigma_fmea.cli import main
from sigma_fmea.conversion import convert, import_records
from sigma_fmea.export import export
from sigma_fmea.methodology import get_profile, registry
from sigma_fmea.models import EngineeringContext, FMEADraft
from sigma_fmea.providers import MockProvider, generate

ROOT = Path(__file__).resolve().parents[1]


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.context = EngineeringContext(**json.loads((ROOT / "examples/context.json").read_text()))
        self.source = json.loads((ROOT / "examples/fmeca.json").read_text())
        self.profile = get_profile("general")

    def test_all_profiles_generate_without_network_or_keys(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(socket, "socket", side_effect=AssertionError("Network forbidden")):
            for name in ("general", "dfmea", "pfmea", "aerospace"):
                draft = generate(self.context, get_profile(name), MockProvider())
                draft.validate()
                self.assertIsNone(draft.rows[0].severity)
                self.assertEqual(draft.rows[0].provenance_kind, "hypothesis")
                self.assertEqual(draft.rows[0].review_status, "needs_review")
        self.assertTrue(all(not p["compliance_claim"] for p in registry()["profiles"]))

    def test_conversion_preserves_risk_and_reports_unknowns(self):
        original = copy.deepcopy(self.source)
        draft, report = convert(self.source, self.context, self.profile)
        row = draft.rows[0]
        self.assertEqual(self.source, original)
        self.assertEqual(report["records"][0]["original_record"], original[0])
        self.assertEqual(row.source_risk_data["severity"], "II")
        self.assertEqual(row.source_risk_data["rpn"], 12)
        self.assertIsNone(row.rpn)
        self.assertIsNone(row.detection)
        self.assertIn("effect_next_level", row.unknown_fields)
        self.assertEqual(row.existing_detection_controls, [])
        self.assertEqual(row.recommended_actions, ["Evaluate pressure monitoring"])
        self.assertIn("legacy_note", report["records"][0]["unmapped_fields"])
        self.assertEqual(convert(self.source, self.context, self.profile)[1], report)

    def test_control_implementation_required(self):
        self.source[0].pop("detection_controls")
        self.source[0]["controls"] = [
            {"kind": kind, "description": description, "status": "implemented", "evidence_refs": [{"source_id": "verified-fixture", "locator": "implemented design record", "field": "controls"}]}
            for kind, description in (("prevention", "Verified interlock"), ("detection", "Pressure indication"))
        ]
        draft, _ = convert(self.source, self.context, self.profile)
        self.assertEqual(draft.rows[0].existing_detection_controls, ["Pressure indication"])
        self.assertEqual(draft.rows[0].existing_prevention_controls, ["Verified interlock"])

    def test_source_locator_required(self):
        del self.source[0]["source_locator"]
        with self.assertRaises(ValueError):
            convert(self.source, self.context, self.profile)

    def test_incompatible_target_ratings_rejected(self):
        draft = generate(self.context, self.profile, MockProvider())
        for value in (3, True, "3", 3.5):
            draft.rows[0].severity = value
            with self.assertRaises(ValueError):
                draft.validate()

    def test_missing_reason_and_duplicate_ids_rejected(self):
        draft = generate(self.context, self.profile, MockProvider())
        draft.rows[0].unknown_fields.pop("effect_local")
        with self.assertRaises(ValueError):
            draft.validate()
        draft = generate(self.context, self.profile, MockProvider())
        draft.rows.append(copy.deepcopy(draft.rows[0]))
        with self.assertRaises(ValueError):
            draft.validate()

    def test_invalid_context_and_profile_rejected(self):
        with self.assertRaises(ValueError):
            EngineeringContext("a", "b", "scope", [{"name": "pump", "function": ""}])
        with self.assertRaises(ValueError):
            get_profile("unknown")

    def test_provider_cannot_approve(self):
        class BadProvider(MockProvider):
            def generate(self, context, profile):
                rows = super().generate(context, profile)
                rows[0].review_status = "accepted"
                rows[0].review_decision = dict(reviewer="invented", timestamp="today", rationale="invented", artifact_version="0.1")
                return rows
        with self.assertRaisesRegex(ValueError, "Providers cannot"):
            generate(self.context, self.profile, BadProvider())

    def test_export_round_trip_and_csv_escaping(self):
        draft = generate(self.context, self.profile, MockProvider())
        draft.rows[0].failure_mode = "=HYPERLINK(1)"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            export(draft, output)
            restored = FMEADraft.from_dict(json.loads((output / "fmea.json").read_text(encoding="utf-8")))
            self.assertEqual(restored.to_dict(), draft.to_dict())
            with (output / "fmea.csv").open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["failure_mode"], "'=HYPERLINK(1)")
            self.assertEqual(json.loads(row["source_risk_data"]), {})

    def test_csv_import_and_malformed_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.source[0])
                writer.writeheader()
                writer.writerow({**self.source[0], "causes": "Drive unavailable", "proposed_mitigations": "Inspect", "controls": json.dumps(self.source[0]["controls"])})
            draft, report = convert(import_records(path), self.context, self.profile)
            self.assertEqual(draft.rows[0].failure_causes, ["Drive unavailable"])
            self.assertEqual(draft.rows[0].source_risk_data["likelihood"], "3")
            path = Path(directory) / "bad.json"
            path.write_text("{}")
            with self.assertRaises(ValueError):
                import_records(path)

    def test_cli_workflow_and_visible_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            for command in ("generate", "convert"):
                output = Path(directory) / command
                args = [command, "--context", str(ROOT / "examples/context.json"), "--profile", "general", "--output", str(output)]
                if command == "convert":
                    args += ["--input", str(ROOT / "examples/fmeca.json")]
                self.assertEqual(main(args), 0)
                self.assertEqual(main(["validate", str(output / "fmea.json")]), 0)
                self.assertTrue((output / "fmea.csv").exists())
            self.assertTrue((Path(directory) / "convert/conversion_report.json").exists())
            bad = Path(directory) / "invalid.json"
            bad.write_text("{}")
            errors = io.StringIO()
            with redirect_stderr(errors):
                self.assertEqual(main(["validate", str(bad)]), 2)
            self.assertIn("Draft missing required fields", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
