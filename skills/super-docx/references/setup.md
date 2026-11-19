# Dependencies and setup

Read this before the first Word document operation on a machine, or whenever a recipe, a vendored script, or a CLI tool named by the guide fails.

The upstream declares its runtime surface in one Dependencies line — "`docx` (npm, preinstalled — install only if `require('docx')` fails) · `pandoc` · LibreOffice (`soffice`) · `pdftoppm` (Poppler)" — and assumes those tools are already present. This package does not assume. Every dependency below is named with what consumes it, how to verify it, and the failure boundary; dependencies the upstream never declares (the script-side Python imports, the `zip` binary, Node itself) are marked as such.

## Runtime dependencies

| Requirement | Consumed by | Verify |
|---|---|---|
| Python 3.11+ | all vendored Python scripts (`scripts/*.py` and the `scripts/office/` subtree) | `python --version` |
| Node.js | the Create track: the docx-js scripts the guide has the agent write at run time (`require('docx')`) — the npm `docx` library implies a Node runtime the upstream never names | `node --version` |
| npm `docx` library | the Create track (the "Creating with docx-js — gotchas" section); the upstream marks it preinstalled and its only repair is `npm install docx` | `node -e "require('docx')"` must resolve; version: `node -p "require('docx/package.json').version"` |
| `pandoc` | the Read track (`pandoc -t markdown file.docx`) and the tracked-changes caveats that compare `pandoc --track-changes=accept` | `pandoc --version` |
| LibreOffice (`soffice` on PATH) | `scripts/office/soffice.py` (every soffice invocation in this package runs the `soffice` binary through this wrapper, which resolves it from PATH), the Verify track (`--convert-to pdf`), the legacy `.doc` → `.docx` conversion, and `scripts/accept_changes.py` (macro-based accept) | `soffice --version` |
| `pdftoppm` (Poppler) | the Verify track (rasterizing the converted PDF into page JPEGs) | `pdftoppm -v` |
| `zip` | the Verify track's folder-entry drop (`zip -d output.docx '*/'`) and the Edit track's repack (`zip -XrDy ../out.docx .`) — **not declared anywhere in the upstream Dependencies line**; declared here | `zip -h` (prints usage and exits 0) |
| `defusedxml` | `scripts/comment.py`, `scripts/merge_runs.py`, `scripts/office/soffice.py`, `scripts/office/validate.py`, `scripts/office/validators/base.py`, `scripts/office/validators/docx.py`, `scripts/office/validators/redlining.py`, `scripts/office/helpers/pptx_chart.py` — script-side imports with no upstream declaration (recorded in the import review §3) | `python -c "import defusedxml; print(defusedxml.__version__)"` |
| `lxml` | `scripts/office/validators/base.py`, `scripts/office/validators/docx.py`, `scripts/office/validators/pptx.py` (the XSD validation behind `scripts/office/validate.py`) — script-side imports with no upstream declaration (recorded in the import review §3) | `python -c "import lxml.etree; print(lxml.etree.__version__)"` |

Probe note (2026-11-19, verified against installed distributions defusedxml 0.7.1 and lxml 6.1.3): both modules define `__version__`, so the probes read the attribute directly; no `importlib.metadata` fallback is needed for this package's dependencies. No dependency is vendored: the package carries instructions and vendored helper scripts only, and the scripts import the environment's libraries.

## The office/ shared subtree

`scripts/office/` (50 files) is the Office subtree shared verbatim by the upstream docx/pptx/xlsx packages: the XSD schema library under `scripts/office/schemas/`, the validators under `scripts/office/validators/` and `scripts/office/helpers/`, and the soffice wrapper. This package vendors its own byte-identical copy so it stays independently installable — no dependency on sibling skill directories — and `tests/test_office_subtree_parity.py` pins every file against the import-review appendix A office section. The subtree's Python files import only the standard library plus `defusedxml` and `lxml` above.

## Fail-closed boundary

Fail closed per operation, not per machine: a Create script needs Node and the npm `docx` library only; the Edit track needs Python with `defusedxml` (through `merge_runs.py` and `comment.py`) and `zip`, plus `lxml` when the XSD validator runs; the Verify track needs LibreOffice, `zip` and `pdftoppm`; accepting tracked changes and converting legacy `.doc` files need LibreOffice; reading content needs `pandoc`. A missing dependency stops that operation with a named hold naming the requirement and its verify command. The upstream's own repair for the npm library — `npm install docx` in the working project — runs only on explicit request. Do not fall back to a different library, an untested CLI substitution, or a partial install, and do not silently skip a declared verification step.

## Vendored script inventory

Fifty-nine files vendored byte-identical under `scripts/` (digests in [provenance.md](provenance.md) and the office parity test): the three top-level helpers `accept_changes.py`, `comment.py`, `merge_runs.py` plus `scripts/__init__.py`, the five comment templates under `scripts/templates/`, and the 50-file `scripts/office/` subtree. Run the top-level scripts from this package's `scripts/` directory (or with it on `sys.path` — they import the sibling `office` package, which Python resolves from the script's own directory). Verified CLI behavior (2026-11-19): the four argparse CLIs (`merge_runs.py`, `comment.py`, `accept_changes.py`, `scripts/office/validate.py`) print usage and exit 2 on missing arguments and handle `--help` with exit 0; `merge_runs.py`, `comment.py` and `office/validate.py` additionally exit 1 on input errors they guard (bad path, non-docx input, bad zip); `accept_changes.py` exits 1 when its result message contains "Error". `scripts/office/soffice.py` is a library module with a thin `__main__` passthrough: it forwards argv to the `soffice` binary and exits with soffice's own return code, has no argument guard and no `--help`, and on a machine without LibreOffice it crashes with a traceback and exit 1 (observed, 2026-11-19) — read its output rather than trusting the exit code alone.

## Upgrade

1. Resolve the newest official state of `anthropics/skills` and pin an immutable commit per the stable-source rules in [docs/skill-standard.md](../../../docs/skill-standard.md) §1.2.
2. Re-fetch `skills/docx/` at that commit, re-verify every per-file SHA-256 against the upstream, and record the new digests in [provenance.md](provenance.md) and `tests/test_super_docx.py` together. The office/ subtree must stay byte-identical to the upstream pptx/xlsx copies — re-run the shared-subtree check described in the import review §5.
3. Reconcile the frozen guide body and the vendored scripts with this package; if the upstream Dependencies line or the preinstalled wording changes, fold it into the table above and record the delta in [provenance.md](provenance.md).
4. Refresh the license copy and the third-party notice when the upstream LICENSE.txt bytes change; if the placeholder copyright line is ever filled in upstream, re-run the R1 attribution ruling recorded in the [import review](../../../docs/research/2026-11-18-anthropics-skills-import-review.md) before syncing.
5. Run the skill validator and `python scripts/verify.py` before promotion.
