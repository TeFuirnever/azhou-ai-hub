# Spec: `super-` 前缀审计 —— 忠实 skill 保留原名，改造 skill 统一加 `super-` 前缀

> Spec 日期：2026-09-08（Asia/Shanghai）
> 来源证据：15 个 canonical skill 的 `references/provenance.md` 及其锁定上游 commit / SHA-256（2026-09-08 逐个核对）；`docs/skill-standard.md`（上游改造、状态迁移、frontmatter 合同）；`docs/support-matrix.md`；`scripts/check_repository.py` 的 discovery / 路由货币 / invocation 声明检查；super-caveman 晋升记录的 reviewed blobs 约束（AGENTS.md 不变量）。
> 状态：ready-for-agent。本 spec 只定义工作，不执行修改。
> 发布：2026-09-08 已按 to-spec 流程发布为 [issue #176](https://github.com/TeFuirnever/azhou-ai-hub/issues/176)（英文，spec-of-record，标签 `ready-for-agent`）；本文件保留中文扩展细节与落地约束，实现以 issue 为准，两处冲突时先对齐再动工。

## Problem Statement

用户无法从名字判断一个 skill 是"原版能力"还是"在原版基础上调整过的能力"。`super-caveman` 用名字声明了它是 Caveman 的增强版，但 `repo-pedant`（自述为 neat-freak 的严格增强版）、`llm-wiki`（上游实现的 Python 重写）、`ci-test-reliability` 与 `prose-standard`（换栈重表达）、`lavish`（保留上游工作流外加新增 relay 模式）看起来和 `eli5`（行为句逐字保留的忠实导入）或 `ask-azhou` / `autoresearch`（零上游字节的原创包装）毫无区别。命名语义没有规则约束，会持续漂移。

## Solution

全目录采用一条命名规则：忠实保留原版能力的 skill 保留原名；能力被调整（增强、合并、重表达、换栈移植、重写）的 skill 统一加 `super-` 前缀。判定标准用户已确认为**能力改造判定**。分四步落地：先在 skill-standard 定义 fidelity 轴并把每个 skill 的证据化分类写进 provenance 记录；再逐 skill 原子改名并同步全部引用面；与 super-caveman 晋升记录 reviewed blobs 相交的那一个改名走 maintainer 批准的 promotion 流程；最后由仓库 gate 机械强制"前缀 ⟺ 分类"。

预期结果：改名 5 个（`super-repo-pedant`、`super-ci-test-reliability`、`super-prose-standard`、`super-llm-wiki`、`super-lavish`），其中两个边界案例由审计引证确认（`eli5` 预期保留原名，`lavish` 预期加前缀）；全部 Azhou 原创 skill 保留原名；`super-caveman` 已合规。

## 判定标准（fidelity 轴）

| 分类 | 定义 | 结果 |
|---|---|---|
| `original` | 无上游 skill 血缘：Azhou 原创、仅借用模式零上游字节、或包装未修改的外部运行时 | 保留原名 |
| `faithful` | 原版能力原样保留；本地新增仅限包装/交互层（身份锚点、收据、provenance、setup、边界、frontmatter 规范化） | 保留原名 |
| `adapted` | 原版能力被换栈/换语言重表达、合并、重写，或被扩展增强（在原流程上新增模式、路由、行为超集） | 加 `super-` 前缀 |

品牌锚点、收据、provenance、setup、授权 checkpoint 本身永远不构成 `adapted`；不改变原版承诺行为的输出形态约束属于包装层。

## 预登记分类（审计逐个引证确认）

**`adapted` → 改名（5 个）：**

| 现名 | 改为 | 证据要点 |
|---|---|---|
| repo-pedant | super-repo-pedant | 自述"neat-freak 的严格增强版"，兼容边界有专文 |
| ci-test-reliability | super-ci-test-reliability | 上游方法论整体换栈重表达（TypeScript/Vitest → Python 标准库） |
| prose-standard | super-prose-standard | 三个上游能力合并 + 重表达，probe 移植为 Python |
| llm-wiki | super-llm-wiki | 上游 hook/tool 实现的 Python 标准库重写，非字节拷贝 |
| lavish | super-lavish（边界，预期） | 上游工作流完整保留 + 新增 Spec Relay 整套新模式 = 能力扩展 |

**`faithful` → 保留（边界，预期 1 个）：**

- `eli5`：上游 321 字节行为句逐字保留；新增仅 topic 边界、单 artifact 输出形态、品牌、收据、provenance —— 属包装层。

**`original` → 保留（9 个）：**

- `ask-azhou`（借用 ask-matt 模式，零上游字节，路由的是本仓自己的目录）、`autoresearch`（包装未修改的 karpathy/autoresearch 环境，vendor 零上游字节）、`azhou-doctor`、`azhou-info`、`azhou-setup`、`azhou-verify`、`arch-doc`、`excalidraw-diagram`（Azhou 自维护；上游为无许可证 prior art 未分发）、`super-caveman`（已合规，仍记录分类以纳入统一 gate）。

> 对 seam 讨论时预览的修正：`autoresearch` 当时列为可能改名，但其 provenance 证明它 vendor 零上游字节、只包装外部环境，判为 `original` 保留原名；`lavish` 反向 —— 新增 relay 模式构成能力扩展，预期加前缀。两者均由审计引证确认。

## 里程碑

- **M1 —— 立规则与记录**：fidelity 轴写入 skill-standard；每个 skill 的分类 + 证据写入其 provenance 记录。不改名、不改 gate。
- **M2 —— 无耦合改名**：每个 skill 一个原子 commit（`git mv` 保留历史）：移动包目录、更新 frontmatter `name`、品牌锚点行、ask-azhou 路由图、discovery 与 invocation 声明表、双语 README、support-matrix、skill-standard 提及、第三方声明路径、benchmark 目录 + manifest + integrity 套件、tests、收据/schema 机器身份串。`llm-wiki` 的 `.azhou/llm-wiki/` 状态根随改名 commit 按标准 §2.1 迁移协议迁到新 canonical 名（先稳定 dry-run plan，同 planId 原子应用，源目录保留为具名 compatibility source，禁止 fallback read）。
- **M3 —— repo-pedant 改名（promotion 耦合）**：动手前先读最新 super-caveman 晋升记录的 reviewed blobs；凡相交编辑（AGENTS.md 中点名 `skills/repo-pedant/...` 的不变量、results bookkeeping）必须与 maintainer 批准的 promotion 流程同批落地，附新的 checked-in receipt，否则公开 gate 失败。
- **M4 —— 机械强制**：仓库 gate 新增"前缀 ⟺ 分类"检查；新 skill 引入时必须声明分类；改名残留检查（旧名只允许出现在兼容触发词、迁移源、provenance/changelog 历史）；跑完整 closeout。

## 引用面清单（每个改名 commit 必须同步）

`skills/<name>/` 目录、frontmatter `name`、`🦊 阿舟 · <Skill>` 锚点行、ask-azhou 路由图（gate 强制其覆盖全部 canonical skill）、`check_repository.py` 的 discovery/invocation 表、`README.md` 与 `README.zh-CN.md`（同一 commit）、`docs/support-matrix.md`、`docs/skill-standard.md`（含"十四个 canonical skill"等计数与点名）、`THIRD_PARTY_NOTICES.md` 与 `LICENSES/` 路径引用、`benchmarks/<skill>/` 目录与 manifest/integrity 套件、`tests/`、收据 schema 串（如 `schema_version` 内嵌名）。改名后的旧名仅允许保留为入口 description 内的兼容触发词（沿用 super-caveman 的 `/caveman` 先例）。

## Testing Decisions

- 只测外部行为：gate 对"分类/前缀不一致"的退出码、路由货币、discovery parity、品牌锚点合同（锚点文本必须匹配新名）、收据身份串、改名残留检查。
- 每个改名 commit 保持 `scripts/verify.py` 全绿（仓库政策 + 单测 + benchmark integrity + whitespace）；Windows 验证 job 保持绿（ASCII `super-` 前缀路径安全，检查即证明）。
- 迁移测试沿标准既有合同：dry-run plan 确定性、同 planId 原子应用、源目录保留、无 fallback read。
- 先例：现有 repository-gate 测试（discovery parity、路由货币、invocation 声明）、benchmark integrity 套件、promotion paired-review gates。
- 审计本身可复核：每个分类引用 provenance 记录中已锁定的上游证据；边界判定引用决定性的能力新增或逐字保留。

## Out of Scope

- 不改任何 skill 行为；不重同步上游；除名字与引用同步外不改内容；不动品牌层。
- 不改名、不触碰 Azhou 原创 skill、super-caveman 行为及其 adapter 命令面。
- GitHub label 改名、对外的改名公告。
- session-insights（#161 及后续）与其他新 skill 工作。
- Harness adapter 身份与任何模型专用打包（继续禁止）。

## Further Notes

- 命名规则是既有上游改造要求（来源、许可证、能力基线、可复现更新路径）的补充，不是替代。
- 双语 README 同步规则与 support-matrix 真实性规则适用于每个改名 commit。
- 预期终态：15 个 skill，6 个带 `super-` 前缀（super-caveman + 上表 5 个，最后一个待审计确认），9 个保留原名。
- super-caveman 的 invocation 类继续由声明表持有至下次 promotion ride 迁入 frontmatter；本 spec 不改变该安排。
