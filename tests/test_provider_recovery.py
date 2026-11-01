"""Offline bounded-retry tests: synthetic SDK responses, no provider or GitHub calls."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from google.genai.errors import ServerError, ClientError
from scripts import provider_recovery as retry
from scripts import recover_fmea as recovery
import test_recover_fmea as fixtures


class RetryPolicyTests(unittest.TestCase):
    """Verify only explicit HTTP 503 permits bounded retry and provider wait handling."""
    def test_typed_503_only(self):
        error = ServerError(503, {"error": {"status": "UNAVAILABLE", "message": "high demand"}})
        record = retry.diagnostic(error)
        self.assertEqual(record["failure_classification"], "provider_unavailable_503")
        self.assertEqual(retry.retry_delay(record, 0), 60)
        self.assertEqual(retry.retry_delay(record, 1), 120)
        self.assertIsNone(retry.retry_delay(record, 2))
        for error in (RuntimeError("HTTP 503"), ConnectionError("503"), ValueError("schema invalid"), ClientError(403, {}), ServerError(500, {})):
            self.assertIsNone(retry.retry_delay(retry.diagnostic(error), 0))

    def test_retry_after_and_redaction(self):
        error = ServerError(503, {"error": {"message": "synthetic-secret"}}, response=SimpleNamespace(headers={"retry-after": "90"}))
        with patch.dict("os.environ", {"GEMINI_API_KEY": "synthetic-secret"}):
            record = retry.diagnostic(error)
        self.assertNotIn("synthetic-secret", record["provider_diagnostic"])
        self.assertEqual(retry.retry_delay(record, 0), 90)
        for value in ("10000", "nan", "invalid"):
            self.assertIsNone(retry.retry_delay({**record, "retry_after": value}, 0))

    def test_budget_exhaustion_never_dispatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            retry.update(root, reserved_requests=6)
            with patch.object(retry, "github") as call:
                with self.assertRaises(ValueError): retry.run_workflow(root, "wrapper", "branch", "ce_recovery_single", "batch", "system_C")
                call.assert_not_called()

    def test_uncertain_dispatch_reservation_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            retry.update(root, reserved_requests=0)
            with patch.object(retry, "github", return_value="uncertain") as call:
                with self.assertRaises(RuntimeError): retry.run_workflow(root, "wrapper", "branch", "ce_recovery_single", "batch", "system_C")
                self.assertEqual(call.call_count, 1)
            self.assertEqual(recovery.read(root / "status.json")["reserved_requests"], 1)

    def test_wrong_remote_identity_never_generates(self):
        with patch.object(recovery, "generate") as call:
            with self.assertRaises(ValueError): retry.remote("not-read", "system_C", "campaign-E-attempt-1", "out")
            call.assert_not_called()


class RetryReconciliationTests(unittest.TestCase):
    """Extend isolated synthetic fixtures to exercise multiple failed retries plus a success."""
    setUp = fixtures.RecoveryTests.setUp
    csv = fixtures.RecoveryTests.csv
    receipt = fixtures.RecoveryTests.receipt

    def test_two_503_failures_then_success(self):
        batch = "bounded"
        system = "system_C"
        for number in (1, 2, 3):
            folder = self.root / "batch" / batch / system / f"attempt-{number}"
            folder.mkdir(parents=True)
            self.csv(folder / "new.csv")
            record = self.receipt(system, folder, batch)
            record.update(attempt_id=f"C-recovery-{number}", retry_number=number-1, retry_wait_seconds=60 if number < 3 else 0)
            if number < 3: record.update(status="failed", http_status=503, failure_classification="provider_unavailable_503", csv_path=None)
            recovery.atomic(folder / "recovery_metadata.json", record)
        plan = self.root / "plan.json"
        recovery.atomic(plan, {"original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": batch, "systems": [system]})
        recovery.reconcile(plan, self.root / "batch", self.root / "reports")
        output = self.root / "reports" / recovery.ORIGINAL / batch
        manifest = recovery.read(output / "reconciliation_manifest.json")
        self.assertEqual(manifest["attempt_count"], 7)
        self.assertEqual(manifest["effective_results"][system]["effective_attempt_id"], "C-recovery-3")
        metrics = recovery.read(output / "financial_impacts" / (batch + "-financial-v1") / "metrics.json")
        self.assertEqual(metrics["observed"]["provider_unavailable_503_count"], 2)
        self.assertEqual(metrics["observed"]["retry_wait_seconds"], 120)
        # A second successful candidate cannot silently replace or coexist with the first.
        failed = self.root / "batch" / batch / system / "attempt-2/recovery_metadata.json"
        record = recovery.read(failed); record.update(status="success", csv_path="new.csv")
        recovery.atomic(failed, record)
        with self.assertRaises(ValueError): recovery.reconcile(plan, self.root / "batch", self.root / "ambiguous")
