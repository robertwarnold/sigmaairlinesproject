# Assumptions and sources

Assumptions version: financial-assumptions-2026-11-01-v1.
Loaded labor rate: USD 92.708473/active hour; illustrative, not measured company cost.

BLS (2026a) = Aerospace Engineers; BLS (2026b) = ECEC; Google (2026) = pricing; Fraser (n.d.) = teaching example.

No empirical accepted-cost/savings CI exists without measured matched cases. Unknown failed billing is not zero. Scenario distributions, if supplied, are assumptions and not the real project dataset.

## Versioned assumptions snapshot

```json
{
  "version": "financial-assumptions-2026-11-01-v1",
  "currency": "USD",
  "seed": 5300,
  "iterations": 10000,
  "labor": {
    "wage_usd_per_hour": 64.89,
    "benefit_wage_usd_per_hour": 32.82,
    "benefit_total_usd_per_hour": 46.89,
    "fully_burdened_override_usd_per_hour": null,
    "status": "illustrative national-average assumption, not a company rate",
    "source_ids": [
      "bls_wage_2025",
      "bls_ecec_2026"
    ]
  },
  "pricing": [
    {
      "model": "gemini-3.8-flash",
      "tier": "standard_paid",
      "billing_arrangement": "pay_as_you_go",
      "effective_from": "2026-11-01",
      "effective_through": "2026-12-31",
      "input_usd_per_million": 0.75,
      "output_including_thinking_usd_per_million": 3.75,
      "source_id": "google_pricing_2026",
      "status": "token estimate only; pilot account tier and invoices unverified"
    }
  ],
  "scenario": null,
  "minimum_independent_clusters": 3,
  "missing_cost_policy": "Unknown failed billing or required labor makes total cost unavailable; retain known subtotal."
}
```

## References

- U.S. Bureau of Labor Statistics (May 2025). Aerospace Engineers, Occupational Outlook Handbook. https://www.bls.gov/ooh/architecture-and-engineering/aerospace-engineers.htm (accessed 2026-11-01).
- U.S. Bureau of Labor Statistics (June 2026). Employer Costs for Employee Compensation. https://www.bls.gov/news.release/ecec.nr0.htm (accessed 2026-11-01).
- Google (November 2026; listed promotion through December 31, 2026). Gemini Developer API pricing: Gemini 3.8 Flash Standard. https://ai.google.dev/gemini-api/docs/pricing (accessed 2026-11-01).
- Fraser, T. (accessed 2026). Financial impact analysis of a process improvement. https://github.com/timothyfraser/sysen/blob/main/code/ZZ_financial_analysis.R (accessed 2026-11-01).

## Figure captions

- 01_before_after_cost: Preliminary cost comparison; 95% paired cluster confidence bounds appear only when estimable. Cohort bars without bounds have no separately estimable confidence interval.
- 02_labor_breakdown: Record development, supervision, review, rework, peer review and approval separately; exclude passive waiting from labor cost.
- 03_savings_bootstrap: 95% percentile confidence interval resamples connected system/reviewer clusters while preserving pairs. Three generations from one system are not three systems.
- 04_cost_sensitivity: Scenario-only when distributions are supplied; otherwise unavailable. Loaded-rate sensitivity alone is USD per active hour saved, not a measured labor saving.
- 05_break_even: Fixed skill investment and annual maintenance must be explicit. If AI unit cost is higher, positive fixed investment has no finite break-even.
- 06_skill_versions: Keep skill hashes, model settings and canonical/standalone conditions separate. No version improvement is established by this pilot.
- 07_observed_generation: Observed elapsed durations and tariff estimates only. Red bars are failed/uncertain attempts; unobserved failed billing remains unknown. No labor or acceptance claim.