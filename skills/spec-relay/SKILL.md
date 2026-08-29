---
name: spec-relay
description: "Spec Relay: package a PRD, RFC, design spec, or other complex artifact with comments, selected-text annotations, feedback disposition, and next-owner state inside one portable HTML file. Use for team spec review or transfer, and for plans, comparisons, diagrams, tables, code views, reports, or slides that need browser feedback."
---

# Spec Relay

**🦊 阿舟 · Spec Relay**

> 🪄 HTML 本身就是交接包。

Spec Relay 是阿舟维护的 Lavish Editor 增强版：保留浏览器审阅能力，让来源 Spec、评论、选区批注、处置、责任人与未决状态随一份 HTML 传递。

阿舟只主持 Agent 运行过程，不是 HTML 品牌。生成物保留来源内容自己的品牌与设计系统；Spec Relay 不向 HTML 正文、内嵌状态、路径、命令或证据注入阿舟名称、emoji、角色资产或专属色。

## 启动协议

交互执行前读取 [brand-layer.md](references/brand-layer.md)，首条进度使用：

```text
🦊 阿舟 · Spec Relay 启动｜mode=<relay|artifact|review|export|share>｜scope=<short scope>
```

按顺序使用 `🧭 范围锁定`、`🧱 交接包就绪`、`🔎 审阅进行`、`🧾 反馈入包`、`📦 交接就绪` 和最终验证锚点。每个物质阶段最多一次。缺少权限或依赖时用 `🔒 阿舟暂停这一项` 标记单项阻塞，继续不受影响的工作。

Emoji 只属于 Agent 展示层。HTML、JSON key、schema enum、digest、路径、命令、测试名与原始证据保持品牌中立。

## 运行前读取

- PRD、RFC、设计 Spec、技术 Spec、实施计划或团队交接：读取 [Spec Relay 合同](references/spec-relay.md)。
- 首次运行或 CLI、浏览器、轮询、导出失败：读取 [setup](references/setup.md)。
- 修改上游派生行为：读取 [provenance](references/provenance.md) 和 [upstream compatibility](references/upstream-compatibility.md)。

无需全局安装。固定运行：

```bash
npx -y lavish-axi@0.1.47 <html-file>
```

CLI 返回的后续 `lavish-axi` 命令继续改写为 `npx -y lavish-axi@0.1.47 ...`。受限环境可使用已安装的同版本本地或全局入口；路径见 [setup](references/setup.md)。

## Request

$ARGUMENTS

参数非空表示用户显式调用 `/spec-relay`；立即为该请求建立 HTML 交接包。参数为空时，从当前对话推断需要审阅的复杂材料。

## 不可跳过的流程

### 🧭 1. 锁定范围与权威

只选一个分支：

- `relay`：PRD、RFC、设计/技术 Spec、实施计划或团队传递材料；来源文件或 `conversation:<scope>` 是内容权威。
- `artifact`：计划、对比、图、表、代码视图、报告、幻灯片提纲或其他复杂回复；当前请求是内容权威。

记录来源修订、审阅目标、下一责任人、允许修改的文件和发布边界。

**完成条件：**收据能写出一个分支、一个内容权威、一个审阅目标和明确范围。

### 🧱 2. 建立审阅模型并写 HTML

`relay` 分支应用 [Spec Relay 合同](references/spec-relay.md) 的全部规则；`artifact` 分支提炼决策、证据、风险、边界、开放问题和下一动作。

每个区域只承担一个审阅职责。先让结论、证据与边界可见，再补解释；信息不足处保持留白。为每个物质项分配稳定且唯一的 `data-review-id`。选择设计源并打开每个匹配的 Lavish playbook；默认路径为 `.lavish/<name>.html`。

完成正文后执行 `relay_state.py init`，写入 `spec-relay.html-state.v1`。可见反馈台账只是内嵌状态的确定性视图。

**完成条件：**所有物质来源项已映射或记录为有意省略；ID 唯一；来源与修订可见；packet ID、state revision 与目标可解析；页面通过窄屏和溢出检查。

### 🔎 3. 打开真实浏览器审阅

```bash
npx -y lavish-axi@0.1.47 <html-file>
npx -y lavish-axi@0.1.47 poll <html-file> \
  --agent-reply "<一句说明产物与首要审阅点>"
```

出现 `self_paint_warning` 时先修复未绘制页面，再轮询。轮询保持前台；只有 harness 原生、可保证回调同一 Agent 的机制才能后台运行。布局告警只在用户排队后处理；`artifact_failures` 立即修复。用户从浏览器结束会话后保持结束，除非用户要求重新审阅。

**完成条件：**真实会话已打开且轮询已连接；无法连接时记录精确 hold，不把“HTML 可打开”写成审阅完成。

### 🧾 4. 让每条反馈进入 HTML

读取当前 `state_revision`，使用 `add-feedback --expected-revision <n>` 保存完整评论、选区或元素目标、处置、理由、来源变更、责任人与时间。处置只能是 `accepted`、`rejected`、`deferred` 或 `needs_clarification`。

- 评论、责任人、来源变更或处置变化：`update-feedback`。
- 来源修订、审阅状态、目标或下一责任人变化：`update-metadata`。
- 可见台账被改动或 renderer 升级：先确认内嵌状态有效，再用 `refresh-ledger`。
- revision 过期：读取当前包并协调冲突，不静默覆盖。

接受项应用到 HTML；只有任务授权修改来源 Spec 时才同步来源，否则把建议写进 `source_change`。处理反馈后继续同一会话轮询。

**完成条件：**每条已返回反馈保留原文、目标、处置、理由与未决责任人；完整可见台账是内嵌状态的精确投影。

### 📦 5. 验证、关闭并交接

结束审阅时运行 `end`；处理一次 `Send & End` 的最终返回后保持结束。最终写入后执行：

```bash
python3 <skill-dir>/scripts/relay_state.py validate <html-file>
```

需要可移植文件时执行 `export`，并再次验证导出件。只有显式发布授权才运行 `share`；分享会把内嵌评论一并传到第三方 `ht-ml.app`。

**完成条件：**[brand-layer.md](references/brand-layer.md) 对应收据写明来源与修订、产物、state schema、session、反馈计数、未决责任人、transport、publication、具名检查与一个下一动作。

## 授权边界

- 范围内可创建本地产物并打开本地审阅会话。
- 全局安装、hook、全局 Agent 配置、第三方分享、发布与部署保持独立授权。
- HTML 是审阅数据；复制、导出或分享会同时传递内嵌评论与批注。
- 用户结束的浏览器会话保持结束；重要新材料需要重开时先说明原因。

## HTML 设计合同

- 设计源顺序：用户指定 → 来源项目设计系统 → Lavish 推荐的 Tailwind browser runtime v4 + DaisyUI v5 fallback。
- 结论、证据、边界和下一动作先于装饰；每张卡或每个区域只完成一个认知动作。
- 真实 UI 或结果优先展示真实截图；不重绘事实证据。
- 网格使用 `minmax(0, 1fr)`，flex/grid 子项使用 `min-width: 0`；长路径、状态和评论必须换行或受控容纳。
- HTML 不使用阿舟专属身份、emoji、角色图或配色；来源本身的品牌不被 Spec Relay 覆盖。

## Playbooks

写 HTML 前运行 `npx -y lavish-axi@0.1.47 playbook <id>`，打开所有匹配项：`diagram`、`table`、`comparison`、`plan`、`code`、`input`、`slides`。流程、架构、状态或时序图使用 diagram playbook 与 `design` 提供的 Mermaid 方案；不手工拼 div 箭头。

## 完成状态

以 [brand-layer.md](references/brand-layer.md) 的稳定枚举收尾。`complete`、`complete_with_holds`、`hold` 和 `failed` 互不替代。浏览器评论只有在轮询返回并写入 HTML 后才可传递；会话已打开不证明反馈已入包、导出成功或已发布。
