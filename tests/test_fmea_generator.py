import unittest
from fmea_generator import parse_fmea
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fmea_generator import call_gemini, generate_fmea, FIELDS, RATINGS, PROMPT_VERSION

VALID_ROW = {"component": "x", "function": "x", "failure_mode": "x", "cause": "x",
             "local_effect": "x", "system_effect": "x", "recommended_action": "x",
             "severity": 1, "occurrence": 1, "detection": 1,
             "rating_rationale": "x", "evidence": "x", "review_flag": "x"}


class FMEATests(unittest.TestCase):
    def test_invalid_run_metadata_prevents_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            system = root / "system.txt"
            system.write_text("test system", encoding="utf-8")
            for metadata in ({"version": "v1.0"}, {"version": "v3.0"},
                             *({"run": run} for run in (True, False, 0, -1, 1.5, "1"))):
                with self.subTest(metadata=metadata), patch("fmea_generator.call_gemini") as call:
                    with self.assertRaises(ValueError):
                        generate_fmea(system, "case", output_dir=root / "out", **metadata)
                    call.assert_not_called()
                    self.assertFalse((root / "out").exists())

    def test_existing_outputs_prevent_model_calls_and_preserve_files(self):
        for suffix in (".csv", "_raw.txt"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                system = root / "system.txt"
                system.write_text("test system", encoding="utf-8")
                out = root / "out"
                out.mkdir()
                existing = out / f"case_{PROMPT_VERSION}_run01{suffix}"
                original = b"existing evidence\r\n"
                existing.write_bytes(original)
                with patch("fmea_generator.call_gemini") as call:
                    with self.assertRaises(FileExistsError):
                        generate_fmea(system, "case", output_dir=out)
                    call.assert_not_called()
                self.assertEqual(existing.read_bytes(), original)
                self.assertEqual(list(out.iterdir()), [existing])

    def test_csv_created_during_request_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            system = root / "system.txt"
            system.write_text("test system", encoding="utf-8")
            csv_path = root / f"case_{PROMPT_VERSION}_run01.csv"

            def response(*args, **kwargs):
                csv_path.write_bytes(b"concurrent output")
                return {"text": json.dumps([VALID_ROW]), "finish_reason": "STOP",
                        "max_output_tokens": 100}

            with patch("fmea_generator.call_gemini", side_effect=response):
                with self.assertRaises(FileExistsError):
                    generate_fmea(system, "case", output_dir=root)
            self.assertEqual(csv_path.read_bytes(), b"concurrent output")
            self.assertEqual((root / f"case_{PROMPT_VERSION}_run01_raw.txt").read_text(),
                             json.dumps([VALID_ROW]))

    def test_request_enforces_parser_field_types(self):
        from google.genai import types

        client = MagicMock()
        client.models.get.return_value = SimpleNamespace(output_token_limit=65536)
        client.models.generate_content.return_value = SimpleNamespace(
            text="[]", candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)])
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-key"}), \
                patch("fmea_generator.load_local_env"), \
                patch("google.genai.Client", return_value=client):
            self.assertEqual(call_gemini("test system", model="test-model"),
                             {"text": "[]", "finish_reason": "STOP", "max_output_tokens": 65536})
        client.models.get.assert_called_once_with(model="test-model")
        config = client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.max_output_tokens, 65536)
        schema = types.Schema.model_validate(config.response_schema)
        self.assertEqual(schema.type, types.Type.ARRAY)
        self.assertEqual(schema.min_items, 1)
        self.assertEqual(set(schema.items.required), set(FIELDS))
        for field in FIELDS:
            with self.subTest(field=field):
                prop = schema.items.properties[field]
                self.assertFalse(prop.nullable)
                if field in RATINGS:
                    self.assertEqual(prop.type, types.Type.INTEGER)
                    self.assertEqual((prop.minimum, prop.maximum), (1, 10))
                else:
                    self.assertEqual(prop.type, types.Type.STRING)
        client.close.assert_called_once()

    def test_no_sdk_retries_and_execution_metadata(self):
        from google.genai import types
        client = MagicMock()
        client.models.get.return_value = SimpleNamespace(output_token_limit=65536)
        usage = types.GenerateContentResponseUsageMetadata(prompt_token_count=10, candidates_token_count=20)
        client.models.generate_content.return_value = SimpleNamespace(
            text="[]", candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)],
            usage_metadata=usage, model_version="test-version", response_id="test-response")
        execution = {"expected_max_output_tokens": 65536}
        before = MagicMock()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-key"}), \
                patch("fmea_generator.load_local_env"), \
                patch("google.genai.Client", return_value=client) as factory:
            call_gemini("test", "test-model", execution=execution, before_request=before)
        self.assertEqual(factory.call_args.kwargs["http_options"].retry_options.attempts, 1)
        before.assert_called_once()
        self.assertEqual(execution["request_invocations"], 1)
        self.assertEqual(execution["model_version"], "test-version")
        self.assertEqual(execution["usage_metadata"]["prompt_token_count"], 10)
        self.assertEqual(execution["finish_reason"], "STOP")

    def test_changed_limit_prevents_generation(self):
        client = MagicMock()
        client.models.get.return_value = SimpleNamespace(output_token_limit=10)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-key"}), \
                patch("fmea_generator.load_local_env"), \
                patch("google.genai.Client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "limit changed"):
                call_gemini("test", execution={"expected_max_output_tokens": 20})
        client.models.generate_content.assert_not_called()

    def test_rpn_calculated(self):
        row = {"component": "pump", "function": "pressurize", "failure_mode": "loss of pressure",
               "cause": "wear", "local_effect": "low output", "system_effect": "actuator loss",
               "recommended_action": "inspect", "severity": 8, "occurrence": 4,
               "detection": 3, "rating_rationale": "provisional", "evidence": "none",
               "review_flag": "yes"}
        parsed = parse_fmea(json.dumps([row]))
        self.assertEqual(parsed[0]["RPN"], 96)

    def test_invalid_rating(self):
        row = {"component": "x", "function": "x", "failure_mode": "x", "cause": "x",
               "local_effect": "x", "system_effect": "x", "recommended_action": "x",
               "severity": 11, "occurrence": 1, "detection": 1,
               "rating_rationale": "x", "evidence": "x", "review_flag": "x"}
        with self.assertRaises(ValueError):
            parse_fmea(json.dumps([row]))

    def test_empty_text_cell_rejects_sheet(self):
        for value in ("", "   "):
            with self.subTest(value=value):
                rows = [VALID_ROW, {**VALID_ROW, "evidence": value}]
                with self.assertRaisesRegex(ValueError, "Row 2: evidence is empty"):
                    parse_fmea(json.dumps(rows))

    def test_missing_model_limit_makes_no_request(self):
        client = MagicMock()
        client.models.get.return_value = SimpleNamespace(output_token_limit=None)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-key"}), \
                patch("fmea_generator.load_local_env"), \
                patch("google.genai.Client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "output token limit"):
                call_gemini("test system", model="test-model")
        client.models.generate_content.assert_not_called()
        client.close.assert_called_once()

    def _generate(self, finish_reason, text):
        """Run generate_fmea offline with a canned Gemini result; return the output folder and rows or error."""
        out = Path(self.enterContext(tempfile.TemporaryDirectory()))
        system = out / "system.txt"
        system.write_text("test system", encoding="utf-8")
        result = {"text": text, "finish_reason": finish_reason, "max_output_tokens": 100}
        with patch("fmea_generator.call_gemini", return_value=result):
            try:
                return out / "out", generate_fmea(system, "case", output_dir=out / "out")
            except ValueError as error:
                return out / "out", error

    def test_truncated_response_fails_and_keeps_raw(self):
        out, error = self._generate("MAX_TOKENS", '[{"component": "x"')
        self.assertRegex(str(error), "truncated at the 100-token limit")
        self.assertEqual({p.name for p in out.iterdir()},
                         {"case_v2.0_run01_raw.txt", "case_v2.0_run01_execution.json"})

    def test_other_finish_reason_fails(self):
        out, error = self._generate("SAFETY", "")
        self.assertRegex(str(error), "finish reason SAFETY")
        self.assertFalse(any(p.suffix == ".csv" for p in out.iterdir()))

    def test_complete_response_writes_csv(self):
        out, rows = self._generate("STOP", json.dumps([VALID_ROW]))
        self.assertEqual(rows[0]["RPN"], 1)
        self.assertTrue((out / "case_v2.0_run01.csv").is_file())


if __name__ == "__main__":
    unittest.main()
