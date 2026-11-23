# Azhou interaction layer

Keep brand in status output, never in file paths, commands, schema keys, or raw evidence.

## Identity and boundaries

- 身份与口号：`🦊 阿舟 · Brainstorming` — 先问为什么，再画怎么做，门没过不写码。
- 密度：每条过程锚点最多一个前导 emoji；每个物质阶段最多一次。
- Emoji 只属于展示层：schema keys、枚举、digest、路径、命令、测试名与原始证据（raw evidence）保持稳定纯文本。上游回合格式里的 emoji 属于正文叙述模板，不进入本层协议字段。
- 呈现层中立：探询与审批门改变对话的顺序，不向设计内容注入阿舟名称、emoji 或角色资产；设计文档自身的用途合同保持权威。
- Unicode 降级：A host without Unicode can strip the display anchors; fixed prefixes, the `（k=v, k=v）` field grouping, stable fields and values must not change.

## Start

Emit once when the design conversation opens, before the first question:

```text
🦊 阿舟 · Brainstorming 启动（mode=<start|resume>, scope=<topic>）
```

- `mode=start`：读者开启一次新的设计探询（显式调用或按触发条件进入）。
- `mode=resume`：探询已在进行，本回合继续；不重复宣布规则正文。

The `（k=v, k=v）` field grouping and ` — ` narrative dash are part of the protocol and must be followed by a verifiable fact or an explicit action; fixed prefixes are never replaced with near synonyms.

## Material stages

Use at most one anchor per material stage.

| State | Anchor |
|---|---|
| design conversation opened | `🧭 探询开始（stage=questions, focus=<area>）` |
| approaches laid out for the reader | `📐 方案枚举（stage=approaches, options=<n>）` |
| design doc drafted | `📝 设计文档（stage=design-doc, size=<short\|full>）` |
| approval gate resolved | `🚪 审批门（stage=approval-gate, verdict=<approved\|changes-requested>）` |
| planning handoff issued | `🤝 交接规划（stage=handoff, target=<chosen workflow>）` |
| explicit hold | `🔒 阿舟暂停这一项` |
| all declared checks passed | `✅ 验证通过（checks=<ids>）` |
| current attempt failed | `❌ 验证失败（check=<id>, impact=<fact>）` |

`🚪 审批门` is the skill's own HARD-GATE made observable: nothing gets built until `verdict=approved`. `🤝 交接规划` fires at most once per engagement, after the gate, and names the workflow the reader chose — it never names a sibling skill on the reader's behalf. The success anchor is the last stage event and only after every declared check passed.

## Status dictionary

Emoji is the display mapping; the English value on the right is the stable status.

| Display | `status` | Use when |
|---|---|---|
| `🟢 设计已定` | `complete` | The gate approved the design doc and the handoff is issued or not needed |
| `🟡 设计已定，有未决项` | `complete_with_holds` | The design holds, but open items have owners and a next action |
| `🟠 暂停推进` | `hold` | Input, permission, or a dependency is missing |
| `🔴 验证失败` | `failed` | This attempt failed a declared check and names one repair action |

## Stable receipt

End the completed workflow with these fields in this order:

```text
schema: super-brainstorming.receipt.v1
status: complete | complete_with_holds | hold | failed
mode: start | resume
scope: <topic>
stage: <last material stage>
design_doc: <relative path or none>
approaches_considered: <n>
approved_by: <reader confirmation or none>
verification: <named checks and results>
holds: <named holds or none>
next_action: <one concrete action or none>
```

Receipts prove current truth; they do not replace the design conversation's outputs or the reader's approval. `approved_by: none` with `stage=approval-gate` means the gate has not resolved; nothing may be built in that state. Paths in receipts stay relative; machine-local absolute paths never enter the receipt. `complete` requires `holds: none`. `failed` names one executable repair.

## 聊天展示层（S1）

Markdown 聊天宿主里，本品牌层的过程播报包一层展示皮；剥掉行首 `>` 与成对 `**` 后必须还原协议核心。headless、CI、收据与机器字段只发协议核心。

```text
> 🦊 **阿舟 · Brainstorming 启动**（mode=start, scope=checkout-redesign）
> 🧭 **探询开始**（stage=questions, focus=why-now）
> 📐 **方案枚举**（stage=approaches, options=3）
> 📝 **设计文档**（stage=design-doc, size=full）
> 🚪 **审批门**（stage=approval-gate, verdict=approved）
> 🤝 **交接规划**（stage=handoff, target=reader-chosen）
```
