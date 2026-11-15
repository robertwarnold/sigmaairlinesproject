# V3 discovery and V4 gap assessment

Discovery fetched ALL remotes on November 15, 2026 from a clean tree. Main remains
`d5806f59144c14962a47f07a39d54102dd933637`. Remote V3 was not merged into main.
PR metadata for all 15 available PRs contained no V3 PR. No dashboard development
was found in the relevant branch file lists. Existing reporting is Python/matplotlib
operational reporting, separate from independent judge quality evaluation.

V4 starts at `origin/feat/fmea-skill-v3`, `e143ec4`, and combines the complementary
local `feat/fmea-skill-v3-round2`, `99647d4`, by integrating its working-tree changes (no merge commit, rebasing or reset).
Initial integration conflicts were confined to generate-fmea.yml and generator tests.
They were resolved by explicit version selection and retaining regression coverage.
A preliminary no-commit merge exposed those conflicts; `git merge --quit` then cleared
only merge state, preserving all staged work for a normal V4 commit. No branch merge
was completed. The original branches are retained. Canonical package version remains 0.3.0.

| Function | Remote V3 (a447606 / e143ec4) | Local V3 audit (99647d4) | V4 addition |
|---|---|---|---|
| Unit inventory | Internal prompt checklist | Model-emitted inventory | Independent package-hash-bound input inventory |
| Repeated units | Prompt expansion | Declared unit/case links | Deterministic count/index and response reconciliation |
| Connections | Prompt coverage | Declared connections | Binding input IDs and interface coverage audit |
| Failure directions | Prompt checklist | Thirteen-case schema | Eighteen categories; independent applicability where reviewed |
| Completeness | Model self-check | Structural audit of model inventory | Model cannot omit an independent input ID |
| Quality | Provisional ratings | Required fields and duplicate check | Unsupported IDs/categories, causal/text review flags, gap report |
| Metadata | Existing execution receipts | Skill hashes and coverage report | Git commit and independent inventory hash |
| Research | Existing operational reporting | Judge import, CSV/Excel, deferred ANOVA | Primary V2/V4, exploratory V3, bootstrap CIs, human review, safe dashboard data |
| Dashboard | None | None | Shiny, ggplot2, poster PDF, refresh/cache, offline baseline |

Remote V3's exact prompt bytes are retained in `skill/fmea_instructions_v3_remote.md`
and selected by `--version v3.0` with its historical array schema. The previous local
structured V3 prompt stays byte-for-byte in `skill/fmea_instructions_v3.md` and is
explicitly selected as `--version v3.0-audit`. These are different experimental
conditions even though both were originally called V3. No existing outputs are relabeled
or pooled: imports require prompt hash identity per version. Historical local V3 records
require human provenance resolution before any comparison. Main's original V2 default
and prompt are retained; no existing V3 prompt has been renamed into V4.

Tests previously available: standalone mocked Gemini, package CLI/research, operational
catalog/reporting, financial analysis and repository hygiene; local V3 added 11 offline
audit/import/statistical tests. V4 reuses those plus new engineering/research/R checks.

Remaining engineering gap: deterministic verification can establish ID/quantity/field
coverage, not infer the entire physical architecture or validate causal correctness.
The generic table extractor intentionally flags narrative interfaces, functions,
hierarchy, operating states and category applicability for human reconciliation.
No source FMECA or human reference worksheet was opened. The original Round 1 report
was not supplied as an accessible named report; only user-provided aggregates and
non-reference metadata were used. No per-system denominators were inferred.

## Branch inventory captured after fetch, before V4 commit

| Branch | Commit |
|---|---|
| `chore/fmea-v2-clean-integration` | `64f43af679a091fc3fc047d6e6cad7bb1ec34b19` |
| `feat/automatic-experiment-metrics-20261102` | `a8801fd999370f91903be70a13201a1a9388677e` |
| `feat/fmea-b-e-live-pilot` | `6a355c7f6291cbbad5a27ab7350f78512ba53550` |
| `feat/fmea-financial-impact-analysis` | `f1d79b6c0c69a4297a849a13f75985794c6f6089` |
| `feat/fmea-foundation` | `64d360af1dcfdd1f302cee89951ac633b5af1b90` |
| `feat/fmea-profiles-validation` | `5a1cf4d2a1f026373d7acdb643940d1d93c3240e` |
| `feat/fmea-skill-v3-round2` | `99647d4b4bd0c3a97e9c5d8902b293f92d2accc8` |
| `feat/fmea-skill-v4-research-dashboard` | `e143ec44e9af3d302fe590a324eee8c5aa1e04b5` |
| `feat/publish-fmea-figures-20261102` | `e428fc4906d6906cd1f7b06690beb27c9326b2cc` |
| `feat/system-a-five-replicates` | `ac025e157a8b5ddedb2d2b9dcb10aa21b5387162` |
| `fmea-ce-recovery-20261101` | `5db3550d92b6d2a7e480ecfe927334d6faa0a15e` |
| `main` | `d5806f59144c14962a47f07a39d54102dd933637` |
| `wip/fmea-interrupted-review` | `b4f9ac3ad9949cadb798b137efe4efeb47a4509d` |
| `origin` | `d5806f59144c14962a47f07a39d54102dd933637` |
| `origin/chore/fmea-v2-clean-integration` | `64f43af679a091fc3fc047d6e6cad7bb1ec34b19` |
| `origin/feat/automatic-experiment-metrics-20261102` | `6a745cc70183cb54786f3eff329e6a03efe4b5ce` |
| `origin/feat/fmea-b-e-live-pilot` | `6a355c7f6291cbbad5a27ab7350f78512ba53550` |
| `origin/feat/fmea-financial-impact-analysis` | `f1d79b6c0c69a4297a849a13f75985794c6f6089` |
| `origin/feat/fmea-foundation` | `64d360af1dcfdd1f302cee89951ac633b5af1b90` |
| `origin/feat/fmea-profiles-validation` | `5a1cf4d2a1f026373d7acdb643940d1d93c3240e` |
| `origin/feat/fmea-skill-v2` | `dfebac1c1b254d44fda7ca30bbc162495197260a` |
| `origin/feat/fmea-skill-v3` | `e143ec44e9af3d302fe590a324eee8c5aa1e04b5` |
| `origin/feat/publish-fmea-figures-20261102` | `e428fc4906d6906cd1f7b06690beb27c9326b2cc` |
| `origin/feat/single-run-replicates` | `57eb6c500a85ed1a3cb2939826dd8caa2df17d88` |
| `origin/feat/system-a-five-replicates` | `ac025e157a8b5ddedb2d2b9dcb10aa21b5387162` |
| `origin/fmea-ce-recovery-20261101` | `5db3550d92b6d2a7e480ecfe927334d6faa0a15e` |
| `origin/main` | `d5806f59144c14962a47f07a39d54102dd933637` |
| `origin/wip/fmea-interrupted-review` | `b4f9ac3ad9949cadb798b137efe4efeb47a4509d` |
