# Spec: Windows/macOS 跨平台兼容修复

> Spec 日期：2026-09-07（Asia/Shanghai）
> 来源证据：[docs/research/2026-09-07-skill-cross-platform-macos-windows.md](../research/2026-09-07-skill-cross-platform-macos-windows.md)（研究笔记，六类失败与机制对照）、[evidence/windows-unit-test-v0.7.0-2026-09-07.md](../../evidence/windows-unit-test-v0.7.0-2026-09-07.md)（Windows 实测收据：427 测试，73 FAIL + 21 ERROR + 2 skipped，全部为平台兼容性问题）。
> 状态：ready-for-agent。本 spec 只定义工作，不执行修改；此前一轮修复尝试已按维护者指示整体回退，回退后全量门禁绿。

## Problem Statement

一个 Windows 用户按 README/installation 文档开始使用本仓库的 skill：安装四件套在默认 link 模式上被符号链接特权挡住；文档示例命令 `python3` 被 Microsoft Store 存根拦截（退出码 9009）；安装 super-caveman 时状态写入在文件被占用时报出掩盖真实错误的 `PermissionError`；想复算 provenance 摘要却发现复算命令只存在于 Unix 工具链。同时，仓库所有 "supported" 主张没有任何 OS 维度：全部 CI 只跑 ubuntu，公开文档对 Windows 只字未提——支持状态不可知，失败无人负责。

## Solution

让同一份 canonical 包在 macOS 与 Windows 上等价可用，并让声明与证据对齐：

1. **代码与测试护栏**（macOS 上即可回归验证）：adapter 原子写清理分支不再掩盖真实错误；excalidraw helper 的缓存目录平台化、JSON 读取显式 UTF-8；fuzz 看门狗在无 `SIGALRM` 平台降级；权限位类断言按平台语义加护栏。
2. **文档与合同双平台化**：provenance 复算命令补标准库等价（输出逐字节一致）；文档命令入口统一为三大平台公共命令；hook 与安装文档声明宿主 shell / 权限前提，给出 Windows 变体。
3. **声明与 CI 对齐**：门禁增加 Windows runner（跑同一套纯标准库检查）；support-matrix 增加 OS 维度，每条 OS 主张都有 CI job 或 checked-in 收据背书；README 双语同步。

按三个里程碑推进：M1（代码与测试护栏）→ M2（文档与合同）→ M3（CI 与声明）。M3 的公开声明以 M1/M2 之后的 Windows 实测收据为前提，不允许文档先行。

## User Stories

1. 作为 Windows 上的 skill 使用者，我想按 installation 文档一次成功安装 Foundation 四件套，以便不需要先踩一次符号链接特权失败再自行摸索。
2. 作为 Windows 使用者，我想在标准权限（无开发者模式、无管理员）下完成安装，以便在公司管控机器上也能使用。
3. 作为 Windows 使用者，我想用官方 Python 安装器的标准命令执行所有文档示例，以便不被 Microsoft Store 存根（退出码 9009）拦截。
4. 作为 Windows 使用者，我想安装 super-caveman 并让三个 harness 的 hook 状态写入稳定成功，以便压缩守卫真正生效而不是装完即错。
5. 作为 Windows 使用者，当状态文件被杀毒或索引服务短暂占用时，我想收到明确的"原子写入失败"错误（含目标路径），以便知道真实故障而不是一个来历不明的 `PermissionError`。
6. 作为 macOS 使用者，我想所有修复在 macOS 上行为保持不变（含测试全绿），以便升级没有回归风险。
7. 作为 Windows 使用者，我想使用 excalidraw helper 的网络回退与预缓存目录，以便不依赖 Unix 的 `/tmp` 约定。
8. 作为 Windows 使用者，我想在无 `shasum`/`find|sort -z|xargs` 工具链的机器上复算四个包的 provenance SHA-256（含排序 manifest 管线）得到与文档相同的摘要，以便验证来源与捆绑资产未被改动。
9. 作为 Windows 贡献者，我想权限位类测试在 Windows 上诚实跳过或条件化，以便测试结果反映真实平台语义而不是一屏假失败。
10. 作为贡献者，我想 fuzz 冒烟在无 `SIGALRM` 的平台仍然运行（仅降级单输入超时策略），以便 Windows 不失去解析器崩溃回归的覆盖。
11. 作为维护者，我想 CI 增加 Windows runner 跑同一套纯标准库门禁，以便 Windows 兼容回归被机器持续拦截，而不是依赖某个人记得在 Windows 上试。
12. 作为维护者，我想 support-matrix 增加 OS 维度，且每条 OS 主张都能指向一个 CI job 或 checked-in 收据，以便公开主张可核验、不空谈。
13. 作为维护者，我想触及 promotion 覆盖路径的文档改动与晋级流程合并处理，以便公共 gate 不出现"改了内容、收据失配"的失败。
14. 作为 README 读者（中英双语），我想安装与验证命令提供 Windows 变体或等价说明，以便两种语言的读者得到一致且可执行的指引。
15. 作为依 skill-standard 编写新 skill 的下游作者，我想 setup 命令形态有跨平台规范（及防回潮 lint），以便新 skill 不再无意引入 POSIX-only 命令。
16. 作为 hook 用户（Claude Code / Codex / ZCode），我想 setup 文档明确声明宿主 shell 前提（Git Bash 存在性、PowerShell fallback 下不受支持），以便知道 hook 在我的环境是否在主张范围内。
17. 作为审计者，我想每条 OS 声明都能回溯到研究笔记的实测对照与 evidence 收据，以便独立复核而不需要信任转述。
18. 作为 CI 系统，我想 Windows job 失败时在门禁输出中显式记录原因，以便不允许任何"静默跳过"式的假绿。
19. 作为中文 Windows 控制台用户，我想含品牌 emoji 输出的脚本在文档中声明 `PYTHONUTF8` 前提，以便在 cp936 代码页下不遭遇 `UnicodeEncodeError`。
20. 作为 excalidraw 高级工作流的使用者，我想文档中的手动预缓存路径与 helper 实际缓存目录一致，以便照做之后真的命中缓存。

## Implementation Decisions

- **原子写清理加固（三个 harness adapter 同步落地）**：临时文件清理是尽力而为行为——除"文件不存在"外，同时容忍"文件被占用"；`os.replace` 的真实失败必须以其自身的错误向上传播，不得被清理分支的反向异常掩盖。修复附带一句说明 Windows 语义的注释（约束代码自身无法表达）。
- **同型核查结论（已复核，无需改动）**：仓库内其余 unlink 均为不同模式——CLI 回滚删除（异常整体兜底返回失败）与锁内直删（先拒绝符号链接再删除自有文件），不属于"finally 清理反向掩盖"形态，不在本 spec 范围内修改。
- **excalidraw helper 平台化**：缓存根从硬编码 Unix 路径改为"系统临时目录 + 固定子目录"；索引 JSON 读取补显式 UTF-8（与该文件其余读取处既有做法一致）；高级工作流文档的预缓存路径说明同步，保留各平台示例。
- **fuzz 看门狗降级**：`SIGALRM`/`ITIMER_REAL` 存在时行为逐字节不变；不存在时跳过 itimer 安装，仅依赖既有的 `--seconds` 墙上时钟预算与输入数上限。不加线程定时器（无法向主线程注入异常，等效性差）。
- **权限位护栏两分法**：整个测试就是在考察 POSIX 权限语义 → 平台跳过（沿用既有先例的理由文案）；权限断言只是测试的一个侧面 → 仅条件化该断言，保留其余覆盖。跳过必须带理由字符串，禁止无解释 skip。
- **provenance 等价命令为增量行**：在既有 `shasum` 命令旁补标准库 `hashlib` 等价（含 manifest 管线的一段式脚本），不修改既有命令形态、不动任何锁定摘要。等价性验收标准：两条命令在 macOS 上输出逐字节一致（bundle 与 manifest 两处已在 2026-09-07 预验证通过）。
- **已知坑（M1 第一步）**：上一轮修复尝试触发过一次全量门禁的 unit tests 失败，具体 pinning 测试未及定位即回退。M1 先在全量单测下逐项落地（或先定位该 pinning 测试），避免最后一次撞线。
- **promotion 边界**：凡路径落在最新 exact-diff 批准记录覆盖清单内（如 super-caveman 的 setup 文档、品牌层、CHANGELOG、benchmark manifest），必须与 promotion ride 合并落地或走新一轮晋级；本 spec 的 M1 全部与 M2 的一部分在该边界之外，可直接推进。
- **声明与 CI 同提交**：support-matrix 的 OS 维度、README 双语、CI runner 变更属于同一原子变更；任一 OS 主张没有对应 CI job 或收据即不许落库。
- **既有不变式全部保留**：收据与状态机器字段的 `as_posix()` 规范化、emoji 不进机器字段、命名空间 ASCII 约束、`eol=lf` 行尾合同、`sys.executable` + 列表参数 subprocess 的门禁写法。

## Testing Decisions

- **好测试的标准**：只测外部行为——CLI 退出码、JSON 输出、收据字段、文件系统终态；不测内部实现细节。既有套件已践行此标准，本 spec 沿用。
- **测试缝隙（全部为既有缝隙，不新造框架）**：
  1. 单测 discover 套件（本地 + CI）：adapter 行为、runtime/relay 状态权限语义、fuzz 冒烟、helper 行为的回归缝隙；adapter 与状态类的既有测试即 prior art。
  2. `verify.py` 确定性门禁：仓库策略、全部单测、benchmark-integrity、空白检查——Windows job 复用同一入口。
  3. benchmark-integrity 套件：品牌与收据合同不因修复漂移。
  4. 新增的 OS 维度：GitHub Actions Windows runner 跑缝隙 2（唯一的新增点，且只是给既有入口加 runner，不是新测试框架）。
  5. M1/M2 过渡期验收缝隙：沿 evidence 收据的命令协议做一次人工 Windows 实测并 checked-in 到 evidence/，作为 M3 声明的前置证据。
- **回归红线**：macOS 上现有 429 个测试与四个 benchmark-integrity 保持全绿；新增平台跳过必须逐个带理由；清理加固不得改变"replace 失败 → AdapterError（含路径）"的既有错误合同。
- **防回潮**：仓库合同检查扩展"setup 命令形态"lint（文档命令入口统一），合同测试沿用 check_repository 既有测试的写法。

## Out of Scope

- Harness 层可移植性（发现路径、调用语法、权限模型差异）——由既有 harness 可移植性研究与 support-matrix 的 harness 维度管辖。
- support-matrix 的 harness × OS 全二维展开——等 Windows 实测收据积累后再议，避免无证据扩表。
- WSL 专项优化、Python 3.11 以下支持、品牌/emoji 合同修订、hook 执行模型重设计。
- `sed -i`/`mktemp`/`readlink -f` 类 POSIX 坑的系统性清理（本仓库现状几乎不踩，见研究笔记 1.2"未发现"节）。
- 本 spec 自身不执行任何代码修改。

## Further Notes

- 全部行号级证据锚定 2026-09-07 工作区：研究笔记第一、三节给出逐包差距对照表与风险归类；evidence 收据给出六类失败的完整清单（约 35 项可由环境配置消除：开发者模式 + `python3` 别名；其余约 55 项需要本 spec 的 M1/M2）。
- 回退教训（重要）：修复集中存在被单测固定（pinning）的内容——具体测试未定位。实施 M1 时先定位再落地，防止最后一次全量门禁撞线。
- 前瞻：Python 3.15 默认 UTF-8 模式（PEP 686）落地后，cp936 控制台输出风险自动收窄，届时可撤下相应文档前提；不在本轮。

## 附注：win-01 执行记录（2026-09-07）

上一条"回退教训"已在 treehouse 隔离工作树（lease `8e2fbbc1893e78be1652a48e89178460`）中闭环：

- **Pinning 已命名并归因**：重放完整 M1 批次后，全量单测恰好失败 4 项，全部位于 super-caveman benchmark 测试——`test_passing_attempt_is_bound_to_stable_runtime_tree`（直接断言）、`test_public_integrity_allows_squash_snapshot_but_rejects_blob_drift`、`test_capability_and_trigger_integrity`、`test_approved_benchmark_requires_raw_approval_environment`。机制：benchmark 把当前通过评测（revision-93f38a6b）绑定到 `sha256_skill_tree()` 的实时值，任何 `skills/super-caveman/` 下变更（含 scripts/ 三 adapter）都会使绑定失效——这是门禁在正确要求晋级流程，不是修复缺陷。
- **处置**：三 adapter 的 51 行修复 diff 从工作树摘出，作为晋级候选暂存于 `.azhou/win-02-adapter-atomic-write/`（候选 + README）；移除 adapter 后其余 10 文件批次 **429 单测全绿**，已落地主检出。win-02 落地必须随维护者的 fresh attempt + exact-diff 批准晋级流程。
- **连带澄清 Windows 实测分类六**：Windows v0.7.0 实测中失败的 `test_capability_and_trigger_integrity` 与本次归因同属绑定校验——支持"该机失败源于树偏移/平台差异，而非上游遗漏提交证据文件"的修正判断（研究笔记 1.6 分类 6）。
- **win-08 附带发现**：closeout hook 的 event 路径恒 exit 0（fail-open），静态片段中的 `|| true` 为冗余，渲染器输出已去除；`main()` 的正界校验曾误伤无 `max_input_bytes` 属性的子命令，已限定为 event 子命令。静态片段两文件删除，改为 `render-hooks` 渲染（repo-pedant setup/trigger-hooks 文档与 llm-wiki setup 同步声明宿主 shell 前提；super-caveman setup 文档属 promotion 覆盖路径，其声明随晋级批次落地）。
- **win-09**：installation.md 新增 "Windows notes" 小节（PowerShell 变量/复制对照表、link 模式特权前提与 copy 绕行、`PYTHONUTF8` 提示、hook 宿主 shell 前提）；Windows 全流程复现收据挂 win-05。
