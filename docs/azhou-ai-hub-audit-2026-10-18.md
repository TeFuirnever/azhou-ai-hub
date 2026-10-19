# Azhou AI Hub 全仓代码与系统检视报告

**审查对象**：`/Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub`  
**基线提交**：`b2c6e706262be534813855d83a7accc2b1a7a2c2`  
**日期**：2026-10-18，时间均为 UTC+08:00。  
**结束时 Git 状态核对**：22:02:26。  
**性质**：只读检视、隔离复验与最小处理建议；未修改产品实现、升级依赖、发布、部署或写入真实业务数据。

## 1. 总体判断

**这是已经具备真实运行能力、明确工程约束和相当数量确定性测试的 Agent Skill 仓库，不是只有 README 的概念项目。但它还不能把“门禁通过”解释为“既定安全边界、证据有效性和自进化效果都已经成立”。**

最重要的差距不是缺少一种新架构，而是现有契约没有在所有实际入口上一致兑现：运行状态写入有边界漏洞，演化归档可丢失并发信号，演化投票及绘图评测器能接受不满足其自身要求的证据。

| 维度 | 已有证据支持的判断 | 主要差距或边界 |
|---|---|---|
| 目标 | 以可独立安装的 Skill 完成明确任务，并要求可检查产物、私有状态和受控演化；目标不是建设单体 SaaS 或无人监管平台 | 运行状态、评测及少量当前能力说明与契约不一致；验收强度不均衡 |
| 定位 | 面向使用 Agent Skills 宿主、需要代码/知识/图示/审阅等工作流的用户；Foundation Skill 明确依赖用户选择的 checkout | 安装、宿主信任、实际触发和效果是不同层次；没有全体用户价值或所有宿主当前可调用性的原始证据 |
| 设计 | 本地标准库、可携带包、显式目标、收据归属、人工批准与隔离候选等取舍合理 | 部分状态写入绕过已有安全辅助函数；跨文件事务与锁边界存在可复现问题 |
| 能力 | Wiki 正常链、Session Insights 合成聚合、Archify 真浏览器交付、Excalidraw 官方导出有本次运行证据 | 纯提示词能力仍依赖宿主/模型；未把包存在、示例通过或历史 receipt 当作全流程成功 |
| 自进化 | 反馈、候选、回归、评审、批准等机制存在；两次真实失败候选保留了拒绝记录 | Pedant gate 和信号归档有缺陷；当前材料不足以证明保留任务上的稳定收益或总体效果提升 |
| 质量 | 完整现有门禁两次通过，每次执行 597 个测试；部分现有测试确实覆盖并发冲突、身份、回滚和隐私 | 独立边界检查仍复现重要缺陷；没有全仓逐行运行覆盖率、全面依赖安全证明或新一轮跨平台/跨宿主实测 |

结论不构成发布许可，也不代表应暂停所有只读或已验证的正常功能。**应先修复状态保护与证据判定问题，再依赖这些机制进行真实演化、归档或效果背书。**

依据：`docs/skill-standard.md:1-117`、`docs/foundations.md:3-30,102-153`、本报告 V1–V9 运行记录，以及下文逐项源码位置。

## 2. 审查基线与项目事实

### 2.1 仓库、分支、约束与工作区

原目录分支为 `main`。开始和结束时的 HEAD 均为上述完整提交；没有已跟踪或暂存修改。原目录只有以下未跟踪文件，其状态保留：

```text
.zcode/plans/plan-sess_491e84d7-33b2-4002-873b-5eb75ed72c7b.md
```

这份计划被作为当前本地材料读取，不作为实现完成证明。未对它进行写入。结束时复核的是 Git 状态；没有把该文件“从头到尾字节完全不变”冒充为已经完成的哈希证明。

适用指令包括根 `AGENTS.md`、指向它的 `CLAUDE.md`、`docs/skill-standard.md` 和 `docs/worktree-policy.md`。已检查的祖先目录未发现额外 `AGENTS.md`。按仓库规则取得独立 Treehouse 工作区并确认同一 Git common directory、同一 HEAD、独立分支和干净状态。

```text
审查分支：codex/audit-20261018
审查工作区：/Users/guanxueliang/.treehouse/azhou-ai-hub-2cc7ce/8/azhou-ai-hub
lease_id：4b16e154996c44f6674abfb6c1d166d7
lease_holder：azhou-audit-20261018
取得时间：2026-10-18T21:12:01.869802+08:00
```

**工作区收尾状态**：22:02:26 的直接 Git 检查显示审查工作区干净、原目录仍只有上述未跟踪计划。随后包含更强哈希复核和租约归还的工具调用被安全检查阻止；该调用未执行，不声称完成了哈希复核或归还。租约、工作区及审查分支保留，未强制删除、重置或清理。

### 2.2 环境与执行方式

主要验证环境是 macOS 上 Python **3.14.7**、Node **24.15.0**。绘图另使用机器已经存在的 Python **3.13.13** 虚拟环境和 **Playwright 1.62.0**，核对与项目锁定版本一致，复用现有 Chromium 缓存；没有安装或升级。

运行验证由仓库外的 `audit.py` 记录，工作目录是审查工作区；大部分环境变量被清理，使用隔离 HOME、禁用字节码写入及用户 Git 配置。绘图复用的是既有解释器和浏览器依赖，执行的项目脚本仍来自审查工作区。Treehouse 提供工作区隔离，**不是安全沙箱**；所有故障注入目标均为审查目录中的合成数据。

未调用模型 API、未新建付费模型评估、未安装宿主 hook、未修改真实宿主配置、未执行 npm 发布或远程分享。

### 2.3 项目事实与验收来源

| 事实问题 | 本仓材料支持的答案 | 依据 |
|---|---|---|
| 服务谁 | 使用 Agent Skills 兼容宿主的用户，以及维护这些包的贡献者；没有证据支持更广泛用户群的价值判断 | 各 `skills/*/SKILL.md`；`docs/foundations.md:7-14` |
| 解决什么 | 知识整理、代码/文档协作、简洁输出、图示、审阅交接、会话洞察、显式安装/诊断/验证等独立任务 | 16 个正式 Skill 入口；Foundation CLI |
| 当前阶段 | 多个包已有运行实现和测试，部分是指令适配层，部分依赖外部运行时；不是所有能力同一成熟度 | 各 setup、源码、支持矩阵及本次实际产物 |
| 主要承诺 | 可携带包、明确授权、受控私有状态、证据不升格、失败不伪装成功、演化不直接改 live skill | `docs/skill-standard.md`；`GOVERNANCE.md:24-35` |
| 实际入口 | 宿主加载 `SKILL.md`；确定性任务由各包脚本执行；仓库控制面为 `scripts/azhou_hub.py`，总门禁为 `scripts/verify.py` | `docs/foundations.md:16-30`；`scripts/verify.py:26-44` |
| 验收依据 | 标准、具体 Skill 契约、测试断言、冻结 benchmark、原始输出/评审/批准及最终产物，按证据层次分别判断 | `docs/skill-standard.md`；tests、benchmarks、显式引用的本地评估记录 |

没有找到能替代这些分散契约的一份统一、完整、可执行产品 PRD；本报告不自行补全一个新目标。现有文档之间的冲突在 F08、F10、F11 中保留，而不是靠选择更好看的版本消除。

## 3. 覆盖清单及处理方式

### 3.1 全仓清单的确切含义

建立了 **1,138 个 Git 跟踪文件**的清单，记录路径、字节数、SHA-256、文本行数、类别、源码阅读范围、自动检查和运行证据。另读取了适用本地指令、未跟踪计划、显式暴露的相关配置和为复核具体结论所必需的本地评估记录。

机器清单留在用户 Mac 的：

```text
/tmp/azhou-audit-20261018-tJPQ6B/coverage.json
/tmp/azhou-audit-20261018-tJPQ6B/coverage.csv
/tmp/azhou-audit-20261018-tJPQ6B/coverage-summary.json
```

清单中的保守人工阅读记录为：**164 个文件完整显示并审读，5 个文件部分审读，969 个文件没有完整人工审读记录**。这不是代码行覆盖率，更不是“164 个文件的所有行为通过”。已运行的仓库策略按各自适用规则扫描，不能替代逐文件语义审查。

初始分类为 373 个一方/源码类文件、482 个二进制资产或 vendored 资产、143 个 vendored runtime 文件、138 个 fixture/评估记录、2 个生成或锁定文件。这是便于审查的文件分类，不是精确的版权归属统计；其中源码类还包含模板、许可证和部分参考材料。

已逐段审读主要一方可执行脚本与全部 benchmark 驱动。两个包内 `azhou_runtime_state.py` 未重复逐行读，但与已完整审读的仓库级辅助模块进行了字节等价验证。空初始化文件不作为实质代码审查重点。现有测试全部执行，测试源码重点检查关键链路和发现对应的断言；**没有把这表述成全部测试源码逐行精读**。

### 3.2 逐模块覆盖

“全读/部分/其他”只统计有记录的人工源码阅读；“其他”还可能接受了策略、哈希、测试或运行验证。

| 模块 | 文件数；全读/部分/其他 | 检视与验证落点 | 不能据此证明的部分 |
|---|---:|---|---|
| Foundation 与仓库 scripts | 8；7/0/1 | info、doctor、setup、receipt 生命周期、总门禁、运行状态辅助模块；现有真实临时目录测试与新 doctor 反例 | 新增独立安装全生命周期脚本未完成，见 V10 |
| `.github` | 16；16/0/0 | CI、发布、覆盖率、fuzz、安全扫描和 Windows 验证工作流；失败状态独立检查 | 没有触发远端 Actions、发布或签名 |
| `arch-doc` | 19；10/0/9 | 入口、生成/验证脚本、模板契约、演化及评审方法；现有测试 | 没有新模型撰写并完成人工验收的大型架构文档 |
| `archify` | 144；6/0/138 | Azhou 包装层与边界、完整 vendor manifest 校验、真实 finalize/browser-check | 未逐行审计整个第三方运行时；本次仅一个 workflow 示例 |
| `asd-ste100` | 7；3/0/4 | 指令、写作规则、确定性 linter 与现有回归 | 不证明自然语言改写的全部语义，也不是完整标准认证 |
| `ask-azhou` | 4；3/0/1 | 路由入口、索引生成、未路由记录脚本和现有测试 | 未在每一种真实宿主运行路由到下游交付 |
| `autoresearch` | 3；2/0/1 | 入口与 setup，外部 checkout、GPU、运行批准边界 | 未运行 GPU 实验；不证明训练效果 |
| `azhou-info` | 3；1/0/2 | Skill 入口到共享 Foundation CLI | 独立安装入口不等于内置独立 CLI |
| `azhou-doctor` | 4；2/0/2 | 入口、迁移契约与共享实现；第三方误报复验 | 不证明宿主信任、hook 已激活或浏览器依赖全部就绪 |
| `azhou-setup` | 3；1/0/2 | 入口和共享实现；计划与生命周期参数交叉检查 | 新独立生命周期复验受阻；不代表现有测试未运行 |
| `azhou-verify` | 4；2/0/2 | 入口、gate report 检查器和总门禁 | 不把结构门禁解释为所有模型效果验证 |
| `eli5` | 4；2/0/2 | 入口与受众检查脚本、现有测试 | 未重新生成并评估一份模型解释产物 |
| `excalidraw-diagram` | 507；19/0/488 | 一方图形辅助/转换/导出/检查脚本；官方 PNG/SVG 导出；评测收据反例 | 不穷举字体、库图标、所有图型、CJK 或视觉效果 |
| `session-insights` | 5；4/0/1 | 入口、完整聚合/报告实现和契约；冷/热缓存与错误缓存、输出边界复验 | 没有扫描用户真实全部会话；zcode 不受支持仍保留 hold |
| `super-caveman` | 25；12/0/13 | 入口、压缩保护、三个适配器及重要引用；公开与私有证据门禁、既有真实尝试 | 没有新宿主信任/触发验收、盲保留集或成本收益实验 |
| `super-lavish` | 8；6/0/2 | relay 状态、反馈、版本、账本、授权、轮询和外部运行时契约；现有测试 | 未下载/启动外部 Lavish 浏览器评审与轮询 |
| `super-llm-wiki` | 11；7/0/4 | CLI、MCP、适配器、数据/归档/迁移规则；正常与失败链复验 | 不把 MCP 正常函数存在当成完整协议健壮性 |
| `super-repo-pedant` | 29；19/0/10 | 收尾、知识清单、历史采集、证据验证、迁移、演化脚本与契约；独立边界/竞态反例 | 未证明真实生产演化长期变好 |
| `tests` | 50；3/4/43 | 两次完整发现和执行；关键断言及已有故障注入抽查 | 无全部断言精读或运行行覆盖率 |
| `benchmarks` | 157；11/0/146 | 五个驱动审读，四个总门禁 benchmark 组运行，关键冻结记录回放 | fixtures 不能变成模型效果样本；不全面重跑所有历史实验 |
| `docs` / `evidence` | 43 / 41；15/0/28 与 1/0/40 | 当前关键规范、设计和已选真实失败；历史材料作为线索 | 其余历史报告未逐篇核真，不继承其中“已完成”结论 |

品牌资产、字体、压缩库、依赖缓存、生成图标目录和上游快照主要做清单、完整性、来源边界检查。Archify 的 144 文件 manifest 校验通过；这证明与仓内锁定清单一致，不证明全部第三方语义安全。依赖环境、宿主私人状态、被忽略的任意生成目录和整台电脑不属于本次递归全面审计范围。

## 4. 关键链路与声明—实现—验证对应

### 4.1 实际责任边界

**安装链**：Skill 解析显式 checkout/target → Foundation CLI 计划 → 人工检查 → 带计划摘要的 setup → 锁内重验 → 收据及对象身份 → 后续 repair/migrate/uninstall 的归属复核。收据摘要是完整性检查而不是签名，项目自己对此有明确限定。主要设计可保留；F08、F11 是诊断归属和指令一致性问题，不是要求重写安装器。（`docs/foundations.md:44-153`；`scripts/azhou_hub.py`；`tests/test_azhou_hub.py:147-245,953-1084,1234-1288,1378-1417`）

**知识链**：显式 root → 私有 Wiki store → 锁 → 页面/索引/日志 → 查询与 lint；archive 还必须同步页面生命周期和冻结 hash。正常链成立，F05 的问题恰在页面与 archive-lock 的交接；F06 则在 MCP 参数进入共享核心前。（`skills/super-llm-wiki/scripts/llm_wiki.py:576-612`；`references/schema.md:18,42-63`）

**绘图链**：输入事实/场景 → 确定性语义与几何检查 → 官方浏览器渲染/导出 → 检查冻结产物 → 评测汇总。前半段有真实运行，后半段的证据判定有 F04；“能画出来”和“评测器能正确拒绝坏收据”分别验收。

**演化链**：历史是数据而非指令 → 类型化/摘要化信号 → 阈值聚合 → 隔离候选 → 回归与配对评审 → 人工 exact-diff 批准 → 显式仓库变更。项目并未承诺后台自动改 live skill；F01–F03 发生在信号存储、归档和 gate，不能用末端仍需人工来否认前端缺陷。（`skills/super-repo-pedant/references/history-evolution.md:52-143`）

| 声明 | 实现路径 | 本次验证 | 实际结果 |
|---|---|---|---|
| 完整公开仓库门禁可复现 | `scripts/verify.py:26-44` | V1 | 8 个门禁通过；597 测试；并非所有行为都验证 |
| 原始批准能绑定当前演化树 | Caveman benchmark + Git 外部记录 | V5 | 仓库定义的认证门禁通过；不是新一轮效果证明 |
| 运行状态留在授权项目且默认私有 | 状态辅助模块及各模块写入点 | V2、V3 | 部分实际写入绕过约束，F01 |
| 归档保留未转换及并发信号 | Pedant `cmd_archive` | V2 | 可丢失已成功追加的信号，F02 |
| 晋升需要奇数评委多数 | Pedant `validate_promotion` | V2 | 1 票 candidate + 2 票 tie 仍通过，F03 |
| Wiki 能查询并冻结决策 | Wiki CLI | V3 | 正常链通过；损坏锁下发生部分写入，F05 |
| MCP 错误按请求隔离 | Wiki stdio server | V3 | 非法参数导致进程退出；文件名契约不一致，F06 |
| 缓存坏掉只损失性能 | Session Insights 聚合 | V3 | 坏 JSON 有处理；合法 JSON 的坏 entry 可崩溃，F07 |
| Archify 真浏览器交付 | `bin/archify.mjs finalize` | V4 | validate/deliver/check/browser-check 通过；视觉审查未请求 |
| Excalidraw 官方导出 | render 与 export-official-svg | V7、V8 | 一个英语参考场景 PNG/SVG 成功并查看了 PNG |
| 绘图首轮可用必须有有效视觉结论 | benchmark verify/report | V9 | 矛盾收据、第二次尝试及多余案例可进入成功统计，F04 |

## 5. 运行验证记录

所有 V 编号均绑定本报告完整基线提交。时间为日志记录的完成时间；耗时是本机单次墙钟时间，不是性能基准。

| 编号 / 日志名 | 完成时间；耗时 | 命令及结果 | 证据边界 |
|---|---|---|---|
| V1 `baseline-verify` | 21:15:24；62.610s | `python scripts/verify.py --print-summary`，exit 0，597 tests OK，8 gates passed | 现有测试通过，不等于独立反例通过 |
| V2 `independent-contract-probes` | 21:19:49；0.812s | `python A/repro_evolution.py`，记录 7 个不满足预期的边界场景 | 包括合成 symlink、权限、投票、竞态、doctor；hold 子项按契约缺口解释 |
| V3 `independent-runtime-probes` | 21:30:08；0.817s | `python A/repro_runtime.py`，2 个正常场景通过、7 个边界场景不满足预期 | 全为合成存储；Windows 项是 shell 状态传播复现，不是新 Windows runner |
| V4 `archify-finalize` | 21:34:34；1.978s | 真实 finalize 浏览器链 exit 0 | 一个 workflow 示例；关闭更新检查；没有人工视觉 pass |
| V5 `promotion-replay` | 21:40:37；74.375s | 带两个既有外部记录运行 `verify.py --promotion-evidence --print-summary`，exit 0，597 tests OK | 原批准回放，不是新批准或新模型效果实验 |
| V6 `excalidraw-runtime` | 21:40:07；0.397s | 核对现有解释器、Playwright 1.62.0、浏览器缓存存在，exit 0 | 一次探测，不单独用其证明渲染成功 |
| V7 `excalidraw-render` | 21:42:43；1.193s | 官方 render 参考架构场景，exit 0，生成 PNG | 固定参考输入，不是模型生成成功率 |
| V8 `excalidraw-official-export` | 21:43:11；1.702s | 官方导出 SVG 和 PNG，exit 0 | 实际查看 PNG，Client→Gateway→Service→Database 可读；未穷举其他字体/图型 |
| V9 `independent-evidence-gate-probes` | 21:58:35；0.407s | `python A/repro_evidence_gate.py`，4 个矛盾/非法证据场景均未被正确拒绝 | 只变更一次性收据输入，不改生产代码、不宣称原图有视觉问题 |
| V10 独立生命周期复验 | 21:42:41、21:43:09、21:43:28 | 两次实验脚本因错误 receipt 路径/缺少 planId 退出 1；独立 dry-run 正确拒绝越界 receipt | 是审查脚本问题和正常拒绝，不计产品缺陷；修正后的整链请求被工具拦截，未执行 |

`A` 是 `/tmp/azhou-audit-20261018-tJPQ6B`。V2、V3、V9 的顶层 runner **exit 0 仅表示反例收集完成**；产品行为是否满足预期以各条 `contract_met` 为准。不能把 runner 的成功状态再次误读为所有反例通过。

独立场景的预期在执行产品命令前写入 `repro-expectations.json`、`runtime-expectations.json` 和 `evidence-gate-expectations.json`。它们分别依据已存在的标准、模块契约、协议描述及 benchmark 自身文档；不是单纯照抄当前实现。竞态实验使用受控调用时序和另一个真实 CLI 追加进程；没有修改仓库文件让结果成立。

### 5.1 明确未完成的验证

代码图工具读取项目列表持续无响应，没有可用图结果；停止请求被工具安全检查阻止，未最终确认该查询进程已退出。继续采用已完成的源码、调用点和测试交叉检查。一次更广的 AST/JSON/Node 扫描请求被拦截，**未执行，不计入覆盖**。没有新增全仓 lint/type-check 配置，也没有通过安装新工具改变基线。

未触发新的远端 Windows/Linux CI、实际 release/signature 或宿主 hook 信任/加载验收。现有 Windows receipt 是历史证据，不能替代当前提交的新运行。

没有启动 Lavish 外部 npm/browser/poll、Autoresearch GPU 实验或所有 Skill 的新模型端到端执行。前者涉及未启用外部运行时和真实交互条件，后者缺少本次适用 GPU 环境及运行批准；这些局部缺口不影响已完成的一方状态/验证器审查。

本次无第二名独立审查者。重要发现采用不同于既有成功测试的合成反例、状态读回、独立不变量、错误输入及受控竞态复核，不以多个模型投票代替事实。

## 6. 按影响排序的发现

优先级含义：**P1** 是在依赖相应机制保护真实状态或判定演化/评测成功前应处理；**P2** 是有明确触发条件和用户后果的局部正确性/可靠性问题；**P3** 是已证实的低风险指令一致性问题。它们不是事故概率或安全认证等级。

### F01 — P1｜部分私有运行状态允许越界写入，且未落实私有权限

**证据状态：已复现缺陷。** 项目承诺 `.azhou/<skill>` 状态约束在授权项目内、拒绝 symlink、目录 0700、文件 0600（`docs/skill-standard.md:34-39`）。但 Pedant 的 root 检查不覆盖后续所有 leaf/子目录写入，Session Insights 的默认报告路径也未执行同等级检查。

**位置**：`skills/super-repo-pedant/scripts/manage_evolution.py:95-112,159-171,200-204,247-297`；`skills/session-insights/scripts/session_insights.py:172-197,859-868,1099-1100`。

**触发与后果**：把合成项目中的 `signals.jsonl` 链接到合成项目外的 sentinel，追加成功且外部文件增长；把 `candidates/` 链接到外部目录，候选创建在外部；把 `.azhou/session-insights` 链接到外部目录，默认报告仍成功写入。umask 022 下相关状态目录为 0755、文件为 0644，而不是契约要求的私有权限。触发要求调用者具有对应文件系统权限及项目状态可被预置；本次没有利用真实敏感文件，不声称远程攻击已发生。

**复核**：V2 `signal_leaf_symlink`、`candidate_parent_symlink`、`private_permissions`；V3 `session_default_namespace`、`session_private_permissions`。目标均在 A 内；查看 `outside_changed`、`outside_created`、`outside_files` 与 mode 字段。

**最小动作与验收**：在实际写入端复用仓内已有安全辅助逻辑，不只验证根路径；父链和叶节点都检查，新建私有权限不依赖 umask。上述 symlink 场景必须拒绝且外部字节不变；umask 022 下仍得到 0700/0600。保留“用户显式选择的交付物路径”和“默认私有状态路径”的区别，不把一切导出都限制回项目。

### F02 — P1｜归档会丢失已经成功追加的并发演化信号

**证据状态：已复现缺陷。** `history-evolution.md:93-101` 要求只归档已转换批次，失败保留信号。当前归档先读取 live 快照，发布 archive 后再以旧快照重写 live；它没有与追加操作共享覆盖整个事务的互斥边界。

**位置**：`skills/super-repo-pedant/scripts/manage_evolution.py:159-171,350-406`，尤其读快照与 `392-398` 的归档发布/live 重写。

**触发与后果**：归档已读两个信号之后，另一个真实 CLI 成功追加第三个，随后归档完成；结果 archive 只有旧两个、live 为空，第三个在两处均不存在。不是“可能有竞态”的静态猜测，而是可调度复现的确认写入丢失。

**复核**：V2 `concurrent_archive`：`append_returncode=0`、`appended_signal_preserved=false`。独立断言以所有已确认 signal ID 的保存为准；没有改实现文件。

**最小动作与验收**：追加与归档使用同一事务锁，覆盖快照读取、校验、归档与 live 替换；不需要引入数据库。固定本次交错时序以及归档失败时序，断言所有已确认 ID 恰好保留在 live 或 archive，失败不清空原批次。

### F03 — P1｜演化 gate 把“一票胜过零票”误当三人多数；hold 契约没有完整落地

**证据状态：多数票问题已复现；hold 为源码/契约直接证实的缺口。** 演化契约要求奇数独立评委、多数偏好 candidate、无未决问题和 exact-diff 人工批准。实现以 candidate 票数大于 baseline 票数为核心判据，未要求超过全部评委的一半。

**位置**：`skills/super-repo-pedant/scripts/manage_evolution.py:409-464`，关键比较在 `454` 附近；`references/history-evolution.md:111-129`；`references/evolution-contract.md` 评估条款；`assets/evolution-evaluation.schema.json`。

**触发与后果**：三人投票 `candidate / tie / tie`，其他条件满足，输出 `promotable: true`。这只有一名评委支持，不满足三人多数。另一个合成评估加入 unresolved hold 后也仍通过，但该字段并不是 schema 已承诺支持的合法控制面；准确结论是“契约说要排除未决项，schema/validator 未形成对应机制”，不是“绕过了已实现的 hold 校验”。

**复核**：V2 `tie_majority` 与 `pending_holds`。当前 gate 仍需人工批准且不会自行应用 diff，因此不把它扩大为全自动恶意修改漏洞。Caveman 自己的配对评审实现有较强约束，不应把 Pedant 缺陷外推到所有门禁。

**最小动作与验收**：多数定义为支持票超过有效评委总数的一半，明确 tie 处理；保留独立性、顺序反转、安全审查及人工批准。1/3 必须拒绝、2/3 才满足票数条件。对未决项选择明确字段/校验或收紧文档，不允许含糊的“无 hold”承诺。

### F04 — P1｜绘图评测器和汇总器能把不合格证据升级为成功

**证据状态：已复现缺陷。** 这是证据判定问题，不是本次参考图实际有视觉缺陷。评测器自己的文档要求具名视觉通过且无 defects，矩阵要求每个规定案例恰好一次 attempt-1（`benchmarks/excalidraw-diagram/ordinary-model-floor/benchmark.py:11-19,31-35`）。

**位置**：同文件 `140-166`、`248-277`。单项只检查视觉 status/reviewer，汇总又用更弱条件自行计算；矩阵判断使用集合包含关系且未验证 attempt。

**触发与后果**：V9 四种独立反例全部成立：有具名 `passed` 却存在缺陷；有 `passed` 却存在未解决 hold；缺少 reviewer 的 receipt 被 verify 拒绝后仍被 report 计为可用；五个规定案例全部 attempt 2，再加一个未知案例，汇总却输出 `cases=5, receipts=6, firstPassUsable=6, evidenceEligible=true`。

**复核**：`repro_evidence_gate.py` 与 `repro-evidence-gate-results.json`。保持场景几何、语义不变，只替换临时收据输入；直接对比 verify 与 report 的结果。现有 `tests/test_excalidraw_benchmark.py` 对 passed/skipped 的覆盖不能发现这些矛盾形态。

**最小动作与验收**：共用同一成功判据；具名 reviewer、零 defects、零未决 hold 必须一致，report 不得将失败 receipt 升格。规定案例集合必须相等，每个恰好一条 attempt 1；拒绝未知、重复、缺失和后续尝试。上述四个输入分别变为失败或不具备证据资格，正常与明确 hold fixture 保持原语义。

### F05 — P2｜Wiki 归档遇到坏锁时，命令失败但页面已被改成 archived

**证据状态：已复现缺陷。** 冻结行为需要页面生命周期和 `.archive-lock.json` 哈希共同成立，不能只改其中一半。

**位置**：`skills/super-llm-wiki/scripts/llm_wiki.py:576-612`，页面写入在读取/验证 archive-lock 之前；`references/schema.md:42-48`。

**触发与后果**：对 implemented 决策页预置合法 JSON 但结构不合法的锁 `{"entries": []}`，执行 archive。命令退出 2，页面却已变为 archived，没有有效冻结项，receipt 的 changes 也没有如实反映已发生写入；直接重试仍失败。现有 lint 能发现不一致，schema 文档也有恢复到 implemented 再归档的人工恢复路径，因此不是“无法恢复的数据永久丢失”。

**复核**：V3 `wiki_failed_archive_state` 对操作前后字节、生命周期、返回值和重试进行独立检查。

**最小动作与验收**：在任何页面写入之前完整验证现有锁及拟写入状态；若跨文件提交仍可能部分完成，就准确报告实际 changes 与恢复步骤。坏锁场景必须在修改前失败；正常 archive 和冻结哈希校验继续通过。

### F06 — P2｜MCP 单个错误参数会终止 stdio 服务；archive 文件名契约不成立

**证据状态：已复现缺陷。** 共享 CLI 核心不能替代 MCP 入口的类型检查和调用隔离。

**位置**：`skills/super-llm-wiki/scripts/llm_wiki_mcp.py:155,254,379-390,439`。archive schema 描述允许页文件名，实际却按标题处理；参数检查存在未捕获的类型错误。

**触发与后果**：在同一 stdin 流发送 initialize、`wiki_ingest` 的 `confidence: []`、ping，进程在错误调用处退出 1，后续 ping 没有响应。对真实存在的 `audit-decision.md` 使用 archive 的 page 文件名参数，返回 `page_not_found`，标题调用却可正常归档。

**复核**：V3 `wiki_bad_argument_isolation`、`wiki_archive_filename`。这里未使用最新协议的外部规范作额外要求，依据是本仓自己公布的接口和持续 stdio 服务行为。

**最小动作与验收**：逐请求验证类型，错误调用返回结构化错误但不使下一条正常请求失效；统一文件名/标题查找或收窄 schema。相同消息序列必须收到错误响应及后续 ping，文件名和标题接受范围与公布契约一致。

### F07 — P2｜Session Insights 的合法 JSON 坏缓存导致聚合崩溃

**证据状态：已复现缺陷。** 缓存契约是可丢弃、坏缓存回退源扫描，不应让缓存变成可靠性依赖。

**位置**：`skills/session-insights/scripts/session_insights.py:172-181,217-225,599`；`references/report-contract.md:40-46`。现有相关测试验证了损坏 JSON 的回退，但不充分验证每个已命中 entry 的结构。

**触发与后果**：保留匹配的 mtime/size，将 metadata 改为 `{}`。缓存外层仍可解码，命中后读取 `malformed_lines` 触发 KeyError，聚合退出 1。正常 cold/warm 合成结果一致，源会话没有变化，因此问题限于缓存 entry 的信任边界。

**复核**：V3 `session_cache_shape_recovery`，并与 `session_golden_and_cache` 正向控制对照。

**最小动作与验收**：命中前验证实际消费字段的类型和必要键，不合法即 cache miss；不要只加特定 KeyError 吞错。空 metadata、字段缺失、字段类型错误均应重新扫描并产生与冷运行一致结果，输入文件保持不变。

### F08 — P2｜Doctor 把合法第三方 Skill 和现存 hook 误报为 Azhou 更名残留

**证据状态：已复现缺陷，并存在跨文档契约冲突。** 独立 Skill root 可以包含第三方包，但迁移检查将“不是当前 Azhou canonical name”直接当作残留/陈旧路径。

**位置**：`scripts/azhou_hub.py:1367-1421`，尤其非 canonical 名称及配置路径判断；`skills/azhou-doctor/references/host-migration.md:7-18,29-39`。该迁移文档本身也描述了过宽扫描规则，不能只改实现而保留错误用户预期。

**触发与后果**：合成 host 中存在合法的 `tdd/SKILL.md` 及真实存在的 `skills/tdd/scripts/notice.py` hook，doctor 仍返回失败。用户可能因此对无问题的第三方安装做不必要迁移。Doctor 保持只读，本次没有删除或改写任何 host 文件。

**复核**：V2 `foreign_skill_doctor` 同时检查 hook_exists 和 `host_migration` 的错误结论。

**最小动作与验收**：按已知旧名→新名、归属或确实失效的引用判断，不以 canonical 集合的补集判断错误。合法第三方包必须无迁移误报；已知 Azhou 旧路径仍应被发现。保留只读诊断和显式操作者迁移。

### F09 — P2｜Windows 完整流程收据工作流会吞掉检查失败的退出码

**证据状态：源码直接证实，并由独立 shell 负控复现。** 不是新的 Windows runner 运行结果。

**位置**：`.github/workflows/windows-full-flow.yml:47,60,74,87,99` 的 `command | tee ... || echo ... | tee -a ...` 形式。

**触发与后果**：被测命令返回非零，失败处理只打印记录且最终退出 0；步骤状态可显示成功，尽管日志含 `exit=1`。V3 用 `false` 代替被测命令，在相同 `bash -eo pipefail` 结构下得到 exit 0，证明状态传播问题。

**边界**：主要 `.github/workflows/ci.yml:109-114,132-137` 仍有正常 mandatory gate 与聚合检查；没有证据说主 CI 整体可绕过，也没有证据否定历史 Windows 成功日志本身。

**最小动作与验收**：日志可以始终保存，但必须保留并传播原失败码；上传收据采用始终执行的独立步骤。注入失败时对应检查及工作流失败，日志仍可获得；成功输入保持成功。

### F10 — P2｜Super Caveman 当前能力说明与当前绑定评估的实验身份未充分区分

**证据状态：源码/记录直接证实的说明与证据绑定问题；不是“历史实验造假”的判断。** README 的能力介绍仍以 Codex、19/19、44 条判据及三票配对优势描述效果；当前 manifest/summary 已有 superseded 与 rebind 关系，而当前批准所对应的结果记录使用 zcode/GLM 5.3 Flash，并包含 invariance 比较。

**位置**：`README.md:95`、`README.zh-CN.md:95`、`docs/support-matrix.md:30`；`benchmarks/super-caveman/manifest.json:81`；`results/revision-a726d695-attempt-1-summary.json:3`；`results/revision-8f493670-attempt-1-summary.json:102-144`。后者位于同一 benchmark 目录，包含 harness、paired_status 及相同 baseline/candidate 输出摘要。

**复核与后果**：V5 证明当前外部批准和评审可以通过仓库自己的绑定检查；但不把这种重新绑定/invariance 解释成当前树又完成了“新 Codex 三票胜出”的效果实验。历史 Codex 结果可能有效，本次没有否定它；问题是用户难以从当前能力说明区分历史实验、等价再绑定和当前运行边界。

**最小动作与验收**：文档明确列出实验日期/提交、宿主/模型、任务数、评审方式，以及是新比较还是等价验证。当前状态字段与 manifest/有效 summary 对应；历史优势保留在其原时间和版本范围内。没有新证据，不新增“当前更好”的结论。

### F11 — P3｜部分生效指令与真实 CLI/安装路径不一致

**证据状态：源码/契约直接证实；未完成独立执行复现。** `azhou-setup` 的工作流先列 setup、repair、migrate、uninstall，然后统一要求追加 `--apply --plan-id`，而后面三种命令的 parser 并不支持 `--plan-id`。

**位置**：`skills/azhou-setup/SKILL.md:29-35`；`scripts/azhou_hub.py:1446-1458`；与此相比，`docs/foundations.md:116-133` 给出了不带该参数的正确生命周期命令。另外 `skills/super-lavish/references/artifact-mode.md:68` 仍将安装目录称为 `skills/lavish/`，与当前 canonical 包名不一致。

**后果与边界**：忠实按提示词追加参数会被 argparse 拒绝；跟随旧目录会找不到 helper。这不是授权绕过，也不是需要扩展新 CLI 能力的理由。新增安装全流程脚本未完成，不能将其失败当成本项运行证据。

**最小动作与验收**：按实际命令分别书写步骤，修正 canonical 路径，对公布命令形状做解析/帮助契约测试；保留 receipt/ownership/drift 的现有安全检查，不为让文档示例通过而扩张实现权限。

## 7. 自进化：机制、真实回放与效果限度

### 7.1 机制存在到哪一步

项目允许改变 instructions、references、templates 或确定性脚本，但要求先有失败证据与回归、隔离 candidate、评审、人工 exact-diff 批准；正常回退是显式仓库变更，而不是后台自己撤销 live skill。知识新增、使用计数或健康趋势只是线索，不自动成为推广权。（`GOVERNANCE.md:33-35`；`skills/super-repo-pedant/references/history-evolution.md:103-143`；`skills/excalidraw-diagram/references/evolution-contract.md:18-43`）

本次没有把“没有自动写代码/发布”列为缺陷。真正需要修复的是 F01–F04 这类已经声明要负责的状态和判定环节。

### 7.2 已有真实变更记录

只读取本仓明确引用的本地批准目录和具体评估尝试，不普查用户全部历史。原始私有批准、评委输入和会话不附在可下载报告中；本报告保留版本、聚合及必要证据位置。

本地证据根：

```text
/Users/guanxueliang/.local/share/azhou-ai-hub/super-caveman-approvals/
```

| 真实尝试 | 观察到的结果 | 可支持的结论 |
|---|---|---|
| `rides/revision-03e62944/attempt-1-summary.json` | 19 个任务、44 条判据，17/19；host-plan-tool-state 和 uncertainty 未过；记录了运行条件修正；未进入有效晋升，拒绝 | 项目能保留真实失败并拒绝候选；不能把早期工具条件不等的尝试当公平效果比较 |
| `rides/revision-12b5552a/attempt-1-summary.json` | 19 个任务、44 条判据，18/19；host-plan-tool-state 仍失败；开发探针通过不等于真实任务通过；再次拒绝 | 修复后的局部改善线索存在，但没有达到既定验收，拒绝合理 |
| 当前批准再绑定 `revision-8f493670` | 私有批准/评审回放与当前树绑定通过 | 完整性及批准链可通过当前仓库门禁，不是新增泛化收益证明 |

对上述两次真实失败已查看具体 `host-plan-tool-state.response.txt` 等选择性原始输出，它们支持关键失败判定；未逐条人工重判全部 19 个任务及所有评委记录。

### 7.3 不能证明的部分

这不是未参与优化的盲保留任务集；每个所列尝试主要是一轮生产模型输出，三位评委不是三次独立生产模型重复。两次尝试的提示/工具条件有变化，不能直接把 17→18 解释为统计可靠的版本收益。44 条判据也不是 44 个独立任务。

没有足够的重复次数、波动分布、可比 token/耗时费用和长期退化数据来证明“总体越来越好”或“节省了多少成本”。保留失败、拒绝候选和固定 exact diff 是值得保留的机制证据；把这些当成效果成立则超出了证据。

最小后续不是建设完整评估平台：先修 gate；今后确需提出提升主张时，固定少量已有未参与修改的任务、相同条件和成功标准，保留失败、适量重复并记代价即可。本次不启动该新实验。

## 8. 应保留的合理设计与取舍

**Foundation 的显式归属与保守生命周期**：target、source digest、对象身份、receipt、非覆盖式冲突处理及不支持 force，匹配本仓规模；现有多项故障注入测试真实验证过这些边界。不因为某个提示词参数错误就整体重写安装机制。

**压缩的恢复证据与冲突保留**：`super-caveman` 不只检查字符串短了多少，还保留受保护结构、校验备份、handoff 及外部并发写入冲突，明确 finalize 删除恢复证据需单独批准。可保留这种显式成本，而不是将它判成“代码太多”。（`skills/super-caveman/references/compression.md:28-56`）

**Relay 的乐观版本与可见反馈账本**：适合一个可携带 HTML 交接文件。它明确不是多用户数据库；现有 stale revision 和 ledger mismatch 测试具有实际意义。本次未将缺少网络锁服务视为缺陷。（`skills/super-lavish/references/setup.md:35-37`；`tests/test_super_lavish_relay_state.py:240-334`）

**Wiki 自动 hook 不注入任意页面正文**：自动上下文只输出一方说明与受约束元数据，原始页面内容留给显式 context 命令，降低项目可控文本进入控制通道的风险。这与 archive 事务问题是两件事。（`skills/super-llm-wiki/references/setup.md:60-70`）

**公开验证与私有批准分层**：普通贡献者能运行公开 gate，发布/维护者另验证 Git 外部批准。不能把缺少私有记录误判成公开包不可用，也不能把公开通过当成已认证原始批准。（`docs/foundations.md:29-30`）

**来源与能力边界的诚实保留**：第三方快照和运行包分离；未授权/无许可的上游材料不随意拷贝；Autoresearch 只是用户持有 checkout 的包装；不支持的 zcode 洞察保留 unsupported。未为增加“完整度”要求引入不必要依赖、兼容层或自动化。

## 9. 有限处理顺序与验收

第一批针对真实状态与证据可信度：F01 的写入保护、F02 的并发保存、F03 的多数/未决状态、F04 的单项与汇总判据。先把本次合成场景转成独立失败断言，确认在当前实现上确实失败，再作最小修复；不能仅增加一个“成功 receipt 存在”的测试。

第二批针对局部失败恢复和调用行为：F05 的归档前验证/真实变更报告、F06 的 MCP 请求隔离和实体解析、F07 的逐 entry 缓存回退。验收既检查非零/错误响应，也检查原状态、下一条请求与冷运行结果。

第三批针对操作者信号：F08 第三方归属判定、F09 失败码传播、F10 当前实验身份、F11 命令及路径同步。不要借此进行产品重新定位、全库重构、依赖升级或部署。

每项修复除对应独立反例外，再运行本仓已有 `python scripts/verify.py --print-summary`。触及 Super Caveman 已批准路径时，遵守已有 exact-diff 批准门禁，不修改证据来强行过门。未授权的真实安装、删除、发布、模型调用及私有数据分享仍然不执行。

## 10. 复核路径、原始命令及证据保管

### 10.1 Mac 上的完整审查记录

```text
A=/tmp/azhou-audit-20261018-tJPQ6B

A/baseline.json                         版本、环境、租约
A/baseline-head.txt
A/baseline-status.txt
A/tracked-files.zlist
A/coverage.json                        逐文件 SHA-256 和覆盖
A/coverage.csv
A/coverage-summary.json
A/commands.jsonl                       实际命令、时间、退出码、耗时、HEAD
A/logs/read-*.txt                       带行号源码阅读记录
A/logs/baseline-verify.log
A/logs/promotion-replay.log
A/logs/independent-contract-probes.log
A/logs/independent-runtime-probes.log
A/logs/independent-evidence-gate-probes.log
A/repro_evolution.py
A/repro_runtime.py
A/repro_evidence_gate.py
A/repro-*-results.json                  实际各条反例结果
A/*expectations.json                   运行前的预期
A/archify/workflow.html                 浏览器交付产物
A/archify/browser/                      浏览器/交付检查记录
A/excalidraw/reference.png
A/excalidraw/reference.svg
A/excalidraw/reference.official.png
```

这些是用户 Mac 路径，不是 ChatGPT sandbox 下载链接。`/tmp` 不是长期归档位置；本次未擅自将私有运行记录复制到仓库或公开托管位置。完整逐文件记录保留在这里，可下载报告只携带结论和明确引用，不打包字体、私人原始批准或会话正文。

### 10.2 实际执行的主要命令

下面使用缩写显示已执行命令；`commands.jsonl` 保存没有缩写的真实 argv。所有命令从审查工作区运行，经 `audit.py` 使用隔离环境并记录。

```bash
A=/tmp/azhou-audit-20261018-tJPQ6B
O=/Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub
P=/Users/guanxueliang/.local/share/azhou-ai-hub/super-caveman-approvals

python scripts/verify.py --print-summary

python "$A/repro_evolution.py"
python "$A/repro_runtime.py"
python "$A/repro_evidence_gate.py"

env ARCHIFY_UPDATE_CHECK_DISABLED=1 \
  node skills/archify/bin/archify.mjs finalize workflow \
  skills/archify/examples/agent-tool-call.workflow.json \
  "$A/archify/workflow.html" --quality showcase --json \
  --out-dir "$A/archify/browser"

env SUPER_CAVEMAN_APPROVAL_RECORD="$P/raw-approval-20261006T141525Z.json" \
  SUPER_CAVEMAN_REVIEW_RECORD="$P/revision-8f493670-review-record-release-rebind.json" \
  python scripts/verify.py --promotion-evidence --print-summary

env PLAYWRIGHT_BROWSERS_PATH=/Users/guanxueliang/Library/Caches/ms-playwright \
  "$O/skills/excalidraw-diagram/references/.venv/bin/python" \
  skills/excalidraw-diagram/references/render_excalidraw.py \
  benchmarks/excalidraw-diagram/ordinary-model-floor/fixtures/reference/reference.architecture.excalidraw \
  --output "$A/excalidraw/reference.png"

env PLAYWRIGHT_BROWSERS_PATH=/Users/guanxueliang/Library/Caches/ms-playwright \
  "$O/skills/excalidraw-diagram/references/.venv/bin/python" \
  skills/excalidraw-diagram/scripts/export-official-svg.py \
  benchmarks/excalidraw-diagram/ordinary-model-floor/fixtures/reference/reference.architecture.excalidraw \
  "$A/excalidraw/reference.svg" --png "$A/excalidraw/reference.official.png"
```

三个独立反例脚本读取 A 中记录的 worktree 路径和基线，并在 A 内新建合成输入；复核前应确认该工作区仍为所述提交。`repro_flows.py` 是未完成的安装实验脚本，其两次失败日志保留用于审计过程透明，**不将它列作成功的安装复现入口**。

### 10.3 完成与保留事项

本次已完成全仓跟踪文件覆盖登记、主要一方执行代码与关键契约审读、现有完整门禁、可执行的主要风险反例、两条真实浏览器/导出路径、六个维度判断和逐项最小建议。未把抽样源码阅读、fixture、原始批准认证或收据文字升级为全面能力/效果通过。

保留的具体未完成项为：独立安装整链与部分视觉捕获辅助检查受工具拦截、代码图不可用、跨 OS/宿主/GPU/外部交互未新跑、长期泛化收益无足够证据，以及租约未归还。结束时已确认原目录与审查工作区的 Git 状态；不声称完成额外的最终哈希复核或强制清理。

**最终处置建议：不扩张项目范围，先让已承诺的状态保护、证据判定与失败恢复真正兑现。**
