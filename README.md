# Research Harness

A reusable research workflow for general-purpose coding agents.

Coding agents can implement individual tasks well. Empirical research also needs continuity: questions change, experiments fail, code evolves, and evidence accumulates over weeks or months. Research Harness helps an agent preserve the question, decisions, experiment contracts, failed attempts, evidence boundaries, and next authorized action between sessions.

This is a portable [Agent Skill](https://agentskills.io/home), with optional local integrity helpers. The researcher owns the scientific objective and decisions. The skill supplies a workflow; it does not supply a model, dataset, scheduler, remote service, or scientific guarantee.

[中文说明](README.zh-CN.md) · [Skill instructions](skills/research-harness/SKILL.md) · [MIT license](LICENSE)

## Install for an Agent Skills host

Download or clone [ha5ha/research-harness](https://github.com/ha5ha/research-harness) and install the **entire** `skills/research-harness` directory using your agent host's documented skill mechanism. Preserve its references, templates, scripts, and tests. Installation itself does not initialize or change a research project. See the [Agent Skills standard](https://agentskills.io/home) for the shared format; skill locations, discovery, invocation, and permissions depend on the host.

The portable core is `SKILL.md` together with `references/`, `assets/`, and the optional local helpers in `scripts/`. These files are independent of Codex and use no Codex API or runtime. `agents/openai.yaml` supplies optional Codex UI metadata, and the repository's `.codex-plugin/plugin.json` supplies an optional Codex packaging adapter. Other hosts can use the same core through their own skill mechanism. Live compatibility with other hosts has not been verified.

After installation, start with a natural-language request such as "Use research-harness to continue this research project." Follow your host's documented skill invocation behavior.

### Codex example

Copy the complete skill directory into either:

- `.agents/skills/research-harness` in the project where you will use it; or
- `~/.agents/skills/research-harness` for your user account.

Start a new Codex session in the target project. You can ask it to use research-harness in natural language, or invoke it explicitly with the Codex syntax `$research-harness`. See the [Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) for its installation and discovery behavior.

You can also ask Codex's skill installer:

```text
Use $skill-installer to install the research-harness skill from
https://github.com/ha5ha/research-harness/tree/main/skills/research-harness
```

The source is available on GitHub. No marketplace submission or listing is claimed by this package.

The repository also includes `plugin.json` and `.codex-plugin/plugin.json` for hosts that support those optional package formats. Both refer to the same bundled skill; they are not needed to read or apply the portable core. See the [Codex plugin packaging documentation](https://developers.openai.com/plugins/build/plugins) for the Codex adapter. There are no MCP servers or remote dependencies.

## Use it

Use your own language and research topic. Ask your agent to use research-harness through its skill mechanism. Example requests:

```text
Use research-harness to initialize a research workflow in this project.
Our question is whether the new algorithm improves robustness on held-out data.
Inspect the existing files first; do not overwrite established records.

Use research-harness to continue the current approved research task.
Recover the question, accepted evidence, unresolved issue, and next action.

Use research-harness to organize these existing results and decisions.
This request does not authorize running experiments.

Use research-harness to analyze this failed experiment.
Preserve the attempt and partial outputs, distinguish a technical failure
from evidence about the hypothesis, and propose a discriminating next step.
```

An explicit invocation such as `$research-harness` is a Codex example. Use the invocation form documented by your own host.

The skill starts with existing canonical project records. Its optional initializer refuses an existing `research/` directory rather than inventing a second source of truth. Existing YAML/CSV research systems use their own validators or an explicit adapter.

The research loop is question → competing explanations → frozen contract → distinct attempt → accepted outputs → scoped finding → next action. A contract records the inputs, method identity, label access, selection rules, comparisons, randomness, budget, and acceptance criteria. A failed attempt remains evidence of what happened; it is not silently replaced by a successful retry.

## Optional Python helpers

The core skill workflow does not require Python. Python **3.10 or newer** is needed only for helpers and tests. They use the standard library; there is no `pip install` step. Replace `SKILL_DIR` and `PROJECT` below with the installed skill directory and an existing target project directory.

```text
python SKILL_DIR/scripts/research_harness.py init --project-root PROJECT
python SKILL_DIR/scripts/research_harness.py validate --project-root PROJECT
python SKILL_DIR/scripts/research_harness.py manifest --project-root PROJECT --output research/release.json --files src/worker.py research/contract.json
python SKILL_DIR/scripts/research_harness.py verify --project-root PROJECT --manifest research/release.json
```

`init` creates minimal draft records without modifying `AGENTS.md`. `manifest` accepts an explicit list of project-relative files and refuses to overwrite an existing output. `verify` detects missing or changed bytes. `validate` checks the portable JSON ledger's structural and provenance constraints. See [record schemas and helper scope](skills/research-harness/references/records.md).

These checks do not authenticate authorization, establish scientific validity, prove fair comparison, or provide cross-session locking. Helpers do not launch experiments, query servers, change permissions, promote findings, or publish anything. Follow project-specific monitoring, review, and commit rules.

## Validate this package

From the repository root:

```text
python tools/validate_release.py .
python -B -m unittest discover -s skills/research-harness/tests -p "test_*.py"
python -B -m unittest discover -s tests -p "test_*.py"
```

The first command statically checks package paths, references, templates, manifests, version consistency, and artifact hygiene. The tests exercise observable local behavior in temporary projects. CI is configured to run these checks on Windows and Ubuntu with Python 3.10 and 3.12; remote CI execution is not claimed by the package. This matrix tests the local package, not every agent host or scientific discipline.

Release archives include a file manifest and SHA-256 checksums. The single-skill archive contains the complete installable `research-harness/` folder; the repository archive also includes documentation, plugin manifests, validation, and CI.

Keep the repository archive's root `MANIFEST.json` and `SHA256SUMS.txt` when verifying the downloaded archive: they describe the exact released bytes. When creating an editable GitHub source repository, leave these two generated archive files untracked. The included `.gitignore` excludes them, so normal Git staging respects this separation; source validation accepts their absence, and later README edits do not require an archive rebuild. `.gitattributes` preserves LF line endings on Windows and Unix. CI is configured but has not been run remotely by this package.

## License

MIT, copyright 2026 Research Harness contributors. See [LICENSE](LICENSE). Review the skill before installation and adapt its scientific contracts to your project.
