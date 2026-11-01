"""Fixed five-attempt System A pilot using the standalone v2 engine; no retries."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fmea_generator as engine

SYSTEM = ROOT / "system_descriptions/system_A.txt"
SKILL = ROOT / "skill/fmea_instructions.md"
BASE = ROOT / "results/single-system-replicates/system_A"
CORE = ("component", "function", "failure_mode", "cause", "local_effect",
        "system_effect", "recommended_action")


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value, exclusive=False):
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if exclusive:
        with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    else:
        temporary = Path(str(path) + ".tmp")
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        temporary.replace(path)


def write_csv(path, fields, rows):
    with Path(path).open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        # Derived sheets are escaped for spreadsheet opening; originals are untouched.
        for row in rows:
            writer.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(
                ("=", "+", "-", "@")) else v for k, v in row.items()})


def plan(model, batch_id):
    if not re.fullmatch(r"\d{8}T\d{6}Z-[A-Za-z0-9_-]+", batch_id):
        raise ValueError("Use a timestamped batch ID: YYYYMMDDTHHMMSSZ-unique-suffix")
    if not SYSTEM.read_text(encoding="utf-8").strip():
        raise ValueError("System A input is empty")
    if engine.PROMPT_VERSION != "v2.0":
        raise ValueError("This pilot requires unchanged skill v2.0")
    output = BASE / batch_id
    if os.path.lexists(output):
        raise FileExistsError(output)
    return {
        "system_id": "system_A", "system_file": str(SYSTEM.relative_to(ROOT)),
        "system_sha256": sha(SYSTEM), "skill_sha256": sha(SKILL),
        "generator_sha256": sha(ROOT / "fmea_generator.py"),
        "prompt_version": engine.PROMPT_VERSION, "model": model,
        "temperature": 0, "response_mime_type": "application/json",
        "response_schema_sha256": hashlib.sha256(json.dumps(
            engine.RESPONSE_SCHEMA, sort_keys=True).encode()).hexdigest(),
        "retry_attempts": 1, "planned_run_numbers": [1, 2, 3, 4, 5],
        "max_generation_requests": 5, "batch_id": batch_id,
        "output": str(output.relative_to(ROOT)), "preflight_at": now(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "google_genai_version": importlib.metadata.version("google-genai"),
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "provisional_ratings": "unreviewed; no engineering validity or coverage claim",
    }


def preflight(model, batch_id):
    result = plan(model, batch_id)
    engine.load_local_env()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is unavailable; no generation requested")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key, http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=1)))
    try:
        try:
            selected = client.models.get(model=model)
        except Exception as exc:
            alternatives = [m.name for m in client.models.list()
                            if "generateContent" in (m.supported_actions or [])]
            raise RuntimeError(f"Configured model unavailable ({type(exc).__name__}); "
                               f"no generations sent. Available alternatives: {alternatives}") from None
        if not selected.output_token_limit or "generateContent" not in (selected.supported_actions or []):
            raise RuntimeError("Configured model has no usable generation capability/output limit")
        result["max_output_tokens"] = selected.output_token_limit
        result["available_model_name"] = selected.name
        result["availability_scope"] = "models.get capability check; generation quota not proven"
    finally:
        client.close()
    return result


def populated(value):
    return isinstance(value, str) and value.strip().casefold() not in {
        "", "not provided", "unknown", "n/a", "none", "not specified"}


def describe(values):
    return {"n": len(values), "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None,
            "sample_stddev": statistics.stdev(values) if len(values) > 1 else None}


def package(output, manifest):
    combined = []
    for run in manifest["runs"]:
        if run["status"] == "success":
            with (output / run["csv_file"]).open(encoding="utf-8", newline="") as stream:
                combined.extend({"run_number": run["run_number"], **row} for row in csv.DictReader(stream))
    write_csv(output / "combined.csv", ["run_number", *engine.CSV_FIELDS], combined)
    summary_fields = ["run_number", "status", "request_invocations", "started_at", "duration_seconds",
                      "row_count", "core_populated", "core_total", "review_flag_count", "csv_file", "raw_file"]
    write_csv(output / "run-summary.csv", summary_fields,
              ({k: run.get(k) for k in summary_fields} for run in manifest["runs"]))
    stats = {"generated_rows_per_successful_run": describe([
        run["row_count"] for run in manifest["runs"] if run["status"] == "success"]),
        "pooled_row_ratings_unreviewed": {field: describe([int(row[field]) for row in combined])
                                         for field in (*engine.RATINGS, "RPN")},
        "per_run_ratings_unreviewed": {str(run["run_number"]): {
            field: describe([int(row[field]) for row in combined if row["run_number"] == run["run_number"]])
            for field in (*engine.RATINGS, "RPN")} for run in manifest["runs"] if run["status"] == "success"},
        "limitations": "Descriptive only; rows are nested within runs. No coverage, accuracy, validated ratings or inferential claims."}
    write_json(output / "descriptive-statistics.json", stats, exclusive=True)
    matches = defaultdict(list)
    for row in combined:
        # Conservative lexical candidate grouping; preserve unit numbers and original wording.
        key = tuple(" ".join(row[f].casefold().split()) for f in ("component", "failure_mode"))
        matches[key].append(row)
    candidates = []
    for key, rows in sorted(matches.items()):
        runs = sorted({row["run_number"] for row in rows})
        candidates.append({"component_key": key[0], "failure_mode_key": key[1],
                           "run_numbers": json.dumps(runs), "run_count": len(runs),
                           "classification": "recurring candidate" if len(runs) > 1 else "unique candidate",
                           "original_descriptions": json.dumps(sorted({row["failure_mode"] for row in rows}))})
    write_csv(output / "candidate-matches.csv", ["component_key", "failure_mode_key", "run_numbers",
              "run_count", "classification", "original_descriptions"], candidates)
    readme = """# System A standalone Gemini v2 exploratory repeatability pilot

All sheets and S/O/D/RPN are UNREVIEWED AI drafts. Five independent sequential
requests use identical input, skill, model and temperature 0; independence here
means separate stateless requests, not statistical independence or a model seed guarantee.

Start with manifest.json and run-summary.csv. Successful original CSVs and raw text
are preserved separately. Failures retain available raw evidence; not_attempted
runs did not consume a request. request_invocations counts SDK generation invocations;
an interrupted dispatch can have an uncertain billing outcome and must not be retried.
No automatic retries or fallback models are allowed. Missing provider metadata is null.
Input and skill snapshots have their exact byte hashes recorded in the manifest.

In Excel use Data > From Text/CSV, select UTF-8, and import text columns as text
(original model text can contain spreadsheet formulas). combined.csv and candidate-
matches.csv are derived, spreadsheet-escaped sheets; originals remain unchanged.
In Python: pandas.read_csv('combined.csv'), or use the standard-library csv module.
Check checksums.sha256 before review; it binds every packaged file except itself.

descriptive-statistics.json reports successful-run row counts and provisional ratings,
both per run and pooled. Failed sheets are excluded from rating summaries, not hidden.
candidate-matches.csv groups only case/whitespace-normalized component + mode text,
preserving unit numbers. These are candidate matches, not validated equivalence.
Wording differences may describe equivalent modes; identical wording may not.

## Engineering-review checklist

- [ ] Check each mode/cause/effect for physical plausibility and architecture consistency.
- [ ] Inspect omissions with an independently reviewed reference, prepared by humans.
- [ ] Check individual-unit expansion, shared elements and duplicate rows.
- [ ] Separate supported package facts from assumptions and model hypotheses.
- [ ] Review severity, apportioned occurrence rates, detection provisions and RPN arithmetic.
- [ ] Verify evidence citations and identify unsupported controls/actions/ratings.
- [ ] Adjudicate candidate matches and unique descriptions manually.
- [ ] Record reviewer, date, decisions, unresolved issues and scope limitations privately.

Generated row count is not coverage; no missed-mode denominator is available.
Field population is not engineering correctness. Provisional ratings are not validated.
This is a five-run exploratory pilot, not the full research experiment or the canonical
baseline/improved condition. Keep all outputs out of Git and archived research_results.
"""
    with (output / "README.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(readme)
    manifest["summary"] = {"successes": sum(r["status"] == "success" for r in manifest["runs"]),
                           "failures": sum(r["status"] not in {"success", "not_attempted"} for r in manifest["runs"]),
                           "not_attempted": sum(r["status"] == "not_attempted" for r in manifest["runs"])}
    manifest["finished_at"] = now()
    write_json(output / "manifest.json", manifest)
    with (output / "checksums.sha256").open("x", encoding="utf-8", newline="\n") as stream:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != "checksums.sha256":
                stream.write(f"{sha(path)}  {path.name}\n")


def execute(frozen, approved_calls):
    if approved_calls != 5 or os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise ValueError("Requires exactly five authorized attempts; workflow reruns are prohibited")
    current = plan(frozen["model"], frozen["batch_id"])
    for key in ("system_sha256", "skill_sha256", "generator_sha256", "source_commit",
                "prompt_version", "temperature", "response_schema_sha256", "google_genai_version"):
        if current[key] != frozen[key]:
            raise ValueError(f"Frozen preflight changed: {key}")
    if not isinstance(frozen.get("max_output_tokens"), int) or frozen["max_output_tokens"] < 1:
        raise ValueError("A successful non-generation model preflight is required")
    output = BASE / frozen["batch_id"]
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"plan": frozen, "request_invocations": 0, "reserved_attempts": 0,
                "runs": [{"run_number": run, "status": "not_attempted"} for run in range(1, 6)]}
    for source, name in ((SYSTEM, "system_A.input.txt"), (SKILL, "skill.instructions.md")):
        with (output / name).open("xb") as stream:
            stream.write(source.read_bytes())
    write_json(output / "manifest.json", manifest, exclusive=True)
    for record in manifest["runs"]:
        if sha(SYSTEM) != frozen["system_sha256"] or sha(SKILL) != frozen["skill_sha256"]:
            manifest["halt_reason"] = "Input/skill mutation; remaining requests blocked"
            break
        number = record["run_number"]
        prefix = f"system_A_{engine.PROMPT_VERSION}_run{number:02d}"
        record.update({"system_id": "system_A", "system_sha256": frozen["system_sha256"],
                       "skill_sha256": frozen["skill_sha256"], "prompt_version": frozen["prompt_version"],
                       "model": frozen["model"], "temperature": 0, "started_at": now(),
                       "status": "reserved", "request_invocations": 0,
                       "execution": {"expected_max_output_tokens": frozen["max_output_tokens"]}})
        manifest["reserved_attempts"] += 1
        write_json(output / "manifest.json", manifest)

        def before_request():
            if manifest["request_invocations"] >= 5:
                raise RuntimeError("Five-request cap reached")
            record["request_invocations"] = 1
            record["request_dispatched_at"] = now()
            record["status"] = "dispatching_outcome_uncertain"
            manifest["request_invocations"] += 1
            write_json(output / "manifest.json", manifest)

        start = time.monotonic()
        try:
            rows = engine.generate_fmea(SYSTEM, "system_A", version=engine.PROMPT_VERSION,
                run=number, output_dir=output, model=frozen["model"],
                execution=record["execution"], before_request=before_request)
            record.update({"status": "success", "row_count": len(rows),
                           "core_populated": sum(populated(row[f]) for row in rows for f in CORE),
                           "core_total": len(rows) * len(CORE),
                           "core_fields": list(CORE),
                           "review_flag_count": sum(populated(row["review_flag"]) for row in rows),
                           "ratings_status": "provisional_unreviewed"})
        except Exception as exc:
            finish = record["execution"].get("finish_reason")
            status = ("truncation" if finish == "MAX_TOKENS" else
                      "blocked" if finish and finish != "STOP" else
                      "validation_failure" if isinstance(exc, ValueError) else "provider_failure")
            message = str(exc).replace(os.getenv("GEMINI_API_KEY") or "\0", "[REDACTED]")
            record.update({"status": status, "error_type": type(exc).__name__, "error": message})
            code = getattr(exc, "code", None)
            if not record["request_invocations"] or code in {400, 401, 403, 404, 429} or (number == 1 and status == "truncation"):
                manifest["halt_reason"] = f"Run {number}: configuration/quota/output-limit failure; no further calls"
        finally:
            record["duration_seconds"] = round(time.monotonic() - start, 5)
            record["finished_at"] = now()
            record["outputs"] = {}
            for kind, suffix in (("csv", ".csv"), ("raw", "_raw.txt")):
                path = output / (prefix + suffix)
                if path.is_file():
                    record[f"{kind}_file"] = path.name
                    record["outputs"][path.name] = {"sha256": sha(path), "bytes": path.stat().st_size}
            write_json(output / "manifest.json", manifest)
            print(f"Run {number}: {record['status']}, rows={record.get('row_count')}, "
                  f"seconds={record['duration_seconds']}", flush=True)
        if manifest.get("halt_reason"):
            break
    package(output, manifest)
    return output, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "run"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--approved-calls", type=int, default=0)
    parser.add_argument("--plan-file", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "preflight":
        frozen = preflight(args.model, args.batch_id)
        write_json(args.plan_file, frozen, exclusive=True)
        print(json.dumps(frozen, indent=2))
    else:
        frozen = json.loads(args.plan_file.read_text(encoding="utf-8"))
        if (args.model, args.batch_id) != (frozen["model"], frozen["batch_id"]):
            raise ValueError("CLI does not match frozen preflight")
        output, manifest = execute(frozen, args.approved_calls)
        print(json.dumps({"output": str(output), "requests": manifest["request_invocations"],
                          "summary": manifest["summary"]}, indent=2))
        if manifest["summary"]["successes"] != 5:
            sys.exit(1)


if __name__ == "__main__":
    main()
