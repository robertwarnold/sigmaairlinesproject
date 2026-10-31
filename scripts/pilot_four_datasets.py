"""Explicit plan amendment: preserve/adopt one smoke, reserve at most seven new calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from scripts.pilot_workflow import package
from sigma_fmea.integrity import load_json
from sigma_fmea.llm import build_prompt
from sigma_fmea.methodology import get_profile
from sigma_fmea.research import build_plan, load_system, run_experiment, write_record

CONFIG = ROOT / "examples/research/pilot-four-datasets.json"


def prepare(smoke, output, provider=None):
    smoke, output = Path(smoke), Path(output)
    for line in (smoke / "checksums.sha256").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        source = (smoke / relative).resolve()
        if not source.is_relative_to(smoke.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError("Original smoke checksum mismatch")
    old = load_json(smoke / "plan.json")
    progress = load_json(smoke / "progress.json")
    if progress["attempted"] != 1 or progress["successful"] != 1:
        raise ValueError("Adopt only the single successful original smoke")
    new = build_plan(CONFIG, provider=provider)
    for name in ("provider", "model", "temperature", "max_output_tokens", "prompt_version", "guidance_corpus_sha256", "schema_version"):
        if new[name] != old[name]:
            raise ValueError(f"Smoke treatment/settings changed: {name}")
    for name in ("llm.py", "providers.py", "models.py", "methodology.py", "guidance.py", "integrity.py", "export.py", "evaluation.py"):
        if (smoke / "reproduction/src/sigma_fmea" / name).read_text(encoding="utf-8") != (ROOT / "src/sigma_fmea" / name).read_text(encoding="utf-8"):
            raise ValueError(f"Generation/evaluation code differs from smoke: {name}")
    first = new["jobs"][0]
    if first["job_id"] != old["jobs"][0]["job_id"] or first["condition"] != "baseline":
        raise ValueError("Smoke job identity differs")
    job = smoke / "runs" / first["job_id"]
    state = load_json(job / "state.json")
    context, description, record = load_system(new["systems"][0]["path"])
    current_prompt = build_prompt(context, get_profile(new["systems"][0]["profile"]), description, "baseline")
    if state["state"] != "success" or state["input_sha256"] != record["sha256"] or current_prompt != load_json(job / "prompt.json"):
        raise ValueError("Smoke input/prompt changed")
    if new["blockers"]:
        raise ValueError("; ".join(new["blockers"]))
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(smoke, output / "original-smoke")
    shutil.copytree(job, output / "runs" / first["job_id"])
    shutil.copyfile(smoke / "smoke-origin.json", output / "smoke-origin.json")
    write_record(output / "plan.json", new)
    write_record(output / "amendment.json", {
        "reason": "User approved four datasets and seven new calls after initial two-dataset smoke",
        "original_plan_sha256": old["plan_sha256"], "amended_plan_sha256": new["plan_sha256"],
        "original_source": load_json(smoke / "smoke-origin.json"), "amended_source_commit": os.environ.get("GITHUB_SHA"),
        "adopted_job_id": first["job_id"], "adopted_job_files": "byte-preserved, including original plan_sha256",
        "original_design": "two systems x two conditions x two repeats",
        "amended_design": "four systems x two conditions x one observation per cell",
        "new_call_cap": 7, "existing_smoke_count": 1,
        "compatibility": "identical hydraulic input, exact baseline prompt, settings, generation and evaluation modules; metadata-only sample classification corrected",
        "limitations": "post-smoke design amendment; exploratory only; no reviewed mode-reference data or inferential claims"
    })
    return new


def package_amendment(output, plots=True):
    output = Path(output)
    source = ROOT / "docs/four-dataset-pilot.md"
    if source.exists():
        output.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output / "AMENDMENT.md")
    return package(output, plots=plots, config_path=CONFIG)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", type=Path, default=ROOT / "results/pilot")
    parser.add_argument("--output", type=Path, default=ROOT / "results/pilot-four")
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--approved-calls", type=int, default=0)
    parser.add_argument("--package", action="store_true")
    args = parser.parse_args()
    if args.package:
        print(json.dumps(package_amendment(args.output), indent=2))
        return 0
    if args.approved_calls != 7 or args.model != load_json(CONFIG)["model"]:
        parser.error("Requires explicit seven-call authorization and the frozen model")
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        parser.error("Automatic workflow reruns are blocked")
    prepare(args.smoke, args.output)
    result = run_experiment(CONFIG, args.output, "batch", allow_paid=True, max_calls=8)
    print(json.dumps(result, indent=2))
    return 2 if result["failed"] or result["uncertain"] or result["remaining"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
