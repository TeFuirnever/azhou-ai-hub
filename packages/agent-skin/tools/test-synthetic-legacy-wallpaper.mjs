// Synthetic 0.7.1 ownership and disposal model; not the historical renderer.
export async function installRenderer(payload) {
  const root = document.documentElement;
  const owner = 'azhou.codex-startup-animation';
  const name = '--azhou-wallpaper-image';
  const before = [root.style.getPropertyValue(name), root.style.getPropertyPriority(name)];
  const attribute = root.getAttribute('data-azhou-wallpaper');
  const style = document.createElement('style');
  style.id = 'azhou-wallpaper-style';
  style.setAttribute('data-azhou-owner', owner);
  style.textContent = payload.css;
  root.style.setProperty(name, 'url("synthetic-wallpaper")');
  root.setAttribute('data-azhou-wallpaper', 'active');
  document.head.appendChild(style);
  let disposed = false;
  const api = {
    owner, version: '0.7.1',
    status() { return { version: '0.7.1', applied: !disposed, imageDecoded: true }; },
    dispose() {
      if (disposed) return api.status();
      disposed = true;
      style.remove();
      if (attribute === null) root.removeAttribute('data-azhou-wallpaper');
      else root.setAttribute('data-azhou-wallpaper', attribute);
      if (before[0]) root.style.setProperty(name, before[0], before[1]);
      else root.style.removeProperty(name);
      if (globalThis.__azhouWallpaper === api) delete globalThis.__azhouWallpaper;
      return api.status();
    },
  };
  globalThis.__azhouWallpaper = api;
  return api.status();
}
