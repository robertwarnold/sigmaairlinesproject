"""Synthetic offline validation of the complete A-E index and immutable review ZIP."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile
import test_recover_fmea as fixtures
from scripts import recover_fmea as recovery
from scripts import complete_recovery_review as review


class ReviewTests(unittest.TestCase):
    """Use temporary generated fixtures; no project campaign output is fabricated or changed."""
    setUp = fixtures.RecoveryTests.setUp
    csv = fixtures.RecoveryTests.csv
    receipt = fixtures.RecoveryTests.receipt

    def test_complete_index_preserves_A_alternatives_and_history(self):
        folder = self.root / "campaign"; folder.mkdir()
        batch = "synthetic-review"
        records = []
        for system in ("system_C", "system_E"):
            target = folder / "attempts" / batch / system / "attempt-1"; target.mkdir(parents=True)
            self.csv(target / "new.csv")
            record = self.receipt(system, target, batch)
            record["retry_number"] = 0
            recovery.atomic(target / "recovery_metadata.json", record)
            records.append(record)
        recovery.atomic(folder / "plan.json", {"original_campaign_id":recovery.ORIGINAL,"recovery_campaign_id":batch,"systems":["system_C","system_E"]})
        recovery.reconcile(folder / "plan.json",folder / "attempts",folder / "reconciliation")
        recovery.atomic(folder / "status.json", {"phase":"generation_and_reconciliation_complete","attempts":records,"reserved_requests":2,"retry_wait_seconds":0,"systems":{"system_C":"success","system_E":"success"}})
        protected = self.root / "unchanged.txt"; protected.write_text("synthetic original")
        recovery.atomic(folder / "original_checksums.json", {str(protected):recovery.digest(protected)})
        recovery.atomic(folder / "original_provider_evidence.json", {s:{"http_status":503,"verification":"synthetic evidence"} for s in ("system_C","system_E")})
        baseline = self.root / "results/single-system-replicates/system_A/20261101T163923Z-system-a-five"; baseline.mkdir(parents=True)
        runs=[]
        for number in (3,4):
            path=baseline / f"system_A_v2.0_run{number:02d}.csv";self.csv(path)
            runs.append({"run_number":number,"status":"success","system_id":"system_A","model":recovery.MODEL,"prompt_version":"v2.0","started_at":"2026-11-01T16:00:00Z","duration_seconds":5,"row_count":1,"csv_file":path.name,"outputs":{path.name:{"sha256":recovery.digest(path)}}})
        recovery.atomic(baseline / "manifest.json", {"plan":{"batch_id":"synthetic-A","system_id":"system_A","model":recovery.MODEL,"prompt_version":"v2.0"},"runs":runs})
        with patch.object(review,"ROOT",self.root), patch.object(review,"figures"), patch("analysis.financial_impact.report.figures",return_value={}):
            output, archive=review.complete(folder)
            with self.assertRaises(FileExistsError):review.complete(folder)
        index=recovery.read(output / "A-E-dataset-index.json")
        self.assertEqual(index["effective_FMEA_count"],5)
        self.assertEqual(len(index["system_A_successful_pilot_outputs"]),2)
        self.assertEqual(index["systems"][0]["effective_attempt_id"],"system_A_v2.0_run03")
        financial=next((output / "financial_impacts").glob("*/metrics.json"))
        metrics=recovery.read(financial)
        self.assertEqual(metrics["observed"]["effective_dataset_size"],5)
        self.assertEqual(metrics["observed"]["provider_unavailable_503_count"],2)
        self.assertIsNone(metrics["observed"]["cost_per_successful_generation_usd"])
        with zipfile.ZipFile(archive) as stream:
            self.assertIsNone(stream.testzip())
            self.assertIn("review-v1/A-E-dataset-index.json",stream.namelist())
        for name,digest in recovery.read(output / "review-checksums.json").items():
            self.assertEqual(recovery.digest(output / name),digest)
        self.assertEqual(protected.read_text(),"synthetic original")
