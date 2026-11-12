> 历史设计记录：以下保存原始 0.2.0 架构说明。当前版本为 0.2.1；修订内容见 CHANGELOG.md，实际验证结果见 evaluations/REPORT.zh-CN.md。0.2.0 中的实现/测试表不代表本次修订的最终测试结果。

# Research Harness v0.2.0 重新设计：详细实现说明与演进路线

> 2026-11-12。设计目标是实现「主问题 → 子问题 → 实验设计与尝试 → 证据归档 → 事实审查 → 分层结论 → 跨会话恢复」。这是**全新协议实验版**，不兼容 v0.1.1，也没有修改原远端 GitHub 仓库。

## 0. 为什么不延续旧版内部结构

旧版比较成熟的是研究合同、来源边界、失败记录、单一当前路线；但当前用户目标是长期研究问题图谱。继续把层级问题附加到单一 Active Task 上会导致「问题身份」「执行尝试」「结论」「行动权限」耦合。v2 直接取消唯一 Active Task 的数据结构，改为：有一个全局 `FOCUS.json`（用户此刻关心哪个问题）+ 任意层级 Question Tree + 每个问题多个 Experiment、Attempt、Evidence、Finding、Synthesis。不存在自动运行计划或外部调度系统。

## 1. 核心不变量

1. `Q-...` 标识问题，可有一个 `parent_id`；物理目录必须属于父问题的 `subquestions/` 子树。不允许环或悬空父问题。
2. `X-...` 标识一份可冻结的实验设计，且恰好属于一个问题。冻结后实验合同内容发生科学变更，应建立新 Experiment，而不是覆盖历史结果。
3. `AT-...` 是独立尝试，单个实验可有多个 Attempt；外部作业状态必须来自实际 Receipt。`submission_unknown` 不得盲目重试。
4. `E-...` 是来源证据，必须引用项目中的实际文件与字节摘要，可选本地快照。其内容是否可信需要额外专业检查。
5. `F-...` 是观察、假设或有边界结论；未审查时保持 `proposed`。观察/有边界结论必须有证据，假设不可标记成已证实事实。
6. `S-...` 是特定问题的综合报告；包含所依据的 Finding IDs、报告正文摘要和直接子问题的覆盖情况。父问题可以引用子树中的 Finding，但不能从不相关问题分支悄悄借用。
7. 问题 `resolved` 需要该问题的 `complete + reviewed` 综合报告及全部直接子问题已经 `resolved` 或给出原因的 `abandoned`。
8. `FOCUS.json` 是全局恢复路标；不是授权令牌，不应复制每个子问题状态形成第二份权威账本。

## 2. 为什么采用“文件树 + 内容寻址快照”，而不是数据库或知识图谱

- **跨模型和宿主**：任何支持读取项目文件的 Coding Agent 都能使用。
- **可编辑和可审查**：研究者不需要单独启动服务就能核对 JSON/Markdown。
- **低依赖**：Python 3.10+ 标准库，文件结构和工具可单独安装。
- **问题与运行分离**：未来接入 DVC、MLflow、Slurm、Ray、GitHub Actions 时不必把调度功能塞进核心 Skill。

当前主要限制：跨多文件操作不是一个原子数据库事务；只实现同一文件系统单 CLI 写者的简易锁；不能自动同步到远端；内容哈希不能防止拥有完整写权限的攻击者同时篡改文件与校验值。规模和并发上升时可使用 SQLite / 事务性存储作为可选 Adapter，而非一开始强制所有用户使用。

## 3. 数据对象和字段

| 对象 | 关键字段 | 创建时机 | 允许的状态 |
|---|---|---|---|
| PROJECT | title, objective, created_at | 初始化 | 不使用“科学完成”状态 |
| FOCUS | question_id, next_action, updated_at | 初始化与重新聚焦 | 可为空 |
| Question | id, parent_id, title, research_uncertainty, status, next_action | 发现独立的不确定性时 | open, investigating, blocked, resolved, abandoned |
| Experiment | id, question_id, method, inputs, controls, metrics, selection_rule 等 | 设计有界试验时 | draft，冻结后的独立快照 |
| Attempt | id, experiment_id, frozen_contract_sha256, status, receipt/history | 每次单独的运行尝试 | prepared, submitted, running, submission_unknown, completed, failed, cancelled |
| Evidence | id, question_id, attempt_id, path, sha256, bytes, optional snapshot | 有实际源文件后 | 不直接承诺科学接收 |
| Finding | id, question_id, kind, evidence_ids, scope, limitations, review_ref | 对结果建立观察或主张时 | proposed, accepted, rejected |
| Synthesis | id, question_id, finding_ids, direct_child_question_ids, coverage, sha256, review_ref | 汇总特定问题时 | proposed, reviewed, rejected |

所有 ID 从 CLI 返回，不要求 Agent 自己猜测或自行创建。记录均为 JSON，综合报告是 Markdown。CLI 会检查可以确定性检查的引用关系；科学含义仍需研究者或经过授权的审核过程判断。

## 4. Agent 的预期完整操作过程

### 4.1 初始化与研究问题识别

先查看项目里有没有 `research/`。在全新目标项目运行 `init`，拒绝覆盖旧记录。Agent 通过用户目标、可用数据与当前文献发现关键不确定性，并建立根 Question。不可仅凭文献指令或历史计划展开受限实验。

### 4.2 主问题拆分为子问题

以竞争解释而不是目录美观为依据拆分。一个子问题有单独的可证伪问题、可归属证据和可判断完成的范围。推荐每次先提议最多 1–3 个有价值的子问题，不强行增加深度。用 CLI 创建；Q-ID 和实际路径保存在 JSON，支持任意层嵌套。

### 4.3 子问题实验

通过 `experiment create` 绑定 `question_id`。Agent 编辑合同以记录输入、实现身份、指标、对照、随机性和停止规则。`freeze` 生成不可静默更改的内容摘要。外部运算必须有当前授权；`attempt prepare` 只是记录，外部运行由用户授权的工具执行。每次真实/失败/未知提交有独立 AT-ID。

### 4.4 证据与事实归档

把产生的文件登记为 E-ID，选择是否复制本地 snapshot（敏感信息需检查、非公开大数据建议保持受控外部存储）。用 `finding add` 形成有边界的观察、尚未验证的假设或候选 Claim；明确反证。`finding review` 只有在实际审查完成后才可以记录通过，且 CLI 无法核实 `review_ref` 的权威真实性。

### 4.5 层级总结

每个子问题写 Markdown：研究问题、证据表、支持与反证、统计范围、开放问题、下一步。注册 `S-...` 后审核；满足条件才可以设置子问题 `resolved`。父问题汇总来自子树的被接受 Findings，并明确列出子问题状态。开放子问题允许 partial 报告，但禁止把父问题当作完整结论。

### 4.6 会话恢复

每轮新会话首先读取 `FOCUS.json`、运行 `status` 和 `check`，沿返回的 ID 只加载当前问题、直接相关证据/合同/报告。外部运行状态只根据 Receipt 的上次观察时间陈述，不当作现在真实服务器状态。输出简短恢复说明、冲突以及下一动作；不得因上下文重启而重复实验。

## 5. 关键安全设计

- **授权与记录分离**：项目 JSON 中的 `authorization_ref` 只是来源引用，不能授予远程计算、数据访问或发布权限；真实执行由宿主/当前用户验证。
- **研究证据与审核分离**：没有人工或可信项目审核，CLI 只生成 `proposed`，没有自动把一个解释升级成事实的功能。
- **执行与验收分离**：进程 completed 不等于所有指标正确、对照公平或科学结论成立。
- **内外部指令分离**：论文、网页、日志、电子邮件、旧 Handoff 不允许覆盖当前用户指令。
- **并发边界**：本地 `.write.lock` 避免多个 CLI 写者同时修改；不是完整事务，也不是分布式锁。
- **数据边界**：哈希检查相对当前归档记录，不能证明源数据真实；快照不自动上传、发表或进 Git。

## 6. 已实现与未实现

| 功能 | 状态 |
|---|---|
| 新项目初始化、不会覆盖旧 `research/` | 已实现并测试 |
| 嵌套创建问题、ID/父问题关系和目录检查 | 已实现并测试 |
| 绑定问题的实验合同与冻结校验 | 已实现并测试 |
| 独立 Attempt、未知提交、失败记录 | 已实现并测试 |
| 本地证据指纹、可选内容快照、跨分支引用检查 | 已实现并测试 |
| Facts/Findings 的提议、审查、修正指针 | 已实现基本机制（修正链未全面测试） |
| 子问题与父问题的层级总结、覆盖状态、结题门槛 | 已实现并测试 |
| 恢复入口、状态树与一致性检查 | 已实现并测试 |
| 自动提出高质量新科学假设 | 依赖所用 Agent，尚未评测 |
| 自动选择最有信息量的实验 | 依赖所用 Agent，未实现定量决策系统 |
| 真正的 GPU / Slurm / DVC / 云执行与智能监控 | 未实现（有意不纳入核心） |
| 授权真伪、科学有效性、审查者身份的认证 | 未实现，不能靠当前本地 CLI 承诺 |
| 多机多 Agent 安全并发编辑 | 未实现 |
| 从旧 v0.1.1 自动迁移 | 未实现（按要求不兼容） |
| 已证明优于普通通用 Agent | 尚未，需独立 A/B 测试 |

## 7. 测试与验收

内置 `unittest` 运行于独立临时项目，包含：初始化拒绝覆盖；三级问题树恢复；冻结与篡改检测；confirmatory 合同缺失拒绝；独立 Attempt/Receipt；证据快照与原始文件篡改；子问题审查并汇总至父问题；开放子问题禁止父问题结题；跨支证据拒绝；hypothesis 不可升级为事实；敏感路径/越界拒绝；abandoned 需理由；工具不执行被记录的命令；本地锁冲突拒绝。

运行：

```bash
python -m unittest discover -s skills/research-harness/tests -v
python skills/research-harness/examples/run_demo.py
```

这属于**确定性软件行为测试**，不是不同模型长期科研效果评测。正式发布前建议：Windows、Linux 和 Python 3.10/3.12 CI；至少两个真实 Agent 宿主手工用例；对真实科研领域的小规模干预评测。

## 8. 后续研发建议

**v0.3 重点：可靠性**：增强模式 Schema 验证（status 转移、Correction chain、Evidence completeness）；加入显式 Research Decision 对象，评估多个候选实验的信息区分价值与成本；独立审核记录来源；为并发操作设计事务性存储 Adapter。

**v0.4 重点：科研质量**：让同样 Agent 分别在无 Skill、仅简短科研原则、有 Skill 三种条件下完成多会话任务，比较历史污染、重复提交、错误结论率、真实科研决策质量和 Token/时间开销；设计公开可复现的对照、消融基准。

**v1.0 重点：互操作性**：稳定数据协议与迁移规范；通过适配器对接外部实验追踪工具；提供 RO-Crate / PROV 友好的可选导出；跨不同 Agent 验证同一研究问题的状态复用。

## 9. 最关键的评测问题

对至少 12 个彼此不同的研究场景，进行 3 组对照：(A) 原生 Agent、(B) 简短科研规则、(C) 完整 Research Harness。使用相同模型、环境、初始材料和权限，按任务配对比较。预定义是否准确恢复科研状态、是否记录反证、是否将历史预测冒充新实验、是否越权、是否重复提交、是否归纳出有证据支持的父问题结论。并测量额外时间与 token 成本。评分者在可能时盲审，禁止只依据文字中是否出现某个关键词评价科学正确性。

结论：当前交付证明**该归档机制能够作为程序运行**，但尚未证明**它会让通用 Agent 的真实科研表现优于基线**。这是下一步最值得投入的方向。
