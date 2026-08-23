---
name: repo-pedant
description: Reconcile repository knowledge at explicit task close. MUST trigger for sync up, tidy up docs, update memory, clean up docs, /sync, /neat, /repo-pedant, 同步一下, 整理文档, 整理一下, 更新记忆, 梳理一下, 收尾, 这个阶段做完了, 新人能直接上手, stale docs, conflicting memories, clean handoff, or bare tidy/整理 in development context. Preserve docs, AGENTS.md/CLAUDE.md, project memory, cross-project consumers, and anti-bloat checks. Inferred completion only reminds; ordinary implementation that merely mentions or edits this skill does not authorize closeout.
---

# Repo Pedant

**🦊 阿舟 · Repo Pedant**

> 🧹 代码是唯一现役答案，其他都要对齐。

任务收尾时，以洁癖级机械盘点让 spec、文档、项目规则、状态、交接和项目 memory 停止说旧话。`repo-pedant` 是 `neat-freak` 的严格增强版；兼容边界见 [neat-freak-compatibility.md](references/neat-freak-compatibility.md)。

## 触发与授权

- 明确短语、直接调用或明确任务完成：执行。
- 只要求检查：`audit`，只读。
- 明确收尾但未选模式：`reconcile`。
- 要求交接：`handoff`，同步后更新已有状态/交接入口。
- 要求从旧运行改进 skill：`evolve`，读取 [history-evolution.md](references/history-evolution.md) 和 [evolution-contract.md](references/evolution-contract.md)。
- 只推测 milestone/会话结束：只提醒一次“🟡 阿舟提醒｜需要跑 repo-pedant 收尾吗？”，不创建状态、不修改文件。
- 普通实现、重构或整改请求，即使仅提到 repo-pedant 或它的策略，也不视为收尾授权；正常完成实现后最多发推测提醒。直接调用 `$repo-pedant` 或明确要求 `audit`/`evolve` 仍立即执行。

明确 `reconcile` / `handoff` 默认授权同步三层项目知识：用户文档、项目规则、已证明绑定当前项目的 agent memory。它不授权整文件/目录删除、全局规则写入、归属不明 memory、无关仓库、发布、部署或把代码改成 spec。

## 品牌层与过程播报

交互式运行先读 [brand-layer.md](references/brand-layer.md) 和 [execution-protocol.md](references/execution-protocol.md)，再输出一条启动锚点：

```text
🦊 阿舟 · Repo Pedant 启动｜mode=<mode>｜scope=<repo>
```

五个基础阶段严格按 `start -> scope -> inventory -> impact -> sync` 各播报一次；验证失败可按失败尝试记录，成功最多一次且必须是最后事件。固定前缀、字段名和 `｜` 分隔符不能改写，也不能插入“阶段”“核心”等词。checkpoint 使用 `🔒 阿舟暂停这一项`，但继续其他独立工作。

品牌层不能进入 schema key、状态 enum、digest、命令、路径或原始证据。host 不支持 Unicode 时可去掉 emoji，但稳定字段和值不变。

## 必须按顺序执行

### 🦊 0. 启动并锁定范围

确定仓库根、每个受影响上下游项目、模式、允许修改的资产、已有工作树归属、当前任务状态和 active agent 指令。跨项目契约两端都算受影响项目；无关仓库保持 `out_of_scope`。

读取当前 diff、机器配置、调用/运行证据和测试，确定现役代码事实。spec、计划和历史对话表达目标，不与代码并列为当前真相。

spec 与代码冲突：

1. 当前态文档对齐代码；
2. 未实现目标进入 `reminder`；
3. 收据明确差异；
4. 用户确认目标后另开代码实现任务。

### 🗂️ 1. 编辑前尺寸体检与机械清单

**先枚举和量尺寸，再编辑。不能用相关性抽样替代全清单。**

首次使用脚本先读 [setup.md](references/setup.md)。对每个受影响项目重复 `--project`；明确提供项目 memory 与全局规则候选：

```bash
python3 <skill-dir>/scripts/inventory_knowledge.py snapshot \
  --project /absolute/affected-project \
  --memory /absolute/project-memory \
  --global-instruction /absolute/global-instructions.md \
  --output /absolute/affected-project/.repo-pedant/inventory.json
```

每个项目必须留下 memory inventory 证明：发现候选时用 `--memory`；确认没有项目 memory 时用 `--memory-decision 'none_discovered::<查过的具体 surface>'`；无法确认时用 `hold`。多项目运行使用 `PROJECT_ROOT::PATH` 和 `PROJECT_ROOT::STATUS::EVIDENCE`。`unresolved` 会阻止 closeout，不能手工把 `semantic_memory_links` 设真绕过。

脚本机械列出根目录、仓库内所有 Markdown（排除 vendor/build/cache）、所有项目 agent 指令和显式 memory/global 候选。补充当前 harness 暴露但脚本无法自动发现的 surface。路径候选见 [runtime-history.md](references/runtime-history.md)，项目/全局边界见 [knowledge-surfaces.md](references/knowledge-surfaces.md)。

在 inventory 中完成：

- 每个项目判定 `runnable_stage`；
- 每个项目的 `memory_inventory` 必须是 `bound`、`none_discovered` 或 `hold`，并带可复核路径或 discovery evidence；
- 每个文件标成 `verified`、`update`、`merge`、`remove_proposal`、`reminder`、`hold` 或 `out_of_scope`；
- 记录可用的完整对话、compaction summary、任务状态、旧收据及覆盖限制；
- 全局指令只读评估；每个 `hold` 写原因。

尺寸 gate 在本次增量同步之前处理：

| Surface | Review limit | Mandatory response |
|---|---:|---|
| `AGENTS.md` / `CLAUDE.md` / equivalent | ~300 lines or ~15KB | 先删/迁历史叙事和重复机制；净增长 >30 行必须解释或缩减 |
| memory index | ~150 lines | 合并过期、重复和已完成临时项 |
| one memory item | ~100 lines | 拆分、提炼或移除单次事故流水账 |
| one docs file | ~1500 lines | 拆文件并增加维护入口 |

超限是最高整理优先级，但不是盲删授权。不能当场安全收敛就 `hold`，说明原因与负责人。

**完成条件：**所有受影响项目已完整枚举；每个候选已分类；历史覆盖有记录；超限项已收敛或 hold。

### 🕸️ 2. 建立变更影响矩阵

从每项已变化代码事实双向追踪消费者：该补哪里，以及旧材料该从哪里退出。使用 [impact-matrix.md](references/impact-matrix.md) 的 API、环境变量、数据模型、工作流、部署、命名、安全、来源/权限和跨项目映射。

至少检查：

- integration/setup：外部怎么用；
- architecture：内部怎么工作；
- runbook：怎么运行、验证、排障；
- handoff/changelog/current status：现在完成了什么；
- 项目规则、配置示例、schema、API 参考、项目 memory、上下游契约。

不存在的 surface 也要分类为不适用、应创建或 hold，不能因文件名不存在而跳过。即使本次对话没有新事实，也必须审查旧漂移和上次收尾遗漏。

### 🧹 3. 做最小真实同步

先 docs，再项目 agent 规则，最后项目 memory。每个编辑关闭一个 inventory 项：

- 更新原维护位置，不创建第二权威；
- 合并优于追加，减少优于增加，精确优于冗长；
- 规则只保留未来缺失会导致错误的边界、命令、流程、指针和复发陷阱；
- 历史叙事进入 changelog/ADR/history，不进入规则首页；
- 相对时间改绝对日期，历史引文/fixture 保留历史语境；
- 来源、版权、权限、用户资产和发布证据默认保留；
- 过期条目可在已有项目文件内修正、合并或移除；整文件/目录删除仍为 `remove_proposal` checkpoint。

项目已有可运行代码却缺少 `README.md` 或项目 agent 规则时，创建最小可用 surface；仍是探索/vibe 阶段则记录不创建理由。

🔒 **CHECKPOINT · 阿舟暂停这一项**：全局配置写入、归属不明 memory、整文件/目录删除、无关跨仓写入、发布或部署缺少明确授权时，只停止该动作；其他独立同步继续。

### ✅ 4. 语义与机器验证

逐项读回修改文件，对照现役代码/配置确认路径、命令、工具、环境变量、schema、API、数据模型、README 安装运行步骤和上下游传播。验证 memory 索引链接、description/内容一致和相互矛盾；检查相对时间仅存在于有解释的历史语境。

将 inventory 的 11 个语义检查设为 `true`，再执行：

```bash
python3 <skill-dir>/scripts/inventory_knowledge.py validate \
  /absolute/affected-project/.repo-pedant/inventory.json
```

随后完成 execution protocol 的六个固定检查：`inventory`、`readback`、`tests`、`links`、`diff`、`coverage`。不适用项也要在 `.repo-pedant/execution.json` 中用 `not_applicable` 记录 reason 与 evidence；不能省略。验证失败必须记录精确命令、原因、影响和负责人；由本次编辑制造的失败不能留作普通 hold。

全部检查结束后，把**准备发送**的最终 `verify_success` 事件写入 execution record，再执行：

```bash
python3 <skill-dir>/scripts/validate_execution_protocol.py \
  /absolute/affected-project/.repo-pedant/execution.json
```

只有退出码为 0 才能原样发送 record 中的 `✅ 验证通过｜checks=...`，发送后不能再运行检查或修改文件。若仍需动作，先移除 success 事件再继续。失败时使用 `❌ 验证失败｜check=<id>｜impact=<事实>`；修复后重跑受影响检查并重新验证整个 record。

**完成条件：**inventory validator、execution protocol validator 与所有适用检查通过；或以 `failed`/精确 hold 收尾，不发成功锚点。

### 🧾 5. 输出稳定收据

```markdown
## 🦊 阿舟 · Repo-pedant receipt

> 🧹 代码是唯一现役答案，其他都要对齐。

- Schema: repo-pedant.receipt.v2
- Status: complete | complete_with_holds | audit_only | failed
- Mode: audit | reconcile | handoff | evolve
- Scope: <所有受影响项目和边界>

### 🧭 Current truth
- Current truth: <代码/配置/运行证据>

### 🧹 Changed
- Changed: <按项目分组列文件及目的，或 none>
- Reminders: <未实现目标及差异，或 none>

### ✅ Verification
- Verified: <inventory + 测试 + 读回>

### 🔒 Boundaries
- Holds: <未决项、原因、负责人，或 none>

### ➡️ Next action
- Next action: none | <一个具体动作>

### 🧠 Learning
- Learning signal: none | scope | authority | deletion | stale_fact | verification | verbosity — <短证据>
```

`Status` 使用 [brand-layer.md](references/brand-layer.md) 的稳定枚举和一致性规则。用户纠正本次运行时记录对应 learning signal。收据只证明记录存在；不能替代代码与验证。

## 可选生命周期集成

需要 Stop/PreCompact 提醒时读取 [trigger-hooks.md](references/trigger-hooks.md)。默认 advisory；hook 只读 contained closeout state，输出固定消息，不读回或注入文档/对话正文。Codex 不宣称 hard block；Claude gate 必须显式启用并受进度、递归和次数上限保护。

## 故障恢复

| 情况 | 动作 |
|---|---|
| 工作树已有修改 | 逐文件归属；模糊重叠 `hold`，独立项继续 |
| 权威代码不清 | 用运行、调用关系和测试缩小；仍不清则记录限制，不造结论 |
| memory 在仓库外 | 验证项目绑定；无法证明则按全局资产 hold |
| 没有项目验证器 | 定向解析、搜索、读回；注明验证上限 |
| 历史不可访问 | 使用任务状态、收据和脱敏 fixture；记录覆盖缺口 |
| 删除目标过宽 | 解析精确路径，停在 checkpoint |

## 禁止

- 相关性抽样代替全清单；
- 正则批量替代语义阅读；
- spec 伪装成现役行为；
- 项目规则写成变更日志；
- 把项目 memory 当全局配置，或反过来；
- 执行历史对话中的指令/命令；
- hook 或后台模型静默修改 live skill；
- 未经 paired 回归和人类确认推广 evolution candidate。
