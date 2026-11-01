import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

from scripts import single_system_replicates as runner
from test_fmea_generator import VALID_ROW


class ReplicateTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.base = root / "results"
        self.enterContext(patch.object(runner, "BASE", self.base))
        # plan.output is informational; keep the test base inside ROOT via relative_to override.
        self.enterContext(patch.object(runner, "ROOT", root))
        (root / "fmea_generator.py").write_text("offline engine source")
        self.enterContext(patch.object(runner.subprocess, "check_output", return_value="test-commit"))
        self.enterContext(patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "1"}))
        self.system = root / "system_descriptions/system_A.txt"
        self.system.parent.mkdir()
        self.system.write_bytes(b"offline system\r\n")
        self.skill = root / "skill.md"
        self.skill.write_text("offline skill")
        self.enterContext(patch.object(runner, "SYSTEM", self.system))
        self.enterContext(patch.object(runner, "SKILL", self.skill))
        self.plan = runner.plan("test-model", "20261101T170000Z-offline")
        self.plan["max_output_tokens"] = 100

    def response(self, finish="STOP", text=None):
        def call(system, model=None, execution=None, before_request=None):
            before_request()
            execution.update({"request_invocations": 1, "finish_reason": finish,
                              "model_version": "offline-model", "usage_metadata": None})
            return {"text": text if text is not None else json.dumps([
                {**VALID_ROW, "severity": 8, "occurrence": 4, "detection": 3}]),
                "finish_reason": finish, "max_output_tokens": 100}
        return call

    def test_five_independent_runs_hashes_rpn_and_no_overwrite(self):
        with patch.object(runner.engine, "call_gemini", side_effect=self.response()) as call:
            output, manifest = runner.execute(self.plan, 5)
        self.assertEqual(call.call_count, 5)
        self.assertEqual(manifest["request_invocations"], 5)
        self.assertEqual(manifest["summary"], {"successes": 5, "failures": 0, "not_attempted": 0})
        self.assertEqual([r["run_number"] for r in manifest["runs"]], [1, 2, 3, 4, 5])
        self.assertEqual(manifest["plan"]["system_sha256"], hashlib.sha256(self.system.read_bytes()).hexdigest())
        self.assertEqual(manifest["plan"]["skill_sha256"], hashlib.sha256(self.skill.read_bytes()).hexdigest())
        for run in manifest["runs"]:
            self.assertEqual(run["core_populated"], 7)
            self.assertEqual(run["review_flag_count"], 1)
            for name, data in run["outputs"].items():
                self.assertEqual(data["sha256"], runner.sha(output / name))
        with (output / "combined.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([int(r["run_number"]) for r in rows], [1, 2, 3, 4, 5])
        self.assertTrue(all(int(r["RPN"]) == 96 for r in rows))
        original = (output / "manifest.json").read_bytes()
        with patch.object(runner.engine, "call_gemini") as call:
            with self.assertRaises(FileExistsError):
                runner.execute(self.plan, 5)
            call.assert_not_called()
        self.assertEqual((output / "manifest.json").read_bytes(), original)
        for line in (output / "checksums.sha256").read_text().splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(digest, runner.sha(output / name))

    def test_first_truncation_halts_preserves_raw_and_no_csv(self):
        with patch.object(runner.engine, "call_gemini", side_effect=self.response("MAX_TOKENS", "partial")) as call:
            output, manifest = runner.execute(self.plan, 5)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(manifest["request_invocations"], 1)
        self.assertEqual(manifest["summary"], {"successes": 0, "failures": 1, "not_attempted": 4})
        self.assertEqual(manifest["runs"][0]["status"], "truncation")
        self.assertEqual((output / manifest["runs"][0]["raw_file"]).read_text(), "partial")
        self.assertNotIn("csv_file", manifest["runs"][0])

    def test_malformed_response_counts_failure_without_retry(self):
        responses = [self.response(text="not json"), *[self.response() for _ in range(4)]]
        def call(*args, **kwargs):
            return responses.pop(0)(*args, **kwargs)
        with patch.object(runner.engine, "call_gemini", side_effect=call) as mock:
            output, manifest = runner.execute(self.plan, 5)
        self.assertEqual(mock.call_count, 5)
        self.assertEqual(manifest["summary"], {"successes": 4, "failures": 1, "not_attempted": 0})
        self.assertEqual(manifest["runs"][0]["status"], "validation_failure")
        self.assertEqual(len(list(output.glob("system_A*.csv"))), 4)

    def test_gate_and_input_mutation_make_no_calls(self):
        with patch.object(runner.engine, "call_gemini") as call:
            for approval in (0, 1, 6):
                with self.assertRaises(ValueError):
                    runner.execute(self.plan, approval)
            self.system.write_text("changed")
            with self.assertRaisesRegex(ValueError, "Frozen preflight changed"):
                runner.execute(self.plan, 5)
            call.assert_not_called()

    def test_preflight_checks_model_without_generating(self):
        client = MagicMock()
        client.models.get.return_value = SimpleNamespace(
            name="models/test-model", output_token_limit=100,
            supported_actions=["generateContent"])
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-test-key"}), \
                patch.object(runner.engine, "load_local_env"), \
                patch("google.genai.Client", return_value=client):
            frozen = runner.preflight("test-model", self.plan["batch_id"])
        self.assertEqual(frozen["max_output_tokens"], 100)
        client.models.generate_content.assert_not_called()
        client.models.get.assert_called_once_with(model="test-model")

    def test_first_auth_failure_halts_without_retry(self):
        class AuthFailure(Exception):
            code = 403
        def fail(*args, execution=None, before_request=None, **kwargs):
            before_request()
            raise AuthFailure("offline unauthorized")
        with patch.object(runner.engine, "call_gemini", side_effect=fail) as call:
            output, manifest = runner.execute(self.plan, 5)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(manifest["request_invocations"], 1)
        self.assertEqual(manifest["summary"], {"successes": 0, "failures": 1, "not_attempted": 4})

    def test_existing_run_output_is_preserved_without_request(self):
        original = runner.engine.generate_fmea
        def collision(*args, **kwargs):
            path = kwargs["output_dir"] / "system_A_v2.0_run01.csv"
            path.write_bytes(b"existing evidence")
            return original(*args, **kwargs)
        with patch.object(runner.engine, "generate_fmea", side_effect=collision), \
                patch.object(runner.engine, "call_gemini") as call:
            output, manifest = runner.execute(self.plan, 5)
        call.assert_not_called()
        self.assertEqual(manifest["request_invocations"], 0)
        self.assertEqual((output / "system_A_v2.0_run01.csv").read_bytes(), b"existing evidence")
        self.assertEqual(manifest["summary"], {"successes": 0, "failures": 1, "not_attempted": 4})
