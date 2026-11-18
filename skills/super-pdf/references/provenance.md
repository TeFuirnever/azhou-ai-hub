# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Pdf-Apache-2.0.txt](../../../LICENSES/Pdf-Apache-2.0.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/anthropics/skills` |
| Immutable commit | `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` |
| Upstream path | `skills/pdf` (12 blobs, 68,603 B) |
| Upstream SKILL.md SHA-256 | `d1c7caf5f35eb7d37877dd7fc33a095037be2b34fb5d2f7f4d43bde3165bb4ee` |
| Embedded body SHA-256 | `cccf2463a0d964fa7f619feea772f4364e90af87e18c23d6003596f0cf71ab61` (everything below the upstream `# PDF Processing Guide` title, as embedded in this package's SKILL.md) |
| Upstream LICENSE.txt SHA-256 | `58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd` |
| License | Apache-2.0 (repository-level license field empty; upstream README L20 at the pinned commit declares the document skills "also open source (Apache 2.0)"; each package carries its own LICENSE.txt) |
| Per-file digests | appendix A of the [2026-11-18 import review](../../../docs/research/2026-11-18-anthropics-skills-import-review.md) — the single pinning source for this vendor manifest |

Vendored byte-identical from the pinned commit: `FORMS.md` (`d5df5757…`), `REFERENCE.md` (`07af9a8f…`), and the eight scripts under `scripts/` (`check_bounding_boxes.py 0ced5224…`, `check_fillable_fields.py 1fe10b99…`, `convert_pdf_to_images.py 7f58e292…`, `create_validation_image.py 8fa9fd79…`, `extract_form_field_info.py bb235b36…`, `extract_form_structure.py 6814e3fe…`, `fill_fillable_fields.py d140872c…`, `fill_pdf_form_with_annotations.py 8a56e063…`). The upstream `SKILL.md` body (below its title) is embedded verbatim in this package's SKILL.md; the upstream `LICENSE.txt` is retained as the byte-identical repository copy above. Nothing else from the upstream repository is vendored.

## Adoption basis and rulings

Adoption rides the 2026-11-18 import review (docskills-U0, merged as the frozen record cited above). Its maintainer rulings bind this package:

- **R1 (Apache-2.0 §4(a) attribution): accepted.** Its three conditions are implemented here: the LICENSE.txt copy is byte-identical including the placeholder copyright line; the repository THIRD_PARTY_NOTICES names "Anthropic PBC, from anthropics/skills @ e4bb5d960d…, Apache-2.0"; and the placeholder-line anomaly is recorded below. If the upstream ever corrects the copyright line, the stable-source rules require re-ruling before syncing.
- **R2 (format set and order):** pdf is the first of the four document-format adoptions (pdf → docx → xlsx → pptx).
- **§9 dependency contract:** the upstream declares no Dependencies section; library names sit in section titles ("Python Libraries", "Command-Line Tools"), one inline `# Requires:` comment, and the FORMS.md zoom-crop recipe naming ImageMagick. The full runtime dependency surface (including Pillow, which the upstream SKILL.md never declares although `create_validation_image.py` imports it) is carried by [setup.md](setup.md) under a fail-closed contract.

## Placeholder copyright-line anomaly

The retained Apache-2.0 license copy keeps the upstream appendix line `Copyright [yyyy] [name of copyright owner]` — an unfilled template placeholder, unique to the four document packages (docx/pdf/pptx/xlsx share this byte variant; the two tool packages carry `Copyright 2026 Anthropic, PBC.`). Per R1, the line is preserved byte-identical rather than filled in; retention of the verbatim LICENSE.txt performs the §4(a) attribution together with the repository notice naming Anthropic PBC and the pinned commit.

## Azhou-maintained adaptation

The upstream capability is preserved in full: the guide body verbatim, FORMS.md, REFERENCE.md and all eight scripts byte-identical. The local layer only repackages:

- narrows frontmatter to the neutral `name`, `description`, `invocation` contract: the upstream host-specific `license: Complete terms in LICENSE.txt` key is dropped (the license travels as the retained byte-identical copy and notice, not as frontmatter), `invocation: model-invoked discipline` classifies the "use whenever a task touches PDF files" trigger surface, and the upstream `name: pdf` survives as a compatibility trigger named in the description;
- translates the description while preserving the upstream trigger surface verbatim in substance: reading or extracting text/tables, combining or merging, splitting apart, rotating pages, adding watermarks, creating new PDFs, filling PDF forms, encrypting/decrypting, extracting images, OCR on scanned PDFs to make them searchable, and the closing conditional sentence "If the user mentions a .pdf file or asks to produce one, use this skill.";
- adds the fail-closed dependency setup ([setup.md](setup.md)) — the upstream assumes its libraries are preinstalled and declares no dependency surface; the delta list is below;
- adds the Azhou identity, stage language, status dictionary and stable receipt ([brand-layer.md](brand-layer.md)), and the four-constraint Azhou boundary in the entry (fail-closed per operation, named-file mutations only, no evidence creation, no machine-local absolute paths);
- adds no capability carve sentence: no canonical package overlaps the PDF file-operation surface (every canonical description was read and judged at adoption, 2026-11-18 — the nearest neighbors are artifact producers with their own formats: super-excalidraw-diagram exports SVG/PNG scenes, super-archify delivers HTML diagram maps, super-imagegen generates raster images from its private runtime, and none reads, writes or converts PDF files; no neighbor's description mentions PDF).

## Preinstalled → fail-closed delta

The upstream text is unchanged; this list records where the local layer replaces an unstated preinstalled assumption with an explicit fail-closed gate, so the delta stays auditable:

1. Upstream SKILL.md section titles "## Python Libraries" / "## Command-Line Tools" name pypdf, pdfplumber, reportlab, pytesseract (with pdf2image), poppler-utils (`pdftotext`, `pdfimages`), qpdf and pdftk "(if available)" as available tools → [setup.md](setup.md) requires each to be verified before the operation that needs it, with a named hold on absence.
2. Upstream's only inline dependency comment `# Requires: pip install pytesseract pdf2image` (OCR recipe) → same two requirements plus the `tesseract` binary and poppler backend, verified as commands.
3. `scripts/create_validation_image.py` imports Pillow with no upstream declaration anywhere in SKILL.md → declared in [setup.md](setup.md) (recorded in the U0 §9 contract as an undeclared upstream dependency).
4. `scripts/extract_form_structure.py` imports pdfplumber, which the upstream guide uses only in its extraction recipes → declared as a FORMS.md structure-extraction dependency too.
5. REFERENCE.md's pypdfium2 and Node (`pdf-lib`, `pdfjs-dist`) tracks and the guide's pandas example → recorded as recipe-level optional dependencies rather than assumed installs.
6. `FORMS.md` Approach B.3's zoom-crop refinement names ImageMagick (`magick`, falling back to `convert`) as an assumed install → declared as a recipe-level dependency in [setup.md](setup.md), verified before the recipe with a named hold on absence.

These are packaging gates, not capability changes: every recipe, script and doc keeps its upstream bytes, and no operation gains or loses a step.

## Showcase and visual deferral

No showcase scene or README visual digit has landed with this adoption; both are deferred to a dedicated maintainer visual pass, per the #478 deferral precedent: the skill-standard §4 showcase (an `assets/skills/super-pdf-effect.png` from the governed azhou-scenes pipeline with a named human visual P0) and the README hero/banner 16→17 digit redraw (a deterministic text-layer edit pending that pass). Until that pass lands, the READMEs carry the catalog row and install command without a showcase section, and the hero/banner artwork keeps its existing digits. This deferral is recorded here and in the CHANGELOG entry; it is not a completed visual approval.

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/anthropics/skills/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/pdf/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `d1c7caf5f35eb7d37877dd7fc33a095037be2b34fb5d2f7f4d43bde3165bb4ee`.

On platforms without `shasum` (e.g. Windows), the standard-library equivalent:

```bash
curl -fsSL https://raw.githubusercontent.com/anthropics/skills/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/pdf/SKILL.md \
  | python -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
```

License copy check against the retained file:

```bash
curl -fsSL https://raw.githubusercontent.com/anthropics/skills/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/pdf/LICENSE.txt \
  | shasum -a 256
```

Expected SHA-256: `58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd`, byte-identical to [Pdf-Apache-2.0.txt](../../../LICENSES/Pdf-Apache-2.0.txt).

## Fidelity classification

Classification: `faithful` — the upstream capability is preserved in full (guide body verbatim below the entry, FORMS.md, REFERENCE.md and eight scripts byte-identical at the pinned commit) and the local layer only repackages: neutral frontmatter with the `license:` key dropped and the upstream name kept as a compatibility trigger, the fail-closed dependency setup replacing unstated preinstalled assumptions (delta auditable above), the Azhou interaction layer, and the four-constraint boundary. No recipe is rewritten, extended or removed, and no capability route is added or dropped. Skill-standard §2.3.

## Known upstream defects (observed 2026-11-19, not patched)

Four defects were found by the PR #512 codex review inside the vendored upstream scripts. They are recorded here and deliberately not patched: the vendored bytes stay pinned byte-identical to the appendix A digests and the classification stays `faithful`, so a local patch would fork the package from its immutable source. Each is a candidate for the stable-source update path (skill-standard §1.2: re-pin after upstream review) or an upstream contribution, whichever lands first; none is fixed locally.

- `scripts/extract_form_field_info.py` — choice options that are plain strings are unpacked per character (`['US', 'CA']` yields `U` and `C`; a one-character option raises `IndexError`) instead of being normalized to value/text pairs (review thread 4614734511).
- `scripts/extract_form_field_info.py` — terminal fields whose `/Kids` are separate widgets are dropped by the unconditional `continue` on non-radio fields with `/Kids`, so extraction returns no entry for a supported PDF representation and `fill_fillable_fields.py` then rejects their IDs (review thread 4614734518).
- `scripts/check_bounding_boxes.py` — the image-coordinate workflow compares `entry_height` in pixels against `font_size` in PDF points, so undersized entries pass the mandatory pre-fill check and risk clipped text after unit conversion in the fill script (review thread 4617515945).
- `scripts/fill_pdf_form_with_annotations.py` — a non-zero `/MediaBox` origin is not preserved when transforming image-coordinate boxes to annotation rectangles, shifting placed text on cropped pages such as those produced by the REFERENCE.md cropping recipe (review thread 4618441784).
