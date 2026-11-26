"use strict";

const fs = require("node:fs");
const path = require("node:path");

function readBookRules(readme) {
  const heading = "Agent Rules Books";
  const sections = fs.readFileSync(path.resolve(__dirname, "../..", readme), "utf8").split(/^## /m);
  const section = sections.find((text) => text.split(/\r?\n/, 1)[0] === heading);
  if (!section) {
    throw new Error(`${readme}: missing Agent Rules Books section`);
  }
  return section.slice(heading.length).trim().replace(/^### /gm, "## ");
}

module.exports = function () {
  return {
    en: readBookRules("README.md"),
    zh: readBookRules("README.zh-CN.md"),
  };
};
