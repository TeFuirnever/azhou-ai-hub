# 2026-11-18 super-repo-pedant 稳定来源更新记录（上游 v1.2.1 + v1.2.2）

本记录对应 skill-standard §1.2 Stable-source updates 通道：把 `super-repo-pedant` 的上游 neat-freak 参考基线从仓库 release `v1.2.0`（commit `cfa3436d4d31db9b1340af3082a914adf92f023f`）推进到 `v1.2.2`（commit `71cd50ffe1f1f4d400b54be967dc6b59379aff8f`），一次吸收 v1.2.1 与 v1.2.2 两个 release。实现于 Treehouse 租约（holder `repo-pedant-absorb-v122-20261118`，lease `cfea396e2b82c1e229f865b3ebec2978`）内的 `codex/absorb-repo-pedant-v1.2.2` 分支。这是稳定来源同步，不是 §5 受控演化通道；人工批准经 PR 评审完成。版本同步不声称模型任务质量提升。

## 稳定发布判定（自行重验，非转述）

以下证据均为本任务执行时通过 GitHub 官方 API 直接取得（`gh api repos/KKKKhazix/khazix-skills/...`）：

- `releases/latest` 返回 `v1.2.2`：`draft=false`、`prerelease=false`、`published_at=2026-11-12T10:12:21Z`；`target_commitish=71cd50ffe1f1f4d400b54be967dc6b59379aff8f`。
- `git/ref/tags/v1.2.2` 解引用为 `{sha: 71cd50ffe1f1f4d400b54be967dc6b59379aff8f, type: commit}` —— tag 直接指向该 commit，无歧义。
- `v1.2.1`（`releases/tags/v1.2.1`）同样非 draft、非 prerelease，`published_at=2026-11-10T20:17:28Z`。
- 仓库 release 与 skill 自身版本是两回事：`neat-freak/SKILL.md` 在 `71cd50ff` 的 frontmatter 仍声明 `metadata.version: "3.1.1"`（本任务下载该文件并逐行核验，第 7 行）。基线从 v1.2.0 → v1.2.2 只移动仓库 release 指针，skill 版本号不变。
- 上游仓库 MIT 许可证文件不在 `cfa3436d...71cd50ff` 的变更文件列表中；本地保留的 [Khazix-Skills-MIT.txt](../../LICENSES/Khazix-Skills-MIT.txt) 副本继续有效。

## 变更文件逐条处置

`compare/cfa3436d...71cd50ff`：6 个 commit、11 个变更文件（ahead 6 / behind 0）。逐条映射如下；neat-freak 相关仅 2 个文件，4 个快照 references 逐字节未变。

| 上游文件 | 引入 release / commit | 对 neat-freak 基线 | 处置 |
|---|---|---|---|
| `neat-freak/SKILL.md`（+1/−12） | v1.2.2 / `71cd50ff`（PR #78「正文不动」） | **唯一快照内容变化**：frontmatter description 由 12 行英文压缩为 1 行中文 | 快照 `SKILL.snapshot.md` 刷新为该 commit 原字节；`BASELINE_HASHES` 重锁 1/5 项。触发语义逐类核验保持（见下节）；兼容台账触发行措辞重述，分类不变 |
| `neat-freak/evals/validate.py`（+3/−2） | v1.2.2 / `71cd50ff` | 断言由英文字面（`knowledge-closeout intent`、`Do not trigger`）同步为中文字面（`知识收尾意图`、`不触发`）；上游注释自述「校验意图不变」 | 已按台账 Monitoring 规则完成能力复核：仅断言字面随 description 语言切换，验证意图与覆盖未变，无能力影响。evals 本就不在回归快照内（2026-10-07 审计已声明未取 eval fixtures），快照面不变 |
| `storage-analyzer/assets/report_template.html`（+17/−8）、`tests/test_storage_actions.py`（新增） | v1.2.1 / `10436815`（PR #80） | 属于另一 skill `storage-analyzer`，不属于 neat-freak 能力集 | 不采纳、不建行。部分失败重试（`remainingCleanupPaths` 只重试剩余路径）与批量/单项共用执行锁是 storage-analyzer 页面行为；本包的运行状态持久边界已由 runtime-state 合同（`<authorized-root>/.azhou/super-repo-pedant/`）覆盖，不引入第二套状态面 |
| `STATES.md`（新增）、`README.md`、`README.en.md` | v1.2.1 `10436815`/`bb5c20ad`、v1.2.0 后多篇 | 仓库级持久状态/写入入口/恢复边界说明与勘误，非 neat-freak 包内容 | 记录为观察；无映射对象 |
| `AGENTS.md`（新增）、`.gitignore` | `c8e89502`、`41038813`（PR #82/#83） | 上游仓库自身的 agent 规则与红线声明 | 记录为观察；不赋予本任务权限 |
| `leader/SKILL.md`（+1/−1） | v1.2.2 / `71cd50ff` | 另一 skill 的 description 压缩 | 不在 neat-freak 范围，不处置 |
| `.claude-plugin/marketplace.json` | v1.2.1/v1.2.2 版本号推进 | 仓库发布元数据 | 记录为观察 |

## 触发语义保持核验（v1.2.2 description 压缩）

逐类比对 v1.2.0 与 v1.2.2 的 description（本任务对两个版本文件做了逐行 diff，差异仅 description 块）：

- 点名触发：`neat-freak` / `洁癖` / `/neat` —— 两版一致。
- 意图触发类别：开发后同步文档与记忆、CLAUDE.md/记忆过期或冲突、交接前清场（v1.2.0 "a clean handoff to a teammate or a fresh session"）、审计规则是否被遵守 —— 四类全部保留；压缩删去了三个示例短语中的一个（「收尾时把文档同步掉」），保留「把文档和记忆整理一下」「docs 和代码对不上了」，类别语义不变。
- 负触发：纯写代码/重构/调试、整理数据或文稿（JSON、周报、changelog）、没有项目知识语境的裸「整理」—— 三类全部保留。

结论：压缩是措辞变化而非能力变化。台账触发行（`trigger-explicit-phrases`，分类 `restored`）已重述为 v1.2.2 措辞并注明压缩删例；本地更强的裸 `tidy/整理` 正触发分歧（`trigger-cases.json` `bare-tidy` → `reconcile`）与负向守卫保持不变，不因上游措辞切换而改动。

## 三方比较与保留面

按 §1.2 比较「原采用上游基线 v1.2.0 / 本地当前实现 / 目标 v1.2.2」：本地运行面（SKILL.md、scripts、references 运行合同）在本次 delta 中没有任何上游能力新增或语义变化需要迁移——唯一的 neat-freak 变化是 description 措辞压缩，本地入口本就携带更全的双语触发合同。全部本地增强保留：授权 checkpoint、Python inventory（上游 shell inventory 继续映射到它，不引入第二套扫描器）、exact-diff 人工门、Treehouse 租约、稳定回执、runtime-state 合同。28 项能力处置无一变动。

## 覆盖度量

| 度量 | 数值 |
|---|---|
| 快照哈希锁条目 | 5/5 重新核验：1 项刷新（`SKILL.snapshot.md` SHA-256 `1d5203e3ed52d8c5f57e4b44a3cc70b11be1891abde8ae865eeeed12682bd39e`），4 项 references 与 v1.2.0 逐字节一致（SHA-256 分别复核相等） |
| 兼容台账能力行 | 28/28：1 行措辞重述（触发），0 行分类变动，0 行新增/删除 |
| parity JSON | 基线三字段更新（release `v1.2.2`、commit `71cd50ff`、verified `2026-11-18`；skill 版本保持 `3.1.1`），28 行能力映射不变 |
| 本地运行时行为变化 | 0（无 SKILL.md 正文、scripts、references 运行合同的字节改动；仅 provenance/台账/基线记录更新） |

## 本任务执行的验证

- `gh api repos/KKKKhazix/khazix-skills/releases/latest`、`releases/tags/v1.2.1`、`releases/tags/v1.2.2`、`git/ref/tags/v1.2.2`、`compare/cfa3436d...71cd50ff`、`commits/<sha>`（逐 commit 文件清单与补丁）：判定与逐条处置的直接证据。
- 五个快照文件在 `71cd50ff` 的下载字节与 SHA-256 复核；`SKILL.snapshot.md` 刷新后哈希与 `BASELINE_HASHES` 新锁一致。
- `uv run --with pyyaml python ~/.zcode/skills/skill-creator/scripts/quick_validate.py <worktree>/skills/super-repo-pedant`：退出码 1，唯一发现是通用校验器不认本仓库 §2.2 frontmatter 合同键 `invocation`（允许键表仅 allowed-tools/description/license/metadata/name）。对照包 `skills/super-archify`（本次零改动）在相同命令下产生逐字相同的结果与退出码，证明这是仓库合同与通用校验器白名单的既有差异，非本次变更引入；本包 SKILL.md 本次零字节改动，新 description 仍是合法 YAML（校验器成功解析后才报键名问题）。该命令按 AGENTS.md 仅作开发期校验，不替代仓库门禁。
- `python3 -B -m unittest tests.test_super_repo_pedant_parity`：7/7 通过（补充自查，非门禁）。
- `python3 scripts/verify.py` 本次**未运行**（任务指令：统一门禁稍后由编排方执行）；PR head 的必需 CI 与评审线程是该门禁的一部分。

## 一手来源

- [Khazix Skills v1.2.2 正式发布](https://github.com/KKKKhazix/khazix-skills/releases/tag/v1.2.2)（commit `71cd50ffe1f1f4d400b54be967dc6b59379aff8f`）
- [Khazix Skills v1.2.1 正式发布](https://github.com/KKKKhazix/khazix-skills/releases/tag/v1.2.1)
- 先例：[2026-11-10-skill-upgrade.md](2026-11-10-skill-upgrade.md)、[2026-10-07-neat-freak-v3-capability-audit.md](2026-10-07-neat-freak-v3-capability-audit.md)
