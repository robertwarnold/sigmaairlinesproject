# V4 offline verification record

November 15, 2026. No paid calls, pushes or deployments.

- Full Python suite: 193 tests passed in 67.491 seconds; results/v4-release-tests.log.
- Final targeted V4 suite: 13 tests passed after making preserved-skill hash assertions
  independent of deep Git history (works in shallow CI checkouts).
- R tests: 16 assertions passed, including data validation, valid/invalid refresh,
  baseline-only mode, both plots, PDF export and Shiny testServer startup/rendering.
- All workflow YAML parsed; Python compilation and git diff whitespace checks passed.
- Impeccable detector: no findings on dashboard app/CSS.
- Browser: local app starts at 127.0.0.1:5384, poster and live-results tabs render with
  no Shiny output errors; desktop 1920x1080 and mobile 390x844 examined.
- Populated plot/inference path exercised with 60 SYNTHETIC_TEST_ONLY observations
  under results/v4-synthetic-validation; never counted as research results.
- Real research inputs: user-supplied report aggregates only; no actual judged
  source-run records imported and no actual V3/V4 evaluations executed.

Local deliverables (all ignored, not public):

- results/research/v4-final-readiness/dashboard.json
- results/research/v4-final-readiness/validated/analysis.xlsx
- results/research/v4-final-readiness/validated/statistical_results.json
- results/research/v4-final-readiness/presentation/poster.pdf
- results/research/v4-final-readiness/presentation/coverage.png and pareto.png
- results/research/v4-final-readiness/presenter-notes.md
- results/v4-presentation/dashboard-desktop-final.png
- results/v4-presentation/dashboard-mobile-final.png
- results/v4/round2-plan/experiment_manifest.json (preparation SHA; regenerate after commit)

Windows emitted locale and package-minor-build notices; the R checks passed. Current
R dependencies tested: shiny 1.14.0, ggplot2 4.0.4, bslib 0.12.0, jsonlite 2.0.0,
testthat 3.3.2 on R 4.6.1. These notices were not suppressed to disguise failures.

Remaining gates: historical source records/conditions, curated independent inventories,
unchanged private judge runner, human validation, paid-pilot authorization, branch-push
approval, durable hosted private storage and permanent approved sanitized endpoint.
Local cumulative updates and offline export work; hosted cumulative publication is
prepared but remains unconfigured and unexecuted. No efficacy claim is supported yet.
