# Upstream compatibility

This map records the imported `lavish` baseline at commit `79aa0a18dba9c1a1dcec6db19d2ef4eb7643754b` (release `lavish-axi-v0.1.97`) and the Azhou packaging layer on it. Preserve every non-conflicting upstream capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| CLI as the current source of guidance (`--help`, `reply --help`, `design`, `playbook`) | preserved | `SKILL.md` "Current guidance lives in the CLI" |
| `npx -y lavish-axi <html-file>` without a global install | preserved with locked baseline | every command pinned to `lavish-axi@0.1.97` |
| Follow-up `lavish-axi ...` output commands re-run through npx | preserved | `SKILL.md` CLI rules |
| Explicit `/lavish` request and conversation inference | preserved | Request section; `/super-lavish` and the compatibility `/lavish` |
| Review loop: open, annotate elements or selections, queue prompts, feedback return | preserved | delegated to the locked CLI at run time |
| `self_paint_warning` repair before polling; passive non-queued warnings stay inert | preserved | `SKILL.md` artifact workflow step 3 |
| Foreground long-poll; apply feedback in the same session | preserved | `SKILL.md` artifact workflow steps 3–4 |
| One-shot agent reply without re-polling (`reply`) | preserved | `SKILL.md` artifact workflow step 4 |
| `end` and `Send & End` semantics | preserved | `SKILL.md` artifact workflow step 5 |
| Never reopen browser-ended sessions uninvited | preserved and strengthened | Authorization boundaries |
| Portable standalone export and `ht-ml.app` sharing | preserved with safety checkpoint | explicit publication authorization required |
| Local/global installed-copy fallback for restricted sandboxes | preserved | `SKILL.md` CLI section, same-version requirement |
| `license` and `metadata` frontmatter (`argument-hint`, `hermes-tags`, `hermes-category`) | intentionally omitted | neutral runtime packages expose only `name`, `description`, `invocation`; no behavior removed |
| Unpinned `npx -y lavish-axi` | intentionally narrowed | locked baseline `0.1.97` for reproducibility; upgrade path in `setup.md` |
| Baked workflow/playbook prose in the skill entry (pre-retirement package, `artifact-mode.md`) | intentionally omitted | the `0.1.97` upstream skill itself directs agents to the CLI because installed copies go stale; baking a snapshot would reintroduce drift |
| Spec Relay relay mode and `relay_state.py` | retired with the 2026-11-09 retirement | not resurrected; the maintainer does not operate the relay-handoff surface |
| Azhou interaction branding outside HTML | local enhancement | stable agent stage anchors and receipts; HTML artifacts, commands, and evidence stay brand-neutral |
| Publication, global-install, and hook authorization checkpoints | local enhancement | Authorization boundaries in `SKILL.md` |
| Boundary carve with `super-archify` and `super-excalidraw-diagram` | local enhancement | description records the static-map/explainer and editable-scene boundaries |

A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence.
