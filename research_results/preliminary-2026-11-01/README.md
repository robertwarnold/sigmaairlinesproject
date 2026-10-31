# Sigma Airlines preliminary evidence checkpoint

Status: one verified real smoke is committed; seven additional calls are running on GitHub.

- Continuation run: https://github.com/robertwarnold/sigmaairlinesproject/actions/runs/41245374928
- Original successful smoke: https://github.com/robertwarnold/sigmaairlinesproject/actions/runs/41244305291
- Continuation source commit: 4052aa40548c5fa17c2388d5e474e4eda216f857
- Approved design: hydraulic, battery/DC, NASA 2019 tilt-wing, NASA 2021 eQuad power; baseline/improved; one sheet per cell. Eight total including the adopted smoke; at most seven new attempts.

The seven calls run independently on GitHub. **Do not dispatch again to check progress.** Download `fmea-pilot-41245374928` from the continuation run when available. Pending sheets are not yet committed or claimed as successful.

## Available real evidence

Read smoke/README.md first. The smoke generated 9 candidate failure modes, 100% core-field content completeness, zero schema-validation errors and 18 unresolved row-level review flags. It took approximately 99 seconds. Completeness is not correctness; no reviewed mode-reference dataset exists, so missed-mode percentage is unavailable. All target ratings remain null and engineering review is required.

The smoke directory preserves the complete downloaded artifact, input/prompt, raw response, token/model metadata, per-sheet CSV/JSON, plots/report, reproduction source and all 43 verified checksums. No key values or full source PDFs are included.

## Plan amendment and interpretation

See ../../docs/four-dataset-pilot.md. The original smoke plan is preserved, not silently edited. The continuation adopts that baseline sheet after checking input/prompt/settings and generation code. Two source-grounded NASA architecture summaries replace additional repeats in this exploratory allocation. This is not the full original 4x25x5 study and does not establish statistical significance or engineering validity. All owners remain Unassigned.

## Resume collection if the chat stops

1. Inspect the continuation run above without dispatching another workflow.
2. Download its artifact; verify checksums and each FMEA bundle.
3. Preserve failures/uncertain attempts; do not automatically retry or invent missing results.
4. Commit the final artifact and descriptive report alongside this checkpoint after credential-pattern checks. The user authorized publication to main.

No further calls beyond the seven approved attempts are authorized by this checkpoint.
