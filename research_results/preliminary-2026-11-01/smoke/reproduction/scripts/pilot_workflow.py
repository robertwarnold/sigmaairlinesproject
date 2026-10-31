"""Thin GitHub Actions bridge to the existing research runner; no implicit API calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sigma_fmea.analysis import summarize
from sigma_fmea.integrity import load_json
from sigma_fmea.research import build_plan, run_experiment, write_record

CONFIG = ROOT / "examples/research/pilot-eight.json"


def package(output, plots=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    receipt_path = output / "smoke-origin.json"
    if not receipt_path.exists():
        write_record(receipt_path, {"commit_sha": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID"),
                                   "repository": os.environ.get("GITHUB_REPOSITORY"), "workflow": "generate-fmea.yml"})
    if list((output / "runs").glob("*/state.json")):
        # Smoke and remaining artifacts each retain their own descriptive report.
        analysis = output / ("analysis-" + os.environ.get("GITHUB_RUN_ID", "local"))
        if not analysis.exists():
            summarize(output, analysis, plots=plots)
    reproduction = output / "reproduction"
    for source in [*sorted((ROOT / "src/sigma_fmea").glob("*.py")), ROOT / "scripts/pilot_workflow.py",
                   ROOT / "pyproject.toml", CONFIG,
                   ROOT / "examples/research/hydraulic_actuator.json", ROOT / "examples/research/battery_power.json"]:
        target = reproduction / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    source_roles = ROOT / "docs/pilot-reviewer.md"
    if source_roles.exists():
        shutil.copyfile(source_roles, output / "SOURCE_ROLES_AND_METHODS.md")
    progress = load_json(output / "progress.json") if (output / "progress.json").exists() else {"status": "plan_only_or_failed_before_generation"}
    origin = load_json(receipt_path)
    heading = ("# Sigma Airlines pilot — OFFLINE MOCK REHEARSAL" if progress.get("data_kind") == "offline_mock_rehearsal"
               else "# Sigma Airlines real-model pilot — reviewer bundle" if progress.get("data_kind") == "real_llm_generation"
               else "# Sigma Airlines pilot — no generation evidence yet")
    rows = [heading, "",
            "Read SOURCE_ROLES_AND_METHODS.md first. This is a reduced preliminary pilot, not an approved FMEA or validated benchmark.", "",
            "## Status", "", "```json", json.dumps(progress, indent=2), "```", "",
            f"Smoke source commit: {origin.get('commit_sha')}. Smoke workflow run: {origin.get('run_id')}.",
            f"Current packaging run: {os.environ.get('GITHUB_RUN_ID', 'local offline rehearsal')}.", "",
            "## Inspect without any AI calls", "",
            "- plan.json: frozen systems, profile/prompt/guidance versions, settings, job order and source-code hash. plan-preview.json exists for a no-call preview.",
            "- runs/JOB/input.json and prompt.json: exact engineering inputs and guidance. No benchmark answers belong here.",
            "- runs/JOB/execution.json: actual request (no auth headers), raw response, modelVersion and token usage.",
            "- runs/JOB/bundle/fmea.json, fmea.csv and manifest.json: canonical draft and file integrity hashes.",
            "- runs/JOB/state.json and metrics.json: timing, validation, unknowns, unresolved flags, completeness and coverage availability.",
            "- analysis-RUN_ID/: consolidated CSV, descriptive statistics, PNG/SVG plots and preliminary-findings.md. The smoke report may contain only one observation.",
            "- Failures and uncertain attempts are preserved. No automatic retries or fabricated replacement sheets.", "",
            "## Verify files", "", "From the extracted bundle root:", "", "```python",
            "from pathlib import Path", "import hashlib", "root = Path('.')",
            "for line in (root / 'checksums.sha256').read_text().splitlines():",
            "    expected, name = line.split('  ', 1)",
            "    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name",
            "print('Bundle checksums verified')", "```", "",
            "To validate each FMEA offline, set PYTHONPATH to reproduction/src and run python -m sigma_fmea validate runs/JOB/bundle.",
            "To recompute CSVs/reports without an AI call: python -m sigma_fmea analyze . --output independent-analysis --no-plots.",
            "For plots, install matplotlib locally and omit --no-plots. Do not rerun generation merely to inspect this evidence.", "",
            "## Reproduce a new experiment", "",
            "Use the archived reproduction/ source and pilot-eight.json on Python 3.12. The generation commands require explicit paid approval and a locally configured GEMINI_API_KEY.",
            "Run experiment plan, then one smoke (max-calls 1), inspect it, then batch (max-calls 8) only after approval for seven additional calls. Use a new output directory.",
            "The requested model is fixed to gemini-3.8-flash; actual modelVersion must remain identical. The provider may update a stable alias: this is not an immutable snapshot guarantee.",
            "Repeating a live model request need not yield identical text. Recomputing the stored deterministic metrics does not require the service.", "",
            "No reviewed references currently support missed-mode percentages for the two scenario inputs. Unavailable coverage is not zero. Structural completeness is not correctness.",
            "No credentials, full NASA PDFs, reference FMECA answers or validated ground truth are included. All owners remain Unassigned.", ""]
    (output / "README.md").write_text("\n".join(rows), encoding="utf-8")
    sums = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            sums.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(output).as_posix())
    (output / "checksums.sha256").write_text("\n".join(sums) + "\n", encoding="utf-8")
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with Path(summary_file).open("a", encoding="utf-8") as stream:
            stream.write("## Sigma Airlines pilot\n\n| Planned | Attempted | Successful | Failed | Remaining |\n|---:|---:|---:|---:|---:|\n")
            stream.write("| " + " | ".join(str(progress.get(key, "not run")) for key in ("planned_generations", "attempted", "successful", "failed", "remaining")) + " |\n\n")
            stream.write(f"Download **fmea-pilot-{os.environ.get('GITHUB_RUN_ID')}** under this run's Artifacts. Start with README.md.\n\n")
            stream.write("Design: hydraulic + battery/DC; baseline/improved; two repetitions; eight planned calls. Unreviewed NASA conversions are not ground truth.\n")
    return progress


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "smoke", "remaining", "package"), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "results/pilot")
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--approved-calls", type=int, default=0)
    args = parser.parse_args()
    if args.model != load_json(CONFIG)["model"]:
        parser.error("Pilot model is fixed by pilot-eight.json; no silent model changes")
    if args.mode == "package":
        print(json.dumps(package(args.output), indent=2))
        return 0
    if args.mode == "plan":
        args.output.mkdir(parents=True, exist_ok=False)
        plan = build_plan(CONFIG)
        write_record(args.output / "plan-preview.json", plan)
        print(json.dumps(plan, indent=2))
        return 0
    expected = 1 if args.mode == "smoke" else 7
    if args.approved_calls != expected:
        parser.error(f"{args.mode} requires explicit authorization for {expected} new calls")
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        parser.error("Reruns are blocked to prevent accidental duplicate paid calls")
    if args.mode == "remaining":
        origin = load_json(args.output / "smoke-origin.json")
        if os.environ.get("GITHUB_SHA") != origin.get("commit_sha"):
            parser.error("Use the exact smoke source commit; input/prompt/code changes require a new campaign")
    result = run_experiment(CONFIG, args.output, "smoke" if args.mode == "smoke" else "batch", allow_paid=True,
                            max_calls=1 if args.mode == "smoke" else 8)
    print(json.dumps(result, indent=2))
    return 2 if result["failed"] or result["uncertain"] or (args.mode == "remaining" and result["remaining"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
