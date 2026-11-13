"""Immutable report packages and a rebuildable aggregate index; no provider imports."""
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import uuid
from . import ANALYSIS_VERSION
from .cost_model import comparison, loaded_rate
from .data_schema import read_json
from .ingest import import_attempts, read_log, sha256
from .metrics import costs, matched_pairs, observed_summary
from .uncertainty import paired_bootstrap, simulate
from .visualizations import figures

CONFIG = Path(__file__).parent
ROOT = CONFIG.parents[1]


def write_json(path, value):
    """Write finite UTF-8 JSON once; package contents never replace older reports."""
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def scenario_details(spec):
    """Compute a one-at-a-time tornado from explicit distribution supports, not observations."""
    if spec is None:
        return None, []
    distributions = spec["distributions"]
    def center(d):
        # Triangular modes and uniform midpoints define the deterministic scenario baseline.
        return d["value"] if d["distribution"] == "constant" else d.get("mode", (d["low"] + d["high"]) / 2)
    values = {k: center(d) for k, d in distributions.items()}
    def net(v):
        return (v["labor_rate"] * (v["manual_hours"] - v["ai_hours"]) -
                v["api_usd_per_attempt"] / v["success_probability"] -
                (v["development_usd"] + v["maintenance_usd"]) / v["annual_volume"])
    baseline = {"manual_unit_usd": values["labor_rate"] * values["manual_hours"],
                "ai_unit_usd": values["labor_rate"] * values["ai_hours"] + values["api_usd_per_attempt"] / values["success_probability"],
                "fixed_usd": values["development_usd"] + values["maintenance_usd"],
                "annual_volume": values["annual_volume"]}
    tornado = []
    for name, d in distributions.items():
        endpoints = [d["value"], d["value"]] if d["distribution"] == "constant" else [d["low"], d["high"]]
        if name in {"success_probability", "annual_volume"} and min(endpoints) <= 0:
            raise ValueError("Scenario support must exclude zero probability/volume")
        changes = [net({**values, name: endpoint}) - net(values) for endpoint in endpoints]
        tornado.append({"name": name, "low": min(changes), "high": max(changes)})
    return baseline, tornado


def narrative(metrics):
    """Return a 300-500-word preliminary working draft with unresolved measurements explicit."""
    o, rate = metrics["observed"], metrics["loaded_labor_rate_usd_per_hour"]
    # Values below are metadata-derived; no manual/review labor measurements are invented.
    # The default pilot draft is used only where its unresolved-measurement statements are true.
    if metrics["accepted_costs"]:
        return measured_narrative(metrics)
    wage = metrics["labor_assumption"]["wage_usd_per_hour"]
    tariff_text = "; ".join(f"{p['model']} {p['tier']}: USD {p['input_usd_per_million']}/million input and USD {p['output_including_thinking_usd_per_million']}/million output including thinking"
                            for p in metrics["pricing_assumptions"])
    text = f"""# Financial Impacts

**Preliminary analytical working draft; AI-assisted prose, not a student-authored submission.**

This analysis evaluates financial feasibility using cost per engineering-accepted FMEA as the intended outcome. The available pilot contains {o['n_attempts']} generation attempts, including {o['n_successful_generations']} successful drafts and {o['n_failed_or_uncertain_attempts']} failed or uncertain attempts. Generation success is not engineering acceptance. Consequently, neither the manual before-cost nor the AI-assisted after-cost per accepted FMEA is currently estimable. Missing observations include manual creation and approval time, AI preparation and supervision time, technical review, correction, peer review, and acceptance against equivalent scope and quality criteria.

The initial engineering wage assumption is USD {wage:.2f} per hour, based on national aerospace-engineer median pay for May 2025 (U.S. Bureau of Labor Statistics [BLS], 2026a). Private-industry compensation relative to wages supplies the benefits multiplier (BLS, 2026b). The selected loaded rate is USD {rate:.2f} per active hour, using the versioned calculation or explicit override. The national calculation is illustrative, not a Sigma Airlines company rate, and excludes unmeasured firm-specific overhead. An already burdened company rate replaces the calculation rather than receiving another benefits multiplier.

Configured tariffs are {tariff_text} (Google, 2026). Recorded usage produces a known token-estimated or invoiced subtotal of USD {o['known_token_estimate_or_invoice_subtotal_usd']:.6f}. Billing remains unknown for {o['unknown_billing_attempts']} attempts; invoice evidence is required to establish actual total expenditure. The subtotal cannot be presented as the complete campaign cost while billing is unresolved. Recorded attempt durations sum to {o['total_attempt_elapsed_seconds']/60:.2f} minutes; elapsed waiting is not automatically charged as active engineering labor.

Fraser's financial example illustrates translating an appropriate outcome into money and examining sampling variation (Fraser, n.d.). Here, the intended primary method instead preserves matched manual/AI cases and resamples independent system/reviewer clusters. No empirical 95% confidence interval for savings is presently estimable: one system's repeated drafts are not independent engineering systems, and no measured, quality-matched manual/AI cost pairs exist. Assumption-driven Monte Carlo intervals, when explicitly configured, must be labeled simulation intervals rather than empirical confidence intervals.

The next measurement phase should record active, passive, review, rework, and approval time separately and reconcile failed-request billing. Until those data exist, absolute savings, percentage reduction, annual savings, maintenance-adjusted net savings, break-even workload, and engineering lead-time reduction remain unresolved. Negative savings must remain possible. No financial benefit from avoided accidents, safety improvement, or generated-row counts is claimed.
"""
    return text


def measured_narrative(metrics):
    """Describe populated cohorts without converting tariff estimates into measured invoices."""
    rows = metrics["accepted_costs"]
    available = [r for r in rows if r["cost_per_accepted_fmea_usd"] is not None]
    values = "; ".join(f"{r['method']} / {r['system_id']} / {r['skill_version']}: USD {r['cost_per_accepted_fmea_usd']:.2f}"
                       for r in available) or "No complete accepted-cost cohort is available"
    return ("# Financial Impacts\n\n**Preliminary analytical working draft; AI-assisted prose, not a student-authored submission.**\n\n"
        f"The supplied labor and quality logs contain {len(rows)} separate financial cohorts. Available costs per engineering-accepted FMEA are: {values}. "
        "These cohort summaries combine measured active labor with the stated labor-rate assumption and either invoiced or estimated generation expense. "
        "They are not all invoice-based company expenditures. Before and after comparisons require identical system input, scope, and independent quality criteria. "
        "Rejected work and failed-generation expenses are retained within their experimental workflow and allocated over accepted deliverables, rather than discarded.\n\n"
        f"The loaded engineering rate used in this execution is USD {metrics['loaded_labor_rate_usd_per_hour']:.2f} per active hour. "
        "The versioned assumptions identify whether this is the national illustrative wage-and-benefits calculation or an explicit burdened-rate override. "
        "National wage and compensation data provide a transparent starting point, not a measurement of the firm's fully allocated cost (BLS, 2026a, 2026b). "
        "Passive waiting remains distinct from active development, supervision, review, correction, peer review, and approval. "
        "Lead time is computed separately only when complete timestamp records exist.\n\n"
        "Provider prices are matched by model, tier, billing arrangement, and effective date (Google, 2026). Thinking tokens are included once in the output charge. "
        "Invoices override estimates when supplied, and unknown usage or failed-request billing is never interpreted as a free call. "
        "A workflow with unresolved required expense or incomplete labor closure does not receive a numerical total accepted cost.\n\n"
        "Fraser's financial example motivates explicit monetary quantities and uncertainty evaluation (Fraser, n.d.). This implementation keeps case pairs together "
        "and merges shared systems and reviewers into dependency clusters before resampling. Empirical intervals require sufficient independent clusters and "
        "measured matched inputs; estimated-cost comparisons remain labeled estimates. Monte Carlo results instead depend on the explicitly specified distributions "
        "and represent simulation uncertainty, not sampling confidence. All condition-specific sample sizes, methods, seed, and intervals appear in metrics.json.\n\n"
        "The preliminary comparison permits negative savings. Annual net savings and break-even workload additionally require explicit development, maintenance, "
        "and volume assumptions; unmeasured fixed expenses must not silently become zero. No economic value is assigned to avoided accidents, safety improvements, "
        "or generated-mode counts. Further engineering review, invoice reconciliation, and broader independently sampled systems are required before any validated "
        "financial conclusion or claim of improved skill-version performance.\n")


def create_report(manifests, output_root, assumptions_path=None, labor_path=None, quality_path=None,
                  invoices_path=None, expenses_path=None, analysis_id=None, sources_path=None,
                  tier="standard_paid", billing_arrangement="pay_as_you_go", scenario_path=None):
    """Create one immutable preliminary package; return its path and structured metrics."""
    assumptions_path = Path(assumptions_path or CONFIG / "assumptions.json")
    sources_path = Path(sources_path or CONFIG / "sources.json")
    assumptions, sources = read_json(assumptions_path), read_json(sources_path)
    if scenario_path:
        # Explicit scenario inputs reuse the existing model; source assumptions remain immutable.
        assumptions={**assumptions,"scenario":read_json(scenario_path)}
    # Analysis identity is unique; callers can supply a fixed ID for an auditable rerun attempt.
    created = datetime.now(timezone.utc).isoformat()
    analysis_id = analysis_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    if not analysis_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in analysis_id):
        raise ValueError("Invalid analysis ID")
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / analysis_id
    if target.exists():
        raise FileExistsError(target)
    # Reserve the package name before computation; incomplete runs are never mistaken for reports.
    lock = root / ("." + analysis_id + ".lock")
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(created)
    staging = root / ("." + analysis_id + ".staging")
    try:
        staging.mkdir(exist_ok=False)
        invoices = read_json(invoices_path) if invoices_path else {}
        attempts = []
        for path in manifests:
            attempts.extend(import_attempts(path, assumptions, tier, billing_arrangement, invoices))
        if len({(a["experiment_id"], a["attempt_id"]) for a in attempts}) != len(attempts):
            raise ValueError("Duplicate imported attempts")
        labor, quality = read_log(labor_path, "labor"), read_log(quality_path, "quality")
        expenses = read_json(expenses_path) if expenses_path else []
        rate = loaded_rate(assumptions["labor"])
        accepted, cases = costs(attempts, labor, quality, rate, expenses)
        pairs = matched_pairs(cases)
        # Separate every version/hash/model/settings/workflow condition before resampling.
        strata = {}
        for pair in pairs:
            identity = tuple(pair[k] for k in ("skill_version", "skill_hash", "workflow", "model", "configuration_id"))
            strata.setdefault(identity, []).append(pair)
        intervals = {" | ".join(k): paired_bootstrap([p for p in v if p["basis"] == "measured"],
            assumptions["iterations"], assumptions["seed"], assumptions["minimum_independent_clusters"])
            for k, v in strata.items()}
        unavailable = paired_bootstrap([], assumptions["iterations"], assumptions["seed"], assumptions["minimum_independent_clusters"])
        interval = next(iter(intervals.values())) if len(intervals) == 1 else unavailable
        simulation = simulate(assumptions.get("scenario"), assumptions["iterations"], assumptions["seed"])
        baseline, sensitivity = scenario_details(assumptions.get("scenario"))
        comparisons = {}
        for identity, group in strata.items():
            # Keep before/after differences within the same matched condition; never average versions together.
            value = comparison(sum(p["manual_usd"] for p in group) / len(group),
                               sum(p["ai_usd"] for p in group) / len(group))
            value.update(break_even_fmeas=None, net_annual_savings_usd=None, net_savings_per_fmea_usd=None,
                         status="estimated unless all input expenses are invoiced",
                         lead_time_reduction_hours=(sum(p["lead_time_reduction_hours"] for p in group) / len(group)
                             if all(p["lead_time_reduction_hours"] is not None for p in group) else None))
            workload = assumptions.get("annual_workload")
            if workload:
                value.update(comparison(sum(p["manual_usd"] for p in group) / len(group),
                    sum(p["ai_usd"] for p in group) / len(group), workload["development_usd"],
                    workload["maintenance_usd"], workload["annual_fmeas"]))
            comparisons[" | ".join(identity)] = value
        metrics = {"observed": observed_summary(attempts), "attempts": attempts,
                   "labor_assumption": assumptions["labor"], "pricing_assumptions": assumptions["pricing"],
                   "loaded_labor_rate_usd_per_hour": rate, "accepted_costs": accepted,
                   "uncertainty": interval, "uncertainty_by_condition": intervals,
                   "matched_case_count_including_estimated_pairs": len(pairs), "simulation": simulation,
                   "scenario_baseline": baseline, "sensitivity": sensitivity,
                   "comparison": next(iter(comparisons.values())) if len(comparisons) == 1 else comparison(None, None),
                   "comparisons_by_condition": comparisons,
                   "engineering_lead_time_reduction_hours": (next(iter(comparisons.values())).get("lead_time_reduction_hours")
                                                             if len(comparisons) == 1 else None),
                   "missing_measurements": ["manual development/review/approval", "AI preparation/supervision/review/rework",
                                            "independent acceptance", "failed-call invoices", "skill maintenance", "annual workload"]}
        audit=data_audit(attempts,labor,quality,len(manifests))
        metrics["data_audit"]=audit
        print("FINANCIAL DATA AUDIT (before rendering): " + json.dumps(audit,sort_keys=True),flush=True)
        captions = figures(metrics, staging / "figures")
        write_json(staging / "metrics.json", metrics)
        # Only aggregates and non-sensitive provenance are written; private notes/identities stay out.
        fields = ["method", "system_id", "workflow", "skill_version", "n_accepted", "n_quality_decisions",
                  "cost_per_accepted_fmea_usd", "hours_per_accepted_fmea", "quality_adjusted_acceptance_rate",
                  "absolute_savings_usd", "percentage_reduction", "net_savings_per_fmea_usd",
                  "net_annual_savings_usd", "break_even_fmeas", "missingness"]
        with (staging / "financial_summary.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            if accepted:
                for row in accepted:
                    # Attach only the matching AI-condition comparison; do not pool manual/versions.
                    key = " | ".join(row[k] for k in ("skill_version", "skill_hash", "workflow", "model", "configuration_id"))
                    writer.writerow({**row, **(comparisons.get(key, {}) if row["method"] == "ai_assisted" else {})})
            else:
                writer.writerows({"method": method, "system_id": ";".join(sorted({a["system_id"] for a in attempts})),
                    "workflow": "not_measured" if method == "manual" else ";".join(sorted({a["workflow"] for a in attempts})),
                    "skill_version": "not_applicable" if method == "manual" else ";".join(sorted({a["skill_version"] for a in attempts})),
                    "missingness": "Engineering acceptance and labor unmeasured"} for method in ("manual", "ai_assisted"))
        (staging / "Financial_Impacts.md").write_text(narrative(metrics), encoding="utf-8")
        bibliography = "\n".join(f"- {s['author']} ({s['period']}). {s['title']}. {s['url']} (accessed {s['accessed']})." for s in sources["sources"])
        explanation = (f"# Assumptions and sources\n\nAssumptions version: {assumptions['version']}.\n"
            f"Loaded labor rate: USD {rate:.6f}/active hour; illustrative, not measured company cost.\n\n"
            "BLS (2026a) = Aerospace Engineers; BLS (2026b) = ECEC; Google (2026) = pricing; Fraser (n.d.) = teaching example.\n\n"
            "No empirical accepted-cost/savings CI exists without measured matched cases. Unknown failed billing is not zero. "
            "Scenario distributions, if supplied, are assumptions and not the real project dataset.\n\n"
            "## Versioned assumptions snapshot\n\n```json\n" + json.dumps(assumptions, indent=2) + "\n```\n\n"
            "## References\n\n" + bibliography + "\n\n## Figure captions\n\n" +
            "\n".join(f"- {name}: {caption}" for name, caption in captions.items()))
        (staging / "assumptions_and_sources.md").write_text(explanation, encoding="utf-8")
        paths = [*map(Path, manifests), assumptions_path, sources_path, *[Path(p) for p in (
            labor_path, quality_path, invoices_path, expenses_path, scenario_path) if p]]
        manifest = {"analysis_id": analysis_id, "report_status": "preliminary", "created_at": created,
            "system_ids": sorted({a["system_id"] for a in attempts}),
            "skill_versions": sorted({a["skill_version"] for a in attempts}),
            "analysis_code_version": ANALYSIS_VERSION,
            "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "analysis_code_hashes": {p.name: sha256(p) for p in sorted(CONFIG.glob("*.py"))},
            "datasets": [{"identifier": p.name, "sha256": sha256(p)} for p in paths],
            "assumptions_version": assumptions["version"], "sources_version": sources["version"],
            "assumed_billing_tier": tier, "assumed_billing_arrangement": billing_arrangement,
            "sample_sizes": {"attempts": len(attempts), "systems": len({a["system_id"] for a in attempts}),
                             "successful_generations": metrics["observed"]["n_successful_generations"],
                             "quality_records": len(quality), "labor_records": len(labor), "matched_cases": len(pairs)},
            "statistical_method": "paired connected-cluster percentile bootstrap when estimable; explicit assumption simulation otherwise",
            "seed": assumptions["seed"], "iterations": assumptions["iterations"],
            "dependency_versions": {n: importlib.metadata.version(n) for n in ("pandas", "numpy", "scipy", "matplotlib")},
            "artifacts": {str(p.relative_to(staging)).replace('\\', '/'): sha256(p) for p in sorted(staging.rglob("*")) if p.is_file()}}
        write_json(staging / "manifest.json", manifest)
        # One directory rename publishes a completed package; the old target is never replaced.
        staging.rename(target)
    finally:
        # Failed staging is retained for inspection, while the reservation is released.
        lock.unlink(missing_ok=True)
    rebuild_index(root)
    return target, metrics


def rebuild_index(root):
    """Rebuild the mutable catalog from immutable completed report manifests."""
    root = Path(root)
    entries = []
    for path in sorted(root.glob("*/manifest.json")):
        if path.parent.name.startswith("."):
            continue
        manifest = read_json(path)
        entries.append({k: manifest[k] for k in ("analysis_id", "created_at", "report_status", "system_ids", "skill_versions", "git_commit")})
    # Index refreshes do not change any versioned package; a unique temp avoids concurrent clobbering.
    temporary = root / (".index-" + uuid.uuid4().hex + ".json")
    write_json(temporary, {"analyses": entries})
    temporary.replace(root / "index.json")


def data_audit(attempts,labor,quality,manifest_count):
    """Expose measured inputs and billing missingness before any financial chart is rendered."""
    usable=lambda r:bool(r.get("usage")) and all(r["usage"].get(k) is not None for k in ("prompt_token_count","candidates_token_count","thoughts_token_count"))
    return {"manifests_loaded":manifest_count,"unique_attempts":len(attempts),"systems":sorted({r["system_id"] for r in attempts}),
        "successful_generations":sum(r["status"]=="success" for r in attempts),"failed_generations":sum(r["status"]!="success" for r in attempts),
        "attempts_with_duration":sum(r["duration_seconds"] is not None for r in attempts),"attempts_with_usable_tokens":sum(usable(r) for r in attempts),
        "attempts_with_invoice_expense":sum(r["cost_basis"]=="invoice" for r in attempts),
        "attempts_with_estimated_expense":sum(r["cost_basis"].startswith("estimated") and r["cost_usd"] is not None for r in attempts),
        "attempts_with_unknown_actual_billing":sum(r["cost_basis"]!="invoice" for r in attempts),
        "attempts_without_priced_amount":sum(r["cost_usd"] is None for r in attempts),
        "manual_labor_observations":sum(r["method"]=="manual" for r in labor),"all_labor_observations":len(labor),
        "engineering_review_observations":len(quality),"independent_acceptance_decisions":sum(r["decision"] in ("accepted","rejected") and str(r["independent_review"]).lower()=="true" for r in quality)}
