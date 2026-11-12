# Evidence, facts and corrections

## Evidence archival

`evidence add --question Q-... --file project/relative/path` produces an `E-...` record containing source path, SHA-256 and byte length. `--snapshot` additionally writes a local content-addressed copy under `research/objects/`. This is a *local archival snapshot*, not backed-up or published storage; decide separately whether, where and how this directory is synced. Do not commit private datasets, credentials, medical data, checkpoints or other sensitive blobs. Use reference-only records or approved external stores where appropriate.

The CLI refuses obvious credential-like filenames but **does not inspect content for secrets**, cannot assert an artifact is safe to distribute, and never signs data. `check` detects a missing or changed source/snapshot relative to its recorded digest. A reference-only record becomes invalid if the source is moved or altered; this is expected and should trigger an explicit recovery or new registration, not a silent hash rewrite.

An evidence record belongs to a question; it may refer to an attempt. Parent questions may cite descendant evidence, while unrelated branches may not. Evidence from an incomplete attempt can document failure or partial observation, but must never be represented as a complete matched result.

## Facts and claims

Use `finding add` for: `hypothesis` (unverified explanation); `observation` (supported by evidence); `scoped_claim` (evidence-supported statement with explicit applicability boundary). Observations/scoped claims require evidence IDs. `scoped_claim` requires `scope`. Keep opposing evidence in `counterevidence_ids` and known limitations in `limitations`.

New findings have `status: proposed`; they become `accepted` or `rejected` only through `finding review` and an actual review source. An entered `review_ref` is metadata, not proof of who reviewed it. A hypothesis cannot be accepted as a fact. Review may be delegated within a documented, trusted project policy; absent such a policy, ask the researcher before elevating a consequential claim.

A correction is a new `F-...` record with `supersedes_id` pointing to the earlier finding. Do not delete the earlier evidence or hide adverse results. Reviewers should inspect the correction chain and ensure old conclusions are no longer cited as current without qualification.

## Scientific checks outside the CLI

Before interpreting outputs, verify actual sample IDs and counts, coverage, dependencies, paired comparisons, repeats versus independent units, held-out data access, baselines, metric correctness, missingness, uncertainty, implementation identity and potential explanation reversals. Include negative examples and alternative explanations. A clean file hash does not satisfy any of these scientific requirements.

## Explicit shared evidence and currentness

Use `evidence link --question TARGET --evidence SOURCE --reason TEXT` for deliberate cross-branch reuse. It creates a local reference to the same registered bytes with `derived_from_evidence_id`, `origin_evidence_id` and `reuse_not_independent`. It creates no new experiment or observations; count shared samples once when interpreting aggregate support. Direct silent cross-branch citations remain rejected. Data-use permission still applies.

An accepted correction makes its target historical for current use, while preserving the old accepted record and original evidence. `status` and `show` expose `current`, `currency`, and `superseded_by`. A proposed or rejected correction does not replace the target. Corrected findings invalidate dependent report applicability and propagate through child summaries to ancestors. Use new reviewed reports rather than editing old reports or changing a hash to silence warnings.
