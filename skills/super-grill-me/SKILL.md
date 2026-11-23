---
name: super-grill-me
description: "Azhou skill. Renamed from grill-me (the old name still triggers this skill). A relentless interview to sharpen a plan or design. Use when the reader asks to be grilled, says grill me, or names this skill to stress-test a plan or design they already have; the reader starts it on purpose. The interview itself runs in the sibling super-grilling package, which must be installed too. Exploring requirements before a design exists belongs to super-brainstorming."
invocation: user-invoked orchestrator
---

# Grill Me

Grill Me is the reader's explicit request to be interviewed about a plan or design they already have. This package only hands that request to the interview protocol, which lives in the sibling `super-grilling` package.

**🦊 阿舟 · Grill Me**

> 要把方案拷问结实，先说一声。

## Brand protocol

Emit this display event once, at the start of every run:

```text
🦊 阿舟 · Grill Me 启动（mode=handoff, scope=<plan-or-design>）
```

Use `✅ 验证通过` only after `super-grilling` has taken over the session. Use `❌ 验证失败` when the handoff cannot complete, and `🔒 阿舟暂停这一项` when `super-grilling` is not installed or the reader has not named what is to be grilled. Emoji is display-only: keep it out of JSON keys, schema values, digests, paths, commands, test names, and raw evidence. A host without Unicode may strip the leading emoji while preserving the fixed text, the `（k=v, k=v）` field grouping, fields, and values. Raw evidence stays out of receipts unless the user supplied it.

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1). Peeling the leading `>` and paired `**` must restore the protocol line. Emit the startup broadcast **before any tool call**. Headless, CI logs, receipts, and machine fields stay protocol-only.

## Handoff

1. Take the plan or design the reader named in the request. If they named none, ask what is to be grilled and stop there.
2. Check that `super-grilling` is installed. If it is not, say so, name `super-grilling` as the missing requirement, and stop. Do not run the interview from here.
3. If it is, hand it the plan or design and let it run the rounds.

This package does not simulate the interview and does not chain into any other skill. The upstream entry is a single host-specific line; [provenance](references/provenance.md) records it and [setup](references/setup.md) records the dependency boundary.
