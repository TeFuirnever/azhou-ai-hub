"use strict";

// Build-time loader for the support matrix's opening paragraph. The site
// quotes docs/support-matrix.md verbatim instead of keeping a hand-maintained
// copy, so a matrix edit cannot leave a stale harness list on the page.
//
// Fail loud: a missing heading or paragraph terminates the build instead of
// silently rendering an empty or stale quote.
const fs = require("node:fs");
const path = require("node:path");

const SUPPORT_MATRIX = path.resolve(
  __dirname,
  "..",
  "..",
  "docs",
  "support-matrix.md"
);
const HEADING = "# Support matrix";

// Only the inline constructs the opening paragraph currently uses: bold spans
// and inline code. Anything else fails loud so a richer paragraph gets an
// explicit loader update instead of leaking raw markdown to the page.
function inlineMarkdownToHtml(text) {
  if (/\[[^\]]+\]\([^)]*\)/.test(text) || /(^|\s)_[^_]+_($|\s)/.test(text)) {
    throw new Error(
      "site/_data/supportMatrix.js: opening paragraph uses markdown the loader does not convert; extend inlineMarkdownToHtml"
    );
  }
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

module.exports = function () {
  const raw = fs.readFileSync(SUPPORT_MATRIX, "utf8");
  const lines = raw.split("\n");

  let headingIndex = -1;
  for (let i = 0; i < lines.length; i += 1) {
    if (lines[i].trim() === HEADING) {
      headingIndex = i;
      break;
    }
  }
  if (headingIndex === -1) {
    throw new Error(
      `site/_data/supportMatrix.js: docs/support-matrix.md no longer opens with "${HEADING}"`
    );
  }

  const introLines = [];
  for (let i = headingIndex + 1; i < lines.length; i += 1) {
    const trimmed = lines[i].trim();
    if (trimmed === "") {
      if (introLines.length > 0) {
        break;
      }
      continue;
    }
    if (/^#{1,6}(\s|$)/.test(trimmed)) {
      if (introLines.length === 0) {
        throw new Error(
          "site/_data/supportMatrix.js: docs/support-matrix.md has no opening paragraph before the next heading"
        );
      }
      break;
    }
    introLines.push(trimmed);
  }
  if (introLines.length === 0) {
    throw new Error(
      "site/_data/supportMatrix.js: docs/support-matrix.md ends after the heading without an opening paragraph"
    );
  }

  return { intro: inlineMarkdownToHtml(introLines.join(" ")) };
};
