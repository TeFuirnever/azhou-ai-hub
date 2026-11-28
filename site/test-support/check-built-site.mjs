import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { parseHTML } from "linkedom";
import site from "../_data/site.js";
import library from "../_data/sourceLibrary.js";
import { startBuiltSite } from "./built-site.mjs";

const publicOrigin = new URL(site.siteUrl).origin;
const absolute = path => site.siteUrl + path;
const aggregate = absolute("/library/rss.xml");
const feeds = [
  { path: "/library/", entries: library.entries },
  ...library.channels.map(source => ({ path: `/library/sources/${source.id}/`, entries: source.entries })),
];
const feedAddresses = feeds.map(feed => absolute(feed.path + "rss.xml"));
const pages = Object.values(site.routes).flatMap(routes => [
  { path: routes.home, discovery: [aggregate], panels: library.entries.length ? [aggregate] : feedAddresses },
  { path: routes.library, discovery: [aggregate], panels: feedAddresses },
]).concat(library.sourcePages.map(page => ({
  path: page.path, discovery: [aggregate, absolute(`/library/sources/${page.id}/rss.xml`)],
  panels: [absolute(`/library/sources/${page.id}/rss.xml`)],
})));

export async function checkBuiltSite({ root } = {}) {
  assert.equal(library.preview, false, "Check the public build with preview variables unset");
  const server = await startBuiltSite({ root });
  const resources = new Map();
  const articles = new Set();
  const get = async address => {
    const url = new URL(address);
    assert.equal(url.origin, publicOrigin, `Unexpected origin: ${address}`);
    assert.ok(url.pathname.startsWith(site.pathPrefix), `Missing project prefix: ${address}`);
    if (!resources.has(address)) {
      const response = await fetch(server.url(url.pathname + url.search), { redirect: "error", signal: AbortSignal.timeout(5000) });
      assert.equal(response.status, 200, `HTTP ${response.status}: ${address}`);
      const text = await response.text();
      assert.ok(text.length, `Empty build resource: ${address}`);
      resources.set(address, text);
    }
    return resources.get(address);
  };
  try {
    // Public metadata supplies the expected routes; a missing page/feed cannot
    // disappear from a directory scan and turn the check into an empty loop.
    for (const page of pages) {
      const address = absolute(page.path);
      const { document } = parseHTML(await get(address));
      const discovery = document.querySelectorAll('link[rel="alternate"][type="application/rss+xml"]');
      assert.ok(discovery.length, `Missing RSS autodiscovery: ${address}`);
      const urls = elements => Array.from(elements, element => new URL(element.getAttribute("href"), address).href).sort();
      assert.deepEqual(urls(discovery), [...page.discovery].sort(), `RSS links: ${address} (autodiscovery)`);
      const panels = document.querySelectorAll("details.rss-subscribe");
      assert.equal(panels.length, page.panels.length, `Subscription controls: ${address}`);
      const links = [];
      for (const panel of panels) {
        const anchors = panel.querySelectorAll(".rss-panel > a[href]");
        assert.equal(anchors.length, 1, `Expected one RSS feed link per panel: ${address}`);
        links.push(anchors[0]);
      }
      assert.deepEqual(urls(links), [...page.panels].sort(), `RSS links: ${address} (panels)`);
      for (const [selector, attribute, path, label] of [
        ['link[rel="stylesheet"][href]', "href", "assets/azhou-site.css", "stylesheet"],
        ['script[type="module"][src]', "src", "assets/copy-control.js", "copy module"],
      ]) {
        const matching = Array.from(document.querySelectorAll(selector)).filter(element => {
          const asset = new URL(element.getAttribute(attribute), address);
          return asset.origin === publicOrigin && asset.pathname === site.pathPrefix + path;
        });
        assert.equal(matching.length, 1, `Required RSS ${label}: ${address}`);
      }
      for (const element of document.querySelectorAll('script[src], link[rel="stylesheet"][href]')) {
        const asset = new URL(element.getAttribute("src") ?? element.getAttribute("href"), address);
        if (asset.origin === publicOrigin) await get(asset.href);
      }
    }
    const payload = [];
    for (const address of feedAddresses) payload.push({ url: address, xml: await get(address) });
    // LinkeDOM is suitable for HTML but accepts malformed XML. The stdlib XML
    // parser rejects bad entities and mismatched tags in the actual HTTP body.
    const parsed = JSON.parse(execFileSync(process.platform === "win32" ? "python" : "python3",
      [fileURLToPath(new URL("./parse-rss.py", import.meta.url))], {
        input: JSON.stringify(payload), encoding: "utf8", timeout: 10_000, maxBuffer: 4 * 1024 * 1024,
        stdio: ["pipe", "pipe", "pipe"],
      }));
    assert.equal(parsed.length, feeds.length);
    for (const [index, feed] of parsed.entries()) {
      const expected = feeds[index];
      assert.ok(feed.title, `Missing RSS title: ${feedAddresses[index]}`);
      assert.equal(feed.self, feedAddresses[index]);
      assert.equal(feed.link, absolute(expected.path));
      assert.equal(feed.items.length, expected.entries.length, `RSS item count: ${feed.self}`);
      const byGuid = new Map(expected.entries.map(entry => [`urn:azhou:source-library:${entry.id}`, entry]));
      assert.deepEqual(feed.items.map(item => item.guid).sort(), [...byGuid.keys()].sort(), `RSS identities: ${feed.self}`);
      for (const item of feed.items) {
        const entry = byGuid.get(item.guid);
        assert.equal(item.isPermaLink, "false");
        assert.equal(item.link, absolute(`/library/articles/${entry.id}/`));
        assert.equal(item.title, entry.title);
        assert.equal(item.description, entry.note ?? "");
        const article = await get(item.link);
        assert.ok(parseHTML(article).document.querySelector("[data-pagefind-body]"), `Missing article body: ${item.link}`);
        articles.add(item.link);
      }
    }
    if (library.entries.length) await get(absolute("/pagefind/pagefind.js"));
    return { feeds: feeds.length, pages: pages.length, articles: articles.size, resources: resources.size };
  } finally {
    await server.close();
  }
}
