# Research: super-caveman rule-9 adoption ride 2 — attempt 1 FAILED (18/19), revision rejected

> 日期:2026-10-18(Asia/Shanghai)
> 性质:晋级骑行结题记录。维护者于同日点名 ride 2(producer context:zcode Agent-tool 串行 general-purpose 子代理 + GLM-5.3-Flash,文件式 plan tool 为一等公民;`maximum_attempts: 1`)重试规则 9 采纳;attempt 1 以 18/19 未达 19/19 claim gate,修订 `12b5552a…` 被拒。adopted 草稿树不落地,`b42a45a0` pin 与 8f493670 绑定评估保持不变(2026-10-07 决定继续有效)。前次记录见 [2026-10-18 attempt-1 拒绝](2026-10-18-caveman-rule9-adoption-ride-attempt-1.md)。

## 执行摘要

- ride 2 草稿(已随拒绝停在租赁分支 `codex/caveman-rule9-ride-2`,完整 diff 留档):最小 rule-9 补丁——在受保护集合加入 "concrete next-step actions",并显式豁免 "checklist 居于 task/plan tool 时散文只点名进行中项与其估计";i-have-adhd pin `b42a45a0` → `1ecea199`;cases 世代 `08963fd0…`(3a01e2eb 内容 + `generation: rule9-ride-2` 标记);机器面 12 文件同步。备妥状态(handoff §1)逐项核验通过。
- 行为运行:19 案例串行(并发 1,attempt-1),candidate/baseline 双输出集各 19 份,输出集摘要 candidate `7bf40680…`、baseline `1da29ce9…`;`host-plan-tool-state` 双侧均自首发配备文件式 plan tool(写入即 recorded call),无作废重跑。判据评委 3 名独立计票(J2 反序呈现),**一致 18/19**;claim gate 未达,配对评审 not-eligible。
- 唯一失败案(3/3 一致):`host-plan-tool-state`——recorded plan-tool call 完全合规(恰好三项、单项进行中、估计挂在 backfill),但用户可见散文把三项计划项连同状态全部复述("Schema update is done; verification stays pending"),违反判据 3"不复述全部三项"。与 attempt-1 同形,**modes.md 的 plan-tool 豁免句没有改变该 producer 的散文行为**。
- attempt-1 的另一失败案 `uncertainty-and-idiom` 本次 3/3 通过:改写保留双因不确定性、"circle back" → "Contact ops."、"check the logs" 独立成项、无填充词。rule-9 补丁的受保护集合扩展在该案按设计生效。
- 草拟期合成探针(4 探针 + 机械冒烟,非合同 prompt,Git-external 留档)全部通过,但探针 P2(plan-tool 散文)通过而合同案例失败——探针未预测到该失败形态,已按 Q3-a 披露写入 limitations。
- 过程瑕疵(已留档):candidate `agent-owned-edit` 首发未配备一次性夹具,产出指向真实仓库且仅列未来步骤;无任何真实仓库文件被改(字节核验),夹具补备后补发,attempt 计数不变。

## 证据位置(Git-external)

`~/.local/share/azhou-ai-hub/super-caveman-approvals/rides/revision-12b5552a/`:`attempt-1-summary.json`(status failed,含全部 CONTRACT_FIELDS 与 limitations 披露)、`review-record.json`(判据面板 3 票绑定)、`judges/j{1,2,3}-criteria-votes.json`、`outputs-{candidate,baseline}/`(38 份原始产出 + plan state + RUN-MANIFEST)、`staged-state.diff`/`staged-state.status`(被拒草稿全量)、`prep/`(胶囊双份 + 探针证据)、`notes/`(夹具装备事件 + 无效首发)。

## 后续路径

1. 维持现状:pin `b42a45a0` 不动,10-07 决定自动延续;本记录即 ride 2 批次结题。失败 aggregate 已按合同入库 `benchmarks/super-caveman/results/revision-12b5552a-attempt-1-summary.json`,其 cases 世代 `08963fd0…` 注册为独立 legacy 层(现行 3a01e2eb 世代与 8f493670 绑定评估不受影响,公共门禁保持绿)。
2. `host-plan-tool-state` 的散文复述失败在两个 producer context、两版规则 9 文本下复现,且合成探针无法预测——任何后续骑行在草拟期就需要一个能复现合同案例形态(而非仅探针形态)的 plan-tool 散文验证,或接受该案为该 producer context 类的结构性边界。`uncertainty-and-idiom` 已被最小补丁修复,不再是障碍。
3. caveman 核心 pin 再 vendor(上游已转 Apache-2.0、4 个本地派生快照补丁需向新 HEAD 重推导)仍为独立后续工程,与本骑行解绑。
