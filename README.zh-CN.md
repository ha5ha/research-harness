# Research Harness

让通用 coding agent 能持续承接长期科研的可复用工作流。

Coding agent 擅长完成具体任务；持续数周或数月的实证研究还需要保存问题、决策、失败尝试、代码变化、证据范围及下一步。Research Harness 把这套流程封装为 Agent Skill，使新的会话能够找到可信的研究状态并继续已授权工作。

研究者负责科学目标和决策，skill 按 [Agent Skills 标准](https://agentskills.io/home) 提供可移植的执行流程及可选本地完整性工具。它不绑定模型、数据集或学科，也不提供调度器、远端服务或科学有效性保证。

[English](README.md) · [Skill 入口](skills/research-harness/SKILL.md) · [MIT 许可证](LICENSE)

## 安装到支持 Agent Skills 的宿主

下载或克隆 [ha5ha/research-harness](https://github.com/ha5ha/research-harness)，按所用 agent 宿主的 skill 安装机制，安装 **整个** `skills/research-harness` 文件夹，保留其中的 references、assets、scripts 和 tests。安装不会自动初始化或修改科研项目。[Agent Skills 标准](https://agentskills.io/home) 规定共享格式；目录位置、自动发现、调用和权限遵从各自宿主的文档。

通用核心由 `SKILL.md`、`references/`、`assets/` 以及 `scripts/` 中的可选本地工具组成，独立于 Codex，不依赖 Codex API 或运行环境。`agents/openai.yaml` 是可选的 Codex 界面元数据，仓库的 `.codex-plugin/plugin.json` 是可选的 Codex 打包适配。其他宿主通过自己的 skill 机制使用相同核心；尚未逐个平台进行实机会话兼容验证。

安装后，先用自然语言提出请求，例如“使用 research-harness 继续这个科研项目”。具体的 skill 调用行为遵从宿主文档。

### Codex 安装示例

将完整 skill 文件夹复制到以下任一位置：

- 项目内 `.agents/skills/research-harness`；
- 当前用户的 `~/.agents/skills/research-harness`。

在目标项目新开 Codex 会话，用自然语言要求使用 research-harness，或使用 Codex 的显式调用语法 `$research-harness`。安装和发现方式见 [Codex skill 文档](https://learn.chatgpt.com/docs/build-skills)。

也可以向 Codex 的 skill-installer 提出：

```text
使用 $skill-installer 安装以下 GitHub 目录里的 research-harness：
https://github.com/ha5ha/research-harness/tree/main/skills/research-harness
```

源码已在 GitHub 公开。本包不表示已向任何市场提交或获得上架。

包内另提供 `plugin.json` 和 `.codex-plugin/plugin.json`，供支持相应可选打包格式的宿主使用；两者引用同一套 skill，阅读和使用通用核心无需这些适配。Codex 适配格式见 [Codex 插件打包文档](https://developers.openai.com/plugins/build/plugins)。无 MCP 服务、账号配置或远端依赖。

## 直接使用

可以用自己的语言、课题和项目结构，通过所用宿主的 skill 机制提出请求：

```text
使用 research-harness 为这个项目初始化科研工作流。
研究问题是新算法能否改善独立评估集上的鲁棒性。
先检查已有文件，不覆盖现有研究记录。

使用 research-harness 继续当前已批准但未完成的科研任务，
先恢复问题、已接受证据、未决点和唯一下一动作。

使用 research-harness 整理这些已有结果和决策；本次不授权实验。

使用 research-harness 分析这次失败实验，保留原尝试和部分输出，
区分技术故障与假设的支持或反证，并提出能区分解释的下一步。
```

`$research-harness` 是 Codex 的显式调用示例；其他宿主采用各自文档规定的调用方式。

已有项目优先沿用规范记录；可选初始化工具遇到已存在的 `research/` 目录会拒绝创建，避免形成第二套状态来源。已有 YAML/CSV 账本使用原校验工具，或先建立明确适配。

工作流程为：问题 → 竞争解释 → 冻结合同 → 独立尝试 → 输出验收 → 范围结论 → 下一动作。合同固定输入、方法身份、标签使用、选参规则、对照、随机性、预算与验收标准。失败记录保留，重试使用新身份；进程结束、文件完整、科学结论成立是不同状态。

## 可选 Python 工具

核心 skill 工作流不需要 Python。仅工具和测试需要 **Python 3.10+**，只使用标准库，无需 `pip install`。把 `SKILL_DIR` 换成已安装 skill 的目录，`PROJECT` 换成已有目标项目目录：

```text
python SKILL_DIR/scripts/research_harness.py init --project-root PROJECT
python SKILL_DIR/scripts/research_harness.py validate --project-root PROJECT
python SKILL_DIR/scripts/research_harness.py manifest --project-root PROJECT --output research/release.json --files src/worker.py research/contract.json
python SKILL_DIR/scripts/research_harness.py verify --project-root PROJECT --manifest research/release.json
```

`init` 创建最小草稿记录，不修改 `AGENTS.md`；`manifest` 仅接收逐文件白名单，不覆盖已有输出；`verify` 检查文件缺失与字节变化；`validate` 检查通用 JSON 账本的结构及来源约束。详见 [记录结构与工具边界](skills/research-harness/references/records.md)。

校验通过不代表授权真实性、科学有效性、公平比较或多会话锁成立。工具不启动实验、不查询服务器、不修改权限、不晋级事实、不发布内容。项目自己的监听、审核和提交规则仍然适用。

## 验证安装包

在本仓库根目录运行：

```text
python tools/validate_release.py .
python -B -m unittest discover -s skills/research-harness/tests -p "test_*.py"
python -B -m unittest discover -s tests -p "test_*.py"
```

第一项静态检查包路径、引用、模板、清单、版本一致性及产物边界。测试在临时项目中验证实际本地行为。CI 已配置 Windows、Ubuntu 及 Python 3.10、3.12 检查，包本身不宣称已执行远端 CI；这个矩阵不等于每个 agent 宿主或科学领域均已实机验证。

发布包包含逐文件 manifest 和 SHA-256 校验和。单 skill 包含完整可安装的 `research-harness/` 文件夹；完整仓库包另含说明、插件清单、校验工具和 CI。

验证下载的完整仓库归档时，保留根目录的 `MANIFEST.json` 和 `SHA256SUMS.txt`，它们对应该版本的精确发布字节。建立可编辑的 GitHub 源码仓库时，这两个归档生成文件不应提交；包内 `.gitignore` 已显式忽略它们，普通 Git 暂存会遵守该规则。源码校验允许这两个文件不存在，后续修改 README 不需要重建归档。`.gitattributes` 在 Windows 与 Unix 上均保留 LF 换行。CI 仍是已配置状态，本包不宣称已在远端运行。

## 许可证

MIT，版权 2026 Research Harness contributors。见 [LICENSE](LICENSE)。安装前可审阅全部指令，并根据项目确定科学合同。
