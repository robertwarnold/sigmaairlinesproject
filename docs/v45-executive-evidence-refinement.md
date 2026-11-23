# V4.5 executive intelligence and evidence

V4.5 starts from `feat/v44-executive-ux-refinement` at `a82e999a6fb8bec27243f2d7c6f386d3108e51ac`. Remote branches were fetched before branching. This release uses `feat/v45-executive-evidence-refinement` and retains the five-view Shiny session, URL history, shared filters, and private engineering workstation.

## Visual comparison

The supplied collage guides the navy header, active navigation, light surfaces, compact cards and the visual order of each view. The Executive screen mirrors its conclusion banner, two-thirds coverage panel, supporting KPI column and three-part decision. Quality puts the Pareto beside ranked findings by default. Experiments pairs a grouped timing chart with recent records. Financial pairs a reconciled cost comparison with scenario results. Explorer uses separate real states for empty and populated sessions. A native view selector and a compact Actions disclosure replace the desktop navigation on mobile.

The scope strip sits below the header to accommodate real cohort names and filters on small screens. The chart uses stacked operating cost components because the model calculates an assisted cost composition, rather than incremental reductions from the manual cost for each activity. Fixed costs contribute to first-year net benefit and are excluded from the operating cost bar. The comparison table uses the selected assumptions as the center case and varies matched-item review, missed-item reconstruction, and extra-row review by 25%. Existing presets remain available to set the inputs.

## Evidence labels

- Executive coverage is computed from the archived comparison. The displayed gain is the difference of pooled proportions. Counts and denominators come from the same selected cohort.
- The available historical Pareto represents the V2 report, including 232 missed opportunities. Its source is displayed on both the chart and the ranked findings. The V3 run-level aggregate has no reason classifications. The dashboard shows an unavailable state for filters the published Pareto cannot support.
- Judge repeatability is reported historical trial agreement. Independent accuracy is unverified. The UI does not convert repeatability to an accuracy estimate.
- Operational timing counts registered attempts separately from the historical evaluation cohort. Successful timed attempts contribute to the median. A missing run round remains unverified.
- Current dispositions are rendered from the latest stored review state. Their previous versions and judge links remain in the private register. A synthetic local fixture is visibly labeled in the populated capture.

## Verification and open evidence

Baseline V4.4 screenshots and V4.5 screenshots under ignored `results/` use the same all-systems historical selection. The populated explorer capture comes from a labeled synthetic fixture. Results, logs and screenshot archives remain local.

The browser test checked five views across 1440, 1024, 820 and 390 pixels. A System B, Round 2 drill-down reproduces 92.9% coverage on both Executive and Quality, including after switching views on mobile. The summary outputs stay reactive while their route is hidden to prevent a previous cohort from flashing on return.

Historical item-level reason drill-down requires a human-prepared identifier-only export. Scenario estimates require paired engineering labor records to validate actual savings. Historical workbook normalization and editing competing judge matches remain open. The active V4.0 generator, V1.2 judge, receipt verification and append-only review workflow retain their existing meaning. The 30–60 second comprehension target requires a timed study with representative users.
