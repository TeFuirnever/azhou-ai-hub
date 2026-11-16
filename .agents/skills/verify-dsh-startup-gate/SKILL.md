---
name: verify-dsh-startup-gate
description: "形式化验证 DSH 启动遮罩状态机（packages/agent-skin/extension/hosts/dsh-startup-gate.js）。凡改动该文件或其注入路径，合并前运行本检验。"
metadata:
  internal: true
---

# verify-dsh-startup-gate

## 被验证的承诺

DSH 启动遮罩是注入 DSH 宿主页面的不透明全视口盖板，在渲染器就绪前遮住窗口。它的承诺，一句话：**盖板要么在渲染器 claim 并 ready 后 250ms 内揭示，要么被硬看门狗（未 claim 8s、已 claim 12s）、pagehide 或 release 关掉；离开激活相位的那一刻盖板消失，且永不复现、不留任何存活的 timer/frame/listener。** 承诺被打破时，用户面对的是卡死的全屏不透明窗口（盖板悬挂）、半成品 UI 闪现（提前消失）、或迟到触发的僵尸定时器。

## 验证什么

`packages/agent-skin/tools/verify-dsh-startup-gate.mjs` 在与 `tools/dsh-startup-gate.unit.test.mjs` 同源的 stub 浏览器环境里运行**未经修改的真实 gate 源码**，在单调虚拟时钟下穷举所有事件交错：渲染器 API（claim/ready/release 各至多两次，含合法相位外的 no-op 重试）、expiry listener 注册与取消（各两次）、pagehide、重复 IIFE 注入、动画帧投递、看门狗定时器触发。环境三变体：normal（rAF 正常投递）、dead-rAF（rAF 注册但帧永不投递）、no-rAF（无 rAF，走 setTimeout 回退）。基线状态空间 148,816（normal 64,400 / dead-rAF 49,424 / no-rAF 34,992），node v24 全程约 90 秒，逐确定性可复现。

不变量（每条对应上句承诺的一个分句）：

- P1 盖板挂载 ⟺ 相位 ∈ {waiting, claimed, revealing}；盖板元素至多一个。
- P2 released/expired 是吸收态；过期回调不得把已终结的 gate 翻成另一终态。
- P3 盖板挂载期间，看门狗定时器恰在追踪的硬截止点上处于武装状态，且截止点未被越过。
- P4 claim/ready/release 只在各自的合法前置相位返回 true，**且返回 true 时相位必须已迁移到各自的后继相位**（claim→claimed、ready→revealing、release→expired）。
- P5 expiry listener 恰触发一次 ⟺ gate 进入 expired 的那一刻它已注册、未取消、且注册于激活相位（expired 期注册的立即欠一次）。期望次数独立于 `fired` 推导（模型侧 `owed` 标记），伪造/过早通知本身即违规。
- P6 同时挂起至多一个 timer 与一个 frame（no-rAF 回退下 reveal fallback 与看门狗共存的两个 timer 合法）；终态后 timer/frame/盖板/pagehide listener 计数全部归零。

## 如何运行

```bash
node packages/agent-skin/tools/verify-dsh-startup-gate.mjs
```

- 退出 0：全部不变量成立。
- 退出 1：反例。检验器按 `t=<ms> <事件>` 逐行打印失败调度 —— 把它读成"渲染器/宿主按这个顺序行动就会打破承诺"的最短序列。
- 退出 2：用法或 harness 错误。
- 选项：`--variant normal|dead-rAF|no-rAF`、`--max-states <n>`、`--gate <path>`（默认真实文件；验一份改动副本时不触碰被跟踪字节）。

## 读反例：真缺陷还是模型误差

反例默认按真缺陷处理：修 gate，不改检验器、不为通过而弱化不变量。唯一已知的过近似是**动画帧可在挂起期间的任意调度步投递**（真实可见页面约一帧内投递）；若唯一失败调度依赖"帧晚于该窗口投递"，先上真浏览器复核再动产品代码。退出 2 且报 "gate did not publish" 意味着 stub 环境不再满足 gate 安装自检 —— 先把 stub 对齐 `tools/dsh-startup-gate.unit.test.mjs` 的环境构造，再重跑。

## 有意变更承诺时

新增相位、改截止时长、新增 API 都是对承诺的有意变更：在同一提交里同步更新检验器的不变量集与截止常量，重跑全绿，并按下方探针规程确认"能失败"仍然成立（旧破损变体必须仍被抓，必要时为新承诺补一个新探针）。

## Able-to-fail 探针

检验器本身必须被证明能失败。七个已验收探针（m1–m4 于 2026-11-16 首轮验收，各被 P1/P6/P4/P3 抓住；m5–m7 来自 PR #480 的 Codex 评审——它自行变异验证了检验器三个盲区，修复后同日验收，分别被 P5/P4/P6 的新 oracle 臂抓住）；同步推进 commit 时至少复跑一个：

```python
import pathlib
src = pathlib.Path('packages/agent-skin/extension/hosts/dsh-startup-gate.js').read_text()
MUTATIONS = {
 'm1-early-hide': (
   "      phase = 'claimed';\n      arm(12_000);\n      return true;",
   "      phase = 'claimed';\n      arm(12_000);\n      remove();\n      return true;"),
 'm2-timer-leak': (
   "  const arm = milliseconds => {\n    if (timer !== null) host.clearTimeout(timer);\n    timer = host.setTimeout(expire, milliseconds);",
   "  const arm = milliseconds => {\n    timer = host.setTimeout(expire, milliseconds);"),
 'm3-absorbing-guard': (
   "  const expire = () => {\n    if (phase === 'released' || phase === 'expired') return false;\n    phase = 'expired';",
   "  const expire = () => {\n    phase = 'expired';"),
 'm4-reveal-stall': (
   "      phase = 'revealing';\n      arm(250);",
   "      phase = 'revealing';"),
 'm5-premature-fire': (
   "    expirationListeners.add(listener);",
   "    listener();"),
 'm6-claim-no-transition': (
   "      phase = 'claimed';\n      arm(12_000);\n      return true;",
   "      arm(12_000);\n      return true;"),
 'm7-pagehide-listener-leak': (
   "    host.removeEventListener?.('pagehide', expire);\n",
   ""),
}
out = pathlib.Path('/tmp/azhou-gate-mutations'); out.mkdir(exist_ok=True)
for name, (old, new) in MUTATIONS.items():
    assert src.count(old) == 1, (name, src.count(old))
    (out / f'{name}.js').write_text(src.replace(old, new))
```

对每个变体运行 `node packages/agent-skin/tools/verify-dsh-startup-gate.mjs --gate /tmp/azhou-gate-mutations/<name>.js --variant normal`，期望全部退出 1。探针只写 /tmp 副本，绝不改动被跟踪文件。

## 与代码保持同步

- 覆盖对象：`packages/agent-skin/extension/hosts/dsh-startup-gate.js` 整文件（安装自检、gate 对象、expire/arm/remove、listener 语义）。
- **sync commit：`541619a8`**（2026-11-16 确认：穷举三变体全绿 + 7/7 探针被抓住；该 commit 下 covered file 与工作区字节一致）。
- 覆盖对象在此 commit 之后发生变更而未重跑检验时，结果视为未验证；**只有**在新代码上重新跑出全绿、并至少通过一个 able-to-fail 探针之后，才允许把 sync commit 前移。
- 更大范围的重新对齐（新相位、调度契约变化、环境假设调整）走 pstack `/maintain-formal-verification-skill`。

## 范围诚实

已验证：安装成功路径下，单文档、上述 stub DOM/定时器假设内，gate 相位机的全部生命周期承诺，覆盖所有被枚举的事件交错。未验证：安装失败的 fail-open 路径（隐藏文档、尺寸不足、顶层遮挡 —— 由 `tools/dsh-startup-gate.unit.test.mjs` 与 CDP 浏览器测试覆盖）、真实浏览器合成与 CSS 行为、多文档共存、DSH 宿主侧的注入时机、以及本文件之外的任何东西。通过结论只覆盖枚举边界，不等于全系统证明。
