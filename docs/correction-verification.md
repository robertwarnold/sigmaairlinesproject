# Offline correction verification

Runtime: Python 3.12.14. Package/schema/profile/mapping: 0.2. All owners Unassigned.

The suite contains 38 tests (11 original tests adapted to the corrected contracts and
27 regression/integration tests). The installed-package test installs a locally built
wheel using --no-index --no-deps into a temporary virtual environment. It runs the real
console executable outside the checkout without PYTHONPATH or provider credentials.

```powershell
python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir .venv/correction-wheels .
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
$env:SIGMA_TEST_WHEEL = (Resolve-Path .venv/correction-wheels/sigma_fmea-0.2.0-py3-none-any.whl).Path
& ./.venv/python-runtimes/cpython-3.12.14-windows-x86_64-none/python.exe -m unittest discover -s tests -v
```

The Python 3.12 runtime required a one-time approved download because it was absent;
package building, installation and tests use no network or API. The local build used
existing setuptools/wheel tooling on Python 3.13; the installed package and full suite
are tested on the Python 3.12 target.

Initial regression execution exposed one test assertion mismatch: missing field evidence
correctly rejected a proposed control before the intended independent-status assertion.
The test now supplies evidence so it directly exercises status validation. No production
validation was weakened to make the test pass.

Demonstrations use examples/context.json and examples/fmeca.json and write fresh ignored
directories under results/integrity-correction/. Generate uses general; convert uses
aerospace. Both outputs remain unauthenticated FMEA drafts. Conversion preserves source
criticality and its declared units; S/O/D/RPN remain null; proposed detection and unknown
legacy detection are not existing controls. Each output has its own artifact ID/version,
CSV, canonical JSON, and manifest; conversion additionally includes its matching report.

Each result is checked using `python -m sigma_fmea validate OUTPUT_DIRECTORY`.
Output reuse must return a nonzero error and leave every previous bundle byte unchanged.
Failed write/rename and KeyboardInterrupt tests prove no partially published directory
is exposed. Hash/corruption tests prove altered sidecars, CSV and canonical content fail.

Remaining limitations: preliminary shared methodology behavior, no authenticated review,
no reviewed public engineering fixture, structural rather than semantic verification of
evidence/control implementation, and no crosswalk/scoring. Process-kill recovery and
filesystem durability limits are documented in integrity.md. Remote CI is not executed
locally. Ready for a draft PR; merge requires correction review, acceptance of these
limits, and green remote CI. No next milestone is authorized by these results.
