# Design, authorize, and record experiments

## Freeze the decision being tested

You MUST connect each task to one bounded uncertainty. A hypothesis needs an observable consequence and a possible outcome that would count against it. A control needs a stated identifying role: which competing explanations would produce different results? A control that produces almost no intervention cannot establish that the changed feature is irrelevant.

You MUST distinguish an exploratory analysis chosen after seeing results from a frozen confirmation. Register data access and prior selection honestly. A renamed development set does not become independent confirmation.

Use the [contract template](../assets/templates/experiment-contract.json) only where useful. Before execution, replace unresolved values and freeze:

- Question, task ID, revision, implementation identity and source basis.
- Code commit plus content hashes of all executed code/configuration, including dirty code and delegated dependencies; runtime/library environment.
- Data/model/input-contract identities, sample keys/counts, statistical unit, overlap/dependence, label access and selection restrictions.
- Conditions, matched baselines, controls, sample/state/batch protocol, randomization and repeat hierarchy.
- Primary/secondary metrics, practical thresholds or tolerances, uncertainty method, aggregation and missingness rules.
- Budget, concurrency, runtime limits, output location, acceptance checks and stopping rule.
- Falsifying outcomes, controls' identification limits, and prewritten interpretation boundaries.

You MUST hash the frozen contract bytes. Current permission MUST reference that revision/hash and an actual user authorization source. `status: granted` is a record of permission, not a way to create it. Contract changes invalidate the binding until existing permission is checked against the new scope; scientifically changed conditions require a new revision/attempt.

The portable helper checks an authorization record's fields and digest equality. It cannot authenticate the human source or decide whether a budget is appropriate. You MUST perform that contextual check.

## Separate task and attempt lifecycles

Recommended task states: `draft → approved → frozen → running → analyzing → completed`. Use `blocked` for an external dependency and `superseded` for an unexecuted replacement. Record the prior state and reason for a detour; do not erase the earlier contract.

Attempt execution has its own status: prepared, submitted, running, failed, completed, or awaiting_local_sync. Acceptance separately tracks local coverage, numerical checks, scientific review, and archival integrity. A failed attempt does not erase an approved task; a correction receives a new attempt ID. Retain partial output with its coverage and reason for exclusion.

## Submit once and verify health

You MUST record the attempt ID, frozen digest, exact command/configuration, code/environment identity, approved target, intended output path, and submission receipt. If the launch result is uncertain, inspect that receipt and the existing job before retrying; do not duplicate a possibly running submission.

You MUST confirm payload integrity, supervisor/process identity, and that the worker entered normal work. A process merely existing is insufficient. A completed-at-first-check run is completed execution, not accepted evidence.

You MUST follow the current project's monitoring policy. For launch-check-then-wait, stop active polling after a healthy startup and report the attempt/location. Wait for the required completion notice before synchronizing or analyzing. For bounded monitoring, obey the approved interval, duration, failure triggers, and notification conditions. The skill itself installs no automation.

Remote access MUST use the project's approved credential mechanism and workspace boundary. NEVER put secrets, protected raw data, or model checkpoints into Git, logs, or distribution packages. A credential's existence does not grant permission for a different host or purpose.

## Parallelize bounded work, serialize shared decisions

You MAY delegate independent implementation, review, or offline analysis within the approved task. Assign disjoint write paths and the same contract digest. Keep one writer for shared state, task activation, fact promotion, and budget allocation. Report computational repeats, cached reuse, and independent reproduction as distinct activities.
