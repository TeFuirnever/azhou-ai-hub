# Repo-pedant evidence

这里定义 `repo-pedant` 的演化材料边界。

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
