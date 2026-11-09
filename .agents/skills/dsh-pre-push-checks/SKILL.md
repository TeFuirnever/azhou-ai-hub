---
name: dsh-pre-push-checks
description: "推送、标记可审查或报告检查结果前，以及已发布分支同步后核对变更及验证证据。"
---

# dsh-pre-push-checks

本 Skill 仅用于当前项目。用户授权、项目 AGENTS.md 和实际宿主能力优先。

## 锁定待交付变化

核对 checkout、branch、当前远端 PR base/stack parent 和精确 head。依 [Foundation scope](../../../docs/foundations.md#experimental-change-scope) 运行真实 scope 命令，区分提交、暂存、未暂存和未忽略新文件；完整重查结果，并发变化不能排除就暂停依赖它。忽略的本地 Skill 需另用文件清单/指纹绑定，不能声称 Git scope 已包含它。

改变 base、合并或同步后重新分析实际消费者及已失效证据。保留准确命令、所选测试数量、版本、环境、结果和没有运行的部分。

## 选择检查

本项目交付前必须运行 `python3 scripts/verify.py`，不能照搬 DSH“无统一本地基线”的规则。按 AGENTS.md 加上受影响包的专门门禁；额外检查只覆盖实际风险：

| 变化 | 需要的证据 |
| --- | --- |
| 行为/脚本 | 能在该回归下失败的 owner 测试；共享合同补直接消费者 |
| 异步/资源/CI 拓扑 | 原子分配、全局恢复、确定性负对照、静止清理；必要时独立进程并发 |
| 文档/Skill/生成目录 | 实际格式/链接、双语、owner 与生成新鲜度、适用 validator |
| UI | 实际页面的受影响主题、窄宽、内容/交互状态；自动测试不代替视觉检查 |
| 模型/CLI/编辑器可见输出 | owner 的真实可运行例子或快照，不仅检查字符串存在 |
| manifest/exports/bin/worker/安装 | 相应构建及真实构建产物/安装入口 smoke；区分 build 与全仓类型检查 |
| 真实 provider 行为 | 获授权且环境具备时跑实际场景；不暴露凭据，替身单列 |

先看实际脚本与帮助确认参数传递，核对 runner 真正选择了哪些测试。测试选择与覆盖源码选择不同；不能用 zero tests、缩窄 affected source 或放宽阈值伪造通过。依赖图无法发现配置加载、子进程、生成物和外部入口时显式选择其用例。不复制 DSH 专用快照目录、命令或 hook 假设。

已通过的证据只因代码/环境变化、失败或实质新风险重跑，不因随后 commit/push 机械重复。pre-commit fixer 修改了文件则检查新 bytes 并补受影响验证。

## 发布与历史

本 Skill 负责证据，不自动授权 push、改写历史或 merge。普通授权推送前先通过所需检查；失败先修复或具名报告，不绕 hook 赌 CI。环境失败需给准确特征与平台证据，不以本地猜测归因。

获授权改写非默认分支前读当前远端 OID，用 exact `--force-with-lease=<branch>:<observed-oid>`，禁止裸 force 和重写公开默认分支。若现有 stack 工具在同步时会重写并发布，事前记录干净状态、顺序、heads，之后立即重查每层 base/head 并验证；失败保留现场、修复再发布，验证前不 merge。

推送后核对远端实际 OID、CI、未解决 review、批准与 mergeability。没有 checks 不等于通过：先区分冲突阻止 PR workflow、触发条件、跳过和真实基础设施故障，不用空提交或 draft/ready 往返伪造事件。旧 head 的批准/评论位置不是新 head 的证据。合并遵守项目 squash-only、required checks 和全部讨论解决规则。

来源、适配边界和许可证见 [provenance.md](provenance.md)。
