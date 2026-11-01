"""Report-ready figures; missing measurements are displayed as missing, not zero."""
from pathlib import Path
import textwrap
import matplotlib

# A noninteractive backend supports CI and report generation without desktop windows.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def figures(metrics, output):
    """Write six 300-dpi PNGs with units, evidence labels, sample sizes and captions."""
    output = Path(output)
    output.mkdir(exist_ok=False)
    captions = {}
    n = metrics["observed"]["n_attempts"]
    matched = metrics["uncertainty"]["n_matched_cases"]
    source = f"Execution metadata and supplied logs; attempts n={n}; matched accepted cases n={matched}. USD at configured tariff dates."

    def canvas(title, xlabel, ylabel):
        # Leave a footer for the source and explanation, avoiding clipped report captions.
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
        fig.subplots_adjust(bottom=.28)
        return fig, ax

    def missing(ax, message):
        # A labeled panel avoids the false visual claim of a zero-dollar observation.
        ax.text(.5, .5, textwrap.fill(message, 65), transform=ax.transAxes,
                ha="center", va="center", fontsize=12, bbox={"facecolor": "#f3f4f6", "edgecolor": "#888"})
        ax.set_xticks([])
        ax.set_yticks([])

    def save(fig, name, caption):
        fig.text(.07, .06, textwrap.fill(source + " " + caption, 125), fontsize=9)
        fig.savefig(output / (name + ".png"), dpi=300)
        plt.close(fig)
        captions[name] = caption

    rows = metrics["accepted_costs"]
    fig, ax = canvas("Manual versus AI: cost per accepted FMEA", "Development condition", "USD / engineering-accepted FMEA")
    available = [r for r in rows if r["cost_per_accepted_fmea_usd"] is not None]
    interval = metrics["uncertainty"]
    if interval["status"] == "estimable":
        # Cost bars and error bounds come from the same paired cluster resamples.
        means = [interval["manual_mean_usd"], interval["ai_mean_usd"]]
        bounds = [interval["manual_ci95_usd"], interval["ai_ci95_usd"]]
        errors = np.array([[mean - lo for mean, (lo, hi) in zip(means, bounds)],
                           [hi - mean for mean, (lo, hi) in zip(means, bounds)]])
        ax.bar(["Manual matched cases", "AI matched cases"], means, yerr=np.maximum(0, errors), capsize=7)
    elif available:
        labels = [r["method"] + " / " + r["system_id"] + " / " + r["skill_version"] for r in available]
        ax.bar(labels, [r["cost_per_accepted_fmea_usd"] for r in available], color="#336b87")
        ax.tick_params(axis="x", rotation=20)
    else:
        missing(ax, "Not estimable: manual labor, AI review/correction labor and independent engineering acceptance are missing.")
    save(fig, "01_before_after_cost", "Preliminary cost comparison; 95% paired cluster confidence bounds appear only when estimable. Cohort bars without bounds have no separately estimable confidence interval.")

    fig, ax = canvas("Engineering labor by stage", "Work stage", "Active engineering hours / accepted FMEA")
    stage_rows = [(r, stage, hours) for r in rows if r["hours_per_accepted_fmea"] is not None
                  for stage, hours in r["stage_hours"].items()]
    if stage_rows:
        ax.bar([r["method"] + ":" + stage for r, stage, _ in stage_rows],
               [hours / r["n_accepted"] for r, _, hours in stage_rows], color="#527a51")
        ax.tick_params(axis="x", rotation=30)
    else:
        missing(ax, "Active labor has not been measured. Generation elapsed time is not substituted for paid engineering labor.")
    save(fig, "02_labor_breakdown", "Record development, supervision, review, rework, peer review and approval separately; exclude passive waiting from labor cost.")

    fig, ax = canvas("Savings distribution: paired cluster bootstrap", "Manual minus AI cost (USD / accepted FMEA)", "Bootstrap replicates (count)")
    draws = metrics["uncertainty"].get("draws")
    if draws is not None:
        ax.hist(draws, bins=40, color="#336b87")
        ax.axvline(0, color="#a33", linestyle="--", label="Zero savings")
        ax.legend()
    else:
        missing(ax, "Empirical confidence interval not estimable: insufficient independently clustered, measured, quality-matched cases.")
        ax.axvline(0, color="#a33", linestyle="--", alpha=.3)
    save(fig, "03_savings_bootstrap", "95% percentile confidence interval resamples connected system/reviewer clusters while preserving pairs. Three generations from one system are not three systems.")

    fig, ax = canvas("Cost sensitivity: one-at-a-time tornado", "Change in net savings (USD / accepted FMEA)", "Assumption")
    sensitivity = metrics.get("sensitivity", [])
    if sensitivity:
        ordered = sorted(sensitivity, key=lambda r: r["high"] - r["low"])
        positions = np.arange(len(ordered))
        ax.barh(positions, [r["high"] - r["low"] for r in ordered], left=[r["low"] for r in ordered])
        ax.set_yticks(positions, [r["name"] for r in ordered])
        ax.axvline(0, color="#a33", linestyle="--")
    else:
        missing(ax, "No user-specified labor/rework/volume distributions. A numerical tornado ranking would require invented assumptions.")
    save(fig, "04_cost_sensitivity", "Scenario-only when distributions are supplied; otherwise unavailable. Loaded-rate sensitivity alone is USD per active hour saved, not a measured labor saving.")

    fig, ax = canvas("Break-even: annual accepted FMEA workload", "Engineering-accepted FMEAs / year", "Total annual cost (USD)")
    scenario = metrics.get("scenario_baseline")
    if scenario:
        volumes = np.arange(0, max(2, int(scenario["annual_volume"] * 2)) + 1)
        ax.plot(volumes, scenario["manual_unit_usd"] * volumes, label="Manual scenario")
        ax.plot(volumes, scenario["ai_unit_usd"] * volumes + scenario["fixed_usd"], label="AI + development/maintenance scenario")
        ax.legend()
    else:
        missing(ax, "Break-even unavailable: accepted unit costs, skill-development expense, maintenance and annual workload are not measured or specified.")
    save(fig, "05_break_even", "Fixed skill investment and annual maintenance must be explicit. If AI unit cost is higher, positive fixed investment has no finite break-even.")

    fig, ax = canvas("Skill-version financial comparison", "Separate skill / system / workflow condition", "USD / engineering-accepted FMEA")
    ai_rows = [r for r in available if r["method"] == "ai_assisted"]
    if ai_rows:
        ax.bar([r["skill_version"] + ":" + r["system_id"] + ":" + r["workflow"] for r in ai_rows],
               [r["cost_per_accepted_fmea_usd"] for r in ai_rows], color="#756c91")
        ax.tick_params(axis="x", rotation=20)
    else:
        versions = sorted({a["skill_version"] for a in metrics["attempts"]})
        missing(ax, "Observed versions: " + ", ".join(versions) + ". No accepted-cost observations. Future v2.1 data are not fabricated or pooled with v2.0.")
    save(fig, "06_skill_versions", "Keep skill hashes, model settings and canonical/standalone conditions separate. No version improvement is established by this pilot.")

    # Add an observed-data panel so the preliminary report is useful despite missing labor.
    fig, ax = canvas("Observed generation attempts and known API estimates", "Attempt number (sequential, not independent systems)", "Total elapsed seconds")
    attempts = metrics["attempts"]
    positions = np.arange(1, len(attempts) + 1)
    for i, attempt in zip(positions, attempts):
        duration = attempt["duration_seconds"]
        if duration is not None:
            ax.bar(i, duration, color="#336b87" if attempt["status"] == "success" else "#a34f43")
            cost = attempt["cost_usd"]
            label = f"USD {cost:.5f} estimate" if cost is not None else "Billing unknown"
            ax.annotate(label, (i, duration), ha="center", va="bottom", fontsize=9)
    ax.set_xticks(positions)
    ax.margins(y=.2)
    save(fig, "07_observed_generation", "Observed elapsed durations and tariff estimates only. Red bars are failed/uncertain attempts; unobserved failed billing remains unknown. No labor or acceptance claim.")
    return captions
