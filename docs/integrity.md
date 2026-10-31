# Engineering-data integrity correction pass

Scope: local offline corrections only. Python 3.12 target. All owners Unassigned.

This records the merged 0.2 integrity pass. Subsequent local profile 0.3 work is described
in profile-policies.md; the candidate fixture is described in public-conversion-candidate.md.

## Corrected boundaries

- Strict JSON parser rejects duplicate object keys at every depth, including decoded
  escape-equivalent keys, NaN/infinity, and numeric overflow. Model validation rejects
  non-string dictionary keys, tuples, sets, bytes, nonfinite numbers, and cycles.
- CSV validates its header and every row before constructing dictionaries. Header
  normalization is Unicode NFKC, trim, case fold, and space-to-underscore; collisions
  fail instead of overwriting data. Header spellings are preserved under `_csv_headers`.
- Source/derived claims require evidence referencing each populated target field.
  Mock item/function claims cite context; generated failure modes remain hypotheses.
  A populated engineering field cannot simultaneously carry an unknown marker.
- Controls preserve prevention, detection, and consequence mitigation independently.
  Every structured control has its own status and evidence. Legacy shared statuses
  are not trusted. Existing lists must exactly match implemented structured controls.
- Source records are canonical serialized snapshots, with independent parsed mirrors
  and SHA-256 hashes. Original caller mutation cannot change the snapshot, output row,
  or report. Verification reparses snapshots, checks hashes/mirrors, and regenerates
  mappings. Source risk data and declared units remain separate from target ratings.

## Artifact and review identity

The engineering content version is SHA-256 of canonical context, profile/schema,
metadata, rows, controls, evidence, unknowns, and flags. Review status/decision are
excluded from that content hash to allow a decision to reference the reviewed version
without a circular digest. Any engineering-content or unresolved-flag edit invalidates
the recorded decision. The bundle file hashes additionally bind review metadata.

Review timestamps require valid ISO 8601 calendar date, time, and timezone. A decision
must record reviewer, timestamp, rationale, exact artifact version, all unresolved flags,
and `authenticated: false`. Accepted/rejected is an unauthenticated local review record,
not risk acceptance or release authority. Providers cannot set these decisions. The
envelope always declares `approval_status: unauthenticated_draft`.

## Publication and recovery

Exports accept new directories only and use an exclusive sibling lock, sibling staging,
file flush/fsync, complete bundle verification, then one directory rename. Existing
bundles are never overwritten. Converted drafts require their matching report; mock
drafts cannot attach a conversion report. The manifest enumerates exact files, artifact
identity/version, mapping version, and SHA-256 file checksums. Directory validation
rejects extra/stale files, mismatched CSV, source/report edits, and missing artifacts.

Handled write/publish errors and KeyboardInterrupt remove staging and release the lock
without publishing a partial bundle. An uncatchable process kill or machine failure can
leave a hidden `.NAME.staging-*` directory or `.NAME.lock`; these are not published
bundles. Inspect them manually before removing abandoned state; select a new output
directory to continue. No automatic recovery/deletion of prior analyses is implemented.
Atomic publication assumes local same-filesystem directory-rename semantics. Full
power-loss durability of directory entries/network-filesystem semantics is not claimed.
Hashes provide integrity checking, not digital signatures or authenticated authorship.

## Deferred engineering validation

Four profiles remain preliminary, unverified, unrated team policies. They still share
core behavior; this pass does not add proprietary rules or differentiated workflows.
Licensed rule verification, real page-checked FMECA fixtures, semantic duplicate/mixed-
hierarchy analysis, source/target phase reconciliation, and authenticated review remain
pending. Evidence locators are structurally checked, not checked for truth automatically.
The synthetic fixture exercises software integrity and is not engineering ground truth.

The installed CLI regression builds/uses a local wheel, installs it offline into a
temporary virtual environment, removes source-path/provider-key variables, and runs
generation, conversion, bundle verification, and duplicate-key failure handling outside
the checkout. CI prepares build tooling, then runs the same offline build/test flow.
