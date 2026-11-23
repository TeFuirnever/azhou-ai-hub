# 2026-11-23 super-repo-pedant 稳定来源更新记录（上游 v1.3.0 + v1.3.1）

本记录对应 skill-standard §1.2 Stable-source updates 通道：把 `super-repo-pedant` 的上游 neat-freak 参考基线从仓库 release `v1.2.2`（commit `71cd50ffe1f1f4d400b54be967dc6b59379aff8f`，skill 3.1.1）推进到 `v1.3.1`（commit `76fc0f8e8245b40a809d8eed89b27f04cbcf81bb`，skill 4.0.0），一次吸收 v1.3.0 与 v1.3.1 两个 release，并分段核验（v1.2.2→v1.3.0 与 v1.3.0→v1.3.1）。实现于 Treehouse 租约（holder `upgrade-super-repo-pedant-20261123`）内的 `codex/upgrade-super-repo-pedant-20261123` 分支。这是稳定来源同步，不是 §5 受控演化通道；人工批准经 PR 评审完成。版本同步不声称模型任务质量提升。

## 稳定发布判定（自行重验，非转述）

以下证据均为本任务执行时通过 GitHub 官方 API 与本地 clone 直接取得：

- `releases/latest` 返回 `v1.3.1`：`draft=false`、`prerelease=false`、`published_at=2026-11-18T12:50:27Z`、`target_commitish=76fc0f8e8245b40a809d8eed89b27f04cbcf81bb`。
- `git/ref/tags/v1.3.1` 解引用为 `{sha: 76fc0f8e8245b40a809d8eed89b27f04cbcf81bb, type: commit}` —— tag 直接指向该 commit，无歧义。
- `v1.3.0`（`releases/tags/v1.3.0`）同样非 draft、非 prerelease，`published_at=2026-11-18T10:56:41Z`；tag 解引用为 `1cff16da300db915032a213b28bc7fbe91784986`（PR #85「按现在的模型重写五个 Skill 的指令（1.3.0）」）。
- 仓库 release 与 skill 自身版本是两回事：`neat-freak/SKILL.md` 在 `76fc0f8e` 的 frontmatter 声明 `metadata.version: "4.0.0"`（本地 clone 逐行核验）。skill 版本 3.1.1 → 4.0.0 是上游对指令重写的 major 标记。
- 上游仓库 MIT 许可证文件不在 `71cd50ff...76fc0f8e` 的变更文件列表中（`git diff --stat v1.2.2 v1.3.1 -- LICENSE*` 为空）；本地保留的 `LICENSES/Khazix-Skills-MIT.txt` 副本与上游 `LICENSE` 逐字节 diff 为空，继续有效。
- 分段结论：`v1.3.0..v1.3.1` 仅触及 `.claude-plugin/marketplace.json` 与 `leader/references/anatomy.md`，不含任何 neat-freak 字节；neat-freak 的全部变更集中在 v1.3.0 单个 commit `1cff16da`。

## 变更文件逐条处置

`compare` v1.2.2...v1.3.1 共 23 个变更文件；neat-freak 相关 7 个，逐条映射如下。快照五文件（`SKILL.snapshot.md` + 4 references）全部刷新至 v1.3.1 原字节，`scripts/check_repository.py` `BASELINE_HASHES` 重锁 5/5 项。

| 上游文件 | 引入 release / commit | 对 neat-freak 基线 | 处置 |
|---|---|---|---|
| `neat-freak/SKILL.md`（+74/−147） | v1.3.0 / `1cff16da`（PR #85） | **结构重写**：正文从「完成合同六事实面表 + 四档请求分级 + 轻量/完整路径分叉 + 0–7 步完整流程 + 最终自检 checklist」重排为线性五步（先列全再判断 → 找出对不上的地方 → 改 → 记忆 → 核对然后汇报）；frontmatter description 开头语改写（「知识治理收尾」→「干完活的知识收尾」，新增点名 `CLAUDE.md/AGENTS.md` 等规则文件与会话临时文件）；标题去英文副题；「待你确认」模板的限定语（「只列尚未获准或仍含独有内容的对象」）收敛进正文「边界」节；删除「体量超过平台预算 70% 时才报告读数」句与「真相矩阵」模板 | 快照 `SKILL.snapshot.md` 刷新为该 commit 原字节。能力逐行重判：触发/不触发逐类保持（见下节）；机械盘点、先减后加、绝对日期、记忆授权边界、汇报骨架、四受众模型全部保留；被删结构要素的语义经核验仍存活于 v4.0.0 文本（证据层级表与发布链整体移入 `references/verification.md`，「以什么为准」可信度排序与四问核对替代 checklist，收尾文件的「通常变短或持平」替代净增长自检）。台账触发行与 anti-bloat 组行措辞重述，**28 行分类全部不变**；本包更强的本地形式（inventory 事实面状态机、11 项语义检查、execution protocol、尺寸 gate）不受上游删除影响，未做任何本地行为改动 |
| `neat-freak/references/agent-paths.md`（+10/−7） | v1.3.0 / `1cff16da` | **实质事实更新**：新增 Claude Code 2.1.277 起直接读 `AGENTS.md` 的条件（仅当工作目录及上级均无 CLAUDE 系文件）与三种共存方案（`@AGENTS.md` 导入/软链/`claude-md-and-agents-md` 设置）；新增 `AGENTS.override.md`、`AGENTS.local.md`、`.agents/` 不被 Claude Code 读取；新增 `@路径` 导入按写它的文件解析、最多嵌套四层；「宿主管线生成」措辞改「Codex 自己生成」；标题改各平台速查口径；表头加「核对于 2026-11」 | 快照刷新为该 commit 原字节。属上游 additive 平台事实更新，方向与本包 `disadvantage_replaced` 行（`concrete-cross-runtime-paths`，非永久表 + verify-current）一致；台账该行已注明 4.0.0 表更新。本包 runtime-history 的路径候选表与「discovery candidates, not ownership proof」守卫不变 |
| `neat-freak/references/sync-matrix.md`（+60/−62） | v1.3.0 / `1cff16da` | **口语化重排**：章节重排（噪音表移后），表格措辞全面改写（`pending`→`待决`、`out-of-scope`→`范围外`、`marker`→`版本标记` 等）；能力面（变化→核对处 9 行、四受众职责、记忆路由 8 行、违规→动作 7 行、跨项目 4 条件）逐行保持 | 快照刷新为该 commit 原字节。无能力增删，无台账行变化 |
| `neat-freak/references/governance.md`（+61/−61） | v1.3.0 / `1cff16da` | **口语化重排**：「确定实际规则链」提前为第一节；机械可核验约定表（7 类）、范围分级（4 档）、处置等级（直接修/先报告/只读）、规则质量检查（6 项）、报告要求逐项保持 | 快照刷新为该 commit 原字节。无能力增删，无台账行变化 |
| `neat-freak/references/verification.md`（+51/−83） | v1.3.0 / `1cff16da` | **口语化重写**：标题改「什么结论要什么证据」；9 行结论→最低证据表逐行保持（措辞中文化）；发布状态机压缩为线性链（跳步需理由、卡在哪步按哪步汇报保留；新增「项目没有部署环节（本地工具、还没上线的小项目）时，后面几步不适用，如实说不适用，不编造部署状态」）；「真相矩阵」text 模板删除（其「每一面都核实过」语义保留在证据表末行）；清场前 gate 8 步并为 7 步（内容逐项保持）；「验证失败时」四条逐条保持（`pending`→`未核实` 措辞） | 快照刷新为该 commit 原字节。无能力删除；台账验证行不变 |
| `neat-freak/scripts/audit-inventory.sh`（+3/−2） | v1.3.0 / `1cff16da` | 规则链探测与用户级探测各新增 `GEMINI.md` / `~/.gemini/GEMINI.md` 候选（additive 平台覆盖） | 不在快照面（快照只锁 SKILL + 4 references）。记录为上游 additive 观察；本包 Python inventory 的平台候选由 `runtime-history.md` 表管理，GEMINI 候选暂不加入本地表（无本地宿主证据），未改动本地脚本。无台账行变化 |
| `neat-freak/evals/evals.json`（+10/−10） | v1.3.0 / `1cff16da` | 期望条目措辞中文化（`定稿/毕业/待整合`→`定稿结论、并进文档后留指针，或在平台不许改时如实报告为过期`；`pending/out-of-scope`→`未核实或待决/范围外`；`生产 marker`→`生产的版本标记`），eval-7 期望语义逐条保持 | evals 不在快照面（2026-10-07 审计已声明未取 eval fixtures）。逐条语义比对无能力变化；无处置动作。`evals/validate.py` 在 v1.2.2→v1.3.1 区间逐字节未变（`git diff` 为空），无需复核 |
| 其余 16 个文件（`hv-analysis/`、`khazix-writer/`、`leader/`、`storage-analyzer/`、`AGENTS.md`、`README*.md`、`.claude-plugin/marketplace.json`、`tests/test_hv_report.py`） | v1.3.0 / `1cff16da`；v1.3.1 / `76fc0f8e` 仅 `.claude-plugin/marketplace.json` 与 `leader/references/anatomy.md` | 属其他 skill 或仓库级文件，不属于 neat-freak 能力集 | 不采纳、不建行；v1.3.0→v1.3.1 跳因此无需 neat-freak 能力复核 |

## 触发语义保持核验（v4.0.0 description 改写）

逐类比对 v1.2.2 与 v1.3.1 的 description（本地 clone 逐行 diff，差异仅 description 首句与 version 字段）：

- 点名触发：`neat-freak` / `洁癖` / `/neat` —— 两版一致。
- 意图触发类别：开发后同步文档与记忆、CLAUDE.md/记忆过期或冲突、交接前清场、审计规则是否被遵守，示例短语「把文档和记忆整理一下」「docs 和代码对不上了」—— 全部保留；4.0.0 首句改写为「干完活的知识收尾」并显式点名 `CLAUDE.md/AGENTS.md` 等规则文件与 Agent 记忆、会话留下的临时文件，类别语义不变。
- 负触发：纯写代码/重构/调试、整理数据或文稿（JSON、周报、changelog）、没有项目知识语境的裸「整理」—— 三类全部保留。

结论：4.0.0 的 description 改写是措辞变化而非触发能力变化。台账触发行（`trigger-explicit-phrases`，分类 `restored`）已重述为 4.0.0 措辞；本地更强的裸 `tidy/整理` 正触发分歧（`trigger-cases.json` `bare-tidy` → `reconcile`）与负向守卫保持不变——4.0.0 的负触发「没有项目知识语境的裸『整理』」与本地表逐字相容，不构成触发回归。

## 结构重写的能力映射（v3.1.1 → v4.0.0）

上游删除/合并的四个结构要素逐项核验其语义去向：

1. **完成合同六事实面矩阵**（`verified-current`/`changed-and-verified`/`pending`/`out-of-scope`/`not-applicable` 枚举表）→ 语义收敛为「以什么为准」可信度排序（代码/配置/运行服务 > 用户当次明确决定 > 文档 > 记忆）+『核实不了的不写成事实，在汇报里标「未核实」』。本包 inventory 的 fact-surface 状态机与 validator 不受影响（本地更强形式不变）。
2. **轻量/完整路径分叉** → 线性五步。原轻量五步（盘点/对齐/补规则文件/清点残留/汇报）与完整路径 0–7 步的内容逐项分布在五步正文与四 references：补规则文件五要素+60 行上限保留（「没有规则文件的项目」段）、残留清理候选保留（「会话留下的临时文件」段）、发布闭环移入 `references/verification.md` 发布链与「清场之前」节。
3. **最终自检 checklist** → 「核对，然后汇报」四问（每文件改/不改判断、旧名重搜、命令路径链接真实性、跑项目自有检查）。本包 execution protocol 六固定检查不变。
4. **汇报骨架** → 保留（影响/改动新建/待你确认/遗留），仅「待你确认」两条的括号限定语并入「边界」节的删除授权判断（内容等价且更强：明确「他说的是把文档和记忆收拾、整理干净，要的是内容对齐，不是让你删文件」「项目没有版本管理时删了找不回，除非用户点名了要删的东西，一律先列候选」）。

**上游 additive（v4.0.0 新增，4 项，记录为观察、不建强制行）：**

- 只读盘点与核对量大时可分给子 Agent 并行，修改由主 Agent 统一做；
- Claude Code 2.1.277 `AGENTS.md` 加载规则与三共存方案、`AGENTS.override.md`/`AGENTS.local.md`/`.agents/` 不读取、`@路径` 导入嵌套上限四层；
- `audit-inventory.sh` 新增 `GEMINI.md` / `~/.gemini/GEMINI.md` 探测候选；
- 记忆删除/合并前先留住仍成立的原因、踩过的坑与退役提醒（记忆目录通常无版本管理，删了找不回）。

四项均与本包现有安全方向一致或属平台事实更新，无一与本地授权边界冲突；采纳任何一项改变 skill 行为，需走本仓库自己的 gate 与测试，本次均不采纳、仅记录。

## 三方比较与保留面

- 原采用上游基线：v1.2.2 / skill 3.1.1 / `71cd50ff`（快照字节仍在 Git 历史与本记录引用的上一版 provenance 中）。
- 当前本地实现：`skills/super-repo-pedant/` 全部 Azhou 包装增量（frontmatter 收窄与双语触发、品牌锚与过程播报、四模式、inventory/impact/execution 协议、Python 脚本族、receipt、runtime-state 合同、evolution 合同）逐字节未动。
- 目标稳定版：v1.3.1 / skill 4.0.0 / `76fc0f8e`。
- 结论：按能力迁移为**基线指针移动 + 快照刷新 + 台账措辞重述**；本地无行为变化。全部 28 行 disposition 保持原分类，8 行措辞重述至 4.0.0（触发行、anti-bloat 三行、conversation-review 行、per-file 行、deletion 行、runtime-paths 行）。兼容合同升 v6；`neat-freak-parity.json` 与 `tests/test_super_repo_pedant_parity.py` 的基线 pins 同步；`provenance.md`、`runtime-history.md`、`THIRD_PARTY_NOTICES.md` 记录新 pin。support-matrix 不引用上游版本号，无同步对象。

## 快照字节保真证据

刷新后以两法复核（均为本任务执行时输出）：

- blob 级：`git rev-parse v1.3.1:neat-freak/<file>` 与 `git hash-object <snapshot-path>` 逐一相等（5/5 OK）。
- SHA-256 重锁：`BASELINE_HASHES` 五条更新为 `2d5b6fbc…`（SKILL.snapshot.md）、`706fa70f…`（agent-paths.md）、`e1e7b068…`（sync-matrix.md）、`6ba61a31…`（governance.md）、`39644c1b…`（verification.md），与 `shasum -a 256` 输出一致。
- 换行：上游 `.gitattributes` 为 `* text=auto eol=lf`，五文件在两侧 worktree 均 CR-lines=0（`grep -c $'\r'` 全 0）；本仓 `.gitattributes` 对 `benchmarks/super-repo-pedant/upstream/` 无 scoped 属性覆盖，无归一化漂移。
