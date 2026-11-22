"use strict";

const site = require("./_data/site.js");

module.exports = function (eleventyConfig) {
  // Reuse the repository's own hero asset without duplicating its bytes in
  // the site tree; the shared footer carries the artwork license line and
  // the required attribution (packages/agent-skin/assets/azhou/NOTICE.md).
  eleventyConfig.addPassthroughCopy({
    "../assets/github/readme-hero.png": "./assets/hero.png",
    "../assets/site/hero.webp": "./assets/hero.webp",
    "../assets/site/hero-640.webp": "./assets/hero-640.webp",
    "../assets/skills/super-archify-effect.png": "./assets/skills/super-archify-effect.png",
    "../assets/skills/super-eli5-effect.png": "./assets/skills/super-eli5-effect.png",
    "../assets/skills/super-excalidraw-diagram-effect.png": "./assets/skills/super-excalidraw-diagram-effect.png",
    "../benchmarks/super-excalidraw-diagram/ordinary-model-floor/fixtures/reference/reference.architecture.excalidraw": "./showcase/demos/reference.architecture.excalidraw",
    "./showcase/demos": "./showcase/demos",
    "./robots.txt": "./robots.txt",
  });

  return {
    pathPrefix: site.pathPrefix,
    templateFormats: ["njk"],
    dir: {
      input: "./",
      output: "_site",
      includes: "_includes",
      data: "_data",
    },
  };
};
