# Resume without losing the research process

## Build a small working context

You MUST keep durable project records separate from chat. Load current scope/state, active question/task, direct support and counterevidence, current permission and unresolved decisions first. Retrieve history by IDs or paths; do not repeatedly inject all logs, CSVs, old plans, or prior summaries.

Use [handoff.json](../assets/templates/handoff.json) for a session checkpoint when continuity would otherwise be lost. Record the branch/HEAD and source-state digest/time, the request and user corrections, completed work and artifacts, pending actions, active attempt/receipt, unresolved questions, authority source, and one next action. Link original sources. A checkpoint does not promote findings, extend permission, or turn a last-observed status into a current server observation.

You MUST re-read canonical records on resumption and reconcile the checkpoint. A checkpoint is an aid, not another authoritative current-state file. If information conflicts, retain the discrepancy and inspect the original decision or receipt before dependent work. Repeated summarization MUST NOT replace the source trail.

## Avoid overwriting another session

Before editing shared state, you MUST re-read it and compare with the version/digest you used. If it changed, reconcile before writing. Assign one coordinator to state, claims and task activation; give parallel workers disjoint output paths and a frozen input digest.

This workflow is an operational convention. The bundled helpers do not implement locks, atomic multi-file transactions, or compare-and-swap updates. Concurrent autonomous writers need a real transactional store or locking adapter before safe shared mutation can be claimed. If that is unavailable, serialize writes explicitly.

Git branches, chat threads and scientific questions are different identities. Record each when applicable; never assume a branch name is permanent or that a new conversation means a new experiment. Do not reset, switch branches, merge, push, or clean other work merely to make recovery easier.

## Report only the state actually observed

A status response SHOULD state the research question, last verified finding, active attempt and last observation time, remaining uncertainty, and next action. Keep confirmed facts separate from an inferred or stale execution state. A status request does not authorize polling beyond the project policy or submitting new work.

At handoff, state what was actually completed, how it was checked, what is unresolved, and what the next agent may do. If permission is the remaining boundary, leave a concrete contract or reviewable artifact and identify the missing decision precisely.
