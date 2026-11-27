import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createContext, runInContext } from "node:vm";
import matter from "gray-matter";
import { parseHTML } from "linkedom";
import nunjucks from "nunjucks";

import site from "../_data/site.js";
import sourceLibrary from "../_data/sourceLibrary.js";
import loadSkills from "../_data/skills.js";

export { site, sourceLibrary };
const siteDir = join(dirname(fileURLToPath(import.meta.url)), "..");
const templates = new nunjucks.Environment(new nunjucks.FileSystemLoader([
  join(siteDir, "_includes"), siteDir,
]), { autoescape: false });
templates.addFilter("url", path => site.pathPrefix.replace(/\/$/, "") + path);
templates.addFilter("scriptJson", data => JSON.stringify(data).replaceAll("<", "\\u003c"));
const skills = loadSkills();
const sharedScript = readFileSync(join(siteDir, "assets/copy-control.js"), "utf8");
const rendered = new Map();

export const messages = {
  zh: { pending: "正在复制…", success: "已复制", error: "复制失败。请手动复制下方内容。" },
  en: { pending: "Copying…", success: "Copied", error: "Copy failed. Select and copy the text below." },
};

// Render the real templates/macros and base layout, including the source page's
// computed feed path. No generated _site directory or network is needed.
export function renderPage(kind, lang, sourceId) {
  const key = JSON.stringify([kind, lang, sourceId]);
  if (rendered.has(key)) return rendered.get(key);
  const empty = kind === "empty-home";
  const template = kind === "source" ? "library/source.njk" :
    `_includes/${empty ? "home" : kind}.njk`;
  const parsed = matter(readFileSync(join(siteDir, template), "utf8"));
  const channel = sourceLibrary.sourcePages.find(page => page.id === sourceId && page.locale === lang);
  const route = kind === "source" ? "library" : empty ? "home" : kind;
  const data = {
    ...parsed.data, lang, site, skills, route, channel,
    title: channel?.name ?? "Azhou AI Hub",
    page: { url: channel?.path ?? site.routes[lang][route] },
    sourceLibrary: empty ? {
      ...sourceLibrary, entries: [], featured: undefined, searchRows: [],
      channels: sourceLibrary.channels.map(source => ({ ...source, entries: [] })),
    } : sourceLibrary,
  };
  if (kind === "source") {
    assert.ok(channel, `Unknown source page: ${sourceId}/${lang}`);
    data.sourceFeed = templates.renderString(parsed.data.eleventyComputed.sourceFeed, data);
  }
  const content = templates.renderString(parsed.content, data);
  const html = templates.render("base.njk", { ...data, content });
  const result = { html, content, kind, lang };
  rendered.set(key, result);
  return result;
}

export function parsePage(page) {
  return parseHTML(page.html);
}

export function controls(root) {
  const document = root.ownerDocument ?? root;
  return Array.from(root.querySelectorAll("[data-copy]"), button => {
    const actions = button.closest(".copy-actions");
    const status = (button.closest(".term-bar") ?? actions).querySelector('[role="status"]');
    const source = document.getElementById(button.dataset.copy);
    assert.ok(source, `Missing copy target: ${button.dataset.copy}`);
    assert.ok(status, `Missing status: ${button.dataset.copy}`);
    return { button, actions, status, source, message: status.querySelector("[data-copy-message]") };
  });
}

// Run production code, not a replica of its handlers. Only browser boundaries
// (clipboard, media query, style tokens, timers) are controlled. Base-layout and
// catalog-search scripts are outside these copy tests; layout/permissions and
// native disclosure keyboard activation still require browser experience review.
export function startPage(page, { clipboard = true } = {}) {
  const { document, window } = parsePage(page);
  const writes = [];
  const navigator = clipboard === "missing-write" ? { clipboard: {} } : {};
  if (clipboard === true) {
    navigator.clipboard = {
      writeText(text) {
        const pending = Promise.withResolvers();
        writes.push({ text, ...pending });
        return pending.promise;
      },
    };
  }
  const context = createContext({
    document, window, navigator,
    matchMedia: query => ({ matches: query.includes("prefers-reduced-motion"), addEventListener() {} }),
    getComputedStyle: () => ({ getPropertyValue: name => ({
      "--motion-ease": "linear", "--motion-feedback": "120ms", "--motion-change": "160ms",
    })[name] ?? "" }),
    setTimeout, clearTimeout, cancelAnimationFrame() {},
  });
  if (page.kind === "home" || page.kind === "empty-home") {
    const inline = parseHTML(page.content).document.querySelectorAll("script:not([src])");
    assert.equal(inline.length, 1, "Execute the homepage's actual inline script");
    for (const script of inline) runInContext(script.textContent, context, { filename: "home.njk" });
  }
  const modules = document.querySelectorAll(`script[src="${site.pathPrefix}assets/copy-control.js"]`);
  assert.equal(modules.length, 1, "The page must load the shared script exactly once");
  assert.equal(modules[0].getAttribute("type"), "module");
  runInContext(sharedScript, context, { filename: "copy-control.js" });
  return { document, writes, controls: controls(document) };
}

export function expectStatus(control, state, lang) {
  assert.equal(control.status.dataset.state ?? "", state, control.button.dataset.copy);
  assert.equal(control.message.textContent, state ? messages[lang][state] : "", control.button.dataset.copy);
}

export async function settle(write, outcome = "success") {
  if (outcome === "success") write.resolve();
  else write.reject(new Error("Clipboard permission denied"));
  // The event listener awaits a promise from this realm inside its VM realm.
  await Promise.resolve();
  await Promise.resolve();
}
