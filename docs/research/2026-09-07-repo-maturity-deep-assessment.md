# 研究：仓库整体成熟度深度评估（v0.8.0 时点）

- 研究日期：2026-09-07（Asia/Shanghai）
- 范围：Azhou AI Hub `main@87d5fb9`（v0.8.0）四个维度——仓库工程成熟度、harness 成熟度、skill 资产成熟度、现存问题清单。
- 方法：四个并行只读研究代理分别核查（工程/门禁/CI、harness 声明与回据、15 个 skill 包对照 [docs/skill-standard.md](../skill-standard.md)、问题与债务盘点）；主会话实跑 `python3 scripts/verify.py`（exit 0），并对承重数字（回据数量、tag 状态、workflow 清单、skill 版本字段）做二次抽查。
- 说明：本文为纯研究观察，不修改任何 skill、门禁或声明文档，不触发 promotion 流程。仓库内行号以 2026-09-07 工作区为准。

## 结论（TL;DR）

| 维度 | 评级（1-5） | 一句话定性 |
|---|---:|---|
| 仓库工程/治理 | 4.5 | 门禁代码化、供应链加固、exact-diff 晋升治理，小规模资产仓库中罕见的高水位 |
| Harness（跨宿主） | 3 | 架构成熟（中立核心 + 三 adapter 单源委托），但实测回据覆盖仅半程且严重偏斜 |
| Skill 资产 | 头部 5 / 均值约 3.5 | 3 个包满级、4 个接近满级；尾部薄包与零回据 skill 拉低均值 |
| OS 跨平台（harness 子维度） | 2 | 声明缺失、CI 零覆盖、94 项平台性实测失败未修，修复 spec 完成度 0 |

三个结构性观察：

1. **治理先行、验证跟进**。合同与门禁的成熟度（4.5）系统性领先于运行证据覆盖（3）与 OS 维度（2）。这是"先立标准、后补证据"的有意策略（[azhou-skill-portability.md](azhou-skill-portability.md) 的 Decision 节即此路线），当前正处在证据补课的中段：合同已能机械强制，回据还没跟上。
2. **在途工作流的证据链存在工作区单点**。支撑最大在途工作流（Windows/macOS 兼容）的 spec、两份研究笔记与 Windows 实测回执全部停留在未跟踪文件（`docs/specs/`、[docs/research/2026-09-07-skill-cross-platform-macos-windows.md](2026-09-07-skill-cross-platform-macos-windows.md)、[evidence/windows-unit-test-v0.7.0-2026-09-07.md](../../evidence/windows-unit-test-v0.7.0-2026-09-07.md)），tracked 文件零引用，CHANGELOG 0.8.0 亦未提及。丢工作区即断链。
3. **发布纪律有一处可见脱节**。CHANGELOG 已 cut 至 0.8.0，但本地与远端 tag 均止于 v0.6.0（`git tag` 与 `git ls-remote --tags` 实测一致）——README 的 release 徽章对外显示落后两个版本。

## 一、仓库概况

- 仓库 2026-08-22 首次提交，17 天内 113 个提交（日均约 6.6）；CHANGELOG 自 08-28 起累计 10 个版本段至 0.8.0（#160）。
- 15 个 canonical skill 包（`skills/` 下；`.omc/` 为运行态目录非 skill）。
- 429 个单元测试（`tests/` 43 个文件、约 10,679 行，纯标准库 unittest，支撑零依赖声明）；`python3 scripts/verify.py` 于评估当日实跑通过（exit 0）：926 个公开文件过仓库策略、429 测试全绿（47s）、4 个 benchmark 完整性套件全绿、双空白门通过。
- 单维护者仓库：CODEOWNERS 全部路径指向 @TeFuirnever。

## 二、仓库工程成熟度：4.5 / 5

评级标准：1=无自动化；2=基本 CI；3=完整 CI+测试+文档；4=策略门代码化、供应链加固、来源与晋升治理；5=在 4 之上再加多 OS 矩阵、覆盖率目标、全自动发布闭环。

### 强项（证据）

1. **确定性验证门本地/CI 同构**：[scripts/verify.py](../../scripts/verify.py) 是 8 道门的编排器（仓库策略、unittest、repo-pedant/super-caveman/excalidraw/prose-standard 四个 benchmark、工作区+暂存区空白检查；`--promotion-evidence` 追加 Git 外部晋升证据供 release 用）。
2. **策略核心代码化**：[scripts/check_repository.py](../../scripts/check_repository.py)（542 行）含 13 类检查——必需文件清单、逐 skill 品牌契约咬合（含身份/口号/启动行/三标记/emoji 边界）、路由覆盖与 invocation 枚举 fail-closed、Markdown 断链、**action 40 位 SHA pin 强制**（约 :404-421）、公开边界（禁 `agents/openai.yaml`、禁 raw history 入 Git、100MB 限制）、运行态默认路径契约、5 类高置信密钥形状扫描、neat-freak 基线哈希与 vendored Excalidraw 许可块校验。
3. **CI 供应链姿态一流**：6 个 workflow 文件（ci/codeql/dependency-review/fuzz/release/scorecard）全部最小权限、全 job 有 timeout、并发取消、action 全 SHA pin 且有仓库策略门二次强制；CodeQL 双语言周扫、dependency-review 高危即fail、周度 fuzz、OpenSSF Scorecard；release.yml 仅手动触发、限 main、SemVer 正则、只建草稿。
4. **Git 纪律**：113 个 commit 中仅 2 个偏离 `type(scope): imperative` 格式（Initial commit 与 #136 批量提交）；CHANGELOG 条目详尽并交叉引用 PR/规格/上游 pin。
5. **合规与双语文档**：README EN/ZH 镜像同步（各 14 节、15 条安装命令，抽查无漂移）；`THIRD_PARTY_NOTICES.md` + `LICENSES/` 9 份许可文本，每个 vendored/改编材料记录不可变上游 commit；SECURITY.md 走私有 advisory；GOVERNANCE.md、CODEOWNERS、dependabot 齐备。
6. **晋升治理机制**：super-caveman 晋升门以 blob 级 old/new oid 锁定改动面（[benchmarks/super-caveman/results/revision-93f38a6b-exact-diff-approval.json](../../benchmarks/super-caveman/results/revision-93f38a6b-exact-diff-approval.json) 的 8 个 reviewed_blobs），被覆盖路径再编辑即触发公共门失败——演化链有实打实的哈希绑定。

### 弱项/缺口

1. **tag 与 CHANGELOG 脱节**（见 TL;DR 观察 3；v0.7.0/v0.8.0 无 tag，推测草稿未发布，但对使用者可见）。
2. **CI 仅 ubuntu-latest**：6 个 workflow 文件约 10 个 job 无 OS 维度；测试里写好的 Windows 跳过守卫（如 `tests/test_super_caveman.py:276` 的 `skipIf(os.name=="nt")`）从未被真实执行过。
3. **本地 verify.py 不含 fuzz 门**：fuzz 只在 CI 周扫跑，"交付前本地验证"与 CI 覆盖面不完全一致。
4. **无 lint/类型/覆盖率门**：Python 侧只有策略+单测+空白检查，无 ruff/mypy/coverage。
5. **单维护者总线风险**与一次批量提交违规（#136）。

## 三、Harness 成熟度：3 / 5

支持面为三 harness：Codex、Claude Code、zcode（[docs/support-matrix.md](../support-matrix.md)）。`evidence/` 下 29 份带日期回执中 harness 维度分布约：zcode 13、Codex 5、Claude 2（含 1 份与 zcode 的合并记录、1 份 llm-wiki 生命周期接线），其余为安装冒烟、arch-doc 评审、Windows 单测等非 harness 回执。

**实测 vs 仅声明**：

- Foundation 四件套（azhou-doctor/info/setup/verify）是唯一三 harness 全实测的组（各自 foundation-discovery-invocation 回执）。
- super-caveman：三 harness adapter 均落地且 Codex/zcode adapter 委托 `claude_adapter` 保持中立核心单源；三 harness 均有 live 冒烟回执；但 19/19 行为等价仅在 Codex 列，zcode attempt-1 失败（9/19）被如实记录。
- llm-wiki：生命周期接线 + MCP transport 回执；MCP transport 仅 Codex+zcode 实测，Claude 列"需显式配置"无回据。
- eli5/autoresearch：zcode+Codex 双回执，Claude 仅声明；lavish 仅 zcode 回执。
- **无任何 harness 回据**：repo-pedant 的 Codex 调用、arch-doc（矩阵自认 "no host discovery/invocation receipt yet"）、excalidraw-diagram（仅 Codex 模型底线回执）、ask-azhou/ci-test-reliability/prose-standard（无矩阵行）。约 9/15 的 skill 缺任一 harness 实测回据；0.6.0 CHANGELOG "Planned: First complete cross-harness evidence set" 自认此缺口。
- 中立核心原则落实良好：全仓无 `agents/openai.yaml`（find 实测为空）。

**OS 维度（最弱轴，2/5）**：详见 [2026-09-07-skill-cross-platform-macos-windows.md](2026-09-07-skill-cross-platform-macos-windows.md)。要点：support-matrix 无任何 OS 列/行；文档命令面 100% POSIX 形态（`python3` 约 136 处）；v0.7.0 Windows 实测 427 测试 73 FAIL + 21 ERROR，全部为平台兼容问题、无一业务逻辑缺陷；修复 spec（`docs/specs/2026-09-07-windows-macos-compat.md`，状态 ready-for-agent）完成度为 0——上一轮修复批次因触发未归因的全量门禁失败已整体回退。

**刚标准化的轴（成熟度上行中）**：invocation class 三枚举 14/15 已声明并进 gate（super-caveman 待下次 promotion ride 落地后翻转为全量必填）；llm-wiki 八工具 MCP 生命周期（#154/#159）；eval-case 机制（#152）目前 n=1，刚起步。

## 四、Skill 资产成熟度：头部 5 级、均值约 3.5

`docs/skill-standard.md` 要求的生命周期要素：独立安装包结构、setup 依赖声明、品牌层合同、真实运行证据（reference fixture 只证接线）、评测材料隔离于仓库级 `benchmarks/`、演化链（observed→promoted/rejected，paired 3 法官 + exact-diff 人批）、closeout。

**标准执行力：机械 fail-closed 为主、人纪律为辅**。品牌/发现/invocation/provenance/公开边界均由 `check_repository.py` 强制；super-caveman 的 `benchmark.py` 机械验证 promotion record（staged_patch sha256、reviewed_blobs、raw 记录 Git-external）。靠人纪律的残余：invocation 全量必填未翻转、arch-doc benchmark 未注册进 verify.py。

**15 包分级**（版本均为仓库级 0.8.0，无一声明独立版本号——实测 frontmatter `version:` 字段 0/15）：

| 分级 | skill | 依据 |
|---|---|---|
| 5 | repo-pedant、super-caveman、excalidraw-diagram | 品牌层 + 演化契约 + benchmark 进 gate + 真实实测/promotion 记录全齐 |
| 4 | prose-standard、llm-wiki、lavish、arch-doc | 测试/接线/真实回据充分；差模型实测或 benchmark 未入 gate（arch-doc 有 runner+回据但未注册） |
| 3 | azhou-verify、ci-test-reliability、eli5、autoresearch | 有脚本/测试/加载类回据，无 eval-case |
| 2 | azhou-doctor、azhou-info、azhou-setup、ask-azhou | Foundation 薄包（设计使然，共享 `scripts/azhou_hub.py` 权威）；ask-azhou 仅文档 + router gate，无运行回据 |

**许可面健康**：原生 skill 无需 provenance 属合规；8 个改编/吸收包均有 provenance.md 且 hash 受校验；excalidraw 字库另有独立 LICENSE。

**系统性缺口**：per-skill 版本号缺位（0/15）、benchmark 覆盖 5/15、super-caveman invocation 声明悬置（有明确落地计划）、eval-case 样本量 n=1。

## 五、现存问题清单

### P0（阻塞/正确性）

1. **super-caveman 三 adapter 原子写清理分支真实缺陷**：句柄未关即 `unlink()`，Windows 实测约 45 项 FAIL/ERROR 的根因（`skills/super-caveman/scripts/claude_adapter.py:108`、`codex_adapter.py:276`、`zcode_adapter.py:116`）；`os.replace` 真实失败被 finally 清理分支的 `PermissionError` 反向掩盖。Windows 上安装/状态写入装完即错。
2. **OS 维度声明与验证证据整体脱节**：support-matrix/README/installation 无 Windows 主张亦无"仅验证 macOS/Linux"的诚实声明；10 个 CI job 全部 ubuntu-latest；文档命令面 Windows 用户第一步即卡死。既有研究自评 P0。
3. **pinning 回归雷区未归因**：win-01（tasks-axi）记录上一轮 Windows 修复批次触发全量门禁 `FAILED: unit tests` 后未定位即整体回退；win-02..05 全部排在它后面——M1 修复工单被一个未知回归堵住。

### P1（重要缺口）

4. **spec/research/evidence 未入库**：`docs/specs/` 整目录、两份研究笔记、Windows 实测回据均为 untracked；它们互相引用形成证据链但 tracked 文件零引用，windows-macos-compat spec 连 GitHub issue 都没有（对照：session-insights 至少有 #161 作 spec-of-record）。
5. **积压体量**：tasks-axi 12 个 queued（windows-macos-compat 父任务 + win-01..win-09 + eli5-trigger-watch）；GitHub 10 个 open issue、0 open PR——#161-#168 session-insights 九连、#156 invocation sweep 跟进、#27 OpenSSF 治理（09-02 开，搁置最久）。
6. **hook 宿主 shell 前提未声明**：repo-pedant hook 片段字面硬编码 `python3` 与 POSIX `|| true`（`skills/repo-pedant/assets/hooks/claude-hooks.fragment.json:9,19`），依赖 Git Bash；宿主回退 PowerShell 即不兼容（win-08 未做）。
7. **promotion gate 日常编辑摩擦**：凡触及 revision-93f38a6b reviewed_blobs 覆盖清单（CHANGELOG、brand layer、benchmark manifest 等）的编辑都须与维护者批准的 promotion ride 同行——流程重且易"改了内容、回据失配"。
8. **发布 tag 落后 CHANGELOG 两个版本**（见二.弱项 1）。

### P2（改进项）

9. **局部平台债**：`excalidraw_lib.py` 硬编码 `/tmp` 缓存目录（:39）与 JSON 读取缺显式 UTF-8（:53）；fuzz 看门狗 SIGALRM 无平台降级（win-04，Windows CI 前置）；权限位断言无平台两分法（3 FAIL）。
10. **provenance 复算仅 Unix 工具链**（`shasum`/`find|xargs`），无标准库等价命令（win-06）。
11. **eli5-trigger-watch 任务 body 为空**，观察项无可交接记录。
12. **无 lint/类型/覆盖率门**；**单维护者总线风险**。

### 反向确认（不是问题）

- 代码内标记清扫干净：排除 fixtures/benchmarks/vendored 后真实 TODO/XXX 标记仅约 10 处，全部为文档示例、反标记 lint（`tests/test_skill_package.py:79-80` 断言技能不得含 TODO）或上游 vendored 代码，无代码级 TODO 债。
- README 双语无漂移；427（Windows v0.7.0）vs 429（macOS HEAD）测试数差异有研究笔记解释。
- Windows 实测回据中"category 6 怀疑 revision-93f38a6b 回据与 manifest 不匹配"一项，经本次在 macOS 实跑对应单测（`SuperCavemanBenchmarkTest.test_capability_and_trigger_integrity`）为 OK，应改判为平台行为差异而非入库内容缺失。

## 六、与既有研究的关系

- [azhou-skill-portability.md](azhou-skill-portability.md)（08-26）回答 harness 层设计依据：Agent Skills 不标准化发现/调用/hooks/权限，故选择"中立确定性 CLI + 标准 SKILL.md 包 + 薄安装面"。
- [2026-09-07-skill-cross-platform-macos-windows.md](2026-09-07-skill-cross-platform-macos-windows.md)（09-07）回答 OS 层现状与六类失败。
- 本文在其上加总：整体成熟度分维评级、结构性观察与全量问题清单。三份笔记共同指向同一优先级排序：先归因 pinning 雷区再重放 M1（P0-3 → P0-1），同时把 OS 维度声明与 CI 补上（P0-2），并把在途证据链入库（P1-4）。

## 验证方式

- 主会话：`python3 scripts/verify.py`（exit 0，输出含 926 files / 429 tests OK / 4 benchmark 套件）；`git log`/`git tag`/`git ls-remote --tags origin`；`ls evidence/ | wc -l`；`ls .github/workflows/`；`grep -c '^## ' CHANGELOG.md`；`grep -l '^version:' skills/*/SKILL.md`（0 命中）。
- 研究代理：只读核查 `scripts/verify.py`、`scripts/check_repository.py`、`tests/`、`.github/workflows/`、`docs/`（skill-standard/support-matrix/installation/specs）、`skills/` 全部 15 包、`benchmarks/`（super-caveman promotion record、repo-pedant results.tsv、excalidraw ordinary-model-floor）、`evidence/` 全部回据、tasks-axi backlog、GitHub open issues/PRs。
- 复核建议：任何单条结论可按上文引用的文件路径直接打开核对；评级为研究判断，供维护者决策参考，非机器字段。
