import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.pilot_workflow import CONFIG, package
from scripts.pilot_workflow import main as pilot_main
from sigma_fmea.integrity import load_json
from sigma_fmea.llm import LLMProvider, ProviderError
from sigma_fmea.methodology import get_profile
from sigma_fmea.providers import generate
from sigma_fmea.research import build_plan, load_system, run_experiment

ROOT = Path(__file__).resolve().parents[1]


def response():
    row = {"item_or_process_step": "Pump", "function": "Supply hydraulic pressure", "failure_mode": "No pressure",
           "failure_causes": [], "effect_local": None, "effect_next_level": None, "effect_end_effect": None, "recommended_actions": []}
    return {"modelVersion": "gemini-test-fixed-version", "responseId": "offline-response-id",
            "usageMetadata": {"promptTokenCount": 30, "candidatesTokenCount": 20, "thoughtsTokenCount": 10, "totalTokenCount": 60},
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps({"rows": [row]})}]}}]}


class GeminiPilotTests(unittest.TestCase):
    def test_gemini_adapter_preserves_model_usage_without_logging_key(self):
        context, description, _ = load_system(ROOT / "examples/research/hydraulic_actuator.json")
        captured = []
        def transport(url, body, headers, timeout):
            captured.append(body)
            self.assertTrue(url.endswith("models/gemini-3.8-flash:generateContent"))
            self.assertEqual(headers["x-goog-api-key"], "offline-gemini-test-key")
            self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
            self.assertEqual(body["generationConfig"]["temperature"], 0)
            self.assertIn("responseJsonSchema", body["generationConfig"])
            return response()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-gemini-test-key"}):
            provider = LLMProvider("gemini", "gemini-3.8-flash", description, allow_paid=True, temperature=0, transport=transport)
            draft = generate(context, get_profile("general"), provider)
        self.assertEqual(len(captured), 1)
        self.assertEqual(provider.last_execution["actual_model"], "gemini-test-fixed-version")
        self.assertEqual(provider.last_execution["usage"]["total_tokens"], 60)
        self.assertEqual(provider.last_execution["usage"]["reasoning_tokens"], 10)
        self.assertNotIn("offline-gemini-test-key", json.dumps(provider.last_execution))
        self.assertIsNone(draft.rows[0].severity)

    def test_gemini_missing_version_and_truncation_preserve_failure_without_retry(self):
        context, _, _ = load_system(ROOT / "examples/research/hydraulic_actuator.json")
        for failure in ("missing_version", "truncated"):
            raw = response()
            if failure == "missing_version":
                raw.pop("modelVersion")
            else:
                raw["candidates"][0]["finishReason"] = "MAX_TOKENS"
            transport = unittest.mock.Mock(return_value=raw)
            with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-gemini-test-key"}):
                provider = LLMProvider("gemini", "gemini-3.8-flash", allow_paid=True, transport=transport)
                with self.assertRaises(ProviderError):
                    provider.generate(context, get_profile("general"))
                self.assertEqual(transport.call_count, 1)
                self.assertEqual(provider.last_execution["response"], raw)

    def test_eight_job_design_and_original_smoke_counted_in_remaining_seven(self):
        plan = build_plan(CONFIG, provider="mock")
        self.assertEqual(plan["total_generations"], 8)
        self.assertEqual(plan["jobs"][0]["condition"], "baseline")
        self.assertEqual(plan["systems"][0]["system_id"], "hydraulic-actuator")
        self.assertEqual({s["system_id"] for s in plan["systems"]}, {"hydraulic-actuator", "battery-dc-power"})
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "pilot"
            self.assertEqual(run_experiment(CONFIG, output, "smoke", provider="mock")["successful"], 1)
            first = output / "runs" / plan["jobs"][0]["job_id"] / "state.json"
            original = first.read_bytes()
            self.assertEqual(run_experiment(CONFIG, output, "batch", provider="mock")["successful"], 8)
            self.assertEqual(first.read_bytes(), original)

    def test_reviewer_package_includes_reproduction_checksums_and_no_benchmark_answers(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"GITHUB_RUN_ID": "offline-test", "GITHUB_SHA": "offline-test-commit"}):
            output = Path(temp) / "pilot"
            run_experiment(CONFIG, output, "smoke", provider="mock")
            progress = package(output, plots=False)
            self.assertEqual(progress["successful"], 1)
            self.assertIn("OFFLINE MOCK REHEARSAL", (output / "README.md").read_text())
            for line in (output / "checksums.sha256").read_text().splitlines():
                expected, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), expected)
            self.assertTrue((output / "analysis-offline-test/experiment-results.csv").exists())
            self.assertTrue((output / "SOURCE_ROLES_AND_METHODS.md").exists())
            self.assertTrue((output / "reproduction/src/sigma_fmea/llm.py").exists())
            self.assertFalse(list(output.rglob("*.pdf")))
            self.assertFalse(list(output.rglob("nasa_2019_candidate.json")))

    def test_workflow_declares_complete_pilot_upload_and_restore_inputs(self):
        workflow = (ROOT / ".github/workflows/generate-fmea.yml").read_text()
        for value in ("pilot_plan", "pilot_smoke", "pilot_remaining", "approved_calls", "smoke_run_id", "actions/download-artifact@v4", "results/pilot/", "mode package"):
            self.assertIn(value, workflow)
        self.assertNotIn("workflow_run:", workflow)
        self.assertNotIn("pull_request:", workflow)

    def test_workflow_requires_separate_call_approval_and_blocks_reruns(self):
        for approved, attempt in (("0", "1"), ("1", "2")):
            with patch("sys.argv", ["pilot", "--mode", "smoke", "--approved-calls", approved]), patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": attempt}), patch("scripts.pilot_workflow.run_experiment") as run, patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as failure:
                    pilot_main()
                self.assertEqual(failure.exception.code, 2)
                run.assert_not_called()

    def test_continuation_commit_must_match_original_smoke(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "smoke-origin.json").write_text(json.dumps({"commit_sha": "original"}))
            with patch("sys.argv", ["pilot", "--mode", "remaining", "--approved-calls", "7", "--output", str(output)]), patch.dict(os.environ, {"GITHUB_SHA": "different", "GITHUB_RUN_ATTEMPT": "1"}), patch("scripts.pilot_workflow.run_experiment") as run, patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as failure:
                    pilot_main()
                self.assertEqual(failure.exception.code, 2)
                run.assert_not_called()
