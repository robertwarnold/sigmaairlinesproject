"""Regression cases from the engineering review; no network or API use."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv

from sigma_fmea.conversion import convert, import_records, verify_report
from sigma_fmea.export import export, verify_bundle
from sigma_fmea.integrity import load_json, strict_loads, validate_json
from sigma_fmea.methodology import get_profile
from sigma_fmea.models import EngineeringContext, FMEADraft
from sigma_fmea.providers import generate, MockProvider

ROOT = Path(__file__).resolve().parents[1]


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.context = EngineeringContext(**load_json(ROOT / "examples/context.json"))
        self.source = load_json(ROOT / "examples/fmeca.json")
        self.profile = get_profile("general")

    def mock(self):
        return generate(self.context, self.profile, MockProvider())

    def test_csv_duplicate_normalized_and_blank_headers(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.csv"
            for headers in ("criticality,criticality", "Criticality, criticality ", "Failure Mode,failure_mode", "criticality,ＣＲＩＴＩＣＡＬＩＴＹ", "item, ", ",item"):
                with self.subTest(headers=headers):
                    path.write_text(headers + "\nA,B\n", encoding="utf-8")
                    with self.assertRaises(ValueError):
                        import_records(path)

    def test_csv_short_long_empty_and_bad_quoting(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.csv"
            for text in ("", "item,criticality\npump\n", "item,criticality\npump,HIGH,LOW\n", 'item,criticality\n"pump,HIGH\n', "item,criticality\n\n"):
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        import_records(path)

    def test_csv_headers_normalize_without_coercing_cells(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.csv"
            path.write_text(' Source ID ,Source Locator,Source Edition,Item,Criticality\ns,row1,1,pump,001\n', encoding="utf-8-sig")
            records = import_records(path)
            draft, report = convert(records, self.context, self.profile)
            self.assertEqual(draft.rows[0].source_risk_data["criticality"], "001")
            self.assertEqual(report["records"][0]["original_record"]["_csv_headers"][0], " Source ID ")

    def test_duplicate_json_keys_rejected_at_every_depth(self):
        for text in ('{"criticality":"H","criticality":"L"}', '[{"risk":{"value":1,"value":2}}]', '{"item":1,"\\u0069tem":2}'):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                strict_loads(text)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.json"
            path.write_text('[{"source_id":"a","source_id":"b"}]')
            with self.assertRaises(ValueError):
                import_records(path)

    def test_nonfinite_and_non_json_values_rejected_before_export(self):
        for value in (float("nan"), float("inf"), -float("inf"), {1: "bad key"}, (1, 2), {1, 2}, b"bytes", object()):
            with self.subTest(value=repr(value)):
                draft = self.mock()
                draft.rows[0].source_risk_data["value"] = value
                with self.assertRaises(ValueError):
                    draft.validate()
                source = copy.deepcopy(self.source)
                source[0]["legacy_value"] = value
                with self.assertRaises(ValueError):
                    convert(source, self.context, self.profile)
        for number in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.assertRaises(ValueError):
                strict_loads('{"x":' + number + '}')

    def test_cyclic_values_rejected(self):
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(ValueError):
            validate_json(cycle)
        draft = self.mock()
        draft.rows[0].source_risk_data["cycle"] = cycle
        with self.assertRaises(ValueError):
            draft.validate()

    def test_mixed_control_statuses_and_consequence_mitigation(self):
        self.source[0].pop("detection_controls")
        controls = []
        for kind, status, description in (("prevention", "implemented", "Interlock"), ("detection", "proposed", "New sensor"), ("mitigation", "implemented", "Emergency isolation"), ("detection", "unknown", "Legacy indicator")):
            controls.append({"kind": kind, "status": status, "description": description, "evidence_refs": [{"source_id": "design", "locator": f"{kind}/{status}", "field": "controls"}]})
        self.source[0]["controls"] = controls
        draft, report = convert(self.source, self.context, self.profile)
        row = draft.rows[0]
        self.assertEqual(row.existing_prevention_controls, ["Interlock"])
        self.assertEqual(row.existing_detection_controls, [])
        self.assertEqual(row.existing_mitigation_controls, ["Emergency isolation"])
        self.assertEqual(row.controls, controls)
        row.existing_detection_controls.append("New sensor")
        row.unknown_fields.pop("existing_detection_controls")
        row.evidence_refs.append({"source_id": "design", "locator": "proposed sensor", "field": "existing_detection_controls"})
        with self.assertRaisesRegex(ValueError, "implementation statuses"):
            row.validate()

    def test_legacy_shared_status_never_implies_existing(self):
        self.source[0]["controls_status"] = "implemented"
        draft, report = convert(self.source, self.context, self.profile)
        self.assertEqual(draft.rows[0].existing_detection_controls, [])
        self.assertEqual(draft.rows[0].controls[0]["status"], "unknown")
        self.assertIn("controls_status", report["records"][0]["unmapped_fields"])

    def test_control_requires_own_evidence(self):
        self.source[0]["controls"] = [{"kind": "detection", "description": "Sensor", "status": "implemented", "evidence_refs": []}]
        with self.assertRaises(ValueError):
            convert(self.source, self.context, self.profile)

    def test_source_and_derived_claims_require_field_evidence(self):
        for origin in ("source", "derived"):
            draft = self.mock()
            draft.rows[0].field_provenance["failure_mode"] = origin
            with self.assertRaisesRegex(ValueError, "Evidence required"):
                draft.validate()
        draft, _ = convert(self.source, self.context, self.profile)
        draft.rows[0].evidence_refs = []
        with self.assertRaises(ValueError):
            draft.validate()

    def test_populated_unknown_and_unknown_field_names_rejected(self):
        for field_name in ("function", "not_a_field"):
            draft = self.mock()
            draft.rows[0].unknown_fields[field_name] = "not_in_source"
            with self.assertRaises(ValueError):
                draft.validate()

    def test_snapshot_detached_from_original_nested_objects(self):
        self.source[0]["criticality_units"] = "source dimensionless category"
        self.source[0]["risk_units"] = {"failure_rate": "per flight hour"}
        draft, report = convert(self.source, self.context, self.profile)
        snapshot = report["records"][0]["source_snapshot_json"]
        original = copy.deepcopy(report)
        self.source[0]["causes"].append("Changed after conversion")
        self.source[0]["risk_units"]["failure_rate"] = "changed"
        self.context.items[0]["name"] = "changed"
        self.assertEqual(report, original)
        self.assertEqual(report["records"][0]["source_snapshot_json"], snapshot)
        self.assertEqual(draft.rows[0].source_risk_data["risk_units"]["failure_rate"], "per flight hour")
        verify_report(draft, report)

    def test_source_hash_mapping_and_flags_tampering_rejected(self):
        for target in ("original_record", "source_snapshot_json", "source_sha256", "fields", "review_flags"):
            draft, report = convert(self.source, self.context, self.profile)
            record = report["records"][0]
            if target == "original_record":
                record[target]["criticality"] = "edited"
            elif target in {"fields", "review_flags"}:
                record[target] = []
            else:
                record[target] = "edited"
            with self.subTest(target=target), self.assertRaises(ValueError):
                verify_report(draft, report)

    def test_original_source_flags_preserved(self):
        self.source[0]["review_flags"] = ["unresolved_extraction_uncertainty"]
        draft, report = convert(self.source, self.context, self.profile)
        self.assertIn("unresolved_extraction_uncertainty", draft.rows[0].review_flags)
        draft.rows[0].review_flags.remove("unresolved_extraction_uncertainty")
        report["artifact_id"], report["artifact_version"] = draft.artifact_id, draft.artifact_version
        with self.assertRaises(ValueError):
            verify_report(draft, report)

    def test_malformed_source_flags_are_not_split_into_characters(self):
        self.source[0]["review_flags"] = "unresolved"
        with self.assertRaises(ValueError):
            convert(self.source, self.context, self.profile)

    def test_each_conversion_write_failure_remains_unpublished(self):
        import sigma_fmea.export as exporter
        real_write = exporter._write_bytes
        for fail_at in range(1, 5):
            with self.subTest(write=fail_at), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "bundle"
                draft, report = convert(self.source, self.context, self.profile)
                count = 0
                def fail_write(path, content):
                    nonlocal count
                    count += 1
                    if count == fail_at:
                        raise OSError("Simulated conversion write failure")
                    real_write(path, content)
                with patch("sigma_fmea.export._write_bytes", side_effect=fail_write):
                    with self.assertRaises(OSError):
                        export(draft, output, report)
                self.assertFalse(output.exists())
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_existing_lock_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "bundle"
            lock = Path(temp) / ".bundle.lock"
            lock.mkdir()
            with self.assertRaises(FileExistsError):
                export(self.mock(), output)
            self.assertFalse(output.exists())
            self.assertTrue(lock.exists())

    def review(self, draft):
        row = draft.rows[0]
        row.review_status = "accepted"
        row.review_decision = {"reviewer": "local-reviewer", "timestamp": "2026-10-31T15:30:00Z", "rationale": "Recorded review; unresolved flags remain", "artifact_version": draft.artifact_version, "unresolved_flags": list(row.review_flags), "authenticated": False}

    def test_review_timestamp_and_content_version_binding(self):
        draft = self.mock()
        self.review(draft)
        draft.validate()
        for timestamp in ("today", "2026-10-31T15:30:00", "2026-02-30T15:30:00Z", "2026-10-31T25:30:00Z", "2026-10-31T15:30:00+00:60"):
            candidate = copy.deepcopy(draft)
            candidate.rows[0].review_decision["timestamp"] = timestamp
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                candidate.validate()
        draft.rows[0].failure_mode = "Edited after review"
        with self.assertRaisesRegex(ValueError, "artifact version"):
            draft.validate()

    def test_review_flags_and_authentication_cannot_be_laundered(self):
        for key, value in (("unresolved_flags", []), ("authenticated", True), ("artifact_version", "0.2")):
            draft = self.mock()
            self.review(draft)
            draft.rows[0].review_decision[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                draft.validate()
        draft = self.mock()
        draft.approval_status = "authenticated"
        with self.assertRaises(ValueError):
            draft.validate()
        draft = self.mock()
        draft.metadata["authenticated_approval"] = True
        with self.assertRaises(ValueError):
            draft.validate()

    def test_converted_review_remains_unauthed_and_report_valid(self):
        draft, report = convert(self.source, self.context, self.profile)
        self.review(draft)
        verify_report(draft, report)
        with tempfile.TemporaryDirectory() as temp:
            export(draft, Path(temp) / "reviewed", report)
            self.assertEqual(verify_bundle(Path(temp) / "reviewed").approval_status, "unauthenticated_draft")

    def test_output_directory_reuse_preserves_old_bundle(self):
        draft, report = convert(self.source, self.context, self.profile)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "bundle"
            export(draft, output, report)
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            with self.assertRaises(FileExistsError):
                export(self.mock(), output)
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})
            verify_bundle(output)

    def test_missing_wrong_or_edited_report_rejected(self):
        draft, report = convert(self.source, self.context, self.profile)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "bundle"
            with self.assertRaises(ValueError):
                export(draft, output)
            with self.assertRaises(ValueError):
                export(self.mock(), output, report)
            report["mapping_version"] = "wrong"
            with self.assertRaises(ValueError):
                export(draft, output, report)
            self.assertFalse(output.exists())

    def test_failed_export_writes_and_publish_leave_no_visible_bundle(self):
        import sigma_fmea.export as exporter
        real_write = exporter._write_bytes
        for failure in ("write", "rename"):
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "bundle"
                count = 0
                def broken_write(path, content):
                    nonlocal count
                    count += 1
                    if count == 2:
                        raise OSError("Simulated disk error")
                    real_write(path, content)
                target = "sigma_fmea.export._write_bytes" if failure == "write" else "sigma_fmea.export.os.rename"
                with patch(target, side_effect=broken_write if failure == "write" else OSError("Simulated publish error")):
                    with self.assertRaises(OSError):
                        export(self.mock(), output)
                self.assertFalse(output.exists())
                self.assertEqual(list(Path(temp).iterdir()), [])
                export(self.mock(), output)
                verify_bundle(output)

    def test_abrupt_interrupt_during_staging_is_not_published(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "bundle"
            with patch("sigma_fmea.export._write_bytes", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    export(self.mock(), output)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_bundle_checksums_identity_csv_and_stale_files(self):
        for failure in ("checksum", "artifact", "csv", "stale"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "bundle"
                export(self.mock(), output)
                manifest = load_json(output / "manifest.json")
                if failure in {"checksum", "csv"}:
                    with (output / "fmea.csv").open("ab") as stream:
                        stream.write(b"extra row\n")
                    if failure == "csv":
                        manifest["files"]["fmea.csv"] = hashlib.sha256((output / "fmea.csv").read_bytes()).hexdigest()
                elif failure == "artifact":
                    manifest["artifact_id"] = "wrong"
                else:
                    (output / "conversion_report.json").write_text("{}")
                (output / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    verify_bundle(output)

    def test_exported_json_detects_content_edits(self):
        data = self.mock().to_dict()
        data["rows"][0]["failure_mode"] = "changed"
        with self.assertRaisesRegex(ValueError, "checksum"):
            FMEADraft.from_dict(data)


class InstalledCLITest(unittest.TestCase):
    def test_installed_console_command_without_source_path_or_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            wheel = os.environ.get("SIGMA_TEST_WHEEL")
            if wheel:
                wheel = Path(wheel).resolve()
            else:
                wheels = temp / "wheels"
                built = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheels), str(ROOT)], capture_output=True, text=True)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                wheel = next(wheels.glob("sigma_fmea-*.whl"))
            environment = temp / "installed"
            venv.EnvBuilder(with_pip=True).create(environment)
            scripts = environment / ("Scripts" if os.name == "nt" else "bin")
            python = scripts / ("python.exe" if os.name == "nt" else "python")
            cli = scripts / ("sigma-fmea.exe" if os.name == "nt" else "sigma-fmea")
            env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_API_KEY"}}
            env["PIP_NO_INDEX"] = "1"
            installed = subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], cwd=temp, env=env, capture_output=True, text=True)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            for command in ("generate", "convert"):
                output = temp / command
                args = [str(cli), command, "--context", str(ROOT / "examples/context.json"), "--profile", "general", "--output", str(output)]
                if command == "convert":
                    args += ["--input", str(ROOT / "examples/fmeca.json")]
                result = subprocess.run(args, cwd=temp, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                checked = subprocess.run([str(cli), "validate", str(output)], cwd=temp, env=env, capture_output=True, text=True)
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            bad = temp / "duplicate.json"
            bad.write_text('{"analysis_id":1,"analysis_id":2}')
            result = subprocess.run([str(cli), "generate", "--context", str(bad), "--profile", "general", "--output", str(temp / "bad-output")], cwd=temp, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Duplicate JSON key", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
