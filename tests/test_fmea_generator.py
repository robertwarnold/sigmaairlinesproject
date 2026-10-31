import unittest
from fmea_generator import parse_fmea
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fmea_generator import call_gemini, FIELDS, RATINGS


class FMEATests(unittest.TestCase):
    def test_request_enforces_parser_field_types(self):
        from google.genai import types

        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(text="[]")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-key"}), \
                patch("fmea_generator.load_local_env"), \
                patch("google.genai.Client", return_value=client):
            self.assertEqual(call_gemini("test system", model="test-model"), "[]")
        config = client.models.generate_content.call_args.kwargs["config"]
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


if __name__ == "__main__":
    unittest.main()
