# Research metric dictionary (V4.1)

All quantities are calculated in Python. A workflow execution, a generation attempt,
a successfully generated FMEA and an independent evaluation are different denominators.
Null means unavailable; it never means zero. Historical report aggregates are separate.

| Quantity / snapshot field | Definition and denominator |
|---|---|
| workflow execution | repository + numeric workflow run ID + run attempt; jobs are subordinate metadata |
| registered_generations | distinct generation IDs, including planned/running/failed records |
| total_generated | successful receipt-backed FMEAs with positive generated row count |
| failed_generations | finalized failed generation receipts; not failed workflow counts |
| evaluated_fmeas | distinct generations with one selected accepted evaluation |
| completed_evaluations | all accepted evaluation IDs, including repeated judges |
| awaiting_judge | successful generations lacking a selected evaluation |
| generation_success_percentage | successful / (successful + failed finalized generation attempts) *100; excludes planned/running |
| ground_truth_count | item-level reference opportunities in the imported evaluation |
| found | number of found reference items with distinct one-to-one generated-row matches |
| missed | reference opportunities minus found |
| missed_percentage | missed / reference opportunities *100 |
| coverage_percentage | found / reference opportunities *100 |
| pooled_missed_percentage | sum misses / sum reference opportunities *100 within version/system cohort |
| mean_run_missed_percentage | unweighted mean of independent per-generation percentages; repeated evaluations do not add runs |
| system_weighted_mean | mean of five system means, equal 1/5 weights; separate from raw run mean and pooled rate |
| dpmo | missed / reference opportunities *1,000,000 |
| sigma_1_5_shift | inverse-standard-normal(1 - pooled missed fraction) +1.5; null at exact 0/1; conventional, not certified process capability |
| cause_correct_fraction | observed correct causes / matched items with a supplied cause comparison |
| end_effect_correct_fraction | observed correct end effects / matched items with supplied effect comparison |
| severity/occurrence/detection_difference_fraction | matched observed comparisons with absolute rating difference <=1 / observed matched comparisons |
| rpn_relative_difference_fraction | matched observed relative RPN differences <=0.25 / observed matched RPN comparisons |
| field_accuracy | per-version weighted field fractions, using the summed field-specific observed matched-item denominators |
| extra_unmatched_rows | generated rows minus uniquely matched rows; not adjudicated false positives |
| generated_rows | receipt's validated CSV row count; quantity is not proof of quality |
| structural_status | deterministic inventory/schema audit status where supported; legacy unknown remains pending |
| duplicate_rows | receipt's duplicate/suspicious row count where available; null if not measured |
| traceability_status | PASS when structured row-unit links are recorded; not semantic/engineering certification |
| mean_success_generation_seconds | mean recorded request duration among successful generations; exposes timing_denominator |
| mean_evaluation_turnaround_seconds | nonnegative judge timestamp minus generation finish, where both zoned timestamps exist; exposes turnaround_denominator |
| api_calls | sum recorded invocation counts only when all relevant records supply counts; no fabricated retries |
| total_tokens | sum recorded total_token_count only when all relevant records provide it |
| actual_api_spending | all recorded generation invoice costs, only when every finalized attempt has billing; otherwise null |
| known_billed_subtotal | sum known invoice costs, separately labeled incomplete |
| estimated_api_spending | sum recorded tariff estimates only when complete; never replaces actual bills |
| api_cost_per_attempt | complete observed API spending / finalized attempts |
| api_cost_per_success | complete observed API spending for all attempts / successful generated FMEAs |
| api_cost_per_evaluated | complete observed API spending for all attempts / selected evaluated FMEAs; allocation, not invoice per evaluation |
| recorded_review_minutes | supplied human-review event time summed by generation; unknown stays null |
| modeled review cost | assumed matched/missed/extra review minutes * item counts * scenario loaded rate |
| modeled annual operating savings | (manual unit cost - modeled AI unit cost)*annual volume - annual maintenance |
| first-year net savings | modeled operating savings minus implementation investment |
| break_even_fmeas | ceiling((implementation + annual maintenance)/positive unit savings); unavailable for nonpositive unit savings |
| simulation interval | percentile 2.5%-97.5% of 10,000 seeded assumption-driven draws; not an empirical confidence interval |
| verified_savings | unavailable until comparable accepted manual/AI labor and billing data exist |

Statistical CIs use the existing deterministic system-stratified bootstrap with at least
two independent observations per version/system cell. The primary comparison remains
V2 versus V4. ANOVA uses the additive version+system model and exposes assumptions and
diagnostics. No run-level uncertainty or significance is reconstructed from the V2
aggregate report. V4 acceptance criteria remain separate from these descriptive metrics.
