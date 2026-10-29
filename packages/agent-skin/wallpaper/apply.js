export function createWallpaperApplicator(installRenderer, options, host = globalThis) {
  const { version, css } = options;

  function wallpaperShellState(isCurrent) {
    if (typeof isCurrent === 'function' && !isCurrent()) return 'cancelled';
    const document = host.document;
    const applicationRoot = document?.getElementById('root');
    return document?.body && applicationRoot
      && applicationRoot.querySelector('[data-app-shell-frame]')
      && applicationRoot.querySelector('[data-app-shell-main-surface],[data-app-shell-page-surface]')
      ? 'ready' : null;
  }

  function waitForWallpaperShell(isCurrent) {
    const document = host.document;
    const initial = wallpaperShellState(isCurrent);
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
        const state = wallpaperShellState(isCurrent);
        if (state) finish(state);
      };
      try {
        observer = new Observer(check);
        observer.observe(document.documentElement, {
          childList: true, subtree: true, attributes: true,
          attributeFilter: ['data-app-shell-frame', 'data-app-shell-main-surface', 'data-app-shell-page-surface'],
        });
      } catch {
        finish('unsupported');
        return;
      }
      // Cold hosts can mount the workspace after the startup animation. Keep
      // this wait bounded without extending or replaying the animation.
      timer = host.setTimeout(() => finish(wallpaperShellState(isCurrent) || 'timeout'), 60000);
      check();
    });
  }

  return async function applyWallpaper(value, isCurrent) {
    if (!value || typeof value.image !== 'string'
        || typeof host.crypto?.subtle?.digest !== 'function' || typeof host.atob !== 'function') {
      return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'apply-unavailable', imageDecoded: false };
    }
    if (typeof isCurrent === 'function' && !isCurrent()) return { applied: false, reason: 'operation-cancelled' };
    const encoded = value.image.slice(value.image.indexOf(',') + 1);
    const bytes = Uint8Array.from(host.atob(encoded), character => character.charCodeAt(0));
    const digest = await host.crypto.subtle.digest('SHA-256', bytes);
    const imageSHA256 = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    if (typeof isCurrent === 'function' && !isCurrent()) return { applied: false, reason: 'operation-cancelled' };

    const shellState = await waitForWallpaperShell(isCurrent);
    if (shellState === 'cancelled' || (typeof isCurrent === 'function' && !isCurrent())) {
      return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
    }
    if (shellState !== 'ready') return { applied: false, reason: 'wallpaper-unsupported',
      failureCode: shellState === 'timeout' ? 'shell-timeout' : 'shell-unsupported', imageDecoded: false };
    return installRenderer({
      version, image: value.image, imageSHA256, css,
      strength: value.strength, surface: value.surface, isCurrent,
    });
  };
}
