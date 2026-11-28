const back = document.getElementById("library-return");
const language = document.getElementById("switch-language");
const transferKey = "hub-library-reading-context";
const draftKey = "hub-library-language-draft";
const focusKey = "hub-library-return-focus";

const sameTab = (event) =>
  event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
const withoutHash = (url) => url.split("#")[0];

function sendContext(target, context) {
  try {
    sessionStorage.setItem(transferKey, JSON.stringify({ from: location.href, to: target.href, context }));
  } catch {}
}

function receiveContext() {
  try {
    const transfer = JSON.parse(sessionStorage.getItem(transferKey));
    if (transfer?.to !== location.href) return;
    sessionStorage.removeItem(transferKey);
    if (withoutHash(transfer.from) === withoutHash(document.referrer)) return transfer.context;
  } catch {}
}

function trackArticleLinks() {
  const list = document.querySelector(".edition-list");
  if (!list) return;
  list.addEventListener("click", event => {
    const link = event.target.closest("[data-entry-id] h3 a");
    if (!link || !sameTab(event)) return;
    sendContext(link, {
      listing: location.href,
      entryKey: window.navigation?.currentEntry?.key,
      entryId: link.closest("[data-entry-id]").dataset.entryId,
      draft: document.getElementById("library-query")?.value,
    });
  });

  function restoreFocus() {
    let context;
    try {
      context = JSON.parse(sessionStorage.getItem(focusKey));
      if (context?.target !== location.href) return;
      sessionStorage.removeItem(focusKey);
    } catch { return; }
    if (typeof context.entryId !== "string") return;
    const focusResult = () => {
      if (document.activeElement !== document.body && document.activeElement !== document.documentElement) return;
      list.querySelector(`[data-entry-id="${CSS.escape(context.entryId)}"] h3 a`)?.focus();
    };
    if (list.getAttribute("aria-busy") !== "true") {
      focusResult();
      return;
    }
    const observer = new MutationObserver(() => {
      if (list.getAttribute("aria-busy") === "true") return;
      observer.disconnect();
      focusResult();
    });
    observer.observe(list, { attributes: true, attributeFilter: ["aria-busy"] });
  }
  restoreFocus();
  window.addEventListener("pageshow", restoreFocus);
}

function articleReturn() {
  const root = new URL(back.href);
  const otherRoot = new URL(back.dataset.otherLibrary, root);

  function listing(value) {
    let url;
    try { url = new URL(value); } catch { return; }
    if (url.origin !== root.origin) return;
    for (const base of [root, otherRoot]) {
      if (!url.pathname.startsWith(base.pathname)) continue;
      const relative = url.pathname.slice(base.pathname.length);
      if (!relative || /^sources\/[a-z0-9-]+\/$/.test(relative)) return { url, relative };
    }
  }

  const saved = receiveContext() ?? history.state?.libraryReturn;
  const origin = listing(saved?.listing);
  const referrerListing = listing(document.referrer);
  const source = origin ?? referrerListing;
  if (!source) return;

  const context = origin ? saved : { listing: source.url.href };
  const target = new URL(source.relative, root);
  target.search = source.url.search;
  target.hash = source.url.hash;
  back.href = target.href;
  if (source.relative) back.textContent = back.dataset.sourceLabel;
  else if (target.search) back.textContent = back.dataset.resultsLabel;
  const keepContext = () => {
    try { history.replaceState({ ...history.state, libraryReturn: context }, ""); } catch {}
  };
  keepContext();
  window.addEventListener("hashchange", keepContext);

  function restoreDraft() {
    if (typeof context.draft !== "string") return;
    try {
      sessionStorage.setItem(draftKey, JSON.stringify({ target: target.href, draft: context.draft }));
    } catch {}
  }

  back.addEventListener("click", event => {
    if (!sameTab(event)) return;
    const navigation = window.navigation;
    const index = navigation?.currentEntry?.index;
    const entries = navigation?.entries() ?? [];
    let previous = entries.find(entry =>
      entry.key === context.entryKey && entry.url === target.href && entry.index < index);
    if (!context.entryKey && referrerListing?.url.pathname === target.pathname) {
      // Storage can be denied. Only the immediately preceding verified listing is safe to reuse.
      previous = entries.find(entry => entry.index === index - 1 && entry.url &&
        withoutHash(entry.url) === withoutHash(target.href));
    }
    if (typeof context.entryId === "string") {
      try {
        sessionStorage.setItem(focusKey, JSON.stringify({
          target: previous?.url ?? target.href,
          entryId: context.entryId,
        }));
      } catch {}
    }
    if (!previous) {
      restoreDraft();
      return;
    }
    event.preventDefault();
    navigation.traverseTo(previous.key).committed.catch(() => {
      restoreDraft();
      location.assign(target.href);
    });
  });
  language.addEventListener("click", event => {
    if (sameTab(event)) sendContext(language, context);
  });
}

if (back) articleReturn();
else trackArticleLinks();
