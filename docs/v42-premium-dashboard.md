# V4.2 premium workspace redesign

Starting point: `30f7783bdc618521c3994546c67c82b44a4481df` on
`feat/fmea-skill-v4-research-dashboard`. This extends the chart refactor and visual
audit; the Shiny application and Python research platform were retained.

## Visual changes

- Shared charcoal palette, consistent sans typography, compact navigation, restrained
  dividers and one cool accent. `dashboard/theme.R` supplies colors to HTML/SVG,
  academic plots and the poster PDF. `DESIGN.md` records the active design system.
- Mission Control has four KPIs, one activity chart, a five-system progress summary
  and recent runs. Registry totals are labeled across all versions. Current Round 2
  missed rate is Pending without an accepted matching cohort; historical 31.4% is
  available separately, never used as the current rate.
- Explorer has seven primary columns, ten records per page, readable timestamps,
  collapsed filters and selected-run metadata. Selecting a recent run opens its
  matching Explorer detail. Mobile tables become labeled record lists.
- Engineering Quality prioritizes evaluated runs, then version comparison. Pareto,
  conditional agreement, completeness and raw inference details are expandable.
- Finance has four modeled/measured outcomes and Cost comparison, Monte Carlo,
  Sensitivity and Assumptions tabs. Inputs and Reset are in the dedicated assumptions
  view. Negative scenarios and the supplied 95% simulation interval remain visible.
- Methods has seven short sections with extended evidence/definitions on demand.
- Presentation has a 16:9 focus canvas with two ggplots, research question, results,
  data, method and discussion. Navigation disappears while presenting; Escape restores
  the workspace. PDF export and presenter notes remain available within this view.

Removed from primary screens: global poster controls, expanded provenance grids,
eleven-column tables, large report-style page headings, permanently expanded
statistical objects, six simultaneous financial figures and the historical-quality
fallback on the landing KPI. These capabilities and source values remain accessible.

The existing native chart layer remains. Added individual selected-evaluation activity
markers using existing accepted-at timestamps; no workflow successes become FMEAs.
Web poster annotations that repeated the results text were removed from the web-only
profile, and narrow-screen category labels now wrap. Academic export annotations and
statistical inputs remain intact. No Plotly or new frontend dependency was added.

## Current experiment and provenance

`SIGMA_DASHBOARD_MANIFEST` points to an existing V4 experiment manifest. Default:
`results/v4/round2-plan/experiment_manifest.json`. `workspace.R` validates its run IDs,
systems and version, then matches exact registry identities. Repeated workflow
attempts do not become extra experiment replicates. Missing/invalid manifests produce
Unknown progress, not assumed denominators. Plan readiness remains available in detail.

The current local plan contains four runs per system and unconfirmed model/settings.
No matching completed V4 generations or accepted evaluations are present. The registry
still has 14 historical attempts, eight successful generations, six failures and eight
awaiting judge. The 30 workflow records reflect the earlier partial/rate-limited sync.
These records are separate from the historical 18-run V2 report.

The landing current-rate field displays an existing Python per-version pooled rate
only when the accepted V4 cohort belongs to the selected manifest. It does not compute
a new subset rate; incompatible or absent cohorts remain Pending. Full research
statistics stay in Engineering Quality, with their existing cohort definitions.

## Screenshot-driven validation

Local comparison gallery: [results/v42-previews/index.html](../results/v42-previews/index.html).
It links the original V4.1 six-view screenshots, first-pass captures, final viewport/
full-page captures and supplemental financial/presentation previews. Artifacts are
ignored and are not publicly published by this commit.

All six views were rendered and visually inspected at 1920x1080, 1440x900 and
390x844. First pass: 18 full-page screenshots. After corrections: 18 viewport and
18 full-page screenshots. The final matrix had zero Shiny output errors and no
horizontal document overflow. These are browser viewport checks, not physical-phone
or cross-browser accessibility certification.

Corrections driven by screenshots included:

1. Aligning the two-line brand without increasing desktop navigation height.
2. Reducing empty-state and comparison spacing without concealing pending data.
3. Replacing the financial unavailable-cost label with compact Unknown wording.
4. Removing repeated long text from the narrow web coverage figure and wrapping Pareto labels.
5. Eliminating the focus canvas's inherited horizontal padding, which initially
   caused overflow; the verified laptop focus canvas is 1440x810 with navigation hidden.

![Final Mission Control](../results/v42-previews/laptop-mission-control-viewport.png)

![Mobile financial workspace](../results/v42-previews/mobile-financial-analysis-full.png)

![Presentation focus](../results/v42-previews/laptop-presentation-focus.png)

The focus layout and Escape recovery were verified. The automation browser did not
enter native browser fullscreen; the native Fullscreen API request is retained and
depends on browser permissions/user activation. The application focus layout works
even when that request is denied.

## Tests and integrity

- **209 Python tests passed**, covering registry compatibility/idempotency, judge
  validation and rollback, GitHub retry/rate-limit/missing-artifact behavior, existing
  statistics and financial calculations. Synchronization was tested offline with
  fixtures; no fresh live GitHub synchronization or paid model request was made.
- **70 R assertions passed**, including baseline/pending separation, plot rendering,
  scenario/reset, retained export behavior, exact manifest identity matching,
  current-rate Pending behavior, and snapshot refresh into evaluated charts.
- The new refresh test uses explicitly synthetic accepted records: valid updates
  change chart data; a subsequent corrupt update retains the last good evaluated
  state. Synthetic data never enter the real dashboard snapshot or preview findings.
- Browser interactions verified page two with four records, search returning only
  matching system E records, correct selected-record drill-down, financial analysis
  tabs, a negative scenario and reset to baseline, manual refresh, focus and Escape.
- Academic export regenerated 12 PNGs, 12 figure PDFs and one poster PDF. Historical
  aggregates, confidence-interval methods, ANOVA and financial assumptions were unchanged.
- Protected calculation modules, prior preview artifacts and the sanitized current
  snapshot retained their audit-time hashes. The public-facing app reads sanitized
  JSON; it neither opens reference worksheets nor writes to the live SQLite registry.

R emits existing locale/package-build and fallback-cache warnings on this workstation.
The browser's missing-favicon resource error is unrelated to Shiny output rendering.
`git diff --check` and the supplementary source design detector passed; visual
acceptance is based on rendered inspection rather than the detector alone.

## Run locally / export

From repository root in PowerShell:

```powershell
# Optional: point at an existing approved experiment plan.
$env:SIGMA_DASHBOARD_MANIFEST = 'results/v4/round2-plan/experiment_manifest.json'
Rscript -e ".libPaths(c('.venv/r-library',.libPaths())); shiny::runApp('dashboard',host='127.0.0.1',port=5392,launch.browser=FALSE)"

.\.venv\gemini\Scripts\python.exe -m unittest discover -s tests -q
Rscript dashboard/tests/run.R
Rscript dashboard/export.R results/research/current.json results/v42-previews/academic
```

If the private manifest is absent, use the existing preparation command in
[the V4 runbook](v4-research-platform.md) after confirming settings. Do not replace
the missing manifest with guessed run identities. The existing synchronization,
registry and judge-import commands in [the V4.1 guide](v41-research-dashboard.md)
remain unchanged. Accepted imports continue through the existing atomic snapshot
pipeline; Shiny checks the snapshot every 30 seconds or on Refresh data.

Remaining limitations: no real accepted V4 research results, incomplete historical
GitHub synchronization, unknown invoices, unconfirmed experiment settings and
engineering approval still required. Narrow layouts scroll vertically through record
lists and academic reading content. No new significance or verified-savings claim is made.
Nothing was pushed, merged, deployed or run against paid models.
