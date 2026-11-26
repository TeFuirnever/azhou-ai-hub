"use strict";

const { RenderPlugin } = require("@11ty/eleventy");
const { pathPrefix } = require("./_data/site");

module.exports = function (eleventyConfig) {
  eleventyConfig.addPlugin(RenderPlugin);
  eleventyConfig.addPassthroughCopy({
    "../assets/azhou/wallpaper-scene-q-v3.png": "./assets/azhou-workspace.png",
    "../assets/cursors/azhou-double-hug/Azhou-Double-Hug-3.6.1.cape": "./assets/Azhou-Double-Hug-3.6.1.cape",
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
