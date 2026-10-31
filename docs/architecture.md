# Offline foundation design and decisions

Status: local first milestone; owners remain Unassigned.

Deadline override (preliminary results due November 1, 2026): the local research prototype
now adds real-provider adapters, allowlisted guidance, two conditions, a configurable
runner, deterministic evaluation and descriptive analysis. See research-prototype.md
and research-verification.md. No paid calls have been authorized/executed.

Update after foundation merge: profile version 0.3 adds distinct preliminary scope
checks, workflows and review questions; see profile-policies.md. Schema/mapping stay
0.2 and legacy profile 0.2 remains verifiable. A limited public conversion candidate is
documented in public-conversion-candidate.md; it is not an approved benchmark.

## Architecture

`EngineeringContext -> selected Profile -> Provider -> FMEADraft -> validation -> export`

`structured FMECA -> deterministic converter -> FMEADraft + conversion report`

Both paths use the same canonical model. Conversion never calls the provider. Initial
runtime uses only the Python standard library. Future provider adapters implement the
`Provider` protocol; adapter output passes shared validation and cannot carry approval.

Context includes analysis/system IDs, scope, hierarchy, phase, assumptions, requirements,
interfaces, and named functions. Rows contain mode, causes, three effect levels,
implemented controls, proposed actions, nullable ratings, source risk metadata,
evidence, unknown reasons, review flags, and review-decision metadata. Schema/profile
versions are checked. JSON exports are the machine-readable contract for this milestone.

## Methodology decision (ADR-001)

Applicable project requirements take precedence over selected profile rules, followed by
applicable supplemental guidance and explicit team policy. Conflicts must be recorded
with source IDs, selected rule, rationale, and engineering decision before adding rules.
Initial profiles have no conflicting numeric rules: all target ratings and priorities
are unavailable. ASQ supplies conceptual guidance; NASA supplements aerospace structure.
IEC/AIAG–VDA/SAE references do not authorize implementing or reproducing licensed tables.
Profile distinctions are initial selection metadata, not complete DFMEA/PFMEA workflows.

Evidence origin (`source`, `derived`, `hypothesis`) is distinct from conversion operation
(`direct`, `normalized`, `unavailable`, `excluded`; inferred mappings are not performed).
Conversion reports link every target source value to its original field; generated
hypotheses are labeled separately from the item/function context evidence.

## Conversion decision (ADR-002)

| Input field | Target |
|---|---|
| item | item_or_process_step |
| function | function |
| failure_mode | failure_mode |
| causes | failure_causes |
| local_effect | effect_local |
| next_level_effect | effect_next_level |
| end_effect | effect_end_effect |
| proposed_mitigations | recommended_actions |
| controls | Individually typed/statused/evidenced controls; only implemented entries populate existing prevention/detection/mitigation lists |
| prevention_controls / detection_controls / mitigation_controls | Legacy descriptions retained as unknown-status controls; shared status ignored |
| criticality, severity, occurrence, likelihood, detection, detection_prevention, rpn, failure_probability, risk_scheme, critical_item | source_risk_data, unchanged |
| Other fields | report.unmapped_fields and original_record |

String causes/actions/controls become singleton lists; lists retain their entries. No
automatic splitting or semantic inference occurs. Missing controls are not invented.
Unknown implementation status excludes controls from existing-control lists, retains
the individual control, and raises a flag.
The original record remains intact even for excluded fields. Hashes use canonical
sorted-key JSON of each original parsed record, not raw source-file bytes.
Canonical source snapshots are immutable strings detached from input objects. Report
validation recomputes each checksum and the complete mapping; changed source mirrors,
flags, mappings, or converted engineering content fail validation. See integrity.md.

Source and target scope/hierarchy/phase reconciliation is mandatory review work; no
hierarchy transformation is attempted. Multiple modes/causes, duplicates, mixed levels,
and extraction uncertainty need reviewer inspection; this slice checks duplicate record
IDs but does not claim semantic ambiguity detection. PDF tables require transcription
and visual validation before structured import.

Crosswalks will require scheme versions, definitions, domain applicability, limitations,
and reviewer approval. Similar column names or numeric ranges are insufficient. Unknown
target ratings remain null with no_reviewed_crosswalk. Even source RPN stays source data.

## Audit and milestone sequence

R code is retained as historical baseline. Static audit found Anthropic coupling,
mandatory provisional ratings, one demonstration input, absent reviewed benchmarks,
and overwrite-prone experiment filenames. No R experiment was executed.

S-01/S-02 -> S-03 -> S-04 -> minimum S-05/S-06/S-07/S-08 offline integration.
Review contracts and benchmark exclusion begin here. S-09 retrieval follows evidence
governance; S-10 freezes reviewed conversions; S-11 calibrates metrics/judges; S-12
runs one reviewed pilot before any larger study; S-13 evaluates statistical assumptions;
S-14 completes controlled review, documentation, and release readiness.

Keep 4 systems x 25 replications x 5 versions as a proposed protocol. Structural
completeness is separate from correctness and rating agreement. Missing-mode denominators
must use reviewed eligible reference modes. Do not invent target ratings to make a
converted benchmark look complete. Holdout answers must never enter generation context.

## Evidence still required

- Legitimate access and detailed rule verification for licensed standards.
- Independent engineering review of the visually checked two-row public candidate;
  synthetic fixtures remain software tests rather than ground truth.
- Four controlled system contexts and independently reviewed benchmark conversions.
- Review authority, matching/adjudication rules, and rubric calibration.
- Optional provider adapter contracts, reproducibility settings, and data-use approval.
