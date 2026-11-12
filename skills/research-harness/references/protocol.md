# Protocol, experiments and state semantics

## Scope

This protocol is an opinionated local state representation, **not** a comprehensive scientific workflow engine. The Python CLI is a deterministic registry and integrity checker. It does not run experiments, choose statistical tests, authenticate human decisions, provide a remote transaction store or guarantee scientific reproducibility.

## Question / experiment relationship

An experiment belongs to exactly one question (`question_id`). A question can own multiple experiments and child questions. An experiment is a *scientific design*; an attempt is a *distinct execution*. Reusing outputs or changing data/metric/implementation is never silently called independent replication. Use a new experiment for science-changing contract alterations, and a fresh attempt for a repeat under the same frozen contract.

## Contract and freeze

`experiment create` creates a draft `contract.json`. Edit the fields with real inputs and scientific decisions; empty placeholders do not count as readiness. `experiment freeze` requires `research_question`, `method`, `inputs`, `outputs`, `stopping_rule`, `metrics`, `statistical_unit`, `randomness`, `data_access`, `budget`, `implementation_ref`, and `environment_ref` in every mode. For `confirmatory` work it additionally requires hypotheses, falsifiers, controls, selection and missingness rules, and decision rules. Exploratory flexibility does not remove provenance, data-access or budget requirements.

Frozen experiments have both a byte-hashed draft and a stored immutable snapshot. The checker detects editing either snapshot relative to its manifest, but **cannot detect an attacker rewriting all trusted records**. A freeze proves only what local bytes were recorded; it does not prove the design is fair, statistical assumptions sound or any execution authorized.

`attempt prepare` requires a declared `authorization_ref` as a *pointer* to actual current approval. Do not construct a fake approval. Before running commands, separately check the host's current permissions and user's scope. The CLI never invokes them.

Old frozen designs remain readable and hash-checkable. New preparations also require the current minimum contract fields; an incomplete historical freeze requires a complete new design, never editing its archived bytes to pass the new gate.

## Attempt lifecycle

`prepared` → `submitted` → `running` → `completed`/`failed`/`cancelled`; `submission_unknown` is available when a response was lost. Require receipts/observations for reported `submitted`, `running` or `completed`. A completed process is *not* automatically accepted scientific evidence. A failed/cancelled attempt retains its logs; retries use a fresh ID. A new preparation for the same experiment is blocked while a submission is unknown. Reconcile the original observation before recording another preparation. `prepared` cannot jump directly to `completed`; record an actual submitted/running observation first, never fabricate an intermediate receipt.

## Exploratory vs confirmatory

Exploratory work is allowed to be flexible, but record any access to labels, parameter tuning, data changes, missing conditions and post-hoc decisions. Do not relabel exploratory evidence as independent confirmation. Confirmatory contracts commit to comparisons, eligibility, metrics and decisions before execution. Neither mode loosens permission or data security.

## Validation boundaries

`check` validates linked records, hashes, paths, status labels, parent relationships, and whether reviewed syntheses refer to reviewed findings. It **does not** validate scientific validity, current authorization, correct math, independence, or causal interpretation. Inspect the actual evidence with the right domain tools. Structural success must never be reported as a scientific proof.
