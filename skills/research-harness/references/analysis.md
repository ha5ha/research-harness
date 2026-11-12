# Analyze evidence around the question

You MUST first say what changed and why it matters to the bounded question. Then show decisive comparisons and exceptions, possible reasons and their evidence, what is explained, and what remains unresolved. IDs, validator output and tables support that reasoning; they do not replace it.

## Establish comparable observations

- Group results by actual model/backbone, source/checkpoint group, cohort, input/state protocol, batch size and implementation. NEVER rank incompatible groups using one pooled average.
- Match sample identities and baselines within each seed and repeat. Compute paired metrics first, aggregate repeats within source seed, then aggregate seed metrics under frozen weights. Report sample/seed/repeat counts and variability. Averaging predictions before computing metrics is an ensemble analysis and MUST be labeled separately.
- Distinguish the statistical sampling unit from multiple predictions on it. Repeated seeds, views or frames are not additional independent subjects. State the resampling unit for intervals.
- Check planned coverage. List failures, missing conditions and exclusions. NEVER silently intersect surviving rows, impute missing results as zero, or rename partial coverage as the planned full result.
- Keep development/tuning exposure separate from held-out confirmation. Labels and parameter choices follow the current contract; retrospective analysis is not an untouched test.

## Explain patterns and anomalies

Look across seeds, repeats, cases and protocol controls; a mean can hide a reversal. For each consequential anomaly, preserve observation and comparison scope, candidate explanations, support/counterevidence, unresolved points, and the next experiment that could distinguish them. A failed control or non-significant difference does not establish mechanism or equivalence.

Track method identity: paper/author implementation, actual project revision, substantive deviations, and intended result use. Assess paper-process fidelity, numerical/state correctness, and same-condition comparison fairness separately. Historical predictions support a derived analysis, not a fresh run; changed implementation identity requires a new design/attempt when execution is needed.

## Deliver a bounded answer

For each analysis point, provide an interpretable table, phenomenon explanation, then evidence boundary. Tables identify groups, samples, statistical unit, baseline and metric direction. Distinguish output acceptance, observed effects, candidate mechanism and generalization. Leave unexplained anomalies unresolved; do not invent reviews or promote a claim because files pass checks.
