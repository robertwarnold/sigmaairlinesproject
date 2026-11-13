# Offline standalone experiment reporting

This module extends the existing `fmea-execution-1` receipts and financial importer.
It never generates an FMEA or requires a provider key. Canonical research conditions,
frozen evidence and human reference worksheets are excluded. All ratings are provisional.

Install from the repository root: `python -m pip install -e '.[financial]'`.

```powershell
python -m analysis.experiments report --source results/my-campaign --artifact-root results/my-campaign --analysis-id my-report-v1
```

For multiple campaigns, use repeated `--source`/`--manifest` arguments or a local JSON
`--registry` with `manifests`, `artifact_roots`, optional `effective_index` and
`provider_evidence`. Paths must identify generated standalone artifacts. Do not scan
reference folders or supply canonical research output as standalone evidence.
An effective index uses the existing A-E index `systems` entries (`system_id`,
`source_campaign`, `effective_attempt_id`, optional `csv_sha256`). It retains every
successful A pilot replication and the selected B-E recoveries. Additional valid
replications remain separately labeled. Without an index, every validated draft is
included; no representative is silently chosen.

## Permanent collection and automatic reports

`execution_metadata.py` extends the existing receipt with retry/wait, verified HTTP,
unknown billing and provisional CSV characteristics; see [receipt_schema.json](receipt_schema.json).
The generator records stable campaign/attempt identity, UTC endpoints, monotonic API,
parse and total durations, input/skill/settings, usage and artifact hashes. Metadata-only
`--campaign-id` or `FMEA_CAMPAIGN_ID` can name local runs. Local generation and campaign
entry points invoke reporting after finalizing receipts. Recovery wrappers add their
retry history without changing request configuration, limits or delay policy.

`SIGMA_FMEA_AUTOREPORT=off` explicitly disables automatic rendering, not receipt capture.
Install financial dependencies before using the default automatic renderer. Reporting
incidents are visible in `*_reporting.json`/`reporting_status.json` and never change the
generation outcome. Retry a failed report with the offline command above. An interrupted
writer may leave a `.lock` file: verify no reporter is running before removing that lock.
Reports are immutable; choose a new analysis ID. Catalog upserts are atomic and locked.

Actions defers rendering to a separate `experiment-report` job with no provider key.
It executes on generation failures too, downloads that run's recoverable artifacts,
uploads the report, and writes a Summary-page link. The manual `report-experiments.yml`
workflow can analyze an existing `source_run_id` without dispatching generation.
Runner storage is ephemeral: a per-run Actions report does not automatically contain
other campaigns. Download and combine campaign artifacts locally using a registry.
Actions artifacts expire after **14 days**; download them to ignored `results/github/<run-id>/`
and back up to controlled-access storage before expiry. Local files do not exist on
GitHub-hosted runners. A failed job before any receipt exists has no recoverable attempt.

## Identity, validation and datasets

`catalog.py` supports execution sidecars, legacy A manifests, campaign containers and
reconciled embedded histories. Physical receipt hashes and campaign/attempt IDs prevent
double accounting; conflicting identities fail visibly. Generic legacy `results` IDs
receive a receipt-derived namespace. Explicit legacy observation dates do not become
invented request-start times. Unsupported manifests are reported as exclusions.
CSV hashes, headers, nonempty fields, rating ranges, RPN arithmetic and system/version/model
identity must validate before a draft enters engineering summaries. Missing/changed
artifacts invalidate the observation. Failures stay in operational history, not risk
distributions or review denominators. HTTP 503 classification requires typed provider
evidence; a string containing '503' is insufficient. Verified historical overlays bind
to a receipt hash and preserve the original record.

`report.py` creates README/dashboard, campaign_summary, attempt_history,
effective_fmea_summary, provisional_risk_summary, cost_summary, audit/provenance,
dashboard_manifest and ten 300-dpi figures. Effective-summary rows expose primary,
representative and additional roles. Literal component counts are representation,
never completeness without a validated inventory. Engineering acceptance requires an
explicit, condition-matched quality-log decision; generated review flags do not qualify.

`figures.py` produces generation outcomes, durations, row counts, S/O/D, RPN,
component representation, reliability/retries, expense, generation efficiency and
engineering review status. Cohorts retain skill/input/settings differences, including
unknown legacy configuration. Descriptive row distributions are nested within drafts;
they do not establish repeatability or technical validity.

Every report actually executes `python -m analysis.financial_impact` on deduplicated
receipts, prints a data audit before plotting and saves `financial_execution.log`.
See the [financial methodology](../financial_impact/README.md). Pass optional `--labor`,
`--quality`, `--invoices`, `--scenario` to use the existing schemas and model. All
invoice-free attempts have unknown actual billing even when a tariff estimate exists.

## Explicit public aggregate publication

```powershell
python -m analysis.experiments publish-stage --report results/experiment_reports/my-report-v1 --output results/publication-review/my-report-v1
```

This stages only hash-verified aggregate PNGs, captions and a publication manifest for
human review. It does not stage raw CSVs, responses, private invoices, reviewer logs or
perform Git operations. After approval, copy only reviewed aggregates to a public report
directory and submit a PR. Never force-add ignored raw output or weaken repository hygiene.

Tests use synthetic fixtures, including full plotting and execution of the financial
CLI, idempotency, retries/partial recovery, missing billing, legacy metadata, immutable
outputs, canonical exclusion and report failure isolation. No model calls are authorized.
