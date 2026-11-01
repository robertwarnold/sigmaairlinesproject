"""Observed paired/clustered bootstrap and separately labeled assumption simulation."""
import numpy as np
from .data_schema import number


def paired_bootstrap(pairs, iterations=10000, seed=5300, minimum_clusters=3):
    """Resample independent dependency clusters, keeping manual/AI cases paired."""
    # Each pair supplies measured accepted costs and all system/reviewer dependencies.
    if iterations < 10000 or minimum_clusters < 2:
        raise ValueError("Require at least 10,000 iterations and two independent clusters")
    unavailable = {"status": "not_estimable", "mean_savings_usd": None, "ci95_usd": None,
                   "iterations": iterations, "seed": seed, "interval_method": "cluster percentile bootstrap",
                   "n_matched_cases": len(pairs), "n_independent_clusters": 0, "draws": None,
                   "reason": "Insufficient independently clustered, measured, quality-matched cases"}
    if not pairs:
        return unavailable
    # Connected components merge cases sharing either a system or a reviewer.
    parent = list(range(len(pairs)))
    def root(index):
        while parent[index] != index:
            index = parent[index]
        return index
    for i, pair in enumerate(pairs):
        if pair.get("basis") != "measured" or not pair.get("dependencies"):
            raise ValueError("Bootstrap requires measured pairs with declared dependency identities")
        for j in range(i):
            if set(pair["dependencies"]) & set(pairs[j]["dependencies"]):
                parent[root(i)] = root(j)
    groups, cost_groups = {}, {}
    for i, pair in enumerate(pairs):
        # Costs are nonnegative; their difference may be negative.
        delta = number(pair["manual_usd"], "manual") - number(pair["ai_usd"], "AI")
        groups.setdefault(root(i), []).append(delta)
        cost_groups.setdefault(root(i), []).append((float(pair["manual_usd"]), float(pair["ai_usd"])))
    unavailable["n_independent_clusters"] = len(groups)
    if len(groups) < minimum_clusters:
        return unavailable
    # Resample whole connected clusters; case weighting is retained in each draw.
    clusters = list(cost_groups.values())
    rng = np.random.default_rng(seed)
    paired_means = np.array([np.mean([v for i in rng.integers(0, len(clusters), len(clusters))
                                     for v in clusters[i]], axis=0) for _ in range(iterations)])
    draws = paired_means[:, 0] - paired_means[:, 1]
    return {**unavailable, "status": "estimable", "reason": None,
            "mean_savings_usd": float(np.mean([v for group in groups.values() for v in group])),
            "ci95_usd": np.quantile(draws, [0.025, 0.975]).tolist(), "draws": draws.tolist(),
            "manual_mean_usd": float(np.mean([p["manual_usd"] for p in pairs])),
            "ai_mean_usd": float(np.mean([p["ai_usd"] for p in pairs])),
            "manual_ci95_usd": np.quantile(paired_means[:, 0], [.025, .975]).tolist(),
            "ai_ci95_usd": np.quantile(paired_means[:, 1], [.025, .975]).tolist(),
            "resampling_unit": "connected system/reviewer dependency cluster; paired cases retained",
            "assumptions": "Clusters independent and representative; small cluster counts remain unstable."}


def simulate(scenario, iterations=10000, seed=5300):
    """Simulate explicitly supplied assumption distributions, never empirical labor data."""
    if scenario is None:
        return {"status": "not_requested", "interval_kind": "assumption-driven simulation", "draws": None}
    if iterations < 10000 or not scenario.get("rationale"):
        raise ValueError("Document scenario rationale and use at least 10,000 simulations")
    required = {"labor_rate", "manual_hours", "ai_hours", "api_usd_per_attempt", "success_probability",
                "maintenance_usd", "development_usd", "annual_volume"}
    if set(scenario["distributions"]) != required:
        raise ValueError("Scenario requires all named financial distributions")
    rng = np.random.default_rng(seed)
    samples = {}
    for name, spec in scenario["distributions"].items():
        # All distributions are supplied explicitly, with bounded nonnegative support.
        kind = spec["distribution"]
        if kind == "constant":
            values = np.full(iterations, number(spec["value"], name))
        elif kind == "triangular":
            low, mode, high = (number(spec[k], name) for k in ("low", "mode", "high"))
            if not low <= mode <= high or high == low:
                raise ValueError("Invalid triangular distribution")
            values = rng.triangular(low, mode, high, iterations)
        elif kind == "uniform":
            low, high = number(spec["low"], name), number(spec["high"], name)
            if high <= low:
                raise ValueError("Invalid uniform distribution")
            values = rng.uniform(low, high, iterations)
        else:
            raise ValueError("Supported distributions: constant, triangular, uniform")
        samples[name] = values
    probability, volume = samples["success_probability"], samples["annual_volume"]
    if np.any(probability <= 0) or np.any(probability > 1) or np.any(volume <= 0):
        raise ValueError("Require 0 < success probability <= 1 and positive volume")
    # Expected attempts per success = 1/p, an assumption of independent stationary trials.
    manual = samples["labor_rate"] * samples["manual_hours"]
    ai = samples["labor_rate"] * samples["ai_hours"] + samples["api_usd_per_attempt"] / probability
    net = manual - ai - (samples["maintenance_usd"] + samples["development_usd"]) / volume
    return {"status": "scenario", "interval_kind": "assumption-driven 95% simulation interval, not confidence interval",
            "rationale": scenario["rationale"], "iterations": iterations, "seed": seed,
            "mean_net_savings_usd": float(np.mean(net)), "interval95_usd": np.quantile(net, [.025, .975]).tolist(),
            "draws": net.tolist(), "assumptions": "Independent specified distributions; stationary geometric attempt model."}
