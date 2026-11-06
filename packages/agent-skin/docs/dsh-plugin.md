# Agent Skin DeepSeek Harness plugin contract

This page is reference for the `azhou-agent-skin` DSH plugin package. It records what the package contains, how the client module behaves, and what is deliberately absent. Build and evidence commands live in the [assembly receipt](../../../evidence/dsh-agent-skin-assembly-2026-11-05.md).

## Package layout

`python3 -B tools/build-dsh-plugin.py` from `packages/agent-skin/` assembles `.build/azhou-dsh-plugin/azhou-agent-skin/`:

| File | Role |
| --- | --- |
| `package.json` | `dsh.bundle.patch` → `./cordis.patch.yml`; `dsh.client` `{platform:"web", immediately:true, inject:[]}`; exports `.`, `./client`, `./locale/*.json`, `./package.json` |
| `cordis.patch.yml` | One insert row `id: azhou-agent-skin`, `name: 'azhou-agent-skin'` |
| `index.js` | Host half, the official no-op `export function apply() {}` |
| `client.js` | `window.__ModuleLoader__.load` factory embedding the neutral core plus `createDSHPageAdapter` and the bootstrap wiring |
| `locale/{zh,en}.json` | Plugin Manager `meta.title` and `meta.description` |
| `icon.png` | 256×256 PNG generated from the theme icon input, within the 256 KiB limit |
| `manifest.json` | Build receipt: source inputs, per-file digests, `targetHost: dsh`, the no-install scope string |

The emitter reuses `build_startup(host='dsh')` from `tools/build-startup.py` for the payload body, so the animation, settings, and wallpaper code is the same neutral core the Codex and ZCode payloads embed. The DSH page adapter is `extension/hosts/dsh.mjs`.

## Client module behavior

`client.js` registers one factory whose module exports `{apply, inject}` with an empty `inject` list. `apply(ctx)` does the following, in order:

1. Returns `{installed:false, reason:'page-unsupported'}` unless the page shows the DSH boot graph, a top-level window with `__ModuleLoader__` and an own `__DSH_BOOT__` data property.
2. If the document is still loading, waits for `DOMContentLoaded` and returns `{installed:false, reason:'dom-loading'}`; the wait listener is registered through `ctx.effect` and returns its own disposer.
3. Creates the page adapter with one disposal sink. The sink wraps each disposal function as `ctx.effect(() => () => fn(), label)`, because cordis runs an effect callback immediately and uses its return value as the disposer. The adapter's `registerCleanup` and the controller's owner-checked `__azhouStartup` disposal both route through the sink, so deactivating the plugin removes the entry, observers, overlay, and wallpaper.
4. Runs the bootstrap tail. Animation and entry visibility follow the controller's existing flow; the plugin adds no new trigger policy.

The wallpaper surface is the unique `[data-slot='main']` element. The appearance entry is an imperative handle appended to the stable sidebar column beside the `[data-slot='sidebar.footer.action']` container, never inside the React-rendered slot list. Theme comes from `data-ds-dark-theme` on `body` and the `--dsw-*` token variables the host writes inline on `body`. Settings persist in IndexedDB under the `azhou-dsh-startup` namespace, separate from the Codex and ZCode databases.

## Adapter capability groups

Since commit `5b9ea50`, a page adapter declares host behavior instead of neutral files branching on host names. `controllerWallpaper` carries `{owner, requiresControllerMetadata}`; a `wallpaper` ports group carries `{validPage, shellState, surfaces, attributes, css, scope}` and is atomic, an adapter that declares it partially is refused as `invalid-host-adapter`. An adapter without the group keeps the built-in Codex anchor path, which the standalone wallpaper payload and the preview fixture still use. The baseline key `zcodeAttributes` in `wallpaper/renderer.js` keeps its name verbatim so live 0.9.0 ZCode installations transfer recorded baselines across a replacement.

## Deliberate limits

- The default wallpaper is the payload's frozen `DEFAULT_ASSETS` artwork (1536×1024, `wallpaperStrength: 42`), the same object the Codex and ZCode payloads embed, and the controller applies it on first run; the live-host receipt observed it applied with all layer checks clear. Heavier additional artwork should not ride `client.js`: a follow-up can serve it from a host-half `webServer` prefix route, the pattern both installed third-party skins use.
- In-host rendering is verified to the machine level. The [live-host receipt](../../../evidence/live-dsh-plugin-host-2026-11-05.md) records the controller registered, the animation completing naturally, the sidebar entry mounted in the real column, the host palette token picked up, the default wallpaper applied, and the settings overlay opening; human aesthetic acceptance, the wallpaper import dialog, Plugin Manager display, and the production-profile install remain open.
- No `dsh.compatibility.dshReleases` map. Compatibility declarations follow accepted live-host rounds, and the aesthetic acceptance is still open.
