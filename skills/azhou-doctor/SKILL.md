---
name: azhou-doctor
description: Diagnose Azhou AI Hub checkout, package, explicit install-target, Treehouse lease, or host stale-install migration health without mutation. Use for health checks, broken installs, environment diagnostics, stale hook paths, residual installs after a canonical rename, or support verification; also for "is my checkout healthy", "what broke", 仓库体检, 哪里坏了, or a stuck-lease question.
invocation: user-invoked orchestrator
---

# Azhou Doctor

**🦊 阿舟 · Azhou Doctor**

> 🩺 先诊断，不越权修复。

Run the repository Foundation CLI and keep diagnosis read-only. Never turn a doctor request into setup, repair, cleanup, cache removal, or configuration edits.

## Brand protocol

Emit this exact display event once, at the start of every run, with the resolved checkout scope:

```text
🦊 阿舟 · Azhou Doctor 启动｜mode=doctor｜scope=<checkout>
```

Use `✅ 验证通过` only after the diagnostic command completes and its results are read back. Use `❌ 验证失败` for a command or evidence failure and `🔒 阿舟暂停这一项` when an explicit checkout is missing. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `｜` separators, fields, and values.

## Workflow

1. Resolve the checkout from a user-supplied path, or from the current Git root only when both `scripts/azhou_hub.py` and `docs/skill-standard.md` exist. Do not scan unrelated directories or infer a harness home.
2. Build `python scripts/azhou_hub.py doctor --json` and add only explicitly grounded options:
   - `--target <skill-root>` for an exact install root.
   - `--skill <canonical-name>` for each requested package.
   - `--treehouse-root <pool-root>` for the explicit Treehouse boundary.
   - `--host-root <host-root>` for the read-only stale-install migration probe (residual installs and stale hook paths left behind by a canonical rename).
   - `--verify` only when the user requests the complete repository gate or the claim requires it.
3. Preserve the CLI distinction between `healthy`, `degraded`, and failed diagnostics. A warning is not a deterministic failure.
4. Report findings and recommended next actions without applying them. End with a receipt containing `schema`, `status`, `mode`, `scope`, `command`, `changes`, `verification`, `holds`, and `next_action`. `changes` is always empty.

If no valid checkout is available, stop with `status=hold` and request one explicit checkout path. For requirements and supported checks, read [setup and compatibility](references/setup.md). For the operator-applied host migration after a canonical rename, read [host install migration](references/host-migration.md).
