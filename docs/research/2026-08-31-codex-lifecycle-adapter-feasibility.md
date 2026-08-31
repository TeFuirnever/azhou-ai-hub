# Codex lifecycle adapter feasibility decision — Super Caveman

> Decision date: 2026-08-31 (Asia/Shanghai). Evidence access date: 2026-08-31.
> Requested by: #39 (follow-up to #36). Not part of Claude v1 completion.
> Sources: official Codex documentation at learn.chatgpt.com —
> [Hooks reference](https://learn.chatgpt.com/docs/hooks) and
> [Sample configuration](https://learn.chatgpt.com/docs/config-file/config-sample) —
> accessed 2026-08-31. Third-party sources were read only for orientation and are
> not cited as evidence.

## Decision

**A one-package Codex lifecycle adapter for Super Caveman is feasible** under the
same boundaries the Claude adapter (PR #71, #38) already enforces: neutral-core
response semantics stay authoritative, the adapter ships inside the canonical
`super-caveman` package, explicit scoped setup writes only owned hook entries,
state stays local and bounded, and the hook output remains a bounded response-style
injection that fails open. The official hooks framework supports every lifecycle
event the #36 contract needs (SessionStart with `startup|resume|clear|compact`
sources and UserPromptSubmit with prompt-bearing events), so no capability is
missing at the framework level.

**No cross-host parity is claimed or implied.** This decision records what official
Codex documentation supports; it does not claim identical behavior between the
Claude Code adapter and a Codex adapter. Codex CLI and Codex App claims stay
separate: official docs describe hooks product-agnostically and name only the CLI
for the `/hooks` trust workflow, so App behavior is classified unverified, not
supported.

## Official capability map (accessed 2026-08-31)

Official hooks reference (learn.chatgpt.com/docs/hooks), classified per #39. "Supported"
means the official docs describe the capability; "adapted" means the adapter must map
its contract onto it; "unverified" means the docs do not settle it and a real-host
receipt would be required before any support claim.

| #39 surface | Official Codex facts | Classification |
|---|---|---|
| Startup | `SessionStart` event with `matcher` on `source`: `startup`, `resume`, `clear`, `compact` | supported |
| Resume | `source=resume` delivered to the same `SessionStart` matcher; session state can persist in the package's own state layer | supported (state layer = adapted) |
| Clear/compact | `source=clear` and `source=compact` delivered to the same matcher; separate `PreCompact`/`PostCompact` events also exist | supported |
| Prompt submission | `UserPromptSubmit` event exists, carries the `prompt` field; `matcher` is ignored for this event | supported |
| Install scope | User `~/.codex/hooks.json` or `~/.codex/config.toml` `[hooks]`; project `<repo>/.codex/hooks.json` or `[hooks]`, loaded only when the project `.codex/` layer is trusted; plugin `hooks/hooks.json` plus managed sources exist; layers merge (all matching hooks run; higher layers do not replace lower) | supported (adapter only ever writes user/project `hooks.json` — never managed or plugin surfaces) |
| Hook input | Stdin JSON: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, plus `source` / `prompt` per event; `model`, and `turn_id` are Codex extensions | supported |
| Hook output | Exit 0 + no output = success; JSON `hookSpecificOutput.additionalContext` for SessionStart/UserPromptSubmit; plain stdout also becomes context for those events | supported (adapter emits only the JSON shape) |
| Output limits | `additionalContextLimit` caps `additionalContext` tokens, default ~2,500; overflow spills to a temp file with a head-and-tail preview | supported (adapter self-bounds below the cap) |
| Timeout | `timeout` in seconds, default 600 for most hooks; SessionEnd caps 1-3s; background hooks async up to 8 concurrent | supported (adapter registers timeout 5) |
| Failure semantics | Default fail-open; blocking only via explicit deny/block shapes or exit 2; unsupported fields mark the hook run failed and continue | supported (adapter always exits 0, never emits deny/block) |
| Trust and review | Non-managed hooks require explicit per-definition trust (hash-recorded); new or changed hooks are skipped until re-trusted; `/hooks` in the CLI inspects/trusts; project hooks need project-layer trust | supported; the setup flow must document mandatory host trust confirmation before behavior is active |
| Feature flag | `[features] hooks = false` disables the framework entirely; `codex_hooks` is a deprecated alias | supported (status must treat a disabled framework as installed-but-inactive) |
| State persistence | `[history] persistence = "save-all"`, `resume_cwd`, and session resume are documented; the package's own defaults/session state is adapter-owned and adapter-scoped | adapted (package-owned state under `~/.config/super-caveman/` and `.azhou/super-caveman/`) |
| Compaction/resume events | SessionStart sources + PreCompact/PostCompact; repeated legitimate compact stays valid (one output per delivered event) | supported |
| Cross-surface (App) | Docs list six surfaces ("ChatGPT desktop app", "Remote", "ChatGPT on the web", "Codex CLI", "Codex IDE extension", "Codex cloud") and describe hooks product-agnostically; only the CLI is named for `/hooks` trust; App trust workflow is not documented | unsupported to claim; **unverified** for the App |
| SessionEnd | Fires on archive/delete, close, or 30-min idle across clients; matcher on `reason` (currently `other`); 1-3s timeout cap | out of the #36 v1 contract; unused by the adapter |
| Managed enterprise hooks | `[hooks]` in `requirements.toml` with `managed_dir` / `windows_managed_dir`; `allow_managed_hooks_only` skips user/project/session/plugin hooks | out of scope; never written by the adapter |

## Existing main-reality coverage (scripts/codex_adapter.py)

`skills/super-caveman/scripts/codex_adapter.py` on main already provides:
`reconcile-legacy` (removes only the two superseded global Caveman/ADHD
SessionStart injections), scoped `setup`/`uninstall` writing only the standard
`~/.codex/hooks.json` / `<repo>/.codex/hooks.json`, one owned SessionStart
registration (`startup|resume|clear|compact`) with timeout 5, capsule ≤4,000 chars
with schema version + rules digest, fail-open rendering, symlink rejection, and
atomic writes. What it lacks versus the #36 state hierarchy: **no UserPromptSubmit
state machine** (mode switches, stop phrases, one-shot routes with restoration,
status/help/stats), **no persistent enable/disable defaults layers**, no session
state layer, and no status surface that reports defaults and effective mode.

## Follow-up requirements

If the captain orders the Codex adapter build: a separate reviewed spec ticket +
implementation ticket before code, deterministic lifecycle tests, a real-host
receipt before any support claim, and fresh exact-diff approval (the repo's
promotion law applies to any skill-tree revision). Until such a build is approved,
the support matrix correctly records no Super Caveman lifecycle-adapter row for
any host, and this decision file makes no support claim by itself.
