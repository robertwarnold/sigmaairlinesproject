# Sigma Airlines — Codex Foundation Work Order (v2)

**Status:** Proposed development instructions — review before implementation  
**Repository:** https://github.com/robertwarnold/sigmaairlinesproject  
**Working branch:** `feat/fmea-foundation` (verify, do not assume)  
**Primary output:** Engineering-reviewable **FMEA**, not FMECA  
**Ownership:** All work packages unassigned until the team decides

## 1. Mission and research boundary

Modernize the existing R/Anthropic FMEA pilot into a **Python-first, provider-agnostic, multi-methodology AI skill for drafting Failure Modes and Effects Analyses (FMEAs)**. It must:

1. Use a curated collection of recognized **FMEA generation guidance**, not rely on NASA alone.
2. Support documented methodology profiles (e.g., general FMEA, design FMEA, process FMEA, aerospace functional FMEA), rather than claim one universal FMEA format.
3. **Translate appropriate FMECA source records into FMEA-format records** through an explicit, loss-aware, auditable conversion workflow. Conversion is not the same as generation.
4. Generate evidence-linked draft FMEAs from engineering descriptions, functions, components, requirements, interfaces, and applicable source guidance.
5. Support **mock/offline**, **local LLM**, and optional **cloud LLM** providers without requiring an Anthropic key to install, test, or use the skill.
6. Measure completeness, missed modes, unsupported/duplicative modes, agreement with reviewed reference FMEAs, consistency, and review effort.
7. Require human engineering review for risk ratings and acceptance; do not claim certification, NASA endorsement, or autonomous safety authority.

Preserve the current R prototype as a baseline unless a change is approved. Do not implement an elaborate UI before the core workflow and evaluation are working.

## 2. Workspace inputs

Read these local files if present:
- `reference_materials/Research_design_Sigma Airlines.docx`
- `reference_materials/GSFC-HDBK-8004_Approved_1.pdf`
- `reference_materials/FMEA_AI_Literature_Review_Draft.docx`
- `SIGMA_AIRLINES_TASK_LEDGER.md`
- `SIGMA_AIRLINES_METHODOLOGY_AND_CONVERSION.md`

If a file is missing or unreadable, report that fact. Do not imply it was reviewed. These are reference inputs, not blanket permission to commit them to a public repository or send them to cloud models.

### Research protocol to preserve
The research-design document specifies **4 system cases × 25 replications × 5 skill versions (baseline + 4 improvements) = up to 500 generated FMEA sheets**. The primary research measures are missed failure modes against expert-reviewed ground truth and structural completeness. Preserve this plan as a *proposed protocol*, not an automatic job to launch. Calibrate an independent evaluator with human reviews. The source NASA FMECA reports require curated conversion and validation before becoming FMEA benchmarks.

## 3. Multi-source methodology, not NASA-only

Build a **source registry** with edition/year, publisher, official URL or bibliographic citation, access/license status, source type, applicable FMEA variant, section/page reference, and verification status. Candidate sources:

- **IEC 60812:2018** — broad FMEA/FMECA process guidance (check licensed access to normative details).
- **AIAG–VDA FMEA Handbook** — structured DFMEA/PFMEA process and action-priority concepts (check edition and licensed access).
- **SAE J1739** — design/process FMEA conventions and scoring (check applicable revision and licensed access).
- **ASQ public FMEA guidance** — accessible introductory FMEA process and terminology; not a replacement for a full standard.
- **NASA GSFC-HDBK-8004 (2024)** — aerospace FMECA and failure-propagation guidance; supporting profile, not the universal default.
- **MIL-STD-1629A** and historical professional FMECA workbooks — FMECA legacy concepts and conversion/benchmark evidence, not a substitute for modern FMEA-specific guidance.

Do not copy paywalled rating tables or proprietary handbook text into the repository without permission. Do not assert full compliance with standards that have not been accessed and verified. Separate **verified normative rule**, **public summary**, **engineering team policy**, and **inferred suggestion** in the registry.

### Methodology profiles and conflict resolution
- Profiles select analysis type, steps, required fields, rating scale, prioritization scheme, and output template.
- A user can select a primary profile and optionally reference supplemental sources; **never silently blend incompatible scales**.
- When sources disagree, show a conflict/decision record with the selected primary rule and rationale. Require explicit review for material differences.
- Keep source references on each generated or converted row, with provenance type `source`, `derived`, or `hypothesis`.
- Default output is an **FMEA draft**. Optional FMECA metadata may be preserved separately but must not be mislabeled as FMEA S/O/D.

## 4. Explicit FMECA → FMEA conversion workstream

Build a converter independent of the generative AI model. It must:

1. Ingest a source FMECA worksheet/table while preserving the original record and source ID, page/table, and edition.
2. Record the original analysis scope, system hierarchy, failure-mode level, operating phase, assumptions, and risk scheme.
3. Map supported fields to a **canonical FMEA schema**: item/step, function, failure mode, effects (local/next-level/end), cause, existing prevention controls, existing detection controls, recommended action, and provenance.
4. Distinguish **existing controls** from **proposed mitigations**, and retain FMECA-only criticality and likelihood information as separate source metadata.
5. Never automatically reinterpret FMECA criticality or NASA likelihood/detection-prevention values as generic 1–10 S/O/D scores. Use an explicitly reviewed, versioned crosswalk only when justified. Leave unavailable FMEA ratings `null` with a reason and review flag. Calculate RPN in deterministic code **only if** all three compatible S/O/D ratings exist under a documented profile.
6. Flag missing fields, ambiguous meanings, mixed levels of decomposition, duplicate modes, multi-cause rows, and source-table extraction uncertainty.
7. Produce a field-by-field conversion report: direct mapping / normalized / inferred (needs review) / unavailable / dropped (with rationale). Do not fabricate an approved FMEA.
8. Validate representative conversions against original source pages with human review. Freeze approved benchmark versions with hashes; **do not expose evaluation-system ground truth to the generation model or its retrieval corpus**.

For full details, see `SIGMA_AIRLINES_METHODOLOGY_AND_CONVERSION.md`.

## 5. Proposed Python architecture (R remains preserved)

Use a simple `src/sigma_fmea/` package, `tests/`, `docs/`, `examples/`, `data/`, and `results/`. Suggested modules:

- `models/`: typed system context, FMEA row, source/evidence, ratings, conversion trace, review decision, run metadata.
- `methodology/`: standards source registry, profile selection, rules, conflict handling, rating profiles.
- `conversion/`: FMECA importers, field mapping, validation, conversion report, human-review flags.
- `ingest/`: structured CSV/JSON and text first; PDF/DOCX later with reliable extraction and page references.
- `retrieval/`: curated guidance/examples with source provenance; strict benchmark holdout.
- `providers/`: one stable provider interface, `mock` (offline), optional `ollama`, `openai`, `anthropic`; no API key needed for mock mode.
- `generation/`: scope interview, missing-information detection, evidence retrieval, candidate mode generation, structured parsing.
- `validation/`: deterministic schema checks, duplicate checks, rating-profile checks, unsupported-claim flags.
- `review/`: draft/accepted/rejected status, reviewer rationale, CSV/JSON/Excel export, no autonomous approval.
- `evaluation/`: deterministic metrics, human-calibrated independent judge, benchmark matching, error analysis.
- `experiment/`: repeatable configuration and run logging, frozen versions/hashes, errors, retries, cost and timing.
- `analysis/`: DMAIC/SPC reporting; avoid unjustified normality and capability assumptions for bounded percentages.
- `skills/fmea-generator/SKILL.md`: Codex/agent-facing instructions to operate the skill safely.

Implement only the minimum needed for each approved milestone. Avoid complex frameworks unless evidence justifies them.

## 6. Priority and staged execution

**Phase 0 — Audit and design (NOW, no substantial implementation):**
- Verify Git branch, remotes, clean state, existing R behavior, source files, and references.
- Review `SIGMA_AIRLINES_TASK_LEDGER.md`; propose any necessary changes without assigning owners.
- Produce source inventory and gaps, architecture diagram, schema draft, conversion rules, methodology-profile decision record, and milestone plan.
- Identify which standard details require legitimate access or human engineering interpretation.
- **STOP for approval** before building the application, calling paid APIs, or committing/pushing.

**Phase 1 — Offline vertical slice (after approval):**
- Python package, tests, linting, CI, mock provider, canonical FMEA schema.
- One documented methodology profile with explicitly sourced *publicly usable* rules.
- One small, hand-checked FMECA→FMEA conversion fixture with an auditable mapping report.
- End-to-end mock FMEA generation, validation, and CSV/JSON export without credentials.

**Phase 2 — Source and provider expansion:**
- Source registry, additional licensed/verified profiles, optional local/cloud adapters, input ingestion, retrieval and evidence traceability.

**Phase 3 — Benchmark and experiments:**
- Reviewed NASA FMECA-to-FMEA benchmark conversions; independent judge calibration; repeated run harness; controlled research pilot.

**Phase 4 — DMAIC improvement:**
- Four approved improvement iterations, comparative metrics, SPC/appropriate capability analysis, final report.

## 7. Research and quality safeguards

- Source corpus and benchmark ground truth must be separated to prevent leakage.
- The unit of observation is **one generated FMEA sheet**. Record row-level and sheet-level metrics separately.
- Define failure-mode matching criteria and adjudicate disagreements; an LLM judge is an instrument, not automatically ground truth.
- Record input, prompt, model, provider, method profile, schema, judge rubric, source versions, sampling settings, timestamps, token/cost data, and run errors.
- Freeze inputs/settings within a comparison. Do not start the 500-run study without cost, scope, and review approval.
- Define specifications and inspect distributions before calculating Cpk; proportions may require non-normal methods.
- Never invent failure rates, requirements, risk scores, citations, or approval status.
- No secrets, proprietary files, licensed standards, or sensitive source documents in commits without explicit permission.

## 8. Git and collaboration

- Work on a feature branch, not `main`; no force push.
- Do not assign work packages to named people. Use `Owner: Unassigned` in the task ledger.
- Avoid editing another contributor's work without coordination. Prefer small PRs with tests.
- Do not commit or push without approval.
- Keep all original R files intact and document compatibility.

## 9. Codex's immediate assignment

**Do not implement yet.** Read the repository, three reference documents, and the two companion Markdown planning files. Return:

1. Baseline repository inventory and risks.
2. Proposed **multi-source FMEA** methodology hierarchy and evidence governance.
3. Draft canonical FMEA schema and **FMECA→FMEA mapping/crosswalk** with unknown-value policy.
4. Provider-independent architecture and offline test plan.
5. Updated task ledger review: priorities, dependencies, acceptance criteria, all owners **unassigned**.
6. Questions requiring engineering decisions or licensed source access.
7. The smallest Phase 1 implementation proposal.

**Stop and ask for approval before modifying implementation files, running paid API calls, committing, or pushing.**
