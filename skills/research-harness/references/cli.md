# Commands and worked workflow

Run from any location. All commands use Python 3.10+ standard library and output machine-readable JSON. The `--project-root` flag appears **before** the command.

```bash
RH="/path/to/research-harness/skills/research-harness/scripts/rh.py"
PROJECT="/path/to/your/research-repo"
python "$RH" --project-root "$PROJECT" inspect
python "$RH" --project-root "$PROJECT" init --title "Robustness study" --objective "Investigate robust algorithm behavior"
python "$RH" --project-root "$PROJECT" question add --title "Why does method A fail on some data?"
# Read the returned root Q-... ID, do not invent one.
python "$RH" --project-root "$PROJECT" question add --parent Q-ROOT_ID --title "Does seed sensitivity explain the regression?"
python "$RH" --project-root "$PROJECT" focus --question Q-CHILD_ID --next-action "Design a matched seed study"
python "$RH" --project-root "$PROJECT" experiment create --question Q-CHILD_ID --title "Seed sensitivity" --mode exploratory
# Fill contract.json: question, method, inputs, outputs, stop rule, metrics, statistical unit,
# randomness, data access, budget, implementation_ref and environment_ref. See protocol.md.
# Confirmatory mode additionally needs preregistered hypotheses, controls and decision rules.
python "$RH" --project-root "$PROJECT" experiment freeze --experiment X-EXPERIMENT_ID
# This records a prepared attempt; it does NOT execute the command.
python "$RH" --project-root "$PROJECT" attempt prepare --experiment X-EXPERIMENT_ID --command "python run.py --config config.yaml" --authorization-ref "current user approval reference"
# After executing independently with actual host/user authorization, record the observed receipt.
python "$RH" --project-root "$PROJECT" attempt update --attempt AT-ATTEMPT_ID --status running --receipt-ref "actual-start-observation"
python "$RH" --project-root "$PROJECT" attempt update --attempt AT-ATTEMPT_ID --status completed --receipt-ref "job-log-or-receipt-path"
python "$RH" --project-root "$PROJECT" evidence add --question Q-CHILD_ID --attempt AT-ATTEMPT_ID --file results/seed_metrics.csv --role output --snapshot
python "$RH" --project-root "$PROJECT" finding add --question Q-CHILD_ID --kind observation --statement "Seed 2 showed a reversal under protocol P" --scope "two seeds, development data" --evidence E-EVIDENCE_ID
python "$RH" --project-root "$PROJECT" finding review --finding F-FINDING_ID --status accepted --review-ref "approved research review source"
# Write a report locally including exact findings, counterevidence and unknowns.
python "$RH" --project-root "$PROJECT" synthesis add --question Q-CHILD_ID --file reports/seed_study.md --findings F-FINDING_ID
python "$RH" --project-root "$PROJECT" synthesis review --synthesis S-SYNTHESIS_ID --status reviewed --review-ref "approved review source"
python "$RH" --project-root "$PROJECT" question update --question Q-CHILD_ID --status resolved
# Add a parent-level finding supported by descendant evidence, and a parent synthesis.
python "$RH" --project-root "$PROJECT" status
python "$RH" --project-root "$PROJECT" check
```

All example IDs are placeholders. Use the actual IDs returned by the program. For an open child, a parent synthesis review requires `--allow-partial`, nonempty `--limitations` on `synthesis add`, and remains `coverage: partial`; the parent cannot be set to `resolved`.

`inspect` is safe on existing native projects and never initializes or migrates them. `focus --question ID` selects an existing question without changing its next action; optional `--next-action` writes the question record. `status` derives the displayed next action from that record.

For deliberate shared evidence, `evidence link --question TARGET --evidence SOURCE --reason "Shared baseline; same observations"` preserves origin and explicitly marks reuse as non-independent. It does not weaken direct cross-branch citation checks.

Other operations:

```text
question update --question Q-ID [--status open|investigating|blocked|resolved|abandoned] [--next-action TEXT] [--reason TEXT]
question add --parent Q-ID --title TEXT [--mode exploratory|confirmatory] [--why TEXT]
experiment create --question Q-ID --title TEXT [--mode exploratory|confirmatory]
experiment freeze --experiment X-ID
attempt update --attempt AT-ID --status STATUS [--receipt-ref REF] [--note TEXT]
evidence add --question Q-ID --file PATH [--attempt AT-ID] [--role ROLE] [--snapshot]
evidence link --question Q-ID --evidence E-ID --reason TEXT
focus --question Q-ID [--next-action TEXT]
inspect
finding add --question Q-ID --kind hypothesis|observation|scoped_claim --statement TEXT [--scope TEXT] [--evidence E-ID ...] [--counterevidence E-ID ...] [--supersedes F-ID]
finding review --finding F-ID --status accepted|rejected --review-ref REF
synthesis add --question Q-ID --file PATH --findings F-ID ... [--limitations TEXT]
synthesis review --synthesis S-ID --status reviewed|rejected --review-ref REF [--allow-partial]
show --id Q-ID|X-ID|AT-ID|E-ID|F-ID|S-ID
status [--question Q-ID] [--limit 20]
check
```

`check` performs deterministic structural/integrity validation only. It does not establish permission authenticity or scientific truth.

`status`/`show` return derived finding/report currentness and effective question status. Historical `accepted`, `reviewed` and `resolved` labels alone are not enough. A `needs_review` question remains open for scientific purposes until its current evidence and affected summaries are reviewed.
