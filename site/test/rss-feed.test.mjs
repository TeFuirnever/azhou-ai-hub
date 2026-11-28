import assert from "node:assert/strict";
import test from "node:test";
import { DOMParser } from "linkedom";
import { renderFeed } from "../lib/rss.mjs";

const entry = {
  id: "a".repeat(24), title: "Example item", note: "Reading note", sourceName: "Official source",
  first_published: "2026-11-27T23:00:00Z", published: "2020-01-01",
};
const options = {
  title: "Azhou Source Library", link: "https://example.org/hub/library/",
  self: "https://example.org/hub/library/rss.xml", description: "New reading notes",
  entries: [entry], articleUrl: item => `https://example.org/hub/library/articles/${item.id}/`,
  sourceTitle: item => item.sourceName,
};
const parse = xml => new DOMParser().parseFromString(xml, "text/xml");

test("RSS escapes channel fields, article text, and attribute URLs without changing their decoded values", () => {
  const text = `Guide <one> & "two" / O'Reilly`;
  const address = `https://example.org/notes?q=<one>&name="two"&author=O'Reilly`;
  const xml = renderFeed({ ...options, title: text, description: text, link: address, self: address,
    entries: [{ ...entry, title: text, note: text, sourceName: text }], articleUrl: () => address });
  const document = parse(xml);
  for (const selector of ["channel > title", "channel > description", "item > title", "item > description", "item > category"]) {
    const elements = document.querySelectorAll(selector);
    assert.equal(elements.length, 1, selector);
    assert.equal(elements[0].textContent, text);
  }
  for (const selector of ["channel > link", "item > link"]) {
    const elements = document.querySelectorAll(selector);
    assert.equal(elements.length, 1, selector);
    assert.equal(elements[0].textContent, address);
  }
  // LinkeDOM does not fully decode XML attribute entities. Check their required
  // serialized spelling directly rather than adding a second XML decoder.
  assert.ok(xml.includes('href="https://example.org/notes?q=&lt;one&gt;&amp;name=&quot;two&quot;&amp;author=O&apos;Reilly"'));
  assert.ok(xml.includes("&lt;one&gt; &amp; &quot;two&quot; / O&apos;Reilly"));
  assert.equal(document.getElementsByTagName("one").length, 0);
});

test("RSS sorts newest publication first with stable ID ties and leaves its frozen inputs untouched", () => {
  const entries = Object.freeze([
    Object.freeze({ ...entry, id: "c".repeat(24), first_published: "2026-11-27T23:00:00Z" }),
    Object.freeze({ ...entry, id: "d".repeat(24), first_published: "2026-11-26T23:00:00Z" }),
    Object.freeze({ ...entry, id: "a".repeat(24), first_published: "2026-11-27T23:00:00Z" }),
  ]);
  const before = JSON.stringify(entries);
  const first = renderFeed({ ...options, entries });
  assert.equal(first, renderFeed({ ...options, entries }));
  assert.deepEqual(Array.from(parse(first).getElementsByTagName("guid"), guid => guid.textContent),
    ["a", "c", "d"].map(letter => `urn:azhou:source-library:${letter.repeat(24)}`));
  assert.equal(JSON.stringify(entries), before);
});

test("RSS GUID remains stable when display metadata or host changes and pubDate uses library publication", () => {
  const first = parse(renderFeed(options));
  const changed = parse(renderFeed({ ...options, entries: [{ ...entry, title: "Updated title", note: "Updated note" }],
    articleUrl: () => "https://new.example.org/relocated-article/" }));
  const guid = first.getElementsByTagName("guid")[0];
  assert.equal(guid.textContent, `urn:azhou:source-library:${entry.id}`);
  assert.equal(guid.getAttribute("isPermaLink"), "false");
  assert.equal(changed.getElementsByTagName("guid")[0].textContent, guid.textContent);
  assert.equal(first.getElementsByTagName("pubDate")[0].textContent, "Fri, 27 Nov 2026 23:00:00 GMT");
});

test("RSS publishes the reading note without including archived bodies or private bookkeeping", () => {
  const xml = renderFeed({ ...options, entries: [{ ...entry, note: "Public reading note",
    readingBody: "private-body-marker", body: "full-body-marker", basis: "private-basis-marker", raw_object: "raw-object-marker" }] });
  const item = parse(xml).getElementsByTagName("item")[0];
  assert.equal(item.getElementsByTagName("description")[0].textContent, "Public reading note");
  assert.doesNotMatch(xml, /private-body-marker|full-body-marker|private-basis-marker|raw-object-marker/);
  assert.equal(item.getElementsByTagName("link")[0].textContent, options.articleUrl(entry));
});

test("an empty RSS feed keeps channel and self-discovery metadata and creates no placeholder item", () => {
  const xml = renderFeed({ ...options, entries: [], description: null });
  const document = parse(xml);
  assert.equal(document.documentElement.tagName, "rss");
  assert.equal(document.documentElement.getAttribute("version"), "2.0");
  assert.equal(document.documentElement.getAttribute("xmlns:atom"), "http://www.w3.org/2005/Atom");
  assert.equal(document.getElementsByTagName("item").length, 0);
  assert.equal(document.getElementsByTagName("title")[0].textContent, options.title);
  const self = document.getElementsByTagName("atom:link")[0];
  assert.equal(self.getAttribute("href"), options.self);
  assert.equal(self.getAttribute("rel"), "self");
  assert.equal(self.getAttribute("type"), "application/rss+xml");
  assert.doesNotMatch(xml, /undefined|null/);
  assert.ok(xml.endsWith("</rss>\n"));
});
