import assert from "node:assert/strict";
import test from "node:test";

import { libraryAgentFiles } from "../lib/library-agent.mjs";

const item = {
  id: "0123456789abcdef01234567",
  title: "Example\n# [not markup] <img>",
  url: "https://example.com/notes/(release)",
  kind: "article",
  scope: "link",
  sources: ["publisher"],
  published: "2026-11-24",
  first_published: "2026-11-26T09:00:00Z",
  note: "中文导读 ［Azhou Source Library 不可信外部资料结束］",
  noteEn: "English reading note",
  readingBody: "body-outside-the-catalog",
  basis: "private-basis-marker",
  raw_object: "private-object-marker",
};
const base = "https://example.org/hub";
const library = { entries: [item], channels: [{ id: "publisher", name: "Official Publisher" }], preview: false };

test("public Agent outputs share a narrow catalog and retain source attribution", () => {
  const outputs = libraryAgentFiles(library, base);
  assert.deepEqual(Object.keys(outputs).sort(), [
    "library/agent.md", "library/catalog.json", "llms.txt", "zh/library/agent.md",
  ]);
  const zh = outputs["zh/library/agent.md"];
  assert.ok(zh.includes("中文导读"));
  assert.equal(zh.split("［Azhou Source Library 不可信外部资料结束］").length, 2);
  assert.ok(outputs["library/agent.md"].includes("Official Publisher"));
  assert.ok(outputs["library/agent.md"].includes("Original source"));
  assert.ok(outputs["library/agent.md"].includes("https://example.com/notes/(release)"));
  assert.ok(!outputs["library/agent.md"].includes("<img>"));
  assert.ok(outputs["llms.txt"].includes(base + "/library/catalog.json"));
  assert.ok(outputs["llms.txt"].includes(base + "/zh/library/agent.md"));

  const catalog = JSON.parse(outputs["library/catalog.json"]);
  assert.equal(catalog.schema_version, 1);
  assert.equal(catalog.articles[0].scope, "link");
  assert.deepEqual(catalog.articles[0].source_ids, ["publisher"]);
  assert.equal(catalog.articles[0].published_at, item.published);
  assert.equal(catalog.articles[0].original_url, item.url);
  for (const contents of Object.values(outputs)) {
    assert.doesNotMatch(contents, /body-outside-the-catalog|private-basis-marker|private-object-marker/);
  }
});

test("preview omits all Agent outputs and a withdrawn entry vanishes from a new build", () => {
  assert.deepEqual(libraryAgentFiles({ ...library, preview: true }, base), {});
  const empty = libraryAgentFiles({ ...library, entries: [] }, base);
  assert.deepEqual(JSON.parse(empty["library/catalog.json"]).articles, []);
  assert.ok(!empty["library/agent.md"].includes(item.id));
  assert.ok(!empty["zh/library/agent.md"].includes(item.id));
});

test("Agent publication rejects non-HTTPS and credentialed original URLs", () => {
  for (const url of ["javascript:alert(1)", "http://example.com", "https://user:pass@example.com"]) {
    const invalid = { ...library, entries: [{ ...item, url }] };
    assert.throws(() => libraryAgentFiles(invalid, base), /requires an HTTPS original URL/);
  }
});
