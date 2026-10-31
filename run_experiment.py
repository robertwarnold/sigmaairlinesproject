"""Batch generation; records failures and combines successful FMEA CSV files."""
import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

from fmea_generator import ROOT, PROMPT_VERSION, CSV_FIELDS, generate_fmea


def append_log(path, row):
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "case_id", "version", "run", "status", "error"])
        if f.tell() == 0:
            writer.writeheader()
        writer.writerow(row)


def combine_results(output_dir, version):
    rows = []
    for path in sorted(output_dir.glob(f"system_*_{version}_run*.csv")):
        if path.name.endswith("_raw.csv"):
            continue
        with path.open(newline="", encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    if rows:
        combined = output_dir / f"all_generated_fmeas_{version}.csv"
        with combined.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Combined {len(rows)} FMEA rows into {combined}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, help="Pilot: 1; experiment: 25")
    parser.add_argument("--version", default=PROMPT_VERSION)
    parser.add_argument("--delay", type=float, default=5, help="Seconds between API requests")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    if args.runs < 1 or args.delay < 0:
        parser.error("--runs must be >= 1 and --delay must be >= 0")
    systems = [(f"system_{i}", ROOT / "system_descriptions" / f"system_{i}.txt") for i in range(1, 5)]
    missing = [str(path) for _, path in systems if not path.is_file()]
    if missing:
        parser.error("Missing system description(s): " + ", ".join(missing))
    output_dir = ROOT / "results"
    output_dir.mkdir(exist_ok=True)
    log = output_dir / "run_log.csv"
    for case_id, path in systems:
        for run in range(1, args.runs + 1):
            output_path = output_dir / f"{case_id}_{args.version}_run{run:02d}.csv"
            if output_path.exists():
                print(f"Skipping existing output: {output_path.name}")
                continue
            print(f"Generating {case_id}, version {args.version}, run {run}")
            status, error = "success", ""
            try:
                generate_fmea(path, case_id, version=args.version, run=run,
                              output_dir=output_dir, model=args.model)
            except Exception as exc:
                status, error = "error", str(exc)
                print(f"FAILED: {error}")
            append_log(log, {"timestamp": datetime.now(timezone.utc).isoformat(),
                             "case_id": case_id, "version": args.version,
                             "run": run, "status": status, "error": error})
            time.sleep(args.delay)
    combine_results(output_dir, args.version)


if __name__ == "__main__":
    main()
