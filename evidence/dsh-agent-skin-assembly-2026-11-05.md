# Agent Skin DeepSeek Harness plugin assembly receipt (2026-11-05)

Scope: the `azhou-agent-skin` DSH plugin emitter on branch `codex/agent-skin-dsh-plugin` (commits `5b9ea50`, `761c7a8`, `28b85a6`, `79d5740`). Every claim below names the command that produced it. The receipt records local assembly evidence only; it does not claim live-host acceptance.

## What was built

`python3 -B tools/build-dsh-plugin.py` (from `packages/agent-skin/`) emits `.build/azhou-dsh-plugin/azhou-agent-skin/` and prints `{"kind":"dshPlugin","plugin":"azhou-agent-skin","appVersion":"0.9.0","appBuild":"33","protocolVersion":1,"outputs":7,"scope":"local assembly only; installing into a DSH profile is a separate manual step; no install or host writes"}`.

The package carries `client.js` (6,707,446 bytes), `icon.png` (78,001 bytes, 256×256 PNG via sips), `manifest.json`, `package.json`, `cordis.patch.yml`, `index.js`, and `locale/{zh,en}.json`. `package.json` declares `dsh.bundle.patch` → `./cordis.patch.yml`, `dsh.client` `{platform:"web", immediately:true, inject:[]}`, and the `./client` export; `cordis.patch.yml` inserts one row `id: azhou-agent-skin`. The host half `index.js` is the official no-op template.

## Verified, each from a command line

- Determinism. Two full builds produce identical bytes. Aggregate SHA-256 over the eight output files is `d89e0086ef8b4f63…` after both runs (`shasum -a 256` over `tools/build-dsh-plugin.py` outputs, run twice).
- Package verification. `python3 -B tools/verify-artifacts.py --verify-dsh-plugin .build/azhou-dsh-plugin/azhou-agent-skin` passes: manifest digest binding to current source inputs, one `window.__ModuleLoader__.load(` registration, `createDSHPageAdapter(` embedded exactly once with its binding line, no Codex or ZCode adapter in `client.js`, no import/export, no URL literals or fetch/XMLHttpRequest, the 24 MiB cap, `DEFAULT_ASSETS` present, locale meta present, icon a valid PNG within 256 KiB.
- Syntax. `node --check .build/azhou-dsh-plugin/azhou-agent-skin/client.js` passes.
- Guard behavior. `python3 -B tools/test-dsh-build.py` (9 tests, OK) includes a `node:vm` probe: `apply(ctx)` on a page without `__DSH_BOOT__`/`__ModuleLoader__` returns `{installed:false, reason:'page-unsupported'}` and makes zero `ctx.effect` calls.
- Package suites. `node --test tools/*.test.mjs` from `packages/agent-skin` reports 298 tests, 298 pass, 0 fail. `python3 -B tools/test-startup-build.py`, `test-production-builders.py`, and `test-production-verifier.py` pass, including the frozen Codex and ZCode fixture regressions.
- Coverage. `python3 -B tools/test-unit-coverage.py --language javascript` reports 95.40% and passes. The Python and shell legs cannot run on this machine (missing `coverage` module and `bashcov` gem, a pre-existing environment gap); `test-dsh-build.py` is registered in the suite list for the CI leg.
- Repository gate. `python3 scripts/verify.py` from the repository root prints `verification passed`.

## Source-level grounding, not host evidence

The adapter's page predicates rest on source readings of the installed DeepSeek Harness 0.2.1-rc.5 application archive, not on a live session: `__DSH_BOOT__` and `window.__ModuleLoader__` are injected before the web shell reads them; the theme presenter writes `--dsw-*` token variables and the `data-ds-dark-theme` attribute on `document.body`; the shell renders under `#root` with `data-slot` containers including `sidebar.footer.action` and `main`. Two installed third-party plugins (`dsh-pet`, `@smalltailqwq/dsh-client-ui-skin-maid-atelier`) supplied the package-manifest and client-module shapes.

## Not performed, not claimed

No live-host step ran. The `dsh` CLI is not on this machine's PATH and the in-session `plugin_manager` tool is unavailable, so nothing was installed into any `~/.dsh` profile. In-host rendering, the sidebar entry, wallpaper application on the real main surface, the IndexedDB namespace on the real origin, and Plugin Manager display of the title, description, and icon all remain unverified.

## Revisit trigger

A live-host round needs one of two paths: the `dsh` CLI (`dsh plugin --profile <throwaway> add <absolute package dir>`) or an agent session with the `plugin_manager` tool (`action: install_bundle`). Both paths record their own receipt; this one does not pre-approve them.
