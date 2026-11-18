# Dependencies and setup

Read this before the first PDF operation on a machine, or whenever a recipe, a vendored script, or a CLI tool named by the guide fails.

The upstream skill ships no dependency manifest: it declares libraries inline (section titles under "Python Libraries" and "Command-Line Tools", one `# Requires:` comment in the OCR recipe) and assumes they are already installed. This package does not assume. Every dependency below is named with what consumes it, how to verify it, and the failure boundary.

## Runtime dependencies

| Requirement | Consumed by | Verify |
|---|---|---|
| Python 3.11+ | all vendored `scripts/*.py` | `python --version` |
| `pypdf` | merge/split/rotate/watermark/encrypt recipes; `scripts/check_fillable_fields.py`, `scripts/extract_form_field_info.py`, `scripts/fill_fillable_fields.py`, `scripts/fill_pdf_form_with_annotations.py` | `python -c "import pypdf; print(pypdf.__version__)"` |
| `pdfplumber` | text/table extraction recipes; `scripts/extract_form_structure.py` (FORMS.md structure-first approach) | `python -c "import pdfplumber; print(pdfplumber.__version__)"` |
| `pdf2image` | `scripts/convert_pdf_to_images.py`; OCR recipe (page rasterization) | `python -c "import pdf2image; print(pdf2image.__version__)"` |
| Pillow | `scripts/create_validation_image.py` (FORMS.md visual-estimation overlay) — **not declared anywhere in the upstream SKILL.md**, only imported by the script; declared here | `python -c "from PIL import Image; import PIL; print(PIL.__version__)"` |
| `reportlab` | create-PDF recipes (Canvas, Platypus) | `python -c "import reportlab; print(reportlab.Version)"` |
| `pytesseract` + the `tesseract` binary | OCR recipe for scanned PDFs | `python -c "import pytesseract; print(pytesseract.get_tesseract_version())"` |
| poppler-utils (`pdftotext`, `pdftoppm`, `pdfimages`) | command-line extraction recipes; `pdfimages` image extraction; `pdftoppm` is also the backend `pdf2image` shells out to | `pdftotext -v` and `pdfimages -v` and `pdftoppm -v` |
| `qpdf` | command-line merge/split/rotate/decrypt recipes | `qpdf --version` |
| `pdftk` (optional; upstream marks it "if available") | command-line merge/split/rotate alternatives | `pdftk --version` — absent means use the qpdf or pypdf paths, never a hold |

Recipe-level optional dependencies, needed only by the recipes that name them:

- `pandas` (plus an Excel engine such as `openpyxl` for `to_excel`) — the "Advanced Table Extraction" recipe in the guide.
- `pypdfium2` and `numpy` — the REFERENCE.md advanced track (render/extract with pypdfium2; its image-extraction recipe imports numpy).
- Node.js libraries `pdf-lib` and `pdfjs-dist` — the REFERENCE.md JavaScript track; they are project-level npm dependencies of whatever JavaScript program uses them, not Python installs.
- Node.js libraries `pdf-lib` and `pdfjs-dist` — the REFERENCE.md JavaScript track; they are project-level npm dependencies of whatever JavaScript program uses them, not Python installs.

No dependency is vendored: the package carries instructions and vendored helper scripts only, and the scripts import the environment's libraries.

## Fail-closed boundary

Fail closed per operation, not per machine: a merge needs `pypdf` only; OCR needs `pytesseract`, `tesseract`, `pdf2image` and poppler; form filling needs `pypdf` or `pdfplumber` per the FORMS.md approach; a missing dependency stops that operation with a named hold naming the requirement and its verify command. Do not fall back to a different library, an untested CLI substitution, or a partial install, and do not silently skip a declared verification step.

## Vendored script inventory

Eight scripts vendored byte-identical from the pinned upstream commit (digests in [provenance.md](provenance.md)): `check_bounding_boxes.py`, `check_fillable_fields.py`, `convert_pdf_to_images.py`, `create_validation_image.py`, `extract_form_field_info.py`, `extract_form_structure.py`, `fill_fillable_fields.py`, `fill_pdf_form_with_annotations.py`. Run them from this package's `scripts/` directory (or with it on `sys.path` — `fill_fillable_fields.py` imports its sibling `extract_form_field_info`); each prints its own usage with `--help` where applicable and reports its exit status honestly.

## Upgrade

1. Resolve the newest official state of `anthropics/skills` and pin an immutable commit per the stable-source rules in [docs/skill-standard.md](../../../docs/skill-standard.md) §1.2.
2. Re-fetch `skills/pdf/` at that commit, re-verify every per-file SHA-256 against the upstream, and record the new digests in [provenance.md](provenance.md) and `tests/test_super_pdf.py` together.
3. Reconcile the frozen guide body, FORMS.md, REFERENCE.md and scripts with this package; if the upstream adds a Dependencies section, fold it into this table and record the delta.
4. Refresh the license copy and the third-party notice when the upstream LICENSE.txt bytes change; if the placeholder copyright line is ever filled in upstream, re-run the R1 attribution ruling recorded in the [import review](../../../docs/research/2026-11-18-anthropics-skills-import-review.md) before syncing.
5. Run the skill validator and `python scripts/verify.py` before promotion.
