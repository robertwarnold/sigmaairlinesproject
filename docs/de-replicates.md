# Three additional datasets each for D and E

This campaign generates six new independent FMEA drafts, not replacements for existing
D/E results. Original data and previous reports remain unchanged. Inputs, skill v2.0,
model gemini-3.8-flash, temperature 0, schema, 65536-token limit and SDK 1.75.0 remain
frozen against the original B-E experiment. The generator and skill are unchanged.

The user authorized three additional valid sets per system and selected up to twelve
requests total for provider failures. All six initial slots run before retries. Each
slot has at most three attempts; successful slots never repeat. The shared cap is twelve,
with at least three initial requests reserved for each system (at most nine for either).
Only verified503 and typed remote-disconnect/read-timeout failures permit retries,
with 60/120-second waits and feasible Retry-After handling. SDK automatic retries are
disabled. Authentication/configuration problems or uncertain dispatch/evidence stop execution.

Prepare: `python scripts/system_replicates.py prepare --folder results/<unique-folder>
--request-limit 12 --baseline-index <latest-A-E-dataset-index.json>` on one line.
After tests pass and source is pushed, run once:
`python scripts/system_replicates.py worker --folder results/<unique-folder>
--wrapper .venv/github-cli/gh_authenticated.py --branch fmea-ce-recovery-20261101`.
Preparation must use the same source commit as the workflow preflight.

The durable local controller dispatches manual generate-fmea.yml with mode
replicate_single through the existing repository secret, so originals need not be staged
on a hosted runner. A same-commit no-generation preflight is restored before every call.
Each D/E replicate has a separate run number (1/2/3), directory, operational attempt ID
and workflow batch ID. Worker locks, reservations before POST and remote duplicate/rerun
rejection prevent unapproved repeats. Progress lives in STATUS.md/status.json/live.log;
remote request logs emit 30-second heartbeats. Always-run uploads retain failures and
successes. Downloads live in results/github/<run-id>/; Actions retention is 14 days.

Offline reports: `python scripts/system_replicates.py complete --folder results/<folder>`.
The new immutable review-v1 contains replicate-index.csv, campaign-summary.json,
campaign-manifest.json, separate successful CSVs, provisional rating distributions,
structural review candidates, descriptive comparison figures and a versioned financial
package using the existing framework. A local ZIP and hashes support review. Financial
reports retain all requests and unknown bills, with costs labeled token estimates or
invoices. No manual time/savings or engineering acceptance is invented. Generated rows
are nested inside drafts; n=3 descriptive variation is not validated engineering
repeatability or benchmark coverage. Existing D/E originals remain separate observations.

Implementation: scripts/system_replicates.py, tests/test_system_replicates.py, the
manual generate-fmea workflow, and the shared dispatch helper. No reference FMEA is
read or transmitted. All generated material remains ignored under results; never commit
raw model responses, FMEA CSVs, credentials or frozen research evidence.
