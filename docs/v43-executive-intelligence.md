# Sigma Airlines V4.3

## Baseline audit

Development starts at `6f8dd6d` on the local `feat/fmea-unified-analytics` branch. Its parents include `78f3c81` and `2a163cb`. The refreshed origin contains the same 16 heads and SHAs in the [remote audit](fmea-remote-branch-audit.md). The premium dashboard head is `543321246beedb011b88cb7949d12eb795a15877` and main is `1fc9630b729008ccda959dad7cd7dc75ea64b9c0`. The integration branch was local at fetch time.

Shiny and bslib render the application. Research and engineering retain their existing SQLite stores. Generation receipts bind input, inventory, skill and produced files to their hashes; the GitHub workflow keeps generated artifacts for 14 days. The research refresh workflow remains receipt-driven and publishes a sanitized projection. Generated rows remain in the private engineering workspace. The two versioned financial reports indexed in `reports/financial_impacts/index.json` are preliminary V2 analyses. Their observations and the current editable financial scenario have different evidence bases.

## Workspace

Run `Rscript dashboard/run_private.R` for the loopback-only workstation. The existing aggregate launcher serves the same navigation with private actions and records gated. The URL fragment identifies one of five views. Changes to view, including browser back and forward, share the same Shiny inputs. Summary links open Engineering Quality, and system links carry the selected system into the experiment registry. Generation metadata opens in an expandable panel with a link to the private row explorer.

Import the human-prepared study comparison with `python -m analysis.research import-historical --file <archive>`. Executive and quality coverage show pooled observed opportunities identified. The experiment comparison preserves pooled missed rates, unweighted run means and equal-system descriptive means separately. The archived counts, rather than displayed rounding, determine each rate. The source hash is included in the historical CSV export. Global system and skill filters also apply to this aggregate. Historical data cannot support run, model or date selections where those attributes are absent.

## Experiment identity

`dashboard/experiment_identity.R` resolves explicit receipt fields first and anchored historical naming patterns second. It retains source identity, filename and known workflow provenance. A disagreement in system, round or replicate is reported in the experiment details. Missing system or round yields an unresolved label. The configuration at `dashboard/data/experiment-mappings.json` supports display-only system labels, anchored parsing rules and per-stable-ID corrections. A workstation operator can point `SIGMA_EXPERIMENT_MAPPINGS` at a reviewed local JSON copy. The aliases object maps a stable ID to optional `system`, `round` and `replicate` values. No correction mutates a run ID or original source artifact.

## Evidence ingestion and review

The private Sync GitHub action collects the original ZIP members matching the generator receipt filename family and verifies declared byte lengths and hashes. Original bytes live under ignored `results/research/private/registry-raw`. The SQLite artifact entry retains workflow, member, generation and content identifiers. The workbook and CSV bytes are preserved where receipt-bound. Structured V4 JSON responses with an accompanying hash-matched inventory can also enter the engineering workspace. Use `python -m analysis.research sync --branch <branch> --engineering-database results/engineering/workspace.sqlite --no-render` for the same path from the command line.

The private workspace projects judge links after resolving the exact generator attempt and matching response provenance. Distinct trials and multiple reference identifiers can link to one row. Reviewer dispositions are append-only versioned corrections. A lack of a verified link means no link can be displayed, and never implies an incorrect generated row. Use `Unresolved` or `Insufficient evidence` when the available evidence does not settle a disposition. V1.2 judging and the active V4.0 generator remain available for controlled comparisons. The candidate diagnostic pass is opt-in through `standalone_v4.py --candidate-review` with an existing response and inventory. It adds review candidates for repeated-unit gaps, potential overlaps, causal separation and severe end effects. It makes no model calls and leaves baseline validation criteria intact.

## Metric and financial basis

| Metric | Numerator and denominator | Basis and limits |
|---|---|---|
| Pooled historical coverage | Found opportunities / all reference opportunities | Historical comparison, grouped by system and skill as available. Multiple opportunities may point to one row. |
| Unweighted missed rate | Mean of individual run missed proportions | Equal weight for each run; opportunity counts can differ. |
| Equal-system missed mean | Mean of system run means | Equal weight for each represented system; descriptive. |
| Historical review burden | Sum of unmatched generated rows / evaluated runs | Unmatched rows include valid additional coverage and unresolved cases. |
| Judge field agreement | Scorable matched opportunities satisfying the specified criterion / all scorable matched opportunities | Snapshot cohort by skill. The V1.2 criteria and field denominators remain in the existing research validator. |
| Judge repeatability | Historical reported agreement across trials | An independent accuracy estimate requires separate adjudication. |
| Modeled engineering time | Manual hours minus modeled human activity hours, per FMEA | Excludes machine latency; uses editable scenario inputs. |
| First-year modeled net benefit | Annual manual workflow cost less annual assisted workflow cost, maintenance and implementation | `analysis.research.finance` with the existing financial impact cost model. Complete paired labor evidence is pending. |

The Financial Impact view provides baseline, conservative and optimistic starting assumptions. The presets scale the review and reconstruction effort inputs. The current assumptions, formulas, source periods, and data basis accompany the results. CSV and text exports describe the current scenario. Pilot API estimates and planning inputs are separate from invoices, and unknown billing remains unknown.

## Limitations and follow-up

- Raw synchronization covers receipt-bound workflow artifacts. Arbitrary branch directories and legacy workbook rows still require reviewed adapters and a trusted source manifest.
- Historical reference worksheets remain human-only. Request identifier-only opportunities and trial outputs for independent accuracy, current repeatability and historical item-level drill-down.
- Timing comparisons use recorded per-attempt durations with system and skill labels. Queue and per-stage labor distributions require separate instrumentation.
- The register supports reviewer dispositions and provenance-backed matches. A dedicated candidate-match adjudication editor with alternative match edges remains open.
- Aggregate judge field agreement uses the published cohort grouped by skill. System-level denominator detail and confirmed disposition aggregation need additional projections.
- Candidate diagnostics need an independently evaluated paired study before any prompt change or quality improvement claim. Paired accepted work logs and complete billing evidence are needed before claiming measured savings.
