const link = document.getElementById("library-return");
const referrer = document.referrer && new URL(document.referrer);
if (referrer && referrer.origin === location.origin && referrer.pathname === link.pathname) {
  link.search = referrer.search;
  link.addEventListener("click", (event) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const navigation = window.navigation;
    const current = navigation?.currentEntry;
    const previous = navigation?.entries().findLast(entry =>
      entry.index < current?.index && entry.url === referrer.href);
    if (!previous) return;
    event.preventDefault();
    navigation.traverseTo(previous.key).committed.catch(() => location.assign(link.href));
  });
}
