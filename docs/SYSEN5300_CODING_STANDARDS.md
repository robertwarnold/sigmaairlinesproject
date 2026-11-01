# SYSEN 5300 coding and annotation standards verification

Verification date: November 1, 2026.

Status: **implementation authorized after user clarification**. The user clarified
that all code must be annotated with comments explaining what it does, and directed
implementation to continue. This is the operative annotation requirement. The public
sources below remain contextual evidence; no unavailable professor rubric is invented.

## Authority and scope

Course requirements, teaching-example conventions, and Sigma Airlines requirements
are different sources of authority. A convention demonstrated in an example is not
automatically a graded requirement. Activity-specific instructions are not assumed
to govern the semester project. No line-comment percentage, annotation score,
mandatory Python type-hint policy, or professor-specific lint rule was verified.

## Authoritative public sources inspected

All links below were accessed November 1, 2026.

1. [SYSEN 5300 syllabus](https://timothyfraser.com/sigma/syllabus.html),
   Policies / AI policy and Academic integrity. Coding assistance is allowed,
   although discouraged. Submitted prose, including project text, must be the
   student's own writing. Collaborative tools must be disclosed and independently
   interpreted. Do not describe AI-authored material as student-authored or insert
   a signed honor pledge on a student's behalf.
2. [Assignments](https://timothyfraser.com/sigma/assignments.html),
   Homework and Rubric. Python is an accepted course language, including Python
   equivalents of named R functions. The public self-check is not the graded rubric;
   the page places each graded assignment rubric in Canvas.
3. [Projects](https://timothyfraser.com/sigma/projects.html),
   Your dataset; Final report R3-R5 and Reminders. Explain variables and units,
   assumptions, methods, limitations and results; cite and interpret figures and
   tables. Include complete commented code in the report appendix. The page has
   project-level assessment criteria but no detailed Python annotation rubric was
   found. Its rough-draft financial subsection length differs from this work order;
   confirm the applicable Canvas assignment before preparing a graded submission.
4. [Coding in Python](https://timothyfraser.com/sigma/chapters/coding-in-python.html).
   Introduces Python comments, variables, calculations and execution. This is
   instructional material, not a verified project annotation scoring rubric.
5. [Code It: Probability](https://timothyfraser.com/sigma/activities/code-it-probability.html)
   and [Code It: Distributions](https://timothyfraser.com/sigma/activities/code-it-distributions.html).
   These individual activities require extensive student-written line comments and
   short interpretations and explicitly disallow AI-generated commenting for those
   exercises. Their scope is those activities; project applicability is unverified.

## Course repository and methodological examples

- [Course repository README](https://github.com/timothyfraser/sysen/blob/main/README.md)
  identifies the textbook as the source for course content and Canvas for grading
  and submission. It supports both language tracks.
- [Code README](https://github.com/timothyfraser/sysen/blob/main/code/README.md)
  describes short script headers identifying the file, author, session and related
  chapter. That is a documented course-repository convention, not a verified grading
  requirement for this project's reusable Python modules.
- [Financial example in R](https://github.com/timothyfraser/sysen/blob/main/code/ZZ_financial_analysis.R)
  and [Python counterpart](https://github.com/timothyfraser/sysen/blob/main/code/ZZ_financial_analysis.py)
  demonstrate section comments, explanatory variable/function comments, printed
  estimates, bootstrap resampling, percentile intervals and scenario comparison.
  They model temperature-related refunds. Their failure definition, resampling
  unit, fixed refund cost, illustrative transformation and 1,000 iterations cannot
  be transplanted into FMEA productivity research. The work order instead requires
  matched/clustered case resampling where supported and at least 10,000 iterations.

These examples were inspected as source text, not executed. No course datasets,
engineering reference FMEAs or ground-truth worksheets were opened.

## Project-specific implementation checklist

The following requirements originate in the Sigma Airlines work order and addendum,
unless explicitly linked to course evidence above. Pending boxes are not claims
that implementation or compliance has already been completed.

- [x] Inspect repository instructions and identify the applicable baseline.
- [x] Inspect the professor's financial examples in both languages.
- [x] Distinguish explicit course requirements from example style and project policy.
- [x] Resolve the implementation gate: user supplied the annotation requirement and
  explicitly authorized continuation. Annotate calculation and control-flow blocks.
- [x] Confirm how the course prose policy applies to the requested report deliverable.
  Do not present generated Discussion prose as a submission-ready student draft.
- [x] Use descriptive section headers and purposeful comments.
- [x] Document reusable functions with purpose, inputs, assumptions and outputs.
- [x] Define financial/statistical variables, units and configurable constants.
- [x] Explain statistical calculations and method limitations in plain English.
- [x] Print interpretable numerical results, including units and evidence status.
- [x] Label every figure with title, axes, units, sample size, source/assumption
  status and an interpretation/caption.
- [x] Reuse course functions only when the method and experimental unit fit.
- [x] Keep the implementation readable without sacrificing modular tests or accuracy.
- [x] Separate measured, estimated and assumed costs and missing values from zero.
- [x] Use paired or clustered resampling when the observed design supports it;
  report insufficient data instead of inventing an empirical confidence interval.
- [x] Record random seed, iteration count, inputs, assumptions and source versions.
- [x] Preserve original pilot evidence and FMEA engineering behavior.
- [x] Review complete commented code for a possible report appendix, consistent
  with the course project requirements and the clarified annotation rubric.
- [x] Run offline tests, compilation, hygiene and whitespace checks after implementation.
- [x] Record checklist review findings and unresolved items in the implementation PR.

## Implementation review record

The financial modules use explanatory calculation/control-flow comments and public
function docstrings. Variables and units are defined in the financial README and
header-only templates. Statistical limitations and evidence status accompany printed
results, plots, and report text. Automated tests inspect module/function documentation,
arithmetic, missingness, resampling, timing, and immutable report publication. A
human must still review annotations for understanding; a syntax test cannot establish
that a student understands or authored the commentary. The course prose policy
remains applicable: generated working text is explicitly labeled and must not be
passed off as student-written submission text.

## Repository and evidence inspection

The initial working tree was clean. The proposed dependency baseline is
`ac025e157a8b5ddedb2d2b9dcb10aa21b5387162`, the head of open
[PR #8](https://github.com/robertwarnold/sigmaairlinesproject/pull/8).
That PR already adds standalone execution metadata and the fixed System A wrapper;
future instrumentation must extend it rather than duplicate it. Main remains
separate and is not changed by creating the financial-analysis branch.

The original pilot manifest is available locally at
`results/single-system-replicates/system_A/20261101T163923Z-system-a-five/manifest.json`.
It records five attempts, three successful generations and two provider failures;
successful row counts are 40, 40 and 37. Usage metadata is missing for failed
attempts. There are no measured manual labor, review/correction labor, acceptance
decisions or invoice costs in that manifest. Generation success is not engineering
acceptance. No missing observations will be replaced with fabricated measurements.

Implementation proceeds under the clarified requirement. No paid API calls were
made during verification. Archived research, system descriptions, skill text and
original pilot outputs must remain unchanged.
