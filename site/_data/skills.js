"use strict";

// Build-time loader for the canonical skill catalog. The site never keeps a
// hand-maintained copy of the catalog: it reads every package's SKILL.md
// frontmatter straight from the repository checkout, so the page follows the
// packages as they are added, renamed or removed.
//
// Fail loud: a package with missing or unreadable SKILL.md frontmatter
// terminates the build instead of silently dropping a skill from the page.
const fs = require("node:fs");
const path = require("node:path");
const matter = require("gray-matter");

const SKILLS_ROOT = path.resolve(__dirname, "..", "..", "skills");
const { treeBase } = require("./site.js");

module.exports = function () {
  const names = fs
    .readdirSync(SKILLS_ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();

  if (names.length === 0) {
    throw new Error(
      "site/_data/skills.js: no skill packages found under skills/"
    );
  }

  const skills = [];
  for (const name of names) {
    const skillMdPath = path.join(SKILLS_ROOT, name, "SKILL.md");
    let raw;
    try {
      raw = fs.readFileSync(skillMdPath, "utf8");
    } catch (err) {
      throw new Error(
        `site/_data/skills.js: skills/${name}/SKILL.md is missing or unreadable: ${err.message}`
      );
    }

    const { data } = matter(raw);
    if (typeof data.name !== "string" || data.name.trim() === "") {
      throw new Error(
        `site/_data/skills.js: skills/${name}/SKILL.md frontmatter has no name`
      );
    }
    if (typeof data.description !== "string" || data.description.trim() === "") {
      throw new Error(
        `site/_data/skills.js: skills/${name}/SKILL.md frontmatter has no description`
      );
    }

    skills.push({
      name: data.name.trim(),
      description: data.description.trim(),
      invocation:
        typeof data.invocation === "string" ? data.invocation.trim() : "",
      url: `${treeBase}/skills/${name}/`,
    });
  }

  return skills;
};
