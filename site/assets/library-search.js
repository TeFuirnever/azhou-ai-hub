const form = document.querySelector("#library-search");
const results = document.querySelector("#library-results");
const status = document.querySelector("#library-status");
const title = document.querySelector("#results-title");
const entries = JSON.parse(document.querySelector("#library-data").textContent);
const byId = new Map(entries.map((entry) => [entry.id, entry]));
const rows = new Map(Array.from(results.children, (row) => [row.dataset.entryId, row]));
const zh = form.dataset.locale === "zh";
const query = form.elements.namedItem("q");
const endDate = form.elements.namedItem("to");
const filterDetails = document.getElementById("library-filter-details");
const reset = document.getElementById("library-reset");
const filterNames = ["source", "kind", "from", "to"];
const languageLink = document.getElementById("switch-language");
const languageDraftKey = "hub-library-language-draft";
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
let appliedQuery = "";
let cleared;
let sequence = 0;
let indexReady;
let pending;

const normalize = (text) => text.normalize("NFKC").trim().toLocaleLowerCase();

function renderResults(matches) {
  const focused = results.contains(document.activeElement) ? document.activeElement : null;
  const focusedId = focused?.closest("[data-entry-id]")?.dataset.entryId;
  const previousIds = new Set(Array.from(results.children, (row) => row.dataset.entryId));
  for (const row of Array.from(results.children)) {
    if (!matches.has(row.dataset.entryId)) row.remove();
  }
  let position = results.firstElementChild;
  for (const [id, text] of matches) {
    const row = rows.get(id);
    const isNew = !previousIds.has(id);
    const existing = row.querySelector("[data-excerpt]");
    if (text && !existing) {
      const excerpt = document.createElement("p");
      excerpt.dataset.excerpt = "";
      excerpt.textContent = text;
      row.append(excerpt);
    } else if (text && existing.textContent !== text) {
      existing.textContent = text;
    } else if (!text) {
      existing?.remove();
    }
    if (isNew && !reducedMotion.matches) {
      row.classList.remove("is-entering");
      void row.offsetWidth;
      row.classList.add("is-entering");
    } else {
      row.classList.remove("is-entering");
    }
    if (row === position) {
      position = row.nextElementSibling;
    } else if (row.parentNode === results && typeof results.moveBefore === "function") {
      results.moveBefore(row, position);
    } else {
      results.insertBefore(row, position);
    }
  }
  if (focused && document.activeElement !== focused) {
    if (matches.has(focusedId)) focused.focus({ preventScroll: true });
    else query.focus({ preventScroll: true });
  }
}

function loadIndex() {
  indexReady ??= import(form.dataset.index).then(async (index) => {
    await index.options({ language: "zh" });
    return index;
  }).catch((error) => {
    indexReady = undefined;
    throw error;
  });
  return indexReady;
}

function setStatus(text, state = "") {
  status.dataset.state = state;
  if (status.textContent !== text) status.textContent = text;
}

function filterValues() {
  return filterNames.map(name => form.elements.namedItem(name).value);
}

function restoreFilters(values) {
  filterNames.forEach((name, index) => {
    form.elements.namedItem(name).value = values[index] ?? "";
  });
}

function syncReset() {
  const label = cleared ? reset.dataset.undo : reset.dataset.clear;
  if (reset.textContent !== label) reset.textContent = label;
  reset.hidden = !cleared && !query.value && !appliedQuery && !filterValues().some(Boolean);
  if (reset.hidden && document.activeElement === reset) query.focus({ preventScroll: true });
}

function rememberDraft() {
  const draft = query.value;
  const current = history.state?.librarySearchDraft;
  if (draft === (current ?? appliedQuery)) return;
  try {
    history.replaceState({ ...history.state, librarySearchDraft: draft }, "");
  } catch (error) {
    if (error.name !== "SecurityError") throw error;
  }
}

languageLink.addEventListener("click", (event) => {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  try {
    sessionStorage.setItem(languageDraftKey, JSON.stringify({ target: languageLink.href, draft: query.value }));
  } catch {}
});

function readLanguageDraft() {
  try {
    const transfer = JSON.parse(sessionStorage.getItem(languageDraftKey));
    sessionStorage.removeItem(languageDraftKey);
    if (transfer?.target === location.href) return transfer.draft;
  } catch {}
}

async function search(updateUrl = true) {
  const current = ++sequence;
  clearTimeout(pending);
  const term = normalize(appliedQuery);
  const filters = filterValues();
  const [source, kind, from, to] = filters;
  syncReset();
  if (from && to && from > to) {
    endDate.setAttribute("aria-invalid", "true");
    endDate.setAttribute("aria-describedby", status.id);
    results.removeAttribute("aria-busy");
    setStatus(zh ? "结束日期须在起始日期当日或之后。" :
      "Choose an end date on or after the start date.", "error");
    return;
  }
  endDate.removeAttribute("aria-invalid");
  endDate.removeAttribute("aria-describedby");
  const filtered = term || source || kind || from || to;
  const eligible = (entry) => entry && rows.has(entry.id) && (!source || entry.sources.includes(source)) &&
    (!kind || entry.kind === kind) && (!from || entry.published?.slice(0, 10) >= from) &&
    (!to || entry.published?.slice(0, 10) <= to);
  const params = new URLSearchParams();
  if (appliedQuery) params.set("q", appliedQuery);
  filterNames.forEach((name, index) => {
    if (filters[index]) params.set(name, filters[index]);
  });
  const alternate = new URL(languageLink.href);
  alternate.search = params.toString();
  if (languageLink.href !== alternate.href) languageLink.href = alternate.href;
  if (updateUrl) {
    const next = location.pathname + (params.size ? "?" + params : "") + location.hash;
    if (next !== location.pathname + location.search + location.hash ||
        history.state?.librarySearchDraft !== query.value) {
      try {
        history.replaceState({ ...history.state, librarySearchDraft: query.value }, "", next);
      } catch (error) {
        if (error.name !== "SecurityError") throw error;
      }
    }
  }

  const matches = new Map();
  let indexUnavailable = false;
  if (term) {
    results.setAttribute("aria-busy", "true");
    pending = setTimeout(() => {
      if (current === sequence) setStatus(zh ? "正在搜索…" : "Searching…", "pending");
    }, 200);
    try {
      const index = await loadIndex();
      if (current !== sequence) return;
      const response = await index.search(term);
      if (current !== sequence) return;
      const hits = await Promise.all(response.results.map((hit) => hit.data()));
      if (current !== sequence) return;
      for (const result of hits) {
        const id = result.url.match(/\/library\/articles\/([a-f0-9]{24})(?:\/|$)/)?.[1];
        if (eligible(byId.get(id))) {
          const excerpt = new DOMParser().parseFromString(result.excerpt, "text/html");
          matches.set(id, excerpt.body.textContent);
        }
      }
    } catch {
      indexUnavailable = true;
    }
  }
  if (current !== sequence) return;
  clearTimeout(pending);
  for (const entry of entries) {
    const text = normalize(`${entry.title} ${entry.note} ${entry.noteEn}`);
    if (eligible(entry) && !matches.has(entry.id) && (!term || text.includes(term))) {
      matches.set(entry.id, term ? (zh ? entry.note : entry.noteEn) : "");
    }
  }
  const heading = filtered ? (zh ? "搜索结果" : "Search results") : (zh ? "选文" : "Selections");
  if (title.textContent !== heading) title.textContent = heading;
  renderResults(matches);
  results.removeAttribute("aria-busy");
  const count = zh ? `${matches.size} 条结果` : `${matches.size} ${matches.size === 1 ? "result" : "results"}`;
  if (indexUnavailable) {
    const fallback = zh
      ? (matches.size ? `标题和导读中找到 ${count}。` : "标题和导读中没有匹配。")
      : (matches.size ? `${count} in titles and notes.` : "No matches in titles or notes.");
    setStatus((zh ? "正文搜索暂不可用。" : "Full-text search is unavailable. ") + fallback, "error");
  } else if (!matches.size) {
    setStatus(zh ? "没有匹配的选文。试试更短的关键词，或放宽筛选条件。" :
      "No matching selections. Try fewer words or clear some filters.", "empty");
  } else if (filtered) {
    setStatus(count, "done");
  } else {
    setStatus("", "");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  cleared = undefined;
  appliedQuery = query.value.trim();
  search();
});
query.addEventListener("input", () => {
  cleared = undefined;
  rememberDraft();
  syncReset();
});
form.addEventListener("change", ({ target }) => {
  if (!filterNames.includes(target.name)) return;
  cleared = undefined;
  search();
});
reset.addEventListener("click", () => {
  if (cleared) {
    ({ draft: query.value, query: appliedQuery } = cleared);
    restoreFilters(cleared.filters);
    cleared = undefined;
  } else {
    cleared = { draft: query.value, query: appliedQuery, filters: filterValues() };
    query.value = appliedQuery = "";
    restoreFilters([]);
  }
  search();
});
function restoreSearch() {
  const params = new URLSearchParams(location.search);
  cleared = undefined;
  appliedQuery = params.get("q") ?? "";
  query.value = history.state?.librarySearchDraft ?? readLanguageDraft() ?? appliedQuery;
  rememberDraft();
  restoreFilters(filterNames.map(name => params.get(name)));
  if (filterValues().some(Boolean)) filterDetails.open = true;
  search(false);
}
window.addEventListener("popstate", restoreSearch);
restoreSearch();
form.hidden = false;
