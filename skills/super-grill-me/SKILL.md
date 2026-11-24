---
name: super-grill-me
description: "Azhou skill. Renamed from grill-me and grilling (the old names still trigger this skill). A relentless interview to sharpen a plan or design. Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, uses any 'grill' trigger phrases, or asks to be grilled. Facts are looked up rather than asked, decisions stay with the user, and nothing is acted on until the user confirms a shared understanding. Exploring requirements before a design exists belongs to super-brainstorming."
invocation: both
---

# Grill Me

Grill Me is a relentless interview about a plan, decision, or idea. It works the plan as a design tree and asks it in rounds until nothing is left silently assumed. The reader can start it on purpose, or the model can reach for it when a plan needs stress-testing. The instruction body below is the upstream grilling skill frozen at the pinned commit recorded in [provenance](references/provenance.md). The Azhou layer adds the brand protocol below and one sentence on what to do without a sub-agent.

**🦊 阿舟 · Grill Me**

> 回合拷问，问到计划扛得住。

## Brand protocol

Emit this display event once on the first turn, and once with `mode=resume` on each later turn that continues the interview:

```text
🦊 阿舟 · Grill Me 启动（mode=<start|resume>, scope=<plan-or-decision>）
```

Use `✅ 验证通过` only after the named checks actually ran. Use `❌ 验证失败` when this attempt fails and name one repair action, and `🔒 阿舟暂停这一项` when the request names nothing to grill or when input, permission, or a dependency is missing. Emoji is display-only: keep it out of JSON keys, schema values, digests, paths, commands, test names, and raw evidence. The two symbols in the round template below belong to that prose template only. A host without Unicode may strip the leading emoji while preserving the fixed text, the `（k=v, k=v）` field grouping, fields, and values. Raw evidence stays out of receipts unless the user supplied it. Stage events, the status dictionary, and the stable receipt are defined in the [Azhou interaction layer](references/brand-layer.md).

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1). Peeling the leading `>` and paired `**` must restore the protocol line. Headless, CI logs, receipts, and machine fields stay protocol-only.

If the request names nothing to grill, the startup line carries `scope=unresolved`. Ask what is to be grilled and stop there. That exit is a hold. Emit `🔒 阿舟暂停这一项（reason=nothing-named）` and end with the stable receipt.


Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Word each question so "yes" accepts your recommended answer.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent with a fresh context window to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait. On a harness without sub-agents, look the fact up yourself and say that it was not checked from an independent context window.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
