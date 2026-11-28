"use strict";

const REPO_NAME = "azhou-ai-hub";
const githubUrl = `https://github.com/TeFuirnever/${REPO_NAME}`;
const originOverride = process.env.AZHOU_SITE_PREVIEW_ORIGIN;
const siteOrigin = originOverride ? new URL(originOverride) : new URL("https://tefuirnever.github.io");
if (originOverride && (
  process.env.AZHOU_LIBRARY_PREVIEW !== "1" ||
  !["http:", "https:"].includes(siteOrigin.protocol) ||
  !["localhost", "127.0.0.1", "[::1]"].includes(siteOrigin.hostname) ||
  siteOrigin.href !== siteOrigin.origin + "/"
)) {
  throw new Error("A custom site preview origin must be a loopback HTTP origin");
}
const siteUrl = `${siteOrigin.origin}/${REPO_NAME}`;

module.exports = {
  githubUrl,
  siteUrl,
  askAzhouDownloadPath: "/downloads/super-ask-azhou.tgz",
  blobBase: `${githubUrl}/blob/main`,
  treeBase: `${githubUrl}/tree/main`,
  pathPrefix: `/${REPO_NAME}/`,
  routes: {
    en: { home: "/", skills: "/skills/", library: "/library/", books: "/agent-rules-books/", docs: "/docs/", support: "/support/" },
    zh: { home: "/zh/", skills: "/zh/skills/", library: "/zh/library/", books: "/zh/agent-rules-books/", docs: "/zh/docs/", support: "/zh/support/" },
  },
  labels: {
    en: {
      skills: "Skills",
      library: "Source Library",
      docs: "Docs",
      support: "Support",
      switchLang: "中文",
    },
    zh: {
      skills: "技能",
      library: "来源库",
      docs: "文档",
      support: "支持",
      switchLang: "English",
    },
  },
};
