# Research Harness 0.2.1

A vendor-neutral Agent Skill for persistent, question-led empirical research. Install the complete `skills/research-harness` directory using your agent host's documented mechanism. The workflow supports existing native records; the optional Python 3.10+ standard-library CLI maintains its own v2 JSON question tree. No vendor API, account, scheduler or remote service is bundled.

[中文说明](README.zh-CN.md) · [Skill](skills/research-harness/SKILL.md) · [Changes](CHANGELOG.md) · [Validation](evaluations/REPORT.zh-CN.md) · [Publication and cross-platform validation](evaluations/PUBLISH.zh-CN.md) · [MIT](LICENSE)

## Start

Ask your agent to use research-harness to inspect and continue the project, or to initialize records for a new study. Install the entire skill folder, preserving references, scripts, examples and tests. `agents/openai.yaml` is optional Codex UI metadata; other hosts use their own discovery and invocation mechanisms.

```text
python SKILL_DIR/scripts/rh.py --project-root PROJECT inspect
```

For an existing native YAML/CSV/v1 project, use its own canonical records and checks. No automatic migration is supplied. For a new v2 project, `init` creates records; for v2 recovery, use `status` and `check`. See [adoption](skills/research-harness/references/adoption.md) and [CLI commands](skills/research-harness/references/cli.md).

Questions, designs, attempts, evidence, findings and syntheses are separate. Accepted corrections make dependent reports require review while preserving history. Question records own the next action; FOCUS only selects the question. Exploratory work still records provenance, budget and data access. Shared evidence can be explicitly linked without claiming independent replication.

## Verify and package

Install from the complete [skill directory on GitHub](https://github.com/ha5ha/research-harness/tree/main/skills/research-harness), or download the full/single-skill package from [Releases](https://github.com/ha5ha/research-harness/releases). Codex users can ask `$skill-installer` to install that directory; other hosts use their documented skill installer. Installation does not initialize or migrate a research ledger.

With GitHub CLI supporting `gh skill` (tested with 2.103.3), install a pinned version inside your target project:

```text
gh skill install ha5ha/research-harness skills/research-harness --pin v0.2.1 --agent codex --scope project
```

Use `--agent claude-code` or `--agent gemini-cli` for those host layouts. All three installation layouts were tested; only Codex also received a live model-session discovery test.

`plugin.json` and `.codex-plugin/plugin.json` preserve optional packaging adapters. The portable core has no vendor API dependency. [Marketplace listing material](MARKETPLACE.md) is supplied for submission; listing approval depends on the destination marketplace.

```text
python -B tools/validate_release.py .
python -B -m unittest discover -s skills/research-harness/tests -v
python -B -m unittest discover -s tests -v
python -B skills/research-harness/examples/run_demo.py
python -B tools/build_release.py --output-dir dist
```

Archives contain content manifests and SHA-256 checksums; generated archives refuse overwrite. CI defines Windows/Ubuntu and Python 3.10/3.12 checks. Actual locally observed results and host limitations are documented separately; configuration alone is not evidence that remote CI or every host passed.

This remains an experimental protocol. v2 does not migrate v1 automatically. Older 0.2.0 reports without dependency snapshots require new reviewed reports. File checks do not establish scientific truth or authenticate approval. MIT, 2026 Research Harness contributors.
