# Generator and judge skill candidates

## Generator candidate

V4.0 already binds generation to a separately prepared inventory, keeps repeated unit identities, requires applicability decisions for every unit/category, separates materially distinct mechanisms, and checks coverage and duplicate content independently. The archived V2.0 to V3.0 comparison shows lower missed rates alongside substantially more unmatched generated rows. The aggregate evidence supports investigating both outcomes. It cannot attribute the change to particular prompt instructions.

Use the following as a separately versioned candidate extension to the V4 skill after its response schema and validator support the new fields.

1. Reconcile the supplied inventory with system boundaries, component functions, repeated units, interfaces and shared dependencies. Record considered inventory IDs and unexplained omissions. Flag incomplete or contradictory inputs for human review.
2. Separate failure modes when mechanisms or consequences materially differ. Combine wording variants and causally interchangeable descriptions with the same consequence and controls. Keep independently identifiable repeated units traceable.
3. For each rating, record a concise engineering justification. For severity record the local effect, propagation to the system limit, applicable protective functions, redundancy and dependencies, and the resulting severity rubric band. Flag uncertain input facts and avoid giving credit to assumed provisions.
4. In the first validation pass, reconcile inventory IDs, interfaces and applicability decisions against generated row links. In the second pass, flag overlapping rows, unsupported assumptions, inconsistent ratings and avoidable splits. A completed second pass does not certify engineering approval.
5. Return structured diagnostics containing considered IDs, coverage gaps, duplicate row ID pairs, assumptions with affected row IDs, rating findings and concise justifications. Attach the candidate prompt version, input hash, response hash and model configuration to the run receipt in software.

Keep the active V4.0 prompt and output contract available for controlled comparisons. Evaluate the candidate against the same independent judge treatment and system strata. Include non-aircraft cases with redundant equipment, shared interfaces and different consequence scales before making cross-domain claims.

## Judge V1.3 candidate

V1.2 already has exceptions for shared failure descriptions and grouped repeated units. It reports unmatched generated rows separately and leaves validity outside the matching step.

- Represent proposed matches as explicit stable-ID links. Record exact unit coverage and the mechanism evidence for each shared link. Count unique opportunities and unique generated rows separately.
- Record ambiguous candidates with competing links and a concise explanation. Defer the final designation in ambiguous cases to a human adjudication event.
- Record suspected duplicate relationships separately from misses and unmatched rows. Let a human classify unmatched rows as valid additional coverage, duplicate, unsupported, or unresolved.
- Preserve explicit mismatch reasons and record exact and within-tolerance judgments for each valid S/O/D pair. Keep blank reference fields out of agreement denominators.
- Retain model, configuration, rubric, dataset version, trial ID and human adjudication history. Compute repeatability on common items evaluated by comparable trials. Report Fleiss’ kappa only when the rating design supports it. Independent accuracy requires a separately adjudicated comparator.

Treat V1.3 as a new judging condition. Preserve V1.2 for ongoing controlled comparisons and re-evaluate both the baseline and candidate under V1.3 before attributing a difference to the generator.
