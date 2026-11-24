"use strict";

const { pathPrefix } = require("./_data/site");

module.exports = function (eleventyConfig) {
  // Reuse the repository's own hero asset without duplicating its bytes in
  // the site tree; the shared footer carries the artwork license line and
  // the required attribution (assets/azhou/NOTICE.md).
  eleventyConfig.addPassthroughCopy({
    "../assets/github/readme-hero.png": "./assets/hero.png",
    "../assets/site/hero.webp": "./assets/hero.webp",
    "../assets/site/hero-640.webp": "./assets/hero-640.webp",
  });

  return {
    pathPrefix,
    templateFormats: ["njk"],
    dir: {
      input: "./",
      output: "_site",
      includes: "_includes",
      data: "_data",
    },
  };
};
