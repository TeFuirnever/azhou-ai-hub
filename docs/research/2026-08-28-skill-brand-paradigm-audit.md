# 8 个 canonical Skill 的阿舟品牌范式审计

> 审计日期：2026-08-28（Asia/Shanghai）
> 审计基线：`0767a19`；品牌合同引入提交：`f5d13c3`。
> 范围：仅 `scripts/check_repository.py` 的 `SKILL_BRAND_CONTRACTS` 所列 8 个 canonical Skill；只使用本仓库一手文件。

## 结论

**合同 PASS：8/8 已遵循同一套“阿舟品牌生命周期”范式。** 这不是要求各 Skill 说同一套话或使用同一组 emoji：共享的是身份、领域口号、精确启动事件、成功/失败/hold 的语义、稳定收据、展示层 emoji 边界、原始证据隔离和 Unicode 降级；领域阶段则有意保留差异。

因此，回答“是否使用 emoji、是否加上项目主题”：**是，但为受控的展示层锚点；阿舟身份和各自领域口号已覆盖全部 8 个包。** 机器 schema、enum、digest、路径、命令、测试名和 raw evidence 不得带 emoji。

## 权威范式

项目级权威是 [skill-standard.md](../skill-standard.md)：canonical package 须在入口或品牌层公开 `🦊 阿舟 · <Skill>` 与领域口号；启动事件带稳定 mode/operation 和 scope；多阶段流程使用品牌层，单阶段 Foundation adapter 可在 `SKILL.md` 内联最小合同（第 43--45 行）。成功、失败、跳过和 hold 分开，成功仅在所有声明检查完成后、且为最后阶段事件（第 46--48 行）。

Emoji 只属于展示层，不能进入 JSON key、schema enum、digest、路径、命令、测试名或原始证据；不支持 Unicode 的 host 只能去掉 emoji，不能改机器字段和值（第 50 行）。仓库 gate 对全部 canonical Skill 强制身份、精确启动格式、success/failure/hold、emoji 边界、raw-evidence 边界和 Unicode fallback（第 52 行）。

实现侧把 8 个目标及其 display name、motto、startup protocol 集中为 `SKILL_BRAND_CONTRACTS`，并要求有品牌层的包在品牌层逐字包含启动协议：[check_repository.py](../../scripts/check_repository.py) 第 83--128、187--241 行。回归测试在缺失任一核心 marker 或启动协议漂移时失败：[test_check_repository.py](../../tests/test_check_repository.py) 第 51--124 行。

## 8 Skill 矩阵

| Skill | 判定 | 身份与项目主题 | 受控 emoji / 生命周期证据 | 保留的领域差异 |
|---|---|---|---|---|
| `azhou-doctor` | PASS | `🦊 阿舟 · Azhou Doctor` 与“先诊断，不越权修复。”：[SKILL.md](../../skills/azhou-doctor/SKILL.md) 第 8--10 行。 | 精确启动、success/failure/hold、display-only、raw evidence 和 Unicode fallback 都内联于第 14--22 行。 | 只读诊断；不把 doctor 变成 setup/repair（第 12、24--36 行）。 |
| `azhou-info` | PASS | 身份与“只报告仓库能证明的事实。”：[SKILL.md](../../skills/azhou-info/SKILL.md) 第 8--10 行。 | 内联精确启动及完整展示边界：[SKILL.md](../../skills/azhou-info/SKILL.md) 第 14--22 行。 | 仅报告 CLI 已返回的事实、`changes` 恒为空（第 24--34 行）。 |
| `azhou-setup` | PASS | 身份与“先看计划，再按同一计划执行。”：[SKILL.md](../../skills/azhou-setup/SKILL.md) 第 8--10 行。 | 内联精确启动、success/failure/hold、managed receipt/raw evidence、Unicode fallback：[SKILL.md](../../skills/azhou-setup/SKILL.md) 第 14--22 行。 | 计划先行、`planId` 绑定 apply、显式授权与 mutation 边界（第 24--40 行）。 |
| `azhou-verify` | PASS | 身份与“完整 gate 跑完，结论才成立。”：[SKILL.md](../../skills/azhou-verify/SKILL.md) 第 8--10 行。 | 内联精确启动、success/failure/hold、展示层限制和 Unicode fallback：[SKILL.md](../../skills/azhou-verify/SKILL.md) 第 14--22 行。 | 只走完整公开 gate；不把选中测试或旧输出算作成功（第 24--34 行）。 |
| `excalidraw-diagram` | PASS | 身份和唯一规范口号“先让结构讲清关系，再让文字补充证据。”已在入口与品牌层逐字统一：[SKILL.md](../../skills/excalidraw-diagram/SKILL.md) 第 8--10 行；[brand-layer.md](../../skills/excalidraw-diagram/references/brand-layer.md) 第 5--10 行。 | 启动至 hold 的固定锚点和每条至多一个前导 emoji：[brand-layer.md](../../skills/excalidraw-diagram/references/brand-layer.md) 第 14--33 行；machine-status 映射和收据分离见第 41--87 行；emoji/raw-evidence/Unicode 边界见第 90--95 行。 | 需求、事实、场景、审核轮次、交付与具名视觉复核，不能用 JSON 可解析替代视觉判断：[SKILL.md](../../skills/excalidraw-diagram/SKILL.md) 第 22--34、191--203 行。 |
| `llm-wiki` | PASS | 身份与“知识要留得住，也要经得起查证。”：[SKILL.md](../../skills/llm-wiki/SKILL.md) 第 8--10 行；品牌层同样声明名称和口号：[brand-layer.md](../../skills/llm-wiki/references/brand-layer.md) 第 5--10 行。 | 固定启动、scope/read/write/migrate/lint、success/failure/hold 词典：[brand-layer.md](../../skills/llm-wiki/references/brand-layer.md) 第 12--40 行；`fail/hold/skipped` 不可再成功（第 56--64 行）；raw evidence、MCP/Hook/CLI emoji-free 和 Unicode fallback（第 118--124 行）。 | 读、写、删、迁移、健康检查各有顺序与安全字段；不会把页面正文或私有输入拼到阶段消息（第 54、58--62 行）。 |
| `repo-pedant` | PASS | 身份、口号和新生成 receipt 均使用 canonical display name `Repo Pedant`：[SKILL.md](../../skills/repo-pedant/SKILL.md) 第 8--10、149 行。解析器仍接受旧品牌标题 `Repo-pedant` 和无品牌旧标题，确保历史记录可读，但不会继续生成旧写法。 | 固定事件、密度、禁止改写分隔符：[brand-layer.md](../../skills/repo-pedant/references/brand-layer.md) 第 12--42 行；machine-status 映射第 50--66 行；emoji/raw evidence、hook 固定文案、success-last、Unicode fallback 第 68--75 行。 | `start -> scope -> inventory -> impact -> sync` 五阶段、execution protocol validator 和 memory/coverage 收尾要求：[SKILL.md](../../skills/repo-pedant/SKILL.md) 第 26--36、122--144 行。 |
| `super-caveman` | PASS（特例符合标准） | 品牌层公开 `阿舟 · Super Caveman`、口号“少说话，技术信号不丢。”与克制语气：[brand-layer.md](../../skills/super-caveman/references/brand-layer.md) 第 5--12 行。 | 对 material multi-step operation 定义精确启动、范围、候选、success/failure/hold（第 14--27 行）；状态映射/稳定收据（第 29--70 行）；emoji/raw evidence/Unicode 边界及 success-last（第 72--77 行）。 | 普通简短答复、help、commit/review/statistics 不播报生命周期事件：[SKILL.md](../../skills/super-caveman/SKILL.md) 第 40--50 行。这正是标准允许的模式 Skill 特例，而非漏配。 |

Foundation 四项没有独立 `brand-layer.md`，是因为其属于单阶段 adapter；项目标准明确允许把同一最小合同内联于 `SKILL.md`，故此处是**符合范式的结构差异**，不是缺失。

## 验证结果

2026-08-28 在当前修复树执行：

```text
python3 -m unittest \
  tests.test_skill_package \
  tests.test_validate_evidence_bundle \
  tests.test_collect_agent_history \
  tests.test_repo_pedant_benchmark

python3 scripts/verify.py
```

结果：**定向 48 tests passed；全仓 309 tests passed；repository policy、3 组 benchmark/integrity gate 与 Git whitespace gate 全部通过。** 全量品牌合同测试直接断言 8 个 canonical Skill 零错误；负例测试会拒绝启动格式漂移、缺 identity/motto/success/failure/hold/Emoji/raw-evidence/Unicode marker 或缺 brand layer 的情况：[test_check_repository.py](../../tests/test_check_repository.py) 第 51--124 行。`test_skill_package.py` 还固定验证 Excalidraw、LLM Wiki、Repo Pedant 与 Super Caveman 的领域锚点、收据或关键边界；Repo Pedant validator 和 history collector 测试同时覆盖新规范标题及两种历史标题兼容。

## 风险与建议

1. **没有发现当前静态合同缺口。** 8/8 的 PASS 是针对受审文档、合同 gate 和回归测试的当前树结论。
2. **两处严格文案差异已关闭。** Excalidraw Diagram 的入口、品牌层与收据使用同一条规范口号；Repo Pedant 的新收据使用 canonical display name。旧 `Repo-pedant` 标题只保留为兼容输入与回归夹具，不再作为当前输出模板。
3. 现有通用 gate 主要验证必需文本和精确 startup；它不能单独证明未来每个 host 的真实 LLM 输出都严格遵从“success 最后”“每阶段一次”等语义。多阶段包已在品牌层写明该约束，但仍应在新增 harness adapter 或输出渲染器时补一个端到端 transcript/receipt validator 测试。
4. 不要为了“统一感”强行把领域阶段改成同一组 emoji。标准要求的是共享语义与边界，不是同质化：图表的 `🧪 审核第 n 轮`、Wiki 的 `📝/📦/🧪`、Repo Pedant 的 `🗂️/🕸️/🧹`、Super Caveman 的 `🪨` 都是有领域含义的受控阶段锚点。

## 可复用结论

这 8 个 Skill 已形成统一的阿舟项目主题：**同一身份结构、同一证据语义、同一机器/展示分层，配合各自领域阶段。** Emoji 是可降级的展示协议，不是 schema 或证据的一部分。共享范式以及当前公开口号、显示名的逐字一致性均已完成；历史 Repo Pedant 标题继续作为只读兼容输入。
