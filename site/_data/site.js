"use strict";

const githubUrl = "https://github.com/TeFuirnever/azhou-ai-hub";
const siteUrl = "https://tefuirnever.github.io/azhou-ai-hub";

module.exports = {
  githubUrl,
  siteUrl,
  blobBase: `${githubUrl}/blob/main`,
  skillsTreeBase: `${githubUrl}/tree/main/skills`,
  pathPrefix: `${siteUrl.replace(/^https?:\/\/[^/]+/, "")}/`,
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
