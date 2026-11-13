"""Four-request B-E pilot: existing generator, durable local status, no retries."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fmea_generator as engine
from analysis.financial_impact.data_schema import read_json
from analysis.financial_impact.ingest import import_attempts, sha256

# These are the actual System A pilot's generation settings, not a new condition.
SYSTEMS = ("system_B", "system_C", "system_D", "system_E")
MODEL = "gemini-3.8-flash"
SKILL_HASH = "082d9e51a01611a2daa7cecab7600359f8920ac64327b643e2fd4fe97942f7a3"
SCHEMA_HASH = "51a9355a78daeac7f19bb4a01331798c47abd9cc9e73117e05764ee392f2e970"
BASELINE_SDK = "1.75.0"
TOKEN_LIMIT = 65536


def now():
    """Use UTC for event provenance; performance counters measure request durations."""
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    """Replace an owned progress file atomically; unique temps avoid reader races."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    text = value if isinstance(value, str) else json.dumps(value, indent=2, allow_nan=False) + "\n"
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def specification(campaign_id):
    """Freeze original Git bytes and reject any model, skill, schema or input drift."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", campaign_id):
        raise ValueError("Unsafe campaign ID")
    # Git blobs identify the Linux execution bytes; Windows text-mode reads normalize CRLF.
    inputs = {}
    for system in SYSTEMS:
        relative = f"system_descriptions/{system}.txt"
        blob = subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT)
        if not blob.strip() or (ROOT / relative).read_bytes().replace(b"\r\n", b"\n") != blob:
            raise ValueError(f"Modified or empty original input: {system}")
        import hashlib
        inputs[system] = {"path": relative, "sha256": hashlib.sha256(blob).hexdigest()}
    skill = (ROOT / "skill/fmea_instructions.md").read_bytes().replace(b"\r\n", b"\n")
    import hashlib
    if engine.PROMPT_VERSION != "v2.0" or hashlib.sha256(skill).hexdigest() != SKILL_HASH:
        raise ValueError("Skill differs from the System A pilot")
    schema = hashlib.sha256(json.dumps(engine.RESPONSE_SCHEMA, sort_keys=True).encode()).hexdigest()
    if schema != SCHEMA_HASH:
        raise ValueError("Output schema differs from the System A pilot")
    return {"campaign_id": campaign_id, "systems": inputs, "model": MODEL, "temperature": 0,
            "prompt_version": "v2.0", "skill_sha256": SKILL_HASH, "response_schema_sha256": schema,
            "max_output_tokens": TOKEN_LIMIT, "sdk_version": BASELINE_SDK, "retry_attempts": 1,
            "maximum_new_requests": 4, "replications_per_system": 1,
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}


def remote_preflight(campaign_id, output):
    """Verify model availability without generate_content; never substitute a model."""
    plan = specification(campaign_id)
    if importlib.metadata.version("google-genai") != BASELINE_SDK:
        raise ValueError("SDK differs from the System A configuration")
    engine.load_local_env()
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("Team Gemini credential is unavailable")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=1)))
    try:
        model = client.models.get(model=MODEL)
        if model.output_token_limit != TOKEN_LIMIT or "generateContent" not in (model.supported_actions or []):
            raise ValueError("Model capability/output limit differs from System A; no generation sent")
    finally:
        client.close()
    plan["preflight_at"] = now()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(plan, stream, indent=2)
    print(json.dumps(plan, indent=2), flush=True)
    return plan


def remote_single(plan_path, system, approved_calls):
    """One workflow job has exactly one allowed generation boundary and no retry loop."""
    if system not in SYSTEMS or approved_calls != 1 or os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise ValueError("Only one first-attempt B-E generation is authorized per job")
    plan = read_json(plan_path)
    current = specification(plan["campaign_id"])
    for key in current:
        if current[key] != plan[key]:
            raise ValueError(f"Frozen configuration mismatch: {key}")
    if importlib.metadata.version("google-genai") != plan["sdk_version"]:
        raise ValueError("SDK changed after preflight")
    output = ROOT / "results/multi-system-remote" / plan["campaign_id"] / system
    if output.exists():
        raise FileExistsError(output)
    if sha256(ROOT / plan["systems"][system]["path"]) != plan["systems"][system]["sha256"]:
        raise ValueError("Execution-byte input hash changed")
    execution = {"experiment_id": plan["campaign_id"], "expected_max_output_tokens": TOKEN_LIMIT}
    print(f"{now()} | {system} | Starting one generation; SDK retries disabled", flush=True)
    # Existing validation, raw preservation, exclusive outputs and timing remain authoritative.
    engine.generate_fmea(ROOT / plan["systems"][system]["path"], system, run=1,
                         output_dir=output, model=MODEL, execution=execution)


class Progress:
    """Keep JSON/Markdown status readable while a detached local worker is running."""
    def __init__(self, folder):
        self.folder = Path(folder)
        self.lock = threading.RLock()
        self.state = read_json(self.folder / "status.json")
        self.wall_elapsed = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(self.state["start_time"])).total_seconds())
        self.performance_start = time.perf_counter()

    def update(self, **changes):
        """Update both status views under one writer lock, without exposing environment secrets."""
        with self.lock:
            self.state.update(changes)
            self.state["elapsed_seconds"] = round(self.wall_elapsed + time.perf_counter() - self.performance_start, 2)
            self.state["last_update"] = now()
            completed = [r for r in self.state["systems"].values() if r.get("request_confirmed")]
            self.state.update(completed_request_count=len(completed),
                successful_request_count=sum(r["status"] == "success" for r in completed),
                failed_request_count=sum(r["status"] != "success" for r in completed))
            atomic(self.folder / "status.json", self.state)
            lines = [f"# Campaign {self.state['campaign_id']}", "", f"Start (UTC): {self.state['start_time']}",
                     f"Phase: {self.state['phase']}", f"Active system: {self.state.get('active_system')}",
                     f"Elapsed (campaign, seconds): {self.state['elapsed_seconds']}",
                     f"Completed requests: {len(completed)}/4; successful: {self.state['successful_request_count']}; failed: {self.state['failed_request_count']}",
                     f"Latest event: {self.state['latest_event']}", f"Updated (UTC): {self.state['last_update']}", ""]
            lines.extend(f"- {system}: {record['status']} | workflow {record.get('workflow_run_id', 'not dispatched')}"
                         for system, record in self.state["systems"].items())
            atomic(self.folder / "STATUS.md", "\n".join(lines) + "\n")

    def heartbeat(self, stopped):
        """Print actual elapsed/stage/counters every 30 seconds; no provider percentages."""
        while not stopped.wait(30):
            with self.lock:
                self.update()
                s = self.state
                active = s.get("active_system") or "none"
                active_start = s.get("active_started_at")
                elapsed = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(active_start)).total_seconds()) if active_start else 0
                print(f"[{now()}] {active} | {s['phase']} | Workflow elapsed: {elapsed:.0f}s | "
                      f"Completed: {s['completed_request_count']}/4 | Success: {s['successful_request_count']} | "
                      f"Failed: {s['failed_request_count']}", flush=True)


def initialize(folder, campaign_id):
    """Reserve an unused local campaign directory before any remote dispatch."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    state = {"campaign_id": campaign_id, "start_time": now(), "phase": "offline_preflight",
             "active_system": None, "systems": {s: {"status": "pending"} for s in SYSTEMS},
             "reserved_request_count": 0, "latest_event": "Campaign reserved; no paid requests dispatched"}
    atomic(folder / "status.json", state)
    progress = Progress(folder)
    progress.update()
    return progress


def github(wrapper, *arguments):
    """Use an existing authenticated CLI wrapper; do not print or persist credentials."""
    command = [sys.executable, str(wrapper)] if str(wrapper).endswith(".py") else [str(wrapper)]
    result = subprocess.run([*command, *arguments], capture_output=True, text=True, encoding="utf-8", timeout=90)
    if result.returncode:
        raise RuntimeError(f"GitHub operation failed ({arguments[0]}); inspect workflow/status. No generation retry.")
    return result.stdout


def verify_download(folder, system, plan):
    """Verify a single receipt and exact artifacts before counting a request as complete."""
    root = Path(folder) / system
    receipt = root / f"{system}_v2.0_run01_execution.json"
    record = read_json(receipt)
    expected = {"system_id": system, "model": MODEL, "prompt_version": "v2.0", "skill_sha256": SKILL_HASH,
                "system_sha256": plan["systems"][system]["sha256"]}
    if any(record[k] != value for k, value in expected.items()) or record["configuration"]["temperature"] != 0:
        raise ValueError("Receipt configuration mismatch")
    if record["execution"].get("request_invocations") != 1:
        raise ValueError("Receipt does not confirm exactly one request; stop before further dispatch")
    for name, metadata in record["artifacts"].items():
        if Path(name).name != name or sha256(root / name) != metadata["sha256"]:
            raise ValueError("Downloaded artifact integrity failure")
    # Existing offline pricing preserves unknown failed bills; it does not perform generation.
    assumptions = read_json(ROOT / "analysis/financial_impact/assumptions.json")
    financial = import_attempts(receipt, assumptions)[0]
    summary = {**financial, "receipt_path": str(receipt.relative_to(folder)),
               "engineering_review_status": "unreviewed", "outputs": record["artifacts"]}
    atomic(root / "generation_metadata.json", summary)
    return summary


def worker(folder, branch, wrapper, approved_calls):
    """Sequential durable controller: a reserved system is never automatically redispatched."""
    folder = Path(folder)
    if approved_calls != 4:
        raise ValueError("This controller only accepts the current four-request authorization")
    plan = read_json(folder / "preflight/plan.json")
    if plan["model"] != MODEL or plan["maximum_new_requests"] != 4:
        raise ValueError("Invalid campaign plan")
    # A persistent lock prevents two local controllers from spending the same authorization.
    with (folder / "worker.lock").open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    progress = Progress(folder)
    if progress.state["campaign_id"] != plan["campaign_id"]:
        raise ValueError("Local status and frozen plan identify different campaigns")
    stopped = threading.Event()
    thread = threading.Thread(target=progress.heartbeat, args=(stopped,), daemon=True)
    thread.start()
    try:
        for system in SYSTEMS:
            entry = progress.state["systems"][system]
            if entry.get("request_confirmed"):
                continue
            progress.update(active_system=system, active_started_at=entry.get("local_started_at", now()),
                            phase="starting system", latest_event=f"{system} beginning; no retry or replacement")
            print(f"{now()} | BEGIN {system} | Completed {progress.state['completed_request_count']}/4", flush=True)
            run_id = entry.get("workflow_run_id")
            if not run_id:
                # Persist the reservation before the POST. An uncertain POST is a blocker, never a retry.
                if entry.get("dispatch_reserved") or progress.state["reserved_request_count"] >= 4:
                    raise RuntimeError("Uncertain/used dispatch reservation; inspect GitHub before manual recovery")
                with progress.lock:
                    entry.update(dispatch_reserved=True, local_started_at=now(), status="dispatch_reserved")
                    progress.update(reserved_request_count=progress.state["reserved_request_count"] + 1)
                response = github(wrapper, "workflow", "run", "generate-fmea.yml", "--ref", branch,
                    "-f", "mode=multi_system_single", "-f", "approved_calls=1", "-f", f"system={system}",
                    "-f", f"model={MODEL}", "-f", f"batch_id={plan['campaign_id']}",
                    "-f", f"preflight_run_id={progress.state['preflight_run_id']}")
                match = re.search(r"/actions/runs/(\d+)", response)
                if not match:
                    raise RuntimeError("Dispatch returned no run ID; reservation remains consumed. Do not redispatch.")
                run_id = match.group(1)
                with progress.lock:
                    entry.update(workflow_run_id=run_id, status="running")
                    progress.update(latest_event=f"{system}: workflow {run_id} dispatched once")
            while True:
                # Polling GitHub status is read-only; heartbeat updates continue during CLI/network waits.
                state = json.loads(github(wrapper, "run", "view", run_id, "--json", "status,conclusion,jobs"))
                if state["status"] == "completed":
                    break
                active = [step["name"] for job in state.get("jobs", []) for step in job.get("steps", [])
                          if step["status"] == "in_progress"]
                progress.update(phase=" | ".join(active) if active else state["status"],
                                latest_event=f"{system}: workflow {run_id} active; no provider-internal progress available")
                stopped.wait(15)
            destination = folder / system
            if not destination.exists():
                download = ROOT / ".venv/campaign-downloads" / (system + "-" + uuid.uuid4().hex)
                github(wrapper, "run", "download", run_id, "--name", f"multi-system-{plan['campaign_id']}-{system}-{run_id}",
                       "--dir", str(download))
                receipts = list(download.rglob(f"{system}_v2.0_run01_execution.json"))
                if len(receipts) != 1:
                    raise ValueError("Missing/ambiguous receipt; request outcome uncertain, do not redispatch")
                destination.mkdir(exist_ok=False)
                for source in receipts[0].parent.iterdir():
                    if source.is_file():
                        with source.open("rb") as incoming, (destination / source.name).open("xb") as outgoing:
                            shutil.copyfileobj(incoming, outgoing)
            result = verify_download(folder, system, plan)
            with progress.lock:
                entry.update(status="success" if result["status"] == "success" else "failed", request_confirmed=True,
                             duration_seconds=result["duration_seconds"], row_count=result["row_count"],
                             cost_usd=result["cost_usd"], billing_uncertain=result["billing_uncertain"])
                progress.update(phase="system complete", latest_event=f"{system} {entry['status']}; next system only after artifact verification")
            print(f"{now()} | END {system} | {entry['status']} | {entry['duration_seconds']:.2f}s | "
                  f"Rows {entry['row_count']} | Completed {progress.state['completed_request_count']}/4", flush=True)
        progress.update(phase="ready_for_offline_evaluation", active_system=None, latest_event="All four attempts finished; authorization exhausted")
        atomic(folder / "campaign_manifest.json", {"plan": plan, "execution": progress.state})
    except Exception as error:
        progress.update(phase="blocked", latest_event=f"{type(error).__name__}: {error}; no automatic redispatch")
        raise
    finally:
        stopped.set()
        thread.join(timeout=2)


def main():
    """Expose only preflight, one remote request and the fixed four-system local controller."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("initialize", "remote-preflight", "remote-single", "worker"), required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--system", choices=SYSTEMS)
    parser.add_argument("--approved-calls", type=int, default=0)
    parser.add_argument("--branch", default="feat/fmea-b-e-live-pilot")
    parser.add_argument("--gh-wrapper", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "initialize":
            initialize(args.folder, args.campaign_id)
        elif args.mode == "remote-preflight":
            remote_preflight(args.campaign_id, args.plan)
        elif args.mode == "remote-single":
            if read_json(args.plan)["campaign_id"] != args.campaign_id:
                raise ValueError("Campaign ID differs from preflight")
            remote_single(args.plan, args.system, args.approved_calls)
        else:
            worker(args.folder, args.branch, args.gh_wrapper, args.approved_calls)
    finally:
        # Reporting remains offline and cannot replace the saved generation outcome.
        if args.mode in ("worker","remote-single"):
            from src.sigma_fmea.execution_metadata import automatic_report
            automatic_report(args.folder if args.folder else ROOT / "results/multi-system-remote" / args.campaign_id)



if __name__ == "__main__":
    main()
