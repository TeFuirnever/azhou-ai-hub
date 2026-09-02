# Dependencies and setup

Read this before first use or when rendering, conversion, export, or font tooling fails.

## Runtime requirements

| Requirement | Minimum | Purpose |
|---|---:|---|
| Python | 3.11 | renderer, official export, converters, validation gates |
| Node.js + npm | Node 20 | local rough-SVG renderer |
| uv | maintained release | locked Python environment |
| Chromium for Playwright | version selected by Playwright | offline render and official export |
| Disk | about 750 MB | current macOS arm64 Python environment, browser, vendored assets, Node modules; varies by platform |

Rendering is offline after dependency installation. Interactive MCP preview is optional and harness-specific; file generation and validation do not depend on it.

## Declared and vendored dependencies

| Component | Declaration or asset | Install action |
|---|---|---|
| Playwright Python | `references/pyproject.toml`, `references/uv.lock` | `uv sync --frozen` |
| Playwright Chromium | Playwright browser manifest | check first; install only when the runtime check exits `2` |
| roughjs, jsdom | `scripts/package.json`, `scripts/package-lock.json` | `npm ci` |
| Excalidraw engine and converters | `references/vendor/excalidraw-all.esm.js` | none; vendored |
| Official fonts | `references/fonts/` | none; vendored |
| Official component libraries | `references/libraries/` | none; vendored |
| Core Python gates | Python standard library | none |
| Xiaolai subsetter | fonttools and brotli | ephemeral `uv run --with ...` |

## Inspect before installing

Set `SKILL_DIR` to the installed skill directory. Do not assume a Codex-, Claude-, zcode-, or project-specific location.

```bash
SKILL_DIR=/absolute/path/to/excalidraw-diagram
python3 --version
node --version
npm --version
uv --version

cd "$SKILL_DIR/references"
uv sync --frozen --dry-run

cd "$SKILL_DIR/scripts"
npm ci --dry-run --ignore-scripts
```

If `uv` is missing, install it as an isolated CLI:

```bash
pipx install uv
```

Install Node.js/npm with the operating system's package manager or an existing version manager. Do not alter global agent or harness configuration.

## Install

```bash
SKILL_DIR=/absolute/path/to/excalidraw-diagram

cd "$SKILL_DIR/references"
uv sync --frozen
uv run python "$SKILL_DIR/scripts/check-playwright-runtime.py"

cd "$SKILL_DIR/scripts"
npm ci --ignore-scripts
```

If the runtime check exits `2`, Chromium for the locked Playwright version is absent. Install it once, then repeat the check:

```bash
cd "$SKILL_DIR/references"
uv run playwright install chromium
uv run python "$SKILL_DIR/scripts/check-playwright-runtime.py"
```

Exit `0` means the browser is already ready and must not be reinstalled. Exit `1` or `3` identifies a Playwright runtime or Python-package problem; fix that problem instead of downloading Chromium. After the locked Playwright version changes, repeat the check and install only if it exits `2`. Linux CI may require Playwright system libraries; use `uv run playwright install --with-deps chromium` only in an environment where OS-package changes are authorized.

## Verify

```bash
SKILL_DIR=/absolute/path/to/excalidraw-diagram

test -s "$SKILL_DIR/references/vendor/excalidraw-all.esm.js"
test -d "$SKILL_DIR/references/fonts/Excalifont"
test -d "$SKILL_DIR/references/libraries"

cd "$SKILL_DIR/references"
uv run python -c "import playwright; print('playwright ok')"
uv run python "$SKILL_DIR/scripts/check-playwright-runtime.py"
uv run playwright install --list

python3 "$SKILL_DIR/scripts/check-scene-hygiene.py" --help
python3 "$SKILL_DIR/scripts/check-handdrawn-style.py" --help
node "$SKILL_DIR/scripts/to-excalidraw.mjs"
```

The last command prints usage and exits `1`; that is the expected no-input smoke result.

## Script-specific requirements

| Script | Additional requirement |
|---|---|
| `scripts/export-official-svg.py` | uv environment + Chromium |
| `scripts/visual-check.py` | uv environment + Chromium; exit `2` means browser unavailable |
| `scripts/mermaid-to-excalidraw.py` | uv environment + Chromium |
| `scripts/svg-to-excalidraw.py` | uv environment + Chromium |
| `scripts/render-svg.mjs` | npm dependencies installed in `scripts/` |
| `scripts/subset-xiaolai.py` | `uv run --with fonttools --with brotli python ...` |
| `scripts/excalidraw_lib.py` | standard library; vendored libraries by default |

## Upgrade vendored assets

Treat engine bundle, converters, and fonts as one versioned set. Rebuild the consolidated ESM bundle in an isolated temporary project, then mirror fonts from the same `@excalidraw/excalidraw` release. Keep license files and update version evidence in [provenance.md](provenance.md).

After an upgrade, verify one real diagram through `render_excalidraw.py`, `export-official-svg.py --png`, the style gate, the hygiene gate, and the repository-level ordinary-model benchmark. Do not promote a dependency update from structural checks alone.
