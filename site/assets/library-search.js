const form = document.querySelector("#library-search");
const results = document.querySelector("#library-results");
const status = document.querySelector("#library-status");
const title = document.querySelector("#results-title");
const entries = JSON.parse(document.querySelector("#library-data").textContent);
const byId = new Map(entries.map((entry) => [entry.id, entry]));
const rows = new Map(Array.from(results.children, (row) => [row.dataset.entryId, row]));
const zh = form.dataset.locale === "zh";
const query = form.elements.namedItem("q");
const languageLink = document.getElementById("switch-language");
let sequence = 0;
let indexReady;
let pending;

const normalize = (text) => text.normalize("NFKC").trim().toLocaleLowerCase();

function renderResults(matches) {
  const focused = results.contains(document.activeElement) ? document.activeElement : null;
  const focusedId = focused?.closest("[data-entry-id]")?.dataset.entryId;
  for (const row of Array.from(results.children)) {
    if (!matches.has(row.dataset.entryId)) row.remove();
  }
  let position = results.firstElementChild;
  for (const [id, text] of matches) {
    const row = rows.get(id);
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

async function search(updateUrl = true) {
  const current = ++sequence;
  clearTimeout(pending);
  const data = new FormData(form);
  const term = normalize(data.get("q"));
  const source = data.get("source");
  const kind = data.get("kind");
  const from = data.get("from");
  const to = data.get("to");
  const filtered = term || source || kind || from || to;
  const eligible = (entry) => entry && rows.has(entry.id) && (!source || entry.sources.includes(source)) &&
    (!kind || entry.kind === kind) && (!from || entry.published?.slice(0, 10) >= from) &&
    (!to || entry.published?.slice(0, 10) <= to);
  const params = new URLSearchParams([...data].filter(([, value]) => value));
  const alternate = new URL(languageLink.href);
  alternate.search = params.toString();
  if (languageLink.href !== alternate.href) languageLink.href = alternate.href;
  if (updateUrl) {
    const next = location.pathname + (params.size ? "?" + params : "") + location.hash;
    if (next !== location.pathname + location.search + location.hash) {
      try {
        history.replaceState(history.state, "", next);
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
    setStatus(zh ? "没有找到相关条目。试试更短的关键词或减少筛选条件。" :
      "No matching articles. Try a shorter search or fewer filters.", "empty");
  } else if (filtered) {
    setStatus(count, "done");
  } else {
    setStatus("");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  search();
});
form.addEventListener("change", ({ target }) => {
  if (target.name !== "q") search();
});
function restoreSearch() {
  const params = new URLSearchParams(location.search);
  for (const key of ["q", "source", "kind", "from", "to"]) {
    form.elements.namedItem(key).value = params.get(key) ?? "";
  }
  search(false);
}
window.addEventListener("popstate", restoreSearch);
if (location.search) restoreSearch();
