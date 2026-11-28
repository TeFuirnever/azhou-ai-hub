const back = document.getElementById("library-return");
const language = document.getElementById("switch-language");
const root = new URL(back.href);
const otherRoot = new URL(back.dataset.otherLibrary, root);
const transferKey = "hub-library-article-return";

function listing(value) {
  if (typeof value !== "string" || !value) return;
  let url;
  try { url = new URL(value); } catch { return; }
  if (url.origin !== root.origin) return;
  for (const base of [root, otherRoot]) {
    if (!url.pathname.startsWith(base.pathname)) continue;
    const relative = url.pathname.slice(base.pathname.length);
    if (!relative || /^sources\/[a-z0-9-]+\/$/.test(relative)) return { url, relative };
  }
}

function readTransfer() {
  try {
    const transfer = JSON.parse(sessionStorage.getItem(transferKey));
    if (transfer?.to !== location.href) return;
    sessionStorage.removeItem(transferKey);
    if (transfer.from.split("#")[0] === document.referrer.split("#")[0]) return listing(transfer.listing);
  } catch {}
}

const source = listing(document.referrer) ?? listing(history.state?.libraryReturn) ?? readTransfer();
if (source) {
  const target = new URL(source.relative, root);
  target.search = source.url.search;
  target.hash = source.url.hash;
  back.href = target.href;
  if (source.relative) back.textContent = back.dataset.sourceLabel;
  else if (target.search) back.textContent = back.dataset.resultsLabel;

  try { history.replaceState({ ...history.state, libraryReturn: target.href }, ""); } catch {}

  const sameTab = event => event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
  back.addEventListener("click", event => {
    if (!sameTab(event)) return;
    const historyNavigation = window.navigation;
    const index = historyNavigation?.currentEntry?.index;
    const previous = historyNavigation?.entries().findLast(entry => entry.index < index && entry.url === target.href);
    if (!previous) return;
    event.preventDefault();
    historyNavigation.traverseTo(previous.key).committed.catch(() => location.assign(target.href));
  });
  language.addEventListener("click", event => {
    if (!sameTab(event)) return;
    try {
      sessionStorage.setItem(transferKey, JSON.stringify({ from: location.href, to: language.href, listing: target.href }));
    } catch {}
  });
}
