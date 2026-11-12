# Research Harness 0.2.1

让通用 coding agent 能够围绕问题、实验和证据持续承接科研。核心工作流不依赖 Codex；`agents/openai.yaml` 只是可选界面元数据。所有宿主采用各自安装和权限机制；本包没有模型 API、账号、MCP、远端服务或调度器依赖。

[English](README.md) · [Skill 入口](skills/research-harness/SKILL.md) · [本次改进](CHANGELOG.md) · [实际测试](evaluations/REPORT.zh-CN.md) · [MIT](LICENSE)

## 安装与使用

按宿主文档安装完整 `skills/research-harness` 文件夹，保留 references、scripts、examples 和 tests。对支持 `.agents/skills` 的宿主，一个可能的位置是目标项目的 `.agents/skills/research-harness`，实际位置和调用方式以宿主为准。

GitHub 安装源：[research-harness skill 目录](https://github.com/ha5ha/research-harness/tree/main/skills/research-harness)。完整包与单 skill 包在 [Releases](https://github.com/ha5ha/research-harness/releases) 提供。可让支持该格式的 agent 按此链接安装完整目录；安装不会创建或迁移科研账本。

Codex 的安装示例：让 `$skill-installer` 从上述 GitHub 目录安装 `research-harness`，下一轮即可调用。仓库另附 `plugin.json` 和 `.codex-plugin/plugin.json` 作为可选打包适配，均不改变通用核心。[市场介绍材料](MARKETPLACE.md) 可用于提交列表；实际审核取决于目标市场。

安装后可直接说：

```text
使用 research-harness 继续这个科研项目。
先识别现有记录格式，恢复当前问题、证据边界和下一动作。
本次只授权分析已有结果，不授权新实验。
```

核心规则不需要 Python；可选本地工具需要 Python 3.10+，仅使用标准库。先识别协议：

```text
python SKILL_DIR/scripts/rh.py --project-root PROJECT inspect
```

已有 YAML/CSV/Markdown/v1 项目沿用原始权威账本及其校验；不为使用 CLI 创建第二套状态。全新项目可在已有项目目录运行 `init --title TITLE`；v2 项目用 `status` 和 `check` 恢复。工具拒绝覆盖已有 `research/`。命令及完整示例见 [cli.md](skills/research-harness/references/cli.md)。

## 本次变化

- 修复 Windows 证据快照失败，并校验已存在对象的字节。
- 已接受更正使旧主张退出当前依据，关联报告与父问题提示待重审；历史原字节保留。
- 问题记录统一维护下一动作，FOCUS 仅保存关注的问题。
- 增加只读协议识别，恢复已有项目接入、配对分析、异常解释、实现身份及 Git/会话保护。
- 探索性合同也要求预算、数据使用和复现身份；未知提交未核清时拒绝同实验新准备。
- 允许显式关联共同证据并保存来源，明确复用不产生独立样本或新运行。

v2 与 v1 不自动互转。0.2.0 的普通问题/证据记录仍使用 schema 2；缺少依赖快照的旧综合报告保留为历史，需重新生成并实际审查，不回填新哈希伪装旧审查。

## 验证与分发

```text
python -B tools/validate_release.py .
python -B -m unittest discover -s skills/research-harness/tests -v
python -B -m unittest discover -s tests -v
python -B skills/research-harness/examples/run_demo.py
python -B tools/build_release.py --output-dir dist
```

完整包与单 skill 包均带逐文件 manifest 和校验和，拒绝覆盖已有归档。CI 已配置 Windows/Ubuntu × Python 3.10/3.12；实际运行范围、agent 场景和限制见 [测试报告](evaluations/REPORT.zh-CN.md)，不将 CI 配置当作已运行证据。

本地锁不提供多机事务，哈希不证明科学有效性，审查引用不认证身份。CLI 不执行实验、不授权计算、不发布内容。该版本仍属实验协议；其他宿主实机发现和真实长期科研效果需另行验证。MIT 允许免费使用及商用，见 LICENSE。
