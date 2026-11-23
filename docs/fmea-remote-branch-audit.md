# Remote branch audit

Git fetch with prune was run against origin. Ahead and behind are commit counts relative to origin/main. Evidence inspection used code, documentation, workflow metadata and the human-prepared comparison CSV.

| Remote branch | Head SHA | Behind | Ahead | Functionality | Paths | Integration action |
|---|---|---:|---:|---|---|---|
| origin/chore/fmea-v2-clean-integration | `64f43af679a091fc3fc047d6e6cad7bb1ec34b19` | 31 | 4 | Standalone V2 cleanup | fmea_generator.py, skill/fmea_instructions.md | Review prompt lineage only |
| origin/feat/automatic-experiment-metrics-20261102 | `6a745cc70183cb54786f3eff329e6a03efe4b5ce` | 11 | 0 | Offline experiment metrics | tests/test_experiment_metrics.py | Reuse main lineage |
| origin/feat/fmea-b-e-live-pilot | `6a355c7f6291cbbad5a27ab7350f78512ba53550` | 21 | 0 | B–E timing and preliminary financial study | analysis/financial_impact/ | Retain as separate preliminary evidence |
| origin/feat/fmea-financial-impact-analysis | `f1d79b6c0c69a4297a849a13f75985794c6f6089` | 26 | 0 | Versioned financial reports | analysis/financial_impact/ | Preserve separate measurement policy |
| origin/feat/fmea-foundation | `64d360af1dcfdd1f302cee89951ac633b5af1b90` | 43 | 0 | Offline validation foundation | src/sigma_fmea/ | Preserve separate canonical pipeline |
| origin/feat/fmea-profiles-validation | `5a1cf4d2a1f026373d7acdb643940d1d93c3240e` | 34 | 0 | Profiles and candidate validation | src/sigma_fmea/, tests/test_profiles_and_candidate.py | Reuse offline validation patterns |
| origin/feat/fmea-skill-v2 | `dfebac1c1b254d44fda7ca30bbc162495197260a` | 31 | 3 | V2 workflow and hygiene | .github/workflows/generate-fmea.yml, skill/fmea_instructions.md | Preserve historical treatment |
| origin/feat/fmea-skill-v3 | `e143ec44e9af3d302fe590a324eee8c5aa1e04b5` | 2 | 0 | V3 generation and version-independent tests | fmea_generator.py, skill/fmea_instructions.md | Compare workflow with dashboard baseline before merging |
| origin/feat/publish-fmea-figures-20261102 | `e428fc4906d6906cd1f7b06690beb27c9326b2cc` | 7 | 0 | Aggregate figures | reports/, tests/test_experiment_metrics.py | Keep aggregate reports separate from research rows |
| origin/feat/single-run-replicates | `57eb6c500a85ed1a3cb2939826dd8caa2df17d88` | 4 | 0 | Single-run replicate workflow | .github/workflows/generate-fmea.yml | Keep dispatch and run identifiers intact |
| origin/feat/system-a-five-replicates | `ac025e157a8b5ddedb2d2b9dcb10aa21b5387162` | 29 | 0 | Controlled System A pilot | tests/test_system_replicates.py | Maintain distinct study cohort |
| origin/feat/v42-premium-dashboard | `543321246beedb011b88cb7949d12eb795a15877` | 2 | 4 | V4.2 Shiny presentation and V4 runner | dashboard/, standalone_v4.py | Inherit through single-page descendant |
| origin/feat/v42-single-page-analytics | `15befe5717aff570478d3a81baeb95095a2b7c02` | 2 | 8 | Light one-page UI and private engineering register | dashboard/single_page.R, analysis/engineering/ | Use as feature baseline |
| origin/fmea-ce-recovery-20261101 | `5db3550d92b6d2a7e480ecfe927334d6faa0a15e` | 12 | 0 | C–E recovery and reconciliation | .github/workflows/recover-fmea-systems.yml | Preserve attempt identity |
| origin/main | `1fc9630b729008ccda959dad7cd7dc75ea64b9c0` | 0 | 0 | Merged V3 and replicate lineage | .github/workflows/generate-fmea.yml, fmea_generator.py | Use as comparison reference |
| origin/wip/fmea-interrupted-review | `b4f9ac3ad9949cadb798b137efe4efeb47a4509d` | 33 | 0 | Interrupted pilot | tests/test_pilot_workflow.py | Keep incomplete observations out of controlled comparisons |

The premium head is an ancestor of the single-page head. The current feature branch starts from the single-page head to carry forward the private engineering register. Its registry and engineering store are both SQLite, with dashboards reading a sanitized JSON snapshot or an explicitly enabled private workspace projection. The retained historical R generation scripts and canonical Python package represent separate pipelines. .github/workflows/python.yml and dashboard-tests.yml cover offline backend and Shiny checks. research-refresh.yml builds dashboard projections.

The public GitHub Actions API reported 64 runs for generate-fmea.yml and 70 repository-wide artifact listings at review time. This count includes metadata and cannot establish download availability or artifact contents. The server sync registers run attempts and execution receipts and honors expiration. Historical workbooks and source reference files were left unopened. A merged branch can still have operational evidence in Actions even when it has zero commits ahead of main.
