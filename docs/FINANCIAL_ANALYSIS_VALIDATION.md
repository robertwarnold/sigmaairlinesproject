# Financial analysis validation and annotation review

Local verification: Python 3.12.14, existing `.venv/gemini` environment.
All **110 offline tests passed** with no skipped tests. This includes the original
suite and synthetic financial/timing regressions. Compilation of analysis, src,
scripts and fmea_generator.py and `git diff --check` passed.

## Reviewed behavior

- Wage/benefit arithmetic applies burden once and accepts a loaded-rate override.
- Gemini input plus candidate/thinking output is priced once; invoices override
  estimates; missing failed billing stays unknown.
- Passive waiting is excluded from active labor. Review/rework buckets are disjoint.
- Rejected work and failed requests stay in their exact workflow cost pool.
- Equivalent input, scope and acceptance criteria are required for matched cases.
- Negative savings remain negative; no positive break-even is invented for a loss.
- Paired bootstrap resamples connected system/reviewer clusters reproducibly with
  at least 10,000 iterations. Insufficient clusters or measured data produce no CI.
- Explicit scenario Monte Carlo is reproducible and labeled as simulation uncertainty.
- Immutable report IDs reject reuse; fixed inputs reproduce the same numerical metrics.
- Report manifests record required provenance and bind generated files by SHA-256.
- Financial report paths disable Git newline conversion so byte hashes remain valid
  after checkout on another operating system; a regression verifies published hashes.
- Standardized timing covers SDK success/disconnection and precise monotonic elapsed
  arithmetic, without live requests. Historical values are not rewritten.
- Existing repository hygiene and installed console-command tests remain enabled.

The real System A input manifest was also used for a local preview. No labor,
acceptance or invoice observations were fabricated. The final preliminary report
must be generated after the framework commit so its Git SHA identifies that code.
CI status is recorded in the implementation PR rather than asserted in advance here.

## Coding/annotation checklist review

The user's clarified convention is explanatory comments throughout new calculation
and control-flow blocks. Reusable functions have purpose docstrings. The financial
README defines input fields, units, mutually exclusive minute buckets, financial
formulas, experimental identities, resampling units, assumptions and limitations.
Printed values identify USD, active-hour units and unavailable empirical intervals.
Every PNG has title, axes/units, sample size, source/evidence label and a caption.
Tests check module/function documentation; review of comment meaning is a manual
code-review responsibility and is not inferred from comment counts.

The instructor examples informed readable stepwise calculations, not temperature
failure definitions or an inappropriate row-level bootstrap. The course prose policy
is documented; generated working Discussion text is labeled and is not represented
as student-authored submission material.

## Limits and publication review

No measured cost per engineering-accepted FMEA, labor savings or empirical financial
confidence interval can be established from the current pilot. No request was made
to Gemini or another paid provider. Frozen research, input packages and skill text
remain unchanged. Original pilot checksums were reverified unchanged.

Financial reports contain only metadata-derived aggregate costs/counts and public
assumptions, not raw FMEA worksheets, raw provider responses, reference answers or
private reviewer records. The financial output paths require no hygiene exception.
Framework changes and each preliminary report belong in separate commits and await
PR review. No automatic merge is authorized.
