from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from sigma_fmea.analysis import collect, summarize
from sigma_fmea.cli import main
from sigma_fmea.evaluation import evaluate, reference_coverage
from sigma_fmea.guidance import retrieve
from sigma_fmea.integrity import canonical_json, digest, load_json
from sigma_fmea.llm import LLMProvider, ProviderError, build_prompt, candidates_to_rows
from sigma_fmea.methodology import get_profile
from sigma_fmea.providers import generate, MockProvider
from sigma_fmea.research import build_plan, execute_run, load_system, run_experiment

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "examples/research/hydraulic_actuator.json"
CONFIG = ROOT / "examples/research/experiment.json"


def candidate():
    return {"rows": [{"item_or_process_step": "Pump", "function": "Supply hydraulic pressure", "failure_mode": "No pressure",
                      "failure_causes": ["Drive unavailable"], "effect_local": "No pump output", "effect_next_level": "No flow to valve",
                      "effect_end_effect": "Load cannot move", "recommended_actions": ["Verify pressure alarm response"]}]}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.context, self.description, _ = load_system(SYSTEM)
        self.profile = get_profile("general")

    def test_real_adapters_use_structured_requests_and_preserve_usage_offline(self):
        for name in ("openai", "anthropic"):
            seen = []
            def transport(url, body, headers, timeout):
                seen.append((url, body))
                if name == "openai":
                    self.assertEqual(body["text"]["format"]["type"], "json_schema")
                    self.assertFalse(body["store"])
                    return {"id": "offline-test-response", "model": "test-model-snapshot", "status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(candidate())}]}], "usage": {"input_tokens": 100, "output_tokens": 50}}
                self.assertIn("output_config", body)
                return {"id": "offline-test-response", "model": "test-model-snapshot", "stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(candidate())}], "usage": {"input_tokens": 100, "output_tokens": 50}}
            with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-key", "ANTHROPIC_API_KEY": "offline-test-key"}), patch.object(socket, "socket", side_effect=AssertionError("No network in test")):
                provider = LLMProvider(name, "test-model", self.description, allow_paid=True, transport=transport)
                draft = generate(self.context, self.profile, provider)
            self.assertEqual(len(seen), 1)
            self.assertEqual(draft.rows[0].field_provenance["function"], "source")
            self.assertEqual(draft.rows[0].provenance_kind, "hypothesis")
            self.assertIsNone(draft.rows[0].severity)
            self.assertEqual(provider.last_execution["usage"]["input_tokens"], 100)
            self.assertNotIn("offline-test-key", canonical_json(provider.last_execution))

    def test_paid_gate_and_missing_credentials_prevent_transport(self):
        transport = unittest.mock.Mock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-key"}):
            with self.assertRaisesRegex(ProviderError, "disabled"):
                LLMProvider("openai", "test", transport=transport).generate(self.context, self.profile)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ProviderError, "not set"):
                LLMProvider("openai", "test", allow_paid=True, transport=transport).generate(self.context, self.profile)
        transport.assert_not_called()

    def test_incomplete_and_malformed_outputs_do_not_retry(self):
        responses = [
            {"model": "test", "status": "incomplete", "output": []},
            {"model": "test", "status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"rows":[],"rows":[]}'}]}]},
        ]
        for response in responses:
            transport = unittest.mock.Mock(return_value=response)
            with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-key"}):
                provider = LLMProvider("openai", "test", allow_paid=True, transport=transport)
                with self.assertRaises(ValueError):
                    provider.generate(self.context, self.profile)
                self.assertEqual(transport.call_count, 1)
                self.assertEqual(provider.last_execution["response"], response)

    def test_output_schema_cannot_smuggle_ratings_or_approval(self):
        for key, value in (("severity", 8), ("review_status", "accepted")):
            data = candidate()
            data["rows"][0][key] = value
            with self.assertRaises(ProviderError):
                candidates_to_rows(data, self.context, self.profile)

    def test_guidance_conditions_differ_without_benchmark_retrieval(self):
        baseline = build_prompt(self.context, self.profile, self.description, "baseline")
        improved = build_prompt(self.context, self.profile, self.description, "improved")
        self.assertEqual(baseline["guidance"]["items"], [])
        self.assertEqual({g["source_id"] for g in improved["guidance"]["items"]}, {"asq", "nasa-gsfc", "sigma-team-policy"})
        self.assertEqual(baseline["user"]["engineering_context"], improved["user"]["engineering_context"])
        self.assertEqual(baseline["user"]["engineering_description"], improved["user"]["engineering_description"])
        self.assertNotEqual(baseline["sha256"], improved["sha256"])
        self.assertNotIn("NASA-CR-2019-220217", canonical_json(improved))
        with self.assertRaises(ValueError):
            load_system(ROOT / "tests/fixtures/nasa_2019_context.json")


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.context, _, _ = load_system(SYSTEM)
        self.draft = generate(self.context, get_profile("general"), MockProvider())

    def reference(self):
        return {"system_id": self.context.system_id, "reference_version": "unit-test-only", "review_status": "reviewed",
                "reviewer": "test-fixture-not-real-engineering-review", "reviewed_on": "2026-10-31", "scope": "Unit-test modes only",
                "modes": [{"reference_id": "R1", "item": "Pump", "mode": self.draft.rows[0].failure_mode}, {"reference_id": "R2", "item": "Pump", "mode": "No pressure", "accepted_aliases": []}]}

    def test_content_completeness_does_not_reward_unknown_markers(self):
        metrics = evaluate(self.draft)
        self.assertEqual(metrics["structural_completeness_pct"], 37.5)
        self.assertTrue(metrics["schema_valid"])
        self.assertEqual(metrics["generated_failure_modes"], 5)
        self.assertIsNone(metrics["missed_failure_modes_pct"])
        self.assertGreater(metrics["unknown_field_count"], 0)

    def test_only_reviewed_references_enable_coverage(self):
        reference = self.reference()
        self.assertEqual(reference_coverage(self.draft, reference)["missed_failure_modes_pct"], 50)
        reference["review_status"] = "unreviewed"
        self.assertIsNone(reference_coverage(self.draft, reference)["missed_failure_modes_pct"])
        reference["review_status"] = "reviewed"
        reference["system_id"] = "other-system"
        with self.assertRaises(ValueError):
            reference_coverage(self.draft, reference)

    def test_matching_is_one_to_one_and_aliases_are_explicit(self):
        reference = self.reference()
        reference["modes"][1]["accepted_aliases"] = [self.draft.rows[0].failure_mode]
        metrics = reference_coverage(self.draft, reference)
        self.assertEqual(metrics["matched_reference_modes"], 1)
        self.assertEqual(metrics["missed_failure_modes_pct"], 50)
        reference["modes"] = []
        with self.assertRaises(ValueError):
            reference_coverage(self.draft, reference)


class ExperimentTests(unittest.TestCase):
    def test_plan_has_24_frozen_same_model_jobs_and_reports_blockers(self):
        plan = build_plan(CONFIG, "mock")
        self.assertEqual(plan["total_generations"], 24)
        self.assertEqual(len(plan["systems"]), 4)
        self.assertEqual(plan["model"], "offline-mock")
        self.assertEqual(len({j["job_id"] for j in plan["jobs"]}), 24)
        self.assertEqual(plan, build_plan(CONFIG, "mock"))
        with patch.dict(os.environ, {}, clear=True):
            blocked = build_plan(CONFIG)
            self.assertTrue(blocked["blockers"])

    def test_smoke_gate_batch_resume_and_descriptive_report(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(socket, "socket", side_effect=AssertionError("No network")):
            output = Path(temp) / "campaign"
            with self.assertRaisesRegex(ValueError, "smoke"):
                run_experiment(CONFIG, output, "batch", provider="mock")
            smoke = run_experiment(CONFIG, output, "smoke", provider="mock")
            self.assertEqual(smoke["successful"], 1)
            result = run_experiment(CONFIG, output, "batch", provider="mock")
            self.assertEqual(result["successful"], 24)
            before = {p: p.read_bytes() for p in (output / "runs").rglob("*") if p.is_file()}
            resumed = run_experiment(CONFIG, output, "batch", provider="mock")
            self.assertEqual(result, resumed)
            self.assertEqual(before, {p: p.read_bytes() for p in (output / "runs").rglob("*") if p.is_file()})
            summary = summarize(output, Path(temp) / "analysis", plots=False)
            self.assertEqual(summary["successful"], 24)
            report = (Path(temp) / "analysis/preliminary-findings.md").read_text(encoding="utf-8")
            self.assertIn("not real LLM research results", report)
            self.assertIn("Coverage is unavailable, not zero", report)
            self.assertTrue((Path(temp) / "analysis/experiment-results.csv").exists())

    def test_plan_changes_do_not_overwrite_existing_experiment(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "campaign"
            run_experiment(CONFIG, output, "smoke", provider="mock")
            changed = load_json(CONFIG)
            changed["repetitions"] = 2
            for system in changed["systems"]:
                system["path"] = str((CONFIG.parent / system["path"]).resolve())
            changed_path = Path(temp) / "changed.json"
            changed_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "plan changed"):
                run_experiment(changed_path, output, "smoke", provider="mock")

    def test_failed_generation_retains_response_and_is_not_repeated(self):
        class BrokenProvider(MockProvider):
            last_execution = {"response": {"offline_failure": True}, "raw_row_count": 2}
            def generate(self, context, profile):
                raise ValueError("Offline simulated invalid response")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            result = execute_run(SYSTEM, "general", "baseline", "mock", "offline-mock", output, provider_override=BrokenProvider())
            self.assertEqual(result["state"], "failed")
            self.assertEqual(load_json(output / "execution.json")["response"], {"offline_failure": True})
            self.assertEqual(load_json(output / "metrics.json")["validation_error_count"], 1)
            with self.assertRaises(FileExistsError):
                execute_run(SYSTEM, "general", "baseline", "mock", "offline-mock", output)

    def test_paid_experiments_cannot_start_without_approval(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-key"}):
            with patch("sigma_fmea.llm._post") as transport:
                with self.assertRaisesRegex(ProviderError, "approval"):
                    run_experiment(CONFIG, Path(temp) / "paid", "smoke", provider="openai", model="test-model")
                transport.assert_not_called()

    def test_paid_attempt_cap_is_cumulative_without_real_network(self):
        class SimulatedLLM(MockProvider):
            last_execution = {"actual_model": "test-snapshot", "usage": {"input_tokens": 10, "output_tokens": 5}}
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-key"}), patch("sigma_fmea.research.LLMProvider", return_value=SimulatedLLM()):
            output = Path(temp) / "campaign"
            smoke = run_experiment(CONFIG, output, "smoke", provider="openai", model="test", allow_paid=True, max_calls=1)
            self.assertEqual(smoke["successful"], 1)
            limited = run_experiment(CONFIG, output, "batch", provider="openai", model="test", allow_paid=True, max_calls=2)
            self.assertEqual(limited["attempted"], 2)
            repeated = run_experiment(CONFIG, output, "batch", provider="openai", model="test", allow_paid=True, max_calls=2)
            self.assertEqual(repeated["attempted"], 2)
            self.assertEqual(repeated["remaining"], 22)

    def test_recorded_error_redacts_a_key_and_retains_failure(self):
        class BrokenProvider(MockProvider):
            last_execution = {}
            def generate(self, context, profile):
                raise ValueError("offline-key-secret-value")
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OPENAI_API_KEY": "offline-key-secret-value"}):
            output = Path(temp) / "run"
            execute_run(SYSTEM, "general", "baseline", "mock", "offline-mock", output, provider_override=BrokenProvider())
            for path in output.glob("*.json"):
                self.assertNotIn("offline-key-secret-value", path.read_text())
            self.assertEqual(load_json(output / "state.json")["state"], "failed")

    def test_evaluation_reference_is_not_supplied_to_provider(self):
        class InspectProvider(MockProvider):
            def generate(self, context, profile):
                self.seen = canonical_json({"context": context.__dict__, "profile": profile.profile_id})
                return super().generate(context, profile)
        reference = {"review_status": "unreviewed", "modes": [{"mode": "BENCHMARK_SECRET_SENTINEL"}]}
        provider = InspectProvider()
        with tempfile.TemporaryDirectory() as temp:
            result = execute_run(SYSTEM, "general", "improved", "mock", "offline-mock", Path(temp) / "run", reference=reference, provider_override=provider)
            self.assertEqual(result["state"], "success")
            self.assertNotIn("BENCHMARK_SECRET_SENTINEL", provider.seen)
            self.assertNotIn("BENCHMARK_SECRET_SENTINEL", (Path(temp) / "run/prompt.json").read_text())

    def test_cli_paid_gate_returns_error_without_traceback(self):
        error = io.StringIO()
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-key"}), redirect_stderr(error), redirect_stdout(io.StringIO()):
            code = main(["draft", "--system", str(SYSTEM), "--profile", "general", "--provider", "openai", "--model", "test", "--output", str(Path(temp) / "run")])
        self.assertEqual(code, 2)
        self.assertIn("approval", error.getvalue())
