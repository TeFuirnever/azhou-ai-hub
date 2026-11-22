# Setup

## Runtime dependencies

| Dependency | Required for | Minimum version | Install / verification |
|---|---|---|---|
| Python 3 | all eight packaged scripts | 3.11 (the repository-gate baseline; seven of the eight scripts use only the standard library, and export_png.py additionally needs Playwright) | present on the checkout host; verify with `python scripts/self_check.py --help` exiting 0 |
| Playwright with a Chromium build (optional) | `scripts/export_png.py` rasterization and the optional render-and-look browser preview | current Playwright release | `pip install playwright` then `playwright install chromium`; `python scripts/export_png.py --help` exiting 0 confirms the Playwright package imports; run one real export to confirm the Chromium build |

Everything else is dependency-free: `self_check.py`, `verify_geometry.py`, `export_svg.py` and the four import extractors (`drawio_extract.py`, `excalidraw_extract.py`, `mermaid_extract.py`, `plantuml_extract.py`) run on the Python standard library alone.

## Failing closed

- `scripts/export_png.py` imports Playwright at startup; without it the script exits with an import error before touching any file. Deliver SVG (standard library) or install Playwright — never claim a PNG export that did not run.
- The optional browser preview of a generated diagram needs the same Playwright Chromium build. Without it, deliver the HTML file itself and skip the look step; a skipped visual check is a named hold, not a pass.
- No diagram CLI is required for import: the four extractors parse `.drawio`, `.excalidraw`, Mermaid and PlantUML sources directly from the file text, with no network access.

## Verification

Run the packaged self-check on any generated or imported diagram, from the installed skill directory:

```bash
python scripts/self_check.py my-diagram.html
```

A passing self-check exits 0; a truncated, mojibake, unsafe or out-of-viewBox file exits non-zero with named findings. `scripts/verify_geometry.py <file>` checks the connector/label geometry contract on top of it.

## System modifications

None. The scripts read their inputs, write only the outputs they are given (`--out` or the explicit destination), and never install, mutate or delete anything outside the paths handed to them.
