# Sigma Airlines — FMEA Methodology & FMECA Conversion Specification (v1 proposal)

## A. Product principle

**Output product = FMEA draft.** FMECA may be a source format, and criticality analysis may be retained as supporting metadata, but the tool must not conflate FMEA and FMECA. The user chooses the FMEA variant and the primary methodology profile before generation. This specification is a project design proposal, not a claim of compliance with any external standard.

## B. Source registry and selection

| Candidate source | Primary use | Profile type | Verification/access caveat |
|---|---|---|---|
| IEC 60812:2018 | General FMEA workflow, scope, documentation | General / cross-industry | Obtain legitimate access to normative text before implementing specific rules |
| AIAG–VDA FMEA Handbook | Structure/function/failure analysis, optimization, action priority | Design FMEA / Process FMEA | Check edition, licensing, and applicability; do not reproduce protected charts |
| SAE J1739 | Design and process FMEA conventions and rating criteria | Design FMEA / Process FMEA | Verify current revision and permitted use of rating tables |
| ASQ public FMEA guidance | Accessible conceptual steps and terminology | Introductory/general | Public overview is not a formal certification standard |
| NASA GSFC-HDBK-8004 (2024) | Aerospace FMECA scope, hierarchy, local-to-ultimate effects, assumptions | Aerospace supplemental / FMECA source | Do not assume NASA scoring equals 1–10 S/O/D |
| MIL-STD-1629A and historical NASA workbooks | Legacy FMECA structure and conversion evidence | FMECA ingestion/benchmark | Preserve original definitions and provenance |

Store each registry entry with `source_id`, title, publisher, edition/date, URL, access/licensing status, verification status, section/page, relevant rule summary (original wording only when allowed), FMEA variant, and conflict notes. Distinguish `verified_primary_source`, `public_secondary_summary`, `team_policy`, and `model_suggestion`.

### Proposed profile behavior

- **General FMEA:** Start from IEC-informed or other accessible general guidance; select explicit field set and rating policy.
- **Design FMEA (DFMEA):** Component/function/design failure mechanisms, prevention/detection controls; use applicable design FMEA profile.
- **Process FMEA (PFMEA):** Process steps, failure modes, causes, current process controls; use applicable process FMEA profile.
- **Aerospace functional FMEA:** System/function/interface hierarchy and effects; NASA guidance can supplement FMEA structure, not override a selected FMEA scoring profile by default.
- **FMECA import:** Conversion only, not automatic risk-scale equivalence.

When two sources conflict, report source IDs, conflicting rules, selected rule, rationale, and whether human approval is required. Never average or silently merge scoring scales.

## C. Canonical FMEA record (proposed fields)

**Context:** `analysis_id`, `system_id`, `analysis_type`, `primary_method_profile`, `profile_version`, `scope`, `hierarchy_level`, `operating_phase`, `assumptions`, `source_documents`.

**FMEA row:** `record_id`, `item_or_process_step`, `function`, `requirement_refs`, `interface_refs`, `failure_mode`, `failure_causes`, `effect_local`, `effect_next_level`, `effect_end_effect`, `existing_prevention_controls`, `existing_detection_controls`, `recommended_actions`.

**Risk:** `severity`, `occurrence`, `detection`, `rating_profile_id`, `rpn`, `action_priority`, `rating_basis`, `rating_unknown_reason`. Every numeric field may be null when not justified. `rpn` is calculated only for a compatible selected S/O/D profile with all required values.

**Traceability and review:** `evidence_refs` (source/page/section/row), `provenance_kind` (direct/normalized/inferred/hypothesis), `review_status` (draft/needs_review/accepted/rejected), `reviewer_notes`, `conversion_trace_id`.

**FMECA-only metadata (not substituted into FMEA scores):** `source_criticality`, `source_failure_probability`, `source_likelihood_rating`, `source_detection_prevention_rating`, `source_critical_item_flag`, `source_risk_scheme`.

## D. FMECA → FMEA field mapping

| FMECA source field | FMEA destination | Conversion rule | Review risk |
|---|---|---|---|
| Item / subsystem / element | Item or process step | Direct when level matches; record hierarchy | Mixed indenture levels |
| Intended function | Function | Direct/normalized; flag missing | Inferred functions |
| Failure mode | Failure mode | Preserve technical meaning and source row | Multiple modes combined in one row |
| Failure causes / mechanisms | Failure causes | Preserve separate cause entries | Mechanism vs cause ambiguity |
| Local effect | Local effect | Direct | Missing or vague effect |
| Next-higher effect | Next-level effect | Direct when supplied | Hierarchy mismatch |
| End/system/mission effect | End effect | Direct when supplied | Inconsistent consequence scope |
| Existing detection/prevention | Existing controls | Map only if **already implemented** | Proposed mitigation misclassified as existing |
| Proposed mitigation / control plan | Recommended actions | Map only if proposed; preserve status | Unclear implementation state |
| FMECA criticality classification | FMECA-only metadata | Preserve; **not** S/O/D or RPN | False score equivalence |
| FMECA failure likelihood | Source likelihood metadata | Do not map to 1–10 occurrence without reviewed crosswalk | Quantitative/ordinal mismatch |
| FMECA severity class | Source severity metadata | Map only when compatible definitions and reviewed crosswalk exist | Different consequence definitions |
| FMECA detection/prevention category | Source D/P metadata | Do not assume equivalent to FMEA detection | Direction/scale mismatch |
| Source references / worksheet IDs | Evidence and conversion trace | Preserve exactly | Loss of provenance |

**Unknowns:** Use `null` plus a specific reason (e.g., `not_in_source`, `not_applicable`, `ambiguous`, `needs_engineer_rating`), not fabricated ratings. Maintain a sidecar `conversion_report` listing direct, normalized, inferred, unavailable, and excluded fields. If a source table cannot be reliably extracted, fail gracefully and require manual transcription/validation.

## E. Conversion verification and benchmark isolation

1. Select a small representative FMECA worksheet with clear public provenance.
2. Preserve original table/row text or source locator, source version, and original rating definitions.
3. Convert to canonical FMEA rows and produce a field-by-field mapping report.
4. Manually verify each converted record against the source, especially causes/effects/controls and risk categories.
5. Resolve duplicates and hierarchy mismatch using documented reviewer decisions.
6. Freeze accepted converted reference rows as a versioned benchmark with a checksum.
7. Place benchmark answers outside the generation/retrieval context for the same test case.
8. Track uncertain or excluded records and benchmark coverage, so missed-mode metrics have an explicit denominator.

**Important:** A FMECA→FMEA conversion is not automatically lossless. If the source lacks a current FMEA field, it remains absent until an engineer supplies/approves it. Converted benchmark records must be labeled `reviewed_converted_reference`, not original professional FMEA.

## F. Initial acceptance tests

- A FMECA row with valid mode, cause, and effects maps to the corresponding FMEA fields and preserves its source reference.
- A FMECA criticality rating is preserved as metadata, not inserted into severity, occurrence, detection, or RPN.
- A source missing a detection control yields an explicit null/flag rather than an invented control.
- A planned mitigation does not become an existing prevention control.
- A record with a NASA-style rating cannot be scored with a generic 1–10 profile without an approved crosswalk.
- A fully specified compatible FMEA row has its RPN calculated deterministically.
- A mixed-level or ambiguous row is flagged for human review.
- Offline mock generation and deterministic conversion run with no cloud credentials.
- Generation never retrieves held-out benchmark answers.

## G. Research alignment

The research design calls for missed-mode rate and structural completeness over four systems and repeated runs. Evaluate converted benchmark quality separately from model quality; report reviewer agreement, matching uncertainty, and source coverage. The AI judge must be independently calibrated against engineers and should not be used as a substitute for benchmark validation.
