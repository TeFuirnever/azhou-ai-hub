# pstack-azhouzhou Claude Code update receipt (2026-11-18)

Scope: update the maintainer host's Claude Code user-scope plugin `pstack-azhouzhou@azhou-hub` from `0.15.37` to `0.15.38` through the Claude CLI's own plugin manager (`claude plugin update`). User-authorized in-session on 2026-11-18 after a version sweep found Claude Code as the only host behind the maintained `0.15.38` candidate. No other host's registration was touched.

## Pre-state

- `~/.claude/plugins/installed_plugins.json`: `pstack-azhouzhou@azhou-hub`, scope `user`, version `0.15.37`, `installPath` `~/.claude/plugins/cache/azhou-hub/pstack-azhouzhou/0.15.37`, `installedAt` `2026-11-13T05:10:10.254Z`.
- Marketplace `azhou-hub` is a directory source rooted at the maintainer checkout `packages/pstack-agent-harness` (`known_marketplaces.json`, last updated 2026-11-13). At update time that tree was byte-identical to `origin/main` `8097fc7a`: `git diff --stat origin/main..HEAD -- packages/pstack-agent-harness` is empty on the then-checked-out `docs/doc-calibration-20261118` (`9f2d8065`), whose only `packages/` changes are two `agent-skin` doc files.
- Marketplace manifest `.claude-plugin/marketplace.json` declared version `0.15.38`.

## Command and output (verbatim tail)

- `claude plugin update pstack-azhouzhou@azhou-hub` → `✔ Plugin "pstack-azhouzhou" updated from 0.15.37 to 0.15.38 for scope user. Restart to apply changes.`

## Post-state (each from a command line)

- `installed_plugins.json`: version `0.15.38`, `installPath` `.../pstack-azhouzhou/0.15.38`, `lastUpdated` `2026-11-18T01:56:13.419Z`.
- Installed `.claude-plugin/plugin.json` declares `"version": "0.15.38"`; its SHA-256 is `c72410f07a9333ed3238af6e7ed626cae30f5a10aa0be5efcece55da8534d52a`.
- The installed `0.15.38` tree carries 68 `SKILL.md` files under `skills/` beside `agents/`, `hooks/` and `docs/`; the retained `0.15.37` cache tree also carried 68, so this update is version alignment, not a skills-form change on this host.
- The CLI retained the old `0.15.37` cache directory; registry `installPath` no longer resolves to it, matching the known keep-old-cache behavior. It was left in place.
- Running Claude Code sessions require a restart to apply; no restart was performed or claimed here.

## Limits

- Installed-file identity and registry state are what this receipt establishes. It does not claim SessionStart hook trust, host workflow invocation, model dispatch, or any pstack task run on the Claude host.
- ZCode (`0.15.38`) and ChatGPT desktop Codex (`0.15.38` cache, enabled) were not modified; DeepSeek Harness and MiMo Code still carry no pstack plugin, with shared-root serving deferred to the separately scoped DSH task.
