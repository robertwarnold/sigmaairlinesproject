"""Synthetic financial/timing regressions only; no real reviewer answers or paid calls."""
import ast
import copy
import csv
import hashlib
import json
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import fmea_generator as engine
from analysis.financial_impact import data_schema as schema
from analysis.financial_impact.cost_model import active_minutes, comparison, loaded_rate, token_cost
from analysis.financial_impact.ingest import configuration_id, import_attempts, read_log
from analysis.financial_impact.metrics import costs, matched_pairs
from analysis.financial_impact.report import CONFIG, create_report, narrative
from analysis.financial_impact.uncertainty import paired_bootstrap, simulate


class FinancialTests(unittest.TestCase):
    """Check arithmetic, missingness and dependency-aware inference with labeled synthetic data."""
    def setUp(self):
        # Configuration is public; no generated worksheet content is read for these tests.
        self.assumptions = schema.read_json(CONFIG / "assumptions.json")
        self.price = self.assumptions["pricing"][0]
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def manifest(self, version="v2.0", failed=True):
        """Create a tiny synthetic manifest without any FMEA rows or engineering assertions."""
        plan = {"batch_id": "synthetic-" + version, "system_id": "synthetic-system",
                "system_sha256": "a" * 64, "skill_sha256": "b" * 64, "prompt_version": version,
                "model": "gemini-3.8-flash", "temperature": 0, "max_output_tokens": 100}
        runs = [{"run_number": 1, "status": "success", "started_at": "2026-11-01T00:00:00+00:00",
                 "duration_seconds": 2, "execution": {"usage_metadata": {
                     "prompt_token_count": 100, "candidates_token_count": 50, "thoughts_token_count": 20}}}]
        if failed:
            # An unknown failed bill must not become a free generation.
            runs.append({"run_number": 2, "status": "provider_failure", "started_at": "2026-11-01T00:01:00+00:00",
                         "duration_seconds": 5, "error_type": "SyntheticDisconnect", "execution": {}})
        path = self.root / (version + ".json")
        path.write_text(json.dumps({"plan": plan, "runs": runs}))
        return path

    def records(self, method="ai_assisted", version="v2.0"):
        """Create clearly synthetic stage and quality records with full cohort identities."""
        identity = {k: "synthetic" for k in schema.IDENTITY}
        identity.update(experiment_id="synthetic-" + version, system_id="synthetic-system", input_hash="a" * 64,
                        workflow="standalone_gemini", skill_version=version, skill_hash="b" * 64,
                        model="gemini-3.8-flash", configuration_id="synthetic-settings")
        labor = {k: "" for k in schema.LABOR_FIELDS}
        labor.update(identity, case_id="synthetic-case", method=method, engineer_id="synthetic-engineer",
                     stage="approval", active_engineering_minutes=30, passive_waiting_minutes=60,
                     rework_minutes=10, review_minutes=20, approval_status="accepted", evidence_source="synthetic fixture")
        quality = {k: "" for k in schema.QUALITY_FIELDS}
        quality.update(identity, case_id="synthetic-case", method=method, reviewer_id="synthetic-reviewer",
                       independent_review="true", decision="accepted", evidence_source="synthetic fixture")
        return schema.validate_records([labor], "labor"), schema.validate_records([quality], "quality")

    def test_wage_burden_and_override_once(self):
        # The national multiplier is applied once; a company loaded rate bypasses it.
        self.assertAlmostEqual(loaded_rate(self.assumptions["labor"]), 64.89 * 46.89 / 32.82)
        self.assertEqual(loaded_rate({"fully_burdened_override_usd_per_hour": 120}), 120)

    def test_thinking_invoice_and_missing_billing(self):
        # Thinking is a separate output bucket in Gemini metadata, not another total-token charge.
        usage = {"prompt_token_count": 1_000_000, "candidates_token_count": 1_000_000, "thoughts_token_count": 1_000_000}
        self.assertEqual(token_cost(usage, self.price)["usd"], 8.25)
        self.assertEqual(token_cost(None, self.price, 0.12)["basis"], "invoice")
        self.assertIsNone(token_cost(None, self.price)["usd"])
        self.assertIsNone(token_cost({"prompt_token_count": 1, "candidates_token_count": 2}, self.price)["usd"])
        self.assertIsNone(token_cost({**usage, "cached_content_token_count": 1}, self.price)["usd"])

    def test_failed_attempt_preserved_and_invoice_override(self):
        path = self.manifest()
        records = import_attempts(path, self.assumptions)
        self.assertEqual(len(records), 2)
        self.assertIsNone(records[1]["cost_usd"])
        self.assertTrue(records[1]["billing_uncertain"])
        priced = import_attempts(path, self.assumptions, invoices={"synthetic-v2.0/2": .10})
        self.assertEqual(priced[1]["cost_usd"], .10)

    def test_passive_time_is_not_labor_and_all_failed_expense_allocated(self):
        labor, quality = self.records()
        self.assertEqual(active_minutes(labor[0]), 60)
        attempt = {k: labor[0][k] for k in schema.IDENTITY if k not in {"scope_id", "criteria_id"}}
        attempts = [{**attempt, "attempt_id": "1", "cost_usd": .2, "cost_basis": "invoice"},
                    {**attempt, "attempt_id": "2", "cost_usd": .1, "cost_basis": "invoice", "status": "failed"}]
        rows, _ = costs(attempts, labor, quality, 100)
        self.assertAlmostEqual(rows[0]["cost_per_accepted_fmea_usd"], 100.3)
        self.assertEqual(rows[0]["hours_per_accepted_fmea"], 1)
        self.assertEqual(rows[0]["passive_hours_recorded"], 1)
        attempts[1]["cost_usd"] = None
        self.assertIsNone(costs(attempts, labor, quality, 100)[0][0]["cost_per_accepted_fmea_usd"])

    def test_rejected_work_and_quality_denominator(self):
        labor, quality = self.records(method="manual")
        labor.append({**labor[0], "case_id": "rejected", "approval_status": "rejected"})
        quality.append({**quality[0], "case_id": "rejected", "decision": "rejected"})
        rows, cases = costs([], labor, quality, 100)
        self.assertEqual(rows[0]["quality_adjusted_acceptance_rate"], .5)
        self.assertEqual(rows[0]["cost_per_accepted_fmea_usd"], 200)
        self.assertEqual(cases[0]["usd"], 200)

    def test_negative_savings_and_no_false_break_even(self):
        result = comparison(100, 150, development_usd=500, annual_volume=20)
        self.assertEqual(result["absolute_savings_usd"], -50)
        self.assertEqual(result["percentage_reduction"], -50)
        self.assertEqual(result["net_annual_savings_usd"], -1500)
        self.assertIsNone(result["break_even_fmeas"])
        self.assertIsNone(comparison(None, 100)["absolute_savings_usd"])

    def test_bootstrap_reproducibility_and_dependencies(self):
        pairs = [{"manual_usd": 100 + i, "ai_usd": 80 + i * 2, "basis": "measured",
                  "dependencies": [f"system:{i}", f"reviewer:{i}"]} for i in range(4)]
        first, second = paired_bootstrap(pairs), paired_bootstrap(pairs)
        self.assertEqual(first, second)
        self.assertEqual(first["n_independent_clusters"], 4)
        self.assertEqual(first["mean_savings_usd"], 18.5)
        # One shared reviewer makes these a single dependency cluster, not four observations.
        for pair in pairs:
            pair["dependencies"].append("reviewer:shared")
        result = paired_bootstrap(pairs)
        self.assertEqual(result["n_independent_clusters"], 1)
        self.assertIsNone(result["ci95_usd"])

    def test_insufficient_samples_never_get_empirical_ci(self):
        self.assertIsNone(paired_bootstrap([])["ci95_usd"])
        pair = {"manual_usd": 100, "ai_usd": 80, "basis": "measured", "dependencies": ["system:A"]}
        self.assertIsNone(paired_bootstrap([pair] * 3)["ci95_usd"])
        with self.assertRaises(ValueError):
            paired_bootstrap([{**pair, "basis": "assumed"}])

    def test_explicit_monte_carlo_reproducible_not_confidence_interval(self):
        values = {"labor_rate": 100, "manual_hours": 1, "ai_hours": 2, "api_usd_per_attempt": .1,
                  "success_probability": .5, "maintenance_usd": 10, "development_usd": 10, "annual_volume": 10}
        scenario = {"rationale": "synthetic test, not project observations", "distributions": {
            k: {"distribution": "constant", "value": v} for k, v in values.items()}}
        result = simulate(scenario)
        self.assertEqual(result, simulate(scenario))
        self.assertAlmostEqual(result["mean_net_savings_usd"], -102.2)
        self.assertIn("not confidence interval", result["interval_kind"])
        self.assertEqual(simulate(None)["status"], "not_requested")

    def test_versions_stay_separate_and_bad_records_rejected(self):
        first = import_attempts(self.manifest("v2.0"), self.assumptions)
        second = import_attempts(self.manifest("v2.1"), self.assumptions)
        self.assertNotEqual(first[0]["experiment_id"], second[0]["experiment_id"])
        self.assertNotEqual(first[0]["skill_version"], second[0]["skill_version"])
        with self.assertRaises(ValueError):
            schema.validate_records([{"case_id": "missing-columns"}], "labor")
        path = self.root / "bad.json"
        path.write_text('{"x":1,"x":2}')
        with self.assertRaises(ValueError):
            schema.read_json(path)
        for value in (True, -1, float("nan"), ""):
            with self.assertRaises(ValueError):
                schema.number(value, "test")

    def test_quality_scope_mismatch_prevents_pair(self):
        # Financial pairing cannot make differing engineering criteria equivalent.
        base = {"case_id": "x", "system_id": "A", "input_hash": "h", "scope_id": "scope", "criteria_id": "one",
                "skill_version": "v2", "workflow": "standalone", "skill_hash": "hash", "model": "model",
                "configuration_id": "config", "usd": 10, "reviewers": ["r"], "basis": "measured", "lead_time_hours": None}
        self.assertEqual(matched_pairs([{**base, "method": "manual"},
                         {**base, "method": "ai_assisted", "criteria_id": "two"}]), [])

    def test_report_is_immutable_has_provenance_and_no_network(self):
        source = self.manifest()
        before = source.read_bytes()
        # Figure generation has its own real-report check; mock it here to focus on publication integrity.
        with patch("analysis.financial_impact.report.figures", return_value={}), \
                patch.object(socket, "create_connection", side_effect=AssertionError("offline only")):
            output, metrics = create_report([source], self.root / "reports", analysis_id="synthetic-report")
            # Different immutable report IDs retain identical numerical results for fixed inputs/seed.
            _, repeated = create_report([source], self.root / "reports", analysis_id="synthetic-repeated")
            self.assertEqual(metrics, repeated)
            with self.assertRaises(FileExistsError):
                create_report([source], self.root / "reports", analysis_id="synthetic-report")
        self.assertEqual(source.read_bytes(), before)
        self.assertIsNone(metrics["uncertainty"]["ci95_usd"])
        manifest = schema.read_json(output / "manifest.json")
        for name in ("analysis_id", "system_ids", "skill_versions", "analysis_code_version", "git_commit",
                     "datasets", "assumptions_version", "sample_sizes", "statistical_method", "seed", "created_at", "report_status"):
            self.assertIn(name, manifest)
        for name, digest in manifest["artifacts"].items():
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(manifest["report_status"], "preliminary")
        words = (output / "Financial_Impacts.md").read_text(encoding="utf-8").split()
        self.assertTrue(300 <= len(words) <= 500, len(words))

    def test_blank_templates_and_malformed_csv(self):
        # Templates are schema-only; no invented labor or acceptance observations are supplied.
        self.assertEqual(read_log(CONFIG / "templates/work_log_template.csv", "labor"), [])
        self.assertEqual(read_log(CONFIG / "templates/quality_review_template.csv", "quality"), [])
        broken = self.root / "malformed.csv"
        broken.write_text("case_id,case_id\nx,y,z\n")
        with self.assertRaises(ValueError):
            read_log(broken, "labor")

    def test_measured_matched_report_preserves_negative_savings(self):
        # Three independent synthetic systems test the populated path, not real project observations.
        manifests, labor_rows, quality_rows, invoices = [], [], [], {}
        for i in range(3):
            source = self.manifest(f"synthetic-source-{i}", failed=False)
            document = schema.read_json(source)
            document["plan"].update(batch_id=f"synthetic-batch-{i}", system_id=f"synthetic-system-{i}", prompt_version="v2.0")
            source.write_text(json.dumps(document))
            attempt = import_attempts(source, self.assumptions)[0]
            manifests.append(source)
            invoices[f"synthetic-batch-{i}/1"] = .10
            for method in ("manual", "ai_assisted"):
                work, review = self.records(method)
                identity = {k: attempt[k] for k in schema.IDENTITY if k not in {"scope_id", "criteria_id"}}
                if method == "manual":
                    identity.update(experiment_id=f"synthetic-manual-{i}", skill_version="not_applicable",
                                    skill_hash="not_applicable", model="not_applicable", configuration_id="not_applicable", workflow="manual")
                for record in (work[0], review[0]):
                    record.update(identity, case_id=f"synthetic-pair-{i}")
                work[0]["engineer_id"] = f"synthetic-engineer-{i}"
                review[0]["reviewer_id"] = f"synthetic-reviewer-{i}"
                # Synthetic AI takes twice the active work; losses must remain visible.
                if method == "ai_assisted":
                    for name in ("active_engineering_minutes", "review_minutes", "rework_minutes"):
                        work[0][name] *= 2
                labor_rows.extend(work)
                quality_rows.extend(review)
        def log(name, fields, rows):
            path = self.root / name
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            return path
        labor = log("synthetic-labor.csv", schema.LABOR_FIELDS, labor_rows)
        quality = log("synthetic-quality.csv", schema.QUALITY_FIELDS, quality_rows)
        invoice_path = self.root / "synthetic-invoices.json"
        invoice_path.write_text(json.dumps(invoices))
        with patch("analysis.financial_impact.report.figures", return_value={}):
            _, metrics = create_report(manifests, self.root / "reports", labor_path=labor,
                quality_path=quality, invoices_path=invoice_path, analysis_id="synthetic-measured")
        self.assertEqual(metrics["uncertainty"]["n_independent_clusters"], 3)
        self.assertLess(metrics["uncertainty"]["ci95_usd"][1], 0)
        self.assertAlmostEqual(metrics["comparison"]["absolute_savings_usd"], -loaded_rate(self.assumptions["labor"]) - .1)
        self.assertIsNone(metrics["comparison"]["break_even_fmeas"])

    def test_annotation_checklist_and_public_function_documentation(self):
        # Verify the user's annotation convention, without inventing a professor grading threshold.
        files = [*CONFIG.glob("*.py"), Path("src/sigma_fmea/execution_metadata.py")]
        for path in files:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            self.assertIsNotNone(ast.get_docstring(tree), path)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertIsNotNone(ast.get_docstring(node), f"{path}:{node.name}")
            self.assertTrue("#" in text or path.name == "__init__.py", path)
        self.assertIn("user clarification", Path("docs/SYSEN5300_CODING_STANDARDS.md").read_text(encoding="utf-8"))


class TimingTests(unittest.TestCase):
    """SDK doubles record success and no-response failures without network access."""
    def test_success_and_failure_receipts(self):
        # This row is deliberately synthetic and does not claim engineering validity.
        row = {f: (2 if f in engine.RATINGS else "synthetic") for f in engine.FIELDS}
        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                system = root / "system.txt"
                system.write_text("synthetic system")
                client = MagicMock()
                client.models.get.return_value = SimpleNamespace(output_token_limit=100)
                if failed:
                    client.models.generate_content.side_effect = ConnectionError("synthetic disconnect")
                else:
                    client.models.generate_content.return_value = SimpleNamespace(
                        text=json.dumps([row]), candidates=[SimpleNamespace(finish_reason="STOP")],
                        usage_metadata=None, model_version="synthetic-model", response_id="synthetic-response")
                with patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test-key"}), \
                        patch("fmea_generator.load_local_env"), \
                        patch("google.genai.Client", return_value=client), \
                        patch.object(socket, "create_connection", side_effect=AssertionError("offline only")):
                    if failed:
                        with self.assertRaises(ConnectionError):
                            engine.generate_fmea(system, "synthetic", output_dir=root / "out")
                    else:
                        engine.generate_fmea(system, "synthetic", output_dir=root / "out")
                record = schema.read_json(root / "out/synthetic_v2.0_run01_execution.json")
                self.assertGreaterEqual(record["api_request_seconds"], 0)
                self.assertGreaterEqual(record["total_elapsed_seconds"], record["api_request_seconds"])
                self.assertIsNone(record["usage_metadata"])
                self.assertIsNone(record["estimated_api_expense_usd"])
                self.assertEqual(record["status"], "failed" if failed else "success")
                if failed:
                    self.assertIsNone(record["parsing_validation_seconds"])
                else:
                    self.assertGreaterEqual(record["parsing_validation_seconds"], 0)
                    with (root / "out/synthetic_v2.0_run01.csv").open() as stream:
                        self.assertNotIn("generation_minutes", csv.DictReader(stream).fieldnames)

    def test_api_duration_uses_monotonic_difference_even_on_disconnect(self):
        # A deterministic clock verifies arithmetic, not just a nonnegative field.
        client = MagicMock()
        client.models.get.return_value = SimpleNamespace(output_token_limit=100)
        client.models.generate_content.side_effect = ConnectionError("synthetic disconnect")
        execution = {}
        with patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test-key"}), \
                patch("fmea_generator.load_local_env"), patch("google.genai.Client", return_value=client), \
                patch("fmea_generator.time.perf_counter", side_effect=[10.0, 12.5]):
            with self.assertRaises(ConnectionError):
                engine.call_gemini("synthetic", execution=execution)
        self.assertEqual(execution["generation_seconds"], 2.5)
        self.assertEqual(execution["request_invocations"], 1)
