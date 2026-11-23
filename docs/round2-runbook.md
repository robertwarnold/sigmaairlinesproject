# Round 2 execution runbook

Implementation starts from `d5806f59144c14962a47f07a39d54102dd933637` on
`feat/fmea-skill-v3-round2` (initial workspace branch was
`feat/publish-fmea-figures-20261102`, `e428fc4906d6906cd1f7b06690beb27c9326b2cc`).
Main was fetched and fast-forwarded from a clean tree. No live calls were made.

V2's instruction file, array schema, default version, temperature zero, model maximum
output cap and single-attempt SDK behavior remain unchanged. V3 has a separate skill
and object schema with individually identified inventory units, relationships, all
13 failure-category decisions per unit and links to distinct rows. Structural validation
rejects missing coverage, duplicates, unknown links, incomplete output and truncation.
The receipt retains the inventory/case audit and row-ID links; CSV retains the historical
column format. These are model-declared checks, not independent engineering validation.
No prompts contain judge answers. Canonical `sigma_fmea` experiments remain separate.

Install analysis dependencies with `python -m pip install -e ".[round2]"`.
The existing `analysis.experiments` command remains the generation operations reporter;
`analysis.round2` is the separate judge-quality importer, not an alternative generator.

The supplied November 14 report is recorded in `analysis/round2/round1_baseline.json`.
It reports 18 runs, 738 opportunities, 232 misses, 43 extras and category totals.
Recomputed pooled misses are 31.4363%, DPMO 314363, extras/run 2.3889.
No run-level mean, per-system denominator or individual judge record is inferred.
No candidate judge filenames were located in the local results search. Historical
operational datasets (including the 24-attempt dashboard) are not the 18 judged runs.
Reference worksheets and the frozen archive were not opened or changed.

Prepare manifests offline (choose a NEW output directory):

```powershell
python -m analysis.round2 plan --output results/round2/confirmed-plan --model CONFIRMED_ROUND1_MODEL_ID
```

The seed is 20261115; four runs per A-E, 20 total, order is randomized reproducibly.
A preparation manifest already exists in `results/round2/preparation` with an explicit
unconfirmed-model placeholder. This is a blocked design, not a dispatchable campaign.
Before execution a human must bind the exact Round 1 model/settings, input hashes,
engineer-written ground-truth revision and unchanged judge v1.2 hash. The baseline
report supplied no exact Gemini model ID; do not substitute the CLI or Actions default.
Keep those private bindings with the experiment manifest. Review token limits too.

After approval to push the branch, and explicit authorization for ONE pilot, use the
first manifest entry's system and replicate. PowerShell commands:

```powershell
$plan = Get-Content results/round2/confirmed-plan/experiment_manifest.json -Raw | ConvertFrom-Json
$pilot = $plan.runs[0]
gh workflow run generate-fmea.yml --ref feat/fmea-skill-v3-round2 -f mode=single -f system="system_$($pilot.system)" -f model="$($plan.generator_model)" -f skill_version=v3.0 -f run_number="$($pilot.replicate)" -f approved_calls=1
gh run list --workflow generate-fmea.yml --limit 5
gh run watch RUN_ID
gh run download RUN_ID --dir results/github/RUN_ID
```

The complete local download location is
`C:\Users\camer\Documents\sigmaairlinesproject\results\github\RUN_ID`.
Artifacts expire in 14 days. Record Actions ID, receipt hashes and manifest run ID
before evaluation. Inspect pilot validation, inventory and directions before continuing.
For remaining runs use the SAME dispatch command with the next manifest entry, one
explicitly authorized dispatch at a time, in recorded order. Never rerun failed Actions;
reserve a separately approved replacement ID and preserve the failed attempt. Count
all team calls, including failures and pilot, toward the approximate 20/day quota.
No batch dispatcher is enabled; shared quota must be coordinated by a human.

For very large systems, prepare explicit physical-inventory subsets with shared
interface context and stable IDs; authorize each batch separately. A truncated batch
is rejected, never published as a valid draft. Offline `merge` combines complete batch
envelopes, validates cross-batch IDs and coverage, and publishes a combined JSON audit.
Example: `python -m analysis.round2 merge --batch results/batch1.json --batch results/batch2.json --output results/combined-audit.json`.
Human review must reconcile scope and boundary interfaces. This changes experimental
conditions: use the SAME batch protocol for compared versions or exclude those runs.
Do not silently batch a Round 2 run or automatically request continuation.

## Import completed judging

The private judge process remains external; `judging_manifest.json` is the queue.
Keep the same Claude Sonnet 5.5, skill v1.2 and human ground truths. No judge instruction
changes are included. A human exports identifier-level results, not reference sheets.
Place an import JSON under ignored `results/round2/imports/`. Required contract:

```json
{
  "schema": "standalone-judge-import-1",
  "workflow": "standalone_gemini",
  "runs": [{
    "run_id": "round2-A-r01", "system": "A", "skill_version": "v3.0",
    "generator_model": "CONFIRMED_MODEL", "settings": {"temperature": 0},
    "judge_model": "Claude Sonnet 5.5", "judge_skill_version": "v1.2",
    "ground_truth_version": "HUMAN_FROZEN_REVISION",
    "classification_rules_version": "ROUND1_REVIEWED_RULE_REVISION",
    "status": "validated", "generated_rows": 1, "extra_unmatched_rows": 0,
    "generation_seconds": null, "usage": null, "estimated_cost": null,
    "items": [{"item_id": "OPAQUE_ID", "found": true, "matched_row_id": "row-1",
      "miss_category": null, "review_status": "human_reviewed",
      "cause_correct": null, "end_effect_correct": null,
      "severity_difference": null, "occurrence_difference": null,
      "detection_difference": null, "rpn_relative_difference": null}]
  }]
}
```

Optional run-level `generation_receipt_path` points to a downloaded standalone
`*_execution.json` under results/. Its identity/status/row count are checked, hashes
recorded, and duration/usage imported. Without it provenance marks metadata as human-exported.
One record per ground-truth opportunity, including misses. Unknown measurements stay
null. Relative RPN difference is a fraction (0.25 = 25%); rating differences are signed.
Optional `judge_notes` must be human-sanitized without reference quotations. There is
no raw judge parser: a human must export this contract and verify receipt identities,
row counts, finish status, settings, ground-truth/classification revisions and matches.
All found opportunities need unique row IDs; matched rows plus extras must equal the
generated-row count. No category guessing: use null when unsupported. Allowed mutually
exclusive categories are Repeated unit skipped, Sub-case not split out, Part never
covered, Wrong failure direction. Unknown categories remain explicitly unclassified.
Do not claim Round 1 classification comparability without its reviewed rule revision.

```powershell
python -m analysis.round2 aggregate --judge results/round2/imports/v2.json --judge results/round2/imports/v3.json --output results/round2/analysis
```

Re-running replaces derived files from the same inputs without appending records.
Duplicate run IDs across distinct inputs fail. Repeating the same path is deduplicated.
Conflicting conditions or per-system opportunity IDs fail. Input hashes and missing
fields are listed in `data_quality_provenance.json`. Inspect it before using the workbook.
Outputs: runs/items/per_system/per_version/pareto CSV, analysis.xlsx, pareto.png and
JSON provenance including report-derived baseline and individual success criteria.
CSV text is formula-escaped; Excel formula/URL conversion is disabled.

For baseline-only readiness reporting (no scores fabricated):

```powershell
python -m analysis.round2 aggregate --output results/round2/baseline-analysis
```

## Analysis interpretation

Mean run percentages weight each run equally; pooled percentages weight opportunities.
System improvements use run means, with pooled results separately available. DPMO is
missed/opportunities times one million; sigma uses inverse-normal yield plus the
conventional 1.5 shift, undefined at exact zero/one defect proportions. Report-derived
approximate sigma is retained separately. Extra rows guard against speculative inflation.
Quality fractions use only found items with observed comparisons and expose denominators.
Run SD describes variation, not a confidence interval.

ANOVA is additive OLS `missed_percentage ~ system + skill_version`, equivalent to R
`anova(lm(missed_percentage ~ system + skill_version))` for the partial version effect.
The full-vs-system-only RSS F test is documented in code. It requires actual comparable
records for both versions across all five systems and positive residual degrees of
freedom/variance. Aggregate baseline cannot support it. Interpret bounded proportions,
independence and residual variance assumptions with the research team; no interaction
effect or significance claim is made. The full Round 1 report was not available to
verify its sums-of-squares convention; confirm this before final inferential reporting.

Each success criterion is reported independently: v3 run mean <20%; adjusted version
p<.05; at least four systems improve; no system worsens >5 percentage points; v3 extra
mean <=4.8. All remain provisional until planned replication and human review complete.
If incomplete, collect the missing four-per-system v3 observations and comparable v2
run/item evidence. Additional power-based replication requires observed run variance.
DMAIC Improve targets inventory and distinct cases; Control freezes conditions, audits
completeness and extras, and preserves failed attempts and provenance.

Offline verification: `python -m unittest discover -s tests -v` with `PYTHONPATH=src`,
`SIGMA_FMEA_AUTOREPORT=off` and the documented wheel for installed-CLI tests.
Only synthetic fixtures are used. No API generation or live judging is part of tests.
