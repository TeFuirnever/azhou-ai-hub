# arch-doc skill 最佳实践评审（评审员原始报告存档）

- 评审日期：2026-09-04 · 评审线：critic（独立、只读、写/审分离）
- 评审对象：skills/arch-doc/ 全部文件（SKILL.md、4 份 references、5 份模板 + PROVENANCE）
- 对标：仓库 docs/skill-standard.md + check_repository.py 品牌契约、Anthropic Agent Skills 官方实践、writing-for-agents 杠杆、供应链与跨 harness 规范
- 裁决：**REVISE（修后可发布）** —— 13 条发现（MAJOR 7 / MINOR 6）；本存档为原始报告，修复记录见 git 历史

## 总评

骨架工程（哈希锁、品牌合同、分步完成判据、渐进披露）扎实，但 SKILL.md 声称层与 vendored 模板实体层未对账——多处完成判据引用包内不存在或与模板直接矛盾的概念。全部 MAJOR 修复后可升 ACCEPT。

## 发现清单（原始）

### MAJOR
1. 入口文件坏替换残留「自target」（SKILL.md:36）——措辞纪律反噬。
2. 完成判据引用包内不存在的「回链行」（SKILL.md:46）——判据不可机械判定。
3. 「骨架必含十二件」与模板实体不符（词汇表/读者指南/时序图/追溯矩阵/视图索引五件模板中不存在），且与 format-standard「以模板为准」形成双权威方向相反。
4. 状态词表分裂：Bundled 无定义，「目标态」与模板 `Planned` 双词汇。
5. design-doc.md 角色错标：模板选择入口元文档被当成可实例化剖面。
6. 路由三缺口：裸 `templates` 误触发；PRD/详设漏触发；与 excalidraw-diagram「时序图」双触发。
7. 四项确定性 gate 无脚本，确定性承诺靠 LLM 目测。

### MINOR
1. PROVENANCE 缺许可证声明与模板版本号。
2. SKILL.md 复述 PROVENANCE 的来源与日期（两处维护）。
3. 「质量场景卡」仅存在于 description，正文无锚。
4. mode→步骤映射缺失；review 报告落盘位置未指定。
5. description 尾句 "proven" 自评。
6. format-standard 「12 节 practically 完整清单」夹生英文。

## 触发词路由测试（原始判定，MAJOR-6 修复前）

应命中 5/5 ✓；不应命中：简历模板（误触发）、.excalidraw 时序图（双触发）、产品需求文档（漏）、功能详细设计（漏）、收尾整理（正确不命中）。

## 修复去向（评审后 lead 执行）

MAJOR-1..7 与 MINOR-1..6 全部修复：坏替换改「自相矛盾」；回链行改为「模板来源行回链 PROVENANCE」；十二件拆「模板章节 + skill 附加件」并在 format-standard 同步附加件条款；状态词对齐模板词表（Planned/Production 等）并声明目标态 ↔ Planned 映射；design-doc.md 更正为「模板选择权威元文档」；description 删裸 templates、补 PRD/详设触发词、时序图触发词加文档域限定、边界补 excalidraw-diagram 让位；新增 scripts/verify_doc.py（配平/链接/图注入账/changelog 有序/空白五项确定性检查）；PROVENANCE 补许可证与版本；重复来源改指针；质量场景卡落正文锚；mode→步骤映射与报告落盘位置补齐；"proven"/"practically" 措辞修正。确定性脚本已在真实 ARCH 文档上自测通过（exit 0）。
