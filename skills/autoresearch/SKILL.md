---
name: autoresearch
description: Wrap Karpathy's autoresearch environment so an agent can run, resume, and report automatic nanochat training experiments inside a user-owned pinned checkout. Requires an NVIDIA GPU and uv; vendors no upstream bytes. Use when the user asks to run or check autoresearch experiments.
---

# Autoresearch

**🦊 阿舟 · Autoresearch**

> 🧪 实验通宵跑，边界先说清。

This package is an Azhou-authored wrapper. The experiment protocol lives in the upstream `program.md` and is read at runtime from the user's own checkout; this package vendors zero upstream bytes because the upstream repository publishes no license file. See [setup](references/setup.md) and [provenance](references/provenance.md).

## Brand protocol

Emit this exact display event once:

```text
🦊 阿舟 · Autoresearch 启动｜mode=<prepare|run|resume|report>｜scope=<checkout>
```

Use `✅ 验证通过` only after every declared check has run and its output was read back. Use `❌ 验证失败` for a failed environment, checkout, or run check and `🔒 阿舟暂停这一项` when an unattended GPU run or a data download waits for explicit user confirmation. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `｜` separators, fields, and values.

## Workflow

1. Emit the startup protocol once with the resolved checkout scope.
2. Resolve the checkout from a user-supplied path only. Verify that `git rev-parse HEAD` inside it equals the pinned commit recorded in [setup](references/setup.md), and refuse to continue on any mismatch. Never scan unrelated directories and never clone into any Git repository.
3. `mode=prepare` verifies the environment per setup: uv present, CUDA GPU visible, `uv sync` clean, data prepared, and one baseline training run possible. Every missing check fails closed; no partial state is reported as ready.
4. `mode=run` and `mode=resume` read `program.md` from the checkout and follow it inside that checkout. Before any unattended sequence, hold with `🔒 阿舟暂停这一项` until the user confirms the GPU hours and disk cost. Results stay in the checkout; this skill never pushes, publishes, or copies results into any repository.
5. `mode=report` aggregates experiment results that already exist in the checkout. Conversation excerpts, machine paths, and other raw evidence stay out of any committed surface.
6. End with a receipt containing `schema`, `status`, `current_truth`, `artifacts`, `verification`, `holds`, `next_action`, and `learning_signal`:

```text
## 🦊 阿舟 · Autoresearch receipt
- schema: autoresearch.receipt.v1
- status: pass | fail | hold
- current_truth: <one sentence the checks actually prove>
- artifacts: <paths inside the user checkout>
- verification: <comma-separated check ids>
- holds: <none|fact>
- next_action: <one concrete step>
- learning_signal: <none|one line>
```

If no pinned checkout is available, stop with `status=hold` and request one explicit checkout path.
