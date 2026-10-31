# Sigma Airlines preliminary real-model pilot: reviewer guide

Status: prepared locally, not yet published or executed. All owners Unassigned.
No paid call, commit, push or merge is authorized by this preparation step.

Offline verification: **71 tests passed on Python 3.12.14**. The eight-generation mock
rehearsal completed 8/8 successfully and produced per-run CSV/JSON, metadata, metrics,
plots, report, reviewer README, reproduction source and verified checksums under ignored
results/eight-pilot-rehearsal. These are rehearsal artifacts, not authentic new model
results. The existing single-shot generator, R baseline and source text inputs remain
unchanged. git diff --check passes.

## What is operational now

At inspected GitHub main commit `03570b6977593f3ed0d0502b1f4326044de361bf`, the actual
workflow is **Generate FMEA with shared Gemini key**, `.github/workflows/generate-fmea.yml`.
It is manually triggered, not triggered by pushes/PRs. Existing inputs are `system`
(`system_1` or `system_2_nasa_fmeca`) and `model` (default `gemini-3.8-flash`). It uses
Gemini only; the Python default model differs if called locally without --model.
The only repository Actions secret listed during inspection was **GEMINI_API_KEY**.
Secret values were never retrieved or printed. The built-in GitHub token is used only
for repository/artifact access, not for Gemini generation.

One historical run, 41240962202, completed successfully. It is evidence that the
single-shot workflow ran, not evidence of a controlled baseline/guided experiment.
Its artifact contains CSV and raw text, retained 14 days. The legacy generator forces
provisional 1–10 estimates and computes an RPN; those estimates are not validated
engineering ratings. Do not combine them with the unrated canonical pilot as one study.

## Minimal prepared extension

The existing workflow retains `mode=single` and its original system/model path. Added
pilot modes reuse the already implemented canonical research runner and reporting.
There is no new application, UI, vector database, or LLM evaluator.

**These added inputs do not exist on GitHub until the changes are approved and pushed.**

| Workflow input | No-call preview | First paid smoke | Seven remaining calls |
|---|---|---|---|
| mode | pilot_plan | pilot_smoke | pilot_remaining |
| approved_calls | 0 | 1 | 7 |
| model | gemini-3.8-flash | gemini-3.8-flash | gemini-3.8-flash |
| system | system_1 (ignored by pilot) | system_1 (ignored by pilot) | system_1 (ignored by pilot) |
| smoke_run_id | empty | empty | successful pilot_smoke run ID |

Select the same frozen branch/source commit for smoke and continuation. Do not change
source/config/prompt files between them. Continuation restores the smoke artifact and
verifies source commit, frozen plan, smoke success and model identity. Run attempts
greater than 1 are blocked; do not use GitHub's rerun button for paid pilot jobs.

Config: examples/research/pilot-eight.json. Two systems (hydraulic actuator and
battery/DC power), two repetitions per condition, baseline and improved, eight planned
generations. Seed 1 makes the first job hydraulic/baseline/repetition 1. Smoke counts
toward the eight; continuation reserves at most seven new calls, cumulative cap eight.
Both conditions use the same requested Gemini model, temperature 0 and 8,192 output-
token cap. No automatic retries or fallback model. Actual modelVersion and all token
usage fields are retained; a version change halts the comparison. The stable model
name is pinned in config, but is not a provider guarantee of immutable model weights.

Budget boundary: one call first; after inspection, separately authorize up to seven
additional calls. At most 65,536 capped output/reasoning tokens for the eight calls,
plus input token charges. No currency estimate or free-tier assumption is made.
Quota/model access is confirmed only by the explicitly approved live smoke.

## Experimental scope and original research design

The original research design is 4 systems × 25 replications × 5 versions (up to 500
sheets), with a generated FMEA sheet as one observation. This initial 2 × 2 × 2 pilot
is a reduced feasibility demonstration, not completion of that study or a powered
effectiveness test. Pair order is frozen. No statistical significance or Cpk is claimed.

The initial hydraulic and battery descriptions are the existing author-created research
scenarios, not professional reference systems or validated NASA benchmarks. NASA-derived
architecture descriptions are prepared separately for follow-up, outside this eight-call
budget. They must be independently checked before larger comparisons.

## Source roles and leakage boundary

| Source | Role | Excluded from generation |
|---|---|---|
| Research_design_Sigma Airlines.docx | Research question, sheet-level observation, proposed 4×25×5 study | No automatic launch of full study |
| FMEA_AI_Literature_Review_Draft.docx | Background and candidate methodology/evaluation ideas | Unverified literature claims are not scoring rules |
| GSFC-HDBK-8004 (2024) and ASQ public guidance | Methodology summaries for improved condition | No source-system benchmark answers or proprietary rating tables |
| NASA/CR-2019-220217 | Architecture context from sections 1.3 and 5.1; separate candidate benchmark material in Appendix B | FMECA mode/cause/effect answers and criticality data |
| NASA/CR-20210017188 | Architecture context from sections 11.1–11.1.1; separate candidate benchmark material in report appendices | FMECA/fault-tree answers, probability and severity reference values |

Prepared follow-up inputs: examples/research/nasa_2019_tilt_wing_context.json and
nasa_2021_equad_power_context.json. They paraphrase architecture and intended functions,
not worksheet answers. For 2021, printed 93–94 corresponds to PDF pages 108–109. The
concept battery-pack distribution is described without copying its analyzed failures.
For 2019, use the existing source-grounded system-description adaptation at printed
2 and 29–30. Full reports stay in ignored reference_materials and are never uploaded
as generator context. The local two-row conversion candidate stays isolated in tests.

No reviewed reference modes exist for the two initial scenarios. Missed-mode percentage
must be unavailable, not zero. Unreviewed conversions are never validated ground truth.
If references are later independently reviewed, evaluate them separately using a stated
eligible denominator and adjudicated aliases; do not silently change this campaign.

Public source links for independent inspection:

- NASA 2019: https://ntrs.nasa.gov/citations/20190026443
- NASA 2021: https://ntrs.nasa.gov/citations/20210017188
- NASA methodology handbook: https://standards.nasa.gov/node/12367
- ASQ public overview: https://asq.org/quality-resources/fmea
- Gemini request/response fields: https://ai.google.dev/api/generate-content

## Artifact location and inspection

GitHub Actions > this workflow > selected run > **Artifacts**:
`fmea-pilot-RUN_ID`, retained 14 days. Download and unzip; start with README.md.
The run Summary also reports planned/attempted/successful/failed counts and links users
to the artifact. `single` keeps the existing `fmea-results-RUN_ID-RUN_ATTEMPT` artifact.

The pilot bundle includes per-sheet canonical JSON/CSV and manifests, exact input and
prompt/guidance snapshots, raw API response, token/model metadata, timing, metrics,
consolidated CSV, descriptive statistics, PNG/SVG plots, preliminary-findings.md,
source-role notes, reproduction source, and checksums. Failed/uncertain attempts remain
visible; no replacement sheet is fabricated. The smoke bundle contains just one real
sheet and cannot support a two-condition comparison yet. The final bundle retains it
alongside up to seven additional sheets.

Structural completeness measures populated content cells, not technical correctness.
Ratings remain null under preliminary unrated profiles; no engineering sign-off is
generated. Reviewer identity and source evidence truth still require human judgment.
Generation and analysis are distinct from deterministic FMECA-to-FMEA conversion.

## Reproduce after approval

```bash
gh workflow run generate-fmea.yml --ref FROZEN_BRANCH -f mode=pilot_plan -f approved_calls=0 -f system=system_1 -f model=gemini-3.8-flash
# Only after approval for ONE paid call:
gh workflow run generate-fmea.yml --ref FROZEN_BRANCH -f mode=pilot_smoke -f approved_calls=1 -f system=system_1 -f model=gemini-3.8-flash
# Inspect successful smoke, then obtain separate approval for SEVEN additional calls:
gh workflow run generate-fmea.yml --ref FROZEN_BRANCH -f mode=pilot_remaining -f approved_calls=7 -f smoke_run_id=SMOKE_RUN_ID -f system=system_1 -f model=gemini-3.8-flash
gh run download RUN_ID --dir results/github/RUN_ID
```

Do not commit real keys, .env, full PDFs or unreviewed output as approved engineering
content. The current step only prepares code, source roles and offline validation.
Publication and actual AI generation require the user's separate explicit approval.
