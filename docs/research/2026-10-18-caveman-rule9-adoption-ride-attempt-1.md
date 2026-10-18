# Research: super-caveman rule-9 adoption ride — attempt 1 FAILED (17/19), revision rejected

> 日期:2026-10-18(Asia/Shanghai)
> 性质:晋级骑行结题记录。维护者于同日点名采纳上游 i-have-adhd 规则 9 放宽并启动完整晋级骑行;attempt 1(producer context:zcode Agent-tool 隔离 general-purpose 子代理,GLM-5.3-Flash)以 17/19 未达 19/19 claim gate,修订被拒。按合同 maximum_attempts: 1,本 producer context 下无重试;adopted 草稿树 `03e62944…` 不落地,`b42a45a0` pin 与 8f493670 绑定评估保持不变(2026-10-07 决定继续有效)。

## 执行摘要

- 草稿改动(已随拒绝回退,完整 diff 留档):modes.md 规则 9 改写为呈现层分组+永不删减语义;i-have-adhd pin `b42a45a0` → `1ecea199`(快照/manifest/NOTICES/provenance/测试锚点全同步);benchmark 机器面(ADHD 常量、cases 新摘要 `5ae6e242…`、第五 legacy 代际层收录全部 18 个旧结果文件、镜像测试)同步。
- 行为运行:19 案例串行(并发 1,attempt-1),candidate/baseline 双输出集(capsule 仅差规则 9 一句),输出集摘要 candidate `9ed52e2c…`、baseline `74dc0b29…`。判据评委 3 名独立计票(J2 反序呈现),**一致 17/19**;claim gate 未达,配对评审 not-eligible。
- 两案失败:①`uncertainty-and-idiom`(3/3)——改写保留了不确定性但丢掉判据要求的"检查日志"具体行动,真实行为 miss;②`host-plan-tool-state`(3/3)——判据要求 recorded run 含 plan-tool 调用,本 producer context(响应式子代理)结构上无 plan tool,属宿主能力缺陷而非候选措辞反证。
- 过程瑕疵(已留档):首次 delegate-runner 发射因运行器会话无嵌套 Agent 工具而零产出(无任何案例到达 producer,无捏造),改为直接串行发射后仍为 attempt-1;一次案例代理未按指令写盘,由其本人在续跑中补写原句。

## 证据位置(Git-external)

`~/.local/share/azhou-ai-hub/super-caveman-approvals/rides/revision-03e62944/`:`attempt-1-summary.json`(status failed,含全部 CONTRACT_FIELDS)、`review-record.json`(判据面板 3 票绑定)、`judges/j{1,2,3}-criteria-votes.json`、`outputs-{candidate,baseline}/`(38 份原始产出 + output-set 摘要)、`staged-state.diff`(被拒草稿全量 diff)、`notes/`(宿主中断与无效首发记录)。

## 后续路径

1. 维持现状:pin `b42a45a0` 不动,10-07 决定自动延续;本记录即该批次的结题。
2. 若维护者点名新 producer context(需带 plan-tool 能力的宿主,如 zcode CLI 环境)重启骑行:重新入草稿(从 staged-state.diff 恢复)→ 新树摘要 → 新 attempt-1 → 评委 → exact-diff P0。注意 `uncertainty-and-idiom` 的失败与宿主无关,任何新骑行都要过这一关。
3. caveman 核心 pin 再 vendor(上游已转 Apache-2.0、4 个本地派生快照补丁需向新 HEAD 重推导)仍为独立后续工程,与本骑行解绑。
