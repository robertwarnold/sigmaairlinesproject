"""Build accepted-deliverable costs with explicit missingness and condition boundaries."""
from collections import defaultdict
from datetime import datetime
import statistics
from .cost_model import active_minutes, comparison
from .data_schema import IDENTITY, number


def condition(row):
    """Return the full financial cohort identity; manual and AI methods are separate."""
    return tuple(row[k] for k in (*IDENTITY, "method"))


def costs(attempts, labor, quality, rate, expenses=()):
    """Allocate failed/rejected overhead within each exact experimental workflow."""
    pools = defaultdict(lambda: {"labor": [], "quality": [], "attempts": [], "expenses": []})
    for row in labor:
        pools[condition(row)]["labor"].append(row)
    for row in quality:
        pools[condition(row)]["quality"].append(row)
    # Attempts link by immutable experiment and configuration identities, not just version labels.
    assigned = set()
    for key, pool in pools.items():
        identity = dict(zip((*IDENTITY, "method"), key))
        if identity["method"] == "ai_assisted":
            pool["attempts"] = [a for a in attempts if all(a.get(k) == identity[k] for k in IDENTITY
                                                         if k not in {"scope_id", "criteria_id"})]
            for attempt in pool["attempts"]:
                # Shared generation expense cannot be charged twice to incompatible acceptance scopes.
                attempt_key = (attempt["experiment_id"], attempt["attempt_id"])
                if attempt_key in assigned:
                    raise ValueError("An attempt maps to multiple financial pools; separate experiment IDs")
                assigned.add(attempt_key)
        pool["expenses"] = [e for e in expenses if condition(e) == key]
    rows, case_costs = [], []
    for key, pool in pools.items():
        identity = dict(zip((*IDENTITY, "method"), key))
        accepted = [q for q in pool["quality"] if q["decision"] == "accepted"]
        decisions = [q for q in pool["quality"] if q["decision"] in {"accepted", "rejected"}]
        pending = any(q["decision"] == "pending" for q in pool["quality"])
        labor_cases = {r["case_id"] for r in pool["labor"]}
        # Require a completed approval-stage labor record for every decided deliverable.
        closed = {r["case_id"] for r in pool["labor"] if r["stage"] == "approval" and r["approval_status"] in {"accepted", "rejected"}}
        complete = bool(decisions) and not pending and all(q["case_id"] in closed for q in decisions)
        complete = complete and labor_cases <= {q["case_id"] for q in decisions}
        hours = sum(active_minutes(r) for r in pool["labor"]) / 60
        passive = sum(r["passive_waiting_minutes"] for r in pool["labor"]) / 60
        generation = pool["attempts"]
        generation_known = sum(a["cost_usd"] for a in generation if a["cost_usd"] is not None)
        ai_complete = identity["method"] == "manual" or (bool(generation) and all(a["cost_usd"] is not None for a in generation))
        nonlabor = sum(number(e["usd"], "expense") for e in pool["expenses"])
        total = hours * rate + generation_known + nonlabor if complete and ai_complete else None
        n = len(accepted)
        row = {**identity, "n_accepted": n, "n_quality_decisions": len(decisions),
               "n_pending_quality": sum(q["decision"] == "pending" for q in pool["quality"]),
               "quality_adjusted_acceptance_rate": n / len(decisions) if decisions else None,
               "active_hours_recorded": hours, "passive_hours_recorded": passive,
               "hours_per_accepted_fmea": hours / n if complete and n else None,
               "known_generation_subtotal_usd": generation_known,
               "unknown_generation_cost_attempts": sum(a["cost_usd"] is None for a in generation),
               "skill_maintenance_expense_usd": sum(number(e["usd"], "maintenance expense") for e in pool["expenses"]
                                                     if e.get("cost_kind") == "skill_maintenance"),
               "cost_per_accepted_fmea_usd": total / n if total is not None and n else None,
               "cost_basis": "measured_labor_at_assumed_rate_plus_estimated_or_invoiced_expenses",
               "missingness": None if total is not None and n else "Requires closed labor, independent acceptance and complete attempt billing",
               "stage_hours": {stage: sum(active_minutes(r) for r in pool["labor"] if r["stage"] == stage) / 60
                               for stage in sorted({r["stage"] for r in pool["labor"]})}}
        rows.append(row)
        # Case-level costs include allocated failed/rejected work; do not pool accepted and rejected denominators.
        if total is not None and n:
            accepted_ids = {q["case_id"] for q in accepted}
            rejected_labor = sum(active_minutes(r) for r in pool["labor"] if r["case_id"] not in accepted_ids) / 60 * rate
            overhead = (rejected_labor + generation_known + nonlabor) / n
            for q in accepted:
                work = [r for r in pool["labor"] if r["case_id"] == q["case_id"]]
                endpoints = [(r["started_at"], r["finished_at"]) for r in work if r["started_at"]]
                case_costs.append({**identity, "case_id": q["case_id"],
                    "usd": sum(active_minutes(r) for r in work) / 60 * rate + overhead,
                    "reviewers": sorted({q["reviewer_id"], *[r["engineer_id"] for r in work]}),
                    "timestamps": endpoints,
                    "lead_time_hours": ((max(datetime.fromisoformat(b) for _, b in endpoints) -
                                          min(datetime.fromisoformat(a) for a, _ in endpoints)).total_seconds() / 3600
                                         if len(endpoints) == len(work) and endpoints else None),
                    # Only invoices permit an empirical cost claim; tariff estimates remain estimates.
                    "basis": "measured" if all(a["cost_basis"] == "invoice" for a in generation) else "estimated"})
    return rows, case_costs


def matched_pairs(cases):
    """Match accepted manual and AI cases only on equal input, scope and quality criteria."""
    pairs = []
    for ai in cases:
        if ai["method"] != "ai_assisted":
            continue
        matches = [m for m in cases if m["method"] == "manual" and all(m[k] == ai[k] for k in
                   ("case_id", "system_id", "input_hash", "scope_id", "criteria_id"))]
        if len(matches) > 1:
            raise ValueError("Ambiguous manual match; distinguish case identifiers")
        if matches:
            manual = matches[0]
            pairs.append({"case_id": ai["case_id"], "skill_version": ai["skill_version"],
                "workflow": ai["workflow"], "skill_hash": ai["skill_hash"], "model": ai["model"],
                "configuration_id": ai["configuration_id"], "manual_usd": manual["usd"], "ai_usd": ai["usd"],
                "basis": "measured" if manual["basis"] == ai["basis"] == "measured" else "estimated",
                "lead_time_reduction_hours": (manual["lead_time_hours"] - ai["lead_time_hours"]
                                              if manual["lead_time_hours"] is not None and ai["lead_time_hours"] is not None else None),
                "dependencies": ["system:" + ai["system_id"], *["reviewer:" + r for r in set(ai["reviewers"] + manual["reviewers"])]]})
    return pairs


def observed_summary(attempts):
    """Describe durations and known expenses without pretending a generation was accepted."""
    successful = [r for r in attempts if r["status"] == "success"]
    durations = [r["duration_seconds"] for r in attempts if r["duration_seconds"] is not None]
    success_durations = [r["duration_seconds"] for r in successful if r["duration_seconds"] is not None]
    api_durations = [r["api_request_seconds"] for r in attempts if r["api_request_seconds"] is not None]
    def describe(values):
        return {"n": len(values), "mean": statistics.mean(values) if values else None,
                "median": statistics.median(values) if values else None,
                "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
                "min": min(values) if values else None, "max": max(values) if values else None}
    return {"n_attempts": len(attempts), "n_successful_generations": len(successful),
            "n_failed_or_uncertain_attempts": len(attempts) - len(successful),
            "generation_success_fraction": len(successful) / len(attempts) if attempts else None,
            "engineering_acceptance_rate": None,
            "attempt_elapsed_seconds": describe(durations), "successful_attempt_elapsed_seconds": describe(success_durations),
            "api_request_seconds": describe(api_durations),
            "known_tokens": {k: sum(r["usage"].get(k, 0) or 0 for r in attempts if r["usage"])
                             for k in ("prompt_token_count", "candidates_token_count", "thoughts_token_count")},
            "attempts_without_usage": sum(r["usage"] is None for r in attempts),
            "total_attempt_elapsed_seconds": sum(durations),
            "known_token_estimate_or_invoice_subtotal_usd": sum(r["cost_usd"] for r in attempts if r["cost_usd"] is not None),
            "unknown_billing_attempts": sum(r["cost_usd"] is None for r in attempts),
            "actual_invoice_total_usd": sum(r["cost_usd"] for r in attempts) if attempts and all(r["cost_basis"] == "invoice" for r in attempts) else None,
            "cost_per_engineering_accepted_fmea_usd": None,
            "caution": "Known subtotal is not total billed expense or cost per accepted FMEA. Waiting is not measured active labor."}
