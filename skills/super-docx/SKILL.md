---
name: super-docx
description: "Azhou skill. Adopted from the upstream docx skill (upstream name still triggers). Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files) or Word templates (.dotx files). Triggers include: any mention of 'Word doc', 'word document', '.docx', '.dotx', or requests to produce professional documents with formatting like tables of contents, headings, page numbers, or letterheads. Also use when extracting or reorganizing content from .docx or .dotx files, inserting or replacing images in documents, performing find-and-replace in Word files, working with tracked changes or comments, or converting content into a polished Word document. If the user asks for a 'report', 'memo', 'letter', 'template', or similar deliverable as a Word or .docx file, use this skill. Do NOT use for PDFs, spreadsheets, Google Docs, or general coding tasks unrelated to document generation. Use when converting a Word document to PDF (soffice path); PDF-internal work belongs to super-pdf."
invocation: model-invoked discipline
---

# Super Docx

Super Docx is the Word document discipline for agents: whenever a task touches Word documents or templates — creating new files with docx-js, unpack-edit-rezip editing, reading content via pandoc, comments, tracked changes, or soffice-verified rendering — the frozen upstream guide below is the recipe source, the vendored scripts under `scripts/` are its mechanical helpers (including the shared Office validator subtree under `scripts/office/`), and dependencies are verified fail-closed before an operation runs.

**🦊 阿舟 · Docx**

> 先验依赖，再动这份 Word 文档。

Invocation class: model-invoked discipline, declared in frontmatter; the axis and its semantics are defined once in `docs/skill-standard.md` §2.2 — reached autonomously whenever a task touches Word documents, no explicit naming required. Orchestrators may point here; this skill orchestrates nothing and calls no orchestrator.

## Brand protocol

Emit once when the skill starts, before any tool call:

```text
🦊 阿舟 · Docx 启动（mode=<create|edit|read|markup>, scope=<word-task>）
```

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1 chat presentation). Peeling the leading `>` and paired `**` must restore the protocol line. Headless, CI logs, receipts, and machine fields stay protocol-only.

Use `✅ 验证通过` only after the named checks actually ran. Use `❌ 验证失败` when this attempt fails and name one repair action, and `🔒 阿舟暂停这一项` when input, permission, or a dependency is missing. Emoji is display-only: keep it out of JSON keys, schema values, digests, paths, commands, test names, and raw evidence. A host without Unicode may strip the leading emoji while preserving the fixed text, the `（k=v, k=v）` field grouping, fields, and values. Raw evidence stays out of receipts unless the user supplied it. Stage events, the status dictionary, and the stable receipt are defined in the [Azhou interaction layer](references/brand-layer.md).

## Dependencies fail closed

Read [setup](references/setup.md) before the first Word document operation on a machine, or whenever a dependency has not been verified yet. The upstream guide below says the npm `docx` library is preinstalled and compresses the rest into one Dependencies line (pandoc, LibreOffice, pdftoppm); this package assumes none of them: every dependency — including the script-side `defusedxml` and `lxml` imports the upstream never declares — is named with a verification command in [setup](references/setup.md), and a missing one stops the affected operation with a named hold — never a silent tool substitution, never a partial install. The vendored helper scripts in `scripts/` (including `scripts/office/`) run under the same contract.

## Frozen upstream guide

The text below is the upstream `docx` skill's SKILL.md body, frozen verbatim at the immutable commit recorded in [provenance](references/provenance.md): everything below the upstream `# DOCX creation, editing, and analysis` title. The upstream frontmatter is replaced by this package's neutral frontmatter and nothing else is paraphrased, extended, or trimmed; the Azhou boundary after the guide appends constraints and never overrides this text. The frozen-upstream marker pair below delimits the vendored bytes from this wrapper for the repository command-surface gate.

<!-- frozen-upstream:begin -->

A `.docx` is a ZIP archive of XML files. Choose your approach by task:

| Task | Approach |
|---|---|
| **Create** a new document | Write a `docx` (npm) script — see gotchas below |
| **Edit** an existing document | unpack → edit `word/document.xml` → `zip` (docx-js cannot open existing files) |
| **Read** content | `pandoc -t markdown file.docx` |

> Script paths below are relative to this skill's directory.

## Creating with docx-js — gotchas

`docx` is preinstalled — do not run `npm install` first; write the script and `require('docx')` directly. Only if that require fails: `npm install docx`. The model knows the API; these are the footguns:

- **Page size defaults to A4.** For US Letter set `page: { size: { width: 12240, height: 15840 } }` (DXA; 1440 = 1″).
- **Landscape:** pass portrait dimensions and `orientation: PageOrientation.LANDSCAPE` — docx-js swaps width/height internally.
- **Tables need dual widths:** set `columnWidths` on the table AND `width` on every cell, both in `WidthType.DXA` (PERCENTAGE breaks in Google Docs). Column widths must sum to the table width.
- **Table shading:** use `ShadingType.CLEAR`, never `SOLID` (renders black).
- **Lists:** never insert `•` literally; use a `numbering` config with `LevelFormat.BULLET`.
- **`ImageRun` requires `type:`** (`"png"`, `"jpg"`, …).
- **`PageBreak` must be inside a `Paragraph`.**
- **Never use `\n`** — use separate `Paragraph` elements.
- **Headings:** style every level you use (`title`, `heading1`, `heading2`…) in `styles.default`: `heading1: { run: { font: "Arial", size: 32, bold: true }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true } }`. Every level needs its own font (even with a document default), `before` and `after` (even if 0) and `keepNext`: the built-in styles set none of them.
- **TOC:** headings must use built-in `HeadingLevel.*`; custom heading styles need `outlineLevel` set or they won't appear.
- **Don't use a table as a horizontal rule** — use a paragraph bottom border instead.
- **Dot-leader / right-aligned-on-same-line:** use `PositionalTab` (`alignment: PositionalTabAlignment.RIGHT`, `leader: PositionalTabLeader.DOT`) inside a `TextRun`, not literal `.` or space padding.

## Verify the output

After writing a `.docx`, render it and look at it:

```bash
zip -d output.docx '*/' >/dev/null || true   # drop the ZIP's folder entries: Word has refused a file that has them when opened through a cloud co-editing service
python scripts/office/soffice.py --headless --convert-to pdf output.docx
pdftoppm -jpeg -r 100 output.pdf page
ls page-*.jpg   # then Read the images
```

`pdftoppm` zero-pads page numbers to the width of the page count (`page-01.jpg`…`page-12.jpg`).

## Editing existing documents

Legacy `.doc` files must be converted first: `python scripts/office/soffice.py --headless --convert-to docx file.doc`.

```bash
python3 -c "import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall('unpacked')" doc.docx   # not unzip, which restores symlinks — docx from external parties is untrusted
python scripts/merge_runs.py unpacked/   # coalesce fragmented runs so text is findable
# edit unpacked/word/document.xml in place — do NOT reformat or pretty-print
(cd unpacked && rm -f ../out.docx && zip -XrDy ../out.docx .)
python scripts/office/validate.py out.docx --original doc.docx   # XSD checks; --auto-repair fixes common issues
# redlining? add --author "<the name you redlined under>" to check every edit is tracked
```

Word splits text across many `<w:r>` runs (revision ids, spell-check markers), so a phrase you can see in the document often doesn't exist as a contiguous string in the XML. `merge_runs.py` merges adjacent identically-formatted runs in `word/document.xml` without changing content or rendering; it also accepts a `.docx` directly (`python scripts/merge_runs.py doc.docx -o merged.docx`).

**Tracked changes:** when redlining, validate with `--author "<the name you redlined under>"` (needs `--original`) — it reports any text you changed without a `<w:ins>`/`<w:del>` around it, which is easy to do by accident and invisible in the accepted view. Wrap runs in `<w:ins>`/`<w:del>` with `w:id`, `w:author`, `w:date` attributes. Inside `<w:del>`, the text element is `<w:delText>`, not `<w:t>`. A deleted paragraph mark (`<w:pPr><w:rPr><w:del w:id=".." w:author=".." w:date=".."/></w:rPr></w:pPr>`) means "merge this paragraph into the next" — so deleting a paragraph outright is that plus a `<w:del>` around every run. The `<w:del/>` must come before the rPr's other children; their order is schema-enforced.

To produce a clean copy with all tracked changes accepted: `python scripts/accept_changes.py in.docx out.docx`.

Accepting a deleted paragraph mark should join that paragraph to the one below it, so a paragraph whose runs are *all* deleted vanishes. Word does this; `accept_changes.py` and `pandoc --track-changes=accept` don't always. Both fail the same way — they strip the deleted text but leave the emptied paragraph behind, which reads as a stray empty bullet when it was auto-numbered:

- `pandoc --track-changes=accept` never joins the paragraphs.
- `accept_changes.py` (LibreOffice) joins them correctly, except when the deleted paragraph is followed by an empty spacer paragraph.

An empty bullet in either view is an artifact of that view, not a defect in the document. Check paragraph deletions in the XML.

## Comments

Comments require six cross-linked files. Use the helper — directory mode when you'll also be editing `document.xml` (saves an unzip/rezip cycle), `.docx`-direct mode otherwise:

```bash
# Against an already-unpacked directory (preferred when also placing markers)
python scripts/comment.py unpacked/ "Fees & expenses cap is too low"
python scripts/comment.py unpacked/ "Agreed" --parent 0

# Against a .docx directly
python scripts/comment.py contract.docx "This cap is too low" -o annotated.docx
```

The script writes `comments.xml`, `commentsExtended.xml`, `commentsIds.xml`, `commentsExtensible.xml`, the relationships, and the content-type overrides. Comment IDs are auto-assigned. It then prints the `<w:commentRangeStart>`/`<w:commentRangeEnd>`/`<w:commentReference>` snippet to add to `word/document.xml` so the comment anchors to specific text — until you place those markers, the comment exists but is not visible.

## Dependencies

`docx` (npm, preinstalled — install only if `require('docx')` fails) · `pandoc` · LibreOffice (`soffice`) · `pdftoppm` (Poppler)
<!-- frozen-upstream:end -->

## Azhou boundary

Four Azhou-maintained constraints wrap the frozen guide; a conflict resolves toward the frozen text, and they bind how operations run, never what the recipes say.

1. **Fail closed per operation.** Before running a recipe or vendored script, confirm the dependencies it actually needs from [setup](references/setup.md) (a create script needs Node with the npm `docx` library; the edit track needs `defusedxml` through `merge_runs.py`, `zip` for the repack, and `lxml` when validating; the verify track needs LibreOffice, `zip` and `pdftoppm`; accepting tracked changes and legacy `.doc` conversion need LibreOffice). A missing dependency is a named `hold` for that operation only — never an untested substitute tool, never a guessed flag.
2. **Mutations touch named files only.** Creating, editing, converting, annotating or accepting changes in a document writes only the outputs the request names. Unpacking goes to the working directory the recipe names; overwriting an input in place requires the request to say so; destructive or bulk filesystem operations never ride along with a Word task. Upstream's own warning stands: docx from external parties is untrusted, so extraction uses the vendored `safe_extract` paths, never a shell `unzip`.
3. **Never create evidence.** Report what the executed check actually printed — soffice conversion results, `validate.py` XSD pass/fail lines, comment-marker snippets, script exit codes and receipts. Absent verification is named as absent; a zero exit code from a writer is not proof the .docx opens, validates, or contains the expected content.
4. **No machine-local absolute paths in deliverables.** Receipts and artifacts reference files relative to the working directory; machine-local absolute paths never enter them.

## Completion

End with the stable receipt defined in [brand-layer.md](references/brand-layer.md): `super-docx.receipt.v1`. Keep `complete`, `complete_with_holds`, `hold`, and `failed` distinct; none substitutes for another. A Word document produced or modified is claimed only after the declared verification ran: for created or edited documents, the upstream verify recipe (soffice render plus page inspection) or `scripts/office/validate.py` XSD validation reports a fact; for content reads, a verifiable sample of the extracted text is reported. The receipt is machine evidence: it never upgrades an unverified output into a verified one.
