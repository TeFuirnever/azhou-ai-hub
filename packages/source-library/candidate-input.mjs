import { readFileSync } from "node:fs";

import { readBatch, readItemFields } from "./vendor/aihot/ingest-fields.mts";
import { firstString, getPath, renderTemplate } from "./vendor/aihot/json-fields.mts";

function projectListing(data, config) {
  const items = getPath(data, config.itemsPath || "");
  if (!Array.isArray(items)) throw new Error("JSON itemsPath did not select an array");

  const candidates = [];
  for (const item of items) {
    const title = firstString(item, config.titlePaths);
    const url = renderTemplate(config.urlTemplate, item)
      || (config.urlTemplateFallback && renderTemplate(config.urlTemplateFallback, item));
    if (!title || !url) continue;
    const date = config.publishedAtPath && getPath(item, config.publishedAtPath);
    candidates.push({ title, url, publishedAt: typeof date === "string" ? date : null });
  }
  return { received: items.length, candidates };
}

function projectExternal(data) {
  const { sourceId, items } = readBatch(data || {});
  return { sourceId, received: items.length, candidates: readItemFields(items) };
}

try {
  const { mode, text, config } = JSON.parse(readFileSync(0, "utf8"));
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("input is not valid JSON");
  }
  const result = mode === "listing" ? projectListing(data, config) : projectExternal(data);
  process.stdout.write(JSON.stringify(result));
} catch (error) {
  process.stdout.write(JSON.stringify({ error: error.message }));
  process.exitCode = 1;
}
