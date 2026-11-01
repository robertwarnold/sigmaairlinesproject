# FMEA v2 integration decisions

The integration starts at `origin/feat/fmea-skill-v2` (`dfebac1`), three commits
ahead of the inspected main (`c03f0e7`), which is its merge base. No main-side merge
or history rewrite was needed.

## Supported entry points

`fmea_generator.py` and the unchanged v2.0 skill provide standalone Gemini drafting
with provisional S/O/D and locally calculated RPN. All five system A-E input
packages remain unchanged. `src/sigma_fmea/` remains the canonical research package:
unrated profiles, mock/OpenAI/Anthropic/Gemini providers, experiments, evaluation,
validation and deterministic FMECA conversion. The two paths intentionally have
different policies and must not be pooled into one experimental condition.

`scripts/pilot_workflow.py` and `scripts/pilot_four_datasets.py` remain the controlled
pilot orchestration, with their existing attempt limits and provenance checks.
The GitHub generation workflow remains manual; offline CI does not dispatch it.

## Intentional removals

Repository-wide searches outside frozen evidence found no callers or documentation
references to these five files. No replacement experiments were run.

| Removed file | Reason and replacement |
|---|---|
| `.DS_Store` | Finder metadata; no source functionality. Ignore it and `Thumbs.db`. |
| `SIGMA_AIRLINES_UPDATE_README.txt` | Superseded setup handoff. Current README and architecture/runbooks describe implemented workflows; AGENTS.md governs reference restrictions. |
| `gitcommit.R` | Personal credential/global Git setup and blanket staging helper. Use normal Git commands with explicit paths. |
| `hello.R` | Greeting-only script, unrelated to research. No replacement needed. |
| `run_experiment.py` | Obsolete standalone batch loop requiring absent system_3/system_4 inputs. Use explicit standalone single runs or canonical controlled experiment/pilot orchestration; these are distinct conditions, not equivalent replacement datasets. |

The historical `fmea_generator.R`, `run_experiment.R`, `README.txt` and R project
remain intact. Similar filenames alone do not establish duplication. No canonical
package code was removed. No archived research files or freeze fixtures were edited.

## Reproducibility safeguards

Standalone generation rejects mismatched prompt versions, nonpositive/noninteger
runs (including booleans), and existing CSV/raw paths before a model call. Raw files
are exclusively reserved before requesting Gemini; CSV creation is also exclusive.
An interrupted/failed call can leave an empty raw reservation requiring inspection.
Truncation, safety stops and parsing failures preserve raw output and reject CSV
publication. There are no automatic retries. Mocked offline regressions cover the
preflight checks, preservation of existing files and a CSV collision during a call.

These checks establish software behavior, not engineering validity. Archived smoke
evidence does not establish accuracy or completion of an eight-generation study.

## Integration verification

All 83 offline unit tests passed on Python 3.12.14, including the installed console
command, mocked generator regressions and repository hygiene checks. The initial
installed-CLI failure was an environment issue: installing setuptools and wheel in
the existing project virtual environment restored the build backend. No source or
test assertion was changed to work around that failure. Compilation and
`git diff --check` passed. No live provider requests or new experiments were run.
