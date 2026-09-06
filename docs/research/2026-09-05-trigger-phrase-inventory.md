# 触发短语证据盘点（evo-trigger-inventory，2026-09-05）

来源：三 harness 使用记录挖掘（见 `.omc/research/skill-evolution-20260905/REPORT.md`）。全部为 digests/分类级信息，无原始引文。

## 结论

**repo-pedant 是唯一达到"自然语言触发失灵"两次独立复现的 skill**，已由候选 `1fbd85da` 修复晋级（C1）。其余 skill 的证据不足以立触发器候选：

| skill | 手贴显式调用记录 | 是否先有 NL 失败证据 | 判定 |
|---|---|---|---|
| repo-pedant | zcode ≥4 会话 6+ 次、codex 2 次 | 是（用户先 NL 后手贴） | ✅ 已修（C1 promoted） |
| eli5 | zcode ×2（sess_9a0d7e71 等） | 未观察到 NL 失败在先 | watch：手贴可能是习惯而非触发失灵；再积 1 次独立 NL 失败即达线 |
| ralph / wayfinder / diagnosing-bugs / ultraqa / research / archify | 各 1+ | 否（多数非本仓 skill） | 不适用（本仓外或单例） |
| 其余 canonical | 无手贴记录 | 无 | 无证据 |

## 方法校准（C1 的可迁移经验）

1. 区分「手贴习惯」与「触发失灵」：只有同会话内先出现自然语言请求、未路由、随后手贴的序列才算 trigger-miss 证据。repo-pedant 的 5 条信号均满足；eli5 的 2 条不满足。
2. 正/负例必须成对：C1 的负例（generic-question、task-scoped）防止过触发扩张——盘点任何新短语时沿用。
3. description 是路由产品也是上下文负载：新增短语与修剪（D1 已落地）同步考虑。

## 各 skill 现行触发面健康度（抽查）

- 描述含明确 MUST trigger 词表的：repo-pedant（已修）、azhou-verify（before completion/handoff/commit/PR/release 触发，边界清晰）、super-caveman（stop 短语 + 显式 enable/disable）。
- 描述为能力型（无显式触发词表）的：eli5（"explain like I'm 5"类）、excalidraw-diagram、arch-doc、llm-wiki 等——这类依赖意图匹配，manual-link 是当前兜底；未观察到失败证据前不动。
