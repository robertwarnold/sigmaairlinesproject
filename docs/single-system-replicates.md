# Controlled standalone System A repeatability pilot

This wrapper uses `fmea_generator.generate_fmea`, not the canonical research runner.
The v2.0 instructions and System A input are unchanged. Five separate stateless
requests use one model, temperature zero, the selected model's preflight output cap
and the same JSON schema. SDK retries are explicitly disabled. Generated S/O/D/RPN
are provisional and unreviewed; row counts and field population do not establish
coverage or correctness. No independently reviewed reference dataset is used.

The existing `generate-fmea.yml` manual workflow has two narrowly scoped modes:

1. `system_a_preflight`, `approved_calls=0`, `system=system_A`: require a unique
   `YYYYMMDDTHHMMSSZ-suffix` batch ID and the explicitly selected model. It checks
   model metadata/capability, with no generation, and uploads a frozen plan. Inspect
   the plan's exact input/skill byte hashes, model, cap and settings before execution.
2. `system_a_replicates`, `approved_calls=5`, `system=system_A`: use the exact same
   branch commit, model and batch ID and supply the successful `preflight_run_id`.
   It restores and checks that plan, then makes at most five sequential generation
   invocations, numbered 1-5. Existing batch directories are rejected. Workflow
   reruns and a previously dispatched matching batch ID are blocked. Never dispatch
   again after an uncertain outcome; inspect/download the available evidence.

These modes require explicit human generation authorization. They do not call any
other system or research workflow. An unavailable configured model is reported with
available alternatives rather than silently replaced. A preflight capability check
does not establish generation quota or engineering validity. First-run truncation,
configuration/quota failures and changed inputs/settings halt remaining attempts.
Other failed responses remain failures; no attempt is retried or replaced.

Artifacts are named `system-a-preflight-RUN_ID` and `system-a-replicates-RUN_ID`,
retained for 14 days. Download the latter into ignored
`results/single-system-replicates/system_A/`. Each unique batch contains original
successful CSVs, raw responses (including available failed responses), a manifest
with request accounting, hashes, timings, population metrics and available provider
metadata, combined CSV, per-run summary, descriptive statistics, candidate lexical
matches, engineering checklist, input/skill byte snapshots and checksums.
No generated data is committed or added to frozen research_results.

The seven core population fields are component, function, failure mode, cause,
local effect, system effect and recommended action. Explicit unknown placeholders
do not count as populated. Review-flag count is the number of rows with a substantive
review_flag. Candidate matches use only case/whitespace-normalized component and
mode text, preserving unit numbers; humans must adjudicate engineering equivalence.

Run offline tests with the declared SDK and build tools installed:
`python -m unittest discover -s tests -v` (`PYTHONPATH=src`). Mock tests cover the
five-attempt cap, run numbering, hashes, RPN, collisions, retained failures, first
truncation/auth stops, no-generation preflight, and disabled SDK retries.
