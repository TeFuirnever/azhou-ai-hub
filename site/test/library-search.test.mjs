import assert from "node:assert/strict";
import test from "node:test";
import { entries, flush, hit, libraryPage } from "../test-support/library-page.mjs";

const [a, b, c] = entries.map(entry => entry.id);
const snapshot = page => ({ ids: page.ids(), text: page.status.textContent, state: page.status.dataset.state, url: page.location.href });

test("a failed full-text index preserves title/note search and retries initialization next time", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let attempts = 0;
  const page = await libraryPage({ index: {
    options: async () => { if (++attempts === 1) throw new Error("index unavailable"); },
    search: async () => ({ results: [hit(c, "<mark>Alpha</mark> indexed &amp; readable")] }),
  } });
  page.submit("Alpha");
  await flush();
  assert.deepEqual(page.ids(), [a]);
  assert.equal(page.status.dataset.state, "error");
  assert.match(page.status.textContent, /Full-text search is unavailable.*1 result in titles and notes/);
  assert.equal(page.results.hasAttribute("aria-busy"), false);
  page.submit();
  await flush();
  assert.equal(attempts, 2, "A rejected index initialization must not remain cached");
  assert.deepEqual(page.ids(), [c, a]);
  assert.equal(page.status.dataset.state, "done");
  assert.equal(page.results.firstElementChild.querySelector("[data-excerpt]").textContent, "Alpha indexed & readable");
  assert.equal(page.results.querySelector("mark"), null, "Search excerpts must be inserted as text");
});

test("an older search response cannot replace a newer search's results or URL", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const old = Promise.withResolvers();
  const page = await libraryPage({ index: {
    search: async term => term === "old body" ? old.promise : { results: [hit(b)] },
  } });
  page.submit("old body");
  await flush();
  page.submit("Beta");
  await flush();
  const latest = snapshot(page);
  assert.deepEqual(latest.ids, [b]);
  old.resolve({ results: [hit(a)] });
  await flush();
  assert.deepEqual(snapshot(page), latest);
});

test("an older hit-data failure cannot turn a newer successful search into a fallback error", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const oldData = Promise.withResolvers();
  const page = await libraryPage({ index: {
    search: async term => ({ results: term === "old body" ? [{ data: () => oldData.promise }] : [hit(b)] }),
  } });
  page.submit("old body");
  await flush();
  page.submit("Beta");
  await flush();
  const latest = snapshot(page);
  oldData.reject(new Error("stale data failure"));
  await flush();
  assert.deepEqual(snapshot(page), latest);
  assert.equal(page.status.dataset.state, "done");
});

test("an invalid date range keeps current results and clears its accessible error after correction", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const page = await libraryPage({ lang: "zh" });
  page.submit("Beta");
  await flush();
  const url = page.location.href;
  const searched = page.calls.search.length;
  page.fields.from.value = "2026-11-23";
  page.change("to", "2026-11-21");
  await flush();
  assert.deepEqual(page.ids(), [b]);
  assert.equal(page.location.href, url);
  assert.equal(page.calls.search.length, searched);
  assert.equal(page.status.textContent, "结束日期须在起始日期当日或之后。");
  assert.equal(page.fields.to.getAttribute("aria-invalid"), "true");
  assert.equal(page.fields.to.getAttribute("aria-describedby"), "library-status");
  page.change("from", "2026-11-20");
  await flush();
  assert.deepEqual(page.ids(), [b]);
  assert.equal(page.fields.to.hasAttribute("aria-invalid"), false);
  assert.equal(page.fields.to.hasAttribute("aria-describedby"), false);
  assert.equal(page.status.dataset.state, "done");
});

test("source, kind, and inclusive date bounds combine without needing the full-text index", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const page = await libraryPage();
  page.fields.source.value = "alpha";
  page.fields.kind.value = "article";
  page.fields.from.value = "2026-11-20";
  page.change("to", "2026-11-22");
  await flush();
  assert.deepEqual(page.ids(), [a, c]);
  assert.equal(page.calls.options.length, 0);
  assert.equal(page.calls.search.length, 0);
  assert.equal(page.status.textContent, "2 results");
  assert.equal(new URL(page.language.href).search, page.location.search);
});

test("changing a filter searches the keyword already in the input", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const page = await libraryPage();
  page.submit("Alpha");
  await flush();
  page.input(" Beta ");
  page.change("source", "beta");
  await flush();
  assert.deepEqual(page.ids(), [b]);
  assert.equal(page.location.searchParams.get("q"), "Beta");
  assert.equal(page.location.searchParams.get("source"), "beta");
});

test("clear and undo retain the applied query, unsent draft, and all filters separately", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const page = await libraryPage();
  page.fields.source.value = "alpha";
  page.fields.kind.value = "article";
  page.fields.from.value = "2026-11-20";
  page.fields.to.value = "2026-11-22";
  page.submit("Alpha");
  await flush();
  page.input("unfinished Beta draft");
  assert.deepEqual(page.ids(), [a]);
  page.reset.click();
  await flush();
  assert.deepEqual(page.ids(), [a, b, c]);
  assert.equal(page.fields.q.value, "");
  assert.equal(page.location.search, "");
  assert.equal(page.reset.textContent, "Undo clear");
  page.reset.click();
  await flush();
  assert.deepEqual(page.ids(), [a]);
  assert.equal(page.fields.q.value, "unfinished Beta draft");
  assert.equal(page.location.searchParams.get("q"), "Alpha");
  assert.equal(page.history.state.librarySearchDraft, "unfinished Beta draft");
  assert.deepEqual(["source", "kind", "from", "to"].map(name => page.fields[name].value),
    ["alpha", "article", "2026-11-20", "2026-11-22"]);
  assert.equal(page.reset.textContent, "Clear search criteria");
});

test("typing a draft does not submit it and language transfer preserves both applied query and draft", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const storage = new Map();
  const page = await libraryPage({ storage, url: "https://tefuirnever.github.io/azhou-ai-hub/library/?q=Alpha&source=alpha#results-title" });
  const applied = page.location.href;
  const calls = page.calls.search.length;
  page.input("unsubmitted translated draft");
  assert.equal(page.calls.search.length, calls);
  assert.equal(page.location.href, applied);
  assert.deepEqual(page.ids(), [a]);
  assert.equal(new URL(page.language.href).searchParams.get("q"), "Alpha");
  page.clickLanguage();
  const translated = await libraryPage({ lang: "zh", url: page.language.href, storage });
  assert.equal(translated.fields.q.value, "unsubmitted translated draft");
  assert.equal(translated.location.searchParams.get("q"), "Alpha");
  assert.equal(translated.fields.source.value, "alpha");
  assert.equal(translated.filters.hasAttribute("open"), true);
  assert.deepEqual(translated.ids(), [a]);
  assert.equal(storage.has("hub-library-language-draft"), false, "Consume the one-navigation draft transfer");
});

test("history restoration applies the saved query and filters while keeping its separate draft", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const page = await libraryPage();
  page.submit("Alpha");
  await flush();
  page.restore("?q=Beta&source=beta#results-title", { librarySearchDraft: "unfinished next query" });
  await flush();
  assert.deepEqual(page.ids(), [b]);
  assert.equal(page.fields.q.value, "unfinished next query");
  assert.equal(page.fields.source.value, "beta");
  assert.equal(page.filters.hasAttribute("open"), true);
  assert.equal(page.location.hash, "#results-title");
  assert.equal(page.location.searchParams.get("q"), "Beta");
  assert.equal(new URL(page.language.href).searchParams.get("q"), "Beta");
});

test("a slow search keeps results while pending and an empty result clears busy and pending feedback", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const response = Promise.withResolvers();
  const page = await libraryPage({ lang: "zh", index: { search: () => response.promise } });
  assert.equal(page.form.hidden, false);
  page.submit("unmatched");
  await flush();
  assert.deepEqual(page.ids(), [a, b, c]);
  assert.equal(page.results.getAttribute("aria-busy"), "true");
  t.mock.timers.tick(199);
  assert.equal(page.status.textContent, "");
  t.mock.timers.tick(1);
  assert.equal(page.status.textContent, "正在搜索…");
  response.resolve({ results: [] });
  await flush();
  assert.deepEqual(page.ids(), []);
  assert.equal(page.results.hasAttribute("aria-busy"), false);
  assert.equal(page.status.dataset.state, "empty");
  t.mock.timers.tick(1000);
  assert.equal(page.status.dataset.state, "empty");
  page.submit("still-unmatched");
  await flush();
  t.mock.timers.tick(200);
  assert.equal(page.status.dataset.state, "empty", "A fast result must not be overwritten by its pending timer");
  page.reset.click();
  await flush();
  assert.deepEqual(page.ids(), [a, b, c]);
  assert.equal(page.status.textContent, "");
});
