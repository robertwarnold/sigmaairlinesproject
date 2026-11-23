# V4.4 executive UX and data clarity

Baseline: `feat/v43-executive-intelligence` at `f3dc385c7c40795e822fcef94f27e0349727e198`, identical to its fetched origin head. The original 16 audit branches were still present, alongside V4.3. V4.4 builds on the five-view Shiny application, Python analytics, and the [V4.3 data architecture](v43-executive-intelligence.md).

## Scope and evidence

The V4.3 desktop screenshot was captured with all systems selected. The mobile screenshot was captured after the browser test navigated through System B. The underlying counts reproduce the difference: V3 found 525 of 603 pooled opportunities across all systems and 117 of 126 in System B. Viewport width is independent of the filter inputs.

The shared scope strip lists applicable selections and independently identifies the contributing historical cohort. Executive coverage, the quality table and historical exports use the same `historical-comparison-1` projection, including system, round and skill. In that archive, Round 1 is V2.0 and Round 2 is V3.0. This mapping is specific to the archived study and should never be applied to an arbitrary execution receipt by skill version alone. Historical aggregates cannot be filtered by unavailable model, judge or execution dates. Financial projections use the research snapshot and the editable scenario inputs. Scenario exports retain that basis. Published judge and missed-reason totals need item-level denominators for system or date cross-sections.

## Experiment identity and timing

Stable run IDs remain the lookup keys. Exact manifest IDs enrich receipt metadata. Anchored conventions recover known system and replicate values from legacy aliases such as `batch:system_c_v2.0_run01`. A round requires an explicit manifest field or a recognized round-specific naming convention. Legacy recovery and pilot runs without verified round evidence show the known system and replicate with a round-unverified label. Conflicts are visible in details and display corrections may be supplied through `SIGMA_EXPERIMENT_MAPPINGS`. No display correction changes the original identifier.

The timing view uses median recorded generator duration by system and skill among successful timed rows in the same run selection as the registry. Group counts identify the denominator. The table includes model, status, judge availability and duration, with run-status selection and sortable order. Queue, model-only, and reviewer times require separate observations. GitHub workflow failures remain available in the workflow diagnostics.

## View changes

- Executive Overview opens with the measured coverage comparison, a prominent coverage metric, and three evidence-linked findings. The financial and time metrics are labeled modeled or estimated.
- Engineering Quality groups pooled denominators and unmatched counts ahead of judge agreement and missed reasons. Missing prerequisites use compact messages.
- Financial Impact leads with first-year net benefit and manual versus assisted unit costs. Cost composition is adjacent, with sensitivity, actual API spending, and provenance in disclosures.
- Data Explorer has a smaller default column set and distinct messages for an empty import and an empty filtered subset. The existing private access checks and append-only review controls remain the source of authority.
- Mobile navigation uses a native labeled view selector and the same URL fragments as desktop. Scope, record filters and browser history remain in the same Shiny session.

## Verification and limitations

Screenshots and test logs are stored in ignored `results/`. The prior `v43-*` captures remain available as before evidence. The `v44-*` captures preserve the all-systems scope across viewport sizes so values can be compared directly. The V4.3 mobile screenshot illustrates a different scope.

Arbitrary directory discovery, legacy workbook normalization, competing match editing and historical identifier-only validation remain open. The V4.4 coverage comparison remains historical. V4.0 and judge V1.2 and their provenance remain available. No timed usability study with representative chief engineers was run.
