# V4 research platform: runbook and architecture

Start with [branch discovery and gap assessment](v4-discovery.md).
The Python package version is 0.3.0; standalone FMEA skills are V2/V3/V4.
Canonical unrated package outputs are a separate workflow and are rejected by this
study's importer. V2 is the designated baseline; V3 is exploratory only when supported.

## Architecture and data ownership

1. **Private raw:** original standalone responses, receipts, unchanged human-controlled
   external judge exports and human review events in ignored `results/` or private storage.
   Reference FMEAs remain human-only and are never read by this agent or the generator.
2. **Validated internal:** `analysis.round2` is the shared schema/metric importer;
   `analysis.research` orchestrates it, statistical methods and internal CSV/Excel output.
   Immutable builds preserve provenance and private copies of source imports. Originals
   are never overwritten. Item-level notes/identifiers stay in this layer.
3. **Sanitized presentation:** explicit allowlist produces `dashboard.json`, containing
   aggregate metrics and safe run metadata, no FMEA text, source IDs, private notes,
   raw token payloads, paths or reference content. R plots and Shiny read only this file.
   A sanitized file is still staged for human publication approval; generation is not
   authorization to publish data.

Python owns rates, counts, inference, CIs, criteria and Pareto percentages. R owns
figure layout, data polling and PDF rendering. There is one current research command:
`python -m analysis.research build`. Historical `analysis.round2` commands remain
available for reproducibility, but new V4 collections use `analysis.research`.

## Setup on Windows / Positron

Use Python 3.12+ and R (tested locally with 4.6.1). From repository root:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e ".[round2]"
New-Item -ItemType Directory -Force .venv/r-library
Rscript -e "install.packages(c('shiny','ggplot2','bslib','jsonlite','testthat'),lib='.venv/r-library',repos='https://cloud.r-project.org')"
Rscript -e ".libPaths(c('.venv/r-library',.libPaths())); shiny::runApp('dashboard',host='127.0.0.1',port=5384,launch.browser=FALSE)"
```

Open `http://127.0.0.1:5384` locally, or run the same R expression in Positron.
No Gemini or Claude key is needed for dashboard, ingestion, analysis or export.
The tracked offline demo is report-derived baseline only, never synthetic V4 findings.

## Version selection and independent inventory

- `--version v2.0`: original main prompt/array behavior; remains the default.
- `--version v3.0`: discovered remote V3 prompt/array behavior.
- `--version v3.0-audit`: retained prior local V3 structured audit; distinct condition.
- `--version v4.0`: new prompt and independent inventory audit.

Prepare an input-only inventory (no model call):

```powershell
python standalone_v4.py --system system_descriptions/system_B.txt --system-id B --output results/v4/inventory-B.json
```

The generic extractor expands explicit pipe-table quantities. Other engineering input
formats use the same manually prepared JSON contract. A human must reconcile narrative
interfaces, hierarchy, functions, states and uncertain quantities. Do not put reference
failure modes or judge answers into this inventory. Do not infer missing architecture.
The table extractor marks this work unreviewed; it does not claim complete architecture.
V4 calls accept that inventory but retain every review flag; engineering acceptance
requires human reconciliation. Reviewed applicable_categories may constrain failure
categories, but must not contain benchmark answers.

Each unit contains unit_id, name, kind (system/subsystem/assembly/component/interface/
connection), parent_id, relationships, function, operating_states, evidence,
detection_provisions, repeat_group/index/quantity and optional applicable_categories.
The document binds schema `input-inventory-4`, system_id and system_sha256. All IDs,
repeat indexes, relationships and hierarchy must validate. V4 FMEA rows retain the
historical 13 fields and add stable row/unit/category/state/detection/assumption links
in raw JSON and the receipt audit; exported CSV preserves existing columns.

Local generator syntax, only after separate generation authorization:

```powershell
python fmea_generator.py --version v4.0-inventory --system system_descriptions/system_B.txt --case-id system_B --run 2 --model CONFIRMED_ROUND1_MODEL_ID --inventory results/v4/inventory-B.json --campaign-id round2-v4-B-r02
```

The Actions legacy `run` input remains supported as an alias for `run_number`.
Team paid generation must use the existing GitHub `generate-fmea.yml`, mode=single,
per AGENTS.md. The local syntax documents the engine and supports offline mocked tests;
it is not a request to consume the team key locally.

## Controlled experiment and first pilot

The seeded V4 plan has A-E, four runs each, randomized order; seed 5300. Preparation
already exists at `results/v4/round2-plan/` with an unconfirmed model placeholder.
Confirm the Round 1 exact model ID, settings/output cap, package revisions, unchanged
judge v1.2 hash, human ground-truth revisions and original classification rules before
calling it a controlled comparison. Engineer-authored references remain human-only.

```powershell
python -m analysis.research plan --output results/v4/confirmed-plan --model CONFIRMED_ROUND1_MODEL_ID
python scripts/v4_schedule.py --manifest results/v4/confirmed-plan/experiment_manifest.json --start 1 --count 1
```

The schedule printer makes no network calls. It prints the first pilot command:

```powershell
gh workflow run generate-fmea.yml --ref feat/fmea-skill-v4-research-dashboard -f mode=single -f skill_version=v4.0-inventory -f system=system_B -f model=CONFIRMED_ROUND1_MODEL_ID -f run_number=2 -f batch_id=round2-v4-B-r02 -f approved_calls=1
gh run list --workflow generate-fmea.yml --limit 5
gh run watch RUN_ID
gh run download RUN_ID --dir results/github/RUN_ID
```

The branch must first be approved and pushed. This command authorizes one call; do not
execute it without explicit paid-pilot approval. Actions extracts a deterministic
input inventory, retains unresolved narrative review flags and records exact skill,
package/inventory hashes and Git SHA. For a curated inventory, use an approved input-only
inventory artifact and an explicitly reviewed workflow adjustment; never silently change
inventory protocol within the comparison. Baseline versus V4 measures the entire new
inventory-plus-prompt protocol, not a prompt-only effect.

After a successful reviewed pilot and explicit authorization for the remaining calls:

```powershell
python scripts/v4_schedule.py --manifest results/v4/confirmed-plan/experiment_manifest.json --start 2 --count 19
```

Run the printed commands one at a time in order, recording the Actions ID and outcome
against each manifest run. Printing all 20 commands (`--start 1 --count 20`) is supported;
there is deliberately no unattended paid dispatcher or retry loop. Coordinate the team's
approximate 20/day limit manually; failed attempts and pilot consume quota too. Stop at
quota exhaustion or an uncertain request. A replacement needs a separately approved new
study identity and plan amendment. Actions rejects reruns and duplicate study IDs; it
checks batch/system/replicate agreement. Download artifacts within 14 days to ignored
`C:\Users\camer\Documents\sigmaairlinesproject\results\github\RUN_ID\` and back up privately.

The manifest records run ID/version/system/model/settings, skill hash, Git SHA, status,
timestamps and artifact slots. Generation receipts are the actual executed provenance.
A preparation manifest's SHA precedes the final implementation commit: regenerate a
confirmed plan after checkout of the approved commit; never rewrite an executed plan.

## Gap audit and targeted remediation

```powershell
python standalone_v4.py --system system_descriptions/system_B.txt --inventory results/v4/inventory-B.json --response results/github/RUN_ID/system_B_v4.0-inventory_run02_raw.txt --output results/v4/gap-report.json
```

Audit checks independent unit/repeat IDs, all 18 case decisions, input applicability,
case/row links, unsupported IDs/names/categories, duplicates, required cells and ratings.
Schema/truncation failure retains raw text and prevents accepted CSV. A machine-readable
report is retained in the receipt, with missing IDs/cases and targeted correction
instructions. Save each corrected response under a new run/attempt identity with its
original hash; never edit original output or automatically call remediation. Textual
specificity, detection wording and causal chain checks are review heuristics. No software
claim substitutes for engineering correctness, applicability or full architecture review.

## External independent judge and import

The unchanged private judge skill v1.2 and original report/item records were unavailable.
No new judge methodology or paid judge client was invented. Prepare one task:

```powershell
python scripts/prepare_v4_judge.py --manifest results/v4/confirmed-plan/experiment_manifest.json --run-id round2-v4-B-r02 --generation-receipt results/github/RUN_ID/system_B_v4.0-inventory_run02_execution.json --output results/v4/judge-task-B-r02.json
```

A human runs that task with the **existing external Claude Sonnet 5.5 judge v1.2** and
same references, then exports identifier-only `standalone-judge-import-1` records.
That external single-evaluation command cannot be supplied until its private runner and
instructions are provided. Judge outputs must not be replaced with guessed scores.
Use the JSON contract in [the retained importer runbook](round2-runbook.md), changing
skill_version to v4.0 and run_id to the V4 study ID. Include generation_receipt_path,
comparison_review_status=human_confirmed, skill_sha256, system_sha256,
judge_instruction_sha256, ground_truth_sha256 and exact common generation settings.
The receipt imports measured timing/usage and checks identity, status and row counts.
Missing fields stay missing; comparison eligibility requires provenance review and hashes.
Mixed hashes within a version or system are rejected, not silently pooled.

Run metadata tracks generation/evaluation timestamps and statuses, model/judge versions,
opportunities/found/missed, DPMO, generated/extras, quality fractions and their denominators,
duration, usage/cost, structure/format/inflation review and missing-data status. Existing
field names (`system`, `ground_truth_count`, `generated_rows`, etc.) are reused; safe
snapshot field mapping is defined by SAFE_RUN_FIELDS. Dates/costs absent from an import
are null, not zero. Token usage remains in private validated runs, not browser payloads.

Items retain opaque item_id, found/missed, matched_row_id, miss_category, cause/effect
comparison booleans, signed rating differences, RPN relative difference, review_status
and optional private judge_notes. One-to-one matching and matched+extras=row count must
hold. Classification categories remain mutually exclusive; unsupported classification
stays null/Unclassified. Ground-truth wording is not accepted by the importer.

## Human engineering review

Prepare an identifier-only deterministic sample queue with:

```powershell
python -m analysis.research review-sample --judge results/v4/imports/v4_judge_import.json --output results/v4/review-queue.json
```

The queue samples correct matches, misses, extras, severity disagreements and ambiguous
categories where evidence exists; empty strata stay empty. For extras, a human must
select the actual unmatched generated-row ID because aggregate exports lack it.
Complete review decisions in a separate event file, never overwrite judge results.
Sample correct matches, misses, extras, severity disagreements and ambiguous categories.
Store a separate private JSON with schema `engineering-review-1` and events containing:
event_id, run_id, item_id (except extras), sample_type, ai_result, engineer_result,
adjudication_status, reviewed_at, optional review_minutes. Sample types are
correct_match/missed/extra/severity_disagreement/ambiguous_classification. Adjudication
states: pending/agreed/adjudicated/unresolved. New events have unique IDs. The importer
calculates agreement; it never changes the original AI item decision. Review identities
are not authenticated and neither a PASS string nor schema validation confers approval.

## Aggregate and regenerate all outputs

```powershell
python -m analysis.research build --judge results/v4/imports/v2_judge_import.json --judge results/v4/imports/v4_judge_import.json --review results/v4/reviews.json --output results/research/study-build-01
```

Omit `--review` until review events exist. Repeated `--receipt` inputs register generation
progress and audited coverage without adding quality scores. Use a new build directory
each time. Inputs are content-deduplicated and archived privately; an import catalog
retains earlier sources, so an incremental refresh cannot erase evaluated history.
Duplicate/conflicting run IDs across genuinely different imports fail. Validation and
rendering finish before current.json is replaced. `--no-render` is for Python-only tests,
not a completed poster update. Sources include exact hashes. Public JSON is built by an
allowlist; originals, item records and notes are not published.

Build outputs: validated runs/items/per_system/per_version/pareto CSV; analysis.xlsx;
engineering_review.csv; statistical_results.json; data_quality_provenance.json;
dashboard.json; two ggplot PNG/PDF figures; poster.pdf; presenter-notes.md. The workbook
contains descriptive summaries and eight V4 criteria. Detailed F-tests/diagnostics and
bootstrap output are in statistical_results.json/dashboard.json.

Baseline-only build (no invented data):

```powershell
python -m analysis.research build --output results/research/baseline-build-NEW
```

Known Round 1 aggregates are report-derived (18, 738, 232, 43 and miss-category totals),
plus user-reported approximate 98% cause correctness and 58% severity accuracy. There
are no source-run records to independently verify these latter percentages. V3 branch
code is not evidence of V3 performance. No actual V3/V4 evaluation has been executed.

## Statistical methods

Primary contrast: V2 versus V4. Exploratory contrasts: V3/V4 and joint V2/V3/V4 when
comparable evaluated records exist. Hash/review-ineligible records remain descriptive
only; they do not enter inference. Additive OLS compares the full version+system model
against system-only, testing the partial version term. The exploratory three-version
F test jointly tests two version terms. No interaction is fitted. Report F, p, degrees
of freedom, residual SD, Shapiro and median-Levene diagnostics. Test status remains
INSUFFICIENT_DATA when cells/rank/residual variance are insufficient. Diagnostics are
not proof of assumptions; bounded proportions and small cells limit interpretation.

The deterministic bootstrap uses seed 5300 and 2,000 resamples, resampling independent
runs within each version/system cell. Each system receives weight 1/5. At least two
observed independent runs per cell are required; four planned runs still give limited
precision. Improvement is baseline minus treatment in percentage points, with percentile
95% CI. Equal-system bootstrap means are explicitly separate from unweighted run means
and opportunity-weighted pooled percentages. Per-system CIs use run resampling. Figure
filters select observations, but published intervals/inference retain the full cohort.
Pooled DPMO=misses/opportunities*1e6. Sigma=inverse-normal yield+1.5, undefined at exact
zero/one rates and never a process certification. Report-derived pooled baseline cannot
support a run mean, CI or ANOVA. No unavailable denominator or observation is inferred.

Criteria use PASS/FAIL/PENDING/INSUFFICIENT_DATA: run mean <20%; primary p<.05; at least
four systems improve; none worsens >5 pp; extras mean <=4.8; structural checks pass;
valid format; human-reviewed unsupported inflation acceptable. Four V4 runs/system
and provenance review are required before PASS on the completed treatment. The last
criterion is a human judgment, not output volume. Inconclusive inference calls for
additional independent runs justified by observed variance; no automatic success claim.

## Dashboard refresh, export and hosting

The five views are Poster, Live results, Failure-mode analysis, Explorer and Methodology.
Version/system/run/date/evaluation filters affect observations. Unknown dates remain
explicitly unavailable. Missing evaluated versions display Pending Evaluation. App data
source defaults to `results/research/current.json`; tracked baseline fallback works offline.
Local files poll for mtime changes every 30 seconds; HTTPS endpoints poll every 30 seconds.
Manual Refresh reads immediately. Invalid/unavailable updates retain the last good cache.
The evidence strip shows status, last update and data version. No provider keys are read.

Set `SIGMA_DASHBOARD_DATA` to a permanent **approved sanitized HTTPS JSON endpoint**
(or local file). For deployment, install R dependencies, bundle dashboard/ with its
baseline fallback, configure the endpoint, and deploy with rsconnect to shinyapps.io,
Posit Connect or a Shiny Server host after explicit approval. No deployment was run.
The bootstrap handles a bundled app without the repository's local R library. Hosting
must grant a writable temporary cache, and endpoint access must expose sanitized data only.

Generation Event A: the generator registers finalized V4 receipts offline; it changes
progress only and never quality metrics. A failed registration leaves the receipt and
prints a visible status for offline retry. Evaluation Event B: build validates imports,
aggregates, recalculates stats, renders figures/poster and atomically replaces current.json.
`research-refresh.yml` prepares offline review artifacts after generation or a manual
source-run import. It has no provider key, write permission or public deployment step.
Artifacts are transport, **not permanent research storage**. For a production hosted
runner, mount/restore the durable private import catalog from team-selected storage
before build, back it up after build, then publish only the approved snapshot/figures.
That private store and approved permanent Pages/HTTPS endpoint are not configured;
cross-run hosted cumulative refresh/publication is blocked until they are selected.
Local cumulative refresh works from the persistent ignored results/research directory.
No temporary artifact URL is used by the Shiny app.

After approval, publish only dashboard.json and presentation figures to the stable
sanitized endpoint, using the host's atomic object replacement/versioned release.
Never copy validated/ or private/ to Pages. Review data_quality_provenance first.
The app refreshes without redeployment; invalid endpoints retain cached evidence.

```powershell
Rscript dashboard/export.R results/research/current.json results/v4-presentation/approved-export
Rscript dashboard/export.R dashboard/data/baseline.json results/v4-presentation/offline-demo
```

These create coverage.png/pdf and pareto.png/pdf at 300 dpi and a 24x13.5-inch landscape
poster.pdf using the same authoritative snapshot. The in-app Export poster PDF uses the
same renderer. Presenter notes generated per build include a two-minute draft and demo
steps; students must verify and rewrite submitted prose. Do not assert fulfillment of
unavailable private Canvas rubric details; this implements the supplied five-part brief.

## Tests and troubleshooting

```powershell
$env:PYTHONPATH='src'
$env:SIGMA_FMEA_AUTOREPORT='off'
$env:SIGMA_TEST_WHEEL=(Resolve-Path .venv/test-wheels/sigma_fmea-0.3.0-py3-none-any.whl).Path
python -m unittest discover -s tests -v
Rscript dashboard/tests/run.R
```

Tests use synthetic cases, never reference content. Synthetic render validation stays
under results/ and is labeled SYNTHETIC_TEST_ONLY. R package startup notices about a
minor build version/local Windows locale do not change research data. If Rscript is
missing, install R and add its bin folder to PATH. If cache permissions fail, use a
writable temp directory; app retains its fallback. A corrupt snapshot/import fails before
publication. Existing build directories are immutable: choose a new build name.
An interrupted process can leave a private stage/lock: inspect before removing it and
retry **offline processing only**. Never retry an uncertain paid request automatically.

Backlog: obtain original Round 1 run/judge evidence and frozen conditions; reconcile input
inventories; provide unchanged private judge runner; authorize pilot and review output;
collect planned runs and human checks; select private storage and approve a sanitized
endpoint; verify inference assumptions and professor-specific rubric before presentation.
