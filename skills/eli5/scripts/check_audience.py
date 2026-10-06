#!/usr/bin/env python3
"""Deterministic audience/style read-back assertion for the eli5 artifact.

eli5 promises "big pictures, few words" for a zero-background reader, but the
2026-10-06 cross-harness research recorded a user semantic complaint: the
delivered prose did not read like an explanation for a total beginner
(``docs/research/2026-10-06-cross-harness-execution-evidence.md`` section 3.3).
Model non-compliance used to surface only after delivery. This script moves
that judgment into the receipt layer: it reads the finished artifact back and
returns a deterministic verdict that the eli5 receipt must honor.

What it checks (all fixed constants, no configuration, no model judgment):

1. ``audience_marker`` - the artifact carries the exact audience declaration
   ``<meta name="eli5-audience" content="zero-background">``.
2. ``html_root`` - the artifact is standalone HTML (an ``<html`` root tag).
3. ``block_word_budget`` - every visible text block (headings, paragraphs,
   list items, table cells, captions, quotes, preformatted text, the
   document title) stays within ``MAX_WORDS_PER_BLOCK``.
4. ``sentence_word_budget`` - every sentence inside a block stays within
   ``MAX_WORDS_PER_SENTENCE``.
5. ``total_word_budget`` - the whole artifact stays within
   ``MAX_TOTAL_WORDS`` words.

Word counting is deterministic across scripts: each CJK character counts as
one word; other words are whitespace-separated tokens containing at least one
alphanumeric character. Sentences end at ``。！？；!`` and ``?`` (always) and
at ``.`` or ``;`` followed by whitespace or end of text, so decimals like
``3.5`` do not split. Text inside ``script`` and ``style`` is ignored; text
inside ``svg`` counts toward the total budget only, because diagram labels are
part of the picture while prose carries the explanation.

Usage from the skill package root::

    python scripts/check_audience.py <artifact.html>

Output: one JSON verdict line on stdout. Exit codes: ``0`` the artifact is
audience-compliant; ``1`` assertion failed (model non-compliance - the eli5
receipt must hold and name these violations, never deliver); ``2`` the
artifact could not be read (fail-closed environment error, a read-back
failure). Dependency-free; standard library only.
"""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

SCHEMA = "eli5.audience.assertion.v1"
AUDIENCE_MARKER = '<meta name="eli5-audience" content="zero-background">'
MAX_TOTAL_WORDS = 350
MAX_WORDS_PER_BLOCK = 45
MAX_WORDS_PER_SENTENCE = 25

SENTENCE_TERMINATORS_ALWAYS = frozenset("。！？；!?")
HTML_ROOT_PATTERN = re.compile(r"<html[\s>]", re.IGNORECASE)


class ArtifactError(RuntimeError):
    """Raised when the artifact cannot be read as text."""


def _is_cjk_word(char: str) -> bool:
    """Return True for characters that each count as one word on their own."""
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF  # CJK Unified Ideographs
        or 0x3400 <= code <= 0x4DBF  # Extension A
        or 0xF900 <= code <= 0xFAFF  # Compatibility Ideographs
        or 0x3040 <= code <= 0x30FF  # Hiragana and Katakana
        or 0xAC00 <= code <= 0xD7AF  # Hangul syllables
    )


def count_words(text: str) -> int:
    """Count words deterministically: CJK characters plus non-CJK tokens."""
    words = 0
    token_has_alnum = False

    def flush() -> None:
        nonlocal words, token_has_alnum
        if token_has_alnum:
            words += 1
        token_has_alnum = False

    for char in text:
        if _is_cjk_word(char):
            flush()
            words += 1
        elif char.isspace():
            flush()
        else:
            token_has_alnum = token_has_alnum or char.isalnum()
    flush()
    return words


def split_sentences(text: str) -> list[str]:
    """Split collapsed block text into sentences deterministically."""
    sentences: list[str] = []
    current: list[str] = []
    for index, char in enumerate(text):
        current.append(char)
        if char in SENTENCE_TERMINATORS_ALWAYS:
            sentences.append("".join(current))
            current = []
        elif char in ".;" and (index + 1 == len(text) or text[index + 1].isspace()):
            sentences.append("".join(current))
            current = []
    if current:
        sentences.append("".join(current))
    return [sentence for sentence in sentences if sentence.strip()]


class _ArtifactTextParser(HTMLParser):
    """Collect visible text blocks in document order."""

    BLOCK_TAGS = frozenset(
        {
            "p",
            "li",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "figcaption",
            "td",
            "th",
            "dt",
            "dd",
            "blockquote",
            "pre",
            "title",
        }
    )
    SKIP_TAGS = frozenset({"script", "style"})
    SVG_TAGS = frozenset({"svg"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.svg_text: list[str] = []
        self._current: list[str] = []
        self._block_stack: list[str] = []
        self._skip_depth = 0
        self._svg_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if normalized in self.SVG_TAGS:
            self._svg_depth += 1
            return
        if normalized in self.BLOCK_TAGS:
            self._flush_block()
            self._block_stack.append(normalized)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if normalized in self.SVG_TAGS:
            self._svg_depth = max(0, self._svg_depth - 1)
            return
        if normalized in self.BLOCK_TAGS:
            self._flush_block()
            if normalized in self._block_stack:
                while self._block_stack and self._block_stack.pop() != normalized:
                    continue

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data.strip():
            return
        if self._svg_depth:
            self.svg_text.append(data)
        else:
            self._current.append(data)

    def close(self) -> None:
        super().close()
        self._flush_block()

    def _flush_block(self) -> None:
        text = " ".join("".join(self._current).split())
        if text:
            self.blocks.append(text)
        self._current = []


def _read_artifact(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ArtifactError(f"cannot read artifact {path}: {exc}") from exc


def assert_audience(raw: str) -> dict[str, object]:
    """Return the deterministic verdict dict for one artifact's text."""
    violations: list[dict[str, str]] = []

    marker_present = AUDIENCE_MARKER in raw
    if not marker_present:
        violations.append(
            {
                "check": "audience_marker",
                "detail": f"missing required head declaration {AUDIENCE_MARKER}",
            }
        )

    html_root_present = HTML_ROOT_PATTERN.search(raw) is not None
    if not html_root_present:
        violations.append(
            {"check": "html_root", "detail": "no standalone <html> root tag found"}
        )

    parser = _ArtifactTextParser()
    parser.feed(raw)
    parser.close()

    for index, block in enumerate(parser.blocks, start=1):
        block_words = count_words(block)
        if block_words > MAX_WORDS_PER_BLOCK:
            violations.append(
                {
                    "check": "block_word_budget",
                    "detail": f"block {index} has {block_words} words (max {MAX_WORDS_PER_BLOCK})",
                }
            )
        for sentence in split_sentences(block):
            sentence_words = count_words(sentence)
            if sentence_words > MAX_WORDS_PER_SENTENCE:
                violations.append(
                    {
                        "check": "sentence_word_budget",
                        "detail": (
                            f"sentence in block {index} has {sentence_words} words "
                            f"(max {MAX_WORDS_PER_SENTENCE})"
                        ),
                    }
                )

    total_words = sum(count_words(block) for block in parser.blocks)
    total_words += sum(count_words(chunk) for chunk in parser.svg_text)
    if total_words > MAX_TOTAL_WORDS:
        violations.append(
            {
                "check": "total_word_budget",
                "detail": f"artifact has {total_words} words (max {MAX_TOTAL_WORDS})",
            }
        )

    return {
        "artifact_checks": {
            "audience_marker": marker_present,
            "html_root": html_root_present,
            "total_words": total_words,
        },
        "pass": not violations,
        "schema": SCHEMA,
        "violations": violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministic audience/style read-back assertion for one eli5 HTML "
            "artifact. Exit 0 compliant, 1 model non-compliance, 2 unreadable."
        )
    )
    parser.add_argument("artifact", help="path to the self-contained eli5 HTML artifact")
    args = parser.parse_args(argv)

    path = Path(args.artifact)
    try:
        raw = _read_artifact(path)
    except ArtifactError as exc:
        verdict = {"artifact": str(path), "error": str(exc), "schema": SCHEMA}
        print(json.dumps(verdict, sort_keys=True, ensure_ascii=True))
        print(f"error: {exc}", file=sys.stderr)
        return 2

    verdict = assert_audience(raw)
    verdict["artifact"] = str(path)
    print(json.dumps(verdict, sort_keys=True, ensure_ascii=True))
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
