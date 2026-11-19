---
name: super-pdf
description: "Azhou skill. Adopted from the upstream pdf skill (the upstream name still triggers this skill). Use whenever the user wants to do anything with PDF files: reading or extracting text and tables from PDFs, combining or merging multiple PDFs into one, splitting PDFs apart, rotating pages, adding watermarks, creating new PDFs, filling PDF forms, encrypting or decrypting PDFs, extracting images, and OCR on scanned PDFs to make them searchable. If the user mentions a .pdf file or asks to produce one, use this skill. Producing a PDF from a Word document belongs to super-docx."
invocation: model-invoked discipline
---

# Super Pdf

Super Pdf is the PDF processing discipline for agents: whenever a task touches PDF files — extracting text, tables or images, merging, splitting, rotating, watermarking, creating new PDFs, filling forms, encrypting or decrypting, or OCR on scanned pages — the frozen upstream guide below is the recipe source, the vendored scripts under `scripts/` are its mechanical helpers, and [FORMS.md](FORMS.md) plus [REFERENCE.md](REFERENCE.md) carry the form-filling and advanced-feature tracks. Dependencies are verified fail-closed before an operation runs.

**🦊 阿舟 · Pdf**

> 先验依赖，再动这份 PDF。

Invocation class: model-invoked discipline, declared in frontmatter; the axis and its semantics are defined once in `docs/skill-standard.md` §2.2 — reached autonomously whenever a task touches PDF files, no explicit naming required. Orchestrators may point here; this skill orchestrates nothing and calls no orchestrator.

## Brand protocol

Emit once when the skill starts, before any tool call:

```text
🦊 阿舟 · Pdf 启动（mode=<extract|assemble|create|forms|secure>, scope=<pdf-task>）
```

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1 chat presentation). Peeling the leading `>` and paired `**` must restore the protocol line. Headless, CI logs, receipts, and machine fields stay protocol-only.

Use `✅ 验证通过` only after the named checks actually ran. Use `❌ 验证失败` when this attempt fails and name one repair action, and `🔒 阿舟暂停这一项` when input, permission, or a dependency is missing. Emoji is display-only: keep it out of JSON keys, schema values, digests, paths, commands, test names, and raw evidence. A host without Unicode may strip the leading emoji while preserving the fixed text, the `（k=v, k=v）` field grouping, fields, and values. Raw evidence stays out of receipts unless the user supplied it. Stage events, the status dictionary, and the stable receipt are defined in the [Azhou interaction layer](references/brand-layer.md).

## Dependencies fail closed

Read [setup](references/setup.md) before the first PDF operation on a machine, or whenever a dependency has not been verified yet. The upstream guide below assumes its Python libraries and CLI tools are already available; this package does not: every dependency is named with a verification command in [setup](references/setup.md), and a missing one stops the affected operation with a named hold — never a silent tool substitution, never a partial install. The vendored helper scripts in `scripts/` run under the same contract.

## Frozen upstream guide

The text below is the upstream `pdf` skill's SKILL.md body, frozen verbatim at the immutable commit recorded in [provenance](references/provenance.md): everything below the upstream `# PDF Processing Guide` title. The upstream frontmatter is replaced by this package's neutral frontmatter and nothing else is paraphrased, extended, or trimmed; the Azhou boundary after the guide appends constraints and never overrides this text.

## Overview

This guide covers essential PDF processing operations using Python libraries and command-line tools. For advanced features, JavaScript libraries, and detailed examples, see REFERENCE.md. If you need to fill out a PDF form, read FORMS.md and follow its instructions.

## Quick Start

```python
from pypdf import PdfReader, PdfWriter

# Read a PDF
reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")

# Extract text
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python Libraries

### pypdf - Basic Operations

#### Merge PDFs
```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### Split PDF
```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### Extract Metadata
```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"Title: {meta.title}")
print(f"Author: {meta.author}")
print(f"Subject: {meta.subject}")
print(f"Creator: {meta.creator}")
```

#### Rotate Pages
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()

page = reader.pages[0]
page.rotate(90)  # Rotate 90 degrees clockwise
writer.add_page(page)

with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

### pdfplumber - Text and Table Extraction

#### Extract Text with Layout
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### Extract Tables
```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"Table {j+1} on page {i+1}:")
            for row in table:
                print(row)
```

#### Advanced Table Extraction
```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:  # Check if table is not empty
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

# Combine all tables
if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

### reportlab - Create PDFs

#### Basic PDF Creation
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter

# Add text
c.drawString(100, height - 100, "Hello World!")
c.drawString(100, height - 120, "This is a PDF created with reportlab")

# Add a line
c.line(100, height - 140, 400, height - 140)

# Save
c.save()
```

#### Create PDF with Multiple Pages
```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

# Add content
title = Paragraph("Report Title", styles['Title'])
story.append(title)
story.append(Spacer(1, 12))

body = Paragraph("This is the body of the report. " * 20, styles['Normal'])
story.append(body)
story.append(PageBreak())

# Page 2
story.append(Paragraph("Page 2", styles['Heading1']))
story.append(Paragraph("Content for page 2", styles['Normal']))

# Build PDF
doc.build(story)
```

#### Subscripts and Superscripts

**IMPORTANT**: Never use Unicode subscript/superscript characters (₀₁₂₃₄₅₆₇₈₉, ⁰¹²³⁴⁵⁶⁷⁸⁹) in ReportLab PDFs. The built-in fonts do not include these glyphs, causing them to render as solid black boxes.

Instead, use ReportLab's XML markup tags in Paragraph objects:
```python
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()

# Subscripts: use <sub> tag
chemical = Paragraph("H<sub>2</sub>O", styles['Normal'])

# Superscripts: use <super> tag
squared = Paragraph("x<super>2</super> + y<super>2</super>", styles['Normal'])
```

For canvas-drawn text (not Paragraph objects), manually adjust font the size and position rather than using Unicode subscripts/superscripts.

## Command-Line Tools

### pdftotext (poppler-utils)
```bash
# Extract text
pdftotext input.pdf output.txt

# Extract text preserving layout
pdftotext -layout input.pdf output.txt

# Extract specific pages
pdftotext -f 1 -l 5 input.pdf output.txt  # Pages 1-5
```

### qpdf
```bash
# Merge PDFs
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

# Split pages
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf input.pdf --pages . 6-10 -- pages6-10.pdf

# Rotate pages
qpdf input.pdf output.pdf --rotate=+90:1  # Rotate page 1 by 90 degrees

# Remove password
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf
```

### pdftk (if available)
```bash
# Merge
pdftk file1.pdf file2.pdf cat output merged.pdf

# Split
pdftk input.pdf burst

# Rotate
pdftk input.pdf rotate 1east output rotated.pdf
```

## Common Tasks

### Extract Text from Scanned PDFs
```python
# Requires: pip install pytesseract pdf2image
import pytesseract
from pdf2image import convert_from_path

# Convert PDF to images
images = convert_from_path('scanned.pdf')

# OCR each page
text = ""
for i, image in enumerate(images):
    text += f"Page {i+1}:\n"
    text += pytesseract.image_to_string(image)
    text += "\n\n"

print(text)
```

### Add Watermark
```python
from pypdf import PdfReader, PdfWriter

# Create watermark (or load existing)
watermark = PdfReader("watermark.pdf").pages[0]

# Apply to all pages
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### Extract Images
```bash
# Using pdfimages (poppler-utils)
pdfimages -j input.pdf output_prefix

# This extracts all images as output_prefix-000.jpg, output_prefix-001.jpg, etc.
```

### Password Protection
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

# Add password
writer.encrypt("userpassword", "ownerpassword")

with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## Quick Reference

| Task | Best Tool | Command/Code |
|------|-----------|--------------|
| Merge PDFs | pypdf | `writer.add_page(page)` |
| Split PDFs | pypdf | One page per file |
| Extract text | pdfplumber | `page.extract_text()` |
| Extract tables | pdfplumber | `page.extract_tables()` |
| Create PDFs | reportlab | Canvas or Platypus |
| Command line merge | qpdf | `qpdf --empty --pages ...` |
| OCR scanned PDFs | pytesseract | Convert to image first |
| Fill PDF forms | pdf-lib or pypdf (see FORMS.md) | See FORMS.md |

## Next Steps

- For advanced pypdfium2 usage, see REFERENCE.md
- For JavaScript libraries (pdf-lib), see REFERENCE.md
- If you need to fill out a PDF form, follow the instructions in FORMS.md
- For troubleshooting guides, see REFERENCE.md

## Azhou boundary

Four Azhou-maintained constraints wrap the frozen guide; a conflict resolves toward the frozen text, and they bind how operations run, never what the recipes say.

1. **Fail closed per operation.** Before running a recipe or vendored script, confirm the dependencies it actually needs from [setup](references/setup.md) (a merge needs pypdf; OCR needs pytesseract plus the tesseract binary and pdf2image with poppler; form filling needs pypdf for every fill path plus pdfplumber for the FORMS.md structure-first approach). A missing dependency is a named `hold` for that operation only — never an untested substitute tool, never a guessed flag.
2. **Mutations touch named files only.** Creating, merging, splitting, rotating, watermarking, filling, encrypting or OCR-ing a PDF writes only the outputs the request names. Overwriting an input in place requires the request to say so; destructive or bulk filesystem operations never ride along with a PDF task.
3. **Never create evidence.** Report what the executed check actually printed — page counts, extracted-text samples, script exit codes and receipts. Absent verification is named as absent; a zero exit code from a writer is not proof the output PDF opens, parses, or contains the expected content.
4. **No machine-local absolute paths in deliverables.** Receipts and artifacts reference files relative to the working directory; machine-local absolute paths never enter them.

## Completion

End with the stable receipt defined in [brand-layer.md](references/brand-layer.md): `super-pdf.receipt.v1`. Keep `complete`, `complete_with_holds`, `hold`, and `failed` distinct; none substitutes for another. A PDF produced or modified is claimed only after the declared verification ran: for merged/split/rotated/watermarked/encrypted output, re-open the result and report its page count and metadata; for extracted text/tables/images, report a verifiable sample; for filled forms, run the FORMS.md verify step. The receipt is machine evidence: it never upgrades an unverified output into a verified one.
