# Financial impact analysis

Run from the repository root with Python 3.12/3.13. This is an offline consumer of
execution metadata. It never calls a provider or requires generation credentials.
All new calculation/control-flow blocks have explanatory comments and public
functions have docstrings, following the user's annotation clarification recorded
in [the standards checklist](../../docs/SYSEN5300_CODING_STANDARDS.md).

```powershell
python -m pip install -e ".[financial]"
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -m unittest discover -s tests -v
python -m analysis.financial_impact --manifest results/single-system-replicates/system_A/20261101T163923Z-system-a-five/manifest.json
```

Each execution creates a new `reports/financial_impacts/TIMESTAMP-UNIQUE/` package.
An existing ID is rejected, not overwritten. Completed packages contain Discussion
working text, summary CSV, metrics, assumptions/references/captions, manifest and
300-dpi figures. `index.json` is a mutable, rebuildable catalog; packages are immutable.
Failed staging directories are hidden and retained for inspection, not indexed.
The `preliminary` status never automatically becomes reviewed or validated.

## Evidence and condition boundaries

Accept one or more explicit `--manifest` paths: existing standalone replicate
manifests, new `*_execution.json` receipts, or canonical `state.json` records. The
importer reads metadata only, not raw FMEA worksheets or reference/ground-truth
answers. Input/skill hashes are preserved as recorded; absent historical timing or
usage fields stay null. Canonical baseline/improved conditions remain separate from
standalone Gemini and from each other. Duplicate imports are rejected.

Financial cohort identity consists of experiment ID, system ID, exact input hash,
workflow, skill version/hash, model/settings hash, scope ID, criteria ID and method.
Use distinct experiment IDs for different scopes; one generation cannot be allocated
twice. Match manual and AI accepted cases by case ID, system/input, scope and criteria.
Do not relabel versions or pool incompatible conditions to gain sample size.
Systems A-E and future names/versions are data values, not hardcoded analysis logic.

## Collect engineering measurements

Copy header-only templates into ignored `data/financial_private/`; never put private
reviewer logs in a tracked report. Templates contain no fabricated project observations.
Pass `--labor`, `--quality`, `--invoices`, `--expenses` as needed. Select the assumed
price schedule with `--tier` and `--billing-arrangement`; a missing matching dated
tariff leaves estimated expense unavailable rather than substituting another tier.

| Columns | Meaning / units |
|---|---|
| experiment_id, case_id | Workflow cost pool and matched deliverable identity; case IDs must distinguish repeated independent deliverables |
| system_id, input_hash | System and exact SHA-256 input identity |
| workflow | `standalone_gemini`, or `canonical_research:baseline` / `canonical_research:improved` |
| skill_version, skill_hash, model, configuration_id | Exact experimental condition; use `not_applicable` for manual-only fields |
| scope_id, criteria_id | Independently established analysis scope and quality-acceptance rubric identifiers |
| method | `manual` or `ai_assisted` |
| engineer_id, reviewer_id | Private pseudonymous personnel IDs; used to identify statistical dependence |
| stage | initial_development, preparation, generation_supervision, engineering_review, correction, peer_review, approval, failure_recovery, skill_maintenance |
| active_engineering_minutes | Active work excluding the separately recorded review and rework buckets |
| review_minutes, rework_minutes | Additional, mutually exclusive active minutes; **do not also include them in active_engineering_minutes** |
| passive_waiting_minutes | Unattended waiting, excluded from labor cost |
| started_at, finished_at | Both zoned timestamps, or both blank; full case endpoints give lead time in hours |
| approval_status | Accepted/rejected closure on an `approval` labor stage; records attest the complete labor log for that case |
| decision, independent_review | accepted/rejected/pending; decided cases require `independent_review=true` and a reviewer |
| missing_modes, unsupported_modes, unit_expansion_corrections, technical_corrections, unsupported_assumptions, rating_corrections | Independent aggregate integer counts, or blank for unknown; never supply answer worksheets |
| notes, evidence_source | Private collection notes and source locator; not copied into reports |
| cost_kind, usd (expenses) | USD expense for the full workflow, e.g. tooling, skill_maintenance, fallback; never repeat an invoice already supplied as generation cost |

Use `configuration_id` from ingested attempt metrics. The quality-adjusted acceptance
rate is accepted cases / independently decided cases; pending cases are reported
separately. It is distinct from successful API requests / attempted API requests.
Missing logs do not establish zero labor or zero accepted deliverables.

Invoices are an optional JSON object mapping `experiment_id/attempt_id` to the actual
USD generation expense, including failed attempts where evidence exists. Use explicit
zero only with invoice/account evidence. Expenses are a JSON list using the identity
columns in `expenses_template.csv` plus method, cost_kind, usd and evidence_source.
Keep costs already invoiced elsewhere out of this file to avoid double counting.

## Financial assumptions and arithmetic

`assumptions.json` and `sources.json` are versioned inputs, copied into report text
and hash-bound by the manifest. Override them with `--assumptions` / `--sources`;
create a new file version instead of editing a historical report.

- Illustrative rate = 64.89 USD/hour × (46.89 / 32.82), approximately 92.71 USD/hour.
  This blends aerospace median wages with private-industry average benefits, not a
  company fully allocated rate. A fully burdened override replaces the calculation.
- Gemini Standard paid estimates add prompt input and candidate + thinking output
  tokens exactly once, at the effective model/tier/date/arrangement tariff. Thinking
  unavailable is not assumed zero. Cached/tool usage needs separate billing support.
  Invoices override estimates. Pilot account tier and failed billing remain unverified.
- Accepted cost = all active labor cost + relevant generation and nonlabor workflow
  expenses, divided by independently accepted deliverables. Failed/rejected work is
  retained in the same pool. Any unresolved required attempt expense makes total
  accepted cost unavailable; known subtotals remain visible. Unknown optional overhead
  is a limitation, not a claim of complete company cost.
- Absolute unit savings = manual accepted cost − AI accepted cost. Percent reduction
  divides by positive manual cost. Negative savings are preserved. Annual net savings
  and break-even additionally require explicit first-year `annual_workload` settings with
  `development_usd`, `maintenance_usd`, `annual_fmeas`. Later years set the already
  incurred development expense to zero explicitly. No avoided-accident valuation.

## Uncertainty and visuals

Seed 5300 and at least 10,000 iterations are recorded. Primary intervals bootstrap
matched measured cost pairs, resampling whole connected clusters sharing a system
or reviewer. Manual/AI pairs stay intact. The configurable minimum of three clusters
is a conservative software gate for exploratory output, not a guarantee of coverage;
very few clusters still yield unstable intervals. Estimated prices are not invoices,
and estimated-cost pairs do not receive an empirical measured-cost confidence interval.

Monte Carlo is optional and requires an explicit `scenario` object, with a rationale
and distributions for labor_rate, manual_hours, ai_hours, api_usd_per_attempt,
success_probability, maintenance_usd, development_usd and annual_volume. Each uses
`{"distribution":"constant","value":...}`, `uniform` (low/high) or `triangular`
(low/mode/high). Specify units as USD/hour, hours/FMEA, USD/attempt, probability,
USD/year or USD investment, and FMEAs/year respectively. For an accepted-FMEA cost
scenario, success_probability must mean the effective probability of producing an
accepted deliverable per attempt, not merely valid JSON. Simulated assumption inputs
are independent; expected attempts per accepted success are 1/p. These are **simulation
intervals, not empirical confidence intervals**. No scenario labor times are inserted
into the pilot dataset. Without explicit distributions, the tornado and break-even
figures explain missing inputs rather than inventing scenario measurements.

The six requested financial figures are always produced, with missing-data panels
where quantities are not estimable. A seventh panel shows the real attempt durations
and known API estimates. Text-only missing panels are intentional, not zero bars.
Candidate engineering ratings and row counts are never treated as financial accuracy,
coverage, acceptance or safety benefits.

## Future versions, publication and reproducibility

Add new explicit manifest paths, input identities, tariffs and independent quality/labor
records; rerun to create a new report ID. Never edit earlier packages. The report
manifest records code version/Git SHA/code hashes, input hashes, assumption version,
dependency versions, sample sizes, methods, seed and creation time. Exact numerical
results reproduce with fixed inputs/seed even though report IDs and timestamps differ.

Only approved aggregate report packages, source, blank templates, documentation and
tests belong in Git. Proposed preliminary report artifacts can be reviewed in a PR;
no change to the generated-FMEA hygiene guard is necessary. Raw outputs remain in
ignored results/. Do not commit private personnel/quality records, invoices or frozen
research modifications. Read the instructor's prose policy: working generated report
text is not a student-authored submission; students must write their own interpretation.

## Future timing receipts

Standalone receipts and canonical `execution-metadata.json` contain UTC endpoints,
monotonic API/parse/total seconds, input/skill/configuration identity, status/failure,
available usage and artifact hashes. Non-request preflight refusals do not generate
a new attempt receipt. No-response attempts have API duration and null parse/usage.
Pricing fields are null with an explicit offline-analysis status; receipt creation
does not guess a billing arrangement or couple generation to financial assumptions.
Historical CSV timing columns and pilot evidence remain unchanged. Newly generated
standalone CSVs omit repeated generation_minutes; clients should read the sidecar.
