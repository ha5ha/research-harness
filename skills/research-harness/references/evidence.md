# Accept outputs, then reason from them

## Separate four questions

| Question | Required evidence |
| --- | --- |
| Did execution finish? | Exit/receipt and coverage; identify failed or absent conditions. |
| Is the computation correct? | Recomputed metrics, numerical tolerances, input/state checks, complete matched keys. |
| Is the implementation faithful and comparison fair? | Paper/author-code basis, actual deviations, matched data/models/protocols and selection opportunity. |
| What scientific claim follows? | Effect and uncertainty, counterexamples, alternative explanations, scope and confirmation status. |

Passing one row MUST NOT be presented as passing another. Hashes detect byte changes relative to a recorded baseline; they neither prove the original bytes were correct nor make a self-authored manifest trustworthy.

## Check the comparisons before averaging

You MUST record the actual statistical unit and distinguish samples, seeds, repeats, folds, sites, and model families. Choose uncertainty methods for the dependencies present; do not count repeated predictions as independent people or independent datasets.

You MUST group results by the conditions needed for a valid comparison: model family/source group, cohort, input and state protocol, batch, implementation/version, and resource/selection policy where relevant. Compute matched metrics at the frozen repeat/seed level, then aggregate metrics using frozen weights. Averaging predictions first measures an ensemble and requires separate labeling.

You MUST show unique sample counts, seeds/repeats, missing conditions, and the frozen aggregation/uncertainty definition. Never silently keep only shared surviving rows, reweight failures, replace missing results with zero, or rank unmatched groups. A justified exploratory subset must retain its identity and cannot replace the primary frozen comparison.

You SHOULD inspect seed/repeat directions, sample-level distributions and tails, protocol reversals, order effects, near-identity controls, and numerical degeneracy when those can change the answer. An average benefit does not establish individual safety. A directional prediction change does not by itself mean improvement or harm.

## Keep implementation identity visible

For methods from literature, record paper/author implementation, source version, project `implementation_id`, actual adaptations, identity status, and permitted result use. Label original-workflow checks, domain adaptations, historical variants, and unresolved implementations alongside method names. Keep source baselines, controls, published methods, variants, failures, and exclusions distinguishable; count algorithms rather than rows.

For example, an existing `MethodName (historical variant; author-workflow check unresolved)` row keeps its original attempt and predictions. A changed objective uses a separate `MethodName (objective variant; not run)` row with a new implementation ID and no invented metrics. The source name may remain recognizable while implementation and execution status remain explicit.

When a metric has a defined preferred direction, you MAY highlight the best value within a complete comparable group. Keep neutral quantities such as prediction movement neutral. Show practical effect sizes and uncertainty; descriptive minima alone do not prove a difference.

## Explain the result around the question

You MUST deliver machine-readable data, then phenomenon analysis, then evidence boundaries. Use [analysis.md](../assets/templates/analysis.md) when helpful. In each analytical paragraph, start with one plain-language finding, provide the necessary same-scope contrast, explain its meaning, and connect it to the remaining question.

Answer in order:

1. What happened that matters to the research question?
2. Which comparison supports that pattern, and where does it reverse or fail?
3. Which experiment distinguishes a reason from a plausible alternative?
4. What is explained, and what remains unresolved?

You MUST define unfamiliar terms on first use. Never substitute a list of metrics, technical names, or passed gates for the reasoning. User examples guide expression, not the result to find.

A key anomaly record MUST contain the observation/baseline, covered units and conditions, evidence IDs, candidate explanations, support and counterevidence for each, unresolved part, and a discriminating next experiment with falsifying outcomes. Failure to explain an anomaly is a valid unresolved result.

## Promote claims conservatively

A claim-support finding MUST carry the model/system, data/cohort, statistical unit, baseline/protocol, code/configuration identity, task/attempt, evidence hashes, verification method, limitations, and relevant counterevidence. Use [finding.json](../assets/templates/finding.json); keep unsupported explanations as hypotheses.

You MUST preserve corrections with explicit supersedes links and the old record. Reuse is a derived analysis with source IDs; it is not a new run or independent replication. Superseded evidence may explain history but cannot silently support a current claim.

Before closure, check that the main finding is understandable alone; every pattern has a matched contrast, scope and exception; reasons explain the stated phenomenon; facts, hypotheses and unresolved items remain distinguishable; tables link to the accepted source version. Run relevant project integrity and numerical checks, then update decisions and one next action. These checks cannot decide scientific truth automatically.
