# 研究：生产级 GAP 审视 与 autoresearch 非 NVIDIA GPU 支持可行性

> 日期：2026-09-13（Asia/Shanghai）
> 性质：纯研究笔记。分两部分：A. 以业界公认准则为基准的端到端生产级 GAP 审视；B. `autoresearch` wrapper 能否支持非 NVIDIA GPU 的源码级调查。本文不修改任何 skill、门禁或公开声明，不关闭 #27 的任何 checkbox。
> 对象版本：`main@12c7838`（2026-09-13 13:43 +0800，CHANGELOG [Unreleased] 段，十四个 canonical package）；OpenSSF Scorecard 快照 `2026-09-13T05:44:12Z`（commit `12c7838`，score 6.9）。
> 用途：给维护者的生产化决策输入；第二部分同时回答“wrapper 层面能把失败报得诚实到什么程度”。
> 证据口径：标注“已验证”的内容来自逐行读取仓库文件或逐行抓取远端源码；标注“推断”的内容给出推理链。仓库内事实一律引用仓库相对路径，外部事实一律引用 URL。

---

## Part A：端到端生产级 GAP 审视

### A.0 基准与判定框架

生产级基准取自四个公开准则源（均为 2026-09-13 抓取）：

- OpenSSF Best Practices Passing（tier 0）全部 67 条 criteria：https://www.bestpractices.dev/en/criteria/0
- OpenSSF Best Practices Silver（tier 1）增量 criteria：https://www.bestpractices.dev/en/criteria/1（注册前映射见 `docs/research/2026-09-13-openssf-best-practices-draft.md`，本文不复述其 Passing 答案表，只在其结论之上做生产级外推）
- OpenSSF Scorecard 各 check 的官方定义与计分规则：https://github.com/ossf/scorecard/blob/main/docs/checks.md
- SLSA v1.0 Build Levels：https://slsa.dev/spec/v1.0/levels ；发布纪律另参照 Keep a Changelog（https://keepachangelog.com/en/1.1.0/）与 SemVer（https://semver.org/），`CHANGELOG.md` 第 3 行已声明遵循两者。

严重度定义（针对“开源 skill 目录的生产级”）：

- **P0**：不解决就不能声称生产级。典型形态是单点故障会同时打断安全响应、发布与演化能力。
- **P1**：生产级的重要缺口，有真实风险或让公开声明弱于现状能力，应在可见周期内补。
- **P2**：改善项。不含本仓库已满足的建议——每个维度先列“已有”，缺口清单只收尚未满足的项。

当前 Scorecard 快照（已验证，API：https://api.securityscorecards.dev/projects/github.com/TeFuirnever/azhou-ai-hub ，commit `12c7838`）：总分 6.9。10 分项：Dependency-Update-Tool、SAST、Security-Policy、Vulnerabilities、Pinned-Dependencies、Token-Permissions、Binary-Artifacts、Dangerous-Workflow、License、CI-Tests。非满分项：Code-Review 0（"Found 0/30 approved changesets"）、Maintained 0（仓库创建不足 90 天）、CII-Best-Practices 0、Fuzzing 0、Branch-Protection 4、Contributors 3、Packaging -1、Signed-Releases -1。

### A.1 供应链与发布

**已有（已验证）**：

- 6 个 workflow 全部最小权限、全 job timeout、action 40 位 SHA pin（`.github/workflows/*.yml`；且 `scripts/check_repository.py` 的 `check_action_pins` 在仓库策略层二次强制）。
- 发布走手动 `Draft release` workflow：仅允许 `main` 触发、SemVer 正则校验、先跑 `verify.py --promotion-evidence` 完整门禁、只创建 draft（`.github/workflows/release.yml`）；发布前 checklist 在 `docs/releasing.md`，明确“不重写已发布 tag”。
- 仓库级 SemVer + Keep a Changelog 人工条目（`docs/releasing.md`、`CHANGELOG.md`）。
- 已有 9 个已发布 release（v0.1.0–v0.9.0，GitHub API `releases?per_page=20` 实查），全部零 assets——纯源码分发，无二进制制品。
- SBOM/provenance 的延后在 `docs/roadmap.md` 是显式决策：“Generate SBOM/provenance artifacts when the project ships downloadable release artifacts, not before”。

**对照 SLSA 与 `signed_releases` 的评估**：

- SLSA v1.0 的 L1–L3 约束对象是“构建产出的 artifact”及其 provenance（levels 页：L1 要求 provenance 存在、L2 要求 hosted build service 加签名 provenance、L3 要求隔离加固构建）。本仓库不产出构建 artifact——分发物就是受版本控制的源码树本身，构建来源即 git 历史。因此在“没有可下载制品”的现状下，SLSA build levels 与 SBOM 没有可作用的对象，`docs/roadmap.md` 的延后在 SLSA 语义范围内是可辩护的（推断：基于 SLSA 的适用范围 + 已验证的零 assets 发布现状）。
- Scorecard `Signed-Releases` 定义（checks.md）：扫描最近 release 的 assets 找签名文件（`*.minisig`/`*.asc`/`*.sigstore` 等），并且“ignoring GitHub's automatic source-code-only releases”。本仓库 -1 是“无可判定对象”的非结论值而非 0 分失败；`Packaging` -1 同理（未检出发布到包注册中心的 workflow）。所以这两项不是“做了会扣分的坏事没做”，而是“尚未到适用条件”。
- 真正的生产级残余风险在**消费侧 pinning 指引**：`README.md` 与 `docs/installation.md` 的 `npx skills add TeFuirnever/azhou-ai-hub --skill <name>` 命令全部不带 tag/ref，消费者默认安装可变默认分支；“This path has no repository-owned receipt”（`docs/installation.md`）。`docs/releasing.md` 的 checklist 要求 release notes 含 skill digests，但没有一份文档教消费者如何拿 digest 核对已安装内容。源码分发 + HTTPS + git 历史满足 BP `delivery_mitm`，但“可变 ref 安装”留给消费者的是一条未加固的信任路径（已验证：两份 README 的安装命令均无 ref；缺口的定性为推断）。

**缺口与定级**：

| 缺口 | 级别 | 下一步 |
|---|---|---|
| 消费者安装无可变 ref 之外的核对指引（digest 核对、tag pin 说明缺失） | P1 | 在 `docs/installation.md` 增补“验证你安装的内容”一节：按 release notes 的 skill digest 核对，或以 tag 为准安装；这是一次纯文档变更 |
| 签名发布路径未演练（`docs/releasing.md` 自己声明“Signed tags remain a target until ... a real release rehearsal”） | P1（当且仅当开始附带可下载制品时升 P0） | 做一次带 sigstore/签名的 release rehearsal（可用空 assets 的 draft release 验证流程），把结果记入 evidence |
| SBOM/provenance 无触发条件定义 | P2 | 在 roadmap 给“downloadable artifacts”一个可判定定义（例如任一 release 附带非源码 asset 即触发），使延后条件可机械检验 |
| v0.7.0 tag 缺失：`CHANGELOG.md` 有 `[0.7.0] - 2026-09-07` 段，但 `git tag -l` 与 `git ls-remote --tags origin` 均无 `v0.7.0`（已验证；v0.8.0 起已恢复连续） | P2 | 维护者决策：为历史 commit 补 tag + release，或在 CHANGELOG 注明该版本未发布；不补则 `version_tags` 的 Passing 作答留一处软点 |

### A.2 测试

**已有（已验证）**：

- 确定性门禁 `scripts/verify.py` 编排 8 道检查：仓库策略（`scripts/check_repository.py`，725 行、17 类检查，含 `check_secret_patterns`、`check_action_pins`、`check_fidelity_axis`、`check_rename_residue`）、unittest 全量（`tests/` 43 个文件、`def test_` 计数 469）、4 个 benchmark 完整性套件（super-repo-pedant / super-caveman 含 exact-diff 回放 / excalidraw / session-insights）、双空白检查；`--promotion-evidence` 追加 Git 外部晋升证据认证。
- CI 双平台强制：`ci.yml` 在 ubuntu（Python 3.11 与 3.14 矩阵）跑单测，windows-latest 跑完整 `verify.py`，`Required` 聚合 job 硬性要求全部通过；Scorecard `CI-Tests 10`（30 个 PR 全部带测试）。
- Fuzz：`scripts/fuzz_relay_state.py` 对 Super Lavish relay 状态解析器做种子化变异，`fuzz.yml` 每次 PR/push 短跑 + 周度 540 秒深跑；曾发现并修复 5 类真实崩溃（`docs/research/2026-09-13-openssf-best-practices-draft.md` Analysis 节）。

**缺口与定级**：

- **覆盖率度量缺失**：全仓无 coverage 统计，“466+ 单测”是绝对数而非覆盖率声明；BP Silver `test_statement_coverage80` 因此不可作答（draft 已如实记录）。生产级要求知道“脚本与解析器的哪部分没有测试”，而不是只有通过数。**P1**。下一步：CI 加一条 coverage 上报 job（仅统计、暂不设阈值阈值线可后定），先得到基线。
- **行为级 benchmark 未成体系**：注册进门禁的 4 个套件都是 integrity/wiring 性质；README 明确标注 “No behavior benchmark yet” 的包有 eli5、ask-azhou、autoresearch、session-insights（`README.md` Skills 表）；唯一有行为级（attempt-1 真跑 + paired judges）证据的是 super-caveman。这与仓库的诚实分级一致，但生产级需要的是“每个包的行为证据-tier 有一条可见的补齐路径”，目前该路径只存在于 super-caveman 的 promotion 机制中。**P1**。下一步：给四类包各立一个最小行为 eval-case 契约（冻结 prompt/runtime/时限/权限的 attempt-1 单例即可起步，`docs/skill-standard.md` §4 已有规范），按 roadmap 转成 `good first issue`。
- **回归率追踪缺失**：BP Silver `regression_tests_added50`（改动伴随回归测试的比例）无度量。**P1**，可并入覆盖率 job 一起做（按 PR 统计“行为变更 PR 是否携带 tests/ 变更”的比率）。
- arch-doc 的 benchmark runner（`benchmarks/arch-doc/run_case.py` + `evidence/arch-doc-benchmark-receipt-2026-09-04.json`）未注册进 `verify.py`/`ci.yml`（grep 零命中，已验证），golden case 只是一次性回据。**P2**。
- 本地 `verify.py` 不含 fuzz 腿（`commands()` 列表可证），交付前本地验证面与 CI 不完全一致。**P2**。
- 观察到一处 README 与门禁的计数出入：`README.md` Develop 节称 “five public benchmark-integrity suites”，而 `scripts/verify.py` 注册的是 4 个 benchmark 套件。本文不做裁决（可能计数口径不同），留给维护者核对，属文档准确性项。**P2**。

### A.3 代码评审与治理

**已有（已验证）**：`GOVERNANCE.md` 定义 maintainer/contributor/reviewer 三角色、lazy consensus + 六类 material change 显式批准清单；`.github/CODEOWNERS` 全路径指向 `@TeFuirnever`；skill 行为演化链（隔离候选、3 名独立 paired judges 奇数多数、A/B 反序、exact-diff 人类批准）在 `docs/skill-standard.md` §5 与 `GOVERNANCE.md` 固化——这套演化治理严于多数同规模项目。`CODE_OF_CONDUCT.md`、`SUPPORT.md`、`CONTRIBUTING.md` 齐备（已验证存在）。

**缺口与定级**：

- **bus factor = 1（P0，唯一的生产级阻塞项）**：Scorecard `Code-Review 0`（0/30 approved changesets）与 `Contributors 3` 都是同一个事实的投影：单人维护者自合自并。checks.md 明确 bot 评审（含 AI 评审）不计入 Code-Review，因此这个 0 分在第二个人出现前结构性地不可修复。更重要的是它同时是安全响应单点——`SECURITY.md` 的 3/7/14 天响应目标、`--promotion-evidence` 的 Git 外部证据、release draft 的人工审核全部压在一个账号上；账号被盗即同时失去发布、安全响应与晋升认证能力。`access_continuity`（Silver）与 issue #27（2026-08-23 开，“Raise OpenSSF governance maturity”，gh API 已验证）指向同一件事。下一步：按 `docs/roadmap.md` “Next” 的 good-first-issue 路线引入外部贡献者，并培养/授权一名第二 trusted maintainer（得到 admin 或至少安全响应与发布权限），之后 Branch-Protection 打开 required reviewer。
- **dco 缺失**：`CONTRIBUTING.md` 只有 inbound-license 声明，无 `Signed-off-by` 机制。P2（draft 已列为低成本可补）。
- Branch-Protection 4/10：已有 force-push/删除保护与 `Required` check，缺 required reviewer 与 admin enforcement——这一项在第二维护者到位前**不该**打开（会阻塞单人日常合并），到位后自动补齐。P1（时序依赖上一项）。

### A.4 安全态势

**已有（已验证，除特别标注）**：CodeQL 双语言（python + javascript-typescript）随 push/PR + 周扫（`.github/workflows/codeql.yml`，Scorecard SAST 10）；dependency review 高危即 fail（`.github/workflows/dependency-review.yml`）；Scorecard 周度发布（`scorecard.yml`）；secret scanning 与 push protection 开启（来源为 `docs/research/2026-09-13-openssf-best-practices-draft.md` 与 issue #27 的维护者陈述，仓库文件无法独立复核——标注为维护者断言）；私有漏洞披露通道 + 3/7/14 天响应目标（`SECURITY.md`，Scorecard Security-Policy 10）；策略层密钥形状扫描（`check_secret_patterns`）；一处 fuzzer 带崩溃回归闭环。

**缺口与定级**：

- **包管理器安装路径的端到端验证不足（P1）**：`docs/installation.md` 明说 npx 路径 “has no repository-owned receipt; verify discovery and invocation in the target harness”；现有公开安装回据只有 `evidence/public-install-smoke-2026-08-23.md`（2026-08-23、两个 skill、单 harness）。十四包 × 三 harness 的矩阵靠 checkout-managed 路径的回据支撑，包管理器路径实质上只有一次抽样。下一步：按 release 节奏做一次“从公开 npx 路径安装全部十四包并在三 harness 中发现”的冒烟回据（只读、可脱敏入库）。
- **动态分析覆盖面窄（P2）**：fuzz 只盖 relay 状态解析器；session-insights 的 metadata cache、`azhou_hub.py` 的 plan/receipt 解析等同类“解析不可信输入”的纯函数面未纳入。模式已验证可行（`fuzz_relay_state.py` 即模板），扩面是机械工作。
- **无对抗性/滥用评审记录（P1）**：`docs/` 与 `evidence/` 中没有任何对 npx 分发路径、receipt 解析（v1→v2 升级路径）或 hook fragment 渲染的对抗性审视记录（已验证：目录内无此类文档）。这套机制本身有防御设计（planId 绑定、digest、identity guard），但“没人记录过试图攻破它”与“它被攻不破”是两回事。下一步：一次具名 threat-review pass，产出与 `SECURITY.md` scope 对齐的记录（可 Git 外或脱敏入库）。
- `release.yml` 的 `contents: write` 是 Scorecard Token-Permissions 唯一 warning；draft 创建需要它，属合理最小授权。**不计入缺口**（列在此处仅为完整性：如追求满分可改用 environment 约束的 fine-grained token）。

### A.5 分发与兼容性

**已有（已验证）**：三种安装路径 + one-path rule（`docs/installation.md`）；`docs/support-matrix.md` 按行声明“已验证/主机依赖/不声明”并把回据文件逐一挂上；OS 维度有独立表：verify 门禁 Linux 强制 + Windows 强制（win-13 后翻正，`evidence/windows-ci-receipt-2026-09-09.md`）+ macOS 逐次维护者实机验证；仓库根目录无任何运行时依赖清单（`requirements*.txt`/`pyproject.toml`/`package.json`/`uv.lock` find 零命中，已验证）——“无 lockfile”对门禁而言是伪问题，因为门禁是纯标准库；真实存在的依赖都在 skill 内部声明并锁定（excalidraw 的 uv/npm 锁定文档、lavish 的 `lavish-axi@0.1.47` 哈希锁定，`docs/installation.md` §Skill-specific dependencies）；Dependabot 覆盖 actions 与 excalidraw 的 npm/pip 目录（`.github/dependabot.yml`）。

**缺口与定级**：

- **Windows 全流程回据未闭环（P1）**：`docs/installation.md` 自认 “A checked-in Windows full-flow receipt (info → setup → verify) is not yet available; it is tracked by the win-05-rerun-receipt ticket”。CI 的 Windows 腿已强制，但“用户在真实 Windows 上从安装到 verify 走通”的入库回据还缺最后一步。
- **Harness 回据覆盖不均（P2）**：arch-doc 在支持矩阵自认 “no host discovery/invocation receipt yet”；eli5/autoresearch 有 Codex+zcode 回据、缺 Claude 列回据（矩阵行如实标注）。按矩阵自己的“Supported = 有确定性检查或真实 adapter 回据”标准，这些行已诚实，生产化只是补齐。
- **宿主依赖下界的文档口径不一（P2）**：`docs/installation.md` 开头写 “Python ≥3.10 required”（针对 checkout-assisted 示例），同文档后文与 `docs/support-matrix.md` 写 Foundation Skills 需要 3.11+，super-caveman 压缩是 3.10+。哪个数字对 `scripts/azhou_hub.py` 成立本文未验证；建议一次核对并统一为单一口径。

### A.6 文档与采用

**已有（已验证）**：双语 README 镜像且有同提交同步规则（`docs/architecture.md` 权威表）；`docs/architecture.md`（67 行）与当前门禁/回据两层结构一致，本次通读未发现过期陈述；`docs/skill-standard.md` 作为单一项目权威；六份 demo 文档（`docs/demos/`）；研究笔记沉淀在 `docs/research/`（含本文）。

**缺口与定级**：

- 无生成式 CLI/API 参考：`scripts/azhou_hub.py` 的子命令面只有 `docs/foundations.md` 的散文合同与 `--help`。包数量与 CLI 面还在增长，手写合同的漂移风险随规模上升。**P2**：从 argparse 定义生成或用测试锁定的命令表。
- 无版本化文档站：`docs/roadmap.md` 已显式推迟（“repository remains the authority”），与仓库即权威的模型自洽。**不视为缺口**。
- 采用信号缺失（P2）：隐私优先（无遥测是设计而非缺陷），当前采用可见性只有 GitHub stars/issues；一个 opt-in 的“谁在用”Discussion 或 issue 模板是零风险替代。此条为可选改善，非生产级必要项。

### A.7 可观测性与维护信号

**事实（已验证）**：仓库首 commit 2026-08-22（`git log --reverse`），快照日仅 22 天——Scorecard `Maintained 0` 是“仓库不足 90 天”的机械判定（checks.md：仅对创建满 90 天的项目评估活跃度），不是活跃度下降。实际节奏（日均多次提交、每周一 Dependabot、周度 Scorecard/CodeQL/fuzz）已满足甚至远超“每周一 commit”的满分线，90 天窗口（约 2026-11-20）自然翻绿，无需任何动作。`Contributors 3` 需要“最近 30 commit 内 3 家公司各 ≥5 commits”（checks.md），只能随外部贡献者增长。**这两个分数的处方不是工程，是时间与人**——与 A.3 的 P0 是同一件事。

### A.8 优先级总表

| # | 级别 | 维度 | 事项 | 为什么是生产级必需 | 具体下一步 | 归属 |
|---|---|---|---|---|---|---|
| 1 | P0 | 治理 | bus factor=1：第二 trusted maintainer 与权限续备 | 安全响应、发布、晋升认证同压一个账号；Code-Review/Contributors/Branch-Protection 三项分数结构性冻结于此 | 按 roadmap good-first-issue 引流；授权第二维护者并演练一次安全响应分工 | maintainer |
| 2 | P1 | 分发 | 包管理器安装路径的公开回据 | 公开入口路径只有一次 2026-08-23 抽样，且自认无 receipt | 按 release 节奏做全量十四包 × 三 harness 冒烟回据 | maintainer |
| 3 | P1 | 供应链 | 消费侧 digest 核对 / tag pin 指引 | 可变默认分支安装把信任链终点交给消费者却没给工具 | `docs/installation.md` 增补核对章节；release notes 固化 skill digest | maintainer |
| 4 | P1 | 测试 | 覆盖率与回归率度量基线 | Silver `test_statement_coverage80`/`regression_tests_added50` 不可作答；不知盲区在哪 | CI 加 coverage 上报（先度量后设阈） | maintainer |
| 5 | P1 | 测试 | 四类 “No behavior benchmark yet” 包的最小 eval-case 路径 | 生产级目录要求每包有可见的证据补齐路径，而非仅 super-caveman 有 | 立最小行为 eval-case 契约并转 issue | maintainer + community |
| 6 | P1 | 安全 | 分发路径与 receipt 解析的具名 threat-review | 防御设计存在但无对抗性审视记录 | 一次具名评审 pass，结论脱敏入库 | maintainer |
| 7 | P1 | 兼容 | Windows 全流程回据（win-05） | 最后一块 OS 声明与用户实况之间的空档 | 在真机或 CI runner 上产出 info→setup→verify 回据 | maintainer |
| 8 | P1 | 供应链 | 签名发布 rehearsal | `docs/releasing.md` 自认的目标；一旦出现可下载制品即升 P0 | 空 assets draft release 演练 sigstore/签名并留回据 | maintainer |
| 9 | P2 | 治理 | DCO 机制 | Silver `dco`；低成本 | CONTRIBUTING 增 Signed-off-by 约定 | maintainer |
| 10 | P2 | 测试 | fuzz 扩面 + 本地 verify fuzz 腿 + arch-doc 套件注册 | 动态分析面与门禁面一致化 | 机械扩三项 | maintainer |
| 11 | P2 | 发布 | v0.7.0 tag 缺档决策；SBOM 触发条件可判定化；README “five suites” 计数核对 | 发布纪律的边角一致性 | 三个小决策各一次提交 | maintainer |
| 12 | P2 | 兼容 | Python 下界口径统一；arch-doc/eli5/autoresearch 的缺列 harness 回据 | 声明面精确性 | 核对后统一文档；按矩阵补回据 | maintainer |

---

## Part B：autoresearch 能否支持非 NVIDIA GPU

### B.1 上游 pinned commit 实际包含什么

对象：`karpathy/autoresearch` @ `228791fb499afffb54b46200aca536f79142f117`（`skills/autoresearch/references/setup.md` 与 `provenance.md` 记录的 pin）。文件树经 GitHub API 实查共 10 个文件：`.gitignore`、`.python-version`（内容 `3.10`）、`README.md`、`analysis.ipynb`、`prepare.py`、`program.md`、`progress.png`、`pyproject.toml`、`train.py`、`uv.lock`（https://api.github.com/repos/karpathy/autoresearch/git/trees/228791fb499afffb54b46200aca536f79142f117 ）。树内**没有 LICENSE 文件**（与 `skills/autoresearch/references/provenance.md` 的记录一致；GitHub repo API 的 license 字段为 null，已验证）。README 声明仓库实质只有三个文件：`prepare.py`（固定数据准备/评测，禁改）、`train.py`（agent 唯一可改的训练单文件）、`program.md`（agent 指令）；训练目标是 nanochat 的单 GPU 简化版，固定 5 分钟墙钟预算，指标 `val_bpb`。

README 的平台声明（原文，https://raw.githubusercontent.com/karpathy/autoresearch/228791fb499afffb54b46200aca536f79142f117/README.md ）：

- “**Requirements:** A single NVIDIA GPU (tested on H100), Python 3.10+, uv”；
- “This code currently requires that you have a single NVIDIA GPU. In principle it is quite possible to support CPU, MPS and other platforms but this would also bloat the code.”——即作者明确知道如何支持但**选择不支持**；
- README 列出了四个社区 fork：`miolini/autoresearch-macos`（macOS）、`trevin-creator/autoresearch-mlx`（macOS/MLX）、`jsegov/autoresearch-win-rtx`（Windows）、`andyluo7/autoresearch`（AMD）。

### B.2 pinned 代码的 GPU/后端假设逐条清单（已验证，逐行）

`train.py`（https://raw.githubusercontent.com/karpathy/autoresearch/228791fb499afffb54b46200aca536f79142f117/train.py ）：

| 位置 | 代码 | 后端含义 |
|---|---|---|
| :21 | `cap = torch.cuda.get_device_capability()` | **import 期硬调用**，无任何 guard。CPU/MPS 构建上此调用即异常，`train.py` 连 import 都过不去 |
| :22-24 | FA3 kernel 从 HF hub 拉取：`cap == (9, 0)` 用 `varunneal/flash-attention-3`（注释：“Hopper only”），否则 `kernels-community/flash-attn3` | 两个分支都是 NVIDIA CUDA 架构专属 kernel；无第三分支 |
| :93 | `fa3.flash_attn_func(...)` | attention 前向完全绑定该 kernel 接口 |
| :459 | `torch.cuda.manual_seed(42)` | CUDA API |
| :461 | `device = torch.device("cuda")` | 设备硬编码，无 autodetect |
| :462 | `torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16)` | autocast device_type 硬编码 cuda + bf16 |
| :463 | `H100_BF16_PEAK_FLOPS = 989.5e12` | MFU 分母是 H100 峰值（:587、:618 使用）——非 H100 设备上 mfu% 数值失真（美观性问题，不影响正确性） |
| :544、:574 | `torch.cuda.synchronize()` | CUDA 计时同步 |
| :619 | `torch.cuda.max_memory_allocated()` | CUDA 显存统计 |
| :305、:316、:508 | `@torch.compile`/`torch.compile(model, dynamic=False)` | 优化器步 fullgraph 编译 + 模型编译 |
| :8 | `PYTORCH_ALLOC_CONF=expandable_segments:True` | CUDA allocator 配置 |
| :179-191 | 权重/rotary 显式 cast `bfloat16` | bf16 精度假设 |

`prepare.py`（同 pin，https://raw.githubusercontent.com/karpathy/autoresearch/228791fb499afffb54b46200aca536f79142f117/prepare.py ）：

| 位置 | 代码 | 后端含义 |
|---|---|---|
| :298-299 | `cpu_buffer ... pin_memory=True`；`gpu_buffer = torch.empty(..., device="cuda")` | dataloader 的 H2D 暂存缓冲硬编码 cuda；pinned memory 依赖 CUDA 主机语义 |
| :336 | `gpu_buffer.copy_(cpu_buffer, non_blocking=True)` | 异步拷贝配对 pinned buffer |
| :352 | `get_token_bytes(device="cuda")` | 评测辅助张量硬编码 cuda |

环境锁定（`pyproject.toml`，同 pin）：

- `torch==2.9.1`，且 `[tool.uv.sources]` 把 torch 强制指到显式 index `pytorch-cu128`（https://download.pytorch.org/whl/cu128 ）。该 index 上 torch 2.9.1 的 wheel 只有 manylinux（x86_64/aarch64）与 win_amd64 三类，**macOS wheel 为零**（index 页实查：linux 28 个、win_amd64 14 个、macosx 0 个）。据此推断：在 macOS 上按 pin 的 `uv sync --locked` 连 torch 都解析不到 wheel（推断依据：uv 显式 index 语义 + 已验证的 wheel 清单；未实机复现）。
- 隐含结论：这个锁不仅是“运行时假设 CUDA”，是“**安装期**就锁定 CUDA 构建的 PyTorch”。

一个容易误读的点：上游代码本身**从不调用 `nvidia-smi`**。`nvidia-smi` 探针是 hub wrapper 自己的预备检查（`skills/autoresearch/references/setup.md` 的最小环境表），上游的做法更简单——不检查，直接在 import 期崩。两者的失败面不同：wrapper 在任何步骤前就能拦住，上游会跑到 Python import 才炸。

### B.3 对照：父项目 nanochat 的平台支持（默认分支 master，2026-09-13 抓取）

autoresearch 的训练目标简化自 nanochat；nanochat 在同一批“CUDA 假设”上全部留了非 CUDA 路径（文件路径均在 https://github.com/karpathy/nanochat master）：

- 设备自动探测：`nanochat/common.py:163-172` `autodetect_device_type()`——`cuda → mps → cpu` 三选；`compute_init` 断言 `cuda|mps|cpu`。
- 精度策略：README 的 dtype 表——“CUDA SM 80+ → bfloat16；CUDA SM < 80 → float32（可 `NANOCHAT_DTYPE=float16`）；CPU / MPS → float32 安全默认，近期 macOS 上 MPS 跑 `NANOCHAT_DTYPE=bfloat16` 也没问题”。
- attention：`nanochat/flash_attention.py` 的 docstring 自述“falls back to PyTorch SDPA on incompatible CUDA GPUs, MPS, and CPU”；FA3 kernel 只为 Hopper（sm90）、Ada（sm89）、Ampere（sm80/sm86）编译，Blackwell sm100 也走 SDPA fallback。
- FP8：`scripts/base_train.py:169-170` 明确 “FP8 training requires CUDA, ignoring --fp8 flag”。
- 官方 CPU/MPS 入口：`runs/runcpu.sh`（`uv sync --extra cpu`；脚本自述“你在 Macbook 上走不远，这是教育性 demo”，在 M3 Max 上调好一个 6 层/512 上下文的小模型约 30 分钟）。
- README 的诚实边界原话：“Most of the code is fairly vanilla PyTorch so it should run on anything that supports that - xpu, mps, or etc, but I haven't personally exercised all of these code paths so there might be sharp edges.”

结论（已验证）：**非 NVIDIA 路径在父项目里逐件存在，autoresearch 是有意裁剪掉它们换极简**——autoresearch README 的 “Platform support” 节就是这个裁剪的作者自述，并把想要非 NVIDIA 平台的人指回 nanochat 与社区 fork。

### B.4 PyTorch 非 CUDA 后端官方文档要点（2026-09-13 抓取）

- **ROCm**（https://docs.pytorch.org/docs/2.14/notes/hip.html ）：“PyTorch for HIP intentionally reuses the existing torch.cuda interfaces”，设备字符串仍写 `'cuda'`，`torch.cuda.is_available()` 在 GPU 构建上为真，用 `torch.version.hip` 区分。即：ROCm 上 `torch.cuda.*` API 面不必改；该页未给出操作系统支持矩阵（不外推）。
- **MPS**（https://docs.pytorch.org/docs/2.14/notes/mps.html ）：`mps` 设备为 macOS + Metal 提供 GPU 训练；可用性要求 macOS 14.0+ 且 MPS-enabled device（`torch.backends.mps.is_built()/is_available()`）。该页未记载 torch.compile 支持与 dtype 覆盖矩阵（不外推；MPS bf16 的可用性引用 nanochat README 的经验陈述）。
- **XPU（Intel GPU）**（https://docs.pytorch.org/docs/2.14/notes/get_start_xpu.html ）：自 PyTorch 2.5 起为 **Prototype**；支持 Data Center GPU Max、Arc A/B 系与 Core Ultra 核显；Linux 与 Windows（client GPU；Windows 上 torch.compile 需 2.7+）；官方稳定安装走 `--index-url https://download.pytorch.org/whl/xpu`；eager 与 torch.compile 均可用，FP32/BF16/FP16/AMP 支持；迁移“typically just swapping `"cuda"` for `"xpu"`”。

把 B.2 的逐条清单映射到三个后端，pinned 代码的断点：

| 后端 | 安装期 | 运行期断点（行号见 B.2） |
|---|---|---|
| Apple Silicon / MPS | cu128 index 无 macOS wheel，锁定环境大概率装不上（推断，见 B.2） | 即使换源装上：`train.py:21` import 期 `torch.cuda.get_device_capability()` 即崩；:461/:462/:459/:544/:619 与 `prepare.py:299/:352` 全链 CUDA API；FA3 kernel 无 MPS 分支；`torch.compile` 在 MPS 的支持状态官方 MPS 页未记载 |
| AMD / ROCm | cu128 index 无 ROCm wheel；锁死的 `pytorch-cu128` 源给出的是 CUDA 构建（已验证 index 清单 + pyproject） | ROCm 构建下 `torch.cuda.*` 面可用（hip 页），代码里**没有任何 ROCm 分支**；FA3 hub kernel 是 CUDA 编译产物，能否在 ROCm 加载无任何一方文档背书（推断，标为未验证） |
| Intel / XPU | cu128 index 无 xpu wheel，需换 `whl/xpu` 源（XPU 文档） | `torch.cuda` API 不被 XPU 别名（XPU 用 `torch.xpu`），`train.py:21` import 期即崩；FA3 同样无 XPU 分支 |
| CPU | cu128 index 有 manylinux wheel 可装（装的是 CUDA 构建，无驱动时 CUDA 不可用） | :21/:461 等全链崩；无 CPU 路径（上游自述） |

一句话结论：**pinned autoresearch 对非 NVIDIA 后端是安装期 + import 期双重硬失败，且这是上游的显式设计决策，不是疏忽。**

### B.5 hub wrapper 的现有合同与回据

- `skills/autoresearch/SKILL.md`：workflow 第 1-2 步要求 pin 校验与 `mode=prepare` 环境，“Every missing check fails closed; no partial state is reported as ready”；无任何 CUDA-ready 状态可以在非 NVIDIA 主机上产生。
- `skills/autoresearch/references/setup.md`：最小环境表第一行 “NVIDIA CUDA GPU; the upstream README documents a single-GPU setup tested on H100, and **other GPUs are unverified**”，检查 `nvidia-smi`，失败边界 “fail closed ... do not start a CPU fallback run”。
- `skills/autoresearch/references/provenance.md`：上游无 LICENSE → 零上游字节 vendor，实验协议运行时从用户 checkout 读取。
- 回据（已验证存在且内容一致）：`evidence/autoresearch-load-fail-closed-zcode-2026-09-03.md`（Apple M5，`nvidia-smi` 缺失，prepare 停在 CUDA 检查，receipt `status: fail`）与 `evidence/autoresearch-load-fail-closed-codex-2026-09-04.md`（`nvidia-smi` exit 127，同结论）。`docs/support-matrix.md` 的对应行把第三列写成 “host-dependent; requires ... NVIDIA CUDA GPU and uv”。

### B.6 三个选项的对照结论

| 选项 | 内容 | 可行性（源码依据） | 工作量 | 与 claim discipline 的相容性 | 改公开声明前需要的证据 |
|---|---|---|---|---|---|
| (a) 维持 NVIDIA-only fail-closed（现状） | 不动 | 已验证现状即此状态；上游 import 期硬失败与 wrapper 探针互相印证 | 零 | 完全相容；support matrix “other GPUs are unverified” 如实 | 无需（现有两份 fail-closed 回据已覆盖） |
| (b) wrapper 层诚实探测非 NVIDIA 加速器，报告 `unsupported` 而非笼统失败 | prepare 阶段在 `nvidia-smi` 缺失时追加识别（如 macOS `system_profiler`、Linux `rocm-smi`/`amd-smi`、`xpu-smi` 或仅报告“无 NVIDIA 设备”），receipt 的 holds 写明 `unsupported: detected <accelerator kind>; upstream supports NVIDIA CUDA only`，仍不启动任何运行 | 可行：wrapper 是 Azhou 自有文本，零上游字节（provenance.md），不触碰上游代码；探测只读主机信息。注意：这不改变“不支持”的结论，只把失败原因从 `nvidia-smi` 缺失升级为“检测到非 NVIDIA 加速器 X，上游限定 NVIDIA” | 小：改 SKILL.md/setup.md 文本 + 保持 package-surface 门禁与品牌合同测试绿（`scripts/check_repository.py` 既有合同；autoresearch 非 super-caveman，不涉及 promotion receipt 重绑，已验证 verify.py 的套件清单） | 相容：support matrix 行无需翻正（仍 unverified），只是失败报告更精确；符合 §4 “skipped/hold 不得升级为 pass” | 每类探测路径各一份真实回据（格式同现有两份 fail-closed 回据）；若宣称“能识别出某具体加速器”，该主机实测 |
| (c) 非 NVIDIA 真支持 | 三个子路径：<br>(c1) 指向上游 README 认可的社区 fork（macos/mlx/win-rtx/AMD）；<br>(c2) 在 MIT 的 nanochat 上做 hub 自有 wrapper/移植（GitHub license API 实查 nanochat 为 MIT）；<br>(c3) 给上游提 PR 引入 generic device（nanochat 已示范全部零件：autodetect、SDPA fallback、dtype 表、runcpu.sh） | (c1) 可行但 fork 同样继承“上游无 LICENSE”状态（fork 不产生许可），只能链接、不能 vendor；且 fork 破坏 pin 合同（setup.md 要求 HEAD 等于 pin）。<br>(c2) 技术可行（B.3/B.4 的零件齐全），但这是一个新产品：新 pin、新 provenance、新评测面。<br>(c3) 长期最正，但受制于上游维护者意愿与 hub 的无 GPU 测试面 | (c1) 小（纯文档）；(c2) 大（等同新增一个 canonical skill + 行为证据链）；(c3) 大且不可控 | (c1) 相容（“链接”不是“支持声明”）；(c2)(c3) 只有在拿到真实 GPU 回据后才允许任何 “runs on X” 声明——当前仓库无任何非 NVIDIA 训练回据，maintainer 自身主机即 Apple Silicon，(c2) 的每一步验证都缺硬件 | 任何 “runs on ROCm/MPS/XPU/CPU” 声明：对应后端一次完整 prepare→train→val_bpb 的 attempt-1 回据（pinned commit、tree digest、运行时长、评测输出），并同步 support matrix 两列 |

**Part B 结论**：

1. “能否支持非 NVIDIA GPU”在 pinned autoresearch 上是明确否定——安装期（cu128 锁、macOS wheel 缺失）与 import 期（`train.py:21` 无 guard 的 CUDA 调用）双重硬失败，且上游 README 明说这是设计选择（B.1/B.2，已验证）。
2. hub wrapper 当前的 fail-closed 是两者中更诚实的一层：它在 Python 还没启动前就拦住，并有两份真实回据背书。
3. 现实的改进序列是 (a) → (b)：把“没有 nvidia-smi”的笼统失败升级为“检测到 <kind> 加速器，上游限定 NVIDIA，unsupported”的具名 hold——这在 claim discipline 内零风险，成本一个小 PR 加一份回据。(c) 的三个子路径在拿到跨后端真实回据之前都不应改变任何公开声明；其中 (c2) 若真要做，MIT 的 nanochat 是唯一许可干净的代码基底。
4. 一个值得记录的反直觉事实：maintainer 自己的日常主机（Apple M5，见两份回据）正是永久无法通过该 skill prepare 的主机——选项 (b) 至少能让这台主机上的失败报告变得对用户有用。

---

## 验证方式

- 仓库事实：本文引用的全部文件为 2026-09-13 在 `main@12c7838` 工作区直接读取；`git tag -l`/`git ls-remote --tags origin`/`git log --reverse`/GitHub releases API/469 计数（`grep -rc "def test_" tests/*.py` 求和）/依赖清单 find 均为当日实跑。
- 外部事实：OpenSSF Scorecard API、bestpractices.dev criteria/0、scorecard checks.md、slsa.dev levels、karpathy/autoresearch pinned tree 与四个文件原文、nanochat master 五个文件原文、PyTorch 2.14 三篇 backend 文档、download.pytorch.org cu128 torch index 页、两个上游仓库的 license API 字段，均为 2026-09-13 抓取。
- 未实机验证并如实标注为推断的三处：macOS 上按 pin 执行 `uv sync --locked` 的失败（基于 wheel 清单 + uv 显式 index 语义）、FA3 hub kernel 在 ROCm 的加载行为、`scripts/azhou_hub.py` 的 Python 下界（A.5 的口径不一问题）。
