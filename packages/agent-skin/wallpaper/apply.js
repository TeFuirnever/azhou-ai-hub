export function createWallpaperApplicator(installRenderer, options, host = globalThis) {
  const { version, css } = options;
  const pageAdapter = options.pageAdapter;

  function captureAdapter() {
    const ports = pageAdapter?.wallpaper;
    const attributes = ports?.attributes;
    const filter = attributes?.observeFilter;
    const controller = pageAdapter?.controllerWallpaper;
    return { ports, attributes, filter, filterValues: Array.isArray(filter) ? [...filter] : filter,
      controller, owner: controller?.owner, validPage: ports?.validPage, shellState: ports?.shellState,
      surfaces: ports?.surfaces, css: ports?.css, scope: ports?.scope, surfaceMarker: attributes?.surfaceMarker };
  }

  function adapterUnchanged(binding) {
    const { ports, attributes, filter, filterValues, controller } = binding;
    if (pageAdapter?.wallpaper !== ports) return false;
    if (!ports) return true;
    return ports.attributes === attributes && attributes?.observeFilter === filter
      && (!Array.isArray(filter) || (filter.length === filterValues.length
        && Array.prototype.every.call(filter, (value, index) => value === filterValues[index])))
      && attributes?.surfaceMarker === binding.surfaceMarker && pageAdapter?.controllerWallpaper === controller
      && controller?.owner === binding.owner && ports.validPage === binding.validPage
      && ports.shellState === binding.shellState && ports.surfaces === binding.surfaces
      && ports.css === binding.css && ports.scope === binding.scope;
  }

  function wallpaperShellState(isCurrent, binding) {
    if (typeof isCurrent === 'function' && !isCurrent()) return 'cancelled';
    if (!adapterUnchanged(binding)) return 'unsupported';
    if (binding.ports) {
      const state = typeof binding.shellState === 'function'
        ? Reflect.apply(binding.shellState, binding.ports, [isCurrent, host]) : null;
      return adapterUnchanged(binding) ? state : 'unsupported';
    }
    const document = host.document;
    const applicationRoot = document?.getElementById('root');
    return document?.body && applicationRoot
      && applicationRoot.querySelector('[data-app-shell-frame]')
      && applicationRoot.querySelector('[data-app-shell-main-surface],[data-app-shell-page-surface]')
      ? 'ready' : null;
  }

  function waitForWallpaperShell(isCurrent, binding) {
    const document = host.document;
    const initial = wallpaperShellState(isCurrent, binding);
    if (initial) return Promise.resolve(initial);
    const Observer = host.MutationObserver;
    if (typeof Observer !== 'function' || !document?.documentElement) return Promise.resolve('unsupported');

    return new Promise(resolve => {
      let observer;
      let timer;
      let settled = false;
      const finish = state => {
        if (settled) return;
        settled = true;
        observer?.disconnect();
        if (timer !== undefined) host.clearTimeout(timer);
        resolve(state);
      };
      const check = () => {
        const state = wallpaperShellState(isCurrent, binding);
        if (state) finish(state);
      };
      try {
        observer = new Observer(check);
        observer.observe(document.documentElement, {
          childList: true, subtree: true, attributes: true,
          attributeFilter: binding.filterValues
            ?? ['data-app-shell-frame', 'data-app-shell-main-surface', 'data-app-shell-page-surface'],
        });
      } catch {
        finish('unsupported');
        return;
      }
      // Cold hosts can mount the workspace after the startup animation. Keep
      // this wait bounded without extending or replaying the animation.
      timer = host.setTimeout(() => finish(wallpaperShellState(isCurrent, binding) || 'timeout'), 60000);
      check();
    });
  }

  return async function applyWallpaper(value, isCurrent) {
    const image = value?.image;
    if (typeof image !== 'string'
        || typeof host.crypto?.subtle?.digest !== 'function' || typeof host.atob !== 'function') {
      return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'apply-unavailable', imageDecoded: false };
    }
    if (typeof isCurrent === 'function' && !isCurrent()) return { applied: false, reason: 'operation-cancelled' };
    const { strength, surface } = value;
    const binding = captureAdapter();
    const encoded = image.slice(image.indexOf(',') + 1);
    const bytes = Uint8Array.from(host.atob(encoded), character => character.charCodeAt(0));
    const digest = await host.crypto.subtle.digest('SHA-256', bytes);
    const imageSHA256 = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    if (typeof isCurrent === 'function' && !isCurrent()) return { applied: false, reason: 'operation-cancelled' };

    const shellState = await waitForWallpaperShell(isCurrent, binding);
    if (shellState === 'cancelled' || (typeof isCurrent === 'function' && !isCurrent())) {
      return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
    }
    const adapterMatches = adapterUnchanged(binding);
    if (shellState !== 'ready' || !adapterMatches) return { applied: false, reason: 'wallpaper-unsupported',
      failureCode: shellState === 'timeout' && adapterMatches ? 'shell-timeout' : 'shell-unsupported', imageDecoded: false };
    return installRenderer({
      version, image, imageSHA256, css, strength, surface, isCurrent,
      ...(binding.ports ? { pageAdapter } : {}),
    });
  };
}
