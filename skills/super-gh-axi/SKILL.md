---
name: super-gh-axi
description: "Azhou skill. Renamed from gh-axi (the old name still triggers this skill). Agent-ergonomic GitHub operations through the locked gh-axi@0.1.52 CLI, a gh wrapper: issues, pull requests, stacked PRs and branches, discussions, workflow runs and workflow dispatch, releases, repositories, labels, gists (list, view, edit, rename, create, delete, clone), Projects (v2) boards, Actions secrets and variables, search, and raw API access. MUST trigger whenever a task touches GitHub — listing or filing issues, reviewing or merging PRs, managing stacked branches and PRs, checking CI runs, triggering workflows, cutting releases, managing labels, gists, Projects boards or Actions secrets/variables — unless the current repository's rules name a different GitHub CLI or recipe for that task (project rules win). Current command, flag and workflow guidance lives in the CLI, not in this file."
invocation: model-invoked discipline
---

# Super Gh Axi

Super Gh Axi is the GitHub operations contract for agents: GitHub-touching work goes through the locked `gh-axi@0.1.52` CLI baseline — an agent-ergonomic wrapper around `gh` with token-efficient output, contextual suggestions and idempotent mutations — and the current command surface is always read from the CLI, never from this file.

**🦊 阿舟 · Gh Axi**

> GitHub 操作，真相永远在 CLI 里。

Invocation class: model-invoked discipline, declared in frontmatter; the axis and its semantics are defined once in `docs/skill-standard.md` §2.2 — reached autonomously whenever a task touches GitHub, no explicit naming required. Orchestrators may point here; this skill orchestrates nothing and calls no orchestrator.

## Brand protocol

Emit once when the skill starts, before any tool call:

```text
🦊 阿舟 · Gh Axi 启动（mode=<inspect|operate|raw>, scope=<github-area>）
```

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1 chat presentation). Peeling the leading `>` and paired `**` must restore the protocol line. Headless, CI logs, receipts, and machine fields stay protocol-only.

Use `✅ 验证通过` only after the named checks actually ran. Use `❌ 验证失败` when this attempt fails and name one repair action, and `🔒 阿舟暂停这一项` when input, permission, or a dependency is missing. Emoji is display-only: keep it out of JSON keys, schema values, digests, paths, commands, test names, and raw evidence. A host without Unicode may strip the leading emoji while preserving the fixed text, the `（k=v, k=v）` field grouping, fields, and values. Raw evidence stays out of receipts unless the user supplied it. Stage events, the status dictionary, and the stable receipt are defined in the [Azhou interaction layer](references/brand-layer.md).

## Current guidance lives in the CLI

Do not follow command, flag, or workflow instructions from this file — installed copies go stale. Get the current source of truth from the locked baseline:

- `npx -y gh-axi@0.1.52` for a dashboard of the current repo
- `npx -y gh-axi@0.1.52 --help` for global flags and the command index
- `npx -y gh-axi@0.1.52 <command> --help` for per-command usage

You do not need `gh-axi` installed globally. Invoke the locked baseline with `npx -y gh-axi@0.1.52 <command>`. If CLI output shows a follow-up command starting with `gh-axi`, run it as `npx -y gh-axi@0.1.52 ...` instead. In restricted subprocess sandboxes, CI, or agent harnesses where `npx -y` exits opaquely, use an already-installed copy of the same version directly: `node "$(npm root)/gh-axi/dist/bin/gh-axi.js" <command>` for a local install, `node "$(npm root -g)/gh-axi/dist/bin/gh-axi.js" <command>` for a global install, or the bare `gh-axi <command>` bin after installing version `0.1.52` once. Never run the CLI's built-in `update` command: it floats the locked baseline outside the recorded provenance.

The CLI wraps `gh`: it needs the `gh` binary (its own guidance names `gh >= 2.99.0` for `--attach` support; `GH_BIN` overrides the binary) and `gh`'s existing authentication. Read [setup](references/setup.md) before first use, or whenever Node, npx, `gh`, or the locked baseline is not verified yet.

## Workflow

1. **Resolve the baseline.** Confirm Node 20+, npx, the `gh` binary, and `gh` authentication, then read the current command surface from the locked CLI's help. When any of these cannot be resolved, stop with a named hold — fail closed, no version substitution, no unauthenticated guessing.
2. **Name the target and the authority.** Resolve the repository (explicit `-R/--repo <OWNER/NAME>`, `--hostname`, or the current checkout), classify the request as inspect, operate, or raw API access, and check the current repository's rules first: when they name a different GitHub CLI or recipe for the task, those rules win. Mutating operations — create, edit, close, merge, delete, release, label, secret or variable changes — run only for what the request explicitly names; a broad instruction never widens into deletions or secret changes.
3. **Execute through the locked baseline.** Run one command per intent, prefer the CLI's idempotent mutations, and read what the output actually reports — the token-efficient output is a fact channel, not a summary of intent. Never echo credentials, tokens, or secret values into logs, receipts, or raw evidence; a secret operation reports the secret name, never the value.
4. **Verify and hand off.** For mutating operations, re-read the resulting state through the CLI (view the issue, PR, release, or run it produced) before claiming it; a zero exit code is not state evidence. Report object numbers and URLs from CLI output. End with the stable `super-gh-axi.receipt.v1` receipt from [brand-layer](references/brand-layer.md).

## Authorization boundaries

- Read operations over repositories the existing `gh` credentials can already see are in scope; authorization to operate does not grant authority over repositories the request never named.
- Do not install global packages, run the CLI's `setup hooks`, or change global agent configuration without explicit authorization.
- Never run the CLI's built-in `update` command or otherwise float the locked baseline; upgrades follow the recorded path in [setup](references/setup.md).
- Do not read, copy, print, or persist `gh` tokens or credentials; the CLI resolves authentication itself, and raw evidence stays out of receipts unless the user supplied it.
- Deleting repositories, cancelling or deleting workflow runs, and changing Actions secrets stay named-operation-only: they never ride along with a broader request.

## Completion

End with the stable receipt defined in [brand-layer.md](references/brand-layer.md): `super-gh-axi.receipt.v1`. Keep `complete`, `complete_with_holds`, `hold`, and `failed` distinct; none substitutes for another. A command that exited zero does not prove the resulting GitHub state; only the CLI's re-read state does. An open pull request does not prove review or merge; a merged PR does not prove CI green.
