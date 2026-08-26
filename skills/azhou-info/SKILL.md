---
name: azhou-info
description: Report provable Azhou AI Hub checkout information or revision facts. Use for project info, installable repository inventory, support facts, version, commit, branch, or dirty-state questions.
---

# Azhou Info

Use the repository Foundation CLI as the only authority. Do not reconstruct version or package facts from memory.

## Workflow

1. Emit `🦊 阿舟 · Azhou Info 启动` with `mode=info|version` and the checkout scope.
2. Resolve the checkout from a user-supplied path, or from the current Git root only when both `scripts/azhou_hub.py` and `docs/skill-standard.md` exist. Do not scan unrelated directories or infer a harness home.
3. Run one read-only command from that checkout:
   - General project/runtime/support facts and installable repository inventory: `python3 scripts/azhou_hub.py info --json`
   - Revision, branch, dirty state, or release-version questions: `python3 scripts/azhou_hub.py version --json`
4. Report only fields returned by the command. A missing `release_version` is not an installation failure and must not be invented.
5. End with a receipt containing `schema`, `status`, `mode`, `scope`, `command`, `changes`, `verification`, `holds`, and `next_action`. `changes` is always empty.

If no valid checkout is available, stop with `status=hold` and request one explicit checkout path. For requirements and a smoke check, read [setup and compatibility](references/setup.md).
