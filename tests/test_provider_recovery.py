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

    def synthetic_worker(self, success):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recovery.atomic(root / "plan.json", {"recovery_campaign_id":"synthetic-worker", "policy":retry.POLICY, "systems":["system_C","system_E"]})
            retry.update(root, reserved_requests=0, attempts=[], retry_wait_seconds=0, systems={"system_C":"pending","system_E":"pending"})
            invocations = []
            def dispatch(folder, wrapper, branch, mode, batch, system, preflight_id=None):
                if mode == "multi_system_preflight":return "preflight", "success"
                invocations.append((batch,system))
                state=recovery.read(root / "status.json")
                retry.update(root,reserved_requests=state["reserved_requests"]+1)
                return str(len(invocations)),"success"
            def download(wrapper, *args):
                path=Path(args[args.index("--dir")+1]);path.mkdir(parents=True)
                if args[2]=="preflight":return ""
                batch,system=invocations[int(args[2])-1]
                number=int(batch[-1])
                recovery.atomic(path / "recovery_metadata.json", {"system_id":system,"recovery_campaign_id":"synthetic-worker","retry_number":number-1,
                    "attempt_id":batch,"status":"success" if success else "failed","csv_path":"synthetic.csv" if success else None,
                    "row_count":1 if success else None,"elapsed_seconds":2,"execution":{"request_invocations":1},"artifacts":{},
                    "failure_classification":None if success else "provider_unavailable_503","http_status":None if success else 503})
                return ""
            with patch.object(retry,"run_workflow",side_effect=dispatch), patch.object(retry,"github",side_effect=download), \
                    patch.object(recovery,"validate_csv"), patch.object(recovery,"reconcile",return_value=root / "reconciliation") as reconcile, patch.object(retry,"retry_delay",return_value=0):
                retry.worker(root,"branch","wrapper")
                reconcile.assert_called_once()
            state=recovery.read(root / "status.json")
            self.assertEqual(len(invocations),2 if success else 6)
            self.assertEqual(state["systems"],{s:"success" if success else "unresolved" for s in ("system_C","system_E")})
            self.assertEqual(state["reserved_requests"],len(invocations))
            with self.assertRaises(FileExistsError):retry.worker(root,"branch","wrapper")

    def test_worker_stops_after_first_success_each_system(self):
        self.synthetic_worker(True)

    def test_worker_stops_at_three_attempts_each_and_six_total(self):
        self.synthetic_worker(False)


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
        metrics = recovery.read(output / "financial_impacts" / "financial-v1" / "metrics.json")
        self.assertEqual(metrics["observed"]["provider_unavailable_503_count"], 2)
        self.assertEqual(metrics["observed"]["retry_wait_seconds"], 120)
        # A second successful candidate cannot silently replace or coexist with the first.
        failed = self.root / "batch" / batch / system / "attempt-2/recovery_metadata.json"
        record = recovery.read(failed); record.update(status="success", csv_path="new.csv")
        recovery.atomic(failed, record)
        with self.assertRaises(ValueError): recovery.reconcile(plan, self.root / "batch", self.root / "ambiguous")


class COnlyTests(unittest.TestCase):
    """The separately authorized C-only budget permits six calls, never E calls."""
    def test_c_retry_policy_and_typed_transport(self):
        import httpx
        record=retry.diagnostic(httpx.RemoteProtocolError("synthetic disconnect"))
        self.assertEqual(retry.c_retry_delay(record,1),60)
        self.assertEqual(retry.c_retry_delay(record,5),300)
        self.assertIsNone(retry.c_retry_delay(record,6))
        self.assertIsNone(retry.c_retry_delay(retry.diagnostic(RuntimeError("503 or disconnect")),1))
        self.assertIsNone(retry.c_retry_delay({"http_status":403},1))
        self.assertEqual(retry.c_retry_delay({"http_status":503,"failure_classification":"provider_unavailable_503","retry_after":"200"},2),200)

    def test_remote_sixth_attempt_and_seventh_rejection(self):
        plan={"campaign_id":"synthetic-c-six","sdk_version":"synthetic-sdk"}
        with patch.object(recovery,"read",return_value=plan), patch.object(retry.pilot,"specification",return_value=plan), \
                patch.object(retry.importlib.metadata,"version",return_value="synthetic-sdk"), patch.object(recovery,"atomic"), patch.object(recovery,"generate") as generate:
            retry.remote("plan","system_C","synthetic-c-six-C-attempt-6","out")
            self.assertEqual(generate.call_args.args[-1],6)
            with self.assertRaises(ValueError):retry.remote("plan","system_C","synthetic-c-six-C-attempt-7","out")
            with self.assertRaises(ValueError):retry.remote("plan","system_E","synthetic-c-six-E-attempt-6","out")
            self.assertEqual(generate.call_count,1)

    def run_c_worker(self,success_at):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            recovery.atomic(root/"plan.json",{"systems":["system_C"],"policy":retry.C_ONLY_POLICY,"authorization":"up_to_six_additional_C_requests","recovery_campaign_id":"synthetic-c-six"})
            recovery.atomic(root/"history.json",{"effective_results":{"system_C":{"status":"unresolved"},"system_E":{"status":"success"}}})
            retry.update(root,reserved_requests=0,attempts=[],retry_wait_seconds=0)
            calls=[]
            def dispatch(folder,wrapper,branch,mode,batch,system,preflight_id=None):
                self.assertEqual(system,"system_C")
                if mode=="multi_system_preflight":return "preflight","success"
                calls.append(batch);state=recovery.read(root/"status.json")
                retry.update(root,reserved_requests=state["reserved_requests"]+1)
                return str(len(calls)),"success"
            def download(wrapper,*args):
                target=Path(args[args.index("--dir")+1]);target.mkdir(parents=True)
                if args[2]=="preflight":return ""
                number=int(args[2]);success=number==success_at
                record={"original_campaign_id":recovery.ORIGINAL,"recovery_campaign_id":"synthetic-c-six","system_id":"system_C","retry_number":number-1,
                    "model":recovery.MODEL,"temperature":0,"prompt_version":"v2.0","skill_sha256":recovery.SKILL_HASH,"system_sha256":recovery.INPUTS["system_C"],
                    "attempt_id":f"synthetic-{number}","execution":{"request_invocations":1},"artifacts":{},"status":"success" if success else "failed",
                    "http_status":None if success else 503,"csv_path":"synthetic.csv" if success else None}
                recovery.atomic(target/"recovery_metadata.json",record)
                return ""
            with patch.object(retry,"run_workflow",side_effect=dispatch),patch.object(retry,"github",side_effect=download), \
                    patch.object(recovery,"validate_csv"),patch.object(recovery,"reconcile",return_value=root/"reconciled"), \
                    patch.object(retry,"c_retry_delay",side_effect=lambda r,n:0 if n<6 else None):
                retry.c_worker(root,"branch","wrapper",root/"history.json")
            self.assertEqual(len(calls),success_at or 6)
            state=recovery.read(root/"status.json")
            self.assertEqual(state["reserved_requests"],len(calls))
            self.assertEqual(state["systems"]["system_C"],"success" if success_at else "unresolved")
            with self.assertRaises(FileExistsError):retry.c_worker(root,"branch","wrapper",root/"history.json")

    def test_c_stops_at_first_success(self):self.run_c_worker(2)

    def test_c_stops_at_six_failures(self):self.run_c_worker(None)
