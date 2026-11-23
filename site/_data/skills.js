"use strict";

const fs = require("node:fs");
const path = require("node:path");
const matter = require("gray-matter");
const { skillsTreeBase: GITHUB_TREE_BASE } = require("./site");

const SKILLS_ROOT = path.resolve(__dirname, "..", "..", "skills");

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
      url: `${GITHUB_TREE_BASE}/${name}/`,
    });
  }

  return skills;
};
