# Arch Doc demo

从上游真源到一份过五道确定性门的架构文档。本 demo 用 MCC ARCH-2026-001 的真实演进轨迹演示两个模式。

## draft + calibrate（真实轨迹）

```text
🦊 阿舟 · Arch Doc 启动｜mode=draft｜scope=<repo>
```

1. 研读：四名研究员按域精读上游 96 篇文档，产出 4 份研究笔记（120 条带出处事实，存 `.omc/research/`）。
2. 骨架与成文：按 `references/templates/software-implementation-architecture.md` 剖面产出 ARCH v0.1–v0.12（含 18 张四联注 PlantUML）。
3. calibrate：两名研究员回源核对，16 处勘误全部应用（升 v0.17）。

## review + 修复（真实轨迹）

```text
🦊 阿舟 · Arch Doc 启动｜mode=review｜scope=docs/architecture/arch-2026-001-mcc-system.md
```

- 双线对标评审：结构 3.1/5、技术 17/30，16 条发现 + 20 项改进清单（存 `evidence/arch-doc-combined-review-2026-09-04.md`）。
- Ralph 循环执行全部改进（18 stories），architect 两轮裁决后 APPROVED（v0.16）。
- 可读性校准：89 条审计逐条应用（v0.13）。

## sequence（真实轨迹）

```text
🦊 阿舟 · Arch Doc 启动｜mode=sequence｜scope=docs/architecture/arch-2026-001-mcc-system.md
```

补 5 张时序图（资产接入 / 记忆提取 / 身份隔离 / 行为约束 / 并发恢复），研究员回源核对 16 处勘误后定稿（v0.17）。

## 收据

最终确定性校验：`✅ 验证通过`——链接 11/11、PlantUML 23/23 配平、changelog 0.1→0.17 有序、正文零图形格式偏差、状态词合规。演进与证据链见 skill 内 `references/history-evolution.md` 与 `evidence/`。
