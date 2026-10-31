# Four-dataset pilot amendment and reviewer notes

The user approved seven new real generations after choosing hydraulic, battery/DC,
NASA 2019 tilt-wing and NASA 2021 eQuad power as the four datasets. All owners Unassigned.

This replaces the *planned allocation* of the remaining seven calls, not the original
smoke evidence. The smoke run 41244305291 used the two-system/two-repeat plan at commit
9a44dab. Its original artifact, plan, request, response, metrics and state files are
byte-preserved under original-smoke/. The hydraulic baseline job is adopted without
editing its files or original plan hash. amendment.json links original and amended
plans, source versions, compatibility checks and the reused job ID.

Amended design: **4 systems × baseline/improved × 1 observation = 8 sheets**, comprising
the existing smoke plus at most seven new calls. There are no within-cell replications.
This is an explicitly post-smoke exploratory design amendment, not a preregistered
confirmatory experiment or the original 4×25×5 research study.

Inputs and profile selections:

| Dataset | Input file | Profile | Classification |
|---|---|---|---|
| Hydraulic actuator | hydraulic_actuator.json | General | Author-created scenario |
| Battery/DC power | battery_power.json | DFMEA | Author-created scenario |
| NASA 2019 tilt-wing | nasa_2019_tilt_wing_context.json | Aerospace | Architecture-only source summary |
| NASA 2021 eQuad power | nasa_2021_equad_power_context.json | Aerospace | Architecture-only source summary |

The NASA descriptions use architectural sections, not FMECA answer tables. Research
design, methodology guidance and candidate benchmark roles remain separate. No reviewed
reference modes are available: missed-mode percentage is unavailable, not zero. The
same requested Gemini model, temperature 0, token cap 8192, prompt/guidance versions
and reported modelVersion are required. No rating conversion, ground-truth claim,
statistical significance or autonomous engineering acceptance is asserted.

The amendment checks exact hydraulic input and baseline prompt, unchanged generation/
evaluation modules and common model/settings against the archived smoke. Sample-label
metadata was corrected to distinguish author-created from source-grounded cases.
The original execution source version and current source version remain documented.

Run the existing workflow with `mode=pilot_four_remaining`, `approved_calls=7`,
`smoke_run_id=41244305291`, `system=system_1` (unused by the fixed pilot config),
`model=gemini-3.8-flash`. The total attempt cap is eight including the adopted smoke.
No automatic retry, workflow rerun or extra model fallback is allowed.

Artifacts: `fmea-pilot-RUN_ID` under the new workflow run. Read README.md, this file,
amendment.json and the final analysis directory first. Compare per-system pairs;
condition-level averages combine heterogeneous systems and are descriptive only.
Prompt contents, inputs, raw responses, usage, validation flags and output files are
available per job. All generated causes/effects/actions still require human review.

The user's publication authorization permits committing this experimental evidence
under research_results/ after integrity and credential checks. Do not commit .env,
API keys, GitHub tokens or complete reference PDFs. Results are preliminary AI drafts,
not approved engineering analyses.
