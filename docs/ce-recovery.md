# Manual C/E recovery and offline financial reconciliation

Original campaign: `20261101T184141Z-B-E-v2`. B/D succeeded; C/E returned
provider HTTP 503 failures. Original records and frozen research evidence remain intact.
Neither workflow is dispatched by push or pull request. No new requests are authorized by this PR.

## Original artifacts and runner access

The original manifest, status and four per-system execution sidecars live locally under
`results/multi-system-pilot/20261101T184141Z-B-E-v2/`; B/D CSVs are in their
system subdirectories. This ignored directory is absent on GitHub-hosted runners.
Original per-system Actions artifacts expire after 14 days and do not by themselves
contain the assembled campaign manifest. Never assume they can restore the campaign.

After approval, configure a trusted self-hosted runner with access to the original
campaign directory (or privately copy the original directory there). Manually run
`Stage Original FMEA Campaign`, passing its absolute directory as `original_directory`.
It uploads the directory as `original-fmea-20261101T184141Z-B-E-v2` without committing
outputs. The upload includes generated content, so use repository artifact access only
as approved by the team; private storage/local reconciliation remains available.
No reference/ground-truth worksheets belong in this directory.

The recovery workflow requires this staging run ID and downloads that exact artifact
with read-only Actions permission. Missing/expired artifacts block initialization before
any paid request. Restored original artifacts are hash checked and B/D CSVs validated.
A self-hosted runner is required only for staging; recovery uses Ubuntu. Availability of
that runner and original files is an operational prerequisite, not provisioned here.
Download artifacts to private storage before their 14-day expiry.

## Dispatch after approval

Use Actions > Recover Failed FMEA Systems > Run workflow, selecting the reviewed branch
(or main after merge). Set original_campaign_id to the ID above, original_artifact_run_id
to the successful staging run, and systems to `system_C`, `system_E`, or
`system_C_system_E`. At most one request per selected system; no retries, fallback models,
or workflow reruns. A later recovery needs a new explicit human authorization.

Live updates appear in the Actions recover job log, including 30-second elapsed heartbeats.
The plan and per-attempt receipts record outcomes. The always-run upload preserves successful
and failed attempts plus partial reconciliation under `fmea-recovery-<recovery-id>-<run-id>`.
Hard runner loss/cancellation can prevent final receipt/upload; inspect logs before any new call.

## Offline use and financial output

Run `python scripts/recover_fmea.py --original-dir <original-directory> reconcile
--plan <plan.json> --recovery <recovery-root> --output results/reconciliation` on one line.
For successive offline batches pass `--history <previous-reconciliation_manifest.json>`
(repeatable) to retain earlier attempts and effective results. Restore the referenced earlier
CSV paths locally; conflicting evidence or an already selected replacement is rejected.
The hosted workflow handles one recovery batch; cumulative cross-batch selection is an
explicit offline operation, never an automatic retry.

Each reconciliation uses a fresh original-ID/recovery-ID directory. It writes
`effective_campaign_summary.csv`, `all_attempts_history.csv`, `reconciliation_manifest.json`,
and a versioned `financial_impacts/financial-v1/` package using the existing
financial reporting framework. Existing reports are never replaced. All generated packages
stay under ignored results, not public source control.

Financial ingestion retains original B/D successes, C/E failures, all supplied recovery
receipts, elapsed durations and available token usage. Effective-result selection is separate
from complete request history. Provider invoices are unknown unless supplied; token tariff
estimates are labeled estimates. Full request expense divided by successful generations is
unavailable when any required expense is unknown. Engineering acceptance, labor savings and
other unmeasured financial outcomes remain unavailable. Existing assumption scenarios remain
separate from observations. The standard financial CLI can rebuild reports offline from a
reconciliation manifest and supply invoices with `<experiment-id>/<attempt-id>` keys.

Acceptance requires a successful receipt, correct campaign/failed-attempt/system linkage,
matching model, temperature, skill version/hash and input hash, exact CSV artifact hash,
and valid headers, row widths, ratings and calculated RPN. Invalid CSVs remain unresolved.
Original B/D are always selected unchanged. Partial C-only or E-only recovery is supported.

Implementation files: `scripts/recover_fmea.py`, the two manual workflows,
`analysis/financial_impact/{ingest,metrics}.py`, and `tests/test_recover_fmea.py`.
Offline tests use synthetic fixtures only; neither tests nor reports call Gemini.

## Authorized bounded HTTP 503 recovery (2026-11-01 work order)

The user explicitly authorized local orchestration and up to six new C/E requests,
with at most three per system and retries only after a verified SDK HTTP 503.
This campaign-specific authorization overrides the original one-request/no-retry
operational rule; the engineering generator and v2.0 skill remain unchanged.

`scripts/provider_recovery.py` provides a reusable verified-503 classifier/delay policy,
offline local preflight, a durable sequential controller and a single-request remote adapter.
The local environment has no Gemini credential, so the existing `generate-fmea.yml`
workflow supports `ce_recovery_single` on the recovery branch, using its existing secret.
This path requires no self-hosted runner: originals are validated/reconciled locally;
remote jobs restore a no-generation preflight from the same commit and verify frozen
Git inputs/schema/model/SDK before each unchanged generator call. SDK retries stay disabled.

Prepare once: `python scripts/provider_recovery.py preflight --folder results/<unique-folder>`.
Execute once: `python scripts/provider_recovery.py worker --folder results/<unique-folder>
--wrapper .venv/github-cli/gh_authenticated.py --branch fmea-ce-recovery-20261101` on one line.
Explicit human authorization for the configured request budget is required before execution.
A persistent worker lock forbids restarting; dispatch reservation is saved before each POST.
Uncertain dispatch/evidence stops execution, never repeats a request. Each attempt has a
unique workflow batch ID and artifact; duplicate dispatch/reruns are rejected remotely.

Delays are 60 then 120 seconds; a valid Retry-After can extend a wait to at most 600 seconds.
Longer/invalid instructions leave the system unresolved rather than violating limits.
Actual waits, typed HTTP status, sanitized diagnostics, timestamps, durations, usage and
unknown provider billing are retained per attempt. STATUS.md/status.json and live logs live
in the campaign directory; runner logs emit 30-second request heartbeats. A failed 503 is
operational evidence only. Reconciliation includes all retry receipts, selects one valid
success per system and rejects multiple successes. Financial metrics count availability
failures and waiting separately from schema validity and engineering acceptance.

New code/tests: `scripts/provider_recovery.py`, `tests/test_provider_recovery.py`;
existing recovery reconciliation and financial ingestion/metrics are extended accordingly.

## Consolidated local review

After the bounded controller finishes, run `python scripts/complete_recovery_review.py
results/<campaign-folder>` on one line. The offline finalizer verifies unchanged source
and original-campaign checksums, copies the reconciled B-E reports into a new `results/ce-review/<recovery-id>-v1/`,
indexes every successful A pilot draft separately and selects run 3 chronologically for
representative A-E comparisons. It produces aggregate CSV/JSON tables, provisional S/O/D
and RPN figures, lexical component review candidates (no invented coverage fraction),
a complete A-E financial report with all historical requests, integrity hashes and a
local ZIP. Verified historical 503 evidence can be supplied in
`original_provider_evidence.json`; original receipts themselves remain unchanged.
The ZIP contains generated CSVs and sanitized operational metadata, not secrets or
reference worksheets. All outputs stay ignored under results. The finalizer and its
synthetic tests are `scripts/complete_recovery_review.py` and
`tests/test_complete_recovery_review.py`. It never dispatches or calls a provider.

A no-response transport disconnect has no verified HTTP status and is never treated as
HTTP 503. Even if request budget remains, the bounded policy does not authorize a repeat
of that system. Preserve the uncertain bill and request receipt, leave the system unresolved,
and report the specific transport failure for human review. Do not change generator behavior
or infer an engineering-quality defect from that operational outcome.

Windows-safe report layout: bounded-controller reconciliation lives under
`results/ce-r/<original-id>/<recovery-id>/` and records its manifest path in status.json.
Financial package IDs are short (`financial-v1`, `A-E-financial-v1`) because the enclosing
campaign directory already supplies unique identity. This prevents Windows MAX_PATH
failures without overwriting any earlier failed staging or successful report directory.
Downloaded Actions artifacts are also retained under `results/github/<run-id>/`.

The offline reviewer explicitly accepts System A's historical `generation_minutes`
metadata column, preserving the original CSV and enforcing the same FMEA content,
rating and RPN validation. Recovery CSV headers remain strict. Use `--version v2`
(or a later integer) for a fresh immutable review rebuild; failed earlier directories
are preserved rather than overwritten.

Runtime configurations are compared exactly against the original B engine receipt.
The unchanged SDK serializes source schema aliases/order in place; source prompt/schema
hashes are separately checked during preflight. Comparing a serialized SDK receipt
against the pre-SDK Python dictionary would falsely flag that representation change.

## Separately authorized C-only six-request follow-up

A subsequent user instruction authorized up to **six additional C requests**, stopping
at the first valid FMEA. This does not authorize any E/A/B/D generation. Prepare with
`provider_recovery.py c-preflight --folder results/<unique-folder>` and execute once with
`c-worker --folder ... --wrapper ... --history <latest-reconciliation-manifest> --branch ...`.
The plan records the distinct C-only authorization and a six-request cap. This extension
retries verified HTTP503 and typed `httpx.RemoteProtocolError`/`ReadTimeout` failures;
other errors and invalid output stop the campaign. Delays are 60/120/180/240/300 seconds,
extended for a feasible provider Retry-After. SDK retries remain disabled. Request
reservations, one-shot locking, identity/integrity checks and previous-history preservation
remain intact. Report validation allows six C attempts only for this explicit C-only plan;
the original C/E policy stays at three per system and six total.
