"use strict";

const site = require("./_data/site.js");

module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy({
    "../assets/github/readme-hero.png": "./assets/hero.png",
    "../assets/site/hero.webp": "./assets/hero.webp",
    "../assets/site/hero-640.webp": "./assets/hero-640.webp",
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
