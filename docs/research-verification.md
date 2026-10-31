# Research prototype verification — October 31, 2026

Working branch: feat/fmea-profiles-validation. All owners Unassigned.

## Tests and scope

61 tests passed on Python 3.12.14, including installed wheel/console execution outside
the checkout. All tests are offline. OpenAI and Anthropic adapters were exercised with
simulated HTTP transports: request schema, output parsing, usage preservation, incomplete
responses, forbidden ratings/approval fields, and absence of retries were tested.
No actual provider account, model availability, or paid request was validated.

Research tests cover baseline/improved guidance isolation, substantive-field completeness,
reviewed-only one-to-one reference matching, 24-job plans, smoke gates, changed-plan
rejection, cumulative paid-attempt caps using simulated providers, retained failed
responses, credential redaction, reference isolation and repeat batch execution without
repeating attempts. Prior converter/schema/export integrity regressions also pass.

The installed console test now additionally runs doctor, research draft, evaluate and
experiment plan. It uses no provider credentials or repository PYTHONPATH.

## Actual offline rehearsal

Location: results/research-rehearsal (ignored by Git).

- First smoke: 1 successful generation.
- Resumed batch: 24 attempted, 24 successful, 0 failures/uncertain attempts.
- Design: four author-created scenarios × three repetitions × baseline/improved.
- Python 3.12.14 generated and evaluated the sheets. Existing Python 3.13 analysis
  environment supplied matplotlib/numpy for standalone PNG/SVG figures.
- Outputs: experiment-results.csv, descriptive-statistics.csv, system-condition-means.csv,
  three comparison figures in PNG/SVG, analysis-summary.json and preliminary-findings.md.
- No reviewed references exist for these scenarios, so all missed-mode measures remain
  unavailable. The coverage figure states that no numerical result is claimed.
- The deterministic mock is not responsive to the guidance treatment. Its numbers are
  pipeline-check observations, not evidence of real AI quality or improvement.

## Remaining blockers and deadline plan

No OpenAI or Anthropic API key is configured in the development process. An explicit
accessible model ID and approval for one paid smoke generation are required. After
reviewing that smoke, approval for up to 23 additional calls enables the 24-sheet study.
The exact commands, cumulative attempt cap, output preservation, reference requirements,
and methods/limitations are documented in research-prototype.md.

All R scripts and original system_1.txt remain unchanged. Git exclusions cover credentials,
reference documents, environments, wheels, and generated outputs. git diff --check passes.
No commits, pushes or merges were made for this prototype work.
