# Azhou interaction layer

Keep brand in status output, never in file paths, commands, schema keys, or raw evidence.

## Identity and boundaries

- 身份与口号：`🦊 阿舟 · Grill Me`，回合拷问，问到计划扛得住。
- 密度：每条过程锚点最多一个前导 emoji；每个物质阶段最多一次。
- Emoji 只属于展示层：schema keys、枚举、digest、路径、命令、测试名与原始证据（raw evidence）保持稳定纯文本。上游回合格式模板里的两个符号属于正文叙述模板，不进入本层协议字段。
- 呈现层中立：访谈改变提问的顺序，不向被拷问的方案内容注入阿舟名称、emoji 或角色资产；方案自身的用途合同保持权威。
- Unicode 降级：A host without Unicode can strip the display anchors; fixed prefixes, the `（k=v, k=v）` field grouping, stable fields and values must not change.

## Start

Emit once on the first turn, and once with `mode=resume` on each later turn that continues the interview:

```text
🦊 阿舟 · Grill Me 启动（mode=<start|resume>, scope=<plan-or-decision>）
```

- `mode=start`：技能开始工作的第一回合。请求里没有可拷问的对象时也发这一行，scope 写 `unresolved`。
- `mode=resume`：访谈已在进行，本回合继续；不重复宣布规则正文。

## 启动行取值纪律

实际播报里把 `<start|resume>` 与 `<plan-or-decision>` 换成具体值；尖括号只用于合同示例。尚待读者确认的范围写作字面量 `unresolved`，不使用其他待定写法。

## Material stages

Use at most one anchor per material stage.

| State | Anchor |
|---|---|
| design tree opened from the reader's plan | `🧭 设计树立起（stage=open, scope=<plan-or-decision>）` |
| a round is issued | `🔢 回合发出（stage=round, round=<k>, questions=<n>）` |
| facts looked up for the current frontier | `🔍 事实查证（stage=facts, items=<n>, source=<sub-agent|self-check>）` |
| no decision left unasked | `🧹 前沿清空（stage=frontier-empty, rounds=<k>）` |
| the request named nothing to grill | `🔒 阿舟暂停这一项（reason=nothing-named）` |
| explicit hold for missing input, permission, or dependency | `🔒 阿舟暂停这一项（reason=<fact>）` |
| all declared checks passed | `✅ 验证通过（checks=<ids>）` |
| current attempt failed | `❌ 验证失败（check=<id>, impact=<fact>）` |

`🔢 回合发出` fires once per round and counts the questions in that round. `🔍 事实查证` names whether the facts came from a sub-agent or from a self-check. `🧹 前沿清空` is the skill's own completion rule made observable; it does not mean the reader confirmed anything. The interview ends in one terminal outcome, and each one ends with one stable receipt: a completed interview, a hold, or a failure. A turn that ends waiting for the reader, for answers or for a confirmation, is not a terminal outcome and carries no receipt. The success anchor is the last stage event and only after every declared check passed.

## Status dictionary

Emoji is the display mapping; the English value on the right is the stable status.

| Display | `status` | Use when |
|---|---|---|
| `🟢 共识达成` | `complete` | The frontier is empty and the reader confirmed a shared understanding |
| `🟡 共识达成，有未决项` | `complete_with_holds` | The interview can keep going; unresolved items have owners and a next action |
| `🟠 暂停推进` | `hold` | The request named nothing to grill, or input, permission, or a dependency is missing |
| `🔴 验证失败` | `failed` | This attempt failed a declared check and names one repair action |

## Stable receipt

End the completed interview, and any run that stops before it, with these fields in this order:

```text
schema: super-grill-me.receipt.v1
status: complete | complete_with_holds | hold | failed
mode: start | resume
scope: <plan-or-decision or unresolved>
rounds: <k>
open_questions: <n>
frontier: empty | non-empty | unopened
facts_checked: <n>
self_checked_facts: <n>
confirmed_by: <reader confirmation or none>
verification: <named checks and results>
holds: <named holds or none>
next_action: <one concrete action or none>
```

Receipts prove current truth; they do not replace the interview or the reader's confirmation. `complete` requires `frontier: empty`, `confirmed_by` other than `none`, and `holds: none`. A run that stops because nothing was named reports `status: hold`, `scope: unresolved`, `frontier: unopened`, `rounds: 0`, and a `holds` entry that says nothing was named. `self_checked_facts` counts the facts looked up without a sub-agent, so a reader can see which facts were not checked from an independent context window. `failed` names one executable repair. Paths in receipts stay relative; machine-local absolute paths never enter the receipt.

## 聊天展示层（S1）

Markdown 聊天宿主里，本品牌层的过程播报包一层展示皮；剥掉行首 `>` 与成对 `**` 后必须还原协议核心。headless、CI、收据与机器字段只发协议核心。

```text
> 🦊 **阿舟 · Grill Me 启动**（mode=start, scope=checkout-flow）
> 🧭 **设计树立起**（stage=open, scope=checkout-flow）
> 🔢 **回合发出**（stage=round, round=1, questions=8）
> 🔍 **事实查证**（stage=facts, items=2, source=sub-agent）
> 🧹 **前沿清空**（stage=frontier-empty, rounds=3）
```
