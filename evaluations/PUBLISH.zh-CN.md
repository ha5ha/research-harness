# 0.2.1 发布补充验证

本次将本地修复版接回原 GitHub 历史，以正常快进更新发布；0.1.1 的原始实现和模板保留在原提交中，没有把 v1 工具与 v2 混装。恢复并更新了通用 `plugin.json`、可选 `.codex-plugin/plugin.json` 和中英文市场介绍。新增插件版本/路径校验及一个失败回归用例。

## 实际运行的跨平台检查

[GitHub Actions 运行](https://github.com/ha5ha/research-harness/actions/runs/43202595729) 对提交 `1f89bea1d36bbfe236edccd05df64a35b20d1f67` 的四组检查全部成功：Ubuntu/Windows × Python 3.10/3.12。每组实际运行 31 项 CLI 测试、6 项分发测试、静态校验和完整示例；日志确认符号链接测试均执行通过。这补齐上一份报告中“CI 已配置但未运行”和本机符号链接权限跳过的覆盖。摘要与对应日志行见 [github_ci.json](github_ci.json)。

这轮验证的是协议工具和分发行为，不是不同操作系统下的科学结论或长期科研收益。原 [研究行为报告](REPORT.zh-CN.md) 记录的是此前本地测试，保留当时环境与数量；本补充不把旧记录改写成后来完成。

## 从 GitHub 实际安装

第一方 skill-installer 从固定提交下载 `skills/research-harness` 到隔离项目的 `.agents/skills/research-harness`，完整安装 15 个文件，逐文件核对内容与发布版一致。未修改用户全局 skill 目录，没有创建或迁移实际科研账本。

Codex CLI 0.146.0 新会话在只读权限下实际发现了项目 skill，读取名称、0.2.1 版本和两项规则。唯一完成的本地命令是读取该 SKILL.md，安装文件哈希保持不变；实际消息和观察摘要见 [host_install.json](host_install.json)。首次测试禁用了用户配置，导致模型认证失败；改为沿用用户既有模型/连接配置后成功，没有更改账号或模型设置。只分发可观察输出，不分发内部推理、凭据或无关宿主日志。

GitHub CLI 2.103.3 的 `gh skill install` 又分别从固定提交安装到 Codex、Claude Code、Gemini CLI 的三个隔离项目。三组命令均成功，目录和 0.2.1 版本正确，支持文件逐字节一致，见 [portable_install.json](portable_install.json)。安装器会重排 YAML 并添加来源字段，因此不能要求它与原 SKILL.md 字节一致；其正文及版本保留。Claude/Gemini 只验证了安装布局，没有启动其模型会话。

发布附件仍提供完整源码包与单 skill 包、逐文件 manifest 和 SHA-256 清单。GitHub 可直接安装使用；市场介绍是可提交材料，不代表某个市场已审核收录。
