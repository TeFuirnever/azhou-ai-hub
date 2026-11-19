# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Docx-Apache-2.0.txt](../../../LICENSES/Docx-Apache-2.0.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/anthropics/skills` |
| Immutable commit | `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` |
| Upstream path | `skills/docx` (61 blobs, 1,166,158 B) |
| Upstream SKILL.md SHA-256 | `895d5aa6c4cd98e4aed4c995d846f056f3549086e79bcd6617afea6014f82288` |
| Embedded body SHA-256 | `db55bfac2feea71c98ee174199b51d9664667a37162f1ee0ae5b9a76e0ba0ea0` (everything below the upstream `# DOCX creation, editing, and analysis` title, as embedded in this package's SKILL.md) |
| Upstream LICENSE.txt SHA-256 | `58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd` |
| License | Apache-2.0 (repository-level license field empty; upstream README L20 at the pinned commit declares the document skills "also open source (Apache 2.0)"; each package carries its own LICENSE.txt) |
| Per-file digests | appendix A of the [2026-11-18 import review](../../../docs/research/2026-11-18-anthropics-skills-import-review.md) — the single pinning source for this vendor manifest |

Vendored byte-identical from the pinned commit (appendix A pins): `scripts/__init__.py` (`01ba4719…`), `scripts/accept_changes.py` (`0c991d2b…`), `scripts/comment.py` (`37d116e5…`), `scripts/merge_runs.py` (`3ab367fd…`), and the five comment templates `scripts/templates/comments.xml` (`a08ba83e…`), `commentsExtended.xml` (`544eeecf…`), `commentsExtensible.xml` (`bad10b32…`), `commentsIds.xml` (`db20f961…`), `people.xml` (`056f63aa…`). The 50-file `scripts/office/` shared subtree (helpers, validators, soffice wrapper and the XSD schema library; 50 blobs, 1,109,154 B) is vendored byte-identical as this package's own copy and pinned file-by-file by `tests/test_office_subtree_parity.py` against the same appendix A office section (the upstream docx/pptx/xlsx copies are byte-identical, import review §5). The upstream `SKILL.md` body (below its title) is embedded verbatim in this package's SKILL.md; the upstream `LICENSE.txt` is retained as the byte-identical repository copy above. Nothing else from the upstream repository is vendored.

## Adoption basis and rulings

Adoption rides the 2026-11-18 import review (docskills-U0, merged as the frozen record cited above). Its maintainer rulings bind this package:

- **R1 (Apache-2.0 §4(a) attribution): accepted.** Its three conditions are implemented here: the LICENSE.txt copy is byte-identical including the placeholder copyright line; the repository THIRD_PARTY_NOTICES names "Anthropic PBC, from anthropics/skills @ e4bb5d960d…, Apache-2.0"; and the placeholder-line anomaly is recorded below. If the upstream ever corrects the copyright line, the stable-source rules require re-ruling before syncing.
- **R2 (format set and order):** docx is the second of the four document-format adoptions (pdf → docx → xlsx → pptx).
- **§9 dependency contract:** unlike pdf, the upstream docx SKILL.md carries a real Dependencies section — one line declaring `docx` (npm, "preinstalled — install only if `require('docx')` fails"), `pandoc`, LibreOffice (`soffice`) and `pdftoppm` (Poppler) — plus a runtime preinstalled note in the Creating section ("`docx` is preinstalled — do not run `npm install` first … Only if that require fails: `npm install docx`"). That declared surface misses the script-side imports `defusedxml` (eight files) and `lxml` (three validator files, recorded in the import review §3), the `zip` binary the recipes shell out to, and the Node runtime the npm library implies. The full runtime dependency surface is carried by [setup.md](setup.md) under a fail-closed contract; the delta list is below.

## Placeholder copyright-line anomaly

The retained Apache-2.0 license copy keeps the upstream appendix line `Copyright [yyyy] [name of copyright owner]` — an unfilled template placeholder, unique to the four document packages (docx/pdf/pptx/xlsx share this byte variant; the two tool packages carry `Copyright 2026 Anthropic, PBC.`). Per R1, the line is preserved byte-identical rather than filled in; retention of the verbatim LICENSE.txt performs the §4(a) attribution together with the repository notice naming Anthropic PBC and the pinned commit.

## Azhou-maintained adaptation

The upstream capability is preserved in full: the guide body verbatim and all 59 vendored script/template files byte-identical (the 50-file office/ subtree included). The local layer only repackages:

- narrows frontmatter to the neutral `name`, `description`, `invocation` contract: the upstream host-specific `license: Complete terms in LICENSE.txt` key is dropped (the license travels as the retained byte-identical copy and notice, not as frontmatter), `invocation: model-invoked discipline` classifies the "use this skill whenever the user wants to create, read, edit, or manipulate Word documents" trigger surface, and the upstream `name: docx` survives as a compatibility trigger named in the description;
- translates the description while preserving the upstream trigger surface verbatim (create/read/edit/manipulate .docx and .dotx; the 'Word doc' / 'word document' / '.docx' / '.dotx' keyword list; professional formatting with tables of contents, headings, page numbers, letterheads; extracting or reorganizing content, inserting or replacing images, find-and-replace, tracked changes and comments, converting content into a polished Word document; the report/memo/letter/template deliverable sentence; and the closing exclusion "Do NOT use for PDFs, spreadsheets, Google Docs, or general coding tasks unrelated to document generation."), plus the capability carve sentence below;
- adds the fail-closed dependency setup ([setup.md](setup.md)) replacing the upstream's preinstalled assumptions — the delta list is below;
- wraps the embedded body in a `frozen-upstream` HTML-comment marker pair (wrapper bytes, outside the digest-bound body): the upstream guide's own extraction recipe invokes a POSIX-only versioned python interpreter, which the repository command-surface gate rejects in Hub guidance; the markers delimit vendored upstream bytes from this wrapper for that gate, mirroring its existing `references/upstream/` frozen-docs exemption, with negative-control tests keeping the gate strict outside the markers;
- adds the Azhou identity, stage language, status dictionary and stable receipt ([brand-layer.md](brand-layer.md)), and the four-constraint Azhou boundary in the entry (fail-closed per operation, named-file mutations only, no evidence creation, no machine-local absolute paths).

## Capability carve (bidirectional with super-pdf, judged 2026-11-19)

Every canonical description in the catalog (all seventeen existing packages plus this one) was read and compared against this package's Word document delivery face before adoption completed, 2026-11-19.

- **super-pdf — overlap found, carved both ways (i-have-adhd precedent).** The upstream docx verify recipe produces a PDF from the Word document (`scripts/office/soffice.py --headless --convert-to pdf`), and a "convert this Word document to PDF" request names a .pdf deliverable, which super-pdf's closing conditional ("If the user mentions a .pdf file or asks to produce one, use this skill.") also claims. Both descriptions now carry a carve sentence: this package's description ends with "Use when converting a Word document to PDF (soffice path); PDF-internal work belongs to super-pdf." and super-pdf's description (local layer, its frozen guide untouched) gains the reverse sentence "Producing a PDF from a Word document belongs to super-docx." The Word side keeps every document-delivery face; the PDF side keeps operations on existing PDFs. This supersedes super-pdf's 2026-11-18 no-carve judgment, which was accurate for the catalog that existed then (no package touched Word documents or Word→PDF conversion); its provenance records this dated supersession.
- **Nearest neighbors judged, no carve:** super-lavish names "report" among its explicitly HTML artifacts while this skill's report face is qualified "as a Word or .docx file" — the artifact type separates them, no carve needed; super-arch-doc authors architecture/PRD document content and names no Word or .docx output (this skill handles the Word file face if one is requested); super-imagegen generates raster images but does not insert or replace them in documents; super-excalidraw-diagram (SVG/PNG scenes), super-archify (HTML diagram maps), super-eli5 (self-contained HTML explainer) deliver their own artifact formats with no Word claim. The Foundation four, super-ask-azhou, super-asd-ste100, super-gh-axi, super-i-have-adhd, super-repo-pedant and super-session-insights describe hub operations, controlled-English rewriting, GitHub operations, output shaping, closeout and session analysis — no description mentions Word documents or .docx/.dotx files.

## Preinstalled → fail-closed delta

The upstream text is unchanged; this list records where the local layer replaces an unstated or "preinstalled" assumption with an explicit fail-closed gate, so the delta stays auditable:

1. Upstream Creating note "`docx` is preinstalled — do not run `npm install` first; write the script and `require('docx')` directly. Only if that require fails: `npm install docx`." → [setup.md](setup.md) requires the `require('docx')` probe (plus a Node runtime check the upstream never names) before the create track; absent → named hold, and the upstream's own `npm install docx` repair runs only on explicit request.
2. Upstream Dependencies line "`docx` (npm, preinstalled — install only if `require('docx')` fails) · `pandoc` · LibreOffice (`soffice`) · `pdftoppm` (Poppler)" → each of the four declared tools is verified per operation with a named hold on absence.
3. Script-side imports with no upstream declaration anywhere in SKILL.md: `defusedxml` (eight vendored files) and `lxml` (three validator files) → declared in [setup.md](setup.md) with probes (import review §3 recorded both as undeclared upstream).
4. The recipes' `zip` binary (verify track `zip -d`, edit track `zip -XrDy`) — undeclared upstream → declared as a recipe-level dependency in [setup.md](setup.md).
5. The Node runtime implied by the npm `docx` library — undeclared upstream → declared in [setup.md](setup.md) with `node --version`.

These are packaging gates, not capability changes: every recipe, script and doc keeps its upstream bytes, and no operation gains or loses a step.

## Showcase and visual deferral

No showcase scene or README visual digit has landed with this adoption; both stay deferred to the dedicated maintainer visual pass per the #478 deferral precedent that super-pdf also rode: the skill-standard §4 showcase (an `assets/skills/super-docx-effect.png` from the governed azhou-scenes pipeline with a named human visual P0) and the README hero/banner digit redraw. The pending redraw is merged into one future pass: 16→17 (owed since the Super Pdf adoption) together with 17→18 from this adoption. Until that pass lands, the READMEs carry the catalog row and install command without a showcase section, and the hero/banner artwork and its alt-text digits keep their existing landed state. This deferral is recorded here and in the CHANGELOG entry; it is not a completed visual approval.

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/anthropics/skills/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/docx/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `895d5aa6c4cd98e4aed4c995d846f056f3549086e79bcd6617afea6014f82288`.

On platforms without `shasum` (e.g. Windows), the standard-library equivalent:

```bash
curl -fsSL https://raw.githubusercontent.com/anthropics/skills/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/docx/SKILL.md \
  | python -c "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"
```

License copy check against the retained file:

```bash
curl -fsSL https://raw.githubusercontent.com/anthropics/skills/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/docx/LICENSE.txt \
  | shasum -a 256
```

Expected SHA-256: `58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd`, byte-identical to [Docx-Apache-2.0.txt](../../../LICENSES/Docx-Apache-2.0.txt).

## Fidelity classification

Classification: `faithful` — the upstream capability is preserved in full (the guide body verbatim below the entry, all 59 vendored script/template files byte-identical at the pinned commit, the 50-file office/ subtree included and parity-pinned) and the local layer only repackages: neutral frontmatter with the `license:` key dropped and the upstream name kept as a compatibility trigger, the fail-closed dependency setup replacing preinstalled assumptions (delta auditable above), the bidirectional capability carve with super-pdf, the Azhou interaction layer, and the four-constraint boundary. No recipe is rewritten, extended or removed, and no capability route is added or dropped beyond the carve sentence. Skill-standard §2.3.

## Known upstream defects (observed 2026-11-19, not patched)

One defect was found inside the vendored upstream scripts — surfaced by the repository's issue-#287 subprocess-encoding guard when the adoption first landed the bytes. It is recorded here and deliberately not patched: the vendored bytes stay pinned byte-identical to the appendix A digests and the classification stays `faithful`, so a local patch would fork the package from its immutable source. It is a candidate for the stable-source update path (skill-standard §1.2: re-pin after upstream review) or an upstream contribution, whichever lands first; none is fixed locally.

- `scripts/accept_changes.py` — line 68 runs the LibreOffice accept macro through `subprocess.run(…, capture_output=True, text=True, timeout=30, …)` with no pinned `encoding`, so on hosts whose default encoding is not UTF-8 (the exact corruption class issue #287 fixed for repository-owned code) the captured soffice output can decode incorrectly; the repository guard exempts this byte-pinned vendored tree per its own scope statement, and the exemption is explicit in `tests/test_subprocess_encoding.py` (`VENDORED_SCRIPT_ROOTS`).

The observed `office/soffice.py` crash-with-traceback when the `soffice` binary is absent is an environment-absence failure mode, recorded as such in [setup.md](setup.md), not a defect entry. The rest of the adoption verification scope (61/61 blob digest pinning, AST import scan of every vendored Python file, and live CLI probes of argument handling, `--help` and exit codes for the four argparse CLIs plus `office/soffice.py`, 2026-11-19) surfaced no further defect.
