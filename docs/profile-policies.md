# Preliminary profile policies 0.3

All policies below are team decisions supported by public conceptual guidance. They
are not implementations of licensed IEC/AIAG–VDA/SAE scoring tables or compliance rules.
Public background: https://asq.org/quality-resources/fmea and
https://standards.nasa.gov/node/12367 (accessed 2026-10-31).

| Profile | Scope evidence checked | Review emphasis |
|---|---|---|
| General | Hierarchy level | Explicit boundary, functions, effects and unknown controls |
| DFMEA | Hierarchy, requirement references, interface references | Design function/requirement failure and interface propagation |
| PFMEA | Operating phase, requirement references, assumptions | Ordered process steps, intended outputs and process error controls |
| Aerospace | Hierarchy, phase, interface references, assumptions | Functional/interface failures, mission effects, recovery and mitigation |

The `scope` CLI prints distinct workflow steps, questions and missing evidence. Missing
context produces profile-specific row flags that shared validation requires. These
checks detect missing values only; nonempty references/assumptions still require review.
Mock hypotheses vary by selected analysis intent; none is validated failure coverage.

Versioned behavior: new generation/conversion selects profile 0.3. Schema and mapping
remain 0.2 because canonical fields and mapping operations are unchanged. Legacy profile
0.2 is retained for exact artifact verification, without applying newer scope policy
retroactively. Unrated policy applies to both versions. Unknown profile versions fail.

Source registry entries distinguish bibliography from accessed guidance. IEC/AIAG–VDA/
SAE normative rule access remains unverified. NASA supplements Aerospace rather than
controlling the other profiles. Detailed licensed rules, action-priority methods and
scoring remain future reviewed work. Owners remain Unassigned.
