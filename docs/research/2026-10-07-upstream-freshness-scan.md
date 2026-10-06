# Research: 上游新鲜度扫描(社区直供 skill 的 pinned upstream 检查)

> 日期:2026-10-07(Asia/Shanghai)
> 性质:只读上游侦察。方法:对每个 adapted/vendored skill 的 provenance 记录提取 immutable pin,用 GitHub compare API(pin...HEAD)与 npm registry 查询领先量,再对变更文件做引入面交叠判断。本仓引入纪律:"adapted or vendored material requires an immutable source, license, retained notice, local boundary and reproducible update path"(AGENTS.md)——本扫描只报告状态,不改 pin、不升级。
> 范围:hub 的 14 个 canonical skill。`session-insights`(zero vendored bytes,URL pin)、`arch-doc`(内部 MCC 管线蒸馏)与四个 Foundation 包(原创)无社区上游,不适用。

## 结论速览

| 本仓 skill | 上游 | pin | 上游现状 | 领先 | 引入面交叠 | 判定 |
|---|---|---|---|---|---|---|
| super-caveman(core) | JuliusBrussee/caveman | `11ddc0c9` | 活跃 | **703 commits / 300+ files** | 有:`commands/caveman-commit.md`、`agents/cavecrew-*.md` 等 pin 时字节一致条目所在路径已变 | **需评估**(高) |
| super-caveman(adhd 合同) | ayghri/i-have-adhd | `b42a45a0` | 活跃 | **87 commits** | 有:`.cursor/skills/i-have-adhd/SKILL.md` 本体已改 | **需评估**(高,动它须晋级骑行) |
| super-lavish | kunchenguid/lavish-axi + npm | `232972be` / CLI `0.1.47` | 活跃 | 95 commits;**npm 0.1.47 → 0.1.83** | CLI 是运行时基线,npm 26 个 minor/patch 未评估 | **需评估**(中,npm 基线是硬 pin) |
| super-llm-wiki | Yeachan-Heo/oh-my-claudecode | `deee3a44` | 极活跃 | 1732 commits | 采样 300 files 中无 wiki 路径命中(compare 文件列表在 300 截断,未穷尽) | 观察即可(实现为标准库重写,仅特性漂移参考) |
| super-repo-pedant | KKKKhazix/Khazix-Skills (neat-freak) | `bab17831` | 活跃 | **50 commits** | 有:`neat-freak/SKILL.md` 与 `evals/` 已改——"28/28 capabilities accounted for" 的账面可能过时 | **需评估**(中) |
| ask-azhou | mattpocock/skills | `3cca18b3` | 活跃 | **68 commits** | 有:`skills/engineering/ask-matt/SKILL.md` 已改;但本仓只引入 pattern 不引入字节,且已用生成式路由表修复上游"手工维护过时"的通病 | 低(样式参考) |
| eli5 | anthropics/claude-plugins-community | `794af9e6` | 低频 | 16 commits | **无**——16 个变更文件里 eli5 目录只有 `LICENSE`,行为句 SKILL.md 未动;其余是 html-plan/next-steps 两个新插件 | 无需动作 |
| autoresearch | karpathy/autoresearch | `228791fb` | 静止 | **0(逐字节 identical)** | — | 无需动作 |
| excalidraw-diagram(引擎) | @excalidraw/excalidraw | npm `0.18.1`(tag `a2ec2889`) | 主线活跃 | main 领先 430 commits,但 **npm 最新仍是 0.18.1**(未发布) | 引擎 vendor 锁的是发布版 | 无需动作(等新 tag) |

## 建议(按优先级)

1. **super-caveman 上游评估票**:caveman 703 / i-have-adhd 87 的领先量意味着本地衍生物(capability-map 内容寻址条目)与上游语义可能已实质分叉。注意:评估本身只读;任何 skill 文件字节变更都会改 skill-tree digest,必须走晋级骑行(AGENTS.md 保护面条款)。
2. **super-lavish CLI 基线评估**:lavish-axi 0.1.47 → 0.1.83 跨 36 个版本,relay 层的 optimistic revision guards 与 stale-rejection 契约是否兼容需一次有界评估;升级即改 provenance 硬 pin,须带回归证据。
3. **super-repo-pedant 能力账面核对**:neat-freak 上游 50 commits 含 SKILL.md 与 evals 变更,`neat-freak-compatibility.md` 的 28/28 账面应做一次增量核对(只读 diff 即可判定)。
4. 其余(ask-azhou 样式、eli5、autoresearch、excalidraw)维持现状;下次例行扫描复用本笔记的 compare 命令即可。

## 评估结论(2026-10-07 当日深查,只读)

**T1 super-caveman 上游(caveman 11ddc0c9→HEAD、i-have-adhd b42a45a0→HEAD)**:三条字节一致条目中,caveman-commit 语义零变化(仅 Claude `.md` 命令格式迁移为 `.toml` 包装),caveman-review 的 prompt 文本逐字未变,cavecrew 只有措辞级漂移(voice 描述改写、加 "if installed" 限定词)。**唯一实质变更:i-have-adhd 行为合同规则 9**——pin 时"Cap lists at 5 items"(硬性截断/拆分)在上游已改为"Cap lists to 5 items"的新语义:仅约束最终响应的呈现层(分组+排序,每组 ≤5),明确"Never omit relevant items when completeness matters…must not limit analysis, search, tool results, candidate generation, or retained information"。这是对 44 条输出行为判据中至少 1 条的语义反转,采纳与否是行为决策;任何采纳都改 skill-tree digest,必须走完整晋级骑行(19 案例 + 3 judge + exact-diff P0)。

**T2 super-lavish CLI(lavish-axi 0.1.47→0.1.83)**:37 个版本全部 0.1.x;整份 CHANGELOG(688 行)**零 BREAKING CHANGES 标记**;近期版本(0.1.72–0.1.83)的功能/修复行没有触及 relay 面词汇(spec/relay/export/init/serve/feedback/ledger/revision)。初步判定升级风险低;但 provenance 的 npm integrity + CLI baseline 是硬 pin,任何升级都要在新 CLI 上重跑 relay 契约回归(optimistic revision guards、stale-revision rejection、exact visible-state projection)后才能改 pin。

**T3 super-repo-pedant(neat-freak bab17831→HEAD)**:上游已发布 **v3.0.0 大改版**——重定位为"knowledge and governance closeout",frontmatter 新增 `compatibility`/`metadata` 键,正文重写,章节 16→18。本地"28/28 neat-freak capabilities accounted for"的兼容账面基于 pin 时版本,已确认过时风险为真。需要一次完整的能力账目重审(逐能力 diff:保留/改名/新增/删除),`neat-freak-compatibility.md` 若要跟上游 v3 对齐属合同级变更,走本仓自己的 gate 与测试面。

**无需动作项(维持现状)**:eli5(行为句未动,仅上游 LICENSE 变更)、autoresearch(逐字节一致)、excalidraw 引擎(npm 最新仍 0.18.1,主线 430 commits 未发布)、ask-azhou(仅 pattern 参考,生成式路由表已结构性解决上游过时问题)。

## 方法与边界

- 命令:`gh api repos/<repo>/commits/HEAD` + `gh api repos/<repo>/compare/<pin>...<head>`,npm 用 `npm view`。快照时间 2026-10-07,上游持续移动,结论有时效性。
- compare 的 files 列表在 300 截断;super-llm-wiki 的"无 wiki 路径命中"是抽样结论,非穷尽。
- 本扫描未评估上游变更的内容质量(是否有安全修复/行为破坏),只判定"是否有更新 + 是否触及引入面";逐内容评估属于上述建议票的范围。
- 未扫描私有整理区(IP/azhou)的 10 个 skill:它们为阿舟原创,不持社区上游 pin。
