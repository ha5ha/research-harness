# Portable records and helper scope

The helper uses Python 3.10+ and the standard library. It reads/writes local files only. All command paths except `--project-root` are relative to that root. It rejects absolute paths, parent traversal, root-escaping links, duplicate JSON keys and existing output targets. It is not a transactional database or authorization authority.

## Canonical state

`init` creates exactly five files: `CURRENT_STATE.json`, `PROJECT_SCOPE.md`, `HARNESS_PROFILE.json`, `facts.json`, and `EVIDENCE_INDEX.json` under a new `research/` directory. Initialization records no active task or permission.

The state schema is:

```json
{
  "schema_version": 1,
  "research_objective": null,
  "active_question_id": null,
  "active_task_id": null,
  "next_action": {
    "id": "DEFINE_RESEARCH_QUESTION",
    "description": "Define a bounded research question and project scope with the owner.",
    "starts_experiment": false
  },
  "task_registry": []
}
```

A registered task has `id`, `question_id`, `status`, `contract_path`, and `contract_sha256`. A draft may have null contract fields; other statuses require an existing byte-matched contract. `active_task_id` identifies one nonterminal task belonging to `active_question_id`. Other tasks may be drafts, historical or future candidates; they cannot be running/analyzing outside the active route. The optional `active: true` marker must agree with the route; prefer the single canonical field.

Task statuses: `draft`, `approved`, `frozen`, `running`, `analyzing`, `completed`, `blocked`, `superseded`. Optional `run_status` values: `not_started`, `running`, `failed`, `completed`, `awaiting_local_sync`. This field is a compact execution summary; detailed attempts use their own records.

An experiment next action (`starts_experiment: true`) additionally requires an active `frozen` task with:

```json
{
  "authorization": {
    "status": "granted",
    "contract_sha256": "the exact 64-character frozen contract digest",
    "source": "reference to the researcher's actual approval and its scope"
  }
}
```

The example above describes fields; its explanatory strings are not valid digests or permission. NEVER manufacture an approval source. Freeze exact bytes and check current user instructions. Changed contract bytes fail even if the old authorization remains present.

A completed task also requires existing `summary_path` and `audit_path`, nonempty `evidence_ids` in the evidence index, and no unclosed run state. You MUST inspect the audit content yourself; existence alone does not establish acceptance.

## Evidence and findings

`EVIDENCE_INDEX.json` has `schema_version: 1` and an `evidence` list. Each entry contains a unique `id`, project-relative `path`, and `sha256`; `bytes` is optional. Every indexed file is hash-checked by `validate`. Remote/unavailable artifacts cannot pass this local archival check; retain their unresolved state until they are available through the project's approved mechanism.

`facts.json` has `schema_version: 1` and a `facts` list. Each entry needs a unique `id`, nonempty `statement`, and nonempty existing `evidence_ids`. Use `status` for scientific status (`observation`, `unresolved`, `verified_under_scope`, `corrected`) and `promotion_role` for intended use (`context_only` or `claim_support`). Findings intended to support a claim require:

- `status: verified_under_scope`.
- Resolved `scope`, `statistical_unit`, `code_ref`, `config_ref`, `source_task_id`.
- A registered completed source task.
- Supporting and, when applicable, opposing evidence references.

The [finding template](../assets/templates/finding.json) contains the richer scientific fields required by the workflow, including systems/models, cohorts, baselines, attempts, limitations and verification. The helper's field checks cover only a subset; it does not verify these scientific meanings, source-code execution, implementation faithfulness, or the truth of a claim. An empty initialized ledger passes structure while all scientific decisions remain unresolved.

Optional `counterevidence_ids` reference evidence IDs. A non-null `supersedes_id` references a different existing finding; preserve that earlier finding. You MUST also inspect the correction chain for semantic and temporal consistency. The helper does not decide which competing claim should prevail.

## Profile

`HARNESS_PROFILE.json` contains schema version, `monitoring_policy`, `commit_policy`, `code_roots`, `result_roots`, and `validation_commands`. Strings/list types are checked; the profile supplies preferences, not executable permissions. Default policies are launch-check-then-wait and manual commits. No profile value is automatically executed.

## Integrity commands

`manifest --files ... --output ...` writes a new JSON file containing `schema_version: 1` and sorted `files` entries (`path`, `sha256`, `bytes`). It uses only the explicit file list, never a recursive directory sweep. `verify --manifest ...` detects byte/size changes, missing files, duplicate paths and traversal. Keep the original manifest's identity in a separate trusted record; changing both content and its manifest is outside an unanchored checksum's guarantees.

The helper rejects common credential/checkpoint/raw-medical file names and extensions as a heuristic. It does not inspect arbitrary content or prove a package contains no secrets. Review the explicit allowlist and content before export.

All commands return JSON; success exits 0, detected problems exit nonzero. `validate` and `verify` report `scientific_acceptance: not_assessed`. `validate` also reports `authorization_authenticity: not_assessed`.

## Unsupported existing formats

If `CURRENT_STATE.yaml`/`.yml` exists, `validate` returns `adapter required`, including when a JSON twin is present. Use native checks rather than overriding that guard. No command silently converts, repairs, runs experiments, changes task states, commits, or cleans evidence.
