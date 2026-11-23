# FMEA analytics integration

The [remote branch audit](fmea-remote-branch-audit.md) records the heads, ancestry, workflows and integration decisions. The implementation retains the light, single-page Shiny dashboard and existing Python analysis stack.

## Storage and provenance

| Layer | Location | Identity and relationships |
|---|---|---|
| GitHub observations | Research registry SQLite, `workflows`, `artifacts`, `sync_runs` | Repository, workflow run ID and attempt identify each execution. Execution payload retains branch and commit. Artifact IDs are scoped to the repository. |
| Generation registry | `generations` and `aliases` | Stable generation ID and exact receipt SHA-256. The receipt identifies the system, model, configuration, skill and skill hash, when supplied. |
| Judge evaluations | `evaluations` | Generation ID plus a stable evaluation ID. Each payload includes judge version, judge model, item IDs and links to matched generated-row IDs. Distinct trials are retained and selection for study metrics is explicit. |
| Engineering register | Separate existing engineering SQLite workspace | Generated record IDs, original rows and append-only review events. Private launch gates access to the register. |
| Raw sources | Ignored `results/research/private/` directories | Content-addressed originals for registry imports and the archived aggregate CSV. |
| Derived outputs | `results/research/current.json`, `results/research/historical-comparison.json`, and local validated exports | The dashboard reads sanitized projections. The historical projection carries CSV hash and archive member provenance. |

The imported judge format accepts human-prepared, identifier-only data. Several reference opportunity IDs may link to one generated row. Opportunity-level denominators count each reference item once. Generated-row measures must count the generated row once across its links. Only matched opportunities with observed, scorable fields contribute to each agreement denominator. Unmatched and engineer-confirmed invalid rows require separate evidence.

## Operation

From the repository root with the Python analysis dependencies and dashboard R packages installed:

```powershell
python -m analysis.research sync --list-branches
python -m analysis.research sync --branch main --branch feat/v42-single-page-analytics --no-render
python -m analysis.research import-historical --file 'C:/path/to/Aggregated Results.zip'
Rscript dashboard/run_private.R
```

GitHub credentials are read from the server environment. Synchronization reads workflow metadata and supported execution receipts and reports partial sync and rate limits. The local dashboard offers branch selection and a staged **Import Judge Results** dialog. Preview validates against a registered successful generation. Confirmation applies the preview digest before persisting and refreshing. JSON, paired CSV, XLSX with `runs` and `items` sheets, and bounded ZIP are supported. ZIP accepts `judge.json`, `judge.xlsx`, or `runs.csv` and `items.csv` at its root. Multiple CSV or Excel trials for the same run require distinct evaluation IDs on both tables. A single trial can use legacy item tables with only the run ID.

## Historical result verification

| Version | Runs | Missed / opportunities | Pooled missed rate | Mean run missed rate | Equal-system mean | Unmatched rows per run |
|---|---:|---:|---:|---:|---:|---:|
| V2.0 | 18 | 232 / 738 | 31.4% | 30.5% | 28.2% | 2.4 |
| V3.0 | 15 | 78 / 603 | 12.9% | 12.1% | 12.1% | 12.0 |

Results above were recalculated from the supplied archive's `runs_both.csv`. The equal-system descriptive mean gives each system the same weight. A model-adjusted estimate and its uncertainty require a separate inferential analysis. This import includes run-level counts and cannot support item-level coverage or judge repeatability. The generated and historical judge workbooks were left unopened because the repository restricts access to human reference materials and the mixed worksheets have not been cleared for automated access.

## Remaining integration

- The SQLite registry still embeds configuration, branch, item links and trial details in JSON payloads. The engineering workspace and registry do not yet share row identities.
- GitHub sync remains receipt-specific. Raw generated result ingestion and configurable branch-tree discovery are pending.
- Historical judge workbook layouts, repeatability matrices, ambiguous adjudication, and summary-only judge uploads still need identifier-only adapters. Those features require a human-prepared, reference-free export.
- The historical table is study-level context with system and skill filters and a provenance-bearing CSV export. Shared branch, judge-version and round filtering across the operational register, historical charts and exports remains pending.
- The in-page import uses synchronous local Python invocations. Registry acceptance and dashboard snapshot creation are separate operations. If a refresh fails after acceptance, rerun refresh to republish the snapshot or re-preview to verify whether an evaluation is already stored.
