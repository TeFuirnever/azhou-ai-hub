# pstack-azhouzhou host migration receipt (2026-11-12)

Scope: migrate the maintainer machine's production Codex registration (`~/.codex`) from the pre-rename identity `pstack-azhouzhou@pstack-claude` (0.15.36 installed cache) to `pstack-azhouzhou@azhou-hub` (0.15.37), on the same day PR #451 landed the marketplace rename (`ab846748`). Everything below was measured on this host through the PATH `codex` CLI (`codex-cli 0.167.0`).

## Pre-state (recorded before any mutation)

- `~/.codex/config.toml` line 354: `[marketplaces.pstack-claude]`, `source_type = "local"`, `source = /Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub/packages/pstack-agent-harness`; line 400: `[plugins."pstack-azhouzhou@pstack-claude"]`, `enabled = true`.
- `codex plugin marketplace list` reported the `pstack-claude` marketplace rooted at the maintainer checkout package path, beside five unrelated marketplaces.
- Model sheet `~/.codex/pstack-models.md` SHA-256 `774f5fa26a99a61c6cf1e122557e410382960038`.
- ChatGPT Desktop was running during the migration (Codex Framework `157.0.8103.51`, app-server daemon `0.167.2`). The CLI operates on the same `config.toml`; no concurrent host-side plugin operation was performed.

## Marketplace-root prerequisite

The registered marketplace root is the maintainer checkout itself, and that checkout was still at `9178880c` (pre-rename manifest) when the migration started. Re-adding from it would have re-registered the old name, so the checkout was first fast-forwarded: `git pull --ff-only origin main` on a clean working tree moved it `9178880c` → `ab846748` (25 files, +261/−79, all pstack package files, docs and CHANGELOG). The root manifest then reported `"name": "azhou-hub"`.

## Commands and outputs (verbatim tails)

1. `codex plugin remove pstack-azhouzhou@pstack-claude` → `Removed plugin 'pstack-azhouzhou' from marketplace 'pstack-claude'.`
2. `codex plugin marketplace remove pstack-claude` → `Removed marketplace 'pstack-claude'.`
3. `codex plugin marketplace add /Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub/packages/pstack-agent-harness` → `Added marketplace 'azhou-hub' from /Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub/packages/pstack-agent-harness. Installed marketplace root: /Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub/packages/pstack-agent-harness`
4. `codex plugin add pstack-azhouzhou@azhou-hub` → `Added plugin 'pstack-azhouzhou' from marketplace 'azhou-hub'. Installed plugin root: /Users/guanxueliang/.codex/plugins/cache/azhou-hub/pstack-azhouzhou/0.15.37`

## Post-state (each from a command line)

- `codex plugin marketplace list`: `azhou-hub` rooted at the maintainer checkout package path; no `pstack-claude` row.
- `codex plugin list --marketplace azhou-hub`: `pstack-azhouzhou@azhou-hub  installed, enabled  0.15.37`.
- `config.toml`: `[marketplaces.azhou-hub]` at line 366 and `[plugins."pstack-azhouzhou@azhou-hub"]` / `enabled = true` at lines 409–410; `grep -c pstack-claude config.toml` = 0.
- Installed manifest `.codex-plugin/plugin.json` version `0.15.37`; 68 `SKILL.md` files under the installed tree.
- Model sheet digest unchanged: `774f5fa26a99a61c6cf1e122557e410382960038`.
- The CLI removal emptied `~/.codex/plugins/cache/pstack-claude/` and left the empty directory; it was removed with `rmdir`, after which no `pstack-claude` path remains under `plugins/`.
- No `hooks.state` table entries referencing pstack exist in `config.toml`.
- ChatGPT Desktop was quit after the migration; a re-check with zero `ChatGPT.app` processes found `config.toml` intact (no write-back clobber) and the CLI view unchanged.

## Not claimed

- Live-session workflow or model-dispatch behavior on the renamed identifier (no session was driven).
- SessionStart hook trust: no pstack hook state exists in `config.toml`, so automatic injection requires a fresh `/hooks` review in a new host session after the desktop host restart; explicit Skill invocation does not depend on it.
- Behavior beyond native registration, installed-file verification and the digest comparisons above. The Hub adapter's lifecycle (`plan`/`apply`/`doctor`) was not run against this shared production home — by design it refuses shared homes; this migration used the host's own plugin manager, matching the 2026-11-04 native-install boundary.
