# 威胁评审收据：公开发行业面、收据解析面、钩子渲染面（ticket #221 / spec #218 T3）

> 日期：2026-09-13（Asia/Shanghai）· 性质：对抗性威胁评审（threat-review pass，只读静态分析）· 范围：worktree `azhou-ai-hub-2cc7ce/8`（基于 origin/main `59d4db8`）的 `skills/super-caveman/scripts/`、`skills/super-llm-wiki/scripts/`、`scripts/azhou_hub.py`、`scripts/azhou_runtime_state.py`、`scripts/check_repository.py`、`docs/installation.md` 及发行声明 · 方法：逐假设沿真实代码路径推演（静态阅读 + `--help` 只读探测），未执行任何状态变更命令，未对真实安装状态运行仓库脚本，未验证第三方包管理器内部实现
> 脱敏口径：本收据不含用户身份、绝对本机路径、临时目录名或运行历史；所有行号引用对应该 worktree 的检出内容。

每个攻击假设给出明确判定：` resisted`（附抵挡机制与代码位置）或 `finding`（附 P0–P2 严重度与后续 issue 提案）。

## (a) 公开 `npx skills add TeFuirnever/azhou-ai-hub --skill <name>` 发行面

**A1 — 被篡改的 SKILL.md/README 能否夹带包管理器或 harness 会"执行"的越权指令？判定：resisted（当前树），但抵挡靠流程而非内容扫描（见 A2）。**

机制：仓库自证的分发行为只有一份实测收据——`evidence/public-install-smoke-2026-08-23.md:19-21` 记录 `skills` CLI 1.5.23 的发现机制是扫描 `skills/*/SKILL.md`，安装是整目录复制（repo-pedant 28 个文件、excalidraw 505 个文件），未观察到安装期执行；`docs/installation.md:24` 明确声明该路径"无仓库收据，须在目标 harness 内自行验证发现与调用"。复制出的文件是惰性数据：SKILL.md 只有被 harness 载入为提示词、由模型选择执行时才产生效果；全部可执行路径是标准库 Python 脚本，受 `scripts/verify.py`（`scripts/azhou_hub.py:1293-1306` 调用）与 promotion-digest 人工批准流程（AGENTS.md 记录）约束。包内唯一 `package.json`（`skills/excalidraw-diagram/scripts/package.json`）只有依赖声明，无 `scripts`/`postinstall`。钩子类适配器在文档与代码两侧都声明"绝不随技能安装自动运行"（`skills/super-caveman/references/setup.md:55,86`；注册只能由用户显式调用 adapter `setup` 完成）。残余风险如实陈述：check_repository 的检查全部是结构性的（A2、A4、品牌契约 `scripts/check_repository.py:440-494`、密钥模式 :655、边界 :604-610、链接 :520），没有任何门检查 SKILL.md 指令语义；若一次恶意提交改写指令文本，结构性门不会拦截——抵挡依赖评审与 promotion digest 流程，而非自动扫描。包管理器内部行为（是否永不执行安装钩子）未第一手验证，本判定在复制语义上以仓库自证收据为界。

**A2 — SKILL.md frontmatter 执行授权键缺失防护。判定：finding，P2。**

机制：当前 14 个 SKILL.md 的 frontmatter 只含 `name`/`description`/`invocation`（逐一核对，`name` 均与目录名一致）。但仓库的门对 frontmatter 只校验 `invocation` 枚举（`scripts/check_repository.py:281-314`），没有键白名单：一次未来提交加入 `allowed-tools`、`hooks` 之类的 harness 级执行授权键不会被任何确定性门拒绝。后续提案：在 `check_repository.py` 增加确定性门——SKILL.md frontmatter 键必须属于固定允许集（name/description/invocation），未知键即 fail。

**A3 — 已退役名称能否被调用以加载本地陈旧副本？判定：仓库内侧 resisted；本机残留侧 finding，P2。**

机制（resisted 半边）：`skills/` 下不存在 `repo-pedant`、`ci-test-reliability`、`prose-standard`、`lavish`、`llm-wiki` 目录，包管理器按目录发现（A1 收据），`--skill lavish` 无可发现包；checkout CLI 侧 `--skill` 被 argparse `choices` 钉死为 14 个现役名（`scripts/azhou_hub.py:1325,1332`），`canonical_source` 拒绝路径拼接（:395-404）；`check_rename_residue` 把旧名 token 限制在兼容性/迁移/出处/历史表面，越界即 fail（`scripts/check_repository.py:320-437`）。
机制（finding 半边）：发行路径无收据也无卸载（`docs/installation.md:24`），早先以旧名安装到 harness 技能根的目录不会被 `--skill <新名>` 移除；harness 扫描技能根时会继续加载陈旧副本，且陈旧副本的名字精确匹配会遮蔽新技能 description 里的兼容触发（如 `skills/super-repo-pedant/SKILL.md` description 的 "Renamed from repo-pedant (the old name still triggers this skill)"）。`azhou_hub.py doctor --target` 只检查现役名（:1127-1159），对目标根里非现役的陈旧目录不可见；仓库仅有文档级缓解（`docs/installation.md:120-129` 单一路径规则、:143-157 升级/卸载与 neat-freak 清理指引）。后续提案：给 `doctor` 增加只读告警项，枚举目标根下命中 `RENAMED_AWAY_SKILLS`（含 `neat-freak`）的非现役目录并给出清理指引；或在 `docs/installation.md` 给出一次性清扫命令。

**A4 — description 里的旧名别名被滥用于无关任务劫持？判定：resisted。**

机制：别名是刻意路由面，把旧名触发收敛到现役包；越权升级被技能内边界文本限制（super-repo-pedant description 明示 "Inferred completion only reminds; ordinary implementation that merely mentions or edits this skill does not authorize closeout"），触发面受 benchmarks 触发用例约束，旧名 token 的合法出现面由 A3 所引残留门钉死。

## (b) checkout 托管的计划/收据解析（`scripts/azhou_hub.py`）

前置事实：收据完整性摘要只防意外损坏——`docs/installation.md:58` 明示"receipt integrity digest detects accidental corruption, not malicious rewriting"；`_receipt_digest` 是对去除 digest 字段后规范 JSON 的 SHA-256（`scripts/azhou_hub.py:57-60`），校验在 `_load_receipt`（:92）。因此以下假设均假定攻击者能写收据文件（即同用户写权限），考察写权兑现后还能越权什么。

**B1 — 恶意重算 integrity_digest 的收据，经 destination/source 做路径穿越？判定：resisted。**

机制：语义信任不从收据文本出发，而从活体状态重derive。`name` 必须在 `canonical_skills(root)`（目录枚举，:777）；source 必须 resolve 到 `canonical_source(root, name)`，后者拒绝 `..`、绝对路径与嵌套名（:395-404）；destination 逐字符等于 `(target/name).absolute()`（:780-783），而 `target` 来自调用方 `expanduser().resolve()`——收据里任何非规范写法都落到 "receipt source or destination does not match canonical identity" 的 conflict。收据文件路径本身被 `_receipt_path_error` 钉死在 `target/.azhou/hub/receipts` 直接子级并拒绝符号链接（:112-129）。

**B2 — 伪造收据能否让 uninstall/migrate/repair 删除或覆盖非本仓库拥有的内容？判定：resisted。**

机制：删除路径全部经过 `_remove_exact_installation`（:453-474）：先做 `(st_dev, st_ino, st_mode)` 身份比对，再要求 `inspect_installation` 判定 `current`——copy 模式要求目标内容包摘要等于现役源包摘要（:418-423），link 模式要求符号链接 resolve 到现役源（:410-413）。伪造收据最多让"恰好是现役包逐字节副本/精确符号链接"的工件被移除（可由 setup 复原），无法伤及任意内容。repair 重装时 source_digest 与 installed_digest 全部从活体重算（:849-855, 876-878），不信任收据里的旧值；v2 收据的 installed_identity 使身份漂移 fail（:792-796）。伪造收据可达成的新能力只有"收养"一个内容与本 checkout 现役包逐字节一致的既有安装——内容既已钉死，无越权面。

**B3 — 符号链接置换（收据文件、receipts 目录、destination、包内文件）？判定：resisted（存在同用户竞态窗口，无跨权提升）。**

机制：分层拒绝——收据路径、receipts 目录、`.azhou/hub` 任一为 symlink 即 fail（:118-119）；运行态路径逐组件拒 symlink（`scripts/azhou_runtime_state.py:54-65`）；copy 模式 destination 为 symlink 即 conflict（:799-800），link 模式必须是指向源的精确 symlink（:798）；包内 symlink 使复制与摘要直接抛错（:347-348）；`_receipt_path_error` 在读取前拒绝 symlink 收据。残余：`_load_receipt` 的 `read_text` 跟随 symlink，路径检查与读取之间存在同用户竞态；写入用 `os.replace`（覆盖链接本身而非目标，:77），无放大。此类竞态要求攻击者已具同用户写权，不构成跨信任边界提升。

**B4 — v1→v2 收据升级与 `migrate-receipts` 的 confused deputy / TOCTOU？判定：迁移本身 resisted；附 finding，P2（真实 v1 收据被搁浅）。**

机制（resisted）：`migrate_receipt_namespace` 先逐收据校验 target/source_root/内容身份（`scripts/azhou_hub.py:164-177`），再由 `plan_directory_migration` 生成绑定"路径 + 逐文件 SHA-256 清单"的 planId（`scripts/azhou_runtime_state.py:186-224`）；apply 前 `_replan` 重算并比对 planId（:260-262），评审与执行之间任何字节替换都会改变 planId 而被拒；复制后再次对 stage 与 source 双向重新清点（:276）。dry-run 只做语义校验、apply 只做内容保持搬迁，错位窗口被 planId 内容绑定封闭。
机制（finding）：`migrate_receipt_namespace` 与 `_doctor_hub_receipts` 调用 `_receipt_item_state` 时未传 `legacy_receipt=True`（`scripts/azhou_hub.py:175` 与 :222），而 v1 收据的 `installed_identity` 是模式字符串、`_receipt_identity` 必返回 None（:441-450），于是一律命中 "receipt lacks installed object identity" 的 conflict；同时 `repair`（唯一能升级 v1 的入口，:822-833, 849-860）又被 `_receipt_path_error` 限制在新命名空间 `.azhou/hub/receipts`（:125-126），v1 收据所在的 `.azhou-ai-hub/receipts` 永远到不了 repair。结果：`docs/installation.md:60-68` 承诺的迁移路径对真实 v1 收据不可达（fail-closed，非安全洞，是兼容性死路）。后续提案：要么让 migrate-receipts 的校验段使用 legacy 语义（`legacy_receipt=True` + `_legacy_package_digest`）并在搬迁后走既有 upgrade 路径，要么在文档明示 v1 收据须重新 setup；补一个真实 v1 收据的测试夹具。

**B5 — 陈旧或不同的计划借 `--plan-id '<reviewed-planId>'` 被执行？判定：resisted。**

机制：planId 是计划全内容的 SHA-256（模式、target、收据路径、每技能 name/status/source/destination/source_digest，:599-616）；apply 以同一活体输入重算并整串比对（:619-620）。陈旧计划因状态或摘要漂移必然哈希不同；跨 checkout 重放要求 target、源路径与内容摘要全部相同——即包逐字节相同，此时"恶意 checkout"未引入任何差异。计划计算与落盘之间的残余竞态最坏造成 apply 失败回滚（`symlink_to` 对已存在目标抛错、`os.replace` 对非空目录抛错，:664-692），且装完后还有二次终验（:694-714）。无任何路径能让 reviewed id 掩护不同内容。

**B6 — 旧收据的部分重放（旧 target/旧技能名的收据复用）？判定：resisted。**

机制：`target` 必须等于显式 `--target` 且经 `--target` 绝对路径强制（:1407, 1413）；`source_root` 必须等于本 checkout 的 `skills/`（:584, 820, 907, 948）——收据被单点绑定到"创建它的那个 checkout + 那个 target"；技能名与源摘要钉死现役包（B1/B2）。旧收据重放的可达成集合与其诚实描述的操作集合重合。
观察（不计 finding）：`_mutation_lock` 的 `lock.mkdir()`（:143）对残留锁无超时回收（对比 `llm_wiki.py:312` 的 300 秒陈旧锁回收），同用户可预留 `mutation.lock` 使托管操作持续不可用；:1468 的三元表达式两分支相同（`args.receipt if args.managed and args.apply else args.receipt`），属易误导的死代码，建议清理。

## (c) 钩子片段渲染（super-caveman 适配器与钩子状态文件）

**C1 — 仓库文件（AGENTS.md 片段、状态文件）内容能否经 super-caveman 胶囊注入提示词？判定：resisted。**

机制：`capsule_text`（`skills/super-caveman/scripts/claude_adapter.py:291-314`）的全部文本是静态字面量，动态槽只有五个且全部受控：`mode`/`why` 来自 `resolve_mode`，其输入经 `ok_defaults`/`ok_session` 的枚举白名单（:186-205，mode 只能是六个模式或 off，one_shot 只能是三个路由）；`source` 白名单为四事件（:338-340）；`rules_digest()` 是 SHA-256 十六进制（:58-68）；路径槽只输出安装位置字符串。任何 AGENTS.md、SKILL.md 或状态文件内容都不被内联——文件只以摘要与路径形式出现。输出有界（capsule 10,000 字符、reinforcement 1,024 字符，:33-34）。事件输入与渲染错误一律 fail open 输出 `{}`（:369-372），无静默注入通道。

**C2 — 胶囊对 `session_id` 的渲染未过正则。判定：finding，P2。**

机制：`run_render` 取 `sid = str(event.get("session_id", ""))` 后未经 `SID_RE` 校验即传入 `capsule_text`，逐字嵌入 `session={sid}` 行（`claude_adapter.py:341, 366, 312`）；而状态落盘侧 `session_path` 对同一值强制 `^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`（:40, 179-183）。攻击者须控制 harness 事件载荷（host→hook 边界，非 repo→prompt 边界）才能注入换行/伪指令文本，故非越权通道，但与自身校验纪律不一致。后续提案：渲染前对 sid 应用 `SID_RE`，不匹配回退 `unknown`。

**C3 — zcode 适配器 setup 翻转全局 `hooks.enabled`。判定：finding，P2。**

机制：`_apply_event(install=True)` 无条件写 `hooks["enabled"] = True`（`skills/super-caveman/scripts/zcode_adapter.py:206`），这是该 scope 配置的全局钩子总开关：用户若曾刻意禁用（可能正是为了压制其他第三方钩子），setup 会连同他人钩子一并重新启用；uninstall 不恢复原值（:211-230 从不触碰该键）。`setup.md:55` 只承诺"保留无关条目"，未披露此全局翻转。宿主对 `enabled` 的确切语义未第一手验证（`evidence/zcode-hook-surface-2026-09-04.md` 记录了字段形态）。后续提案：setup 记录并恢复 `enabled` 先前值、或至少在 setup 输出与 `setup.md` 中显式声明全局翻转；uninstall 考虑恢复进入前状态。

**C4 — `_owned_command` 按词法形状识别自身（`parts[-3:] == ("super-caveman", "scripts", "<adapter>.py")`）。判定：resisted（附观察）。**

机制：任何 checkout 的同形状钩子都被视为"owned"（`claude_adapter.py:396-405`、`zcode_adapter.py:128-138`）：setup 会把（可能属于另一 worktree 的）同形状注册整体替换为指向当前代码的注册，uninstall 会将其移除。两个方向的收敛都是"落到正在运行的这份代码"，且前提是已能写宿主配置（该边界上攻击本就无需此漏洞）；替换不产生攻击者可控的注册。观察：跨 checkout 的卸载半径大于用户直觉，可在文档注明。

**C5 — super-llm-wiki SessionStart 将项目控制的 index.md 原文行渲染进 `additionalContext`。判定：finding，P1。**

机制：钩子链 `llm_wiki_adapter.run_host_hook` → `run_hook_event` → `lifecycle_session_context`：后者在页面与 index 存在时直接 `index.read_text().splitlines()[:limit]` 取最多 30 行原文，拼进 `additionalContext`（`skills/super-llm-wiki/scripts/llm_wiki.py:1025-1039`），适配器不加改造地透传为 SessionStart 的 `hookSpecificOutput.additionalContext`（`skills/super-llm-wiki/scripts/llm_wiki_adapter.py:109-119`）。store 目录虽被 `state_path` 逐组件拒 symlink（`llm_wiki.py:276-287`、`azhou_runtime_state.py:54-65`），但其**内容**是项目侧可控文本：无转义、无逐字节上限（仅 30 行数）、无"以下为不可信项目内容"的出处标注。攻击链：钩子为显式 opt-in（`render-hooks` 只打印配置、不改宿主配置，`llm_wiki_adapter.py:135-167`），但安装后用户打开任一仓库即以其 cwd 解析 store；仓库可以自带 `.azhou/super-llm-wiki/`（本仓库 `.gitignore:43` 的 `.azhou/` 只约束本仓库，攻击者仓库可自由提交该目录），配合合法 frontmatter 的页面文件即可让 30 行任意文本在每次 SessionStart 以钩子上下文的信任外观注入模型，且持续存在、独立于源文件删除。`[LLM Wiki: N pages at …]` 前缀反而为注入行背书。对照面：C1 的 caveman 胶囊证明同一作者知道如何只渲染受控槽位，此面未套用同一纪律。缓解事实：须用户显式安装钩子且打开恶意仓库为会话根；载荷上限 30 行；作用域限于单项目。后续提案：SessionStart 摘要改为从页面元数据重新生成（不读 index 原文），或对行做引用转义；增加总字节上限；在输出中显式标注"以下为项目侧不可信内容"。

## 汇总表

| 编号 | 假设 | 判定 | 严重度 | 后续 |
|---|---|---|---|---|
| A1 | 发行内容夹带安装期/harness 期越权执行 | resisted（复制惰性 + 结构门 + 流程），包管理器内部未第一手验证 | — | 保持收据式发行验证 |
| A2 | frontmatter 执行授权键无门 | finding | P2 | check_repository 增加 frontmatter 键白名单 |
| A3 | 退役名调用加载本机陈旧副本 | 仓库内 resisted；本机残留 finding | P2 | doctor 增加退役名目录只读告警 + 清扫文档 |
| A4 | description 旧名别名劫持 | resisted（边界文本 + 残留门 + 触发用例） | — | — |
| B1 | 伪造收据做 destination/source 路径穿越 | resisted（规范身份逐字钉死） | — | — |
| B2 | 伪造收据删除/覆盖非自有内容 | resisted（身份 + 内容等值双验） | — | — |
| B3 | 符号链接置换（收据/目录/目标/包内） | resisted（分层拒 symlink；同用户竞态无放大） | — | 可选：读取前复检收据非 symlink |
| B4 | migrate-receipts confused deputy / TOCTOU | resisted（planId 内容绑定 + 双重清点）；附 v1 搁浅 | P2（附随） | 修 v1 迁移路径或改文档；补 v1 夹具 |
| B5 | 陈旧/不同计划借 reviewed plan-id 执行 | resisted（重算比对 + 终验；残余竞态仅 DoS） | — | — |
| B6 | 旧收据部分重放 | resisted（target+source_root+摘要三点钉死） | — | 顺带：清理 :1468 死三元、锁回收策略 |
| C1 | 仓库文件经 caveman 胶囊注入提示词 | resisted（静态文本 + 枚举槽 + 摘要） | — | — |
| C2 | 胶囊渲染未校验 session_id | finding | P2 | 渲染前应用 SID_RE |
| C3 | zcode setup 翻转全局 hooks.enabled 且不恢复 | finding | P2 | 保存/恢复先值或在文档与输出中声明 |
| C4 | 词法 owned 识别跨 checkout 生效 | resisted（收敛到运行中代码；前提是已可写宿主配置） | — | 文档注明卸载半径 |
| C5 | llm-wiki SessionStart 原文注入项目可控行 | finding | P1 | 重生成/转义 + 字节上限 + 不可信出处标注 |

统计：15 个假设，10 个 resisted，6 个 finding（1 个 P1：C5；5 个 P2：A2、A3、B4 附随、C2、C3）。

范围与限度：本评审为纯静态分析——沿源码推演攻击路径，未执行任何真实利用，未对真实安装状态运行仓库脚本（仅 `--help`），未触碰网络，未验证第三方包管理器（`skills` CLI）与钩子宿主（Claude/zcode/Codex）的内部实现；凡依赖宿主行为的结论（A1 的复制语义、C3 的 `enabled` 语义、C5 的 additionalContext 信任权重）均以仓库自证收据或代码事实为界并已在正文标注不确定性。所有行号基于 worktree `azhou-ai-hub-2cc7ce/8` 的检出（HEAD `59d4db8`）；后续修复应以合入分支时的行号重校。

Reviewer: zcode-agent/threat-review-t3/2026-09-13
