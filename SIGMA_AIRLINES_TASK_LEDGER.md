# Sigma Airlines — Unassigned Development Task Ledger (v2)

**Scope:** Multi-source FMEA drafting skill + auditable FMECA→FMEA conversion + research evaluation.  
**Status:** Architecture approved; first local offline milestone implemented for review. **No individuals assigned.**  
**Workflow:** Proposed → Ready → In progress → In review → Accepted. Acceptance remains a team decision.

## Deadline research prototype — preliminary results due 2026-11-01

Priority changed by the team to rapid end-to-end research integration. All owners
remain **Unassigned**. Working branch remains `feat/fmea-profiles-validation`.

| Task | Current prototype work | Status / remaining gate |
|---|---|---|
| S-02 / S-09 | Lightweight allowlisted ASQ/NASA/team-policy summaries, exact guidance trace | In review; no full RAG or unverified standards-compliance claim |
| S-05 / S-07 | OpenAI and Anthropic HTTP adapters, structured candidates, mock retained; baseline/improved prompts | In review offline; real smoke requires configured credential/model and explicit paid approval |
| S-03 / S-04 / S-06 | Canonical schema, unrated policy and deterministic converter preserved | Historical integrity work retained; further production verification deferred |
| S-08 / S-11 | Deterministic content-completeness, counts/errors/flags/time; reviewed-reference lexical coverage only | In review; no actual reviewed reference sets for research scenarios |
| S-12 | Four scenario inputs, 3 repeats × 2 conditions, frozen plan, smoke gate, attempt claims and cumulative call cap | Offline rehearsal; paid campaign not authorized or executed |
| S-13 | Consolidated CSV, descriptive comparisons, plots and preliminary report | Offline rehearsal artifacts only until real calls approved; no significance/Cpk claims |
| S-14 | CLI demonstration and deadline runbook | In review; production auth/frontend/release hardening deferred |

See docs/research-prototype.md for actual commands, sample limitations, approval gates,
and the deadline run plan. Existing R baseline/reference exclusions remain unchanged.
No commits, pushes, merges or paid calls are authorized by this deadline work order.

Verification: **61 offline tests passed on Python 3.12.14**. Actual mock rehearsal:
24 attempted / 24 successful / 0 failures, after a one-generation smoke. CSVs, descriptive
statistics, PNG/SVG plots and findings report generated under ignored results/. These
are rehearsal artifacts only, not real LLM research evidence. No provider credential is
configured; no paid smoke or batch has run. See docs/research-verification.md.

## Post-merge next slice — 2026-10-31

Foundation PR #1 merged into main as `68841b9` after remote Python 3.12/3.13 CI passed.
Current development branch: `feat/fmea-profiles-validation`. All owners **Unassigned**.

| Task | Status | Current slice |
|---|---|---|
| S-01 | In review | Foundation merged; remote CI recorded; original R baseline preserved. |
| S-02 | In progress | Public ASQ/NASA guidance revisited; licensed normative details remain unverified. |
| S-03 / S-07 | In review (local slice) | Profile 0.3 gives four distinct scope/workflow/review policies, gap flags, and mock intent; legacy 0.2 verification retained. |
| S-04 / S-06 | In review (local slice) | Two real-source NASA rows transcribed as a limited candidate with source-page locators; risks/units and ambiguous controls preserved. |
| S-10 | In progress (candidate only) | Agent visual page comparison completed; independent engineering verification and benchmark approval remain pending. |
| S-09 / S-11–S-14 | Proposed | Retrieval, evaluator, experiments, statistics, authenticated review and release remain deferred. |

No full source document is added to Git. The candidate is isolated under tests/fixtures,
is not generation context, and must not be described as approved ground truth. Real AI
providers and paid calls remain deferred. New slice changes remain local for review;
the foundation merge does not imply acceptance of all remaining work-package criteria.

Local validation: 44 tests pass on Python 3.12.14, including the installed CLI,
profile-specific scope checks, legacy profile verification and the two-row candidate.
The new slice is not committed or pushed; its remote CI is pending.

## Engineering-data integrity correction pass — 2026-10-31

Status: **In review**, pending team acceptance. All owners remain **Unassigned**.
This is a correction pass within the offline milestone; no next milestone is started.

| Task | Updated status | Correction evidence / remaining gate |
|---|---|---|
| S-01 | In review | Python 3.12 target, local offline wheel/installed-CLI verification, R baseline unchanged; remote CI pending. |
| S-02 | In progress | Registry/profile verification status explicitly preliminary; licensed rule verification remains pending. |
| S-03 | In review | Schema 0.2 rejects non-JSON values, contradictory unknown/provenance, invalid review timestamps, stale decisions and authentication claims; independent evidenced controls added. |
| S-04 | In review | Mapping 0.2 separates control types/statuses, preserves source risk/units, snapshots and hashes; real source-page verification pending. |
| S-05 | In review (minimum slice) | Offline mock/provider boundary and installed CLI exercised; real adapters explicitly deferred. |
| S-06 | In review (minimum slice) | Duplicate normalized CSV headers, blank headers, row-width/quoting failures and duplicate JSON keys rejected; source snapshots/checksums and mapping revalidation added. |
| S-07 | In progress | Four profiles retained as preliminary team policies; meaningful specialized methodology behavior still pending. |
| S-08 | In review (minimum slice) | New-directory-only staged export, manifest/file identities, source/report/CSV verification and failure/interrupt regressions; scoring remains disabled. |
| S-10 | Proposed | Public NASA worksheet fixture still requires visual transcription verification and independent review before incorporation. |
| S-14 | Proposed (early contracts in review) | Unauthenticated local review records bind to engineering content version and preserve flags; authenticated release authority remains deferred. |

Acceptance evidence: 38 automated tests on Python 3.12.14, including installed console
commands in an isolated temporary environment, strict parsing, mixed control states,
provenance/unknown contradictions, input/report mutation, file checksums, output reuse,
invalid review metadata, failed/interrupted writes and publication, and writer locks.
See docs/integrity.md for recovery limits and docs/correction-verification.md for results.
No task is marked Accepted automatically. No commit, push, merge, paid API, retrieval,
experiment, or frontend work is included.

## Local milestone review — 2026-10-31

All owners remain **Unassigned**. No task is marked Accepted by the implementation.

| ID | Current status | Evidence and remaining work |
|---|---|---|
| S-01 | In review | Static R/repository audit in docs/architecture.md; baseline preserved, Python configuration, CI definition and exclusion rules added. Remote CI not executed. |
| S-02 | In progress | Source registry includes IEC, AIAG–VDA, SAE, ASQ, NASA with access/verification status. Licensed normative rules and legacy source expansion remain pending. |
| S-03 | In review | Canonical models, explicit unknowns, evidence, review metadata, four selectable unrated team profiles. Specialized methodology rules and authenticated review remain future work. |
| S-04 | In review | Deterministic mapping specification and conversion report, original parsed records and source risk retained. Synthetic fixture only; public page-verified fixture and reviewed crosswalks remain pending. |
| S-05 | In progress | Minimal standard-library Python package/CLI/provider protocol and offline mock delivered. Real adapters deferred. |
| S-06 | In progress | CSV/JSON conversion slice delivered with deterministic reports. Semantic ambiguity detection and reviewed public fixtures remain pending. |
| S-07 | In progress | Structured context, explicit profile selection, mock hypothesis generation. Real generation, scope interview and licensed profile expansion deferred. |
| S-08 | In progress | Shared validation, JSON/CSV exports and negative tests delivered. Scoring disabled for initial unrated profiles; Excel deferred. |
| S-09–S-14 | Proposed | Retrieval, benchmarks, evaluation, experiments, statistics, controlled review and release deferred. |

Recommended dependency refinements: begin S-08 validation contracts with S-03; establish
S-14 review contracts and S-09 benchmark exclusion early; add S-05 to S-09 and S-08 to
S-12 dependencies. Preserve sheet-level observations and 4×25×5 as a proposed study.
Separate structural completeness from technical correctness and compatible rating
agreement. No full study or paid calls are authorized by this local milestone.

## Priority 0 — Repository, methodology, and contracts

| ID | Work package | Dependencies | Deliverables | Acceptance criteria | Owner |
|---|---|---|---|---|---|
| S-01 | Repository audit and collaboration foundation | None | Inventory of R pilot, branch/PR workflow, security policy, environment guide | Existing R files preserved; current features documented; Git/CI plan reviewed | Unassigned |
| S-02 | Multi-source FMEA methodology research | None | Source registry for IEC 60812, AIAG–VDA, SAE J1739, ASQ, NASA, legacy FMECA guidance | Edition/license/verification status documented; FMEA vs FMECA distinguished; no unlicensed standards copied | Unassigned |
| S-03 | FMEA canonical data model and profiles | S-02 | Typed FMEA schema, analysis profiles, source/evidence model, rating-policy ADR | Field meanings documented; incompatible scales separated; missing values allowed and flagged; review status enforced | Unassigned |
| S-04 | FMECA→FMEA translation specification | S-02, S-03 | Mapping matrix, conversion policy, loss/ambiguity report template, source fixtures | No criticality→RPN invention; source fields traceable; sample mappings reviewed against source | Unassigned |

## Priority 1 — Offline engineering pipeline

| ID | Work package | Dependencies | Deliverables | Acceptance criteria | Owner |
|---|---|---|---|---|---|
| S-05 | Python foundation and provider abstraction | S-01, S-03 | Python package, provider interface, deterministic mock, optional provider configuration | Install/test/generate in mock mode without keys/network; R pilot unaffected | Unassigned |
| S-06 | FMECA conversion implementation | S-04, S-05 | CSV/JSON importer, converter, mapping report, review flags | Deterministic unit tests; source data preserved; missing ratings not fabricated; conversion trace exportable | Unassigned |
| S-07 | Multi-method FMEA generation workflow | S-02, S-03, S-05 | Scope questionnaire, method-profile selection, structured FMEA generator, gap detection | Output labeled FMEA draft; selected profile/source traceable; unknowns flagged | Unassigned |
| S-08 | Deterministic validation, scoring, and export | S-03, S-06, S-07 | Schema checks, rating calculators, duplicate checks, CSV/JSON/Excel export | RPN only for compatible complete S/O/D; no automatic signoff; offline test passes | Unassigned |

## Priority 2 — Knowledge, benchmarks, and evaluation

| ID | Work package | Dependencies | Deliverables | Acceptance criteria | Owner |
|---|---|---|---|---|---|
| S-09 | Engineering input ingestion and curated retrieval | S-02, S-03, S-07 | Source-aware ingestion, indexed guidance/examples, evidence citations | Provenance retained; copyright constraints observed; benchmark holdout enforced | Unassigned |
| S-10 | NASA FMECA benchmark conversion and curation | S-04, S-06 | Reviewed FMEA benchmark set from selected 2019/2021 NASA reports, frozen version manifests | Original pages mapped; uncertainties resolved/reviewed; no leakage to generator | Unassigned |
| S-11 | Independent evaluator and human calibration | S-03, S-08, S-10 | Deterministic quality metrics, LLM judge rubric, adjudication protocol | Missed-mode denominator defined; human agreement measured; judge not assumed ground truth | Unassigned |
| S-12 | Reproducible experiment runner | S-05, S-07, S-11 | Versioned runs, 4×25×5 configuration, resume/logging, cost guardrails | One-run pilot first; no 500-run execution without approval; all settings hashed/logged | Unassigned |

## Priority 3 — Analysis, integration, and usability

| ID | Work package | Dependencies | Deliverables | Acceptance criteria | Owner |
|---|---|---|---|---|---|
| S-13 | Six Sigma statistical analysis and DMAIC | S-11, S-12 | Baseline/improvement comparison, appropriate SPC charts, special-cause analysis, results narrative | Bounded-proportion assumptions considered; capability claims justified; reproducible analysis | Unassigned |
| S-14 | Engineer review workflow, docs, and release readiness | S-08, S-09, S-11 | Review states, traceable exports, setup guide, test coverage, agent skill instructions | Human approval remains mandatory; CI green; no credentials/source licenses exposed | Unassigned |

## Workstream boundaries (for future parallel development)

- **Standards and governance:** S-02, S-03 — source catalog, methodology profiles, field definitions. This is upstream of most work.
- **Conversion:** S-04, S-06, S-10 — source FMECA interpretation, deterministic conversion, benchmark curation.
- **Generation:** S-05, S-07, S-09 — provider interface, generation, curated retrieval.
- **Quality and experiments:** S-08, S-11, S-12, S-13 — validation, evaluation, reproducibility, statistical analysis.
- **Integration:** S-01, S-14 — Git, testing, documentation, review and release.

These are **workstreams, not person assignments**. Multiple contributors may work within a workstream after task boundaries and file ownership are agreed.

## Milestone gates

**M0 — Architecture approved:** S-01 through S-04 specifications reviewed. No application refactor required.  
**M1 — Offline proof:** S-05, S-06, S-07, S-08 minimal slices; no API keys required.  
**M2 — Evidence-based prototype:** S-09 and source/profile expansion; clear citation provenance.  
**M3 — Validated research pipeline:** S-10, S-11, S-12; pilot results reviewed before full experiment.  
**M4 — Improvement and release:** S-13, S-14 and approved DMAIC iterations.

## Definition of done for every work package

- Acceptance criteria verified by reproducible tests, manual review, or cited engineering evidence.
- Source/license status and safety assumptions documented.
- No existing R functionality removed without approval.
- No secrets, unlicensed documents, or sensitive datasets committed.
- Change reviewed on a feature branch; no direct push to `main`.
- Owner remains **Unassigned** until the team explicitly assigns one.
