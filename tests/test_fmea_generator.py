import unittest
from fmea_generator import parse_fmea
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fmea_generator import call_gemini, generate_fmea, FIELDS, RATINGS

VALID_ROW = {"component": "x", "function": "x", "failure_mode": "x", "cause": "x",
             "local_effect": "x", "system_effect": "x", "recommended_action": "x",
             "severity": 1, "occurrence": 1, "detection": 1,
             "rating_rationale": "x", "evidence": "x", "review_flag": "x"}


class FMEATests(unittest.TestCase):
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
        self.assertEqual([p.name for p in out.iterdir()], ["case_v2.0_run01_raw.txt"])

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
