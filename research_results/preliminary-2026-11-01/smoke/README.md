# Sigma Airlines real-model pilot — reviewer bundle

Read SOURCE_ROLES_AND_METHODS.md first. This is a reduced preliminary pilot, not an approved FMEA or validated benchmark.

## Status

```json
{
  "planned_generations": 8,
  "attempted": 1,
  "successful": 1,
  "failed": 0,
  "uncertain": 0,
  "data_kind": "real_llm_generation",
  "plan_sha256": "a51b1295d774253feefe4cccee01ff7881135e5d673b981daf95ab090399fc65",
  "remaining": 7
}
```

Smoke source commit: 9a44dab1f498e3ef8cde22caa5a9988b4d871599. Smoke workflow run: 41244305291.
Current packaging run: 41244305291.

## Inspect without any AI calls

- plan.json: frozen systems, profile/prompt/guidance versions, settings, job order and source-code hash. plan-preview.json exists for a no-call preview.
- runs/JOB/input.json and prompt.json: exact engineering inputs and guidance. No benchmark answers belong here.
- runs/JOB/execution.json: actual request (no auth headers), raw response, modelVersion and token usage.
- runs/JOB/bundle/fmea.json, fmea.csv and manifest.json: canonical draft and file integrity hashes.
- runs/JOB/state.json and metrics.json: timing, validation, unknowns, unresolved flags, completeness and coverage availability.
- analysis-RUN_ID/: consolidated CSV, descriptive statistics, PNG/SVG plots and preliminary-findings.md. The smoke report may contain only one observation.
- Failures and uncertain attempts are preserved. No automatic retries or fabricated replacement sheets.

## Verify files

From the extracted bundle root:

```python
from pathlib import Path
import hashlib
root = Path('.')
for line in (root / 'checksums.sha256').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
print('Bundle checksums verified')
```

To validate each FMEA offline, set PYTHONPATH to reproduction/src and run python -m sigma_fmea validate runs/JOB/bundle.
To recompute CSVs/reports without an AI call: python -m sigma_fmea analyze . --output independent-analysis --no-plots.
For plots, install matplotlib locally and omit --no-plots. Do not rerun generation merely to inspect this evidence.

## Reproduce a new experiment

Use the archived reproduction/ source and pilot-eight.json on Python 3.12. The generation commands require explicit paid approval and a locally configured GEMINI_API_KEY.
Run experiment plan, then one smoke (max-calls 1), inspect it, then batch (max-calls 8) only after approval for seven additional calls. Use a new output directory.
The requested model is fixed to gemini-3.8-flash; actual modelVersion must remain identical. The provider may update a stable alias: this is not an immutable snapshot guarantee.
Repeating a live model request need not yield identical text. Recomputing the stored deterministic metrics does not require the service.

No reviewed references currently support missed-mode percentages for the two scenario inputs. Unavailable coverage is not zero. Structural completeness is not correctness.
No credentials, full NASA PDFs, reference FMECA answers or validated ground truth are included. All owners remain Unassigned.
