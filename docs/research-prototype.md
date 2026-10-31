# SYSEN 5300 preliminary-results prototype

Deadline: November 1, 2026, evening (America/New_York). This prototype prioritizes a
working, inspectable research loop. All task owners remain Unassigned.

## Setup and provider status

Python 3.12 is the target runtime. No SDK is required for generation: both OpenAI
Responses and Anthropic Messages use the Python standard library. The offline mock
remains available. A model ID must be selected explicitly; account/model availability
is established by the approved smoke call, not assumed from a model name.

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -m sigma_fmea doctor
```

Set OPENAI_API_KEY or ANTHROPIC_API_KEY locally in the process environment using your
secret manager or shell. Never put a real key in a command shared with others, Git,
an experiment config, or chat. The CLI reports presence only. `.env` is ignored but
is not automatically loaded. Credentials were absent in the development process;
no real provider request or paid smoke/batch was made during implementation.

Optionally install an editable package and plot support:

```powershell
python -m pip install -e ".[analysis]"
```

Package installation can need internet access. Generation/evaluation core has no
third-party runtime dependency. Plotting requires matplotlib/numpy; existing analysis
environments can run `analyze` with PYTHONPATH pointing to src. CSV/report generation
also works with `--no-plots` and only the standard library.

## Four input systems and reference status

| File under examples/research | System | Profile |
|---|---|---|
| hydraulic_actuator.json | Hydraulic actuator circuit | General |
| battery_power.json | Battery/DC supply | DFMEA |
| cooling_loop.json | Equipment liquid cooling loop | General |
| assembly_process.json | Sensor-module assembly process | PFMEA |

All four are author-created research scenarios, version scenario-1. They are usable
structured engineering inputs, not independently validated operational systems or
the four NASA cases originally envisioned. The scope, functions, interfaces and
assumptions are frozen in each file. Do not present them as professional ground truth.
The original R demonstration input is preserved unchanged.

No reviewed failure-mode reference set currently exists for these scenarios. Therefore
missed-mode percentage is unavailable until an engineer reviews an eligible reference
set. `reference_modes.template.json` is an unreviewed empty template, never generation
context. The separate two-row NASA conversion candidate remains unreviewed and is not
reference data for these systems. Generation refuses reference/benchmark/fixture paths.

Optional references belong in ignored data/benchmarks, with system_id, reference_version,
review_status=reviewed, reviewer, reviewed_on, scope, and nonempty modes containing
reference_id/item/mode/accepted_aliases. They are referenced only in the experiment
config's separate references dictionary, never in engineering descriptions. Merely
editing a review label is not independent engineering validation.

## Experimental conditions and traceability

Baseline uses minimal FMEA drafting instructions. Improved adds profile-specific steps,
scope/review prompts, and the small allowlisted ASQ/NASA/team-policy guidance corpus.
The corpus contains original summaries, no proprietary scoring tables or benchmark
answers. There is no vector database or filesystem-wide retrieval. Each generation
preserves the exact selected guidance, prompts, input version/hash, model settings,
profile version, response/model identity, usage where returned, timestamps and elapsed
time. Guidance versions, corpus hash, source-code hash, paired order and plan hash are
frozen. No standards-compliance claim is made.

Generated causes, effects and actions remain hypotheses. Source provenance is granted
only to literal item/function matches in supplied structured context. Current controls
are not fabricated: absent verified controls remain unknown. S/O/D/RPN stay null under
the selected unrated profiles. This is an FMEA draft; FMECA conversion remains separate.

## Offline rehearsal (safe to run without API keys)

Use new output directories; completed analyses are not overwritten.

```powershell
python -m sigma_fmea experiment --config examples/research/experiment.json --provider mock --output results/research-rehearsal --mode plan
python -m sigma_fmea experiment --config examples/research/experiment.json --provider mock --output results/research-rehearsal --mode smoke
python -m sigma_fmea experiment --config examples/research/experiment.json --provider mock --output results/research-rehearsal --mode batch
python -m sigma_fmea analyze results/research-rehearsal --output results/research-rehearsal/analysis
```

The plan has 4 systems × 3 repetitions × 2 conditions = 24 sheets. The smoke is the
first frozen job and counts toward the 24; batch resumes the remaining 23. Pair order
uses a frozen seed. The mock is not guidance-sensitive: its comparisons prove pipeline
operation only. Every mock result, chart and report is labeled offline rehearsal, not
real LLM findings. No numerical improvement from mock data is evidence of effectiveness.

## Real-provider single-generation demonstration

Replace YOUR_MODEL_ID with an explicit accessible model ID; do not type a key here.
Run the paid command only after explicit authorization for that generation:

```powershell
python -m sigma_fmea draft --system examples/research/hydraulic_actuator.json --profile general --provider openai --model YOUR_MODEL_ID --condition improved --output results/real-single-smoke --max-output-tokens 5000 --allow-paid
python -m sigma_fmea validate results/real-single-smoke/bundle
python -m sigma_fmea evaluate results/real-single-smoke/bundle --output results/real-single-smoke/independent-evaluation.json
```

Use `--provider anthropic` with an accessible Anthropic model ID to select that adapter.
The output contains bundle/fmea.json and fmea.csv plus input.json, prompt.json,
execution.json (raw response and usage), state.json and metrics.json. Headers/keys
are never recorded. Input descriptions must be authorized for the chosen cloud service.

## Approved real experiment

First inspect the no-call plan, including model/settings, system sample and blockers:

```powershell
python -m sigma_fmea experiment --config examples/research/experiment.json --provider openai --model YOUR_MODEL_ID --output results/preliminary-real --mode plan
```

After explicit approval for **one** paid smoke generation:

```powershell
python -m sigma_fmea experiment --config examples/research/experiment.json --provider openai --model YOUR_MODEL_ID --output results/preliminary-real --mode smoke --allow-paid --max-calls 1
```

Inspect the first run's draft, raw response, validation flags, token usage and elapsed
time. If it is usable, approve up to **23 additional calls**. Then:

```powershell
python -m sigma_fmea experiment --config examples/research/experiment.json --provider openai --model YOUR_MODEL_ID --output results/preliminary-real --mode batch --allow-paid --max-calls 24
python -m sigma_fmea analyze results/preliminary-real --output results/preliminary-real/analysis
```

`--max-calls` caps cumulative reserved attempts in this campaign, including the smoke,
failures and uncertain outcomes. Existing attempts are never automatically rerun.
There are no automatic API retries or silent model fallbacks. An interrupted attempt
may have been billed; inspect it before taking further action. Change model/settings/
inputs/guidance/code/references only in a new output campaign. Authentication/rate-limit
failures halt further batch calls; actual-model identity changes also halt comparisons.
An interrupted experiment lock requires manual inspection before removal.

Token cap: 5,000 per call by default, up to 120,000 capped generated/reasoning tokens
for 24 calls plus model-specific input token usage. This is not a currency estimate.
Choose account spend limits and approve the actual model/call budget before execution.

## Metrics and analysis outputs

- Structural completeness: populated substantive cells / eight eligible core fields
  per generated row. Fields: item, function, mode, causes, local/next/system effects,
  recommended actions. Unknown placeholders do not earn completion credit.
- Schema validity, errors, mode count, unknown count and unresolved flags are separate.
  Failed generations stay in the consolidated CSV; they are excluded from successful-
  sheet means, so failure rates must be reported alongside those means.
- Ratings/controls are excluded from this completeness denominator: do not invent
  values to boost completeness. Populated hypotheses are not independently correct.
- Reviewed-reference coverage uses normalized exact item/mode or reviewed aliases and
  one-to-one maximum matching. Unreviewed/absent references give null, not zero. This
  lexical measure can miss semantically equivalent modes and needs adjudication.

Analyze writes experiment-results.csv, descriptive-statistics.csv, system-condition-
means.csv, PNG/SVG comparisons, analysis-summary.json and preliminary-findings.md.
Absent reference data produces an explicitly unavailable coverage figure. Reported
statistics are descriptive: repeated runs are nested within systems; no significance,
Cpk, capability, safety authority or certification is claimed. Review time, accuracy,
unsupported modes and semantic duplicate adjudication remain future human work.

## Deadline run plan

1. Finish offline rehearsal and inspect its artifacts (completed during development).
2. Set one provider key locally, select an explicit model, approve one paid smoke.
3. Review smoke validity/coverage and token usage; adjust only through a new frozen
   campaign if necessary. Avoid changing conditions after inspecting outcomes.
4. Approve at most the remaining 23 calls for a usable campaign, then run batch.
5. Analyze and manually inspect selected baseline/improved sheets. Present descriptive
   structural results and execution failures; report missed-mode coverage unavailable
   unless independent references have actually been reviewed.
6. Use November 1 to write the methods/limitations and next DMAIC iteration. A reduced
   sample or failed batch is a reportable preliminary result; do not fabricate missing
   sheets or label simulation as real model evidence.

## Adapter documentation

OpenAI structured outputs:
https://developers.openai.com/api/docs/guides/structured-outputs

Anthropic Messages API:
https://platform.claude.com/docs/en/api/messages/create

Payloads are tested with offline simulated transports. Actual account access,
model-specific format support and service availability require the approved real smoke.
