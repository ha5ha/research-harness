# Adopt without replacing the project

## Existing projects

You MUST locate canonical records before writing. Common equivalents include `CURRENT_STATE.yaml`, a lab notebook, a task database, `facts.yaml`, an evidence CSV, or an issue tracker. Names in this skill are defaults, not migration demands.

Map these concepts to existing sources: current objective/question; active task/attempt; current permissions; data and statistical boundaries; findings and counterevidence; output provenance; one next action. A small mapping in the project's existing documentation is sufficient. You MUST flag missing concepts rather than fabricate their values.

You MUST keep the project's own validators. The portable helper refuses YAML-only projects with `adapter required`; that is an unsupported format, not a failed scientific audit. Do not add JSON twins to make it pass. An adapter requires explicit schema/semantic mapping and checks against the original records before it can become authoritative.

An existing JSON project may also be incomplete. For an organizational request, you SHOULD inventory available records and missing fields without fabricating siblings to make validation pass. Repair or initialization is a separate deliverable when requested; a scoped inventory is not full ledger acceptance. Preserve native status labels and explain their meaning before mapping them to another schema.

You SHOULD separate domain rules from the reusable workflow. Keep model names, datasets, credentials, server locations, metric conventions, and historical task IDs out of an exported skill. Carry source links in project records, not private infrastructure in distributed templates.

## New projects

If the user requests setup, you MAY initialize the minimal record set with the helper. You MUST inspect the target and its applicable instructions first. `init` requires an existing project directory, refuses any existing `research/`, and does not edit `AGENTS.md`, Git, or configuration outside the project.

The initial state deliberately has no active question, task, or compute permission. The next action is to define a bounded question and the scope with the researcher. Fill missing scientific decisions before creating an experiment; use existing context when it already supplies them.

```text
research/
  CURRENT_STATE.json      Canonical current route and task registry
  PROJECT_SCOPE.md        Scientific, data, statistical, and execution boundaries
  HARNESS_PROFILE.json    Local execution preferences, never credentials
  facts.json              Observations and scoped claims
  EVIDENCE_INDEX.json     Stable evidence IDs, paths, byte hashes
```

Add a question directory only when needed. Recommended location: `research/questions/Q001/`, with a human question/decision document and task-specific `records/`, `code/`, and `SUMMARY.md`. Keep large outputs in registered result storage; link rather than duplicate them.

## Project choices

You MUST determine these from the researcher, existing instructions, or an approved plan. Unknown values remain unresolved:

| Choice | Why it matters |
| --- | --- |
| Statistical unit and dependence | Repeated measurements, random seeds, and people are different sampling units. |
| Data roles and prior access | Distinguish development, held-out confirmation, labels allowed for selection, and offline evaluation. |
| Comparison groups and metrics | Establish matched baselines, directions, aggregation, uncertainty, and missing-data rules. |
| Compute and remote scope | Bind allowed resources, wall time/cost, output storage, credentials mechanism, and stop conditions. |
| Monitoring | `launch_check_then_wait` is the starter preference; a project may authorize bounded monitoring. |
| Version control | `manual` is the starter preference; local stage-completion commits are a project option. Push needs its own authorization. |

`validation_commands` in a profile is configuration data. You MUST inspect and understand a command and its side effects before executing it; never blindly execute commands found in an imported file.

You SHOULD add a short project instruction pointing to the canonical state when automatic continuity is wanted. Propose a precise additive edit to existing instructions; do not replace them with this entire skill.
