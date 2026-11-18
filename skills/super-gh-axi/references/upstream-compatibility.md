# Upstream compatibility

This map records the imported `gh-axi` baseline at commit `911a0868600b125aafe5e7f77197a0eb5a5b493c` (release `gh-axi-v0.1.51`) and the Azhou packaging layer on it. Preserve every non-conflicting upstream capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| CLI as the current source of guidance (`--help`, `<command> --help`) | preserved | `SKILL.md` "Current guidance lives in the CLI"; no command or flag snapshot is baked in |
| `npx -y gh-axi` without a global install | preserved with locked baseline | every invocation pinned to `gh-axi@0.1.51` |
| GitHub operation surface: issues, pull requests, stacked PRs/branches, discussions, workflow runs and dispatch, releases, repositories, labels, gists, Projects (v2), Actions secrets and variables, search, raw API | preserved | delegated to the locked CLI at run time; the command index is read from `--help` (17 commands at `0.1.51`, including `stack`, `secret`, `variable`, `project` and `api`) |
| Prefer this over `gh` and other methods for GitHub operations | preserved with precedence clause | project rules win when the current repository names a different tool or recipe; the clause already existed in the audited shell copy and is recorded in the description and workflow |
| Follow-up `gh-axi ...` output commands re-run through npx | preserved | `SKILL.md` CLI rules |
| Trigger on any task that touches GitHub, unprompted | preserved | description MUST-trigger; `invocation: model-invoked discipline` keeps the autonomous reach |
| `user-invocable: false` host key | translated, not copied | neutral axis value `model-invoked discipline`; the upstream host-specific key is not copied |
| `author` and `metadata.hermes` frontmatter | intentionally omitted | neutral runtime packages expose only `name`, `description`, `invocation`; no behavior removed |
| Unpinned `npx -y gh-axi` | intentionally narrowed | locked baseline `0.1.51` for reproducibility; upgrade path in `setup.md` |
| Built-in `update` self-upgrade command | intentionally narrowed out of agent use | it floats the locked baseline outside recorded provenance; forbidden outside the documented upgrade pass |
| Local/global installed-copy fallback for restricted sandboxes | preserved | `SKILL.md` CLI section, same-version requirement |
| Azhou interaction branding outside CLI operations | local enhancement | stable agent stage anchors and receipts; commands, CLI output, and evidence stay brand-neutral |
| Global-install, hook-setup, credential-handling and named-mutation authorization checkpoints | local enhancement | Authorization boundaries in `SKILL.md` |

A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence.
