"use strict";
const { createHash } = require("node:crypto");
const { existsSync, readFileSync } = require("node:fs");
const { dirname, join, resolve } = require("node:path");
const registeredSources = require("../library-content/sources.json");

const preview = process.env.AZHOU_LIBRARY_PREVIEW === "1";
const previewInput = process.env.AZHOU_LIBRARY_PREVIEW_INPUT;
if (previewInput && !preview) {
  throw new Error("A private source-library input requires preview mode");
}
const editionPath = previewInput ? resolve(previewInput) : join(__dirname, "../library-content/first-edition.json");
const release = previewInput || existsSync(editionPath)
  ? JSON.parse(readFileSync(editionPath, "utf8"))
  : { sources: registeredSources, articles: [] };
const approved = release.state === "approved";
const stamp = approved ? release.approved_at : preview ? release.preview_at : null;
if ((approved || previewInput) && !Number.isFinite(Date.parse(stamp))) {
  throw new Error("The source-library edition needs a valid publication or preview timestamp");
}

const sources = Object.entries(release.sources).map(([id, record]) => ({ id, ...record }));
const entries = stamp ? release.articles.map((entry) => {
  if (!/^[a-f0-9]{24}$/.test(entry.id) || !["full", "link"].includes(entry.scope) ||
      !entry.sources.every((id) => Object.hasOwn(release.sources, id))) {
    throw new Error(`Invalid source-library entry: ${entry.id}`);
  }
  if (entry.scope === "link" && (entry.body || entry.body_file || entry.body_sha256)) {
    throw new Error(`Link-only source-library entry has a body: ${entry.id}`);
  }
  let readingBody = "";
  if (entry.scope === "full") {
    if (!/^[a-z0-9-]+\.html$/.test(entry.body_file) || entry.license !== "CC0 1.0") {
      throw new Error(`Unexpected full-text content contract: ${entry.id}`);
    }
    const bytes = readFileSync(join(dirname(editionPath), entry.body_file));
    if (createHash("sha256").update(bytes).digest("hex") !== entry.body_sha256) {
      throw new Error(`Source-library body hash mismatch: ${entry.id}`);
    }
    readingBody = bytes.toString("utf8");
  }
  return {
    ...entry, readingBody, first_published: stamp, noteEn: entry.note_en,
    sourceName: entry.sources.map((id) => release.sources[id].name).join(" / "),
  };
}) : [];
entries.sort((a, b) => (b.published || "").localeCompare(a.published || "") ||
  a.title.localeCompare(b.title));

function localized(page, path) {
  const alternate = { en: path, zh: "/zh" + path };
  return ["en", "zh"].map((lang) => ({ ...page, locale: lang, path: alternate[lang], alternate }));
}

const channels = sources.map((source) => ({
  ...source, entries: entries.filter((item) => item.sources.includes(source.id)),
}));
module.exports = {
  preview,
  entries,
  featured: entries.find((entry) => entry.scope === "full"),
  channels,
  sourcePages: channels.flatMap((source) => localized(source, `/library/sources/${source.id}/`)),
  articlePages: entries.flatMap((entry) => localized(entry, `/library/articles/${entry.id}/`)),
  searchRows: entries.map(({ id, title, published, scope, kind, sources, sourceName, note, noteEn, lang }) =>
    ({ id, title, published, scope, kind, sources, sourceName, note, noteEn, lang })),
};
