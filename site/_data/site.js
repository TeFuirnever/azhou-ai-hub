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
