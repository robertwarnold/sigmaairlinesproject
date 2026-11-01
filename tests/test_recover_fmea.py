"""Offline safety tests for immutable C/E recovery and campaign reconciliation."""
import csv
import json
import socket
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import recover_fmea as recovery


class RecoveryTests(unittest.TestCase):
    """Use isolated synthetic campaign files; generation is always mocked."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original_base = recovery.BASE
        recovery.BASE = self.root / "original"
        self.addCleanup(setattr, recovery, "BASE", self.original_base)
        recovery.BASE.mkdir()
        self.systems = {}
        for system in ("system_B", "system_C", "system_D", "system_E"):
            self.systems[system] = {"path": f"system_descriptions/{system}.txt", "sha256": recovery.INPUTS.get(system, "input-hash")}
            folder = recovery.BASE / system
            folder.mkdir()
            status = "success" if system in ("system_B", "system_D") else "failed"
            (folder / f"{system}_v2.0_run01_execution.json").write_text(json.dumps({"metadata_schema": "fmea-execution-1", "experiment_id": recovery.ORIGINAL,
                "attempt_id": f"{system}_v2.0_run01", "system_id": system, "model": recovery.MODEL,
                "prompt_version": "v2.0", "started_at": "2026-11-01T18:41:41Z", "status": status,
                "total_elapsed_seconds": 2, "estimated_api_expense_usd": None}))
            if status == "success": self.csv(folder / f"{system}_v2.0_run01.csv")
        (recovery.BASE / "campaign_manifest.json").write_text(json.dumps({"plan": {"model": recovery.MODEL, "temperature": 0, "skill_sha256": recovery.SKILL_HASH, "systems": self.systems}}))

    def csv(self, path):
        row = {f: (2 if f in recovery.engine.RATINGS else "synthetic") for f in recovery.engine.FIELDS}
        row = recovery.engine.parse_fmea(json.dumps([row]))[0]
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=recovery.engine.CSV_FIELDS)
            writer.writeheader(); writer.writerow(row)

    def receipt(self, system, folder, batch="recovery-1"):
        return {"attempt_id": system + "-retry", "status": "success", "elapsed_seconds": 3,
            "csv_path": "new.csv", "original_campaign_id": recovery.ORIGINAL,
            "recovery_campaign_id": batch, "supersedes_attempt_id": f"{system}_v2.0_run01",
            "system_id": system, "model": recovery.MODEL, "prompt_version": "v2.0",
            "skill_sha256": recovery.SKILL_HASH, "system_sha256": recovery.INPUTS[system],
            "temperature": 0, "started_at": "2026-11-01T20:00:00Z",
            "artifacts": {"new.csv": recovery.digest(folder / "new.csv")}}

    def test_reconcile_both_success_preserves_originals(self):
        plan = {"original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": "recovery-1", "systems": ["system_C", "system_E"]}
        planfile = self.root / "plan.json"; planfile.write_text(json.dumps(plan))
        batch = self.root / "batch" / "recovery-1"
        for system in plan["systems"]:
            folder = batch / system; folder.mkdir(parents=True)
            self.csv(folder / "new.csv")
            (folder / "recovery_metadata.json").write_text(json.dumps(self.receipt(system, folder)))
        out = self.root / "report"
        recovery.reconcile(planfile, self.root / "batch", out)
        manifest = json.loads((out / recovery.ORIGINAL / "recovery-1/reconciliation_manifest.json").read_text())
        self.assertEqual(manifest["effective_results"]["system_C"]["effective_attempt_id"], "system_C-retry")
        self.assertEqual(manifest["effective_results"]["system_B"]["effective_attempt_id"], "system_B_v2.0_run01")
        self.assertEqual(len((out / recovery.ORIGINAL / "recovery-1/all_attempts_history.csv").read_text().splitlines()), 7)
        self.assertFalse((recovery.BASE / "system_C/system_C_v2.0_run01.csv").exists())
        with self.assertRaises(FileExistsError): recovery.reconcile(planfile, self.root / "batch", out)

    def test_failed_recovery_stays_unresolved_and_unknown_cost(self):
        plan = {"original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": "recovery-2", "systems": ["system_C"]}
        planfile = self.root / "plan.json"; planfile.write_text(json.dumps(plan))
        folder = self.root / "batch/recovery-2/system_C"; folder.mkdir(parents=True)
        (folder / "recovery_metadata.json").write_text(json.dumps({"attempt_id": "retry", "original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": "recovery-2",
            "supersedes_attempt_id": "system_C_v2.0_run01", "skill_sha256": recovery.SKILL_HASH,
            "system_sha256": recovery.INPUTS["system_C"], "temperature": 0, "system_id": "system_C", "model": recovery.MODEL, "prompt_version": "v2.0", "started_at": "2026-11-01T20:00:00Z", "status": "failed", "elapsed_seconds": 1, "csv_path": None}))
        recovery.reconcile(planfile, self.root / "batch", self.root / "reports")
        manifest = json.loads((self.root / "reports" / recovery.ORIGINAL / "recovery-2/reconciliation_manifest.json").read_text())
        self.assertEqual(manifest["effective_results"]["system_C"]["status"], "unresolved")

    def test_partial_invalid_csv_and_conditions(self):
        for change in ("partial", "invalid", "missing", "original_campaign_id", "supersedes_attempt_id", "system_id", "model", "temperature", "prompt_version", "skill_sha256", "system_sha256", "csv_path"):
            with self.subTest(change=change):
                batch = "case-" + change
                folder = self.root / "batch" / batch / "system_C"; folder.mkdir(parents=True)
                self.csv(folder / "new.csv")
                receipt = self.receipt("system_C", folder, batch)
                if change == "invalid":
                    (folder / "new.csv").write_text("invalid")
                    receipt["artifacts"]["new.csv"] = recovery.digest(folder / "new.csv")
                elif change == "missing": (folder / "new.csv").unlink()
                elif change != "partial": receipt[change] = "wrong"
                (folder / "recovery_metadata.json").write_text(json.dumps(receipt))
                plan = self.root / (batch + ".json")
                plan.write_text(json.dumps({"original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": batch, "systems": ["system_C", "system_E"]}))
                if change not in ("partial", "invalid"):
                    with self.assertRaises(ValueError): recovery.reconcile(plan, self.root / "batch", self.root / "reports")
                    continue
                with patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                    recovery.reconcile(plan, self.root / "batch", self.root / "reports")
                report = self.root / "reports" / recovery.ORIGINAL / batch
                manifest = json.loads((report / "reconciliation_manifest.json").read_text())
                self.assertEqual(manifest["reconciliation_status"], "partial")
                metrics = json.loads((report / "financial_impacts" / "financial-v1" / "metrics.json").read_text())
                self.assertEqual(metrics["observed"]["n_attempts"], 5)
                self.assertEqual(metrics["observed"]["total_attempt_elapsed_seconds"], 11)
                self.assertIsNone(metrics["observed"]["cost_per_successful_generation_usd"])
                self.assertEqual(metrics["observed"]["effective_dataset_size"], 3 if change == "partial" else 2)

    def test_cumulative_partial_recovery(self):
        prior = []
        for system, batch in (("system_C", "first"), ("system_E", "second")):
            folder = self.root / "batch" / batch / system; folder.mkdir(parents=True)
            self.csv(folder / "new.csv")
            (folder / "recovery_metadata.json").write_text(json.dumps(self.receipt(system, folder, batch)))
            plan = self.root / (batch + ".json")
            plan.write_text(json.dumps({"original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": batch, "systems": [system]}))
            recovery.reconcile(plan, self.root / "batch", self.root / "reports", prior)
            result = self.root / "reports" / recovery.ORIGINAL / batch / "reconciliation_manifest.json"
            prior = [result]
        manifest = json.loads(result.read_text())
        self.assertEqual(manifest["attempt_count"], 6)
        self.assertEqual(manifest["reconciliation_status"], "complete")

    def test_ambiguous_plan_and_changed_original_rejected(self):
        plan = self.root / "plan.json"
        plan.write_text(json.dumps({"original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": "duplicate", "systems": ["system_C", "system_C"]}))
        with self.assertRaises(ValueError): recovery.reconcile(plan, self.root / "batch", self.root / "reports")
        plan.write_text(json.dumps({"original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": "changed", "systems": ["system_C"]}))
        receipt = recovery.BASE / "system_B/system_B_v2.0_run01_execution.json"
        record = json.loads(receipt.read_text()); record["artifacts"] = {"system_B_v2.0_run01.csv": {"sha256": "wrong"}}
        receipt.write_text(json.dumps(record))
        with self.assertRaises(ValueError): recovery.reconcile(plan, self.root / "batch", self.root / "reports")

    def test_financial_invoices_usage_and_history(self):
        from analysis.financial_impact.ingest import import_attempts
        from analysis.financial_impact.metrics import observed_summary
        from analysis.financial_impact.report import CONFIG
        assumptions = json.loads((CONFIG / "assumptions.json").read_text())
        receipts = [json.loads(p.read_text()) for p in recovery.BASE.glob("*/*execution.json")]
        receipts[0]["usage_metadata"] = {"prompt_token_count": 10, "candidates_token_count": 20, "thoughts_token_count": 3}
        path = self.root / "reconciled.json"
        path.write_text(json.dumps({"financial_schema": "reconciled-campaign-1", "attempts": receipts,
            "effective_results": {r["system_id"]: {"effective_attempt_id": r["attempt_id"] if r["status"] == "success" else None} for r in receipts}}))
        invoices = {recovery.ORIGINAL + "/" + r["attempt_id"]: .1 for r in receipts}
        records = import_attempts(path, assumptions, invoices=invoices)
        summary = observed_summary(records)
        self.assertEqual(summary["n_attempts"], 4)
        self.assertEqual(summary["n_failed_or_uncertain_attempts"], 2)
        self.assertEqual(summary["effective_dataset_size"], 2)
        self.assertAlmostEqual(summary["cost_per_successful_generation_usd"], .2)
        self.assertEqual(summary["generation_cost_basis"], "invoice")
        self.assertEqual(summary["known_tokens"]["thoughts_token_count"], 3)
        unknown = observed_summary(import_attempts(path, assumptions))
        self.assertIsNone(unknown["cost_per_successful_generation_usd"])

    def test_duplicate_or_unselected_generation_rejected_without_call(self):
        plan = self.root / "plan.json"; plan.write_text(json.dumps({"systems": ["system_C"], "recovery_campaign_id": "x"}))
        with patch.object(recovery.engine, "generate_fmea") as generate:
            with self.assertRaises(ValueError): recovery.generate(plan, "system_E", self.root / "out")
            generate.assert_not_called()


if __name__ == "__main__": unittest.main()
