# Minimal behavior eval-case contract

本文定义本目录中最小的**行为证据层**（minimal behavior eval-case）：一个包在"wiring-integrity benchmark 已绿"之上、在"paired-judges 行为演化"之下，所能做出的第一层真实行为声明。它回答一个问题：*这个 skill 在冻结条件下被真实调用一次时，是否做到了它的入口合同所承诺的事。*

适用对象：目录中标注 "No behavior benchmark yet" 的包（当前为 eli5、ask-azhou、autoresearch、session-insights）。super-caveman 的 promotion 评测链是更高一层，不受本文约束。

## 六要素

一个 eval-case 必须同时冻结以下六项，缺一即不算行为证据：

1. **Frozen prompt**：逐字固定的触发输入（版本化在 case 文件里，含语言）。改一个字即新 case。
2. **Frozen runtime**：harness 名称与版本、模型标识、操作系统；skill 内容以某个仓库 commit 的 tree digest 锚定。
3. **Wall-clock budget**：单次运行的明确时限；超时即该次 attempt 记为 `fail(timeout)`，不得重跑择优。
4. **Permission scope**：允许触碰的路径/工具/网络面，逐项列出；越界即 `fail(boundary)`。
5. **Attempt-1 single run**：每个 case 每个（runtime × commit）组合只跑一次并如实记录；不重跑、不采样、不挑结果。重跑产生新 attempt 编号，全部留存。
6. **Verdict vocabulary**：`pass` / `fail(<anchor>)` / `hold(<reason>)`。`pass` 的每个锚点必须来自 case 文件预声明的机械可查断言（产物存在、产物含预声明结构、退出码），不接受"看起来不错"。

## 存放与命名

- case 定义：`benchmarks/<skill>/behavior/<case-id>.json`（prompt、断言、budget、permission scope）。
- 运行回据：`evidence/<skill>-evalcase-<case-id>-<harness>-<日期>.md`，格式沿用现有 evidence 回据。
- attempt 编号写进回据文件名或首行，不覆盖旧 attempt。

## 声明纪律

- 一个 case 的 `pass` 只允许把包的公开措辞从 "No behavior benchmark yet" 升级为 "minimal behavior eval-case (n=1) passed (`<case-id>`)"。
- n=1 **不是**泛化行为声明：不得据此声称"在所有输入上"如何；跨输入泛化需要多个 case，跨模型泛化需要 paired judges（那是 `docs/skill-standard.md` §5 的 promotion 链）。
- 任何 `fail`/`hold` 如实公开，不触发门禁红灯（本契约是证据层，不是回归门）；但禁止在存在未公开 fail 记录时声明 pass。
- 升级措辞的编辑若触及 promotion receipt 的 reviewed 集，按 `AGENTS.md` 走收据重绑。

## 当前占位（尚未有任何 eval-case 运行）

| Package | 候选首案例（最小诚实锚点） |
|---|---|
| eli5 | 冻结主题 → 断言：自包含 HTML 产物存在、含预声明结构标记、精度关键拒绝句在边界输入下出现 |
| ask-azhou | 冻结意图输入 → 断言：推荐指向真实 canonical skill 且边界句在场；负例输入得到 ❌ 而非伪造推荐 |
| autoresearch | 冻结非 NVIDIA 主机 → 断言：prepare 产出具名 `unsupported` hold 且无任何运行启动（复用 #219 的回据形态） |
| session-insights | 冻结合成 store → 断言：aggregate golden 逐字节一致且报告含 holds 节（对真实行为的接线再确认） |

这些占位不是承诺；每包第一次真实运行前，公开措辞维持 "No behavior benchmark yet"。
