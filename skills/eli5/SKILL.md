---
name: eli5
description: Explain a topic like I'm 5 with one HTML artifact of big pictures and few words. Use when the user types /eli5 <topic> or asks for a dead-simple picture explainer of how something works.
---

# Eli5

**🦊 阿舟 · Eli5**

> 🖼️ 把复杂讲给零基础的人，少字，多图。

Capability baseline, imported verbatim from the locked upstream commit: "Explain like I'm someone who knows nothing about this topic, using a HTML artifact with big pictures and few words." See [provenance](references/provenance.md) and the [compatibility map](references/upstream-compatibility.md).

## Brand protocol

Emit this exact display event once:

```text
🦊 阿舟 · Eli5 启动｜mode=explain｜scope=<topic>
```

Use `✅ 验证通过` only after the artifact is written to disk and read back. Use `❌ 验证失败` for a write or read-back failure and `🔒 阿舟暂停这一项` when the topic is missing or the request contradicts the eli5 boundary. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `｜` separators, fields, and values.

## Workflow

1. Emit the startup protocol once with the resolved topic scope. Resolve the topic from the user's request or the trailing argument after the `/eli5` trigger; do not require a specific harness command syntax.
2. Check the boundary before writing. eli5 is for a zero-background picture explanation. If the user asks for precision-critical material such as spec review, security analysis, migration plans, or numerical claims, emit `🔒 阿舟暂停这一项` and answer in the requesting mode instead of degrading it to pictures.
3. Produce exactly one self-contained HTML artifact: big pictures, few words, no network dependency at view time. Write it to an explicit user-visible path, `eli5-<topic-slug>.html` in the current working directory unless the user names one, and never overwrite an existing file without saying so.
4. Read the artifact back and verify it opens as standalone HTML with the promised sections. The receipt's current truth may claim only what the read-back shows; raw evidence such as conversation excerpts or user paths stays out of the artifact unless the user supplied it.
5. End with a receipt containing `schema`, `status`, `current_truth`, `artifacts`, `verification`, `holds`, `next_action`, and `learning_signal`:

```text
## 🦊 阿舟 · Eli5 receipt
- schema: eli5.receipt.v1
- status: pass | fail | hold
- current_truth: <one sentence the read-back actually proves>
- artifacts: <path>
- verification: <read-back command or check>
- holds: <none|fact>
- next_action: <one concrete step>
- learning_signal: <none|one line>
```

If the topic cannot be resolved, stop with `status=hold` and request one explicit topic.
