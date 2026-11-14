# Azhou immersive experience plan

按顺序交付阿舟连续启动与工作区体验，保留 Azhou IP、最新已保存设置与原生控件。
本计划是设计资产，不是执行授权或已通过回执。
P01 冻结基线，P02 与 P03 可并行，P04 集成视觉，P05 独立完成 DSH，P06 分端收尾。

## How to read this

One box is one unit of work. Every box names the evidence that checks it. Check a box only when its evidence exists. The body is a how-to. The appendices explain and record.

实施使用 `packages/pstack-agent-harness/harness/pstack/codex/skills/poteto-mode/playbooks/autopilot-stack.md`。产品 PR 由操作者最终合并，文档归档本身不启动实施。该安排不限制用户已授权的本设计文档 PR 合并。更高优先级会话要求 PR 为草稿时先建草稿，通过审阅后再标为 ready，不照抄上游 never draft。

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] 向操作者说明协议并等待明确启动产品实施。保存该次授权证据。
- [ ] 在开始与每个审计 tick 重新读取 `git show origin/main:packages/pstack-agent-harness/harness/pstack/codex/skills/poteto-mode/playbooks/autopilot-stack.md`、swarm、opening-a-pr 及当前项目 AGENTS。保存读取的 SHA。
- [ ] 用可用调度器落实上游 `/loop 1h` 意图，记录任务与停止条件。不可用时明确保持人工 tick，不声称已调度。没有实施授权前不安排执行循环。
- [ ] 每个 tick 重新读协议，按实际副作用检查 owner 与证据。仅对新变化发 status message，并记录本轮决定。发现停滞先查 owner，再决定接替，不能以无进程推断可抢占。
- [ ] 收到 hold 立即停止所有写入，保留工作树和未合入成果。

### Spawn owners

- [ ] 按 TASKS.json 核对原编号与 PR 依赖。一个 PR 一个 owner、独立 Treehouse 租约与分支，记录在私有任务证据。
- [ ] P01 先行。P02 和 P03 在 P01 后独立。P04 在 P02 与 P03 后。P05 在 P01 与 P03 后。P06 等 P04 完成且 P05 有独立结果。
- [ ] 保持每节列出的文件边界。共享文件只允许一个 writer，依赖 PR 合入或明确堆叠后才写。
- [ ] P02、P03、P04 及实际改变交互的 P05 在截图和视频审阅前不得合并。P05 仅记能力缺口时重新记录其无交互范围。

### PR mechanics, for every PR

- [ ] 先解析 forge，已安装且可解析仓库的 Origin 优先，否则用 gh 并记录原因。不得绕过仓库 hooks。
- [ ] 提交前运行 deslop，审阅前运行 no-comments。只改本任务文档或该 PR 允许的生产边界。
- [ ] 运行仓库 lint、类型与 `python3 scripts/verify.py`。记录冻结输入与结果，外部变化则作废重跑。
- [ ] PR 的 Why 说明用户目标。按当前会话默认先建草稿，不把草稿状态误报为可合并。
- [ ] 逐项处理所有审核线程和必需检查。重新定基前结束冻结验证，禁止改写他人的未提交分支。

### Verdict and merge, for every PR

- [ ] 在精确代码候选 SHA 做独立审查，审计代码、原始本地证据与支持声明，不只读 PR 正文。
- [ ] 每个新增行为跑真实交互和性能协议。十条 lane 可按实际宿主能力分批执行，不谎称十台云 VM 或可用模型。
- [ ] 仅精确验证过的差异获得 verdict。改变内容、输入或运行身份后刷新对应验证。合并前采用 shipping 的 patch-id 规则，不复用已失效批准。
- [ ] 所有 required checks 通过且 review threads 全解决后交操作者 squash 合并。UI 仍需独立人工视觉批准。

### Boot recipe, for every live lane

- [ ] 获取候选分支并 checkout 记录的完整 head SHA。在独立租约中保存源、索引、输入和运行时指纹。
- [ ] 按 `packages/agent-skin/docs/local-install-sop.md` 规划测试入口，取得所需安装和启动权限后才操作。不要重启正在工作的宿主。
- [ ] 用当前可用真实 UI 控制工具操作宿主。没有驱动能力时留下具体验收步骤并标记 blocked，不改用 mock 宣称 live pass。
- [ ] 每条 lane 保存截图到私有证据目录的对应相对路径，保存完整显示器视频与事件日志。先检查画面无敏感内容，公开 PR 只放脱敏素材。

## 冻结来源、所有权与协议 (P01)

**Depends on.** None.

**Files.**

- [ ] 审核并仅在需要时修改 `packages/agent-skin/docs/design/azhou-immersive-experience/*`，在 PR diff 中保存精确文件清单。

**Build.**

- [ ] 核对原需求包、修复分支当前差异、运行输入指纹和安装所有权。记录引用及未证明项，不重做已有代码。冻结首帧、设置和对比协议。 以 NH-00, NH-10, ALIGN-00, ALIGN-01 的对应产物作为完成证据。

**You see.**

- [ ] 在本 PR 回执中展示对应可观察结果。未实现、blocked 与未运行分别列出，不以文档或编译成功代替用户可见结果。

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] 运行 `python3 scripts/verify.py` 并保存结果。按文件边界运行 `packages/agent-skin/docs/testing.md` 中对应生产入口和状态测试；无产品代码时检查链接、依赖和禁止数据扫描。

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `gpt-6-luna` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. 对比 trunk 与候选来源清单。Save `p01/lane-1.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。 若 trunk 无此功能，记录事实，单独验新增行为与最终状态，不虚构对比。
- [ ] Lane 2. 核对原始需求包映射。Save `p01/lane-2.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。
- [ ] Lane 3. 核对现有修复分支所有权。Save `p01/lane-3.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。
- [ ] Lane 4. 核对签名与可信入口。Save `p01/lane-4.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。
- [ ] Lane 5. 核对设置保存链。Save `p01/lane-5.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。
- [ ] Lane 6. 核对工作区 ready 定义。Save `p01/lane-6.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。
- [ ] Lane 7. 核对热启动策略。Save `p01/lane-7.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。
- [ ] Lane 8. 核对 DSH 实际 hook。Save `p01/lane-8.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。
- [ ] Lane 9. 核对 Pet 当前可见与独立边界。Save `p01/lane-9.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。
- [ ] Lane 10. 核对回退与租约保留责任。Save `p01/lane-10.png`. Pass when 来源或能力得到可复核结论，未知被明确标记而非推定支持。

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. 对两版测量该阶段实际交付的检查或素材读取耗时与峰值 RSS，不声称运行时优化。
- [ ] Probe. 同设备相同输入交错运行五次，保存命令、原始样本及候选摘要。纯文档检查不得替代整体验收。
- [ ] Baseline. 先记录 trunk 的实际值与可比范围。新素材或缺失功能单独记新增工作。
- [ ] Rule. 可比工作 p50 耗时超过 trunk 1.10 倍或 RSS 超过 1.20 倍需调查并重新定界。不同工作不得强算比值；未冻结绝对预算则维持 inconclusive。

**Review gate.** None. P01 is not review-gated.

**Merge.**

- [ ] 独立 root verdict 对应精确 head SHA，所有检查与线程解决。由操作者 squash 合并，保留实际合并结果及恢复点后才考虑释放租约。

## 审阅阿舟场景和素材 (P02)

**Depends on.** P01.

**Files.**

- [ ] 审核并仅在需要时修改 `packages/agent-skin/assets/azhou/*`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/theme-config.json`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/tools/verify-artifacts.py`，在 PR diff 中保存精确文件清单。

**Build.**

- [ ] 先审角色参考页，再审场景母版、关键帧和壁纸。只在授权及人工通过后提交生产资产，联动素材清单、许可与生产验证。 以 ALIGN-02, ALIGN-03, ALIGN-04 的对应产物作为完成证据。

**You see.**

- [ ] 在本 PR 回执中展示对应可观察结果。未实现、blocked 与未运行分别列出，不以文档或编译成功代替用户可见结果。

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] 运行 `python3 scripts/verify.py` 并保存结果。按文件边界运行 `packages/agent-skin/docs/testing.md` 中对应生产入口和状态测试；无产品代码时检查链接、依赖和禁止数据扫描。

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `gpt-6-luna` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. 并排对比 trunk 与候选角色身份。Save `p02/lane-1.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若 trunk 无此功能，记录事实，单独验新增行为与最终状态，不虚构对比。
- [ ] Lane 2. 审角色正面与侧面。Save `p02/lane-2.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 3. 审浅色宽窗。Save `p02/lane-3.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 4. 审深色宽窗。Save `p02/lane-4.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 5. 审窄窗裁切。Save `p02/lane-5.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 6. 审底板与末帧。Save `p02/lane-6.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 7. 审工作区留白。Save `p02/lane-7.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 8. 审静态降级图。Save `p02/lane-8.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 9. 审素材透明边缘和元数据。Save `p02/lane-9.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 10. 审素材来源与许可清单。Save `p02/lane-10.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. 对两版测量该阶段实际交付的检查或素材读取耗时与峰值 RSS，不声称运行时优化。
- [ ] Probe. 同设备相同输入交错运行五次，保存命令、原始样本及候选摘要。纯文档检查不得替代整体验收。
- [ ] Baseline. 先记录 trunk 的实际值与可比范围。新素材或缺失功能单独记新增工作。
- [ ] Rule. 可比工作 p50 耗时超过 trunk 1.10 倍或 RSS 超过 1.20 倍需调查并重新定界。不同工作不得强算比值；未冻结绝对预算则维持 inconclusive。

**Review gate.** The operator reviews before merge.

- [ ] 将本节 screenshot 与 30 至 60 秒 video 发给 operator，记录其对精确候选的审阅。未批准停在 merge-ready。

**Merge.**

- [ ] 独立 root verdict 对应精确 head SHA，所有检查与线程解决。由操作者 squash 合并，保留实际合并结果及恢复点后才考虑释放租约。

## 完成原生快照与交接 (P03)

**Depends on.** P01.

**Files.**

- [ ] 审核并仅在需要时修改 `packages/agent-skin/Native/*`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/image-settings.js`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/extension/*`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/tools/*`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `scripts/integration_startup_animation.py`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `tests/test_agent_skin*`，在 PR diff 中保存精确文件清单。

**Build.**

- [ ] 先与现有修复 owner 协调已完成部分，再实现剩余只读快照、单播放器、代际就绪、跳过和绝对期限。同步所有终态消费者及测试，不创建第二设置库。 以 NH-20, NH-30 的对应产物作为完成证据。

**You see.**

- [ ] 在本 PR 回执中展示对应可观察结果。未实现、blocked 与未运行分别列出，不以文档或编译成功代替用户可见结果。

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] 运行 `python3 scripts/verify.py` 并保存结果。按文件边界运行 `packages/agent-skin/docs/testing.md` 中对应生产入口和状态测试；无产品代码时检查链接、依赖和禁止数据扫描。

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `gpt-6-luna` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. 相同冷启动比较 trunk 与候选。Save `p03/lane-1.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若 trunk 无此功能，记录事实，单独验新增行为与最终状态，不虚构对比。
- [ ] Lane 2. 保存自定义设置后冷启。Save `p03/lane-2.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 3. 空记录与损坏记录分别启动。Save `p03/lane-3.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 4. 合法大图的分块快照。Save `p03/lane-4.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 5. 快照前页面退休与替换。Save `p03/lane-5.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 6. 快照后页面替换。Save `p03/lane-6.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 7. cover 与播放中分别跳过。Save `p03/lane-7.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 8. 热启动与重复打开。Save `p03/lane-8.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 9. 慢宿主及总期限释放。Save `p03/lane-9.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 10. 用户切应用与多显示器焦点。Save `p03/lane-10.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. 首个自有帧、动画持续时间、工作区交互就绪、峰值 RSS 与结束后 60 秒静置 CPU。
- [ ] Probe. 按 ACCEPTANCE.md 在同设备以相同设置交错测 trunk 和 head，各至少五次，保留故障样本。
- [ ] Baseline. 先记录 trunk 原始值、p50、最坏值及录屏开销，缺失功能单列。
- [ ] Rule. 使用 NH-10 冻结门禁。初始提案为首帧 500 ms、就绪 p50 不超过可比 trunk 1.10 倍、RSS 不超过 1.20 倍；12 秒播放和 60 秒总预算不变。未测基线不得判通过。

**Review gate.** The operator reviews before merge.

- [ ] 将本节 screenshot 与 30 至 60 秒 video 发给 operator，记录其对精确候选的审阅。未批准停在 merge-ready。

**Merge.**

- [ ] 独立 root verdict 对应精确 head SHA，所有检查与线程解决。由操作者 squash 合并，保留实际合并结果及恢复点后才考虑释放租约。

## 衔接阿舟动画与分层工作区 (P04)

**Depends on.** P02, P03.

**Files.**

- [ ] 审核并仅在需要时修改 `packages/agent-skin/animation.js`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/wallpaper/*`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/style.css`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/theme-config.json`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/extension/codex-page-adapter.mjs`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/tools/*`，在 PR diff 中保存精确文件清单。

**Build.**

- [ ] 把已审场景放入 12 秒编排并匹配末帧与壁纸焦点。实现首页与任务页的可读层级。保持原生控件、preview 和既有 Pet，不改 Pet 安装。 以 ALIGN-05, ALIGN-06, ALIGN-07 的对应产物作为完成证据。

**You see.**

- [ ] 在本 PR 回执中展示对应可观察结果。未实现、blocked 与未运行分别列出，不以文档或编译成功代替用户可见结果。

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] 运行 `python3 scripts/verify.py` 并保存结果。按文件边界运行 `packages/agent-skin/docs/testing.md` 中对应生产入口和状态测试；无产品代码时检查链接、依赖和禁止数据扫描。

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `gpt-6-luna` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. 同样首页到任务页比较 trunk 与候选。Save `p04/lane-1.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若 trunk 无此功能，记录事实，单独验新增行为与最终状态，不虚构对比。
- [ ] Lane 2. 浅色主题长对话。Save `p04/lane-2.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 3. 深色主题代码块。Save `p04/lane-3.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 4. 窄窗与窗口缩放。Save `p04/lane-4.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 5. 菜单与对话框操作。Save `p04/lane-5.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 6. 保存取消预览及恢复默认。Save `p04/lane-6.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 7. 禁用和减弱动态。Save `p04/lane-7.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 8. 末帧到壁纸完整交接。Save `p04/lane-8.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 9. Pet mini 与 detached 不注入。Save `p04/lane-9.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 10. 动画后静置与资源释放。Save `p04/lane-10.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. 首个自有帧、动画持续时间、工作区交互就绪、峰值 RSS 与结束后 60 秒静置 CPU。
- [ ] Probe. 按 ACCEPTANCE.md 在同设备以相同设置交错测 trunk 和 head，各至少五次，保留故障样本。
- [ ] Baseline. 先记录 trunk 原始值、p50、最坏值及录屏开销，缺失功能单列。
- [ ] Rule. 使用 NH-10 冻结门禁。初始提案为首帧 500 ms、就绪 p50 不超过可比 trunk 1.10 倍、RSS 不超过 1.20 倍；12 秒播放和 60 秒总预算不变。未测基线不得判通过。

**Review gate.** The operator reviews before merge.

- [ ] 将本节 screenshot 与 30 至 60 秒 video 发给 operator，记录其对精确候选的审阅。未批准停在 merge-ready。

**Merge.**

- [ ] 独立 root verdict 对应精确 head SHA，所有检查与线程解决。由操作者 squash 合并，保留实际合并结果及恢复点后才考虑释放租约。

## 证明并接入 DSH 首帧能力 (P05)

**Depends on.** P01, P03.

**Files.**

- [ ] 审核并仅在需要时修改 `packages/agent-skin/extension/hosts/*`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/tools/build-dsh-plugin.py`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/tools/*dsh*`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `packages/agent-skin/docs/dsh-plugin.md`，在 PR diff 中保存精确文件清单。

**Build.**

- [ ] 先证明当前 DSH 的早期 hook、CSP 和 desktop 支持。只有支持时实施 gate、独立 watchdog 与原子接管。无支持时提交脱敏能力缺口，不改官方宿主。 以 NH-11, NH-40 的对应产物作为完成证据。

**You see.**

- [ ] 在本 PR 回执中展示对应可观察结果。未实现、blocked 与未运行分别列出，不以文档或编译成功代替用户可见结果。

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] 运行 `python3 scripts/verify.py` 并保存结果。按文件边界运行 `packages/agent-skin/docs/testing.md` 中对应生产入口和状态测试；无产品代码时检查链接、依赖和禁止数据扫描。

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `gpt-6-luna` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. 同样 DSH 文档启动比较 trunk 与候选。Save `p05/lane-1.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。 若 trunk 无此功能，记录事实，单独验新增行为与最终状态，不虚构对比。
- [ ] Lane 2. web 早期 hook 与 CSP。Save `p05/lane-2.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。
- [ ] Lane 3. desktop 早期 hook 与 CSP。Save `p05/lane-3.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。
- [ ] Lane 4. client 无法下载。Save `p05/lane-4.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。
- [ ] Lane 5. 脚本被 CSP 拒绝。Save `p05/lane-5.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。
- [ ] Lane 6. 插件禁用与卸载。Save `p05/lane-6.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。
- [ ] Lane 7. 热重载不重播。Save `p05/lane-7.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。
- [ ] Lane 8. 导航与刷新策略。Save `p05/lane-8.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。
- [ ] Lane 9. 多 profile 设置隔离。Save `p05/lane-9.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。
- [ ] Lane 10. 早期 gate watchdog 与接管失败。Save `p05/lane-10.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若能力不成立，记录受影响动作、证据、owner 和解除条件，不能将 blocked 计作 pass。

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. 首个自有帧、动画持续时间、工作区交互就绪、峰值 RSS 与结束后 60 秒静置 CPU。
- [ ] Probe. 按 ACCEPTANCE.md 在同设备以相同设置交错测 trunk 和 head，各至少五次，保留故障样本。
- [ ] Baseline. 先记录 trunk 原始值、p50、最坏值及录屏开销，缺失功能单列。
- [ ] Rule. 使用 NH-10 冻结门禁。初始提案为首帧 500 ms、就绪 p50 不超过可比 trunk 1.10 倍、RSS 不超过 1.20 倍；12 秒播放和 60 秒总预算不变。未测基线不得判通过。

**Review gate.** The operator reviews before merge.

- [ ] 将本节 screenshot 与 30 至 60 秒 video 发给 operator，记录其对精确候选的审阅。未批准停在 merge-ready。

**Merge.**

- [ ] 独立 root verdict 对应精确 head SHA，所有检查与线程解决。由操作者 squash 合并，保留实际合并结果及恢复点后才考虑释放租约。

## 完成分端验收与支持文档 (P06)

**Depends on.** P04; P05 resolved as completed or evidenced blocked.

**Files.**

- [ ] 审核并仅在需要时修改 `packages/agent-skin/docs/*`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `docs/support-matrix.md`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `docs/integration-provenance.md`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `README.md`，在 PR diff 中保存精确文件清单。
- [ ] 审核并仅在需要时修改 `README.zh-CN.md`，在 PR diff 中保存精确文件清单。

**Build.**

- [ ] 完成每端真实入口与视觉验收，记录源码、构建、安装、加载和运行身份。同步双语说明与支持范围。DSH blocked 只允许 Codex 独立结论，不称双端完成。 以 NH-90, ALIGN-90 的对应产物作为完成证据。

**You see.**

- [ ] 在本 PR 回执中展示对应可观察结果。未实现、blocked 与未运行分别列出，不以文档或编译成功代替用户可见结果。

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] 运行 `python3 scripts/verify.py` 并保存结果。按文件边界运行 `packages/agent-skin/docs/testing.md` 中对应生产入口和状态测试；无产品代码时检查链接、依赖和禁止数据扫描。

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `gpt-6-luna` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. 重复已验收路径并对比 trunk 与候选。Save `p06/lane-1.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。 若 trunk 无此功能，记录事实，单独验新增行为与最终状态，不虚构对比。
- [ ] Lane 2. 生产入口运行身份。Save `p06/lane-2.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 3. 冷启完整显示器录屏。Save `p06/lane-3.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 4. 热启不重播。Save `p06/lane-4.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 5. 真实故障释放。Save `p06/lane-5.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 6. 设置持久化与预览隔离。Save `p06/lane-6.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 7. Pet 兼容记录。Save `p06/lane-7.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 8. DSH 独立完成或缺口。Save `p06/lane-8.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 9. 回退入口与资源清理。Save `p06/lane-9.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。
- [ ] Lane 10. 双语文档和支持范围核对。Save `p06/lane-10.png`. Pass when 该场景符合 NH-ACCEPTANCE 与 ACCEPTANCE 的对应约束，有真实观察与无敏感内容证据。

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. 对两版测量该阶段实际交付的检查或素材读取耗时与峰值 RSS，不声称运行时优化。
- [ ] Probe. 同设备相同输入交错运行五次，保存命令、原始样本及候选摘要。纯文档检查不得替代整体验收。
- [ ] Baseline. 先记录 trunk 的实际值与可比范围。新素材或缺失功能单独记新增工作。
- [ ] Rule. 可比工作 p50 耗时超过 trunk 1.10 倍或 RSS 超过 1.20 倍需调查并重新定界。不同工作不得强算比值；未冻结绝对预算则维持 inconclusive。

**Review gate.** None. P06 is not review-gated.

**Merge.**

- [ ] 独立 root verdict 对应精确 head SHA，所有检查与线程解决。由操作者 squash 合并，保留实际合并结果及恢复点后才考虑释放租约。

## Close the program

- [ ] 每个完成项都有对应证据，未完成项明确保留，不能为收尾而勾选。
- [ ] 分别报告 Codex、DSH、素材及 Pet 范围结果，提供实际 PR 与受跟踪文档链接。

## Appendix A. Prototype evidence

本次只有源码与既有设计阅读，没有新的原型、截图或测量。P01 先恢复原包，P02 原型审角色和构图，P03 证实冷启首帧及故障释放，P05 证实 DSH hook。没有原型 SHA，不虚构链接。原型不准操作未授权安装或正在工作的宿主。

## Appendix B. Alternatives rejected

不采用新通用 Coordinator、第二原生设置权威、宿主未启动即播放未知最新设置、用 DOM-ready 冒充首帧、复制 Dragon 角色、自动重装 Pet或缩短至 2.8 秒。理由见 DESIGN.md 与 NH-DESIGN.md。

## Appendix C. Risks

P01 的原包缺失阻止需求映射冻结。P03 面临宿主页换代和多显示器露底。P05 面临真实 hook 与 CSP 能力缺口。P02 的新素材需身份及授权审阅。P06 不能因某端 blocked 宣称双端完成。

实际模型、独立 reviewer 与控制工具以执行时能力为准。十条 lane 是必须覆盖的场景，不要求十个并发 owner 或十台云 VM。缺少工具时记录明确阻塞，不能把计划形式校验当成运行验证。

## Appendix D. Links and reading list

先读 [README](README.md)、[DESIGN](DESIGN.md)、[ASSETS](ASSETS.md)、[ACCEPTANCE](ACCEPTANCE.md)、[NH-CONTRACT](NH-CONTRACT.md)及仓库 AGENTS。P03 与 P05 在改变架构前读取 `packages/pstack-agent-harness/harness/pstack/codex/skills/how/SKILL.md` 和 architect。设计有争议时读取 interrogate。各阶段按 show-me-your-work 保存私有决策轨迹，仓库只保留脱敏设计决定。
