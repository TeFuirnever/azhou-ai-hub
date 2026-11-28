import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DOMParser } from "linkedom";
import { parsePage, renderPage, site } from "./copy-page.mjs";
import { calls, configure } from "./pagefind-fixture.mjs";

export const entries = [
  { id: "a".repeat(24), title: "Alpha release", note: "Alpha 中文导读", noteEn: "Alpha reading note",
    published: "2026-11-20", sources: ["alpha"], kind: "article", sourceName: "Alpha", lang: "en", scope: "link" },
  { id: "b".repeat(24), title: "Beta research", note: "Beta 中文导读", noteEn: "Beta reading note",
    published: "2026-11-21", sources: ["beta"], kind: "research", sourceName: "Beta", lang: "en", scope: "link" },
  { id: "c".repeat(24), title: "Gamma update", note: "Gamma 中文导读", noteEn: "Gamma reading note",
    published: "2026-11-22", sources: ["alpha"], kind: "article", sourceName: "Alpha", lang: "en", scope: "link" },
];
const sourceLibrary = {
  entries, searchRows: entries, preview: false,
  channels: [{ id: "alpha", name: "Alpha" }, { id: "beta", name: "Beta" }],
};
const script = readFileSync(new URL("../assets/library-search.js", import.meta.url), "utf8");

export function hit(id, excerpt = "Indexed text") {
  return { data: async () => ({ url: `${site.siteUrl}/library/articles/${id}/`, excerpt }) };
}

export const flush = () => new Promise(resolve => setImmediate(resolve));

export async function libraryPage({ lang = "en", url, state = null, storage = new Map(), index = {} } = {}) {
  configure(index);
  const { document, window } = parsePage(renderPage("library", lang, undefined, { sourceLibrary }));
  const location = new URL(url ?? site.siteUrl + site.routes[lang].library);
  const history = {
    state,
    replaceState(value, _title, address) {
      this.state = value;
      if (address !== undefined) location.href = new URL(address, location.href).href;
    },
  };
  const sessionStorage = {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: key => storage.delete(key),
  };
  const form = document.getElementById("library-search");
  const fields = Object.fromEntries(Array.from(form.querySelectorAll("[name]"), element => [element.name, element]));
  const results = document.getElementById("library-results");
  const status = document.getElementById("library-status");
  const reset = document.getElementById("library-reset");
  const language = document.getElementById("switch-language");
  const filters = document.getElementById("library-filter-details");
  const modules = document.querySelectorAll(`script[src="${site.pathPrefix}assets/library-search.js"][type="module"]`);
  assert.equal(modules.length, 1, "The rendered library must load the actual search module");
  assert.equal(form.dataset.index, `${site.pathPrefix}pagefind/pagefind.js`);
  form.dataset.index = new URL("./pagefind-fixture.mjs", import.meta.url).href;

  // LinkeDOM omits these standard browser properties. These shims supply DOM
  // boundaries only; search, filtering, draft, and history logic stay in the
  // unmodified production script. No browser layout or navigation is simulated.
  Object.defineProperty(form, "elements", { value: { namedItem: name => fields[name] } });
  for (const select of form.querySelectorAll("select")) {
    Object.defineProperty(select, "value", {
      get: () => (select.querySelector("option[selected]") ?? select.querySelector("option"))?.value ?? "",
      set: value => {
        for (const option of select.querySelectorAll("option")) option.toggleAttribute("selected", option.value === value);
      },
    });
  }
  Object.defineProperty(filters, "open", {
    get: () => filters.hasAttribute("open"),
    set: value => filters.toggleAttribute("open", Boolean(value)),
  });
  language.href = new URL(language.getAttribute("href"), location.href).href;
  class BrowserDOMParser {
    parseFromString(value, type) {
      return new DOMParser().parseFromString(type === "text/html" ? `<html><head></head><body>${value}</body></html>` : value, type);
    }
  }
  const environment = {
    document, window, history, location, sessionStorage,
    matchMedia: () => ({ matches: true }), DOMParser: BrowserDOMParser, setTimeout, clearTimeout,
  };
  new Function(...Object.keys(environment), '"use strict";\n' + script)(...Object.values(environment));
  await flush();
  const dispatch = (element, type) => element.dispatchEvent(new window.Event(type, { bubbles: true, cancelable: true }));
  return {
    document, window, location, history, storage, form, fields, results, status, reset, language, filters, calls,
    ids: () => Array.from(results.children, row => row.dataset.entryId),
    input(value) { fields.q.value = value; dispatch(fields.q, "input"); },
    submit(value) { if (value !== undefined) fields.q.value = value; dispatch(form, "submit"); },
    change(name, value) { fields[name].value = value; dispatch(fields[name], "change"); },
    clickLanguage() {
      const event = new window.Event("click", { bubbles: true, cancelable: true });
      Object.defineProperty(event, "button", { value: 0 });
      language.dispatchEvent(event);
    },
    restore(address, restoredState) {
      location.href = new URL(address, location.href).href;
      history.state = restoredState;
      window.dispatchEvent(new window.Event("popstate"));
    },
  };
}
