"""Offline immutable A-E index, operational/financial report and local research ZIP."""
import argparse
from collections import Counter
import csv
import json
import re
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import recover_fmea as recovery
from scripts import evaluate_multi_system as evaluation
from analysis.financial_impact.ingest import import_attempts
from analysis.financial_impact.metrics import observed_summary
from analysis.financial_impact.report import create_report, CONFIG


def table(path, rows):
    """Write a nonempty aggregate table once with stable columns."""
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def figures(summary, structures, output):
    """Save descriptive plots for representative drafts, without confidence claims."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    output.mkdir()
    labels = [r["system_id"][-1] for r in summary]
    for field, label in (("row_count", "Rows in selected unreviewed FMEA"), ("generation_duration_seconds", "Selected attempt duration (s)"), ("total_attempts_including_original", "All historical requests")):
        fig, ax = plt.subplots(figsize=(8, 5))
        values = [r[field] if r[field] is not None else 0 for r in summary]
        ax.bar(labels, values, color="#336b87")
        for i, row in enumerate(summary):
            if row[field] is None: ax.text(i, 0, "unresolved", ha="center")
        ax.set(xlabel="System (different engineering conditions)", ylabel=label)
        fig.text(.1, .01, "One selected draft per system; A alternatives remain separately indexed. No repeatability inference.", fontsize=8)
        fig.tight_layout(rect=(0,.04,1,1)); fig.savefig(output / (field + ".png"), dpi=300); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, metric in zip(axes.flat, (*recovery.engine.RATINGS, "RPN")):
        for i, row in enumerate(summary):
            data = structures.get(row["system_id"])
            if data:
                values = [r[metric] for r in data["rows"]]
                ax.boxplot([values], positions=[i], widths=.45, whis=(0,100), showfliers=False)
        ax.set(xticks=list(range(5)), xticklabels=labels, title="Provisional " + metric)
    fig.text(.1,.01,"Generated rows are nested within unreviewed drafts; distributions are descriptive, not engineering acceptance.",fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1)); fig.savefig(output / "provisional_ratings.png",dpi=300); plt.close(fig)


def validate_pilot_csv(path):
    """Allow the known historical timing column while validating unchanged FMEA content."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        headers = next(csv.reader(stream), None)
    expected = recovery.engine.CSV_FIELDS
    historical = expected[:4] + ["generation_minutes"] + expected[4:]
    if headers not in (expected, historical):
        raise ValueError("Unsupported System A pilot CSV headers")
    data = evaluation.structure(path, "system_A")
    if not data["row_count"]:
        raise ValueError("Empty System A pilot CSV")
    return data


def complete(folder, version="v1"):
    """Revalidate every selected artifact and publish a fresh versioned local review package."""
    if not re.fullmatch(r"v[1-9][0-9]*", version):
        raise ValueError("Invalid review version")
    folder = Path(folder).resolve()
    plan = recovery.read(folder / "plan.json")
    campaign = plan["recovery_campaign_id"]
    state = recovery.read(folder / "status.json")
    if state["phase"] != "generation_and_reconciliation_complete":
        raise ValueError("Campaign not ready for offline finalization")
    records = state["attempts"]
    if len(records) > 6 or state["reserved_requests"] > 6 or any(sum(r["system_id"]==s for r in records)>3 for s in plan["systems"]):
        raise ValueError("Request limit violation")
    snapshots = recovery.read(folder / "original_checksums.json")
    for path, digest in snapshots.items():
        if recovery.digest(path) != digest: raise ValueError("Original evidence or generation source changed: " + path)
    reconciliation_path = Path(state.get("reconciliation_manifest", folder / "reconciliation" / recovery.ORIGINAL / campaign / "reconciliation_manifest.json")).resolve()
    reconciled = recovery.read(reconciliation_path)
    # Keep a conventional local copy of downloaded Actions artifacts as well as the controller evidence.
    for downloaded in (folder / "downloads").glob("*"):
        if not downloaded.is_dir(): continue
        canonical = ROOT / "results/github" / downloaded.name
        if canonical.exists():
            for source in downloaded.rglob("*"):
                if source.is_file() and recovery.digest(canonical / source.relative_to(downloaded)) != recovery.digest(source):
                    raise ValueError("Conflicting canonical Actions artifact")
        else:
            canonical.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(downloaded, canonical)
    output = ROOT / "results/ce-review" / (campaign + "-" + version)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    shutil.copytree(reconciliation_path.parent, output / "reconciled-B-E")
    baseline = ROOT / "results/single-system-replicates/system_A/20261101T163923Z-system-a-five"
    a = recovery.read(baseline / "manifest.json")
    a_successes = sorted((r for r in a["runs"] if r["status"]=="success"), key=lambda r:r["run_number"])
    a_selected = a_successes[0] if a_successes else None
    a_index = []
    receipts = list(reconciled["attempts"])
    evidence_path = folder / "original_provider_evidence.json"
    evidence = recovery.read(evidence_path) if evidence_path.exists() else {}
    for record in receipts:
        if record.get("experiment_id") == campaign:
            source = next((r for r in records if r["attempt_id"] == record["attempt_id"]), {})
            if source.get("metadata_path"):
                execution_path = Path(source["metadata_path"]).parent / f"{record['system_id']}_v2.0_run01_execution.json"
                if record["artifacts"].get(execution_path.name) != recovery.digest(execution_path):
                    raise ValueError("Recovery execution receipt hash mismatch")
                engine_record = recovery.read(execution_path)
                if any(engine_record[k] != record[k] for k in ("system_id", "model", "prompt_version", "skill_sha256", "system_sha256")):
                    raise ValueError("Recovery engine identity mismatch")
                config = engine_record["configuration"]
                # The SDK serializes schema aliases/order in-place; compare with the original runtime receipt.
                original_config = recovery.read(recovery.BASE / "system_B/system_B_v2.0_run01_execution.json")["configuration"]
                if config != original_config:
                    raise ValueError("Recovery engine configuration mismatch")
                for key in ("configuration", "api_request_seconds", "parsing_validation_seconds"):
                    record[key] = engine_record.get(key)
        historical = evidence.get(record["system_id"], {})
        if record.get("experiment_id") == recovery.ORIGINAL and record["status"] == "failed" and historical.get("http_status") == 503:
            record["original_failure_classification"] = record.get("failure_classification")
            record.update(http_status=503, failure_classification="provider_unavailable_503", historical_http_evidence=historical)
    for run in a["runs"]:
        normalized = {**a["plan"], **run, "metadata_schema": "fmea-execution-1", "experiment_id": a["plan"]["batch_id"],
            "attempt_id": f"system_A_v2.0_run{run['run_number']:02d}", "configuration": {"temperature": 0, "retry_attempts": 1, "max_output_tokens": 65536}}
        receipts.append(normalized)
        if run["status"] != "success": continue
        for name, item in run["outputs"].items():
            if Path(name).name != name or recovery.digest(baseline / name) != item["sha256"]: raise ValueError("System A integrity failure")
        validate_pilot_csv(baseline / run["csv_file"])
        a_index.append({"attempt_id": normalized["attempt_id"], "run_number": run["run_number"], "path": str(baseline / run["csv_file"]),
            "row_count": run["row_count"], "representative": run is a_selected, "duration_seconds": run["duration_seconds"]})
    effective = dict(reconciled["effective_results"])
    effective["system_A"] = {"status": "success" if a_selected else "unresolved", "effective_attempt_id": f"system_A_v2.0_run{a_selected['run_number']:02d}" if a_selected else None,
        "path": str(baseline / a_selected["csv_file"]) if a_selected else None}
    financial_input = {"financial_schema": "reconciled-campaign-1", "original_campaign_id": recovery.ORIGINAL,
        "recovery_campaign_id": campaign, "attempts": receipts, "effective_results": effective}
    recovery.atomic(output / "all-A-E-financial-input.json", financial_input)
    financial, metrics = create_report([output / "all-A-E-financial-input.json"], output / "financial_impacts", analysis_id="A-E-financial-v1")
    attempts = metrics["attempts"]
    summary, structures, coverage, distributions = [], {}, [], []
    review = ["# Preliminary A-E engineering review", "", "Unreviewed AI drafts; no independent engineering acceptance. No reference or ground-truth FMEA was read.",
        "A representative is the earliest schema-valid successful pilot run (run 3); runs 4 and 5 remain separate alternatives. No selection by quality score.",
        "Provider availability, CSV validity, engineering acceptance and financial cost are separate outcomes. A 503 is not a skill engineering-quality failure.", ""]
    for system in ["system_"+c for c in "ABCDE"]:
        result = effective[system]
        history = [r for r in attempts if r["system_id"]==system]
        selected = next((r for r in history if r["attempt_id"]==result["effective_attempt_id"]), None)
        path = Path(result["path"]) if result["path"] else None
        data = None
        if path:
            if system == "system_A":
                data = validate_pilot_csv(path)
            else:
                recovery.validate_csv(path)
                data = evaluation.structure(path, system)
            structures[system] = data
            # Copy only generated CSVs and non-secret operational metadata into the local review package.
            dataset = output / "dataset" / system; dataset.mkdir(parents=True)
            shutil.copy2(path, dataset / path.name)
        row = {"system_id": system, "source_campaign": selected["experiment_id"] if selected else None,
            "effective_attempt_id": result["effective_attempt_id"], "generation_status": result["status"],
            "row_count": data["row_count"] if data else None,
            "generation_duration_seconds": selected["duration_seconds"] if selected else None,
            "attempts_to_selected_success": sum(r["started_at"] <= selected["started_at"] for r in history) if selected else None,
            "total_attempts_including_original": len(history), "successful_generations": sum(r["status"]=="success" for r in history),
            "provider_503_failures": sum(r.get("http_status")==503 for r in history),
            "total_generation_duration_seconds": sum(r["duration_seconds"] or 0 for r in history),
            "retry_wait_seconds": sum(r.get("retry_wait_seconds",0) for r in history),
            "model": recovery.MODEL, "skill_version": "v2.0", "engineering_review_status": "provisional_unreviewed",
            "path": str(path) if path else None, "csv_sha256": recovery.digest(path) if path else None}
        summary.append(row)
        review += ["## " + system, "", f"Selected draft rows: {row['row_count']}; historical requests: {len(history)}; engineering acceptance unavailable."]
        if not data:
            review += ["No usable FMEA. No quality distribution or coverage fabricated.", ""]; continue
        review += [f"CSV/schema/rating/RPN checks pass. Exact duplicate component/mode/cause triples: {data['exact_duplicate_triples']}.",
            f"Grouped-unit candidates: {data['grouped_unit_candidates']}.",
            f"Literal component labels with only one mode row: {len(data['single_mode_component_labels'])}; these require review, not a proven omission."]
        for item in data["inventory"]:
            coverage.append({"system_id":system, **item, "validated_component_coverage_fraction": None})
            if item["needs_omission_or_unit_review"]:
                review.append(f"- Possible omission/unit expansion: {item['inventory_component']} (stated quantity {item['stated_quantity']}); lexical candidate labels: {item['candidate_labels']}.")
        for metric, counts in data["ratings"].items():
            for score, count in counts.items(): distributions.append({"system_id":system,"metric":metric,"score":score,"row_count":count})
        for index, generated in enumerate(data["rows"],1):
            text = " ".join(str(generated[f]) for f in ("evidence","rating_rationale","review_flag"))
            if any(word in text.lower() for word in ("assum", "unknown", "not provided", "not specified", "requires", "verify", "review")):
                review.append(f"- Row {index}, {generated['component']} / {generated['failure_mode']}: {generated['review_flag']} | {generated['rating_rationale']}")
        review += ["Human checks still required: verify effects against architecture, proposed versus existing detection, occurrence apportionment, severity premises and unsupported assumptions. Suspect modes are review candidates, not adjudicated defects.", ""]
    # Retain each successful A pilot worksheet as a separate indexed alternative.
    alternatives = output / "dataset/system_A/alternatives"; alternatives.mkdir(parents=True)
    for record in a_index: shutil.copy2(record["path"], alternatives / Path(record["path"]).name)
    table(output / "A-E-summary.csv", summary)
    if coverage: table(output / "component-coverage-candidates.csv", coverage)
    if distributions: table(output / "provisional-rating-distributions.csv", distributions)
    recovery.atomic(output / "structure-metrics.json", structures)
    index = {"recovery_campaign_id":campaign, "original_campaign_id":recovery.ORIGINAL,
        "representative_selection_rule": "A: earliest successful schema-valid pilot run; C/E: sole valid successful recovery; B/D: unchanged originals",
        "effective_FMEA_count":sum(r["generation_status"]=="success" for r in summary), "systems":summary, "system_A_successful_pilot_outputs":a_index,
        "request_history":str(output / "all-A-E-financial-input.json"), "financial_report":str(financial),
        "engineering_acceptance":"unmeasured", "caution":"Different systems are not repeatability replicates; A pilot alternatives remain separate observations."}
    recovery.atomic(output / "A-E-dataset-index.json", index)
    (output / "engineering-review.md").write_text("\n".join(review),encoding="utf-8")
    figures(summary, structures, output / "figures")
    recovery_summary = []
    for system in plan["systems"]:
        observations = [r for r in records if r["system_id"]==system]
        recovery_summary.append({"system_id":system,"attempts":len(observations),"http_503_failures":sum(r.get("http_status")==503 for r in observations),
            "final_status":state["systems"][system], "FMEA_rows":next((r.get("row_count") for r in observations if r["status"]=="success"),None),
            "total_generation_seconds":sum(r["elapsed_seconds"] for r in observations),"retry_wait_seconds":sum(r.get("retry_wait_seconds",0) for r in observations)})
    new_financial = [r for r in attempts if r["experiment_id"] == campaign]
    campaign_summary = {"recovery_campaign_id":campaign,"original_campaign_id":recovery.ORIGINAL,"new_requests":len(records),
        "successful_new_requests":sum(r["status"]=="success" for r in records),"failed_new_requests":sum(r["status"]!="success" for r in records),
        "retries":sum(r.get("retry_number",0)>0 for r in records),"generation_seconds":sum(r["elapsed_seconds"] for r in records),
        "api_request_seconds":sum(r.get("execution",{}).get("generation_seconds",0) for r in records),
        "retry_wait_seconds":state["retry_wait_seconds"], "effective_system_count": index["effective_FMEA_count"], "systems":recovery_summary,
        "new_request_known_token_estimate_subtotal_usd":sum(r["cost_usd"] for r in new_financial if r["cost_usd"] is not None),
        "new_request_unknown_cost_attempts":sum(r["cost_usd"] is None for r in new_financial),
        "new_request_actual_billed_total_usd":None,
        "new_request_cost_per_successful_generation_usd":observed_summary(new_financial)["cost_per_successful_generation_usd"],
        "financial_observed":metrics["observed"], "all_original_checksums_verified":True,"skill_unchanged":True}
    recovery.atomic(output / "campaign-summary.json", campaign_summary)
    (output / "README.md").write_text("# C/E recovery and A-E review\n\nAll FMEAs are unreviewed AI drafts. See A-E-dataset-index.json, A-E-summary.csv, campaign-summary.json, engineering-review.md and financial_impacts/.\nA run 3 is the chronological representative; all three successful A pilot drafts remain separately indexed. Original C/E HTTP503 failures are operational history only.\nNo repeatability or engineering-acceptance claim; no manual labor or savings invented. Literal component candidate matches have no validated coverage percentage.\n",encoding="utf-8")
    evidence_dir = output / "operational-evidence"; evidence_dir.mkdir()
    for file in (folder / "plan.json",folder / "status.json", folder / "original_checksums.json", evidence_path):
        if file.exists(): shutil.copy2(file,evidence_dir / file.name)
    for i, record in enumerate(receipts): recovery.atomic(evidence_dir / f"attempt-{i+1:02d}.json",record)
    for path, digest in snapshots.items():
        if recovery.digest(path)!=digest: raise ValueError("Original changed during reporting")
    checksums = {str(p.relative_to(output)).replace("\\","/"):recovery.digest(p) for p in output.rglob("*") if p.is_file()}
    recovery.atomic(output / "review-checksums.json", checksums)
    for candidate in output.rglob("*"):
        if candidate.is_file() and candidate.suffix in (".json", ".csv", ".md", ".txt"):
            if re.search(r"AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN .*PRIVATE KEY", candidate.read_text(encoding="utf-8-sig")):
                raise ValueError("Possible credential in review package; archive not created")
    archive=folder / (campaign + "-A-E-review-" + version + ".zip")
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as stream:
        for path in output.rglob("*"):
            if path.is_file(): stream.write(path,"review-"+version+"/"+str(path.relative_to(output)).replace("\\","/"))
    print(json.dumps({"output":str(output),"zip":str(archive),"summary":campaign_summary},indent=2))
    return output,archive


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("folder",type=Path);parser.add_argument("--version",default="v1")
    args=parser.parse_args()
    complete(args.folder,args.version)
