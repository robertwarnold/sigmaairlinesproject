# V4.1 validation and security record

Start: feat/fmea-skill-v4-research-dashboard, 9f110cda11a717b7df0533a572c908d62222fcee.

## Verification

- Before edits: complete Python suite 193 tests passed; R suite 16 assertions passed.
- Release verification: complete Python suite 209 tests passed; R suite 26 assertions
  passed. Logs are ignored under results/v41-final-python.log and v41-final-r.log.
- New tests cover batch/retry identity, failed workflows, idempotent receipt hooks,
  unknown/mismatched judge runs, duplicate/conflicting evaluations, explicit selection,
  human review, JSON/CSV/XLSX adapters, CSV header corruption, rollback and last-good
  render behavior, API rate limits, missing artifacts, monetary nulls, deterministic
  simulation, negative savings and reset. Synthetic cases are never research findings.
- R startup, legacy/4.1 validation, premature-quality rejection, cache/manual refresh,
  baseline-only display, synthetic evaluated plots, Python-backed scenario updates,
  negative savings, reset, shared figures and PDF export are checked.
- Browser checks exercise all six views at 1920x1080, scenario/reset, metadata drill-down,
  presentation focus and responsive layout. Preview screenshots remain ignored.
- All Actions YAML parsed; Python compilation and Git whitespace/hygiene checks passed.

## Real operational-data smoke test

A read-only public GitHub API backfill registered 30 workflow executions before the
unauthenticated rate limit. This is PARTIAL, not a completed authenticated sync. The
existing credential helper had no credential available. No workflows were dispatched.
Fourteen preexisting local execution sidecars were normalized: 8 successful generated
FMEAs, 6 failed attempts, 8 awaiting judge, 0 accepted evaluations. Their metadata is
private under results/research/registry.sqlite; no FMEA sheet or reference was opened.
Historical workflow attempts not verified from metadata remain null; unknown parent
links and ambiguous old aliases are reconciliation findings rather than guesses.
These operational records are not a reconstruction of the Round 1 18-run judged study.

## Data and security checks

- Private SQLite/raw archives/validated items and sanitized snapshots are separate.
- Workflows, generation attempts and evaluations have distinct stable keys. No workflow
  conclusion becomes a fabricated FMEA, replicate or quality score.
- Evaluation acceptance is private CLI-only and requires an exact preview digest. Batch
  validation and run/model/version/row-count/receipt matching precede DB acceptance.
  Repeated evaluations do not overwrite prior results or inflate research sample size.
- Lifecycle/reviewer events are preserved separately; reviewer identity is not authenticated.
- GitHub tokens remain server-side environment values. Browser JSON contains no token,
  reference item IDs, private judge notes, raw FMEA text or private receipt paths.
- Supported REST endpoints replace scraping. Signed download redirects omit Authorization.
  ZIP consumers read only bounded receipt JSON members and use content-hashed local
  filenames, preventing archive path traversal. No worksheet contents are interpreted.
- The local financial subprocess accepts numeric assumptions, validates them in Python,
  and writes only ignored transient scenario files. It cannot dispatch models. Scenario
  changes do not mutate research observations; losses remain visible. No recorded invoice
  is represented by a zero-spending line when billing is absent.
- Last-good JSON is replaced only after validation and requested rendering. DB-accepted
  but unrendered updates are recoverable by offline refresh. SQLite transactions protect
  concurrent acceptance/snapshot consistency; lock contention is visible, not silent.
- V2/V3/V3-audit/V4 prompts, frozen archive and generation retry controls are preserved.
  No API keys, generated FMEA rows or protected outputs are staged or committed.

## Remaining gates

Authenticated artifact retrieval and actual GitHub-triggered execution of the new code
await an Actions-read credential and approved branch publication. Continuous hosting
needs an authorized persistent workstation/self-hosted private store and approved
sanitized endpoint. No public deployment is configured or claimed. Live V4 judging,
independent engineering validation and verified financial savings remain pending data.
The app runs locally without provider credentials; only billing-complete costs are measured.

## Preview locations

- results/v41-previews/01-mission-control.png
- results/v41-previews/02-experiment-explorer.png
- results/v41-previews/03-engineering-quality.png
- results/v41-previews/04-financial-analysis.png
- results/v41-previews/05-research-methodology.png
- results/v41-previews/06-presentation-mode.png
- results/v41-previews/mobile-mission-control.png
- results/research/exports/<snapshot-data-version>/poster.pdf
- results/research/exports/<snapshot-data-version>/*.png and *.pdf
- results/research/validated/analysis.xlsx

Architecture and commands: docs/v41-research-dashboard.md.
Metric definitions: docs/v41-metrics.md.
