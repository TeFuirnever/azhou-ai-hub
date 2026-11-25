"use strict";

const { pathPrefix } = require("./_data/site");

module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy({
    "../assets/azhou/wallpaper-scene-q-v3.png": "./assets/azhou-workspace.png",
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
