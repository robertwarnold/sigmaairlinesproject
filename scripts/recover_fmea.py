"""Run one-request C/E recovery attempts and reconcile them offline."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fmea_generator as engine

# Bind recovery to the fixed, reviewed first B-E campaign and original condition.
ORIGINAL = "20261101T184141Z-B-E-v2"
MODEL = "gemini-3.8-flash"
SKILL_HASH = "082d9e51a01611a2daa7cecab7600359f8920ac64327b643e2fd4fe97942f7a3"
INPUTS = {
    "system_C": "29bdc570466761181e219b46c7bc7c52df05641bae94295aafdf7809b41e0435",
    "system_E": "cf69a81f1e3a53614e066a2f1610a420a66137892c3e9ac35478fdc5f91df371",
}
BASE = ROOT / "results/multi-system-pilot" / ORIGINAL


def digest(path):
    """Hash file bytes for source and output integrity checks."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, data):
    """Write status and receipts through a temporary file to avoid partial JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def read(path):
    """Read a UTF-8 JSON record."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def initialize(original, systems, label, output):
    """Validate the immutable original condition and reserve a unique recovery batch."""
    if original != ORIGINAL or not BASE.is_dir():
        raise ValueError("Unknown original campaign")
    chosen = tuple(systems.replace("system_C_system_E", "system_C,system_E").split(","))
    if not chosen or len(set(chosen)) != len(chosen) or any(s not in INPUTS for s in chosen):
        raise ValueError("Only unique system_C/system_E recovery selections are allowed")
    if engine.PROMPT_VERSION != "v2.0":
        raise ValueError("Active prompt version differs from original campaign")
    skill = digest(ROOT / "skill/fmea_instructions.md")
    if skill != SKILL_HASH:
        raise ValueError("Skill instructions changed")
    original_plan = read(BASE / "campaign_manifest.json")["plan"]
    if original_plan["model"] != MODEL or original_plan["temperature"] != 0 or original_plan["skill_sha256"] != SKILL_HASH:
        raise ValueError("Original generation configuration mismatch")
    for system in chosen:
        if original_plan["systems"][system]["sha256"] != INPUTS[system]:
            raise ValueError("Original system hash mismatch")
    # Fail before any paid boundary if the restored original evidence is incomplete.
    for system in ("system_B", "system_C", "system_D", "system_E"):
        folder = BASE / system
        record = read(folder / f"{system}_v2.0_run01_execution.json")
        expected_status = "success" if system in ("system_B", "system_D") else "failed"
        if record["status"] != expected_status:
            raise ValueError("Unexpected original attempt status")
        for name, metadata in record["artifacts"].items():
            if Path(name).name != name or digest(folder / name) != metadata["sha256"]:
                raise ValueError("Original artifact integrity mismatch")
        if expected_status == "success":
            validate_csv(folder / f"{system}_v2.0_run01.csv")
    recovery_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-CE-recovery-" + uuid.uuid4().hex[:8]
    plan = {"original_campaign_id": original, "recovery_campaign_id": recovery_id,
        "recovery_label": label, "systems": list(chosen), "model": MODEL,
        "temperature": 0, "prompt_version": "v2.0", "skill_sha256": skill,
        "inputs": {s: INPUTS[s] for s in chosen}, "maximum_new_requests": len(chosen),
        "retry_attempts": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "status": {s: "pending" for s in chosen}}
    atomic(output, plan)
    print(f"[RECOVERY] Initialized {recovery_id}; systems={','.join(chosen)}; maximum requests={len(chosen)}", flush=True)


def heartbeat(stop, system, start):
    """Report elapsed wait every thirty seconds without inventing provider progress."""
    while not stop.wait(30):
        print(f"[RECOVERY] {system} | API request pending | {time.perf_counter()-start:.0f}s elapsed", flush=True)


def generate(plan_path, system, output_root):
    """Make a single request through existing generator; persist either outcome immutably."""
    plan = read(plan_path)
    if system not in plan["systems"] or os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise ValueError("System is not authorized or workflow rerun detected")
    root = Path(output_root) / plan["recovery_campaign_id"] / system
    root.mkdir(parents=True, exist_ok=False)
    source = ROOT / "system_descriptions" / f"{system}.txt"
    if digest(source) != plan["inputs"][system]:
        raise ValueError("Input hash mismatch")
    if digest(ROOT / "skill/fmea_instructions.md") != plan["skill_sha256"]:
        raise ValueError("Prompt hash mismatch")
    receipt = {"original_campaign_id": plan["original_campaign_id"], "recovery_campaign_id": plan["recovery_campaign_id"],
        "supersedes_attempt_id": f"{system}_v2.0_run01", "attempt_id": f"{system}_recovery_{plan['recovery_campaign_id']}",
        "system_id": system, "model": MODEL, "prompt_version": "v2.0", "skill_sha256": plan["skill_sha256"],
        "system_sha256": plan["inputs"][system], "temperature": 0, "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed", "usage_metadata": None, "failure_reason": None}
    start = time.perf_counter()
    stop = __import__("threading").Event()
    thread = __import__("threading").Thread(target=heartbeat, args=(stop, system, start), daemon=True)
    thread.start()
    try:
        # The established engine owns output collision checks, schema validation and raw evidence.
        engine.generate_fmea(source, system, run=1, output_dir=root, model=MODEL,
            execution={"experiment_id": plan["recovery_campaign_id"], "expected_max_output_tokens": 65536})
        receipt["status"] = "success"
    except Exception as exc:
        receipt["failure_reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        stop.set()
        thread.join(timeout=2)
        sidecar = root / f"{system}_v2.0_run01_execution.json"
        if sidecar.exists():
            execution_record = read(sidecar)
            receipt["usage_metadata"] = execution_record.get("usage_metadata", execution_record.get("execution", {}).get("usage_metadata"))
            receipt["execution"] = execution_record.get("execution", {})
        receipt["elapsed_seconds"] = time.perf_counter() - start
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        files = {p.name: digest(p) for p in root.iterdir() if p.is_file()}
        receipt["artifacts"] = files
        csv_files = [p for p in root.glob("*.csv")]
        if csv_files:
            receipt["csv_path"] = csv_files[0].name
            receipt["row_count"] = sum(1 for _ in csv.DictReader(csv_files[0].open(encoding="utf-8-sig")))
        atomic(root / "recovery_metadata.json", receipt)
        plan["status"][system] = receipt["status"]
        atomic(plan_path, plan)
        print(f"[RECOVERY] {system} | {receipt['status']} | {receipt['elapsed_seconds']:.2f}s", flush=True)


def validate_csv(path):
    """Validate CSV structure and ratings through the established response validator."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != engine.CSV_FIELDS:
            raise ValueError("Invalid FMEA CSV headers")
        rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError("Invalid CSV row width")
    for row in rows:
        for field in engine.RATINGS:
            row[field] = int(row[field])
    validated = engine.parse_fmea(json.dumps(rows))
    for row, valid in zip(rows, validated):
        if int(row["RPN"]) != valid["RPN"]:
            raise ValueError("Invalid RPN")


def reconcile(plan_path, recovery_root, output_root, histories=()):
    """Create a new immutable effective view while retaining every original attempt."""
    plan = read(plan_path)
    if plan["original_campaign_id"] != ORIGINAL or not re.fullmatch(r"[A-Za-z0-9_-]+", plan["recovery_campaign_id"]):
        raise ValueError("Invalid campaign linkage")
    if len(set(plan["systems"])) != len(plan["systems"]) or any(s not in INPUTS for s in plan["systems"]):
        raise ValueError("Invalid or ambiguous system selection")
    destination = Path(output_root) / plan["original_campaign_id"] / plan["recovery_campaign_id"]
    destination.mkdir(parents=True, exist_ok=False)
    original = read(BASE / "campaign_manifest.json")
    original_plan = original["plan"]
    if original_plan["model"] != MODEL or original_plan["temperature"] != 0 or original_plan["skill_sha256"] != SKILL_HASH or original_plan.get("prompt_version", "v2.0") != "v2.0":
        raise ValueError("Original experiment configuration mismatch")
    attempts, effective, rows, financial_sources = [], {}, [], []
    for system in ("system_B", "system_C", "system_D", "system_E"):
        source = BASE / system / f"{system}_v2.0_run01_execution.json"
        old = read(source)
        financial_sources.append(old)
        if system in INPUTS and old["status"] != "failed":
            raise ValueError("Recovery may replace only original failures")
        if system not in INPUTS and old["status"] != "success":
            raise ValueError("Original B/D success missing")
        for name, artifact in old.get("artifacts", {}).items():
            if Path(name).name != name or digest(source.parent / name) != artifact["sha256"]:
                raise ValueError("Original artifact changed")
        attempts.append({"system_id": system, "attempt_id": f"{system}_v2.0_run01", "status": old["status"],
            "duration_seconds": old["total_elapsed_seconds"], "cost_usd": old.get("estimated_api_expense_usd"), "origin": "original"})
        chosen_path = BASE / system / f"{system}_v2.0_run01.csv" if old["status"] == "success" else None
        recovery = Path(recovery_root) / plan["recovery_campaign_id"] / system / "recovery_metadata.json"
        recovery_record = read(recovery) if recovery.exists() else None
        if recovery_record and system not in plan["systems"]:
            raise ValueError("Unexpected recovery result")
        if system in plan["systems"] and recovery_record:
            financial_sources.append({**recovery_record, "metadata_schema": "fmea-execution-1",
                "experiment_id": plan["recovery_campaign_id"],
                "total_elapsed_seconds": recovery_record["elapsed_seconds"]})
            attempts.append({"system_id": system, "attempt_id": recovery_record["attempt_id"], "status": recovery_record["status"],
                "duration_seconds": recovery_record["elapsed_seconds"], "cost_usd": None, "origin": "recovery"})
            if recovery_record["status"] == "success" and recovery_record.get("csv_path"):
                # Validate linkage and every condition before allowing a recovery to replace a failure.
                expected = {"original_campaign_id": ORIGINAL, "recovery_campaign_id": plan["recovery_campaign_id"],
                    "supersedes_attempt_id": f"{system}_v2.0_run01", "system_id": system,
                    "model": MODEL, "prompt_version": "v2.0", "skill_sha256": SKILL_HASH,
                    "system_sha256": INPUTS[system], "temperature": 0}
                if any(recovery_record.get(key) != value for key, value in expected.items()):
                    raise ValueError(f"Recovery linkage or configuration mismatch: {system}")
                if Path(recovery_record["csv_path"]).name != recovery_record["csv_path"]:
                    raise ValueError("Unsafe recovery CSV path")
                if original_plan["model"] != recovery_record["model"] or original_plan["temperature"] != recovery_record["temperature"] or original_plan["skill_sha256"] != recovery_record["skill_sha256"] or original_plan["systems"][system]["sha256"] != recovery_record["system_sha256"]:
                    raise ValueError("Original/recovery condition mismatch")
                chosen_path = recovery.parent / recovery_record["csv_path"]
                if not chosen_path.is_file() or recovery_record.get("artifacts", {}).get(chosen_path.name) != digest(chosen_path):
                    raise ValueError(f"Missing or hash-mismatched recovery CSV: {system}")
                # Reuse the original parser; a present but invalid worksheet stays unresolved.
                try:
                    validate_csv(chosen_path)
                except Exception:
                    chosen_path = None
        if chosen_path and chosen_path.exists():
            validate_csv(chosen_path)
            effective[system] = {"effective_attempt_id": recovery_record["attempt_id"] if recovery_record and chosen_path.parent == recovery.parent else f"{system}_v2.0_run01",
                "path": str(chosen_path), "status": "success"}
        else:
            effective[system] = {"effective_attempt_id": None, "path": None, "status": "unresolved"}
        rows.append({"system_id": system, "original_status": old["status"], "recovery_status": recovery_record["status"] if recovery_record else "not_attempted",
            "effective_status": effective[system]["status"], "effective_attempt_id": effective[system]["effective_attempt_id"]})
    # Save auditable tables, original failures and new attempt records without copying raw FMEAs into reports.
    def write_csv(name, data):
        with (destination / name).open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader(); writer.writerows(data)
    manifest = {"original_campaign_id": ORIGINAL, "recovery_campaign_id": plan["recovery_campaign_id"],
        "financial_schema": "reconciled-campaign-1", "attempts": financial_sources,
        "effective_results": effective, "attempt_count": len(attempts), "original_plan": original["plan"],
        "reconciliation_status": "complete" if all(v["status"] == "success" for v in effective.values()) else "partial"}
    for history in histories:
        previous = read(history)
        if previous["original_campaign_id"] != ORIGINAL:
            raise ValueError("Prior history campaign mismatch")
        existing = {(r.get("experiment_id", r.get("recovery_campaign_id")), r["attempt_id"]): r for r in financial_sources}
        for record in previous["attempts"]:
            key = (record.get("experiment_id", record.get("recovery_campaign_id")), record["attempt_id"])
            if key in existing and existing[key] != record:
                raise ValueError("Conflicting prior attempt evidence")
            if key not in existing:
                financial_sources.append(record)
        if any(v["status"] == "success" and s in plan["systems"] for s, v in previous["effective_results"].items() if s in INPUTS):
            raise ValueError("Previously selected recovery cannot be replaced ambiguously")
        for system in INPUTS:
            prior = previous["effective_results"][system]
            if prior["status"] == "success" and effective[system]["status"] != "success":
                path = Path(prior["path"])
                matches = [r for r in previous["attempts"] if r["attempt_id"] == prior["effective_attempt_id"]]
                if len(matches) != 1:
                    raise ValueError("Ambiguous prior selected receipt")
                record = matches[0]
                expected = {"status": "success", "original_campaign_id": ORIGINAL, "system_id": system,
                    "supersedes_attempt_id": f"{system}_v2.0_run01", "model": MODEL, "temperature": 0,
                    "prompt_version": "v2.0", "skill_sha256": SKILL_HASH, "system_sha256": INPUTS[system]}
                if any(record.get(k) != v for k, v in expected.items()) or record.get("artifacts", {}).get(path.name) != digest(path):
                    raise ValueError("Prior selected recovery failed integrity or compatibility checks")
                validate_csv(path)
                effective[system] = prior
    manifest["attempt_count"] = len(financial_sources)
    manifest["reconciliation_status"] = "complete" if all(v["status"] == "success" for v in effective.values()) else "partial"
    ids = [r["attempt_id"] for r in financial_sources if "attempt_id" in r]
    if len(ids) != len(set(ids)):
        raise ValueError("Ambiguous attempt identity")
    for row in rows:
        result = effective[row["system_id"]]
        row.update(effective_status=result["status"], effective_attempt_id=result["effective_attempt_id"])
    attempts = [{"system_id": r["system_id"], "attempt_id": r["attempt_id"], "status": r["status"],
        "duration_seconds": r.get("total_elapsed_seconds", r.get("elapsed_seconds")),
        "usage_metadata": json.dumps(r.get("usage_metadata", r.get("execution", {}).get("usage_metadata"))),
        "provider_billing_usd": None} for r in financial_sources]
    write_csv("effective_campaign_summary.csv", rows)
    write_csv("all_attempts_history.csv", attempts)
    atomic(destination / "reconciliation_manifest.json", manifest)
    from analysis.financial_impact.report import create_report
    create_report([destination / "reconciliation_manifest.json"], destination / "financial_impacts",
                  analysis_id=plan["recovery_campaign_id"] + "-financial-v1")
    (destination / "README.md").write_text("# Reconciled B-E campaign\n\nEffective view only; original attempt records remain in the source campaign. A recovery is effective only after validation.\n", encoding="utf-8")
    print(f"[RECOVERY] Reconciliation ready: {destination}; requests={len(attempts)}", flush=True)


def global_base(path):
    """Select an explicitly restored local original campaign directory."""
    global BASE
    BASE = Path(path)


def main():
    """Expose offline initialization, one-call generation and offline reconciliation commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("initialize")
    init.add_argument("--original", required=True); init.add_argument("--systems", required=True); init.add_argument("--label", default=""); init.add_argument("--output", required=True)
    gen = sub.add_parser("generate"); gen.add_argument("--plan", required=True); gen.add_argument("--system", choices=["system_C", "system_E"], required=True); gen.add_argument("--output", required=True)
    rec = sub.add_parser("reconcile"); rec.add_argument("--history", action="append", default=[]); rec.add_argument("--plan", required=True); rec.add_argument("--recovery", required=True); rec.add_argument("--output", required=True)
    parser.add_argument("--original-dir", type=Path, default=BASE)
    args = parser.parse_args()
    global_base(args.original_dir)
    if args.command == "initialize": initialize(args.original, args.systems, args.label, args.output)
    elif args.command == "generate": generate(args.plan, args.system, args.output)
    else: reconcile(args.plan, args.recovery, args.output, args.history)


if __name__ == "__main__":
    main()
