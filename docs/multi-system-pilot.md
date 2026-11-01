# Fixed B-E v2.0 pilot with live local status

This campaign is exactly one authorized request per system, in B/C/D/E order.
There is no replication-count parameter and no automatic retry or replacement.
`fmea_generator.generate_fmea()` remains the sole engine; instructions, inputs,
temperature zero, Gemini 3.8 Flash, schema, SDK 1.75.0 and the 65,536-token cap are
checked against the System A condition. The financial implementation is unchanged.

The team credential remains in GitHub Actions. The existing manual generation
workflow has a no-generation `multi_system_preflight` and a one-request
`multi_system_single` mode. Separate workflows provide an artifact per system,
avoiding the previous all-results-at-the-end visibility problem. Preflight source
SHA and hashes must match. Duplicate system/campaign dispatches and workflow reruns
are blocked before the model boundary. No unrelated pilot mode is dispatched.

`scripts/multi_system_pilot.py` initializes an unused ignored campaign directory
and runs a detached local controller. A 30-second heartbeat prints UTC, active
system, actual workflow stage, workflow elapsed time and confirmed outcome counts.
It does not invent model progress. API and local validation durations come from
existing monotonic execution receipts, not the workflow clock or assumed labor.
Atomic status.json and STATUS.md remain readable during execution. A durable
reservation precedes each POST; an uncertain POST is never automatically repeated.
worker.lock records the process ID and prevents a second controller from spending
the same authorization. UI interruption does not stop the detached process.

After the successful remote preflight, download its plan into CAMPAIGN/preflight/plan.json,
set preflight_run_id in status.json through Progress.update, and inspect the frozen
plan before starting the worker with --approved-calls 4. Use Python -u and redirect
stdout/stderr to CAMPAIGN/live.log and errors.log. On Windows start the process with
Start-Process -WindowStyle Hidden and an explicit working directory. Monitor its PID
and status file every 30-60 seconds. Never erase a reservation or lock to rerun a
request. If a controller dies, inspect its recorded workflow ID and recover that
artifact before considering another action; no recovery step authorizes another call.

The worker downloads each system before dispatching the next. It verifies receipt
identity, one SDK invocation, and artifact hashes. Existing financial pricing is used
offline; missing failed-call usage remains unknown, not free. Original engine files
retain their names; generation_metadata.json is a derived, unreviewed summary.

`scripts/evaluate_multi_system.py CAMPAIGN` revalidates CSV fields, ratings and RPN,
compares the historical A pilot with B-E, writes descriptive summaries and seven
300-dpi figures, and generates candidate component/unit review findings from original
input inventories. Exact text duplicates and schema failures are objective findings;
lexical matches, possible omissions and engineering concerns require human judgment.
No reference/ground-truth FMEA is read. Rows and provisional ratings do not establish
coverage, safety or independent engineering acceptance.

Invoke the existing financial CLI with A's manifest and each B-E execution sidecar
to create a new immutable preliminary financial report. Never overwrite A's baseline.
Manual/review labor, acceptance and unresolved billing remain missing. Do not compute
a repeatability interval from one B-E observation or pool unlike systems as replicas.

Only source/tests/documentation and separately reviewed aggregate financial artifacts
belong in Git. Campaign raw CSVs, responses, status/logs and the review ZIP stay under
ignored results/. Stop after this pilot: the proposed 16 additional generations need
a new explicit user authorization. All new Python calculation/control-flow blocks
are annotated, following docs/SYSEN5300_CODING_STANDARDS.md.
