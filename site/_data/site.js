"use strict";

const REPO_NAME = "azhou-ai-hub";
const githubUrl = `https://github.com/TeFuirnever/${REPO_NAME}`;
const siteUrl = `https://tefuirnever.github.io/${REPO_NAME}`;

module.exports = {
  githubUrl,
  siteUrl,
  blobBase: `${githubUrl}/blob/main`,
  treeBase: `${githubUrl}/tree/main`,
  pathPrefix: `/${REPO_NAME}/`,
  routes: {
    en: { home: "/", skills: "/skills/", books: "/agent-rules-books/", docs: "/docs/", support: "/support/" },
    zh: { home: "/zh/", skills: "/zh/skills/", books: "/zh/agent-rules-books/", docs: "/zh/docs/", support: "/zh/support/" },
  },
  labels: {
    en: {
      skills: "Skills",
      docs: "Docs",
      support: "Support",
      switchLang: "中文",
    },
    zh: {
      skills: "技能",
      docs: "文档",
      support: "支持",
      switchLang: "English",
    },
  },
};
