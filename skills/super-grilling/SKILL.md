---
name: super-grilling
description: "Azhou skill. Renamed from grilling (the old name still triggers this skill). Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases. Facts are looked up rather than asked, decisions stay with the user, and nothing is acted on until the user confirms a shared understanding. Exploring requirements before a design exists belongs to super-brainstorming."
invocation: both
---

# Grilling

Grilling is the interview protocol: it works a plan, decision, or idea as a design tree and asks it in rounds until nothing is left silently assumed. The instruction body below is the upstream grilling skill frozen at the pinned commit recorded in [provenance](references/provenance.md). The Azhou layer adds the brand protocol below and one sentence on what to do without a sub-agent.

**🦊 阿舟 · Grilling**

> 回合拷问，问到计划扛得住。

## Brand protocol

Emit this display event once, when the interview opens:

```text
🦊 阿舟 · Grilling 启动（mode=<start|resume>, scope=<plan-or-decision>）
```

Use `✅ 验证通过` only after the named checks actually ran. Use `❌ 验证失败` when this attempt fails and name one repair action, and `🔒 阿舟暂停这一项` when input, permission, or a dependency is missing. Emoji is display-only: keep it out of JSON keys, schema values, digests, paths, commands, test names, and raw evidence. The two symbols in the round template below belong to that prose template only. A host without Unicode may strip the leading emoji while preserving the fixed text, the `（k=v, k=v）` field grouping, fields, and values. Raw evidence stays out of receipts unless the user supplied it. Stage events, the status dictionary, and the stable receipt are defined in the [Azhou interaction layer](references/brand-layer.md).

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1). Peeling the leading `>` and paired `**` must restore the protocol line. Headless, CI logs, receipts, and machine fields stay protocol-only.


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
