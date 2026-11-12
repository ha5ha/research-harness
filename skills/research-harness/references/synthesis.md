# Child and parent synthesis

## Purpose

A synthesis explains what is learned about **one question** using reviewed findings and the recorded status of its direct subquestions. Parent synthesis is not a concatenation of child summaries. It must reconcile conflicting, negative and partial evidence and state which competing explanations are and are not distinguishable.

## Recommended Markdown sections

1. **Question and scope:** exact question, system/data/population, why it matters, known limits.
2. **Current answer:** plain-language answer with explicit confidence and qualification.
3. **Evidence table:** finding IDs, original evidence IDs, baselines, coverage and statistical unit.
4. **Child assessments:** for every direct child, status, conclusion/synthesis ID or reason unresolved/abandoned, and parent implication.
5. **Counterevidence and alternatives:** contradictory results, uncertainty, numerical/pathological cases, leakage or selection risks.
6. **What remains unknown:** avoid turning a missing experiment or abandoned child into a positive result.
7. **Next action:** one decision-relevant, authorized or proposed action and its falsifying alternatives.

## How synthesis is registered

Write the report in the project first. `synthesis add --question Q --file path --findings F1 F2` snapshots it and records direct child IDs and incompleteness. It is initially `proposed`. For `synthesis review --status reviewed`, each cited finding must have status `accepted` and the review source must be given.

If any direct child is unresolved (or has no complete reviewed synthesis), a review is only possible with `--allow-partial` **and** documented limitations. This produces `coverage: partial`; it does **not** allow resolving the parent. A question becomes `resolved` only when it has a **complete reviewed synthesis**, and all direct children are resolved or explicitly abandoned with reasons. This is a governance rule, not proof of scientific correctness.

Parent reports may cite findings and evidence in descendant subtrees; sibling/unrelated branches cannot be silently imported. A direct child that is abandoned contributes a recorded limitation/decision, not evidence of the parent's scientific answer.

## When to stop

A question can remain open indefinitely when evidence is insufficient. It is better to have an honest bounded result with a clear next discriminating test than a fabricated final answer. Review has to be based on the underlying report and data, not on CLI success alone.

## Review dependencies

Reports store a digest of each cited finding revision and a snapshot of direct child conclusions. `reviewed` describes the historical review; `current`/`currency` describes present applicability. An accepted correction, changed finding revision or changed child conclusion makes dependent reports require review. A previously resolved question then displays effective `status: needs_review`, preserving `recorded_status: resolved` and historical report bytes. `check` reports this as an explicit warning, allowing corrective work; a new `resolved` action is rejected until current complete support exists.

Old 0.2.0 reports lacking dependency snapshots require new reports and actual review. Never backfill hashes to claim the old reviewer examined new evidence.
