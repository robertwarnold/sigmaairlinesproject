"""Synthetic offline D/E replication tests; never send provider or GitHub requests."""
import csv
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from scripts import system_replicates as campaign
from scripts import recover_fmea as recovery
from scripts import provider_recovery as provider


class ReplicatePolicyTests(unittest.TestCase):
    """Initial six observations, stable slot identity, early success and exact request budgets."""
    def plan(self,limit=12):
        return {"maximum_attempts_per_replicate":3 if limit==12 else 1,"maximum_requests_per_system":limit-3}

    def test_slots_and_scope(self):
        self.assertEqual(len(campaign.slots()),6)
        self.assertEqual(campaign.parse_batch("synthetic-study-D-r3-a2","system_D"),("synthetic-study",3,2))
        for batch,system in (("x-C-r1-a1","system_C"),("x-D-r4-a1","system_D"),("x-E-r1-a4","system_E"),("x-D-r1-a1","system_E")):
            with self.assertRaises(ValueError):campaign.parse_batch(batch,system)

    def test_initials_before_retries_and_successful_slot_never_repeats(self):
        attempts=[{"system_id":"system_D","replicate_number":1,"status":"failed","http_status":503,"failure_classification":"provider_unavailable_503"}]
        queue=campaign.pending_slots(self.plan(),attempts)
        self.assertEqual(len(queue),5)
        self.assertNotIn(("system_D",1,2),queue)
        all_succeeded=[{"system_id":s,"replicate_number":r,"status":"success"} for s,r in campaign.slots()]
        self.assertEqual(campaign.pending_slots(self.plan(),all_succeeded),[])

    def test_provider_retry_rounds_and_invalid_content_stop(self):
        attempts=[{"system_id":s,"replicate_number":r,"status":"failed","http_status":503,"failure_classification":"provider_unavailable_503"} for s,r in campaign.slots()]
        attempts.append({**attempts[0],"retry_number":1})
        queue=campaign.pending_slots(self.plan(),attempts)
        self.assertEqual(queue[0],("system_D",2,2))
        self.assertEqual(queue[-1],("system_D",1,3))
        self.assertEqual(campaign.pending_slots(self.plan(6),attempts),[])
        self.assertIsNone(campaign.retry_wait({"status":"failed","error_type":"ValueError"},1))

    def test_replication_budget_does_not_relax_recovery_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            provider.update(folder,reserved_requests=12,maximum_new_requests=12)
            with patch.object(provider,"github") as github:
                with self.assertRaises(ValueError):provider.run_workflow(folder,"wrapper","branch","replicate_single","batch","system_D")
                github.assert_not_called()
            provider.update(folder,reserved_requests=6)
            with patch.object(provider,"github",return_value="uncertain") as github:
                with self.assertRaises(RuntimeError):provider.run_workflow(folder,"wrapper","branch","replicate_single","batch","system_E")
                self.assertEqual(github.call_count,1)
            self.assertEqual(recovery.read(folder/"status.json")["reserved_requests"],7)
            with patch.object(provider,"github") as github:
                with self.assertRaises(ValueError):provider.run_workflow(folder,"wrapper","branch","ce_recovery_single","batch","system_C")
                github.assert_not_called()


class ReplicateReceiptTests(unittest.TestCase):
    """Exercise the one-call adapter, unique replica metadata and real CSV validation."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.addCleanup(patch.stopall)
        patch.object(campaign,"ROOT",self.root).start()
        source=self.root/"system_descriptions/system_D.txt";source.parent.mkdir();source.write_text("synthetic system")
        self.condition={"campaign_id":"synthetic-study","systems":{"system_D":{"path":"system_descriptions/system_D.txt","sha256":recovery.digest(source)}},"sdk_version":"synthetic-sdk","source_commit":"synthetic-commit"}
        self.planfile=self.root/"remote-plan.json";recovery.atomic(self.planfile,self.condition)
        self.config={"temperature":0,"max_output_tokens":65536,"retry_attempts":1}

    def generate(self,source,system,run,output_dir,model,execution):
        row={f:2 if f in campaign.engine.RATINGS else "synthetic" for f in campaign.engine.FIELDS}
        row=campaign.engine.parse_fmea(json.dumps([row]))[0]
        path=output_dir/f"{system}_v2.0_run{run:02d}.csv"
        with path.open("w",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=campaign.engine.CSV_FIELDS);writer.writeheader()
            writer.writerow({"case_id":system,"version":"v2.0","run":run,"model":model,**row})
        recovery.atomic(output_dir/f"{system}_v2.0_run{run:02d}_execution.json",{
            "metadata_schema":"fmea-execution-1","experiment_id":execution["experiment_id"],"attempt_id":f"{system}_v2.0_run{run:02d}",
            "system_id":system,"model":model,"prompt_version":"v2.0","skill_sha256":campaign.pilot.SKILL_HASH,
            "system_sha256":recovery.digest(source),"run_number":run,"configuration":self.config,"status":"success","row_count":1,
            "started_at":"2026-11-01T20:00:00Z","total_elapsed_seconds":3,"execution":{"request_invocations":1,"generation_seconds":2}})

    def test_valid_replicate_receipt_and_no_duplicate_call(self):
        with patch.object(campaign.pilot,"specification",return_value=self.condition),patch.object(campaign.importlib.metadata,"version",return_value="synthetic-sdk"), \
                patch.object(campaign.engine,"generate_fmea",side_effect=self.generate) as generate,patch.object(socket,"create_connection",side_effect=AssertionError("offline only")):
            campaign.remote(self.planfile,"synthetic-study-D-r2-a1","system_D",self.root/"out")
            self.assertEqual(generate.call_count,1)
            self.assertEqual(generate.call_args.kwargs["run"],2)
            with self.assertRaises(FileExistsError):campaign.remote(self.planfile,"synthetic-study-D-r2-a1","system_D",self.root/"out")
            self.assertEqual(generate.call_count,1)
        receipt=self.root/"out/system_D/r02/a01/attempt_metadata.json"
        plan={"campaign_id":"synthetic-study","condition":self.condition,"runtime_configurations":{"system_D":self.config}}
        record=campaign.check_receipt(receipt,plan,"system_D",2,1)
        self.assertEqual(record["attempt_id"],"system_D-r02-a01")
        csv_path=receipt.parent/record["csv_path"];csv_path.write_text("invalid")
        with self.assertRaises(ValueError):campaign.check_receipt(receipt,plan,"system_D",2,1)

    def test_mismatched_system_never_calls_generator(self):
        with patch.object(campaign.engine,"generate_fmea") as generate:
            with self.assertRaises(ValueError):campaign.remote(self.planfile,"synthetic-study-E-r2-a1","system_D",self.root/"out")
            generate.assert_not_called()

    def test_source_drift_never_calls_generator(self):
        with patch.object(campaign.pilot,"specification",return_value={**self.condition,"source_commit":"changed"}),patch.object(campaign.engine,"generate_fmea") as generate:
            with self.assertRaises(ValueError):campaign.remote(self.planfile,"synthetic-study-D-r2-a1","system_D",self.root/"out")
            generate.assert_not_called()


    def run_campaign(self,failed,quota=False):
        source=self.root/"system_descriptions/system_E.txt";source.write_text("synthetic E")
        self.condition["systems"]["system_E"]={"path":"system_descriptions/system_E.txt","sha256":recovery.digest(source)}
        folder=self.root/"campaign";folder.mkdir()
        baseline=self.root/"baseline.json";recovery.atomic(baseline,{"systems":[]})
        plan={"campaign_id":"synthetic-study","batch_id":"synthetic-study","condition":self.condition,"systems":["system_D","system_E"],
            "target_successes_per_system":3,"maximum_new_requests":12,"maximum_requests_per_system":9,"maximum_attempts_per_replicate":3,
            "authorization":"three_additional_D_and_E_datasets_up_to_12_requests","runtime_configurations":{s:self.config for s in campaign.SYSTEMS},"baseline_index":str(baseline)}
        recovery.atomic(folder/"plan.json",plan);recovery.atomic(folder/"original_checksums.json",{})
        provider.update(folder,maximum_new_requests=12,reserved_requests=0,attempts=[],retry_wait_seconds=0,replicate_status={f"{s}-r{r:02d}":"pending" for s,r in campaign.slots()})
        dispatched=[]
        def dispatch(folder,wrapper,branch,mode,batch,system,preflight_id=None):
            if mode=="multi_system_preflight":return "preflight","success"
            self.assertEqual(mode,"replicate_single");dispatched.append((batch,system))
            state=recovery.read(folder/"status.json");provider.update(folder,reserved_requests=state["reserved_requests"]+1)
            return str(len(dispatched)),"success"
        def download(wrapper,*args):
            target=Path(args[args.index("--dir")+1]);target.mkdir(parents=True)
            if args[2]=="preflight":recovery.atomic(target/"plan.json",self.condition);return ""
            batch,system=dispatched[int(args[2])-1]
            campaign.remote(self.planfile,batch,system,target)
            return ""
        def generate(*args,**kwargs):
            self.generate(*args,**kwargs)
            if failed:
                from google.genai.errors import ServerError, ClientError
                system=args[1];run=kwargs["run"];path=kwargs["output_dir"]/f"{system}_v2.0_run{run:02d}_execution.json"
                record=recovery.read(path);record.update(status="failed",row_count=None);recovery.atomic(path,record)
                if quota:raise ClientError(429,{"error":{"status":"RESOURCE_EXHAUSTED","message":"synthetic daily quota exhausted"}})
                raise ServerError(503,{"error":{"status":"UNAVAILABLE","message":"synthetic capacity failure"}})
        recovery.atomic(self.planfile,self.condition)
        with patch.object(campaign.pilot,"specification",return_value=self.condition),patch.object(campaign.importlib.metadata,"version",return_value="synthetic-sdk"), \
                patch.object(campaign.engine,"generate_fmea",side_effect=generate),patch.object(provider,"run_workflow",side_effect=dispatch), \
                patch.object(provider,"github",side_effect=download),patch.object(campaign,"retry_wait",side_effect=lambda r,n:0 if n<3 and r.get("http_status")==503 else None):
            if quota:
                with self.assertRaises(RuntimeError):campaign.worker(folder,"branch","wrapper")
            else:campaign.worker(folder,"branch","wrapper")
        state=recovery.read(folder/"status.json")
        self.assertEqual(len(dispatched),1 if quota else 12 if failed else 6)
        self.assertEqual(state["reserved_requests"],len(dispatched))
        self.assertEqual(state["phase"],"blocked" if quota else "generation_complete")
        self.assertTrue(all(s in campaign.SYSTEMS for _,s in dispatched))
        with self.assertRaises(FileExistsError):campaign.worker(folder,"branch","wrapper")
        return folder,state

    def test_six_successful_datasets_stop_and_report_separately(self):
        import zipfile
        folder,state=self.run_campaign(False)
        self.assertEqual(len({r["attempt_id"] for r in state["attempts"]}),6)
        with patch("analysis.financial_impact.report.figures",return_value={}):
            output,archive=campaign.complete(folder)
        summary=recovery.read(output/"campaign-summary.json")
        self.assertEqual(summary["successful_datasets"],6)
        self.assertEqual([s["additional_successful_datasets"] for s in summary["systems"]],[3,3])
        metrics=recovery.read(output/"financial_impacts/financial-v1/metrics.json")
        self.assertEqual(metrics["observed"]["n_attempts"],6)
        self.assertEqual(metrics["observed"]["n_successful_generations"],6)
        self.assertEqual(metrics["observed"]["effective_dataset_size"],6)
        self.assertIsNone(metrics["observed"]["cost_per_successful_generation_usd"])
        with zipfile.ZipFile(archive) as stream:self.assertIsNone(stream.testzip())

    def test_twelve_provider_failures_respect_shared_cap(self):
        folder,state=self.run_campaign(True)
        self.assertEqual(sum(r["status"]=="success" for r in state["attempts"]),0)
        self.assertTrue(all(r["http_status"]==503 for r in state["attempts"]))

    def test_quota_exhaustion_stops_before_any_further_dispatch(self):
        folder,state=self.run_campaign(True,quota=True)
        self.assertEqual(len(state["attempts"]),1)
        self.assertEqual(state["attempts"][0]["http_status"],429)

    def test_partial_quota_report_does_not_assume_zero_or_paid_cost(self):
        folder,state=self.run_campaign(True,quota=True)
        state["phase"]="generation_complete";state["stop_reason"]="provider_daily_quota_exhausted"
        record=state["attempts"][0]
        record["provider_diagnostic"]="synthetic quota metric generate_content_free_tier_requests"
        record["usage_metadata"]={"prompt_token_count":100,"candidates_token_count":200,"thoughts_token_count":10}
        recovery.atomic(Path(record["metadata_path"]),{k:v for k,v in record.items() if k not in ("metadata_path","workflow_run_id")})
        recovery.atomic(folder/"status.json",state)
        with patch("analysis.financial_impact.report.figures",return_value={}):output,archive=campaign.complete(folder)
        summary=recovery.read(output/"campaign-summary.json")
        self.assertTrue(summary["provider_reported_free_tier_quota"])
        self.assertEqual(summary["stop_reason"],"provider_daily_quota_exhausted")
        self.assertEqual(summary["successful_datasets"],0)
        metrics=recovery.read(output/"financial_impacts/financial-v1/metrics.json")
        self.assertIsNone(metrics["attempts"][0]["cost_usd"])
        self.assertEqual(metrics["observed"]["unknown_billing_attempts"],1)
