# 2026-11-10 skill 升级审查记录

本记录对应基线 `79905b55c2ac78e265813c485955b9b568127ae9`。实现与评测在 `codex/skill-upgrade-20261110` 的 Treehouse 租约中完成。上游同步与 C2 实现分别提交；2026-11-10 的 exact-diff 批准仅绑定下述 C2 三文件补丁，整项 PR 还包含原任务授权的上游同步和必要记录。pstack 保护边界继续生效。机器清单见 [skill-upgrade-2026-11-10.json](../../evidence/skill-upgrade-2026-11-10.json)。

## 范围与稳定发布判定

仅纳管 12 个 canonical skills 与 21 个 Git 跟踪工程 skills。8 个原创包不被当成上游 skill 的副本；17 个 DSH 工程 skill 没有正式稳定发布；eli5 与 asd-ste100 无 release/tag；4 个 ZCode 工程 skill 已在 v3.17.2；2 个来源需要稳定版同步。历史快照、临时副本、缓存、可选集成及 pstack 随附 skills 不作为升级目标。

稳定版采用官方非 draft、非 prerelease 的相关产品线发布，解析到 commit；不把默认分支 HEAD、文内版本或不同产品线当稳定升级。archify-dsh-v1.1.0 不属于 archify skill 产品线。archify 的默认分支许可证不能替代目标 tag：v3.1.0 与 v3.2.0 均为 MIT，原文已逐字核验。

2026-11-10 16:24:30（Asia/Shanghai）交付前再次核对六个官方仓库：最新适用稳定发布及三个 tag 解引用后的 commit 均未改变；DSH 的 37 个 release 仍全部为 prerelease，ASD 与 eli5 来源仍无 release/tag。22 次官方 API 请求和 44 个原始输出文件已保存并读回校验，未用默认分支 HEAD 代替稳定发布。复核摘要为 96e34eda0dd1d3be562268e756c8473771002244b22ce4acfdb6e7b0540195c9。

| 纳管 skill | 分类 | 判定 | 目标或保留来源 |
|---|---|---|---|
| agent-experience | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| architecture-governance | adapted(project-local) | 已在最新稳定来源 | v3.17.2 @ a9fe401eede6e6e5e01be9048679c206fe6f02d9 |
| cordis-styling-nitpicking | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dep-refs | adapted(project-local) | 已在最新稳定来源 | v3.17.2 @ a9fe401eede6e6e5e01be9048679c206fe6f02d9 |
| dsh-archive-agent-notes | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-ci-test-reliability | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-client-ui-ux | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-code-review | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-create-upgrade-guide | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-doc | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-error-handling | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-find-simplifications | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-pre-push-checks | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-prose-standard | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-responsive-ui | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-speed-up-perf | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-translate-docs | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| dsh-trim-cot-leakage | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| e2e-case-lifecycle | adapted(project-local) | 已在最新稳定来源 | v3.17.2 @ a9fe401eede6e6e5e01be9048679c206fe6f02d9 |
| feature-boundary-planner | adapted(project-local) | 已在最新稳定来源 | v3.17.2 @ a9fe401eede6e6e5e01be9048679c206fe6f02d9 |
| record-browser-gif | adapted(project-local) | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| super-arch-doc | original | 原创，保留 | 原固定来源；见 provenance 与机器清单 |
| super-archify | faithful | 稳定版已同步至本变更 | v3.2.0 @ 208acba8d412335185b2056fedf54b3405df43fb |
| super-asd-ste100 | faithful | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| super-ask-azhou | original | 原创，保留 | 原固定来源；见 provenance 与机器清单 |
| super-azhou-doctor | original | 原创，保留 | 原固定来源；见 provenance 与机器清单 |
| super-azhou-info | original | 原创，保留 | 原固定来源；见 provenance 与机器清单 |
| super-azhou-setup | original | 原创，保留 | 原固定来源；见 provenance 与机器清单 |
| super-azhou-verify | original | 原创，保留 | 原固定来源；见 provenance 与机器清单 |
| super-eli5 | faithful | 无可认定稳定发布，保留 | 原固定来源；见 provenance 与机器清单 |
| super-excalidraw-diagram | original | 原创，保留 | 原固定来源；见 provenance 与机器清单 |
| super-repo-pedant | adapted | 稳定版已同步至本变更 | 仓库 v1.2.0 / skill 3.1.1 @ cfa3436d4d31db9b1340af3082a914adf92f023f |
| super-session-insights | original | 原创，保留 | 原固定来源；见 provenance 与机器清单 |

## 上游三方迁移

| 对象 | 原引入 / 前能力基线 | 目标 | 吸收与保留 |
|---|---|---|---|
| super-archify | v3.1.0 @ 1c2b42d660e4a7571813fb43839c79e3e9ca7720 | v3.2.0 @ 208acba8d412335185b2056fedf54b3405df43fb | 十种原图模式保留，纳入 explainer；保留 Azhou 前门、品牌、receipt、独立安装和 Excalidraw 边界；内部 CLI 路径和官方更新身份恢复上游原名。 |
| super-repo-pedant | 原引入 bab178311a65f93ffd073e4fdebc9911eae35791；前基线 neat-freak 3.0.0 @ 322346ded8129436b3f64707789a73e732ae24d9 | 仓库 release v1.2.0 @ cfa3436d4d31db9b1340af3082a914adf92f023f；skill 3.1.1 | 保留全部 28 项兼容处置、Python inventory、触发差异、Treehouse、exact-diff 审批和收据。新增发现候选路径、生成记忆边界和共享交接可发现性；现有明确授权不重复确认。 |

neat-freak 的 6 个变更文件逐项映射：SKILL 的授权/交接/只读/已有修改边界对应本地现役流程；sync-matrix/governance/verification 的授权变化沿现有 checkpoint 实现；agent-paths 的新目录作为需验证的发现候选；audit-inventory.sh 的目录枚举由现有 Python inventory 和显式候选承担，不建立第二扫描器。前版本快照保留于 Git 基线与 A 归档；当前选定回归快照绑定稳定来源。

另外修复了来源记录中的本地改名污染：eli5 上游路径为 `eli5/skills/eli5/SKILL.md`；asd-ste100 的上游原名不带 super-；ask-azhou 与 eli5 的本地 frontmatter 为三键合同。这些是记录修复，不冒充新的上游版本。

## 上游效果的归因

archify 使用同一 workflow、官方稳定 manifest 和 explainer 输入，固定 Node v24.15.0、关闭在线 update check。比较 A、仅修旧版身份的控制、B。

| 可执行任务 | A | A 仅修旧版路径/身份 | B | 归因 |
|---|---|---|---|---|
| workflow preview 生成产物 | 找不到 super-archify.mjs，无产物 | 恢复 | 恢复 | 现有本地改名缺陷的修复 |
| 官方更新 manifest 身份校验 | 拒绝 archify 身份 | 接受 | 接受 | 上游身份与本地品牌分离 |
| explainer validate/deliver/check | Unknown diagram type | 仍不支持 | 生成产物 | v3.2.0 的新增能力 |

随后固定使用 v3.2.0 归档内未经修改的上游回归测试字节，在 A/B 同环境重放：

| 共同测试组 | A | B |
|---|---:|---:|
| Timeline DST | 3/8 | 8/8 |
| Workflow semantic migration | 5/11 | 11/11 |
| 合计 | 8/19 | 19/19 |

11 项失败转为通过，8 项既有成功全部保留；另有 6 项新增 explainer/chart 用例在 B 通过。这是选定上游回归用例上的功能收益，不是最终留出自然任务上的模型泛化收益。

默认 explainer 调用的 browser-check 确为 not-run；另行显式请求 Chrome 浏览器检查后，workflow 与 explainer 均完成 validate、deliver、check、browser-check 四项 gate。两者的 visualReview 均为 not-requested，不宣称独立视觉质量验收。explainer 示例的一项 scope-length 写作警告原样保留。完整输入、命令、产物、测试源 SHA 与运行包 190 文件摘要保存在 Git 外 archify-behavior.json 和 archify-source-tests.json。原始源码归档与 Git tree/blob 全量一致，未依赖有 300-file 上限的 compare API 来判定完整性。

## 集成检查发现的本地兼容修复

以上上游 A/B 结果对应归档的 B 提交，不覆盖后来新增的本地修复。[PR #430](https://github.com/TeFuirnever/azhou-ai-hub/pull/430) 首轮 CodeQL 报告 6 条新路径（4 high、2 medium），另有一次引用 revision 一致性检查发现。它们涉及 explainer 的 4 个新增文件，修复前均与正式 v3.2.0 原字节相同。该计数是静态报告，不表示 6 起已发生的利用事件。

本地改动分别处理 reader 动态文本/属性转义、CSS HTML 结束标签边界、CDP 选择器参数传递，以及显式引用 revision 与文档 pin 冲突时的明确拒绝。每文件的来源摘要、实际打包摘要和取舍已进入 [provenance](../../skills/super-archify/references/provenance.md)、兼容映射与 vendor manifest；官方 commit、许可证、203 个来源文件及 190 个安装包文件数量保持。C2 三文件及其批准摘要不变，这些修复不归因于 RSI。

| 配对或回归检查 | 修复前 | 修复后 | 解释 |
|---|---:|---:|---|
| 原 6 例 citation API 输入 | 4/6 | 6/6 | 两个冲突原先静默换成新 revision；现明确拒绝。另 4 个成功对照的完整 JSON 相同，全部输入对象未改 |
| 真实 Chrome 的 8 个边界观察 | 3/8 | 8/8 | reader 受控 payload 原产生 7 个标记图片并触发 handler，现保持字面文本；两类 CSS payload 在两个宽度均被阻断，合法 CSS range 行为保留 |
| 未改字节的上游功能回归 | — | 25/25 | 19 个原共同用例及 6 个 explainer/chart 用例，3.497s |
| 未改字节的上游 Chrome 回归 | — | 4/4 | focus/Enter、native Viewer 节点/边、双主题、resize、打印/无 JS、走查，12.634s |
| 新增定向单元回归 | — | 3/3 | revision 7 种情形、真实 render 的 HTML 边界、CDP 参数/错误/对象释放，0.498s |

这些是控制输入下的 API/浏览器边界证据。reader 压力输入覆盖了通常可信的 locale/source 元数据，恶意行号绕过了正常源验证；旧 CDP JSON.stringify 表达式未被证明可注入，修复消除的是数据/代码拼接边界。reader/CSS 探针直接控制 prepared/DOM 数据，不能据此认定所有正常作者输入都能到达相同攻击路径；重复宽度不是独立自然样本。citation 的 6 例规则汇总在观察后形成，不冒充事前注册或盲测；候选独立耗时未记录，保持 unknown。浏览器边界探针总耗时 6.600s，不做速度结论。原始 HTML、DOM 结果、输入、规则和命令留在 Git 外，公开逐例布尔结果和摘要见机器证据。

首轮本地兼容修复源码已再次执行全仓 verify，8/8 通过、76.237s，包含 665 项 Hub 单元测试及 59/45 两组现有包级测试；已知 native-event sample skip 保留。日志 SHA-256 为 `25f64c4409a04b290aeafa2df686e0be8cfe024ee386bf6792851c5a59c51607`。这些本地结果不替代最终 PR head 的必需 CI 和审查线程状态。 五文件本地补丁另在隔离副本上完成 reverse-check、reverse 和 reapply，均恢复到预期字节；补丁与恢复摘要见机器证据。

### Clipboard API 回退的后续修复

后续审查发现，两处复制 handler 在 Clipboard API 缺失时把 undefined 当成成功，导致 Ask 关闭并假报复制，snippet 也误报成功。这里只加入共享 async 可用性检查，让 API 缺失和拒绝进入原有失败分支：Ask 保持弹窗并选中完整上下文文本供手动复制，snippet 显示失败；成功路径保留。该差量仅修改 reader 与一个仓库行为测试，属于上游集成兼容修复，不归因于 C2 或 RSI。

冻结的同一六例（两个处理器 × 缺失/拒绝/成功）在真实 Chrome 的受控 API 状态下从 **4/6 到 6/6**，四个原成功对照保留；新增行为单测在旧 reader 上退出 1、修复后退出 0。原 paired run 未逐臂记录浏览器版本，这一限制保留。另做的认证复放使用未修改输入、规则与 probe，两臂实际 Browser.getVersion 完全相同：Chrome/157.0.8103.39、V8 15.7.112.23、protocol 1.3；仍为 4/6 与 6/6，两个 190 文件包仅 reader 不同，运行前后源字节稳定。原 paired 耗时 2.260/2.201s，认证复放 2.710/2.242s，分别保留，不推断速度收益。

第一版探针误用没有复制按钮的 code block，1.217s 后中止；改用 snippet 并在 reader 修改前重新冻结，原失败记录保留。后续只整理测试空行，Python AST 相同，旧单测摘要与最终源码通过格式等价记录连接；最终全仓 verify 单独覆盖最终字节。最终两文件 diff SHA-256 为 `69da26120afc5f92f6bb1a48e02551348f249c84ec5c2e8746ca0e611de2eaa1`，隔离 reverse/check/reapply 四步均为 0，准确恢复旧版和候选字节。

这些六条观察共用一个合成页面，Clipboard API 结果受控，不声称六个独立自然会话或实际系统剪贴板写入。probe 内模型调用/token/API 费用为 0，整项编排模型成本仍 unknown。原运行、认证复放、失败尝试、格式等价、最终 diff 与恢复记录分别绑定在机器证据中。

剪贴板修复后的最终源码已执行全仓 verify：**8/8 门禁通过**，包含 **666 项 Hub 单元测试与 59/45 两组现有测试**，实际耗时 75.731s，日志 SHA-256 为 `b54625c2d796d0b2868a4fdf506953cf48765d9d60eb2349c9fb32c1c86ebb0e`。11 项源码、测试、manifest 与合同摘要在运行前后相同；该次 unittest 摘要报告 1 项 skip，未逐项打印原因。本任务未提供 native-event 实采样本，不声称宿主原生事件实弹验证。最终来源与公开摘要随后只补充这次实际结果，精确 PR head 的必需 CI 与线程仍是集成条件。

## 一个候选：项目证据归属

失效机制：现有 `cmd_propose` 按 mechanism/outcome 取证，却没有在 project scope 中核对 `project_id`；外项目信号可以凑足本项目门槛、触发 severe 例外，并被候选归档消费。来源是当前实际 CLI 受控复现，不是由历史复盘反推的自然事故。修复仅复用既有 `project_identity`，在统计前过滤项目归属；显式 global 行为保留。

| 当前缺口 | 一手依据 | Hub 位置 | 最小改动 | 验证 |
|---|---|---|---|---|
| project scope 混入外项目信号 | backpass c8d60c24 的 discovery/association 与 evidence identity；Hub 现有项目范围合同 | manage_evolution.py 的既有 matching 入口 | 既有 project_id 相等条件 | 冻结 A/B/C CLI、负例拒绝、成功保留、隔离回滚 |
| 评价与修改版本须可复核 | GEPA 的逐例父候选比较、train/validation/test 隔离 | 本次已有 benchmark/外部运行 manifest | 绑定输入、命令、源码、产物、diff 和 evaluator；不新增优化平台 | 独立 evaluator 从精确 diff 重建 C 并比较被执行源码 |
| 改进声明不能超过证据 | Reflexion 的经验反馈；DGM 固定修改器消融及后代谱系 | 本审查记录的结论范围 | 按经验/指令/执行流程区分 | 不声明递归收益；无后代自改或同预算固定修改器实验 |

backpass 的会话归属、去重、采样、预算、候选隔离、拒绝和应用代码已审计，选定269项测试通过。 原运行完整 stdout 未保存且进程记录已不可取，保留此缺口。2026-11-10 01:41:28（设备时区）在同一 clean commit 上另行重放原先八个测试文件和两个负对照：269/269 通过、7.136s；这次 later replay 保留完整输入、命令、输出、源码/测试摘要，不冒充原运行日志。未复制其整套框架：它的 usedRawTranscript opt-out 可跳过引文核验，合法 source label 也不必证明 quote 入目录；两者均有合成负对照。其 staging/fingerprint 不是 OS 沙箱，bytes/4 不是实际 token 计费。Hub 已有门槛、隔离、归档、审批与回滚合同，仅对确认的项目归属缺口提出候选。

### A/B/C 结果

被测层是确定性 CLI，固定 Python、权限、项目配置、原始 signal 字节、预算与任务输入，模型为不参与。B 的这段 CLI 代码与 A 相同，上游指令变化不参与此项效果估计。

| 集合 | A | B | C | 范围 |
|---|---:|---:|---:|---|
| 修改器可见 16 例 | 10/16 | 10/16 | 16/16 | 开发、选择及可见回归，非最终留出 |
| 独立合成留出 12 检查 | 4/12 | 4/12 | 12/12 | 11 家族；含一对顺序变换；对冻结 C 盲测 |
| 留出内 global | 3/3 | 3/3 | 3/3 | 已有跨项目能力保留 |

独立留出的最后文件冻结发生在收到 C 的 hash 后，但创建者在冻结前未看 C 实现、diff 内容、工程用例或 C 结果；准确时序保存在 manifest。冻结后不修改评价器、答案或通过条件，也不根据该留出重新调参。其素材为合成源记录，多项检查复用记录，不能当作独立自然任务估计置信度。全部逐例结果与摘要见机器证据。

实验时冻结的 C1 三文件 diff SHA-256 为 `699841646943b92ee158cbb7de7e4566ac2caf2750f5ed31ffcc3ecc5610881e`。全仓编码政策随后发现新增测试 fixture 的一个 subprocess 缺少显式 UTF-8；C2 仅补此参数，不改变断言、冻结评价器、输入、答案或运行时。C1 与全部旧记录保留，不覆盖实验历史。

已获 exact-diff 人类批准的 C2 三文件 diff SHA-256 为 **`d81dc19a7b323a87f52e2090c21f3e4386f45301109d0e92be235e57f71fe059`**；C1→C2 单行 delta 为 `7b93fc7aa08279c39dd5fe2814ca1654a97d30a6cb17ccb573750c152dbc5471`。两版的实际运行时均为 `9f2c60ce99652ce0f1b41b4525d6a2c2533e7ac3570a63b5448d01fdb971a77d`。实际字节比对把原 A/B/C 运行结果绑定至相同运行时，不把 C1 整包差异冒充 C2 差异。

只有项目证据归属这一个机制候选被实现，未向其他技能盲目扩散。其他正式技能并无同一准入代码，工程技能的现有能力继续保留。

### 成本、拒绝与恢复

可见集每组18次CLI；累计时间 A 0.837s / B 0.876s / C 1.123s。独立集每组12次 proposal；evaluator wall A 0.494s / B 0.483s / C 0.687s；输入准备28次命令0.942s，补丁重建2次命令0.022s。均为本机单次观测，不作速度收益结论。确定性 runner 无模型调用，实际 runner API token/费用为0；编排、研究与候选生成的模型用量/费用不可观测，整项任务费用为 unknown。

不良外项目候选在 C 被拒绝；自身严重事件、普通两会话、同 origin worktree 和 global 对照保持。隔离副本上反向应用精确三文件 diff 后，原运行时、helper、测试和合同摘要恢复，10例开发/验证输出语义与 A 一致。回滚不删除失败证据。

### 配对评审与独立验收的边界

三位评审使用独立上下文，X/Y 标签隐藏映射且第二位交换顺序；三位都选择候选，无已观察的回归。评审使用相同继承模型，不声称模型多样性或统计独立样本。初审要求补足归档后的原始行与 live sentinel 摘要；追加的单夹具核验确认 C 仅归档 2 条本项目合格记录、保留其余 5 条，所有 7 条的字段无丢失/重复，sentinel 与 runtime 字节保持。它不是新增留出样本；外部 include 文件为空、并发/中断等未被该补充覆盖。

评审对 C2 的测试编码改动另出实际 diff 等价声明。投票不替代上述运行证据，也不构成人类批准。原始评审中的 human_approval=false 保留；2026-11-10 的用户批准另行记录，不把投票或历史 promoted 状态作为人类授权。

## pstack 保护证据

上一轮审查的原始保护快照覆盖 18 个根路径、4,746 个普通文件、46,845,893 bytes；在该轮结束时，文件内容、大小和权限 **4,746/4,746 一致**，新增/删除/改变均为 0。前后规范化文件映射 SHA 为 `4524fc4aa96d72e5cbf63bf73356a3d314f193144ab3ab42ae8edc4d29d5fcd8`。leased worktree 内保护范围的 3,234 个 Git 纳管文件与基线及 main 全部一致，共享检查器中的 pstack AST 节点没有改变。

上述原始审查窗口内，Claude 注册的 pstack-azhouzhou 0.15.36 安装目录、marketplace 源、两侧 cache/config、模型配置及共享集成运行时均在保护清单内且未改变。两处初始快照之外的历史 target home 当前不存在，其回执为 removed；回执所指 0.9.102 历史源快照的 271 个清单文件仍相符。旧移除回执中的 Codex CLI 指纹与当前文件不同，当前文件 mtime 早于本次任务；该二进制未纳入初始快照，因此只报告历史差异，不归因于本次任务。

原快照未独立记录目录权限、根类型和符号链接文本；这些只补充为当前快照。没有运行/安装 pstack，没有声称 live 模型/服务或所有外部状态完全等价。保护结论由实际文件/配置/注册状态与相关现有测试支撑，范围之外保持未验证。

批准阶段首次复核发现：Claude 共享 settings.json 与上一轮文件快照不同，其当前 SHA-256 为 `030f5781d03ea1b640633ac1ebacb458aefe2ec6a8efff61b67d14c73c857456`。仅有旧整文件摘要，无法还原或归因期间的设置变化；本次未写回该文件。当前 pstack enabled 值为 true，marketplace 引用摘要另有记录。以本轮首次快照为基线的提交前检查确认 4,746 个普通文件及 3,234 个受保护纳管文件均未改变；该结论不声称两轮之间所有配置始终相同。

## 尚未解决的证据限制

1. 历史存储的11条活跃信号、5条归档信号和2个 promoted 记录不能替代原始事件；引用的两个旧 rollout 当前不可用。47个精确归属 Hub 的现存会话只找到相关源码阅读，未确认 propose/gate/archive 的真实运行。历史收益保持未验证。
2. 现有 promotion gate 只比较 evaluation/approval 声明的 hash，没有读实际 patch。当前受控变更实际 patch 后，gate 仍可宣告 promotable；本候选没有混入第二机制去修它。本次使用独立实际字节绑定，不把这个 gate 的自述当充分证据。
3. project_id 来自既有信号，不是密码学认证；会话祖先归并、原始来源真实性等不是本候选覆盖范围。
4. 尚未证明自然任务完成质量、人工修改成本或模型 token 改善；也没有改进后的系统生成下一代、固定改进器同预算对照，因此不称已验证 RSI。
5. C2 的人类批准只解决本补丁的授权条件；既存 skip、历史来源缺口、通用 gate 缺陷和范围之外的能力结论仍保留。

## 验证与恢复入口

基线 A、仅同步上游 B、加入机制的 C2 均实际执行 `python3 scripts/verify.py --print-summary`，最终各通过 **8/8 阶段**。B 首次因新 Archify 测试三处漏写 UTF-8 失败；修复后重跑通过。另一次定向检查发现 C1 测试的同类遗漏，C2 修复后 47 项定向检查通过；失败日志和重试成本保留。

B 全仓最终用时 65.606s，C2 用时 67.579s；相同机器单次测量不作速度结论。C2 的日志 SHA 为 `a751e14dee655977bc2ffbddb6cd8d9e436a157cfaa19d99adbdf1c246b687af`，包括 repository policy、全部 unit、package manifest/POSIX lifecycle、三套注册 benchmark integrity、working/staged whitespace。既有 Agent Skin native producer 集成类因未提供 `AZHOU_AGENT_SKIN_NATIVE_EVENT_SAMPLES` 跳过；这不是本次范围的宿主实弹证明。最后结果文字、双语导航和证据目录的旧路径修正另做文档读回、链接、策略和空白检查，未改变已测运行时代码。

现有 pedant benchmark 实际登记 4 个 case，README 旧计数 3 已对齐注册表；其完整性通过不冒充模型效果。逐例运行、版本绑定、失败与重试均在 [机器证据](../../evidence/skill-upgrade-2026-11-10.json) 和 Git 外原始记录中可查。

上游同步提交 `ddd914f76673efad666a51d17fbe0cec0a7f0e18` 与 C2 实现提交 `15cd81343eb18e760e03752e5d9b0cca1b1ec8b0` 分开保存。两提交之间的实际 binary diff SHA-256 与获批 C2 完全一致。公开收据是另一项记录变更，不能把整项 PR 的 diff 冒充获批的三文件补丁。恢复先执行 `git apply --check --reverse candidate-r2.diff`，通过后在拥有该变更的隔离目录反向应用；上游提交则通过新反向提交恢复，不 reset/clean 主工作区或改写公共历史。Git 外原始证据、上游 bundle 与 C2 精确补丁继续保留；仓库集成通过既有 PR、必需检查和 squash 流程，实际合并结果由 Git 历史证明。

## 2026-11-10 exact-diff 决定

用户对上一轮完整 C2 摘要与精确差异的最终审批请求作出明确批准。原始批准留在 Git 外，批准记录 SHA-256 为 `3feb817c71b3ab22b9afb00185a874fb5c7b7819afc4308d7d5385c03f3d0eff`；记录时间是本轮整理时间，不冒充消息的精确发送时间。当前 [演化决定](../../benchmarks/super-repo-pedant/history/project-evidence-promotion-2026-11-10.json) 与 [机器证据](../../evidence/skill-upgrade-2026-11-10.json) 绑定实际 C2、三份原始 paired review、三份 R2 attestation、当前认证回放和保护检查。旧执行记录保持原样；生成夹具状态的回放副作用与精确恢复另记如下。

普通失败的两来源门槛由分别设计、分别执行的工程开发验证与独立合成评测支持；当前 curated candidate 记录为 source=synthetic、source_type=controlled_execution、natural_history_sessions=0。这里的 2 是两个实际执行上下文，不是用例数或夹具内 session 数。独立运行发生在 C1 冻结之后，因此当前整理不追认“早期冻结时已具备两来源”，也不声称统计独立性。

批准后按原冻结评价器再次执行 C2，16/16 通过，耗时 1.515s；它是认证回放，不是新增盲测。同期全仓 verify 8/8 通过、75.524s，日志 SHA-256 为 `2ca204a6468ed7ed4e5db7072e7fb9ab5dc8e613abc77e83cb642e4773fab13b`。gate 返回 promotable=true；应用前仍独立读取实际补丁字节并比对批准摘要，未将通用 gate 的声明校验当作实际字节验证。

### 认证回放的夹具状态副作用

交接完整性检查发现，本轮两次认证回放复用了原评价器的 inputs/<case>/projects/own/.azhou/super-repo-pedant/evolution 生成状态目录；评价器会先清理该目录、再生成 candidate/archive。原始清单中 14 项生成状态因此发生短暂漂移。此问题归于评测 harness 的状态隔离与本次编排，不是 C2 项目过滤逻辑，也不是冻结输入、答案或评价规则被改写。

全部 14 项都在原已冻结 run artifacts 中找到 SHA-256、字节数和权限一致的副本。先完整保存 16 个回放后状态目录，再恢复原 30 个夹具状态文件；原 5,036 项清单复核全部匹配，原 manifest、冻结输入、评价器和历史执行记录未改。恢复记录 SHA-256 为 `a1f6811071cb96e1f385a0270d203caa4abf53f75f2dd2371b59bcdaa3ebd963`。回放结果与事件记录同时保留，不用恢复后的相等性声称从未发生过漂移。后续复现须先保存并恢复完整状态，或另行声明隔离路径映射；夹具包含绝对 ownership 路径，不能悄悄修改原冻结协议。

## 一手来源

- [Backpass 源码固定 commit](https://github.com/kunchenguid/backpass/tree/c8d60c24d4dc7e341d363bd4cddb5c8d6fedbb54)
- [Reflexion 原论文 v4](https://arxiv.org/html/2303.11366v4) 与 [作者代码](https://github.com/noahshinn/reflexion)
- [GEPA 原论文 v2](https://arxiv.org/html/2507.19457v2) 与 [作者实验 artifact](https://github.com/gepa-ai/gepa-artifact)
- [DGM 原论文 v1](https://arxiv.org/html/2505.22954v1) 与 [作者代码](https://github.com/jennyzzt/dgm)
- [archify v3.2.0 正式发布](https://github.com/tt-a1i/archify/releases/tag/v3.2.0)
- [Khazix Skills v1.2.0 正式发布](https://github.com/KKKKhazix/khazix-skills/releases/tag/v1.2.0)
- [ZCode v3.17.2 正式发布](https://github.com/zai-org/ZCode/releases/tag/v3.17.2)

论文用于限定机制和验证方法，不以论文成绩替代 Hub 运行证据。三篇作者代码的网页 main 检查未获得 immutable commit，因此不复制代码、不称为稳定依赖；借鉴的概念在本次来源表中明确注明。
