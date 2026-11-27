"use strict";

const fs = require("node:fs");
const path = require("node:path");

function readBookRules(file) {
  const source = fs.readFileSync(path.resolve(__dirname, "..", "..", "docs", file), "utf8");
  return source.replace(/^# Agent Rules Books\r?\n\r?\n/, "").trim().replace(/^### /gm, "## ");
}

module.exports = function () {
  return {
    en: readBookRules("agent-rules-books.md"),
    zh: readBookRules("agent-rules-books.zh-CN.md"),
  };
};
