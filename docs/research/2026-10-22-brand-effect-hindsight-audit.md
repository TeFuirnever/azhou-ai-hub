# 品牌锚点效果验证与 Hindsight 对照审计

> 审计日期：2026-10-22（Asia/Shanghai）
> 基线：`6ae1f87`（PR #324 品牌层 v2 合并后）
> 范围：一手研究 Hindsight 本机运行时；实弹合规 ≥3 个阿舟 skill；对抗探针；渲染矩阵。
> 边界：不改任何 skill 行为；缺陷只记录。不引用 Hindsight 的 `SKILL.md` 作为实现证据。

## 预声明阈值

| 指标 | 阈值 | 本轮结果 | 判定 |
|---|---|---|---|
| 启动行服从率 | ≥95% | **75%（3/4）** | **未达阈值** |
| 成功 / 失败 / hold 锚点服从率 | 100% | **100%（9/9）** | 达阈值 |
| 对抗探针拦截 | 漏拦=缺陷 | **11/11 拒绝，0 漏拦** | 通过 |

样本量：4 次真实 Claude Code headless 会话、每个 skill 1 次 attempt-1。小样本，启动行失败对速率敏感；结论按「本轮样本 + 证据路径」陈述，不外推为长期率。

---

## 问题 1：Hindsight 效果里，哪些来自确定性注入，哪些来自模型服从？

### 一手证据（实现，非 SKILL.md）

| 组件 | 证据 | 性质 |
|---|---|---|
| 包 | `@vectorize-io/hindsight-coding-agents` **0.8.2**，`<home>/.hindsight/coding-agents/package.json` | 本机 npm 安装 |
| 安装来源 | `.install-origin.json` → npx 缓存 `@vectorize-io/hindsight-coding-agents` | 确定性 |
| Claude SessionStart 布线 | `~/.claude/settings.json` hooks → `node …/dist/claude-sessionstart-hook.js` | 确定性 |
| Codex 布线 | `~/.codex/hooks.json` SessionStart / UserPromptSubmit / Stop 三钩 + `config.toml` MCP `hindsight` | 确定性 |
| Banner 模板 | `dist/claude-sessionstart-hook.js` 内 `buildSeedBanner()`：cold 时 `Hindsight is learning this repo — ingesting…`，否则 `tracking…`；详情行 `↳ memory bank “${bankId}”` | 确定性字节 |
| 品牌字渐变 | 同文件 `brandWord()`：对 `Hindsight` 逐字符 ANSI 24-bit 色 | 确定性 |
| 工具指南 + 署名指令 | `buildKnowledgePreamble()` 注入 `<hindsight_knowledge>…`；`TOOL_GUIDE` 含强制 credit 句式 | 确定性指令 |
| Host 发射形状 | `standardSessionStart` → `systemMessage` + `hookSpecificOutput.additionalContext` | 确定性 |

### ≥2 harness 真实会话样本

**Harness A — Claude Code 2.1.307**（session `e9f9d432-…`，digest 见 `evidence/brand-effect-audit-2026-10-22/transcript-digests.json`）

确定性注入（hook_response，非模型复述）：

```text
Hindsight is learning this repo — ingesting its decisions, conventions and history
  ↳ memory bank “coding-agent::azhou-ai-hub”
```

同钩 `additionalContext` 含完整 `<hindsight_knowledge>` 与 credit 句式：
`> 🧠 **From Hindsight memory (<page>)** — <the specific facts you drew on>`。

**Harness B — Codex CLI 0.160.1**（session `01a160d4-…`）

- Hook 面：stderr 出现大量 `hook: SessionStart` / `UserPromptSubmit` Completed（确定性触发）。
- 模型可见 banner：模型列出的是知识页索引行 `8 knowledge pages cover this repository — …`；**未看到** `↳ memory bank` 行。ANSI `systemMessage` 在 Codex 用户可见面是否透出 **未验证**（本轮转写未捕获到该行原文）。
- MCP：`hindsight_search_knowledge_pages` / `read` 可调用；`hindsight_reflect` 返回 **401**（token 过期）。页面正文为 `Generating content...`。

### 归因结论

| 效果 | 来源 | 证据 |
|---|---|---|
| SessionStart banner 双行 + bank 名 | **确定性注入** | Claude hook_response 解析出的 `systemMessage`；`buildSeedBanner` 源码 |
| 工具指南与 credit 强制句式 | **确定性注入** | `additionalContext` + `TOOL_GUIDE` 字节 |
| 多 harness 钩子触发 | **确定性注入** | Codex stderr hook Completed；settings/hooks.json 注册 |
| 回复中是否调用 hindsight 工具 | **模型服从** | 两 harness 均调用；属指令遵循 |
| 记忆有用时是否写出 credit 行 | **模型服从** | 指令为 “CREDITING IS NOT OPTIONAL…”，运行时无消费端 validator 拒绝坏 credit |
| 本轮两会话均未写出 credit | **模型服从（正确省略）** | 页面无实质内容；Codex 明确声明无 credit；符合 “nothing useful needs no mention” |
| Codex 用户是否看到 bank 行 | **未验证** | 转写无该行原文 |

Hindsight 的「可见品牌效果」= **钩子注入 banner（确定性）+ 模型按注入指令使用工具并署名（服从）**。署名本身没有 Hindsight 侧的机械消费端校验。

---

## 问题 2：阿舟品牌锚点效果是否达成？

### 实弹合规（真实会话，机械打分）

会话（Claude Code headless，attempt-1）：

| Skill | 类型 | Session（截断） | 启动行 | 锚点 |
|---|---|---|---|---|
| `azhou-info` | Foundation | `c1927daa-…` | 合规 | `✅ 验证通过（mode=info, scope=checkout）` 合规 |
| `super-repo-pedant` | 多阶段 | `41226a0c-…` | 合规 | 五阶段 + hold 合规；未发虚假 ✅ |
| `super-llm-wiki` | 多阶段 | `524096ff-…` | 合规 | 范围锁定 + 检索完成；空 store 未发 ✅ |
| `eli5` | Foundation | `27b8bd6f-…` | **不合规** | hold 合规 |

**eli5 启动行缺陷（DEFECT-A，本任务不修）**：

```text
实际：🦊 阿舟 · 舟5 启动（mode=explain，scope=什么是 startup anchor）
合同：🦊 阿舟 · Eli5 启动（mode=explain, scope=<topic>）
问题：display name 错写为「舟5」；字段分隔用了全角「，」而非「, 」
```

打分明细：`evidence/brand-effect-audit-2026-10-22/brand-compliance-score.json`  
方法：只抽取 assistant 发射的锚点行（排除 SKILL.md 契约示例与 api-request 注入字节）；启动行对照 `scripts/check_repository.py` 的 `SKILL_BRAND_CONTRACTS` + 括号字段文法；多阶段锚点对照 `validate_execution_protocol.py` 的 `MESSAGE_PATTERNS` / brand-layer 固定前缀。

**阈值对照**：启动行 75% < 95% → **启动行阈值未达成**；成功/失败/hold 9/9 = 100% → **锚点阈值达成**。

**阿舟 vs Hindsight 的效果结构差异**（有证据）：

| | Hindsight | 阿舟（本轮） |
|---|---|---|
| 启动可见行 | 钩子注入，确定性 | **模型发射**，服从 SKILL.md/brand-layer |
| 机械消费端 | 无 credit 运行时校验 | `validate_execution_protocol` / `check-brand-startup` / 合同 gate（静态 + 协议记录） |
| 实弹启动服从 | 本轮未测模型改写 banner | 3/4 完全合规；1/4 文法+身份错误 |

### 对抗探针（消费端拒绝）

11 个故意违规样本（值内分隔符、混合文法、模板泄漏）全部被拒绝，0 漏拦。  
证据：`evidence/brand-effect-audit-2026-10-22/adversarial-probes.json`

覆盖面：

1. `validate_execution_protocol.validate_protocol` — 4/4 拒绝（含 impact 值内 `, ` 注入）
2. `check-brand-startup.check` — 4/4 拒绝
3. 记忆署名文法（按 skill-standard §3 精确形状，仓库无独立 credit CLI）— 3/3 拒绝

### 渲染矩阵

同一组锚点在三态下并排：`evidence/brand-effect-audit-2026-10-22/render/00-render-matrix.png`

| 渲染 | chars | UTF-8 bytes | whitespace tokens | CJK | emoji |
|---|---:|---:|---:|---:|---:|
| 纯文本终端 | 336 | 469 | 40 | 39 | 9 |
| Markdown 聊天 | 434 | 569 | 61 | 39 | 9 |
| 无 Unicode 降级 | 319 | 428 | 32 | 39 | 0 |

无 Unicode 降级去掉 emoji 后，`（k=v, k=v）` 结构与固定标签仍在，符合 brand-layer「可去 emoji、不得改机器字段」边界。Markdown 态因围栏/引用增加 token，结构可读。

---

## 是否达到业界最佳实践？

对照物：本机 Hindsight coding-agents 0.8.2（一手实现 + 双 harness 会话）。

| 维度 | 判定 | 支撑 |
|---|---|---|
| 启动可见性的确定性 | **部分达到** | Hindsight：钩子必发 banner。阿舟：启动靠模型发射，本轮 75% 合规，无 SessionStart 强制注入。 |
| 文法可机检性 | **达到（甚至更强）** | 阿舟有 `validate_execution_protocol`、`check-brand-startup`、合同 gate；对抗 11/11 拒绝。Hindsight credit 无对等运行时拒绝面。 |
| 记忆署名协议 | **达到（格式同构，执行靠模型）** | `skill-standard.md` §3 与 Hindsight TOOL_GUIDE 句式同构；阿舟要求无 Markdown 粗体。本轮无阿舟记忆署名实弹成功样本（wiki 空 store）。 |
| 多 harness 布线广度 | **未验证 / 不对等** | Hindsight 为十余 harness 提供 hook 构建。阿舟本轮仅 Claude Code headless 实弹。 |
| 跨渲染稳定性 | **达到（渲染矩阵）** | 三态截图 + token 计数；降级不破字段结构。 |

**综合**：相对本机 Hindsight，阿舟在**消费端机械校验与对抗拒绝**上达到或超过对照；在**启动行确定性注入**上弱于对照（模型发射 + 本轮 1/4 文法失败）。称「全面达到业界最佳实践」**证据不足**；称「锚点协议与校验面已业界同构，启动服从率未过预阈值」有证据。

## 品牌锚点效果是否达成？

| 声称 | 判定 | 证据 |
|---|---|---|
| 多阶段阶段锚点可按合同复现 | **达成（本轮样本）** | repo-pedant / llm-wiki 阶段行全合规 |
| 成功/失败/hold 分离且可机械拒绝非法文法 | **达成** | 9/9 锚点 + 11/11 探针 |
| 启动行在真实会话 ≥95% 服从 | **未达成（本轮 75%）** | eli5 身份与分隔符错误 |
| 记忆署名在真实贡献场景被写出 | **未验证** | 两 harness 记忆页无实质内容；未观察到有效 credit 发射 |
| Codex 用户可见 banner 与 Claude 同构 | **未验证** | 无 bank 行转写原文 |

## 缺陷清单（只记录，不修）

1. **DEFECT-A**：`eli5` 实弹启动行 display name「舟5」+ 全角逗号分隔（`evidence/…/brand-compliance-score.json` → sessions.eli5.startup）。
2. **DEFECT-B（观测边界）**：Codex 上 Hindsight `systemMessage` bank 行是否进入用户/模型可见面，本轮转写无法证明；若产品依赖该行跨 harness 品牌可见性，需单独捕获实验。不属阿舟 skill 缺陷。

## 未验证（禁止推断补齐）

- Hindsight 在记忆页有实质正文时，模型 credit 行的真实发射率。
- Hindsight 对坏 credit 的任何运行时拦截（实现中未见对等 validator；未做全量源码穷举）。
- 阿舟 skill 在 Codex / zcode / Kimi 上的锚点服从率。
- 交互式 TUI（非 headless）品牌体验。
- `super-caveman` 新文法（树哈希冻结，按 PR #324 设计 hold）。
- 长期服从率、多模型方差、温度敏感性。

## 证据索引

| 路径 | 内容 |
|---|---|
| `evidence/brand-effect-audit-2026-10-22/brand-compliance-score.json` | 实弹服从率与逐行打分 |
| `evidence/brand-effect-audit-2026-10-22/adversarial-probes.json` | 11 探针与拒绝原因 |
| `evidence/brand-effect-audit-2026-10-22/hindsight-injection-samples.json` | Banner / preamble 脱敏摘录 + 源码行号 |
| `evidence/brand-effect-audit-2026-10-22/transcript-digests.json` | 原始转写 sha256-16（原文 Git 外） |
| `evidence/brand-effect-audit-2026-10-22/render/` | 三态截图与 token 计数 |
| `evidence/brand-effect-audit-receipt-2026-10-22.md` | 服从率 receipt |

## 复现要点

1. 在 `6ae1f87` 工作树，用 Claude Code headless 分别触发 `azhou-info` / `super-repo-pedant` / `super-llm-wiki` / `eli5`，保留 `~/.claude/projects/<proj>/<session>.jsonl`。
2. 仅从 assistant 文本行抽取 `🦊 阿舟 · … 启动` 与阶段 emoji 行，用 `SKILL_BRAND_CONTRACTS` + `validate_execution_protocol.MESSAGE_PATTERNS` 打分。
3. 对抗样本写入临时 protocol JSON，调用 `validate_protocol`；启动行喂 `check-brand-startup.py`。
4. Hindsight：读 `~/.hindsight/coding-agents/dist/*sessionstart-hook.js`；在 Claude/Codex 各跑一次会话并解析 hook 输出 / stderr。

## 后续：S1 聊天展示层（审计后落地）

审计完成后，按维护者选择落地了 S1（blockquote + label 加粗，无 HTML 品牌色）。协议核心字节不变；`peel_chat_presentation` 与 standard 样张检查进入公开 gate。

实弹（Claude Code headless，Markdown chat）：`azhou-info` 发射了 S1 启动行，剥皮后精确还原协议核心。`super-llm-wiki` 空 store list 连协议核心广播都未发射，S1 皮无从谈起（模型服从缺口）。`super-repo-pedant` 多阶段 headless 超时，未验证。见 `evidence/brand-effect-audit-2026-10-22/s1-live-score.json`。
