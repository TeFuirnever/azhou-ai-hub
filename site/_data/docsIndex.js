"use strict";

// Build-time loader for the documentation map. docs/README.md stays the
// single authority; the site does not mirror any document body, it only
// re-renders the index table with each relative link rewritten to the
// versioned blob URL on GitHub.
//
// Fail loud: an index row whose links cannot be parsed terminates the build
// instead of silently losing the rewritten link.
const fs = require("node:fs");
const path = require("node:path");

const DOCS_INDEX = path.resolve(__dirname, "..", "..", "docs", "README.md");
const BLOB_BASE = "https://github.com/TeFuirnever/azhou-ai-hub/blob/main";
const LINK_PATTERN = /\[([^\]]+)\]\(([^)\s]+)\)/g;

function toBlobUrl(target, line) {
  if (/^(https?:)?\/\//i.test(target)) {
    return target;
  }
  const hashIndex = target.indexOf("#");
  const filePart = hashIndex === -1 ? target : target.slice(0, hashIndex);
  const anchor = hashIndex === -1 ? "" : target.slice(hashIndex);
  if (filePart === "") {
    throw new Error(
      `site/_data/docsIndex.js: docs/README.md row carries an anchor-only link: ${line}`
    );
  }
  const repoPath = path.posix.normalize(path.posix.join("docs", filePart));
  return `${BLOB_BASE}/${repoPath}${anchor}`;
}

module.exports = function () {
  const raw = fs.readFileSync(DOCS_INDEX, "utf8");
  const lines = raw.split("\n");

  const rows = [];
  let headerSeen = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("|")) {
      continue;
    }
    const inner = trimmed.endsWith("|")
      ? trimmed.slice(1, -1)
      : trimmed.slice(1);
    const cells = inner.split("|").map((cell) => cell.trim());

    if (!headerSeen) {
      if (cells.length < 2 || cells[0] !== "Need" || cells[1] !== "Maintained source") {
        throw new Error(
          `site/_data/docsIndex.js: docs/README.md table header changed, expected "| Need | Maintained source |": ${line}`
        );
      }
      headerSeen = true;
      continue;
    }
    if (cells.every((cell) => /^:?-+:?$/.test(cell) && cell !== "")) {
      continue;
    }
    if (cells.length < 2) {
      throw new Error(
        `site/_data/docsIndex.js: docs/README.md row has fewer than two columns: ${line}`
      );
    }

    const links = [...cells[1].matchAll(LINK_PATTERN)];
    if (links.length === 0) {
      throw new Error(
        `site/_data/docsIndex.js: docs/README.md row has no parseable link: ${line}`
      );
    }

    rows.push({
      need: cells[0],
      sources: links.map((match) => ({
        label: match[1],
        url: toBlobUrl(match[2], line),
      })),
    });
  }

  if (rows.length === 0) {
    throw new Error("site/_data/docsIndex.js: docs/README.md table has no rows");
  }

  return rows;
};
