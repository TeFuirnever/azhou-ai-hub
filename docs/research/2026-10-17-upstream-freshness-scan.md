# Research: 上游新鲜度重录(2026-10-17 例行复查)

> 日期:2026-10-17(Asia/Shanghai)
> 性质:只读上游侦察 + 一个治理内升级动作。方法:对每个持上游 pin 的 canonical skill,用 GitHub compare API(pin...HEAD)与 npm registry 复查领先量,沿用 `docs/research/2026-10-07-upstream-freshness-scan.md` 的 compare 命令;对唯一触发升级条件的 super-lavish CLI 基线按 provenance 更新路径带证据改 pin。引入纪律不变:"adapted or vendored material requires an immutable source, license, retained notice, local boundary and reproducible update path"(AGENTS.md)。
> 范围:hub 的 14 个 canonical skill 中持社区上游 pin/外部源的 9 个;四个 Foundation 包与私有整理区 skill 无社区上游,不适用。

## 结论速览

| 本仓 skill | 上游 | pin | 上游现状(2026-10-17) | 领先 | 引入面交叠 | 判定 |
|---|---|---|---|---|---|---|
| super-caveman(core) | JuliusBrussee/caveman | `11ddc0c9` | 活跃 | **1553 commits**(10-07 为 703;compare files 在 300 截断) | 采样确认 `commands/caveman-*.md`、`agents/cavecrew-*.md` 等引入面路径继续漂移;10-07 深查已定语义零变化 | **维持 pin**(决定重申,见下) |
| super-caveman(adhd 合同) | ayghri/i-have-adhd | `b42a45a0` | 活跃 | **97 commits**(10-07 为 87) | 10-07 后 `SKILL.md` 再变更,但可见新增为 eval 工具类提交(`measure` 子命令、盲评 `judge.py`、多轮持久化场景、frontmatter 剥离);未见规则 9 再改写 | **维持 pin**(决定重申) |
| super-lavish | kunchenguid/lavish-axi + npm | `232972be` / CLI `0.1.83`→`0.1.89`(本批) | 活跃 | skill 源 **108 commits**;npm 0.1.84–0.1.89 六个版本,零 `BREAKING CHANGES`、零 relay 面词汇 | 本批已按更新路径升级并带双基线回归证据 | **已升级**(本批落地) |
| super-llm-wiki | Yeachan-Heo/oh-my-claudecode | `deee3a44` | 极活跃 | **2274 commits**(10-07 为 1732) | 实现为标准库重写,上游仅特性漂移参考(10-07 判定沿用) | 观察即可 |
| super-repo-pedant | KKKKhazix/Khazix-Skills (neat-freak) | `bab17831` | 静止 | **50 commits**,与 10-07 一致(上游 2026-10-01 后未再推送) | v3 能力账目重审与合同 v2 已逐项记录 delta | **维持合同 v2**(决定重申,见下) |
| ask-azhou | mattpocock/skills | `3cca18b3` | 活跃 | **86 commits**(10-07 为 68) | 仅引入 pattern、零上游字节;生成式路由表已结构性免疫上游过时 | 无需动作 |
| eli5 | anthropics/claude-plugins-community | `794af9e6` | 低频 | **17 commits**(10-07 为 16) | 17 个变更文件中 eli5/ 下仅 `LICENSE` 被上游移除(0 增 21 删),行为句 `SKILL.md` 未动;本仓合规根基是 pin 时版本的仓库级 Apache-2.0 与留存副本 `LICENSES/Claude-Plugins-Community-Apache-2.0.txt`,不受上游后删影响 | 无需动作 |
| autoresearch | karpathy/autoresearch | `228791fb` | 静止 | **0**(上游最后推送 2026-03-26) | 包装器零上游字节 | 无需动作 |
| excalidraw-diagram(引擎) | @excalidraw/excalidraw | npm `0.18.1`(tag `a2ec2889`) | 主线活跃 | npm 最新发布版**仍是 0.18.1**(2026-10-17 复查) | 引擎 vendor 锁发布版 | 无需动作(等新 tag) |

## 建议(按优先级)

1. 无新评估票。唯一满足升级条件的 super-lavish CLI 基线已在本批按 provenance 更新路径完成(`0.1.83` → `0.1.89`,回归与双基线冒烟证据记录在 `skills/super-lavish/references/provenance.md` 的 update path),不另开统计性工单。
2. 下次例行扫描(建议间隔 ≤1 个月)优先复查 caveman 上游:领先量十天内自 703 翻倍至 1553,若出现触及引入面的行为语义变更(而非格式/措辞漂移),按 10-07 决定的采纳路径报告维护者。

## 决定(2026-10-17 重申,workspace-owner 会话内确认)

**决定 A — super-caveman 维持 pin,不采纳上游 i-have-adhd 规则 9 放宽。** 沿用 2026-10-07 决定(issue #272 T1 与同日扫描记录,含 #273 修正后的决策与理由):pin `b42a45a0` 与 44 条输出行为判据保持不变;10-07 后上游新增为 eval 工具类提交,未触及行为决策面。采纳仍以维护者明确点名为前提,并须先通过完整晋级骑行(19 案例 + 3 独立配对评委 + exact-diff P0)。

**决定 B — super-repo-pedant 保持合同 v2,实现基线留在 pin `bab17831`。** 沿用 2026-10-07 neat-freak v3.0.0 能力账目重审的"等价演进"判定(`docs/research/2026-10-07-neat-freak-v3-capability-audit.md`:kept 20 / changed 8 / removed 0,12 项 upstream-additive 均有 disposition);上游自 2026-10-01 起无新提交,现有账面与快照哈希锁仍然新鲜。未来采纳任何 v3 语义仍属行为变更,须走本仓 gate 与测试面的完整评估。

**[2026-10-18 更新]** 决定 B 已由 workspace-owner 于同日指示修订:参考基线移至 v3.0.0(`322346de`,快照哈希锁刷新,合同 v3,账面 8 个 changed 行按 v3 措辞重述;本地行为字节不变,12 项 disposition 保留)。见审计文档的 "Decision (2026-10-18)" 节。决定 A(super-caveman 维持 pin)仍被同日指令修订为启动完整晋级骑行,该骑行已于同日执行并在 attempt-1 被拒(17/19,claim gate 未达):见 `docs/research/2026-10-18-caveman-rule9-adoption-ride-attempt-1.md`;决定 A 的保留 pin 状态因此延续。

## 方法与边界

- 命令:`gh api repos/<repo>/compare/<pin>...HEAD` + `npm view`;快照时间 2026-10-17,上游持续移动,结论有时效性。
- compare 的 files 列表在 300 截断;caveman 的"引入面继续漂移"是采样结论(与 10-07 相同的路径集),非穷尽。
- 本扫描不评估上游变更的内容质量,只判定"是否有更新 + 是否触及引入面";caveman/i-have-adhd 的逐内容深查以 10-07 记录为准,本次仅复查"是否有新的行为面变更"(结论:无)。
- super-lavish 的升级证据(16 项确定性测试、12 万级 fuzz 输入零崩溃、双基线隔离安装、open/poll/export/end/validate 冒烟与跨版本字节一致导出)记录在 provenance update path;冒烟不含浏览器人工批注回路,与既有 receipts 的披露边界一致。
- 用户级 Matt Pocock 技能套件(`mattpocock/skills` 的本地安装通道,`~/.agents/.skill-lock.json` 管理)不属于 hub pin 体系,本批在仓库外独立升级,不进入本记录的 pin 台账。
