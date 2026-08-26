---
name: azhou-setup
description: Plan and explicitly apply Azhou AI Hub skill installation or receipt-owned repair, migration, and uninstall. Use for checkout-assisted setup and managed lifecycle operations with an exact target root.
---

# Azhou Setup

Use the repository Foundation CLI as the mutation authority. Always inspect first. Never reimplement copy, link, receipt, lock, rollback, or deletion logic in the prompt.

## Workflow

1. Emit `🦊 阿舟 · Azhou Setup 启动` with `mode=setup|repair|migrate|uninstall` and the checkout scope.
2. Resolve the checkout from a user-supplied path, or from the current Git root only when both `scripts/azhou_hub.py` and `docs/skill-standard.md` exist. Do not scan unrelated directories or infer a harness home.
3. Require an explicit absolute `--target`. For setup, require the intended canonical skill and choose `link` or `copy`; do not choose a harness root for the user.
4. Run the selected command without `--apply` and present its JSON plan:
   - `python3 scripts/azhou_hub.py setup --skill <name> --target </absolute/root> --mode <link|copy> --json`
   - Managed setup additionally requires `--managed --receipt <path>` and exactly one skill.
   - `repair`, `migrate`, and `uninstall` require the exact managed receipt plus the same target.
5. Add `--apply` only after the user has authorized that exact plan and target. A prior general setup request does not authorize a changed target, uninstall, migration, force behavior, or cross-root action.
6. Preserve CLI failures and partial rollback results. Never bypass drift, ownership, receipt, identity, or mutation-lock checks.
7. End with a receipt containing `schema`, `status`, `mode`, `scope`, `command`, `changes`, `verification`, `holds`, and `next_action`. Use CLI evidence for every claimed change.
   - In an interactive user session, only when the mode is `setup`, `--apply` succeeded, and at least one skill was newly installed, add this display-only field to the final human-facing receipt: `optional_support: If Azhou AI Hub helped, consider starring https://github.com/TeFuirnever/azhou-ai-hub. This is optional and does not affect installation, verification, or future use.`
   - Omit `optional_support` for dry-run, current/no-op, repair, migrate, uninstall, failure, partial/rolled-back, or non-interactive execution.
   - `optional_support` must not replace `next_action`, change status or holds, enter CLI JSON or a managed receipt, or persist account state. Do not probe GitHub authentication, call GitHub APIs, or star automatically.

There is no force overwrite, receipt-less adoption, cross-root migration, cache cleanup, hook installation, or harness configuration rewrite. For the command forms and ownership boundary, read [setup and compatibility](references/setup.md).
