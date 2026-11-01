# Sigma Airlines FMEA engineering support

This repository supports two distinct Python workflows and preserves a historical R
prototype. All generated analyses require engineering review.

- **Standalone Gemini skill v2.0:** `fmea_generator.py` uses
  `skill/fmea_instructions.md` and input packages `system_descriptions/system_A.txt`
  through `system_E.txt`. It estimates provisional S/O/D scores and calculates RPN.
- **Canonical research package:** `src/sigma_fmea/` provides profiles, provider
  integrations, controlled experiments, validation, evaluation and auditable
  FMECA-to-FMEA conversion. Its unrated policies intentionally leave unsupported
  target risk ratings null, including when converting source risk data.
- **Historical research:** `fmea_generator.R`, `run_experiment.R`, `README.txt` and
  `project.Rproj` preserve the original R prototype. They are not the current Python
  entry points. See [cleanup decisions](docs/fmea-v2-integration.md).

Do not pool standalone v2 and canonical research outputs as one experimental
condition: they use different prompts, schemas, scoring policies and research aims.
Keep prompt versions separate as well.

The archived `research_results/preliminary-2026-11-01/` evidence is frozen. Its
preliminary smoke result demonstrates execution, not engineering accuracy or a
completed eight-run comparison. See [the historical reviewer guide](docs/pilot-reviewer.md)
and [the four-dataset amendment](docs/four-dataset-pilot.md) for provenance and
limitations; preparation-time status statements describe those historical snapshots.

## Standalone Gemini v2

Use Python 3.12 or 3.13 and install `python -m pip install -r requirements.txt`.
Configure `GEMINI_API_KEY` locally (environment or ignored `.env`). The following
command makes one paid generation; run it only with explicit generation authorization:

```powershell
python fmea_generator.py --system system_descriptions/system_A.txt --case-id system_A --version v2.0 --run 1 --model YOUR_MODEL_ID
```

Outputs go to ignored `results/`. The version must match the active prompt and the
run number must be a positive integer. Either existing CSV or raw-response output
blocks the request. Exclusive file creation prevents overwriting; a raw-output file
is reserved before calling Gemini. Failed calls can leave an empty reservation, and
invalid/truncated responses retain raw text for manual inspection. Inspect these
before choosing a fresh run number; never automatically retry an uncertain paid call.
Provisional scores and RPN are hypotheses requiring engineering review, not approved
risk assessments. The skill text and its v2.0 version remain bound together.

## Team generation with the shared Gemini secret

Store the team's key as a repository Actions secret named `GEMINI_API_KEY`
under **Settings > Secrets and variables > Actions**. Do not commit a key or `.env`.
The generator already reads this environment variable; GitHub supplies it during
the generation step. Local runs still need a locally configured key.

After `.github/workflows/generate-fmea.yml` is pushed to the default branch,
teammates with write access can open **Actions > Generate FMEA with shared Gemini key >
Run workflow**, select a system description and an accessible model, and start a run.
This manually triggered workflow uses the team's API quota; pushes and pull requests
do not trigger generation. A model overload (503) may require trying again later.

Open the completed run and download **fmea-results-...** under **Artifacts** for
the CSV and raw model response. Results are retained for 14 days, including a raw
response when generation succeeds but parsing fails. Outputs require engineering review.

### Run from Terminal using GitHub CLI

These commands start generation on GitHub using the shared secret, then download
the results to your computer. No local `.env` is needed. Running
`python fmea_generator.py` directly on your computer still requires a local key;
it cannot retrieve the repository secret.

On macOS, install GitHub CLI with Homebrew and sign in once:

```bash
brew install gh
gh auth login
```

From your cloned project folder, start the workflow (it must already be pushed
to the repository's default branch):

```bash
gh workflow run generate-fmea.yml \
  -f system=system_2_nasa_fmeca \
  -f model=gemini-3.8-flash
```

Use `-f system=system_1` for the original hydraulic system. Each workflow run
uses the shared account's API quota.

Find your run by its time and user in the list:

```bash
gh run list --workflow generate-fmea.yml --limit 5
```

Replace `RUN_ID` below with the numeric ID of your run. Watch it until it finishes,
then download the artifact:

```bash
gh run watch RUN_ID
gh run download RUN_ID --dir results/github/RUN_ID
```

The downloaded artifact contains the CSV and raw response when generation succeeds.
For failures, inspect the run logs with `gh run view RUN_ID --log-failed`.
If the key is missing, configure the `GEMINI_API_KEY` repository Actions secret.
If Google returns 503, wait and start a new workflow run.


**Research deadline prototype:** real OpenAI/Anthropic adapters, baseline/improved
conditions, a 24-generation runner, deterministic evaluation and descriptive analysis
are now available locally. Start with [the research runbook](docs/research-prototype.md).
Paid calls require explicit approval; offline mock and the converter remain available.

Python-first offline milestone. Outputs are **FMEA drafts requiring engineering review**.
The original R scripts and README.txt remain the historical baseline.

## Canonical package and offline tests

Python 3.12 is the target runtime (3.13 is also tested). From the repository root in PowerShell:

```powershell
python -m pip install --upgrade setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e ".[analysis]"
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -m sigma_fmea profiles
python -m sigma_fmea generate --context examples/context.json --profile general --output results/mock
python -m sigma_fmea convert --context examples/context.json --profile aerospace --input examples/fmeca.json --output results/conversion
python -m sigma_fmea validate results/mock
python -m sigma_fmea validate results/conversion
python -m unittest discover -s tests -v
```

For a console command, install with `python -m pip install -e .` and use `sigma-fmea`.
Installation may require a locally available setuptools build backend; source execution
and model/conversion tests need only Python's standard library. The installed-CLI test
also requires pip, venv/ensurepip, and either local setuptools/wheel build tools or a
prebuilt wheel supplied in `SIGMA_TEST_WHEEL`. Its install uses `--no-index --no-deps`
in a temporary isolated environment, clears provider keys and PYTHONPATH, and runs the
actual console executable outside the repository. All tests and build/install steps
run offline with those tools available. There are no API calls or credentials.

The complete suite also tests the standalone Gemini SDK with mocked clients, so it
requires `requirements.txt`. Install dependencies before running offline tests; package
installation may require network access. Tests never need live provider credentials.

For a target runtime without local build tools, build once using an available Python
with setuptools/wheel, then run the suite on Python 3.12:

```powershell
python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir .venv/test-wheels .
$env:SIGMA_TEST_WHEEL = (Resolve-Path .venv/test-wheels/sigma_fmea-0.3.0-py3-none-any.whl).Path
# Run using your Python 3.12 interpreter:
python -m unittest discover -s tests -v
```

## Scope and profiles

Select `general`, `dfmea`, `pfmea`, or `aerospace` explicitly. All four are initial
**preliminary unrated team-policy profiles**, sharing the core field contract. Version
0.3 adds distinct workflows, context-gap checks, review questions and mock hypotheses.
Licensed methodology-specific procedures, scoring, and action-priority tables remain
unimplemented. No standards-compliance claim is made.
The methodology registry references IEC, AIAG–VDA, SAE, ASQ, and NASA and distinguishes
bibliographic references from reviewed guidance. Additional sources require registry review.

The deterministic mock creates one loss-of-function hypothesis per context item. It
does not assess failure coverage, establish causes/effects, or supply ratings. Context
evidence supports the item/function, not the generated hypothesis. Missing content is
identified explicitly. The canonical package implements OpenAI Responses, Anthropic
Messages and Gemini REST adapters in `src/sigma_fmea/llm.py`, plus the offline mock.
The standalone generator uses the Google Gen AI SDK. No Ollama adapter exists.

## Conversion and artifacts

CSV or JSON source records must use the documented field map in
[docs/architecture.md](docs/architecture.md). JSON input is an array; CSV cells are
literal strings (including numeric source ratings), not automatically interpreted JSON.
CSV headers are normalized with Unicode NFKC, trimming, case folding, and space-to-
underscore replacement. Blank/duplicate normalized headers, malformed quoting, and
row-width mismatches are rejected. Original header spellings are retained. JSON duplicate
keys at every depth and nonfinite numbers are rejected at every CLI JSON boundary.
CSV `controls` cells may contain strict JSON arrays; other CSV fields remain strings.
The converter requires a source ID, locator, edition, and item. Keep source scope,
hierarchy, phase, and definitions in source metadata; reconcile them with target context
through engineering review. Unknown source fields remain in the report.

Each conversion produces `fmea.json`, `fmea.csv`, `conversion_report.json`, and `manifest.json`.
The report preserves original records, hashes, field mappings, unmapped content, and
review flags. Keep it with the FMEA; the FMEA alone is not the complete conversion record.
Source criticality, severity, likelihood, detection, D/P, probability, RPN, and declared
units remain source metadata. Target ratings stay null. No risk-scale crosswalk exists.

Controls are individual objects with `kind` (`prevention`, `detection`, `mitigation`),
`description`, `status` (`implemented`, `proposed`, `unknown`), and `evidence_refs`.
Only individually evidenced implemented controls populate existing-control lists.
Proposed and unknown controls retain their statuses and flags; they are never promoted.
Legacy text control columns become unknown-status controls. A shared `controls_status`
is preserved as unmapped data and never determines implementation.

JSON is canonical. Nested CSV cells contain JSON; null scalar cells are empty. CSV
formula-like text is escaped for spreadsheet viewing. The JSON carries full analysis
context. Export requires a **new output directory**. Reuse is rejected, preserving the
previous bundle. Files are flushed in a hidden sibling staging directory, verified,
then published with one same-filesystem directory rename. A manifest binds the artifact
identity, content version, mapping version, and file hashes. Validate the directory to
check JSON/CSV consistency, preserved-source hashes, report mappings, and file identities.
Validating only `fmea.json` checks the draft, not the complete bundle.

Package/profile versions are now 0.3; schema/mapping remain 0.2. Profile 0.2 remains
supported when validating existing bundles. Old 0.1 drafts require regeneration from
retained original inputs; they are rejected rather than silently migrated. Hashes detect
inconsistency, not malicious re-authoring or authenticated authorship. See
[docs/integrity.md](docs/integrity.md) for transaction/review limits.

Examples are **synthetic software fixtures**, not reviewed NASA benchmarks. Source
documents, secrets, benchmarks, and experimental outputs are excluded from Git.

The separate `tests/fixtures/nasa_2019_candidate.json` is a two-row public-source
conversion candidate, not an approved benchmark. Its page locators, source definitions,
review gaps and generation exclusion are documented in [docs/public-conversion-candidate.md](docs/public-conversion-candidate.md).

Inspect profile-specific gaps without generation:

```powershell
python -m sigma_fmea scope --context examples/context.json --profile dfmea
```

Missing profile context produces persistent review flags; the tool does not infer
requirements, interfaces, mission phases or process assumptions. General asks for an
analysis hierarchy; DFMEA adds design requirement/interface traceability; PFMEA asks for
phase, output requirements and process assumptions; Aerospace asks for hierarchy, phase,
interfaces and assumptions. These checks test presence, not engineering adequacy.

## Verification and limitations

Tests cover the original offline behavior and the engineering-review regressions:
duplicate keys/headers, malformed CSV, mixed controls, provenance contradictions,
source mutation/checksums, review-version binding, nonfinite/non-JSON values, bundle
reuse/corruption, failed/interrupted publication, and installed console execution.
They establish software behavior, not engineering validity.

The research prototype adds allowlisted guidance retrieval, real-provider adapters,
an experiment runner and descriptive reporting; see docs/research-prototype.md.
Actual paid generation still requires configured credentials and explicit approval.
The canonical package has no PDF/DOCX importer, reviewed crosswalk, RPN calculator, authenticated review,
LLM judge, vector database, or frontend. Review-decision
metadata validates zoned ISO timestamps and exact content-version binding, but reviewer
identity is not authenticated. Unresolved flags remain attached to decisions and
`approval_status` must stay `unauthenticated_draft`. Providers cannot create review
decisions. A future controlled workflow must establish approval authority.

### Skill v2.0 (`skill/fmea_instructions.md`)

CSV rows and file names carry `version` v2.0; do not pool them with v1.0 sheets as one condition.
Intentional differences from v1.0 that change what a comparison measures:

- v1.0 analysed "ONLY the supplied system description"; v2.0 allows general engineering
  knowledge for modes, causes, effects and actions, but forbids recalled details of a known design.
- One row per individual unit ("Motor 1", "Motor 2"), never grouped. Grouped reference
  sheets ("Motor #1-#4") must be expanded to one row per unit before matching.
- Banded severity/detection scales; occurrence from apportioned package failure rates or
  calibration anchors; detection only from provisions the package states.

The generator uses the selected model's own maximum output length, fails with a clear error
when the response is truncated or stops for any other reason (raw output is still saved),
and rejects the whole sheet if any text cell is empty.
