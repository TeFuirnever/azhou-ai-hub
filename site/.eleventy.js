"use strict";

const { RenderPlugin } = require("@11ty/eleventy");
const { execFileSync } = require("node:child_process");
const { mkdir, writeFile } = require("node:fs/promises");
const { dirname, join } = require("node:path");
const { pathPrefix, siteUrl } = require("./_data/site");
const library = require("./_data/sourceLibrary");

module.exports = function (eleventyConfig) {
  eleventyConfig.addPlugin(RenderPlugin);
  eleventyConfig.addPassthroughCopy({
    "../assets/azhou/wallpaper-scene-q-v3.png": "./assets/azhou-workspace.png",
    "../assets/cursors/azhou-double-hug/Azhou-Double-Hug-3.6.1.cape": "./assets/Azhou-Double-Hug-3.6.1.cape",
    "./assets": "./assets",
  });
  eleventyConfig.addNunjucksFilter("scriptJson", (data) => JSON.stringify(data).replaceAll("<", "\\u003c"));
  eleventyConfig.on("eleventy.after", async ({ dir }) => {
    const { renderFeed } = await import("./lib/rss.mjs");
    const { libraryAgentFiles } = await import("./lib/library-agent.mjs");
    const feeds = [
      { path: "/library/", name: "阿舟来源库", entries: library.entries },
      ...library.channels.map((source) => ({
        path: `/library/sources/${source.id}/`, name: `${source.name} / 阿舟来源库`, entries: source.entries,
      })),
    ];
    for (const feed of feeds) {
      const file = join(dir.output, feed.path, "rss.xml");
      await mkdir(dirname(file), { recursive: true });
      await writeFile(file, renderFeed({
        title: feed.name, link: siteUrl + feed.path, self: siteUrl + feed.path + "rss.xml",
        description: "阿舟来源库新增条目及自写导读",
        entries: feed.entries, sourceTitle: (item) => item.sourceName,
        articleUrl: (item) => `${siteUrl}/library/articles/${item.id}/`,
      }));
    }
    for (const [path, contents] of Object.entries(libraryAgentFiles(library, siteUrl))) {
      const file = join(dir.output, path);
      await mkdir(dirname(file), { recursive: true });
      await writeFile(file, contents);
    }
    if (library.entries.length) {
      execFileSync(join(__dirname, "node_modules", ".bin", "pagefind"),
        ["--site", dir.output, "--glob", "library/articles/**/*.html", "--force-language", "zh"],
        { stdio: "inherit" });
    }
  });

  return {
    pathPrefix,
    templateFormats: ["njk"],
    dir: {
      input: "./",
      output: process.env.AZHOU_LIBRARY_PREVIEW === "1" ? ".cache/site-preview" : "_site",
      includes: "_includes",
      data: "_data",
    },
  };
};
