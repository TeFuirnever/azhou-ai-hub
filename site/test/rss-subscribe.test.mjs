import assert from "node:assert/strict";
import test from "node:test";

import { controls, parsePage, renderPage, site, sourceLibrary } from "../test-support/copy-page.mjs";

const allFeed = `${site.siteUrl}/library/rss.xml`;
const sourceFeeds = sourceLibrary.channels.map(source => ({
  id: `rss-${source.id}`, title: source.name, url: `${site.siteUrl}/library/sources/${source.id}/rss.xml`,
}));

for (const lang of ["zh", "en"]) {
  const all = { id: "rss-all", title: lang === "zh" ? "阿舟来源库" : "Azhou Source Library", url: allFeed };
  const pages = [
    { kind: "home", feeds: [all] },
    { kind: "empty-home", feeds: [all, ...sourceFeeds] },
    { kind: "library", feeds: [all, ...sourceFeeds] },
    ...sourceLibrary.channels.map((source, i) => ({ kind: "source", sourceId: source.id, feeds: [sourceFeeds[i]] })),
  ];
  for (const { kind, sourceId, feeds } of pages) {
    test(`${lang} ${kind}${sourceId ? `/${sourceId}` : ""}: subscriptions retain usable no-JS fallbacks and canonical feeds`, () => {
      const { document } = parsePage(renderPage(kind, lang, sourceId));
      assert.equal(document.documentElement.lang, lang === "zh" ? "zh-CN" : "en");
      const ids = Array.from(document.querySelectorAll("[id]"), element => element.id);
      assert.equal(new Set(ids).size, ids.length, "Copy targets and other page IDs must be unique");
      assert.equal(document.querySelectorAll("details.rss-subscribe").length, feeds.length);
      const autodiscovery = Array.from(document.querySelectorAll('link[rel="alternate"][type="application/rss+xml"]'),
        link => new URL(link.getAttribute("href"), site.siteUrl).href);
      assert.deepEqual(autodiscovery, sourceId ? [allFeed, feeds[0].url] : [allFeed]);
      for (const feed of feeds) {
        const panel = document.getElementById(feed.id);
        assert.equal(panel?.tagName, "DETAILS", feed.id);
        assert.equal(panel.hasAttribute("open"), false);
        const summary = panel.firstElementChild;
        assert.equal(summary.tagName, "SUMMARY");
        const compact = feed.id !== "rss-all" && kind !== "source";
        assert.equal(summary.textContent, compact ? "RSS" : lang === "zh" ? "订阅 RSS" : "Subscribe by RSS");
        if (compact) assert.equal(summary.getAttribute("aria-label"), `${lang === "zh" ? "订阅" : "Subscribe to"} ${feed.title} RSS`);
        assert.match(panel.querySelector(".rss-panel > p").textContent, lang === "zh" ? /RSS 阅读器/ : /RSS reader/);
        const [control] = controls(panel);
        assert.equal(panel.querySelectorAll("[data-copy]").length, 1);
        assert.equal(control.actions.hidden, true, "Unavailable copy controls must not appear without JS");
        assert.equal(control.button.getAttribute("type"), "button");
        assert.equal(control.button.textContent, lang === "zh" ? "复制订阅地址" : "Copy feed address");
        assert.equal(control.source.textContent, feed.url);
        assert.equal(control.source.closest(".rss-subscribe"), panel, "Each panel owns its copy target");
        assert.equal(control.source.closest("[hidden]"), null, "The manual address must not depend on JS");
        const link = panel.querySelector(".rss-panel > a");
        assert.equal(link.getAttribute("href"), feed.url);
        assert.equal(link.closest("[hidden]"), null);
        assert.equal(link.textContent, lang === "zh" ? "查看 RSS 文件" : "View RSS feed");
      }
      const script = document.querySelectorAll(`script[src="${site.pathPrefix}assets/copy-control.js"][type="module"]`);
      assert.equal(script.length, 1, "Rendered pages must load the real copy handler");
    });
  }
}
