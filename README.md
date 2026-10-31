# Sigma Airlines FMEA engineering support

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

## Run without credentials or third-party runtime packages

Python 3.12 is the target runtime (3.13 is also tested). From the repository root in PowerShell:

```powershell
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
identified explicitly. Provider adapters for OpenAI, Anthropic, and Ollama are future work.

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
There is no PDF/DOCX importer, reviewed crosswalk, RPN calculator, authenticated review,
LLM judge, vector database, or frontend. Review-decision
metadata validates zoned ISO timestamps and exact content-version binding, but reviewer
identity is not authenticated. Unresolved flags remain attached to decisions and
`approval_status` must stay `unauthenticated_draft`. Providers cannot create review
decisions. A future controlled workflow must establish approval authority.

## RUN PROPERLY - FROM ROBERT

python fmea_generator.py --system system_descriptions/system_2_nasa_fmeca.txt --case-id system_2 --model gemini-3.8-flash
