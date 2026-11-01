"""Offline A-E structural/execution review; candidate engineering findings, not validation."""
from collections import Counter
import csv
import json
from pathlib import Path
import re
import statistics
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fmea_generator as engine
from analysis.financial_impact.data_schema import read_json
from analysis.financial_impact.ingest import import_attempts, sha256
from scripts.multi_system_pilot import Progress, SYSTEMS, atomic
from scripts.single_system_replicates import write_csv

# A deliberately loose lexical screen for human review, not a validated component crosswalk.
CANDIDATE_NAME_WORD_FRACTION = .65


def inventory(system):
    """Extract stated quantities/provisions from original input packages, not reference answers."""
    text = (ROOT / f"system_descriptions/{system}.txt").read_text(encoding="utf-8")
    # Only the input package's component list supplies the matching inventory.
    section = text.split("COMPONENT LIST", 1)[1].split("10.", 1)[0]
    items = []
    for line in section.splitlines():
        fields = [part.strip() for part in line.lstrip("- ").split("|")]
        if len(fields) >= 4 and fields[1].isdigit():
            items.append({"name": fields[0], "quantity": int(fields[1]), "rate": fields[2], "provisions": fields[3]})
    return items


def words(text):
    """Normalize component words for candidate matching; never claim engineering equivalence."""
    stop = {"the", "and", "of", "per", "one", "each", "between", "with", "system", "includes"}
    return {w for w in re.findall(r"[a-z]+", text.casefold()) if w not in stop}


def structure(path, system):
    """Revalidate CSV/schema/RPN and identify review candidates without a ground-truth set."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or set(engine.FIELDS + ["RPN"]) - set(reader.fieldnames):
            raise ValueError("Missing required CSV columns")
        source = list(reader)
    if any(None in row or None in row.values() for row in source):
        raise ValueError("Malformed CSV row width")
    rows = []
    for row in source:
        candidate = {f: int(row[f]) if f in engine.RATINGS else row[f] for f in engine.FIELDS}
        validated = engine.parse_fmea(json.dumps([candidate]))[0]
        if validated["RPN"] != int(row["RPN"]):
            raise ValueError("CSV RPN arithmetic mismatch")
        rows.append(validated)
    components = Counter(r["component"] for r in rows)
    triples = Counter((r["component"].casefold(), r["failure_mode"].casefold(), r["cause"].casefold()) for r in rows)
    items = inventory(system)
    mapping = []
    for item in items:
        item_words = words(item["name"].split("(", 1)[0])
        candidates = []
        for component in components:
            overlap = len(item_words & words(component)) / max(1, len(item_words))
            if overlap >= CANDIDATE_NAME_WORD_FRACTION:
                candidates.append(component)
        # Similar names can overlap (ESC vs ESC cooling fan); retain candidates, not coverage claims.
        mapping.append({"inventory_component": item["name"], "stated_quantity": item["quantity"],
            "candidate_labels": candidates, "candidate_distinct_labels": len(candidates),
            "candidate_rows": sum(components[name] for name in candidates),
            "needs_omission_or_unit_review": len(candidates) < item["quantity"], "match_status": "lexical candidates only"})
    return {"rows": rows, "row_count": len(rows), "distinct_components": len(components),
            "component_counts": dict(components), "repeated_component_labels": {k: v for k, v in components.items() if v > 1},
            "missing_required_fields": 0, "schema_validation_failures": 0,
            "exact_duplicate_triples": sum(count - 1 for count in triples.values()),
            "grouped_unit_candidates": [name for name in components if re.search(r"\d\s*[-–]\s*\d|#?\d\s*(?:and|&)\s*#?\d", name)],
            "single_mode_component_labels": [name for name, count in components.items() if count == 1],
            "review_flags": Counter(r["review_flag"] for r in rows), "inventory": mapping,
            "ratings": {f: {str(value): sum(r[f] == value for r in rows) for value in sorted({r[f] for r in rows})}
                        for f in (*engine.RATINGS, "RPN")}}


def make_figures(attempts, structures, output):
    """Save seven descriptive 300-dpi figures with sample sizes and no confidence intervals."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import textwrap
    output.mkdir(exist_ok=False)
    systems = ["system_" + letter for letter in "ABCDE"]
    captions = {}
    def save(fig, name, caption):
        fig.subplots_adjust(bottom=.25)
        sizes = "; ".join(f"{s[-1]}: {sum(a['system_id']==s for a in attempts)} attempts/{sum(a['system_id']==s and a['status']=='success' for a in attempts)} successes" for s in systems)
        fig.text(.06, .035, textwrap.fill(sizes + ". Source: execution metadata and unreviewed generated drafts. " + caption, 130), fontsize=9)
        fig.savefig(output / (name + ".png"), dpi=300)
        plt.close(fig)
        captions[name] = caption
    for metric, filename, title, ylabel in (
        ("row_count", "01_rows", "Generated failure-mode rows by system", "Rows / successful draft"),
        ("duration_seconds", "02_duration", "Elapsed attempt duration by system", "Seconds / attempt"),
        ("cost_usd", "03_api_cost", "Known token estimates by system", "Estimated USD / attempt")):
        fig, ax = plt.subplots(figsize=(11, 6))
        for i, system in enumerate(systems):
            records = [a for a in attempts if a["system_id"] == system]
            for j, a in enumerate(records):
                value = a.get(metric)
                x = i + (j - (len(records) - 1) / 2) * .10
                if value is not None:
                    ax.scatter(x, value, marker="o" if a["status"] == "success" else "x",
                               color="#336b87" if a["status"] == "success" else "#a34f43", s=65)
            if metric == "cost_usd" and any(a["cost_usd"] is None for a in records):
                ax.annotate("Failed billing unknown", (i, .94), xycoords=("data", "axes fraction"), ha="center", fontsize=8)
        ax.set(title=title, xlabel="Engineering system (distinct conditions)", ylabel=ylabel)
        ax.set_xticks(range(5), list("ABCDE"))
        ax.set_xlim(-.5, 4.5)
        save(fig, filename, "Each point is one observed attempt; blue circles succeed, red crosses fail. Missing rows/cost are not zero. No repeatability interval or pooled system inference.")
    fig, ax = plt.subplots(figsize=(11, 6))
    successes = [sum(a["system_id"] == s and a["status"] == "success" for a in attempts) for s in systems]
    failures = [sum(a["system_id"] == s and a["status"] != "success" for a in attempts) for s in systems]
    ax.bar(list("ABCDE"), successes, label="Successful generations", color="#336b87")
    ax.bar(list("ABCDE"), failures, bottom=successes, label="Failed attempts", color="#a34f43")
    ax.set(title="Observed execution outcomes", xlabel="Engineering system", ylabel="Attempts (count)")
    ax.legend()
    save(fig, "04_execution_outcomes", "Generation success is not engineering acceptance. B-E each have one attempt; five System A attempts are a separate pilot.")
    for metric, name, title in (("severity", "05_severity", "Provisional severity distributions"), ("RPN", "06_rpn", "Provisional RPN distributions")):
        fig, ax = plt.subplots(figsize=(11, 6))
        for i, system in enumerate(systems):
            values = [row[metric] for key, data in structures.items() if key.startswith(system + "/") for row in data["rows"]]
            if values:
                ax.boxplot([values], positions=[i], widths=.5, whis=(0, 100), showfliers=False)
                ax.text(i, .96, f"n={len(values)} rows", transform=ax.get_xaxis_transform(), ha="center", fontsize=9)
        ax.set(title=title, xlabel="System; rows nested within successful drafts", ylabel="Provisional score (1-10)" if metric == "severity" else "Provisional RPN (S × O × D)")
        ax.set_xticks(range(5), list("ABCDE"))
        save(fig, name, "Boxes summarize generated rows only: median, quartiles and full range, not confidence intervals. Ratings remain unreviewed; rows are not independent engineering cases.")
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    for ax, system in zip(axes.flat, SYSTEMS):
        data = next((v for k, v in structures.items() if k.startswith(system + "/")), None)
        if data:
            # Plot literal generated labels, avoiding an unvalidated semantic coverage crosswalk.
            pairs = sorted(data["component_counts"].items(), key=lambda x: x[1], reverse=True)[:15]
            ax.barh([textwrap.shorten(k, width=35) for k, _ in pairs][::-1], [v for _, v in pairs][::-1])
            ax.set_title(f"{system}: top 15 literal labels; {data['row_count']} rows total")
        else:
            # Identify failed systems explicitly even when there are no component rows.
            ax.set_title(f"{system}: one failed attempt; no worksheet")
            ax.text(.5, .5, "No successful FMEA", ha="center", transform=ax.transAxes)
        ax.set(xlabel="Generated rows per component label", ylabel="Literal component label")
        ax.tick_params(labelsize=8)
    fig.tight_layout()
    save(fig, "07_components_vs_modes", "Literal labels and row counts are objective. Input-inventory candidate matches and possible omissions appear in CSV/Markdown and require human adjudication; no mode-coverage denominator exists.")
    return captions


def evaluate(folder, baseline):
    """Integrate existing System A with exactly four B-E receipts; never call a provider."""
    folder, baseline = Path(folder), Path(baseline)
    progress = Progress(folder)
    if progress.state["completed_request_count"] != 4:
        raise ValueError("Four confirmed attempts are required before final evaluation")
    progress.update(phase="offline evaluation", active_system=None, latest_event="Validating outputs and comparing A-E; no further requests authorized")
    output = folder / "analysis"
    output.mkdir(exist_ok=False)
    assumptions = read_json(ROOT / "analysis/financial_impact/assumptions.json")
    attempts = import_attempts(baseline / "manifest.json", assumptions)
    structures, receipt_paths = {}, []
    original = read_json(baseline / "manifest.json")
    for run in original["runs"]:
        if run["status"] == "success":
            structures[f"system_A/{run['run_number']}"] = structure(baseline / run["csv_file"], "system_A")
    for system in SYSTEMS:
        receipt = folder / system / f"{system}_v2.0_run01_execution.json"
        receipt_paths.append(receipt)
        record = import_attempts(receipt, assumptions)[0]
        record["failure_classification"] = read_json(receipt).get("failure_classification")
        attempts.append(record)
        if record["status"] == "success":
            structures[f"{system}/1"] = structure(folder / system / f"{system}_v2.0_run01.csv", system)
    # Preserve attempt-level failures and unknown costs in the execution dataset.
    fields = ["system_id", "attempt_id", "status", "failure_type", "duration_seconds", "api_request_seconds",
              "parsing_validation_seconds", "row_count", "cost_usd", "cost_basis", "billing_uncertain"]
    write_csv(output / "generation_summary.csv", fields, [{k: a[k] for k in fields} for a in attempts])
    comparison, review = [], ["# Preliminary engineering review", "", "Not independent technical validation. No reference FMEA or ground-truth worksheet was read.",
        "Lexical component matches are candidates, not validated coverage; shared words can overmatch similar parts.", ""]
    for system in ["system_" + letter for letter in "ABCDE"]:
        records = [a for a in attempts if a["system_id"] == system]
        success = [a for a in records if a["status"] == "success"]
        known = sum(a["cost_usd"] for a in records if a["cost_usd"] is not None)
        unknown = sum(a["cost_usd"] is None for a in records)
        duration = [a["duration_seconds"] for a in records if a["duration_seconds"] is not None]
        priced_successes = [a["cost_usd"] for a in success if a["cost_usd"] is not None]
        row = {"system_id": system, "attempts": len(records), "successes": len(success), "failures": len(records)-len(success),
            "success_rate": len(success)/len(records), "mean_seconds": statistics.mean(duration), "median_seconds": statistics.median(duration),
            "min_seconds": min(duration), "max_seconds": max(duration), "known_token_estimate_usd": known,
            "unknown_billing_attempts": unknown, "total_api_expense_usd": None if unknown else known,
            "cost_per_successful_generation_usd": known/len(success) if success and not unknown else None,
            "known_success_response_cost_mean_usd": statistics.mean(priced_successes) if priced_successes else None,
            "failure_types": json.dumps(dict(Counter(a["failure_type"] for a in records if a["status"] != "success"))),
            "schema_validation_failures": sum(a.get("failure_classification") == "validation_failure" for a in records),
            "known_input_tokens": sum(a["usage"].get("prompt_token_count", 0) or 0 for a in records if a["usage"]),
            "known_output_tokens": sum(a["usage"].get("candidates_token_count", 0) or 0 for a in records if a["usage"]),
            "known_thinking_tokens": sum(a["usage"].get("thoughts_token_count", 0) or 0 for a in records if a["usage"])}
        comparison.append(row)
        review.extend([f"## {system}", "", f"Observed attempts: {len(records)}; successful generations: {len(success)}; failures: {len(records)-len(success)}."])
        for key, data in structures.items():
            if not key.startswith(system + "/"):
                continue
            review.extend([f"### Draft {key}", f"Objective checks: {data['row_count']} rows; {data['distinct_components']} literal component labels; "
                f"0 missing required fields; 0 schema errors; {data['exact_duplicate_triples']} exact duplicate component/mode/cause triples; RPN arithmetic verified.",
                f"Input inventory: {len(data['inventory'])} listed component categories; {sum(i['stated_quantity'] for i in data['inventory'])} stated unit/category instances. "
                "Some package categories intentionally aggregate circuits or operating modes; these counts are not failure-mode coverage.",
                "Potential omission/unit-expansion candidates (lexical check; inspect wording before concluding omission):"])
            review.extend("- " + i["inventory_component"] + f": quantity {i['stated_quantity']}, candidate labels {i['candidate_labels']}"
                          for i in data["inventory"] if i["needs_omission_or_unit_review"])
            review.extend([f"Grouped-unit label candidates: {data['grouped_unit_candidates']}",
                f"Labels with only one generated row: {len(data['single_mode_component_labels'])}; review for underrepresented modes, not proven missing modes.",
                "Subjective review still required: trace architectural dependencies and credible effects; reconcile common design facts with system-specific operating premises; "
                "check detection claims against stated indications, apportion occurrence by mode, inspect unusual supplied rates, confirm severity premises, "
                "and distinguish proposed actions from existing provisions. All S/O/D/RPN values remain provisional.", ""])
    write_csv(output / "system_comparison.csv", list(comparison[0]), comparison)
    # Store detailed structural findings as ignored review evidence, not as reference answers.
    atomic(output / "structure_metrics.json", structures)
    atomic(output / "engineering_review.md", "\n".join(review))
    captions = make_figures(attempts, structures, output / "figures")
    atomic(output / "figure_captions.json", captions)
    atomic(folder / "CAMPAIGN_SUMMARY.md", "# Four-request B-E pilot\n\nAuthorization exhausted: four new requests, no retries or replacements.\n\n"
        + "\n".join(f"- {r['system_id']}: {r['successes']}/{r['attempts']} successful, mean {r['mean_seconds']:.2f} s, known estimate USD {r['known_token_estimate_usd']:.6f}, unknown bills {r['unknown_billing_attempts']}" for r in comparison)
        + "\n\nA is a historical five-attempt pilot; B-E each have one observation. Do not pool systems to claim repeatability. "
          "No engineering acceptance, manual labor, AI review labor, avoided-accident value or empirical financial savings is established. "
          "A further 16-generation campaign requires new explicit authorization.\n")
    progress.update(phase="evaluation_complete", latest_event="CSV/schema/RPN checks and descriptive figures complete; no additional generation authorized")
    return attempts, receipt_paths, comparison


def package(folder):
    """Freeze non-secret campaign outputs into a review ZIP without overwriting earlier packages."""
    folder = Path(folder)
    hashes = {str(p.relative_to(folder)).replace('\\', '/'): sha256(p) for p in sorted(folder.rglob("*"))
              if p.is_file() and not p.name.endswith(".lock") and p.name not in {"checksums.json", "live.log", "errors.log"}}
    with (folder / "checksums.json").open("x", encoding="utf-8") as stream:
        json.dump(hashes, stream, indent=2)
    archive = folder.parent / (folder.name + "-review.zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as stream:
        for name in [*hashes, "checksums.json"]:
            stream.write(folder / name, folder.name + "/" + name)
    return archive


if __name__ == "__main__":
    # A separate explicit offline invocation cannot accidentally dispatch another generation.
    evaluate(Path(sys.argv[1]), ROOT / "results/single-system-replicates/system_A/20261101T163923Z-system-a-five")
