export function createWallpaperApplicator(installRenderer, options, host = globalThis) {
  const { version, css } = options;
  const pageAdapter = options.pageAdapter;
  // Continuation is available only while the old renderer calls back, never
  // retained across a wait, another task, or another applicator instance.
  let decodedHandoff = null;
  const ownData = key => {
    if (!pageAdapter || !['object', 'function'].includes(typeof pageAdapter)) return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(pageAdapter, key);
    return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
  };
  const workspaceDeclared = () => !!pageAdapter && ['object', 'function'].includes(typeof pageAdapter)
    && 'workspaceContract' in pageAdapter;

  function captureAdapter() {
    const ports = pageAdapter?.wallpaper;
    const attributes = ports?.attributes;
    const filter = attributes?.observeFilter;
    const controller = pageAdapter?.controllerWallpaper;
    return { ports, attributes, filter, filterValues: Array.isArray(filter) ? [...filter] : filter,
      controller, workspaceDeclared: workspaceDeclared(), workspaceContract: ownData('workspaceContract'),
      observeWorkspace: ownData('observeWorkspace'), workspaceCurrent: ownData('isWorkspaceCurrent'), watchWorkspace: ownData('watchWorkspace'),
      observation: null, workspaceLease: null, workspaceInvalidated: false, owner: controller?.owner, validPage: ports?.validPage, shellState: ports?.shellState,
      surfaces: ports?.surfaces, css: ports?.css, scope: ports?.scope, surfaceMarker: attributes?.surfaceMarker };
  }

  function adapterUnchanged(binding) {
    const { ports, attributes, filter, filterValues, controller } = binding;
    if (pageAdapter?.wallpaper !== ports) return false;
    if (workspaceDeclared() !== binding.workspaceDeclared || ownData('workspaceContract') !== binding.workspaceContract
      || ownData('observeWorkspace') !== binding.observeWorkspace
      || ownData('isWorkspaceCurrent') !== binding.workspaceCurrent
      || ownData('watchWorkspace') !== binding.watchWorkspace) return false;
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
    if (binding.workspaceDeclared || typeof binding.observeWorkspace === 'function') {
      if (binding.ports || binding.workspaceContract !== 'codex-active-workspace/v1'
        || ![binding.observeWorkspace, binding.workspaceCurrent, binding.watchWorkspace].every(value => typeof value === 'function')) return 'unsupported';
      try {
        if (binding.observation) return !binding.workspaceInvalidated && (!binding.workspaceLease || binding.workspaceLease.current())
          && Reflect.apply(binding.workspaceCurrent, pageAdapter, [binding.observation, host]) ? 'ready' : 'cancelled';
        const observed = Reflect.apply(binding.observeWorkspace, pageAdapter, [host]);
        binding.layoutTargets = observed?.layoutTargets ?? [];
        if (observed?.kind === 'pending') return null;
        if (observed?.kind !== 'observed') return binding.waitForWorkspace ? null : 'unsupported';
        binding.observation = observed;
        if (typeof binding.watchWorkspace === 'function') binding.workspaceLease = Reflect.apply(binding.watchWorkspace, pageAdapter,
          [observed, () => { binding.workspaceInvalidated = true; }, host]);
        return binding.workspaceInvalidated ? 'cancelled' : 'ready';
      } catch { return 'unsupported'; }
    }
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

  function waitForWallpaperShell(isCurrent, binding, signal) {
    const document = host.document;
    if (signal?.aborted) return Promise.resolve('cancelled');
    const initial = wallpaperShellState(isCurrent, binding);
    if (initial) return Promise.resolve(initial);
    const Observer = host.MutationObserver;
    if (typeof Observer !== 'function' || !document?.documentElement) return Promise.resolve('unsupported');

    return new Promise(resolve => {
      let observer;
      let resize;
      let resizeTargets = [];
      let timer;
      let onAbort;
      let settled = false;
      const listeners = [];
      const safely = action => { try { action(); } catch {} };
      const finish = state => {
        if (settled) return;
        settled = true;
        safely(() => observer?.disconnect());
        safely(() => resize?.disconnect());
        if (timer !== undefined) safely(() => host.clearTimeout(timer));
        if (onAbort) safely(() => signal.removeEventListener('abort', onAbort));
        for (const [target, event] of listeners) safely(() => target.removeEventListener(event, check));
        resolve(state);
      };
      const refreshResizeTargets = () => {
        if (!resize || settled) return;
        const next = binding.layoutTargets ?? [];
        if (next.length === resizeTargets.length && next.every((node, index) => node === resizeTargets[index])) return;
        resize.disconnect();
        resizeTargets = [...next];
        for (const node of resizeTargets) resize.observe(node);
      };
      const check = () => {
        if (settled) return;
        try {
          const state = wallpaperShellState(isCurrent, binding);
          if (state) finish(state);
          else refreshResizeTargets();
        } catch { finish('unsupported'); }
      };
      try {
        if (signal) {
          if (typeof signal.addEventListener !== 'function' || typeof signal.removeEventListener !== 'function') {
            finish('unsupported');
            return;
          }
          onAbort = () => finish('cancelled');
          signal.addEventListener('abort', onAbort, { once: true });
          if (signal.aborted) {
            finish('cancelled');
            return;
          }
        }
        observer = new Observer(check);
        observer.observe(document.documentElement, {
          childList: true, subtree: true, attributes: true,
          attributeFilter: binding.filterValues
            ?? (typeof binding.observeWorkspace === 'function'
              ? ['data-app-shell-frame', 'data-app-shell-main-surface', 'data-app-shell-page-surface', 'class', 'style', 'hidden']
              : ['data-app-shell-frame', 'data-app-shell-main-surface', 'data-app-shell-page-surface']),
        });
        if (typeof binding.observeWorkspace === 'function') {
          if (typeof host.ResizeObserver === 'function') {
            resize = new host.ResizeObserver(check);
            refreshResizeTargets();
          }
          for (const [target, event] of [[host, 'resize'], [document, 'visibilitychange'], [host, 'hashchange'], [host, 'popstate']]) {
            if (typeof target?.addEventListener !== 'function') continue;
            target.addEventListener(event, check);
            listeners.push([target, event]);
          }
        }
      } catch {
        finish('unsupported');
        return;
      }
      if (settled) return;
      if (signal?.aborted) {
        finish('cancelled');
        return;
      }
      timer = host.setTimeout(() => finish(wallpaperShellState(isCurrent, binding) || 'timeout'), 60000);
      check();
    });
  }

  return async function applyWallpaper(value, isCurrent, signal, workspaceOptions) {
    if (value != null && 'mainPaint' in Object(value)) {
      return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'main-paint-unsupported', imageDecoded: false };
    }
    const image = value?.image;
    if (typeof image !== 'string'
        || typeof host.crypto?.subtle?.digest !== 'function' || typeof host.atob !== 'function') {
      return { applied: false, reason: 'wallpaper-unsupported', failureCode: 'apply-unavailable', imageDecoded: false };
    }
    if (signal?.aborted || (typeof isCurrent === 'function' && !isCurrent())) {
      return { applied: false, reason: 'operation-cancelled' };
    }
    const { strength, surface, themeState } = value;
    const binding = captureAdapter();
    binding.waitForWorkspace = workspaceOptions?.waitForWorkspace === true;
    const onWorkspaceInvalidated = workspaceOptions?.onWorkspaceInvalidated;
    const handoff = !themeState && strength !== 0 && binding.waitForWorkspace
      && decodedHandoff?.image === image ? decodedHandoff : null;
    const notify = typeof onWorkspaceInvalidated === 'function' ? (notice, continuation) => {
      const previous = decodedHandoff;
      decodedHandoff = continuation ?? null;
      try { onWorkspaceInvalidated(notice); }
      finally { decodedHandoff = previous; }
    } : undefined;
    try {
      let reusable = null;
      if (handoff && wallpaperShellState(isCurrent, binding) === 'ready'
        && binding.observation?.documentToken === handoff.documentToken
        && binding.observation.workspaceEpoch > handoff.workspaceEpoch) reusable = handoff;
      if (!reusable && (binding.workspaceDeclared || typeof binding.observeWorkspace === 'function')) {
        const state = await waitForWallpaperShell(isCurrent, binding, signal);
        if (state !== 'ready') return { applied: false, reason: state === 'cancelled' ? 'operation-cancelled' : 'wallpaper-unsupported',
          failureCode: state === 'timeout' ? 'shell-timeout' : 'shell-unsupported', imageDecoded: false };
      }
      let imageSHA256 = reusable?.sha;
      if (!reusable) {
        const encoded = image.slice(image.indexOf(',') + 1);
        const bytes = Uint8Array.from(host.atob(encoded), character => character.charCodeAt(0));
        const digest = await host.crypto.subtle.digest('SHA-256', bytes);
        imageSHA256 = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
      }
      if (binding.workspaceInvalidated || signal?.aborted || (typeof isCurrent === 'function' && !isCurrent())) {
        return { applied: false, reason: 'operation-cancelled' };
      }
      const shellState = reusable ? wallpaperShellState(isCurrent, binding) : await waitForWallpaperShell(isCurrent, binding, signal);
      if (shellState === 'cancelled' || signal?.aborted
        || (typeof isCurrent === 'function' && !isCurrent())) {
        return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
      }
      const adapterMatches = adapterUnchanged(binding);
      if (shellState !== 'ready' || !adapterMatches) return { applied: false, reason: 'wallpaper-unsupported',
        failureCode: shellState === 'timeout' && adapterMatches ? 'shell-timeout' : 'shell-unsupported', imageDecoded: false };
      return await installRenderer({
        version, image, imageSHA256, css, strength, surface, isCurrent,
        ...(signal ? { signal } : {}),
        ...(themeState ? { themeState } : {}),
        ...(workspaceOptions?.transactional === true ? {transactional:true} : {}),
        ...(binding.ports || binding.observation ? { pageAdapter } : {}),
        ...(binding.observation ? { workspaceObservation: binding.observation,
          ...(notify ? { onWorkspaceInvalidated: notify } : {}),
          ...(reusable ? { claimDecodedScene: reusable.claim } : {}),
          ...(typeof workspaceOptions?.onDecodeAdmitted === 'function' ? { onDecodeAdmitted: workspaceOptions.onDecodeAdmitted } : {}) } : {}),
      });
    } finally { binding.workspaceLease?.dispose(); }
  };
}
