"use strict";

// Static documentation site for the Azhou AI Hub repository.
// The pathPrefix is a hard-coded assumption: this is a project site served
// at https://tefuirnever.github.io/azhou-ai-hub/. If the repository is
// renamed or moves to a user site, update pathPrefix in the same change.
module.exports = function (eleventyConfig) {
  // Reuse the repository's own hero asset without duplicating its bytes in
  // the site tree; the shared footer carries the artwork license line and
  // the required attribution (packages/agent-skin/assets/azhou/NOTICE.md).
  eleventyConfig.addPassthroughCopy({
    "../assets/github/readme-hero.png": "./assets/hero.png",
  });

  return {
    pathPrefix: "/azhou-ai-hub/",
    templateFormats: ["njk"],
    dir: {
      input: "./",
      output: "_site",
      includes: "_includes",
      data: "_data",
    },
  };
};
