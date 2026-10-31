"""Descriptive research reporting; no manufactured scores, significance or capability."""
import csv
import io
from pathlib import Path
import statistics

from .export import safe_cell, verify_bundle
from .integrity import load_json
from .research import write_record


def collect(output):
    output = Path(output)
    rows = []
    for directory in sorted((output / "runs").glob("*")):
        if not directory.is_dir():
            continue
        state = load_json(directory / "state.json") if (directory / "state.json").exists() else {"state": "uncertain"}
        metrics = load_json(directory / "metrics.json") if (directory / "metrics.json").exists() else {}
        error = state.get("error", "")
        status = state["state"]
        if status == "success":
            try:
                draft = verify_bundle(directory / "bundle")
                if draft.artifact_id != state.get("artifact_id") or metrics.get("artifact_id") != draft.artifact_id or draft.metadata.get("research_execution_sha256") != state.get("execution_sha256"):
                    raise ValueError("Execution/bundle/evaluation identities differ")
            except (ValueError, OSError, KeyError, TypeError) as failure:
                status, error = "integrity_failed", str(failure)
        usage = state.get("usage") or {}
        usable = status == "success"
        rows.append({"job_id": state.get("job_id", directory.name), "system_id": state.get("system_id"),
                     "condition": state.get("condition"), "repetition": state.get("repetition"), "status": status,
                     "data_kind": state.get("data_kind"), "input_classification": state.get("classification"),
                     "provider": state.get("settings", {}).get("provider"), "requested_model": state.get("settings", {}).get("model"),
                     "actual_model": state.get("actual_model"), "profile_id": state.get("profile_id"), "profile_version": state.get("profile_version"),
                     "prompt_version": state.get("prompt_version"), "input_sha256": state.get("input_sha256"), "prompt_sha256": state.get("prompt_sha256"),
                     "guidance_sha256": state.get("guidance_sha256"), "generation_seconds": state.get("generation_seconds"),
                     "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                     "structural_completeness_pct": metrics.get("structural_completeness_pct") if usable else None,
                     "missed_failure_modes_pct": metrics.get("missed_failure_modes_pct") if usable else None,
                     "reference_mode_count": metrics.get("reference_mode_count") if usable else None,
                     "coverage_status": metrics.get("coverage_status"), "generated_failure_modes": metrics.get("generated_failure_modes"),
                     "validation_error_count": metrics.get("validation_error_count", 0) + (1 if status == "integrity_failed" else 0),
                     "unresolved_review_flag_count": metrics.get("unresolved_review_flag_count"), "error": error})
    return rows


def _csv(path, rows, columns=None):
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: safe_cell(v) for k, v in row.items()})


def describe(values):
    return {"n": len(values), "mean": statistics.mean(values) if values else None,
            "sd": statistics.stdev(values) if len(values) > 1 else None,
            "median": statistics.median(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None}


def summarize(output, destination, plots=True):
    output, destination = Path(output), Path(destination)
    plan = load_json(output / "plan.json")
    rows = collect(output)
    if not rows:
        raise ValueError("No attempted generations to summarize")
    destination.mkdir(parents=True)  # never replace an existing report
    _csv(destination / "experiment-results.csv", rows)
    statistics_rows, grouped = [], []
    measures = ("structural_completeness_pct", "missed_failure_modes_pct", "generated_failure_modes", "generation_seconds")
    for condition in ("baseline", "improved"):
        successful = [r for r in rows if r["condition"] == condition and r["status"] == "success"]
        for metric in measures:
            values = [r[metric] for r in successful if isinstance(r.get(metric), (int, float))]
            statistics_rows.append({"condition": condition, "metric": metric, **describe(values)})
        for system in plan["systems"]:
            selected = [r for r in successful if r["system_id"] == system["system_id"]]
            grouped.append({"system_id": system["system_id"], "condition": condition, "successful_generations": len(selected),
                            **{metric: describe([r[metric] for r in selected if isinstance(r.get(metric), (int, float))])["mean"] for metric in measures}})
    _csv(destination / "descriptive-statistics.csv", statistics_rows)
    _csv(destination / "system-condition-means.csv", grouped)
    warnings = []
    if plots:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np
            for metric, title, ylabel in (("structural_completeness_pct", "Structural completeness", "Populated core content cells (%)"),
                                          ("missed_failure_modes_pct", "Reference failure-mode coverage", "Missed reviewed reference modes (%)"),
                                          ("generated_failure_modes", "Generated failure modes", "Candidate modes per FMEA")):
                fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
                available = any(isinstance(r.get(metric), (int, float)) for r in grouped)
                if available:
                    x = np.arange(len(plan["systems"]))
                    for offset, condition, color in ((-.18, "baseline", "#355c7d"), (.18, "improved", "#c06c3b")):
                        values = [next(r[metric] for r in grouped if r["system_id"] == s["system_id"] and r["condition"] == condition) for s in plan["systems"]]
                        ax.bar(x + offset, [v if v is not None else float("nan") for v in values], .34, label=condition, color=color)
                    ax.set_xticks(x, [s["system_id"] for s in plan["systems"]], rotation=15, ha="right")
                    ax.set_ylabel(ylabel)
                    ax.legend()
                    if metric.endswith("pct"):
                        ax.set_ylim(0, 100)
                else:
                    ax.text(.5, .5, "No reviewed reference coverage available\nNo numeric coverage result is claimed", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
                kind = "OFFLINE MOCK REHEARSAL — " if plan["provider"] == "mock" else "Preliminary research — "
                ax.set_title(kind + title)
                fig.savefig(destination / (metric + ".png"), dpi=160)
                fig.savefig(destination / (metric + ".svg"))
                plt.close(fig)
        except ImportError:
            warnings.append("matplotlib/numpy unavailable: CSVs and report generated; plots not generated. Install the analysis extra.")
    successful = [r for r in rows if r["status"] == "success"]
    title = "Offline pipeline rehearsal — not real LLM research results" if plan["provider"] == "mock" else "Preliminary AI-assisted FMEA findings"
    lines = [f"# {title}", "", f"Planned: {plan['total_generations']}; attempted: {len(rows)}; successful: {len(successful)}; failed/uncertain: {len(rows)-len(successful)}.",
             f"Systems: {len(plan['systems'])}. {plan['sample_note']}. Conditions: baseline versus improved. Planned repetitions per system/condition: {plan['repetitions']}.",
             f"Requested provider/model: {plan['provider']} / {plan['model']}. Actual model identities: {sorted({r['actual_model'] for r in successful if r['actual_model']})}.", "",
             "## Methods", "", "The baseline uses minimal FMEA instructions; improved adds the selected methodology workflow and allowlisted ASQ/NASA/team-policy guidance. The same systems, requested model, token cap and sampling settings are used in both conditions. Pair order is randomized with a frozen seed. Every sheet is one observation; repeats are nested within systems.",
             "", "Structural completeness is the percentage of eight core row fields containing substantive text/list content. Explicit unknowns count as missing content; schema validity is a separate measure. Controls/ratings are excluded from this denominator because current controls need evidence and selected profiles are unrated. Completeness does not establish correctness or safety.",
             "", "Missed-mode percentage is calculated only for explicitly reviewed eligible reference modes using normalized exact item/mode matching or reviewed aliases, with one-to-one matching. It is lexical coverage, not a semantic expert judgment. No LLM judge is used.", "", "## Descriptive results", "",
             "| Condition | Measure | n | Mean | SD |", "|---|---|---:|---:|---:|"]
    def number(value):
        return "unavailable" if value is None else f"{value:.2f}"
    for row in statistics_rows:
        lines.append(f"| {row['condition']} | {row['metric']} | {row['n']} | {number(row['mean'])} | {number(row['sd'])} |")
    lines += ["", "## Interpretation and limitations", ""]
    if plan["provider"] == "mock":
        lines.append("These are actual outputs of the deterministic mock, used solely to exercise data collection, scoring and analysis. They provide no evidence that a real model or guidance improves FMEA quality. The mock does not respond to the guidance treatment.")
    else:
        means = {r["condition"]: r["mean"] for r in statistics_rows if r["metric"] == "structural_completeness_pct"}
        if all(means.get(k) is not None for k in ("baseline", "improved")):
            lines.append(f"Observed improved-minus-baseline completeness difference: {means['improved']-means['baseline']:.2f} percentage points. This is descriptive and may reflect unsupported detail; engineering correctness has not been established.")
    if not any(r.get("missed_failure_modes_pct") is not None for r in successful):
        lines.append("No reviewed reference set supported numerical missed-mode estimates. Coverage is unavailable, not zero. Unreviewed NASA candidates are not ground truth.")
    if len({r["actual_model"] for r in successful if r["actual_model"]}) > 1:
        lines.append("Actual model identity varied: do not treat these data as a controlled same-model comparison.")
    lines += ["The scenarios are author-created demonstrations, not validated operational systems. This is a small convenience sample. No statistical significance, Cpk, capability, certification or autonomous risk acceptance is claimed. Model facts, causes/effects/actions and unsupported controls require engineering review. Token counts are reported only where returned by the provider; no monetary cost is inferred.",
              "", "Next iterations: inspect the real smoke draft, calibrate a reviewed reference set and alias rubric independently, review unsupported/duplicate modes, and then increase replications while freezing inputs and settings.", "", "## Execution failures", ""]
    lines.extend([f"- {r['job_id']}: {r['status']} — {r['error']}" for r in rows if r["status"] != "success"] or ["None recorded."])
    lines.extend(["", *warnings])
    (destination / "preliminary-findings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {"attempted": len(rows), "successful": len(successful), "failed_or_uncertain": len(rows)-len(successful),
               "data_kind": "offline_mock_rehearsal" if plan["provider"] == "mock" else "real_llm_generation", "warnings": warnings, "output": str(destination)}
    write_record(destination / "analysis-summary.json", summary)
    return summary
