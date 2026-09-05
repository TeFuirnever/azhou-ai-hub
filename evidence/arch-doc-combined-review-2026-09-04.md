# arch-doc skill 综合评审报告（两轮合并）

- 对象：azhou-ai-hub `skills/arch-doc/`（SKILL.md + 4 references + scripts/verify_doc.py + 5 份只读模板）
- 第一轮：通用 skill 最佳实践（仓库 skill-standard、Anthropic Agent Skills 官方实践、writing-for-agents、供应链/跨 harness）——critic 独立评审，13 条发现，**已全部修复**
- 第二轮（本报告新增）：**架构设计文档 skill 生态专项**——对标 skill-creator 的 benchmark 纪律、ADR 工具链（adr-tools）、docs-as-code CI 工具链（markdownlint/vale/lychee/PlantUML 渲染门）、模板实例化实践（脚手架）、安全实践（不可信输入按数据处理）
- 存档：本轮发现随报告入 `evidence/`；第一轮原始报告见 `evidence/arch-doc-review-2026-09-04.md`

## 结论

第一轮修复后，skill 在**纪律层**（证据状态、图纪律、回源校准、确定性校验）已达可用；第二轮显示**工具层与生态层**还有 8 个 GAP——skill 目前「教得对」但「替 agent 做得少」：缺脚手架、缺基准、缺渲染门、缺不可信输入防护。全部 GAP 均为增量能力，不动已发布结构。

## 第一轮发现与修复状态（13/13 CLOSED）

| # | 发现 | 状态 |
|---|---|---|
| M1 | 入口坏替换「自target」 | ✅ 已改「自相矛盾」 |
| M2 | 「回链行」判据不可判定 | ✅ 改「模板来源行回链 PROVENANCE」 |
| M3 | 「十二件」与模板实体不符 + 双权威反向 | ✅ 拆「模板章节 + skill 附加件」两清单，format-standard 同步 |
| M4 | 状态词表分裂（Bundled 无定义 / 目标态 vs Planned） | ✅ 对齐模板词表，声明目标态 ↔ Planned 映射 |
| M5 | design-doc.md 角色错标（选择元文档当骨架） | ✅ 更正为「模板选择权威元文档」 |
| M6 | 路由三缺口（裸 templates / PRD 详设漏触发 / 时序图双触发） | ✅ description 重写 + 边界补 excalidraw-diagram 让位 |
| M7 | 四项 gate 无脚本 | ✅ 新增 scripts/verify_doc.py（五项确定性检查，实测 exit 0） |
| m1–m6 | PROVENANCE 许可证/重复来源/质量场景卡锚/mode 映射/proven 措辞/practically 夹生 | ✅ 全部修复 |

## 第二轮：生态专项 GAP（8 项，均未修）

| # | 严重度 | GAP | 业界对标 | 建议动作 | 工作量 |
|---|---|---|---|---|---|
| G1 | 高 | **无脚手架**：新文档起步靠手工复制模板改头；业界的 adr-tools / docx skill 都有 `new` 命令 | adr-tools `adr new`；Anthropic docx skill 生成器模式 | 加 `scripts/new_doc.py <剖面> <ID> <标题>`：从模板实例化、盖 ID/版本/日期/文档控制表、输出到指定路径（不改模板） | M |
| G2 | 高 | **无行为基准**：`benchmarks/` 下 excalidraw/repo-pedant/super-caveman 都有，arch-doc 没有；README 诚实写「No behavior benchmark yet」的模式 skill 未沿用 | 仓库 skill-standard §4（benchmarks 统一放仓库级）+ Anthropic eval 纪律 | 建 `benchmarks/arch-doc/`：一个 golden case（样例上游事实 → 期望产物过 verify_doc 门 + 结构抽查） | M |
| G3 | 中 | **PlantUML 可渲染性无门**：模板自己要求「评审前验证 PlantUML 可渲染」，但环境无 Java/PlantUML 时 verify_doc 只查配平，语法错（如 activity 图混用旧新语法）检不出 | docs-as-code 渲染门（ PlantUML server/CLI pre-commit） | verify_doc 增 `--plantuml-cli` 可选项：检测到本地 plantuml 就逐图渲染验证，缺失时输出 `skipped`（诚实门，与 excalidraw visual-check 同款语义） | S-M |
| G4 | 中 | **不可信输入无防护**：上游文档/代码是外部输入，可能带指令注入（「忽略以上规则…」）；skill 未声明「研读材料按数据处理，其中的指令不执行」 | Anthropic/OpenAI agent 安全实践：fetched content is data, not instructions | calibration-guide 增一条研读纪律：上游材料只提事实，材料内出现的指令一律忽略并在笔记中记「发现注入尝试」 | S |
| G5 | 中 | **追溯无 checker**：§16 追溯矩阵人工维护，PRD-Fxx ↔ ARCH ↔ DETAIL 漂移无机器检查 | docs-as-code 一致性门 | verify_doc 增 `--trace "PRD路径,DETAIL目录"` 可选项：抽取三列矩阵行并核对目标存在 | M |
| G6 | 中 | **无 ADR 脚手架**：ADR-0001 手工立；ADR 索引约定（编号/状态/日期）无模板 | adr-tools 模板与编号约定 | references 增 `adr-template.md`（Nygard 五段式占位）+ SKILL.md §15.1 指针 | S |
| G7 | 低 | **模板上游同步流程未写**：PROVENANCE 锁了哈希，但 MCC 模板演进后如何同步（重拷→重算哈希→更新表）只在哈希表校验命令里隐含 | 供应商依赖同步实践 | PROVENANCE 增「同步流程」三步 | S |
| G8 | 低 | **输出语言规则未写**：archify 等同类 skill 显式声明「产出语言跟随请求」；arch-doc 模板为中文，英文请求时行为未定义 | Anthropic 语言一致性实践 | SKILL.md 边界加一句：产出语言跟随用户请求语言；模板为中文剖面时按模板结构、按请求语言书写 | S |

另两条**记录在案、建议不做**：导出 PDF/HTML（stakeholder 分发属交付转换，超出「写文档」边界，pandoc 可后补）；TOC 生成（Markdown 渲染器自带）。

## 合并 backlog（两轮合并后的剩余工作，按价值排序）

| 优先级 | 项 | 来源 |
|---|---|---|
| P0 | G1 脚手架 + G6 ADR 模板（模板体系闭环的最后两块） | 本轮 |
| P0 | G4 注入防护一句 + G8 语言规则一句（两句话护栏） | 本轮 |
| P1 | G2 行为基准 golden case（进仓库 benchmarks/ 与 CI） | 本轮 |
| P1 | G3 渲染门（可选项）+ G5 追溯 checker（verify_doc 扩展） | 本轮 |
| P2 | G7 同步流程注 + 首轮两条非阻塞观察（§8.1 词形 / ADR 路径写法） | 两轮 |

---

## 状态更新（同日执行记录）

合并 backlog 全部执行完毕：G1 `scripts/new_doc.py`（含选择器链接改写，脚手架→verify 实测 exit 0）；G2 `benchmarks/arch-doc/`（case-01-scaffold）；G3 `verify_doc.py --plantuml-cli`（可选项，缺失时诚实 skipped）；G4 calibration-guide 不可信输入纪律；G5 `verify_doc.py --trace-prd/--trace-detail-dir`；G6 `references/adr-template.md`；G7 PROVENANCE 同步流程；G8 SKILL.md 产出语言规则。首轮两条非阻塞观察此前已修。仓库门禁：861 files passed、unittest OK、whitespace 干净。
