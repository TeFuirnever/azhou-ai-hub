"use strict";

const fs = require("node:fs");
const path = require("node:path");
const matter = require("gray-matter");
const { treeBase: GITHUB_TREE_BASE } = require("./site");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const SKILLS_ROOT = path.join(REPO_ROOT, "skills");

function readSkillSummaries(readme) {
  const source = fs.readFileSync(path.join(REPO_ROOT, readme), "utf8");
  const rows = source.split("\n");
  const summaries = new Map();
  for (const row of rows) {
    const match = /^\| \[([^\]]+)\]\(skills\/([^/]+)\/SKILL\.md\) \| ([^|]+) \|/.exec(row);
    if (!match) continue;
    const [, title, name, task] = match;
    if (summaries.has(name)) throw new Error(`${readme} lists ${name} more than once`);
    summaries.set(name, { title, task: task.replaceAll("`", "") });
  }
  return summaries;
}

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

  const english = readSkillSummaries("README.md");
  const chinese = readSkillSummaries("README.zh-CN.md");
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

    const en = english.get(name);
    const zh = chinese.get(name);
    if (!en || !zh) throw new Error(`Add a description for ${name} to both README skill tables`);
    skills.push({
      name: data.name.trim(),
      summary: { en, zh },
      url: `${GITHUB_TREE_BASE}/skills/${name}/`,
    });
  }

  return skills;
};
