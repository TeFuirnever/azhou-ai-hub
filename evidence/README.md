# Repo-pedant evidence

这里定义 `repo-pedant` 的演化材料边界。

## 公开收据

- [2026-08-23 public install smoke](public-install-smoke-2026-08-23.md)：从公开 GitHub 默认分支发现并隔离安装两个 canonical skill；不升级为发布、跨 harness 或模型质量证明。
- [2026-09-01 Foundation discovery/invocation on Claude Code](foundation-discovery-invocation-claude-2026-09-01.md)：四个 Foundation package 的项目级 link 安装、headless 主机发现与文档化只读调用；不升级为个人根安装、交互会话或跨 harness 一致性证明。
- [2026-09-01 Foundation discovery/invocation on zcode](foundation-discovery-invocation-zcode-2026-09-01.md)：四个 Foundation package 的项目级 link 安装、`skills list` 主机发现与文档化只读调用；调用依赖已授权的最小用户级 model provider 配置；不升级为 GUI 行为或跨 harness 一致性证明。

## 可进入 Git

- 脱敏 synthetic fixtures；
- 不含会话标识的聚合计数；
- 失败机制与证据哈希；
- 回归 prompts、验证命令、paired votes；
- 已知覆盖限制。

## 不进入 Git

- Codex 或 Claude 原始 JSONL；
- zcode 原始 session JSON；
- 带 request/correction excerpt 的采集报告；
- 用户路径、身份、账号、URL、token、私有代码或未公开资产。

本地运行 `collect_agent_history.py` 后，先用 `validate_evidence_bundle.py` 校验，再依据高信号哈希回看原始会话，把机制级结论写入 `benchmarks/repo-pedant/history/`。原始历史始终留在 runtime 自己的目录。
