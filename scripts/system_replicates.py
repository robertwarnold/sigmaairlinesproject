"""Three additional D/E FMEA datasets: immutable attempts, bounded provider retries and offline analysis."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import sys
import threading
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fmea_generator as engine
from scripts import multi_system_pilot as pilot
from scripts import provider_recovery as provider
from scripts import recover_fmea as recovery
from scripts import evaluate_multi_system as evaluation
from scripts.single_system_replicates import write_csv
from analysis.financial_impact.report import create_report

SYSTEMS = ("system_D", "system_E")
TARGET = 3


def slots():
    """Keep each of the six planned replicate observations independently identified."""
    return [(system, replica) for system in SYSTEMS for replica in range(1, TARGET + 1)]


def prepare(folder, request_limit, baseline_index):
    """Freeze the unchanged experiment and original evidence before any paid request."""
    if request_limit not in (6, 12): raise ValueError("Authorize either six initial requests or twelve including provider retries")
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
    campaign = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-DE-three-" + uuid.uuid4().hex[:8]
    condition = pilot.specification(campaign)
    original = recovery.read(recovery.BASE / "campaign_manifest.json")["plan"]
    for key in ("systems", "model", "temperature", "prompt_version", "skill_sha256", "response_schema_sha256", "max_output_tokens", "sdk_version", "retry_attempts"):
        if condition[key] != original[key]: raise ValueError("Original condition mismatch: " + key)
    if importlib.metadata.version("google-genai") != condition["sdk_version"]: raise ValueError("SDK mismatch")
    baseline_index = Path(baseline_index).resolve()
    baseline = recovery.read(baseline_index)
    protected = [ROOT / "fmea_generator.py", ROOT / "skill/fmea_instructions.md", baseline_index,
        *[ROOT / "system_descriptions" / (s + ".txt") for s in SYSTEMS], *recovery.BASE.rglob("*")]
    for row in baseline["systems"]:
        if row.get("path"):
            source=Path(row["path"])
            if recovery.digest(source)!=row["csv_sha256"]:raise ValueError("Baseline CSV changed")
            protected.append(source)
    runtime_configs = {system: recovery.read(recovery.BASE/system/f"{system}_v2.0_run01_execution.json")["configuration"] for system in SYSTEMS}
    plan = {"campaign_id":campaign, "batch_id":campaign, "condition":condition, "systems":list(SYSTEMS),
        "target_successes_per_system":TARGET, "maximum_new_requests":request_limit,
        "maximum_requests_per_system":request_limit-TARGET, "maximum_attempts_per_replicate":3 if request_limit==12 else 1,
        "authorization":"three_additional_D_and_E_datasets" + ("_up_to_12_requests" if request_limit==12 else "_six_requests"),
        "baseline_index":str(baseline_index), "runtime_configurations":runtime_configs,
        "created_at":datetime.now(timezone.utc).isoformat(), "replicate_slots":[f"{s}-r{n:02d}" for s,n in slots()]}
    recovery.atomic(folder/"plan.json",plan)
    recovery.atomic(folder/"original_checksums.json",{str(p.resolve()):recovery.digest(p) for p in protected if p.is_file()})
    provider.update(folder, campaign_title="D/E three additional datasets", campaign_id=campaign,
        phase="preflight_complete", maximum_new_requests=request_limit,reserved_requests=0,attempts=[],retry_wait_seconds=0,
        replicate_status={key:"pending" for key in plan["replicate_slots"]})
    return plan


def parse_batch(batch, system):
    """Reject out-of-scope systems, slot numbers and attempt numbers before provider access."""
    match=re.fullmatch(r"(.+)-([DE])-r([123])-a([123])",batch)
    if not match or system!="system_"+match[2]:raise ValueError("Invalid D/E replicate attempt")
    return match[1],int(match[3]),int(match[4])


def remote(plan_path, batch, system, output):
    """Use the unchanged generator once and preserve either outcome in a unique attempt directory."""
    campaign,replica,attempt=parse_batch(batch,system)
    if os.getenv("GITHUB_RUN_ATTEMPT","1")!="1":raise ValueError("Workflow reruns prohibited")
    frozen=recovery.read(plan_path)
    current=pilot.specification(campaign)
    if frozen["campaign_id"]!=campaign or any(frozen.get(k)!=v for k,v in current.items()):raise ValueError("Same-commit preflight mismatch")
    if importlib.metadata.version("google-genai")!=frozen["sdk_version"]:raise ValueError("SDK changed")
    root=Path(output)/system/f"r{replica:02d}"/f"a{attempt:02d}";root.mkdir(parents=True,exist_ok=False)
    source=ROOT/frozen["systems"][system]["path"]
    if recovery.digest(source)!=frozen["systems"][system]["sha256"]:raise ValueError("Execution-byte input hash mismatch")
    stop=threading.Event();start=time.perf_counter()
    heartbeat=threading.Thread(target=recovery.heartbeat,args=(stop,f"{system} replicate {replica} attempt {attempt}",start),daemon=True)
    heartbeat.start();diagnostics={}
    try:
        engine.generate_fmea(source,system,run=replica,output_dir=root,model=pilot.MODEL,
            execution={"experiment_id":campaign,"expected_max_output_tokens":pilot.TOKEN_LIMIT})
    except Exception as error:
        diagnostics=provider.diagnostic(error)
    finally:
        stop.set();heartbeat.join(timeout=2)
        sidecar=root/f"{system}_v2.0_run{replica:02d}_execution.json"
        if not sidecar.exists():raise RuntimeError("Generator did not preserve an execution receipt")
        record=recovery.read(sidecar)
        record.update(diagnostics,source_attempt_id=record["attempt_id"],attempt_id=f"{system}-r{replica:02d}-a{attempt:02d}",
            replicate_number=replica,retry_number=attempt-1,elapsed_seconds=time.perf_counter()-start,source_receipt=sidecar.name,
            provider_billing_usd=None,engineering_review_status="provisional_unreviewed")
        csv_path=root/f"{system}_v2.0_run{replica:02d}.csv"
        if record["status"]=="success":
            recovery.validate_csv(csv_path);record["csv_path"]=csv_path.name
        record["artifacts"]={p.name:{"sha256":recovery.digest(p),"bytes":p.stat().st_size} for p in root.iterdir() if p.is_file()}
        recovery.atomic(root/"attempt_metadata.json",record)
        print(f"[REPLICATE] {system} r{replica} a{attempt}: {record['status']}; HTTP {record.get('http_status')}; rows={record.get('row_count')}",flush=True)


def check_receipt(path, plan, system, replica, attempt):
    """Verify request identity, exact runtime settings, artifact hashes and successful CSV content."""
    path=Path(path);record=recovery.read(path)
    expected={"experiment_id":plan["campaign_id"],"system_id":system,"replicate_number":replica,"retry_number":attempt-1,
        "attempt_id":f"{system}-r{replica:02d}-a{attempt:02d}","model":pilot.MODEL,"prompt_version":"v2.0",
        "skill_sha256":pilot.SKILL_HASH,"system_sha256":plan["condition"]["systems"][system]["sha256"]}
    if any(record.get(k)!=v for k,v in expected.items()):raise ValueError("Replicate identity/configuration mismatch")
    if record.get("execution",{}).get("request_invocations")!=1:raise RuntimeError("Unconfirmed request count; no automatic redispatch")
    if record["configuration"]!=plan["runtime_configurations"][system]:raise ValueError("Original runtime settings changed")
    for name,item in record["artifacts"].items():
        if Path(name).name!=name or recovery.digest(path.parent/name)!=item["sha256"]:raise ValueError("Replicate artifact integrity failure")
    if record["status"]=="success":
        name=record.get("csv_path","")
        if not name or Path(name).name!=name:raise ValueError("Missing/unsafe successful CSV path")
        csv_path=path.parent/name;recovery.validate_csv(csv_path)
        import csv
        with csv_path.open(encoding="utf-8-sig") as stream:
            rows=list(csv.DictReader(stream))
        if any(r["case_id"]!=system or r["version"]!="v2.0" or r["run"]!=str(replica) or r["model"]!=pilot.MODEL for r in rows):
            raise ValueError("CSV metadata mismatch")
        if len(rows)!=record["row_count"]:raise ValueError("CSV row count mismatch")
    return record


def retry_wait(record, attempt):
    """Retry only verified provider capacity/transport failures within the authorized extra budget."""
    return provider.c_retry_delay(record,attempt) if attempt<3 else None


def pending_slots(plan, attempts):
    """Schedule all initial observations before bounded retries; never regenerate a successful slot."""
    initial=[];retry=[]
    for system,replica in slots():
        records=[r for r in attempts if r["system_id"]==system and r["replicate_number"]==replica]
        if any(r["status"]=="success" for r in records):continue
        if not records:initial.append((system,replica,1))
        elif len(records)<plan["maximum_attempts_per_replicate"] and retry_wait(records[-1],len(records)) is not None:
            if sum(r["system_id"]==system for r in attempts)<plan["maximum_requests_per_system"]:
                retry.append((system,replica,len(records)+1))
    return initial or sorted(retry,key=lambda slot:(slot[2],slot[0],slot[1]))


def worker(folder, branch, wrapper):
    """Run at most the authorized six/twelve requests and stop after three valid D and E datasets."""
    folder=Path(folder)
    with (folder/"worker.lock").open("x") as stream:stream.write(str(os.getpid()))
    plan=recovery.read(folder/"plan.json")
    limit=plan["maximum_new_requests"]
    expected="three_additional_D_and_E_datasets"+("_up_to_12_requests" if limit==12 else "_six_requests")
    if limit not in (6,12) or plan["authorization"]!=expected or plan["systems"]!=list(SYSTEMS) or plan["target_successes_per_system"]!=3:
        raise ValueError("D/E replication authorization mismatch")
    try:
        preflight,conclusion=provider.run_workflow(folder,wrapper,branch,"multi_system_preflight",plan["campaign_id"],"system_D")
        if conclusion!="success":raise RuntimeError("No-generation remote preflight failed")
        provider.github(wrapper,"run","download",preflight,"--name","multi-system-preflight-"+preflight,"--dir",str(folder/"remote-preflight"))
        remote_plan=recovery.read(folder/"remote-preflight/plan.json")
        if any(remote_plan.get(k)!=v for k,v in plan["condition"].items()):raise ValueError("Local/remote frozen condition mismatch")
        provider.update(folder,phase="remote_preflight_complete",preflight_run_id=preflight)
        while True:
            state=recovery.read(folder/"status.json");attempts=state["attempts"]
            queue=pending_slots(plan,attempts)
            if not queue or state["reserved_requests"]>=limit:break
            system,replica,number=queue[0]
            if number>1:
                old=[r for r in attempts if r["system_id"]==system and r["replicate_number"]==replica][-1]
                delay=retry_wait(old,number-1)
                provider.update(folder,phase="retry_wait",active_system=system,replicate_number=replica,message=f"Provider retry {number}/3 after {delay}s")
                start=time.perf_counter()
                while time.perf_counter()-start<delay:
                    time.sleep(max(0,min(30,delay-(time.perf_counter()-start))))
                    provider.update(folder,phase="retry_wait",message=f"Actual waiting {time.perf_counter()-start:.1f}s / {delay}s")
                actual=time.perf_counter()-start
                state=recovery.read(folder/"status.json")
                prior=next(r for r in state["attempts"] if r["attempt_id"]==old["attempt_id"])
                prior["retry_wait_seconds"]=actual
                recovery.atomic(Path(prior["metadata_path"]),{k:v for k,v in prior.items() if k not in ("metadata_path","workflow_run_id")})
                provider.update(folder,attempts=state["attempts"],retry_wait_seconds=state["retry_wait_seconds"]+actual)
            for path,digest in recovery.read(folder/"original_checksums.json").items():
                if recovery.digest(path)!=digest:raise ValueError("Original evidence changed")
            batch=f"{plan['campaign_id']}-{system[-1]}-r{replica}-a{number}"
            provider.update(folder,phase="starting_attempt",active_system=system,replicate_number=replica,attempt_number=number,
                message=f"{system} additional dataset {replica}/3, attempt {number}; campaign cap {limit}")
            run,conclusion=provider.run_workflow(folder,wrapper,branch,"replicate_single",batch,system,preflight)
            download=ROOT/"results/github"/run
            provider.github(wrapper,"run","download",run,"--name",f"system-replicate-{batch}-{run}","--dir",str(download))
            matches=list(download.rglob("attempt_metadata.json"))
            if len(matches)!=1:raise RuntimeError("Missing/ambiguous receipt; do not redispatch")
            record=check_receipt(matches[0],plan,system,replica,number)
            destination=folder/"attempts"/system/f"r{replica:02d}"/f"a{number:02d}"
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(matches[0].parent,destination)
            record.update(metadata_path=str((destination/"attempt_metadata.json").resolve()),workflow_run_id=run)
            state=recovery.read(folder/"status.json");state["attempts"].append(record)
            state["replicate_status"][f"{system}-r{replica:02d}"]=record["status"]
            provider.update(folder,phase="attempt_complete",attempts=state["attempts"],replicate_status=state["replicate_status"],
                message=f"{system} dataset {replica}: {record['status']}; HTTP {record.get('http_status')}; rows={record.get('row_count')}")
            if record.get("http_status") in (400,401,403,404):raise RuntimeError("Provider authentication/configuration error; stop")
        provider.update(folder,phase="generation_complete",message="No further calls; offline replicate analysis and financial reporting")
    except BaseException as error:
        provider.update(folder,phase="blocked",message=f"{type(error).__name__}: {error}; no automatic restart")
        raise


def complete(folder):
    """Create immutable per-replicate analysis and cost reports; successful drafts stay separate."""
    folder=Path(folder).resolve();plan=recovery.read(folder/"plan.json");state=recovery.read(folder/"status.json")
    if state["phase"]!="generation_complete":raise ValueError("Generation is not complete")
    records=state["attempts"]
    if len(records)>plan["maximum_new_requests"] or state["reserved_requests"]>plan["maximum_new_requests"]:raise ValueError("Request cap exceeded")
    if any(sum(r["system_id"]==s for r in records)>plan["maximum_requests_per_system"] for s in SYSTEMS):raise ValueError("System request cap exceeded")
    for path,digest in recovery.read(folder/"original_checksums.json").items():
        if recovery.digest(path)!=digest:raise ValueError("Original evidence changed")
    output=folder/"review-v1";output.mkdir(exist_ok=False)
    manifest={"plan":plan,"runs":records};recovery.atomic(output/"campaign-manifest.json",manifest)
    financial,metrics=create_report([output/"campaign-manifest.json"],output/"financial_impacts",analysis_id="financial-v1")
    rows=[];structures={};distributions=[]
    for system,replica in slots():
        attempts=[r for r in records if r["system_id"]==system and r["replicate_number"]==replica]
        valid=[r for r in attempts if r["status"]=="success"]
        if len(valid)>1:raise ValueError("Ambiguous successful replicate")
        chosen=valid[0] if valid else None
        row={"system_id":system,"replicate_number":replica,"status":"success" if chosen else "unresolved",
            "attempt_id":chosen["attempt_id"] if chosen else None,"csv_path":None,"row_count":None,
            "generation_seconds":chosen["total_elapsed_seconds"] if chosen else None,"requests":len(attempts),
            "http_503_failures":sum(r.get("http_status")==503 for r in attempts),"engineering_review_status":"provisional_unreviewed"}
        if chosen:
            source=Path(chosen["metadata_path"]);check_receipt(source,plan,system,replica,chosen["retry_number"]+1)
            csv_path=source.parent/chosen["csv_path"];row["csv_path"]=str(csv_path);row["row_count"]=chosen["row_count"]
            target=output/"datasets"/system;target.mkdir(parents=True,exist_ok=True);shutil.copy2(csv_path,target/csv_path.name)
            data=evaluation.structure(csv_path,system);structures[f"{system}/r{replica}"]=data
            for metric,counts in data["ratings"].items():
                distributions.extend({"system_id":system,"replicate_number":replica,"metric":metric,"score":score,"row_count":n} for score,n in counts.items())
        rows.append(row)
    write_csv(output/"replicate-index.csv",list(rows[0]),rows)
    if distributions:write_csv(output/"provisional-rating-distributions.csv",list(distributions[0]),distributions)
    recovery.atomic(output/"structure-metrics.json",structures)
    summaries=[]
    for system in SYSTEMS:
        success=[r for r in rows if r["system_id"]==system and r["status"]=="success"]
        counts=[r["row_count"] for r in success];durations=[r["generation_seconds"] for r in success]
        summaries.append({"system_id":system,"additional_successful_datasets":len(success),"target":3,
            "requests":sum(r["system_id"]==system for r in records),"row_counts":counts,
            "mean_rows":statistics.mean(counts) if counts else None,"sample_sd_rows":statistics.stdev(counts) if len(counts)>1 else None,
            "mean_success_seconds":statistics.mean(durations) if durations else None,"engineering_acceptance":None})
    summary={"campaign_id":plan["campaign_id"],"systems":summaries,"total_new_requests":len(records),
        "successful_datasets":sum(r["status"]=="success" for r in rows),"target_datasets":6,
        "failed_requests":sum(r["status"]!="success" for r in records),"actual_retry_wait_seconds":state["retry_wait_seconds"],
        "financial_observed":metrics["observed"],"baseline_index":plan["baseline_index"],"replicate_index":rows,
        "financial_report":str(financial),"caution":"Three separate drafts per system; rows are nested observations. No engineering acceptance, reference coverage or validated repeatability claim."}
    recovery.atomic(output/"campaign-summary.json",summary)
    notes=["# D/E additional replicate campaign", "", "Each new successful CSV is a separate observation. Original D/E outputs remain separate and unchanged.",
        "S/O/D and RPN are provisional; no reference FMEA was read. Row distributions and n=3 summaries are descriptive, not engineering acceptance or independent row-level replication.", ""]
    for key,data in structures.items():
        notes.extend(["## "+key,f"Rows: {data['row_count']}; labels: {data['distinct_components']}; duplicate component/mode/cause triples: {data['exact_duplicate_triples']}; one-row labels: {len(data['single_mode_component_labels'])}.",
            "Possible unit-coverage/omission candidates (lexical only): "+str([i["inventory_component"] for i in data["inventory"] if i["needs_omission_or_unit_review"]]),
            "Review generated assumption/detection/severity/occurrence rationales against the input architecture; no defect or coverage percentage is adjudicated here.",""])
    (output/"engineering-review.md").write_text("\n".join(notes),encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for row in rows:
        if row["status"]=="success":
            label=row["system_id"][-1]+str(row["replicate_number"])
            axes[0].scatter(label,row["row_count"]);axes[1].scatter(label,row["generation_seconds"])
    axes[0].set(ylabel="Generated rows / separate draft");axes[1].set(ylabel="Successful attempt seconds")
    fig.suptitle("Three additional replicates per system; descriptive, unreviewed")
    fig.tight_layout();fig.savefig(output/"replicate-comparison.png",dpi=300);plt.close(fig)
    checksums={str(p.relative_to(output)).replace("\\","/"):recovery.digest(p) for p in output.rglob("*") if p.is_file()}
    recovery.atomic(output/"checksums.json",checksums)
    for path in output.rglob("*"):
        if path.is_file() and path.suffix in (".json",".csv",".md",".txt"):
            if re.search(r"AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN .*PRIVATE KEY",path.read_text(encoding="utf-8-sig")):
                raise ValueError("Possible credential in review package; ZIP not created")
    archive=folder/(plan["campaign_id"]+"-review.zip")
    with zipfile.ZipFile(archive,"x",zipfile.ZIP_DEFLATED) as stream:
        for path in output.rglob("*"):
            if path.is_file():stream.write(path,"review-v1/"+str(path.relative_to(output)).replace("\\","/"))
    provider.update(folder,phase="outputs_ready",review_directory=str(output),review_zip=str(archive),message=f"{summary['successful_datasets']}/6 additional valid datasets; no further calls")
    print(json.dumps(summary,indent=2));return output,archive


def main():
    """Expose explicit preparation, one remote call, bounded campaign execution and offline reports."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("prepare","remote","worker","complete"));parser.add_argument("--folder",type=Path,required=True)
    parser.add_argument("--request-limit",type=int,choices=(6,12),default=6);parser.add_argument("--baseline-index",type=Path)
    parser.add_argument("--plan",type=Path);parser.add_argument("--batch");parser.add_argument("--system",choices=SYSTEMS)
    parser.add_argument("--branch",default="fmea-ce-recovery-20261101");parser.add_argument("--wrapper",type=Path)
    args=parser.parse_args()
    if args.mode=="prepare":prepare(args.folder,args.request_limit,args.baseline_index)
    elif args.mode=="remote":remote(args.plan,args.batch,args.system,args.folder)
    elif args.mode=="worker":worker(args.folder,args.branch,args.wrapper)
    else:complete(args.folder)


if __name__=="__main__":main()
