# arch-doc 与 azhou-ai-hub 兄弟 skill 横向对比（GAP 报告）

- 日期：2026-09-04 · 对象：`skills/arch-doc/` · 基线：本轮修复后
- 对比样本：repo-pedant（最重装）、excalidraw-diagram（最重装 + 基准门）、llm-wiki、lavish、super-caveman、azhou-* 工具族、eli5、autoresearch

## 面矩阵（skill × surface）

| surface | 兄弟现状 | arch-doc | 判定 |
|---|---|---|---|
| SKILL.md | 全有 | 有（92 行，六步 + 判据） | ✓ |
| references/brand-layer.md | 多阶段 skill 必备（repo-pedant / excalidraw / lavish / llm-wiki / super-caveman 有） | **本轮已补**（启动行对齐契约、状态前缀、收据 schema、Unicode 降级） | ✓（本轮闭环） |
| references/history-evolution.md + evolution-contract.md | repo-pedant / excalidraw 有（受控演化 §5：采集、失败分类、promotion gate） | 缺 | GAP（首演进前必须建） |
| references/setup.md | 全部兄弟有（含零依赖声明） | **本轮已补**（stdlib 声明 + plantuml 可选依赖 fail-closed 边界） | ✓（本轮闭环） |
| scripts/ | 重装 skill 9–16 个；azhou-* 0 个 | 2 个（new_doc / verify_doc），均确定性、标准库 | ✓ 够域用 |
| benchmarks/<skill>/ + runner | excalidraw（5 frozen case + integrity gate）、repo-pedant（3-case + 上游快照哈希）、super-caveman（fixtures + response cases） | 有目录 + 手工 case，**无 runner、无运行证据收据** | GAP |
| docs/demos/<skill>.md | 4 个 skill 有 demo | 缺 | GAP（低） |
| assets effect 图 | 仅 REQUIRED 的两张（super-caveman / llm-wiki） | 缺 | 非必须 |
| MCP / 外部运行时 | llm-wiki（MCP）、autoresearch（GPU checkout） | 不适用 | — |

## GAP 清单（修复后剩余）

| # | 优先级 | GAP | 依据 | 动作 |
|---|---|---|---|---|
| 1 | **必须（本轮已补）** | brand-layer.md 缺失——skill-standard §3「多阶段 skill 将顺序、固定前缀、字段和分隔符写入 references/brand-layer.md」 | skill-standard §3 | 已建：四模式阶段表、启动行（与契约逐字一致）、✅/❌/🔒 前缀、收据 schema、Unicode 降级；brand_path 已登记，gate 实测通过 |
| 2 | **必须（本轮已补）** | setup.md 缺失——--plantuml-cli 是可选外部依赖，按 §2「有外部依赖须写最低版本、定位、失败边界、验证命令」 | skill-standard §2 surfaces 表 | 已建：stdlib 声明 + plantuml 可选依赖 fail-closed 边界（缺 CLI 时 skipped，不宣称已渲染） |
| 3 | 应建（首演进前） | history-evolution.md + evolution-contract.md：受控演化要求「observed→…→promoted」管线有家可归；arch-doc 必然会被用户反馈迭代 | skill-standard §5；repo-pedant / excalidraw 先例 | 下次演化发生时先补这两份，把首轮/本轮评审作为首批历史案例收录 |
| 4 | 应建 | 基准只有手工 case：无 runner、无运行证据收据（skill-tree digest / case digest / artifact digest / 具名人工检查）；excalidraw/repo-pedant 都有可重跑 runner + integrity 门 | skill-standard §4 证据与评测 | 把 benchmarks/arch-doc/case-01 的四条期望写成自动断言脚本并接入 CI；跑一次留收据 |
| 5 | 可选 | docs/demos/arch-doc.md 缺（4 个兄弟有 demo，利于使用者上手） | hub 惯例 | 用 draft 模式对一个样例 repo 走一遍，截 receipt 成 demo |
| 6 | 不适用 | scripts 深度（16 个）、effect 图、MCP | 域差异 | — |

## 结论

横截面对照下，arch-doc 的结构性缺口只剩两个：**受控演化双文件（history-evolution + evolution-contract，首演进前必须）** 与 **基准 runner + 证据收据（CI 化）**；brand-layer 与 setup 两个必须项本轮已闭环并通过仓库 gate（863 files passed、unittest OK、whitespace 干净）。demo 与 effect 图属可选营销面，不影响 skill 合规与可用性。
