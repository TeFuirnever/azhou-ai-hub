---
name: super-lavish
description: "Azhou skill. Renamed from lavish (the old name still triggers this skill). Turn complex or visual agent responses into rich, reviewable HTML artifacts the user can annotate, select, and send feedback on through the lavish-axi CLI browser review loop. Use when about to give a plan, comparison, diagram, table, code diff, report, prototype, or anything easier to grasp visually than as prose; also for 把这个结果做成可审阅的 HTML. Static interactive diagram maps and one-page explainers belong to super-archify; editable Excalidraw scenes belong to super-excalidraw-diagram; a human-annotated feedback loop on a generated page belongs here; raster images belong to super-imagegen."
invocation: both
---

# Super Lavish Editor

Super Lavish Editor turns rich HTML artifacts into collaborative human review surfaces. First generate an interactive HTML artifact for the request, then run `npx -y lavish-axi@0.1.98 <html-file>` so the user can inspect it in the browser, annotate elements or selected text, queue prompts, and send feedback back to the agent.

**🦊 阿舟 · Super Lavish**

> 把复杂结果变成可审阅的界面。

## Brand protocol

Emit once when the skill starts, before any tool call:

```text
🦊 阿舟 · Super Lavish 启动（mode=<artifact|review|export|share>, scope=<short scope>）
```

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1 chat presentation). Peeling the leading `>` and paired `**` must restore the protocol line. Headless, CI logs, receipts, and machine fields stay protocol-only.

Use `✅ 验证通过` only after the named checks actually ran. Use `❌ 验证失败` when this attempt fails and name one repair action, and `🔒 阿舟暂停这一项` when input, permission, or a dependency is missing. Emoji is display-only: keep it out of JSON keys, schema values, digests, paths, commands, test names, and raw evidence. A host without Unicode may strip the leading emoji while preserving the fixed text, the `（k=v, k=v）` field grouping, fields, and values. Raw evidence stays out of receipts unless the user supplied it. Stage events, the status dictionary, and the stable receipt are defined in the [Azhou interaction layer](references/brand-layer.md).

## Current guidance lives in the CLI

Do not follow workflow, design, or playbook details from memory — installed copies go stale. Get the current source of truth from the locked CLI baseline:

- `npx -y lavish-axi@0.1.98 --help` for commands and the review-loop workflow
- `npx -y lavish-axi@0.1.98 reply --help` to post an agent reply and exit once the server accepts it, when you are not about to long-poll
- `npx -y lavish-axi@0.1.98 design` for design-direction priority and current snippets
- `npx -y lavish-axi@0.1.98 playbook <id>` for focused artifact guidance (`playbook` with no id lists the ids)

You do not need `lavish-axi` installed globally. Invoke the locked baseline with `npx -y lavish-axi@0.1.98 <html-file>`. If CLI output shows a follow-up command starting with `lavish-axi`, run it as `npx -y lavish-axi@0.1.98 ...` instead. In restricted subprocess sandboxes, CI, or agent harnesses where `npx -y` exits opaquely, use an already-installed copy of the same version directly: `node "$(npm root)/lavish-axi/dist/cli.mjs" <html-file>` for a local install, `node "$(npm root -g)/lavish-axi/dist/cli.mjs" <html-file>` for a global install, or the bare `lavish-axi <html-file>` bin after installing version `0.1.98` once.

## Request

$ARGUMENTS

If the request above is non-empty, the user invoked `/super-lavish` (or the compatibility name `/lavish`) explicitly. Build the HTML artifact for that request now.
If it is empty, infer what to visualize from the conversation: a plan, comparison, diagram, table, code view, report, prototype, or review loop that is clearer as a page than as prose.

## Artifact workflow

1. Generate the HTML artifact for the request. Default path `.lavish/<name>.html`. `.lavish/` is ignored at the repository root; keep artifacts with private content out of Git unless the user explicitly selects one for version control.
2. Read [setup](references/setup.md) before first use, or whenever Node, npx, or the locked baseline is not verified yet.
3. Open the review session with the locked baseline and keep polling in the foreground. Repair any `self_paint_warning` the CLI reports before polling; passive layout warnings that were not queued stay inert.
4. Long-poll for feedback and apply every returned prompt in the same session. Use one `reply` only when the user asks for a one-shot answer without re-polling.
5. Run `end` when the review finishes and process one final `Send & End` return. Do not reopen a session the user ended from the browser unless the user asks; when material new facts require reopening, explain why first.
6. End with the stable `super-lavish.receipt.v1` receipt from [brand-layer](references/brand-layer.md).

## Authorization boundaries

- Create local artifacts and open local review sessions when they are in scope.
- Do not install global packages, install session hooks, or change global agent configuration without explicit authorization.
- Do not run `share` without explicit publication authorization. A share uses the third-party `ht-ml.app` service and is public by default unless a password is supplied. Authorization to create or review an artifact is not authorization to publish it.
- `.lavish/` artifacts can carry private comments and selection state: copying, exporting, or sharing the file also transfers that content.

## Completion

End with the stable receipt defined in [brand-layer.md](references/brand-layer.md): `super-lavish.receipt.v1`. Keep `complete`, `complete_with_holds`, `hold`, and `failed` distinct; none substitutes for another. A local artifact or an open session does not prove human review, export portability, or publication. Browser feedback is only deliverable after the poll returns it; an open session does not prove feedback was persisted.
