# Preliminary AI-assisted FMEA findings

Planned: 8; attempted: 1; successful: 1; failed/uncertain: 0.
Systems: 2. reduced/changed sample: 2 systems. Conditions: baseline versus improved. Planned repetitions per system/condition: 2.
Requested provider/model: gemini / gemini-3.8-flash. Actual model identities: ['gemini-3.8-flash'].

## Methods

The baseline uses minimal FMEA instructions; improved adds the selected methodology workflow and allowlisted ASQ/NASA/team-policy guidance. The same systems, requested model, token cap and sampling settings are used in both conditions. Pair order is randomized with a frozen seed. Every sheet is one observation; repeats are nested within systems.

Structural completeness is the percentage of eight core row fields containing substantive text/list content. Explicit unknowns count as missing content; schema validity is a separate measure. Controls/ratings are excluded from this denominator because current controls need evidence and selected profiles are unrated. Completeness does not establish correctness or safety.

Missed-mode percentage is calculated only for explicitly reviewed eligible reference modes using normalized exact item/mode matching or reviewed aliases, with one-to-one matching. It is lexical coverage, not a semantic expert judgment. No LLM judge is used.

## Descriptive results

| Condition | Measure | n | Mean | SD |
|---|---|---:|---:|---:|
| baseline | structural_completeness_pct | 1 | 100.00 | unavailable |
| baseline | missed_failure_modes_pct | 0 | unavailable | unavailable |
| baseline | generated_failure_modes | 1 | 9.00 | unavailable |
| baseline | generation_seconds | 1 | 99.15 | unavailable |
| improved | structural_completeness_pct | 0 | unavailable | unavailable |
| improved | missed_failure_modes_pct | 0 | unavailable | unavailable |
| improved | generated_failure_modes | 0 | unavailable | unavailable |
| improved | generation_seconds | 0 | unavailable | unavailable |

## Interpretation and limitations

No reviewed reference set supported numerical missed-mode estimates. Coverage is unavailable, not zero. Unreviewed NASA candidates are not ground truth.
The scenarios are author-created demonstrations, not validated operational systems. This is a small convenience sample. No statistical significance, Cpk, capability, certification or autonomous risk acceptance is claimed. Model facts, causes/effects/actions and unsupported controls require engineering review. Token counts are reported only where returned by the provider; no monetary cost is inferred.

Next iterations: inspect the real smoke draft, calibrate a reviewed reference set and alias rubric independently, review unsupported/duplicate modes, and then increase replications while freezing inputs and settings.

## Execution failures

None recorded.

