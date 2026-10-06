# Research: 跨 harness 执行证据盘点与 skill 升级规划

> 日期:2026-10-06(Asia/Shanghai)
> 性质:只读证据挖掘 + 升级规划。未修改任何 skill、门禁或公开声明;本文是候选清单,不是已接受工作。
> 数据源:本机四个 harness 的聊天/会话记录(Claude Code、Codex、Kimi Code、zcode)。原始会话记录按仓库规则不入库;本文只保留聚合结论、计数与必要的机器输出短引文,用户消息一律转述。
> 边界:私有 azhou 仓(IP/azhou)中发现的问题不进入本仓规划;本仓与私有仓的同步红线不变。

## 1. 数据源与覆盖

| Harness | 存储位置 | hub 相关量 | 时间窗 | 说明 |
|---|---|---|---|---|
| Claude Code | `~/.claude/projects/-Users-guanxueliang-Desktop-oh-my-ai-azhou-ai-hub/` 等 + `~/.claude/history.jsonl` | 该项目目录 6 个会话(全部为 Hindsight 自动化结构调查,非人工);另 52 个 super-caveman 评测骑行会话;history.jsonl 约 6200 条提示 | 2026-08-22 → 10-05 | firstmate/treehouse 时期的会话 jsonl 已不存在,其结论沉淀在本仓 `evidence/` 与 backlog |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`(610 个,按 session_meta.cwd 过滤) | cwd 为 hub/worktree 的仅 3 个(2 个空启动 + 1 个 backpass 自动评审);真实执行证据是 2026-09-04/05 在 `/tmp` 的 22 个"harness 适配验证"会话;全文提及 hub 的文件 181 个 | 2026-08-23 → 10-06 | Codex 侧不存在常规人工 hub 开发会话;证据以验收式单轮会话与跨仓记忆为主 |
| Kimi Code | `~/.kimi-code/sessions/wd_azhou-ai-hub_*/` | 1 个会话:2026-09-11→12 连续约 24 小时,15 个用户提示、572 个 LLM step、726 次工具调用、28 次 verify.py、6 个 PR 全部合并(#198–#203,即 super- 前缀五连改名收官 + #167 元数据缓存) | 2026-09-11 → 09-12 | 单会话但工作量大、全程真实执行;中途因配额 403 停摆约 2.8 小时 |
| zcode | `~/.zcode/cli/db/db.sqlite`(session/message/part 三表)+ `~/.zcode/v2/tasks-index.sqlite` | db.sqlite 共 1461 会话,其中 directory=hub 的 **287 个**(含子代理;主会话约 28 个);tasks-index 26 个 hub 任务 | 2026-08-29 → 10-06 | zcode 是 hub 实际的主力开发 harness;`cli/rollout/` 是滚动窗口(仅保留最近 3 个文件,已观察到轮转),不构成历史证据;`v2/sessions/` 的 claude-import 与 hub 无关(全部为另一工作区的 Claude 副本) |

## 2. 执行事实:哪些能力真的跑过

- **全量记录中只有一次** hub skill 经 harness 原生 Skill 工具正式触发执行:azhou-info(Kimi Code,2026-09-11),一次成功、receipt 完整、品牌协议逐字输出。
- 其余真实使用形态:zcode 侧 hub skill 的使用全部走手贴链接、`scripts/azhou_hub.py` CLI 或派单,287 个会话中没有一次 Skill 工具交互调用;Codex 侧 ask-azhou 在 137 个文件的技能枚举文本中出现、真实调用为零;用户曾把"该用哪个 skill"的路由问题直接问给裸模型(Claude history,2026-10-03)。
- 门禁体系是高频真实用户:`verify.py` 在 Kimi 会话中 28 次、贯穿 zcode 全部维护会话;`azhou_hub.py info/doctor/verify` 在 Codex 沙箱 exit 0;eli5 的 `eli5.receipt.v1` 在 Codex 完整走通;excalidraw-diagram 5 场景 4 全绿;super-caveman stop 协议与 super-llm-wiki hook 注入探针在 Codex 验证可用;`migrate_state.py` 干跑→应用的首个生产实例(Kimi 会话)成功。
- Windows 修复轨迹(94→46→7→4→1→0 失败,verify-windows 翻 Required)按回据闭环,无新增证据。

## 3. 摩擦与失败模式(按证据强度排序)

### 3.0 main 分支当前为红(2026-10-06 实测,最高优先)
两个独立原因叠加,均与本文档无关(在干净克隆与主 checkout 双重复现):

1. **promotion-evidence 校验确定性失败。** 本地两个 checkout 与 CI(run 37208827994 的 Coverage and regression-rate baseline job,以及 main HEAD 的 Required 聚合/Python 3.14 腿)报同一断言:`AssertionError: True is not false : ['passing evaluation result lacks valid paired promotion evidence: revision-8f493670-attempt-1-summary.json']`。时间线与根因初判:#251(2026-10-04,README 嵌入宣传片)触碰了 `revision-d266751c` 晋级收据 reviewed_blobs 内的 README 保护路径,但未按 AGENTS.md 要求携新晋级收据落地——即门禁按设计拦截,落地流程漏了骑行。该失败同时让 #170(promotion-evidence 回放结构性破损)从"历史遗留"变为"正在发生"。
2. **compact-adviser 本地工具安装未被 #246 边界覆盖。** 仓库根的 `compact-adviser/`(2026-09-26 装入)不在 `.gitignore` 的本地工具清单里,repository policy 对其扫描即报 `cannot scan compact-adviser: Is a directory`,维护者本机的 verify.py 在第 1 项之前就先死在这里。

另外,当日复现了 §3.7 描述的输出矛盾:同一轮运行里 `FAILED (failures=1)` 与字符串 `verification passed` 并存。

### 3.1 session-insights 的 zcode fail-closed 前提已过期
2026-09-10 的格式侦察(`2026-09-10-zcode-session-store-format.md`)在 ZCode 3.11.2 上结论"无明文原生会话转写",其中 `cli/db.sqlite` 记录为"结构探测无表(可能锁/空)"。本次实测(3.14.4):`~/.zcode/cli/db/db.sqlite` 存在 session/message/part 三表,1461 会话、hub 工作区 287 个,消息正文可读。zcode 适配器的 `unsupported` hold 依据已失效,但 rollout 轮转、表结构稳定性、schema 是否随版本漂移均未验证。

### 3.2 改名与宿主安装的断裂(跨 harness 双证)
五连改名(#178–#183)同步了仓内全部表面,但已装到宿主的 hook 布线没有迁移路径:super-llm-wiki 改名后,Claude Code 侧 SessionStart/SessionEnd hook 仍指向 `skills/llm-wiki/...` 旧路径,2026-09-14 报 startup hook error,2026-09-26 仍靠手工修复;用户同期的认知负担("llm-wiki 是不是改名了""还有哪些没装")也源于此。这是四份数据里唯一同时被两个 harness 独立记录的同一故障。

### 3.3 触发/发现层是最弱的真实使用面
见 §2:正式触发仅 1 次;ask-azhou 零调用;路由问题流向裸模型;eli5 的 NL 触发 watch 计数停在 2(唯一两次独立复现 NL 触发失灵的是旧 repo-pedant,已由晋级修复);用户对 eli5 语义也有明确不满("ELI5 不是 5 岁吗",2026-09-15,经 backpass 内嵌转录,中高置信)。

### 3.4 Codex 沙箱下 excalidraw 视觉复核链路受阻
2026-09-04 layered-architecture 会话五连击:项目外写入被拒、render_excalidraw.py Traceback、sips 无法提取图像、file:// 预览被浏览器策略拦截、magick 字体缺失;最终自述"Visual review: skipped"。同批其余 4 场景靠 cua 浏览器路径完成复核——说明链路可用但不稳,且"skipped"没有按其他会话的 holds 机制表述。

### 3.5 azhou-setup 第二 checkout 的冲突语义
已用 link 模式装到主仓的机器上,任何第二份 checkout 的 dry-run 都会因"目标符号链接已指向主仓"被判 conflict 并以 exit 1 收场;输出里有 planId(计划已生成、未应用)却返回 fail 退出码,验收脚本必须特判,CI 语义歧义。这是 Codex receipts 流程里唯一的非零退出。

### 3.6 promotion 骑行的易漏字段与记录形态分歧
Kimi 会话中 reviewer 绑定字段(reviewer.review_sha256)漏更新导致首轮回放红;#184/#185 的 7 键带 notes 原始审批记录与校验器 8 键精确集不匹配(已并入 issue #170:promotion-evidence 回放结构性破损);docs-only 改动也须走完整骑行(受 reviewed_blobs 保护路径约束)。改名期间 6 次 Edit old_string 失配、broken link、rename residue 红全部集中出现——多表面改名靠 LLM 手编易漏。

### 3.7 verify.py 输出与退出码纪律
zcode 会话两次记录:管道里 `tail` 的退出码 0 掩盖了实际 FAILED(2 项失败);以及同一输出块里"FAILED (failures=2)"与"verification passed"并存。后台任务通知按退出码汇报,放大了误导。

### 3.8 中断与生命周期摩擦
Kimi 403 配额把后台子代理打死在任务中(主代理接手其 6 文件 diff 收尾);treehouse 归还租约删除 worktree 后,持久 shell 三次 getcwd 失效;Kimi 端 rtk 包装层的 jq 类型错把"PR 创建成功"报成 exit 1。用户在两个 harness 里都明确要求"全程自主、不用逐项问我"——对停顿点敏感。

### 3.9 其余已知项(有既有工单,不重复立项)
Windows cp1252 编码导致的 session_insights.py 输出崩溃(#236);离线依赖恢复(Playwright arm64 wheel、uv `--frozen --offline`)已换出血泪经验但未手册化;arch-doc 参考文档中的脚本路径失效(与 excalidraw 脚本漂移构成同机制第 2 例,尚无 gate 覆盖)。

## 4. 升级候选项

每项格式:证据 → 提案 → 验收。所有公开声明变更须携回据,双语 README 同提交。**本节是提案,接受与否由维护者决定,接受后按 backlog/GitHub issue 流程立项。**

### P0(main 当前为红,先恢复再谈升级)

**U0 恢复 main 绿:为 #251 的 README 变更补晋级收据(或回滚)**
证据:§3.0-1。提案:按 `revision-d266751c` 的先例走 producer-context invariance pathway 重绑(skill 树字节不变,仅 README 保护路径变更需新 exact-diff 收据 + 人工 P0),或与维护者确认后回滚 #251 的 README 嵌入。验收:本地 verify.py 与 CI Required 双绿;#170 的修复范围与此对齐。
**U15 compact-adviser 纳入本地工具安装边界**
证据:§3.0-2。提案:`.gitignore` 与 repository policy 的本地工具清单增加根级 `/compact-adviser/`(沿用 #246 的"本地安装不是公开包"语义),防止后续本地工具再度踩红维护者门禁。验收:带该目录的树 verify 通过 + 负控(一个未收录目录仍被拦截)。

### P1(证据充分、用户显式要求或前提已失效)

**U1 session-insights zcode 适配器:重启只读格式侦察**
证据:§3.1。提案:按 #162 模式对 ZCode 3.14.4 的 `~/.zcode/cli/db/db.sqlite` 做只读结构侦察(表 schema、角色/轮次语义、目录字段、版本稳定性;不读正文入仓),产出 go/no-go 研究文档;go 才立项适配器,维持同源去重(claude-import 不进 zcode 范围)。验收:新研究文档 + support-matrix/support 声明同步(仅当 go)。

**U2 改名与宿主安装的迁移闭环**
证据:§3.2。提案:(a) azhou-doctor 增加"陈旧 hook 路径 / 指向已改名 skill 的残留安装"探测(只读,报告清单);(b) 未来任何 canonical 改名的落地提交附带宿主侧迁移指引(或 `migrate_state.py` 同族的 hook 重写入口,显式 apply)。验收:doctor 对已知旧路径样本报出清单的负控测试;改名 runbook 增加宿主迁移步骤。

**U3 每 skill 的平台支持视图(用户 2026-10-06 显式要求"说明好哪些 skill 支持哪个平台")**
证据:zcode 会话(2026-10-06)原话要求;support-matrix 目前是能力粒度,读者无法按 skill 一眼读出"harness × OS"结论。提案:从 `docs/support-matrix.md` 单一权威派生一张 skill 粒度汇总(14 skill × {Codex, Claude Code, zcode, 其他/Kimi Code 见 U9} × {Linux/macOS/Windows}),派生表不引入新声明;双语 README 增加指针。验收:派生表与 support-matrix 逐格一致(可加一致性检查);双语同提交。

**U4 触发/发现面强化**
证据:§3.3(正式触发 1/14、路由零调用、路由问题流向裸模型)。提案:(a) ask-azhou 路由表改为从 canonical skills 与已安装清单生成式构建,保留 gate 的 routing-coverage parity(静态散文地图的漂移无校验可发现);(b) eli5 补触发词表与"未路由即记录"的主动埋点,替代被动等第 3 次 NL 失败(现 watch 计数停在 2);(c) 各 SKILL.md description 增加可被模型路由命中的意图关键词。验收:路由生成器 parity 测试;埋点落 `.azhou/` 命名空间且有负控;eli5 触发词进 frontmatter 并有 gate 覆盖。

### P2(证据明确、影响面中等)

**U5 excalidraw-diagram 沙箱降级通道与 holds 表述对齐**:证据 §3.4。渲染→预览链路提供无 GUI 降级(几何+像素哈希级)验证;"sandbox blocked preview"从 skipped 改为显式 holds。验收:一条沙箱友好路径的回据 + holds 表述测试。
**U6 azhou-setup 冲突语义细分**:证据 §3.5。`conflict-same-source`(目标已链接到同一来源)与真冲突分开,dry-run 单独退出码或 `--allow-conflict`。验收:两种冲突形态的输出/退出码负控测试。
**U7 promotion 重派生的字段提示**:证据 §3.6 与 §3.0-1(本次 fresh clone 亦确定性复现)。重派生/校验器在字段未同步时输出"应改的旧值→新值"提示;raw 审批记录 schema 版本化(与 #170 的修复范围对齐,不另起炉灶)。验收:构造漏更新样本时提示可复现。
**U8 verify.py 终判纪律**:证据 §3.7。单一终判行 + 退出码不被管道消费误导的文档说明(或 summary JSON 出口),消除 FAILED/passed 并存。验收:输出契约测试。
**U9 Kimi Code 进 support-matrix**:证据 §1/§2(Kimi 24h 会话、6 PR、azhou-info 正式触发——四 harness 里唯一)。提案:新增 Kimi Code 列,按现有回据格式补一份可复跑回据后再声明。验收:新回据 + 双语 README/support-matrix 同提交。

### P3(小改进或文档化)

**U10 断点续跑协议文档化**:403/中断后子代理任务的可重入拆分与中间产物落盘约定,写进 `docs/skill-standard.md` §5 或 azhou-doctor 参考(证据 §3.8)。
**U11 treehouse 归还前 cd 出 worktree**:worktree-policy/执行协议加一步,消除归还后 getcwd 失效(证据 §3.8)。
**U12 离线依赖恢复 runbook**:Playwright arm64 wheel / uv / npm 离线恢复流程手册化进 `docs/installation.md`(证据 §3.9)。
**U13 参考文档脚本路径完整性检查**:repo gate 扩展——references 文档引用的脚本路径必须存在(arch-doc 失效路径是第 2 例,证据 §3.9)。验收:种一个坏路径负控。
**U14 eli5 受众断言自检**:receipt 增加受众/风格断言的读回校验(如词句复杂度阈值),把"模型没遵从"拦在交付前(证据 §3.3 用户语义不满)。

### 已在跟进、不重复立项
#236(Windows 编码分歧)、#225(签名发布收官)、#218(P1 批次收尾)、#27(OpenSSF)、backlog 的 eli5-trigger-watch(U4 吸收其埋点思路)。

## 5. 建议顺序与执行方式

0. U0 + U15 先行:恢复 main 与维护者本机门禁双绿,其余工作全部让路。
1. U1 侦察先行(半天级,只读,产出 go/no-go 后再定 U1 后续)。
2. U3(用户点名)→ U2 → U4 构成 P1 主体;U5–U9 可并行拆票。
3. 执行沿用本仓惯例:一票一原子提交、回据先行、双语 README 同步、`python3 scripts/verify.py` 全绿交付;涉及 super-caveman 保护路径的改动按 AGENTS.md 与晋级骑行合并规划。
4. 用户明确偏好:批次内自主连跑,门禁绿即信任,减少逐项请示。

## 6. 未覆盖与置信度

- Codex 侧用户原话来自 backpass 会话内嵌转录(原始会话不在库内),置信中高;其余三家为直读原文,高。
- 被轮转掉的 zcode rollout、已删除的 firstmate 工作树会话不可考;结论以 db.sqlite 与仓内回据交叉验证。
- 未发现其他 harness(Gemini 等)在本机有 hub 相关记录。
- 本文所有计数为 2026-10-06 一次性挖掘快照;原始记录路径仅在本节与正文以目录级形式出现,逐会话定位信息保留在本地挖掘过程,不入库。
