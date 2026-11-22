"use strict";

const PAGES_ORIGIN = "https://tefuirnever.github.io";
const REPO_NAME = "azhou-ai-hub";
const GITHUB_BASE = `https://github.com/TeFuirnever/${REPO_NAME}`;

module.exports = {
  githubUrl: GITHUB_BASE,
  blobBase: `${GITHUB_BASE}/blob/main`,
  treeBase: `${GITHUB_BASE}/tree/main`,
  pathPrefix: `/${REPO_NAME}/`,
  siteUrl: `${PAGES_ORIGIN}/${REPO_NAME}`,
  labels: {
    en: {
      home: "Home",
      skills: "Skills",
      docs: "Docs",
      support: "Support",
      switchLang: "中文",
    },
    zh: {
      home: "首页",
      skills: "技能",
      docs: "文档",
      support: "支持",
      switchLang: "English",
    },
  },
};
