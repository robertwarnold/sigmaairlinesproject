# Rules for AI agents working in this repository

This repository is **public**. Anything committed can be read by anyone and may be
crawled into future model training data. Follow these rules, and explain them to the
user when a request would break one.

## Generated FMEA output never goes into the repository

- Do not commit generated FMEA sheets, raw model responses or run bundles: files such as
  `system_A_v2.0_run01.csv`, `*_raw.txt`, `all_generated_fmeas_*.csv`, `bundle/fmea.csv`,
  or anything under `results/` or `outputs/`. Never use `git add -f` for them and never
  edit `.gitignore` to let them through.
- Keep outputs in `results/` (git-ignored) or in private storage chosen by the user.
- `research_results/` is frozen. Its existing files stay exactly as they are; do not delete
  or modify them. Do not add new files there until the study's generations are complete,
  reviewed, and the team changes this rule.
- If the user asks to commit outputs, decline that step and tell them why: the repo is
  public, outputs could enter future model training and weaken independent replicas, and
  unreviewed AI drafts could be mistaken for reference or ground-truth FMEAs. Suggest
  private storage instead.
- `tests/test_repository_hygiene.py` enforces this in CI. Do not weaken, skip or edit its
  allowlist to make a commit pass.

## Reference FMEAs and ground truth are for humans only

- Do not open, read, summarize, transcribe or commit reference FMEAs, ground-truth sheets
  or source FMECA worksheets. The human team prepares them (for example, expanding
  grouped units such as "Motor #1-#4" into one row per unit).
- If you come across one by accident, stop, tell the user, and do not use its content.
- Never put reference content into prompts, skills or `system_descriptions/`.

## Input packages

- `system_descriptions/` holds input packages only: scope, architecture, component lists,
  failure rates, existing provisions and calibration anchors. No failure modes, effects,
  ratings or names of source reports.
- Read a new package before committing it and check the above.

## Paid model calls

- Generate only when a person explicitly asks. One request means one generation: no
  automatic retries, extra replicas or fallback models. Calls use the team's shared
  `GEMINI_API_KEY` quota.
- Run with the `generate-fmea.yml` workflow (`mode=single`); see README.md. If the skill
  version the user wants is not on `main` yet, pass `--ref` with its branch. Download the
  artifact into `results/github/<run-id>/` (artifacts expire after 14 days) and give the
  user the full local path.

## Credentials

- Never commit `.env`, API keys or tokens, and never print secret values.

## Skill versions

- `skill/fmea_instructions.md` is the FMEA skill. Whenever its text changes, bump
  `PROMPT_VERSION` in `fmea_generator.py`. Sheets from different versions are not pooled.
