"""Bounded verified-503 recovery; durable local controller and one-request remote adapter."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import httpx
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import recover_fmea as recovery
from scripts import multi_system_pilot as pilot

POLICY = {"max_attempts_per_system": 3, "maximum_new_requests": 6,
          "retry_delays_seconds": [60, 120], "retry_trigger": "provider_unavailable_503",
          "maximum_retry_after_seconds": 600, "sdk_attempts": 1}


def diagnostic(error):
    """Only typed SDK HTTP 503 responses authorize retries; redact diagnostic text."""
    from google.genai.errors import APIError
    code = getattr(error, "code", None) if isinstance(error, APIError) else None
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}
    text = str(error)
    recovery.engine.load_local_env()
    key = os.getenv("GEMINI_API_KEY")
    if key: text = text.replace(key, "[REDACTED]")
    text = re.sub(r"AIza[0-9A-Za-z_-]+", "[REDACTED]", text)
    transport = isinstance(error, (httpx.RemoteProtocolError, httpx.ReadTimeout))
    return {"retryable_transport_failure": transport, "http_status": code, "failure_classification": "provider_unavailable_503" if code == 503 else "provider_transport_failure" if transport else "non_retryable_failure",
            "provider_diagnostic": text[:4000], "retry_after": headers.get("retry-after"),
            "error_type": type(error).__name__}


def retry_delay(record, retry_index, now=None):
    """Choose the approved delay or feasible provider Retry-After, never retry other failures."""
    if record.get("failure_classification") != "provider_unavailable_503" or record.get("http_status") != 503 or retry_index not in (0, 1):
        return None
    delay = POLICY["retry_delays_seconds"][retry_index]
    header = record.get("retry_after")
    if header is not None:
        try:
            seconds = float(header)
        except (TypeError, ValueError):
            try: seconds = (parsedate_to_datetime(header) - (now or datetime.now(timezone.utc))).total_seconds()
            except (TypeError, ValueError, OverflowError): return None
        if not __import__("math").isfinite(seconds) or seconds > POLICY["maximum_retry_after_seconds"]:
            return None
        delay = max(delay, seconds)
    return delay


def preflight(folder, systems="system_C,system_E"):
    """Verify local original evidence, original Git blobs, schema and SDK without a provider call."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    recovery.initialize(recovery.ORIGINAL, systems, "authorized bounded HTTP 503 recovery", folder / "plan.json")
    plan = recovery.read(folder / "plan.json")
    original = recovery.read(recovery.BASE / "campaign_manifest.json")["plan"]
    current = pilot.specification(plan["recovery_campaign_id"])
    for key in ("model", "temperature", "prompt_version", "skill_sha256", "response_schema_sha256", "max_output_tokens", "sdk_version", "retry_attempts", "systems"):
        if current[key] != original[key]: raise ValueError("Original condition mismatch: " + key)
    if importlib.metadata.version("google-genai") != original["sdk_version"]:
        raise ValueError("SDK mismatch")
    plan.update(policy=POLICY, maximum_new_requests=6, execution_path="github_single_request_local_controller")
    recovery.atomic(folder / "plan.json", plan)
    paths = [*recovery.BASE.rglob("*"), * (ROOT / "results/single-system-replicates/system_A/20261101T163923Z-system-a-five").rglob("*"),
             ROOT / "skill/fmea_instructions.md", ROOT / "fmea_generator.py", * (ROOT / "system_descriptions").glob("system_[ABCDE].txt")]
    recovery.atomic(folder / "original_checksums.json", {str(p.resolve()): recovery.digest(p) for p in paths if p.is_file()})
    update(folder, phase="preflight_complete", reserved_requests=0, attempts=[], retry_wait_seconds=0,
           recovery_campaign_id=plan["recovery_campaign_id"], systems={s: "pending" for s in plan["systems"]})
    return plan


def update(folder, **changes):
    """Publish persistent status and readable progress while a detached worker executes."""
    path = Path(folder) / "status.json"
    state = recovery.read(path) if path.exists() else {}
    state.update(changes, updated_at=datetime.now(timezone.utc).isoformat())
    recovery.atomic(path, state)
    lines = ["# " + state.get("campaign_title", "C/E recovery"), "", json.dumps(state, indent=2)]
    (Path(folder) / "STATUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[{state['updated_at']}] {state.get('phase')} | {state.get('active_system', '')} | {state.get('message', '')}", flush=True)
    return state


def remote(plan_path, system, batch, output):
    """Execute exactly one unchanged generator request on a verified GitHub runner."""
    match = re.fullmatch(r"(.+)-([CE])-attempt-([1-6])", batch)
    if not match or system != "system_" + match[2] or os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise ValueError("Invalid single-attempt authorization")
    if int(match[3]) > 3 and system != "system_C":
        raise ValueError("Extended attempt limit is authorized for C only")
    original_plan = recovery.read(plan_path)
    current = pilot.specification(original_plan["campaign_id"])
    if current != {k: original_plan[k] for k in current}:
        raise ValueError("Remote preflight configuration changed")
    if original_plan["campaign_id"] != match[1] or importlib.metadata.version("google-genai") != original_plan["sdk_version"]:
        raise ValueError("Preflight/attempt campaign or SDK mismatch")
    plan = {"original_campaign_id": recovery.ORIGINAL, "recovery_campaign_id": match[1], "systems": [system],
            "inputs": {system: recovery.INPUTS[system]}, "skill_sha256": recovery.SKILL_HASH, "status": {system: "pending"}}
    local_plan = Path(output) / "remote-plan.json"
    recovery.atomic(local_plan, plan)
    recovery.generate(local_plan, system, output, int(match[3]))


def github(wrapper, *args):
    """Use the existing authenticated GitHub adapter, without exposing credentials."""
    return pilot.github(wrapper, *args)


def run_workflow(folder, wrapper, branch, mode, batch, system, preflight_id=None):
    """Dispatch once; persist reservation before POST and never repeat an uncertain dispatch."""
    state = recovery.read(Path(folder) / "status.json")
    paid = mode in ("ce_recovery_single", "replicate_single")
    if paid:
        limit = state.get("maximum_new_requests", 6) if mode == "replicate_single" else 6
        if limit not in (6, 12) or state["reserved_requests"] >= limit:
            raise ValueError("Campaign request budget exhausted")
        update(folder, reserved_requests=state["reserved_requests"] + 1, phase="dispatch_reserved", active_system=system, active_batch=batch)
    args = ["workflow", "run", "generate-fmea.yml", "--ref", branch, "-f", "mode=" + mode,
            "-f", "approved_calls=" + ("1" if paid else "0"),
            "-f", "batch_id=" + batch, "-f", "system=" + system, "-f", "model=" + recovery.MODEL]
    if preflight_id: args += ["-f", "preflight_run_id=" + str(preflight_id)]
    response = github(wrapper, *args)
    match = re.search(r"/actions/runs/(\d+)", response)
    if not match:
        raise RuntimeError("Dispatch has no run ID; do not redispatch; inspect Actions")
    run_id = match[1]
    update(folder, workflow_run_id=run_id, phase="workflow_pending", message="One dispatch recorded; no automatic workflow reruns")
    poll_start = time.perf_counter()
    while True:
        run = json.loads(github(wrapper, "run", "view", run_id, "--json", "status,conclusion,jobs"))
        if run["status"] == "completed": return run_id, run["conclusion"]
        active = [step["name"] for job in run.get("jobs", []) for step in job.get("steps", []) if step["status"] == "in_progress"]
        update(folder, phase="workflow_pending", message=(" | ".join(active) or run["status"]) + f" | workflow elapsed {time.perf_counter()-poll_start:.0f}s")
        time.sleep(15)


def worker(folder, branch, wrapper):
    """Sequential C/E recovery with durable one-shot ownership and verified 503-only retries."""
    folder = Path(folder)
    with (folder / "worker.lock").open("x") as stream: stream.write(str(os.getpid()))
    plan = recovery.read(folder / "plan.json")
    if plan["policy"] != POLICY: raise ValueError("Retry authorization mismatch")
    campaign = plan["recovery_campaign_id"]
    try:
        preflight_id, conclusion = run_workflow(folder, wrapper, branch, "multi_system_preflight", campaign, "system_C")
        if conclusion != "success": raise RuntimeError("Remote no-generation preflight failed")
        github(wrapper, "run", "download", preflight_id, "--name", "multi-system-preflight-" + preflight_id, "--dir", str(folder / "remote-preflight"))
        update(folder, phase="remote_preflight_complete", preflight_run_id=preflight_id)
        for system in ("system_C", "system_E"):
            for number in range(1, 4):
                batch = f"{campaign}-{system[-1]}-attempt-{number}"
                update(folder, phase="starting_attempt", active_system=system, attempt_number=number, message=f"Attempt {number}/3")
                run_id, conclusion = run_workflow(folder, wrapper, branch, "ce_recovery_single", batch, system, preflight_id)
                target = folder / "downloads" / run_id
                github(wrapper, "run", "download", run_id, "--name", f"ce-recovery-{batch}-{run_id}", "--dir", str(target))
                receipts = list(target.rglob("recovery_metadata.json"))
                if len(receipts) != 1: raise RuntimeError("Missing/ambiguous attempt evidence; do not retry")
                record = recovery.read(receipts[0])
                if record["system_id"] != system or record["recovery_campaign_id"] != campaign or record["retry_number"] != number - 1:
                    raise ValueError("Downloaded attempt identity mismatch")
                if record.get("execution", {}).get("request_invocations") != 1:
                    raise RuntimeError("Attempt did not confirm exactly one generation request; stop")
                for name, digest in record["artifacts"].items():
                    if Path(name).name != name or recovery.digest(receipts[0].parent / name) != digest:
                        raise ValueError("Downloaded artifact integrity mismatch")
                destination = folder / "attempts" / campaign / system / f"attempt-{number}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                __import__("shutil").copytree(receipts[0].parent, destination)
                state = recovery.read(folder / "status.json")
                state["attempts"].append({**record, "workflow_run_id": run_id, "metadata_path": str(destination / "recovery_metadata.json")})
                update(folder, attempts=state["attempts"], phase="attempt_complete", message=f"{record['status']} | HTTP {record.get('http_status')} | rows={record.get('row_count')}")
                if record["status"] == "success":
                    recovery.validate_csv(destination / record["csv_path"])
                    state["systems"][system] = "success"
                    update(folder, systems=state["systems"], phase="system_success")
                    break
                delay = retry_delay(record, number - 1)
                if delay is None or number == 3:
                    state["systems"][system] = "unresolved"
                    update(folder, systems=state["systems"], phase="system_unresolved")
                    # Authentication/model/security failures make continuing unsafe.
                    if record.get("http_status") in (400, 401, 403, 404):
                        raise RuntimeError("Nonretryable provider configuration/authentication error")
                    break
                update(folder, phase="retry_wait", message=f"Verified HTTP 503; next attempt {number+1}/3 after {delay}s")
                start = time.perf_counter()
                while time.perf_counter() - start < delay:
                    time.sleep(min(30, delay - (time.perf_counter() - start)))
                    update(folder, phase="retry_wait", message=f"Actual waiting {time.perf_counter()-start:.1f}s / {delay}s")
                actual = time.perf_counter() - start
                record["retry_wait_seconds"] = actual
                recovery.atomic(destination / "recovery_metadata.json", record)
                state = recovery.read(folder / "status.json")
                state["attempts"][-1]["retry_wait_seconds"] = actual
                update(folder, attempts=state["attempts"], retry_wait_seconds=state["retry_wait_seconds"] + actual)
        update(folder, phase="reconciling", message="No further requests; offline validation and reports")
        destination = recovery.reconcile(folder / "plan.json", folder / "attempts", ROOT / "results/ce-r")
        update(folder, phase="generation_and_reconciliation_complete", reconciliation_manifest=str((destination / "reconciliation_manifest.json").resolve()))
    except BaseException as exc:
        update(folder, phase="blocked", message=f"{type(exc).__name__}: {exc}; no automatic restart")
        raise


C_ONLY_POLICY = {"max_attempts_per_system": 6, "maximum_new_requests": 6,
    "retry_delays_seconds": [60, 120, 180, 240, 300], "sdk_attempts": 1,
    "retry_triggers": ["verified_http_503", "typed_remote_disconnect_or_read_timeout"]}


def c_retry_delay(record, completed):
    """Apply the separately authorized C-only six-request policy to transient failures."""
    if completed not in range(1, 6): return None
    baseline = C_ONLY_POLICY["retry_delays_seconds"][completed - 1]
    if record.get("http_status") == 503:
        provider_delay = retry_delay(record, min(completed - 1, 1))
        return max(baseline, provider_delay) if provider_delay is not None else None
    if record.get("retryable_transport_failure") is True and record.get("http_status") is None:
        return baseline
    return None


def c_prepare(folder):
    """Prepare one explicitly authorized six-request C-only campaign, without generation."""
    plan = preflight(folder, "system_C")
    plan.update(policy=C_ONLY_POLICY, authorization="up_to_six_additional_C_requests")
    recovery.atomic(Path(folder) / "plan.json", plan)
    return plan


def c_worker(folder, branch, wrapper, history):
    """Make at most six C requests, stopping on valid success or a nontransient failure."""
    folder = Path(folder)
    with (folder / "worker.lock").open("x") as stream: stream.write(str(os.getpid()))
    plan = recovery.read(folder / "plan.json")
    if plan["systems"] != ["system_C"] or plan.get("authorization") != "up_to_six_additional_C_requests" or plan["policy"] != C_ONLY_POLICY:
        raise ValueError("C-only six-request authorization mismatch")
    previous = recovery.read(history)
    if previous["effective_results"]["system_C"]["status"] == "success":
        raise ValueError("C already has a selected success; refuse another generation")
    campaign = plan["recovery_campaign_id"]
    try:
        preflight_id, conclusion = run_workflow(folder, wrapper, branch, "multi_system_preflight", campaign, "system_C")
        if conclusion != "success": raise RuntimeError("Remote no-generation preflight failed")
        github(wrapper, "run", "download", preflight_id, "--name", "multi-system-preflight-" + preflight_id, "--dir", str(folder / "remote-preflight"))
        update(folder, phase="remote_preflight_complete", preflight_run_id=preflight_id, systems={"system_C":"pending", "system_E":previous["effective_results"]["system_E"]["status"]})
        for number in range(1, 7):
            update(folder, phase="starting_attempt", active_system="system_C", attempt_number=number, message=f"C request {number}/6; stop at first valid success")
            batch = f"{campaign}-C-attempt-{number}"
            run_id, conclusion = run_workflow(folder, wrapper, branch, "ce_recovery_single", batch, "system_C", preflight_id)
            target = folder / "downloads" / run_id
            github(wrapper, "run", "download", run_id, "--name", f"ce-recovery-{batch}-{run_id}", "--dir", str(target))
            matches = list(target.rglob("recovery_metadata.json"))
            if len(matches) != 1: raise RuntimeError("Missing/ambiguous attempt evidence; do not redispatch")
            record = recovery.read(matches[0])
            expected = {"original_campaign_id":recovery.ORIGINAL,"recovery_campaign_id":campaign,"system_id":"system_C",
                "retry_number":number-1,"model":recovery.MODEL,"temperature":0,"prompt_version":"v2.0",
                "skill_sha256":recovery.SKILL_HASH,"system_sha256":recovery.INPUTS["system_C"]}
            if any(record.get(k)!=v for k,v in expected.items()):raise ValueError("Downloaded attempt identity/configuration mismatch")
            if record.get("execution",{}).get("request_invocations")!=1:raise RuntimeError("Unconfirmed generation count; stop")
            for name,digest in record["artifacts"].items():
                if Path(name).name!=name or recovery.digest(matches[0].parent/name)!=digest:raise ValueError("Artifact integrity mismatch")
            destination=folder/"attempts"/campaign/"system_C"/f"attempt-{number}"
            destination.parent.mkdir(parents=True,exist_ok=True)
            __import__("shutil").copytree(matches[0].parent,destination)
            state=recovery.read(folder/"status.json")
            record.update(workflow_run_id=run_id,metadata_path=str(destination/"recovery_metadata.json"))
            state["attempts"].append(record)
            update(folder,attempts=state["attempts"],phase="attempt_complete",message=f"C {record['status']}; HTTP {record.get('http_status')}; rows={record.get('row_count')}")
            if record["status"]=="success":
                recovery.validate_csv(destination/record["csv_path"])
                state["systems"]["system_C"]="success"
                update(folder,systems=state["systems"],phase="system_success")
                break
            delay=c_retry_delay(record,number)
            if delay is None:
                state["systems"]["system_C"]="unresolved"
                update(folder,systems=state["systems"],phase="system_unresolved")
                break
            update(folder,phase="retry_wait",message=f"Transient provider failure; C request {number+1}/6 after {delay}s")
            start=time.perf_counter()
            while time.perf_counter()-start<delay:
                time.sleep(max(0,min(30,delay-(time.perf_counter()-start))))
                update(folder,phase="retry_wait",message=f"Actual waiting {time.perf_counter()-start:.1f}s / {delay}s")
            actual=time.perf_counter()-start
            record["retry_wait_seconds"]=actual
            recovery.atomic(destination/"recovery_metadata.json",record)
            state=recovery.read(folder/"status.json");state["attempts"][-1]["retry_wait_seconds"]=actual
            update(folder,attempts=state["attempts"],retry_wait_seconds=state["retry_wait_seconds"]+actual)
        update(folder,phase="reconciling",message="No further requests; retain all previous history and E success")
        destination=recovery.reconcile(folder/"plan.json",folder/"attempts",ROOT/"results/ce-r",[history])
        update(folder,phase="generation_and_reconciliation_complete",reconciliation_manifest=str((destination/"reconciliation_manifest.json").resolve()))
    except BaseException as error:
        update(folder,phase="blocked",message=f"{type(error).__name__}: {error}; no automatic restart")
        raise


def main():
    """Expose explicit offline preflight, bounded worker, and one-request remote operations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "worker", "remote", "c-preflight", "c-worker"))
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--branch", default="fmea-ce-recovery-20261101")
    parser.add_argument("--wrapper", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--system", choices=("system_C", "system_E"))
    parser.add_argument("--batch")
    parser.add_argument("--history", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "c-preflight": c_prepare(args.folder)
        elif args.mode == "c-worker": c_worker(args.folder,args.branch,args.wrapper,args.history)
        elif args.mode == "preflight": preflight(args.folder)
        elif args.mode == "worker": worker(args.folder, args.branch, args.wrapper)
        else: remote(args.plan, args.system, args.batch, args.folder)
    finally:
        # Reporting remains offline and cannot replace the saved generation outcome.
        if args.mode in ("worker","c-worker"):
            from src.sigma_fmea.execution_metadata import automatic_report
            automatic_report(args.folder)



if __name__ == "__main__": main()
