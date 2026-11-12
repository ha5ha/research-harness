# Existing projects and new records

You MUST inspect the existing project before selecting a record format. Read project instructions and the user's scope. The skill's scientific workflow does not require replacing a project's native records.

| Existing records | Use |
| --- | --- |
| Native YAML/CSV/Markdown or tracker | Map current question, active work, evidence, decisions and next action to existing locations; use native validators. |
| Research Harness v1 | Keep v1 authoritative; use its helper and native checks. No automatic conversion is supplied. |
| Research Harness v2 JSON | Run `status` and `check`; inspect currentness and warnings before dependent work. |
| No records | For an authorized setup request, `init` creates minimal v2 records in an existing project directory. |
| Isolated supplied artifacts | Deliver scoped analysis; record missing context and a proposed next step in the analysis itself. |

`inspect` is read-only protocol discovery. `existing_native_or_unsupported` does not mean corrupted science. NEVER run `init`, erase records, or create shadow JSON to work around unsupported formats. If native validation cannot be run, report that limitation and continue independent analysis.

For v2 created by 0.2.0, question/evidence records keep schema 2. New status views derive finding currentness and one next action without rewriting historical records. An old report lacking `finding_state_snapshot` requires a newly registered and reviewed synthesis; its previous review remains historical. A duplicate legacy FOCUS action that conflicts with its question is an explicit conflict. Read both sources, select the justified action, then use `focus --question ID [--next-action TEXT]` to normalize it.

Migration between native/v1 and v2 remains a separate, agreed deliverable: source mapping, preserved bytes, relationship mapping, validation and review. Installing a skill does not authorize migration.
