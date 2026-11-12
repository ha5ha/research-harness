# Marketplace listing material

Source repository: [ha5ha/research-harness](https://github.com/ha5ha/research-harness). This is ready-to-use listing text, not a statement that a marketplace submission has been made or approved. Choose the destination marketplace when submitting.

## English

**Name:** Research Harness

**Short description:** Keep long-running research questions, experiment contracts, and evidence aligned across coding-agent sessions.

**Description:** Research Harness is a portable [Agent Skill](https://agentskills.io/home) for general-purpose coding agents working on empirical research. It helps recover the current question and authorized next action, design falsifiable experiments, freeze input and evaluation contracts, preserve failed attempts, audit outputs, and report findings within their evidence boundaries. Existing project records remain authoritative. The researcher retains control of objectives, budgets, computation, and publication.

**Use cases:** Initialize research records; resume an approved task; organize existing results without starting experiments; investigate failures and anomalies; prepare a source-linked handoff.

**Install and invoke:** Install the complete `skills/research-harness` folder using your host's Agent Skills mechanism, then ask it to use research-harness in natural language. `$research-harness` is a Codex invocation example; other hosts use their own documented syntax.

**Portable core:** `SKILL.md`, `references/`, optional `scripts/` work independently of Codex. `agents/openai.yaml` and `.codex-plugin/plugin.json` are optional Codex adapters. Other hosts use the same core through their own skill mechanism; live compatibility with those hosts has not been verified.

**Requirements:** A host that supports Agent Skills and local file access. No Python is needed to read and apply the core workflow. Optional local helpers require Python 3.10+ and use only the standard library. No model API key, MCP server, account, or remote service is bundled.

**Limits:** Integrity checks do not establish scientific validity, authenticate authorization, or guarantee a fair comparison. The package is not an experiment scheduler or a multi-session locking service. Host-specific installation and permissions apply; live compatibility with every agent or marketplace has not been verified.

**Version:** 0.2.1. **License:** MIT. **Author:** Research Harness contributors.

## 中文

**名称：** Research Harness

**短介绍：** 让通用 coding agent 在长期科研中持续对齐问题、实验合同与证据。

**介绍：** Research Harness 是按 [Agent Skills 标准](https://agentskills.io/home) 提供的面向实证研究的可移植 Agent Skill。它帮助 agent 恢复当前问题与已授权下一动作、设计可证伪实验、冻结输入及评价合同、保留失败尝试、验收输出，并在证据允许的范围内报告结论。已有项目记录保持权威；研究者决定目标、预算、计算与发布。

**适用场景：** 初始化科研记录；继续已批准任务；仅整理既有结果而不启动实验；分析故障和异常；交接带来源的研究状态。

**安装与调用：** 按宿主自己的 Agent Skills 机制安装完整的 `skills/research-harness` 文件夹，再用自然语言要求使用 research-harness。`$research-harness` 是 Codex 调用示例，其他宿主遵从各自文档。

**通用核心：** `SKILL.md`、`references/`、可选的 `scripts/` 独立于 Codex。`agents/openai.yaml` 与 `.codex-plugin/plugin.json` 是可选的 Codex 适配。其他宿主通过各自 skill 机制使用相同核心；尚未对这些宿主进行实机会话兼容验证。

**依赖：** 支持 Agent Skills 且可访问本地文件的宿主。核心工作流不需要 Python；可选工具需要 Python 3.10+，仅使用标准库。不附带模型 API 密钥、MCP 服务、账号或远端服务。

**能力边界：** 完整性校验不证明科学有效性、授权真实性或比较公平性。本包不是实验调度器，也不提供多会话锁。安装及权限服从宿主；未逐一验证所有 agent 和市场的实机兼容。

**版本：** 0.2.1。**许可证：** MIT。**作者：** Research Harness contributors。
