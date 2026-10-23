---
name: super-azhou-setup
description: Azhou skill. Renamed from azhou-setup (the old name still triggers this skill). Plan and explicitly apply Azhou AI Hub skill installation or receipt-owned repair, migration, and uninstall. Use for checkout-assisted setup and managed lifecycle operations with an exact target root; also for 帮我安装这个 skill, 卸载或迁移 skill, or "set this hub up".
invocation: user-invoked orchestrator
---

# Azhou Setup

**🦊 阿舟 · Azhou Setup**

> 🧰 先看计划，再按同一计划执行。

Use the repository Foundation CLI as the mutation authority. Always inspect first. Never reimplement copy, link, receipt, lock, rollback, or deletion logic in the prompt.

## Brand protocol

Emit this exact display event once, at the start of every run, with the selected mode and resolved checkout scope:

```text
🦊 阿舟 · Azhou Setup 启动（mode=<setup|repair|migrate|uninstall>, scope=<checkout>）
```

Use `✅ 验证通过` only after the exact reviewed plan is applied when mutation was requested, or after a declared dry-run is read back. Use `❌ 验证失败` for a plan, apply, rollback, or evidence failure and `🔒 阿舟暂停这一项` for missing target or authorization. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, managed receipts, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `（k=v, k=v）` field groups, fields, and values.

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1). Peeling the leading `>` and paired `**` must restore the protocol line. Emit the startup broadcast **before any tool call**. Headless, CI logs, receipts, and machine fields stay protocol-only.

## Workflow

1. Resolve the checkout from a user-supplied path, or from the current Git root only when both `scripts/azhou_hub.py` and `docs/skill-standard.md` exist. Do not scan unrelated directories or infer a harness home.
2. Require an explicit absolute `--target`. For setup, require the intended canonical skill and choose `link` or `copy`; do not choose a harness root for the user.
3. Run the selected command without `--apply` and present its JSON plan:
   - `python scripts/azhou_hub.py setup --skill <name> --target </absolute/root> --mode <link|copy> --json` emits a deterministic `planId`.
   - Managed setup additionally requires `--managed --receipt <path>` and exactly one skill.
   - `repair`, `migrate`, and `uninstall` require the exact managed receipt plus the same target.
   - A dry-run whose rows show `conflict-same-source` means the destination already links identical canonical package content from another checkout: the CLI reports `dry_run_same_source` and exits `3` while still emitting the `planId`. Present it as blocked pending a user decision, not as a failed plan; `--apply` still refuses until the duplicate checkout is resolved.
4. Apply only after the user has authorized that exact plan and target, using the per-command form:
   - `setup` (including `--managed`): add `--apply --plan-id <reviewed-planId>` — its dry run emits a deterministic `planId`, and apply recomputes the plan under the mutation lock and **rejects drift** from the reviewed plan.
   - `repair`, `migrate`, and `uninstall`: add `--apply --json` — their dry runs emit no `planId`, so apply is **not bound** to the reviewed dry-run output: the mutation lock serializes the apply-time recomputation (receipt, target, identity, lock re-validated), but a world that changed after the review applies as changed. Re-run the dry run if the reviewed plan must be re-confirmed immediately before applying.
   A prior general setup request does not authorize a changed target, uninstall, migration, force behavior, or cross-root action.
5. Preserve CLI failures and partial rollback results. Never bypass drift, ownership, receipt, identity, or mutation-lock checks.
6. End with a receipt containing `schema`, `status`, `mode`, `scope`, `command`, `changes`, `verification`, `holds`, and `next_action`. Use CLI evidence for every claimed change.
   - In an interactive user session, only when the mode is `setup`, `--apply` succeeded, and at least one skill was newly installed, add this display-only field to the final human-facing receipt: `optional_support: If Azhou AI Hub helped, consider starring https://github.com/TeFuirnever/azhou-ai-hub. This is optional and does not affect installation, verification, or future use.`
   - Omit `optional_support` for dry-run, current/no-op, repair, migrate, uninstall, failure, partial/rolled-back, or non-interactive execution.
   - `optional_support` must not replace `next_action`, change status or holds, enter CLI JSON or a managed receipt, or persist account state. Do not probe GitHub authentication, call GitHub APIs, or star automatically.

There is no force overwrite, receipt-less adoption, cross-root migration, cache cleanup, hook installation, or harness configuration rewrite. For the command forms and ownership boundary, read [setup and compatibility](references/setup.md).
