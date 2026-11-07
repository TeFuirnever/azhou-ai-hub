// DeepSeek Harness page adapter. Identification is structural and never
// URL-based, unlike the ZCode adapter's pinned file URL. DSH injects no
// controller metadata, so the adapter declares none.
export function createDSHPageAdapter(environment = globalThis, configuration = {}, dependencies = {}) {
  const namespace = Object.freeze({ databaseName: 'azhou-dsh-startup', databaseVersion: 1,
    storeName: 'settings', settingsKey: 'images' });
  let lastDocumentURL, documentNonce;
  function matched(host) {
    if (host !== host.top) return false;
    if (typeof host.__ModuleLoader__?.load !== 'function') return false;
    // __DSH_BOOT__ arrives as an own data property in both the loopback http
    // and the Electron carrier; inherited or accessor forms do not identify
    // this boot graph.
    const boot = Object.getOwnPropertyDescriptor(host, '__DSH_BOOT__');
    return !!boot && Object.hasOwn(boot, 'value') && !!boot.value && !!host.document?.body;
  }
  function identify(host) {
    try {
      if (!matched(host)) return { kind: 'unmatched', reason: 'page-unsupported' };
      if (lastDocumentURL !== host.location.href) {
        documentNonce = host.crypto.randomUUID();lastDocumentURL = host.location.href;
      }
      return { kind: 'matched', documentToken: documentNonce };
    } catch { return { kind: 'unmatched', reason: 'page-unsupported' }; }
  }
  function appearance(host) {
    const root = host.document.documentElement;
    const body = host.document.body;
    // DSH writes its --dsw-* token variables inline on document.body, so the
    // palette is read there; documentElement only carries lang and color-scheme.
    const style = host.getComputedStyle(body ?? root);
    const theme = typeof body?.hasAttribute === 'function'
      ? (body.hasAttribute('data-ds-dark-theme') ? 'dark' : 'light')
      : (host.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'dark' : 'light');
    const colors = {};
    for (const [name, token] of Object.entries({ surface: '--dsw-alias-bg-base', text: '--dsw-alias-label-primary',
      muted: '--dsw-alias-label-secondary', border: '--dsw-alias-border-l3' })) {
      const value = style.getPropertyValue(token).trim();
      if (value && value.length < 100 && !/[;{}]/.test(value) && host.CSS?.supports?.('color', value)) colors[name] = value;
    }
    colors.surface ??= theme === 'dark' ? '#161616' : '#f8f8f8';
    colors.text ??= theme === 'dark' ? '#eeeeee' : '#111111';
    colors.border ??= '#777777';
    return Object.freeze({ locale: /^zh/i.test(root.lang || host.navigator?.language || '') ? 'zh-CN' : 'en',
      theme, colors: Object.freeze(colors), reducedMotion: host.matchMedia?.('(prefers-reduced-motion: reduce)').matches });
  }
  function text(factory, value, themeConfig) {
    if (typeof factory === 'function') return factory({ locale: value.locale, themeConfig });
    const zh = value.locale === 'zh-CN';
    const messages = { openAppearance: zh ? '打开主题与外观' : 'Open appearance settings',
      appearanceLabel: zh ? '阿舟主题与外观' : 'Azhou appearance settings',
      overlayLabel: zh ? '阿舟启动动画' : 'Azhou startup animation',
      'appearance.wallpaper.failure.retry': zh ? '重试背景' : 'Retry wallpaper',
      'appearance.wallpaper.failure.close': zh ? '关闭提示' : 'Dismiss notice' };
    return { t: key => messages[key] ?? String(key) };
  }
  const entries = new Set();
  let inertEntry = null, bodyObserver, observerHost, refreshTimer;
  function releaseEntries() {
    if (refreshTimer !== undefined) observerHost?.clearTimeout?.(refreshTimer);
    refreshTimer = undefined;bodyObserver?.disconnect();bodyObserver = null;
  }
  function observeEntries(host) {
    if (bodyObserver || typeof host.MutationObserver !== 'function' || !host.document?.body) return;
    observerHost = host;
    // One adapter-level body observer replaces per-entry observers: it drives
    // entry re-append and appearance refresh, and its attribute set covers the
    // wallpaper ports' shell inputs, which the wallpaper layer's own observer
    // (seeded from wallpaper.attributes.observeFilter) revalidates.
    bodyObserver = new host.MutationObserver(records => {
      const foreign = record => ![...entries].some(entry => record.target === entry.element
        || entry.element.contains?.(record.target));
      if (!records.some(foreign)) return;
      if (refreshTimer === undefined) refreshTimer = host.setTimeout(() => {
        refreshTimer = undefined;
        for (const entry of entries) entry.refresh();
      }, 0);
    });
    bodyObserver.observe(host.document.body, { childList: true, subtree: true, attributes: true,
      attributeFilter: ['data-slot', 'data-phase', 'data-ds-dark-theme', 'class', 'hidden', 'aria-hidden', 'role'] });
  }
  function mountEntry(document, openSettings, assets, factory, current, host, retryWallpaper, dismissFailure) {
    // sidebarEntry:false keeps every host surface (settings modal) as the only
    // appearance entry on this carrier; the inert handle satisfies the
    // controller's optional entry calls without touching the DOM.
    if (configuration.sidebarEntry === false) {
      inertEntry ??= Object.freeze({ element: null, button: null,
        setAppearance() {}, setWallpaperFailure() {}, update() {}, remove() {} });
      return inertEntry;
    }
    const element = document.createElement('span');
    element.setAttribute('data-agent-skin-entry', 'appearance');
    element.style.cssText = 'display:none;flex:none;position:relative;padding:4px;box-sizing:border-box;app-region:no-drag';
    const shadow = element.attachShadow({ mode: 'open' });
    const style = document.createElement('style');
    style.textContent = ':host{all:initial}button{font:12px system-ui;cursor:pointer;border:1px solid var(--entry-border,#888);border-radius:7px;padding:5px 8px;background:var(--entry-bg,#fff);color:var(--entry-fg,#111)}button:focus-visible{outline:2px solid currentColor;outline-offset:2px}[hidden]{display:none!important}';
    const button = document.createElement('button');button.type = 'button';
    const recovery = document.createElement('span');recovery.hidden = true;recovery.setAttribute('role', 'status');
    const retry = document.createElement('button');retry.type = 'button';
    const close = document.createElement('button');close.type = 'button';
    recovery.append(retry, close);shadow.append(style, button, recovery);
    let visible = false, removed = false, timer, failure = null, diagnosed = false;
    const setAppearance = next => {
      current = next;const t = text(factory, current);
      button.textContent = '阿舟';button.setAttribute('aria-label', t.t('openAppearance'));
      retry.textContent = t.t('appearance.wallpaper.failure.retry');close.textContent = t.t('appearance.wallpaper.failure.close');
      for (const [key, value] of Object.entries({ '--entry-bg': current.colors.surface, '--entry-fg': current.colors.text,
        '--entry-border': current.colors.border })) if (value) element.style.setProperty(key, value);
    };
    function column() {
      const slots = document.querySelectorAll('[data-slot="sidebar.footer.action"]');
      const parent = slots.length === 1 ? slots[0].parentElement : null;
      if (parent) return parent;
      const columns = document.querySelectorAll('[class*="sidebarCol"]');
      return columns.length === 1 ? columns[0] : null;
    }
    function position() {
      timer = undefined;if (removed) return;
      if (!visible) { element.style.display = 'none';return; }
      const target = column();
      if (!target) return hide();
      // The React slot container is owned by re-renders; the stable column
      // keeps this row alive as its last in-flow child.
      if (element.parentElement !== target) target.appendChild(element);
      element.style.display = 'inline-flex';
      const rect = element.getBoundingClientRect(), side = target.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0 || rect.left < side.left || rect.right > side.right
        || rect.top < side.top || rect.bottom > side.bottom) hide();
    }
    function hide() {
      element.style.display = 'none';
      if (!diagnosed) { diagnosed = true;
        host.console?.warn?.('agent-skin: no stable DeepSeek Harness sidebar column, appearance entry stays hidden'); }
    }
    const schedule = () => { if (!removed && timer === undefined) timer = host.setTimeout(position, 0); };
    const refresh = () => { if (removed) return;setAppearance(appearance(host));position(); };
    const onRetry = () => retryWallpaper?.();const onClose = () => { dismissFailure?.();recovery.hidden = true; };
    button.addEventListener('click', openSettings);retry.addEventListener('click', onRetry);close.addEventListener('click', onClose);
    host.addEventListener?.('resize', schedule);setAppearance(current);
    const record = { element, refresh };
    entries.add(record);observeEntries(host);
    return { element, button, setAppearance,
      setWallpaperFailure(value) { failure = value;recovery.hidden = !value;retry.disabled = !!value?.retrying;schedule(); },
      update(value) { visible = !!value;button.disabled = !visible;position(); },
      remove() { if (removed) return;removed = true;
        if (timer !== undefined) host.clearTimeout(timer);
        host.removeEventListener?.('resize', schedule);
        button.removeEventListener('click', openSettings);
        retry.removeEventListener('click', onRetry);close.removeEventListener('click', onClose);
        element.remove();failure = null;entries.delete(record);
        if (!entries.size) releaseEntries();
      },
    };
  }
  function mainSurfaces(host) {
    const nodes = typeof host.document?.querySelectorAll === 'function'
      ? host.document.querySelectorAll('[data-slot="main"]') : [];
    return Array.from(nodes).filter(node => !!node.isConnected
      && !node.closest('[role="dialog"],dialog,iframe,webview'));
  }
  return Object.freeze({
    controllerOwner: 'azhou-dsh-startup',
    controllerWallpaper: Object.freeze({ owner: 'azhou.dsh-startup-animation', requiresControllerMetadata: false }),
    identify(host = environment) { return identify(host); },
    observeAppearance(host = environment) { return appearance(host); },
    appearanceText: text,
    mountEntry,
    settingsEnvironment(source = environment) { return Object.freeze({ indexedDB: source?.indexedDB, settingsNamespace: namespace }); },
    registerCleanup(resource) {
      if (typeof dependencies.registerCleanup !== 'function' || !resource || typeof resource.key !== 'string'
        || typeof resource.dispose !== 'function') return false;
      dependencies.registerCleanup(resource);return true;
    },
    wallpaper: Object.freeze({
      validPage(host = environment) { return matched(host); },
      shellState(isCurrent, host = environment) {
        if (typeof isCurrent === 'function' && !isCurrent()) return 'cancelled';
        if (!matched(host)) return null;
        return mainSurfaces(host).length === 1 ? 'ready' : null;
      },
      surfaces(host = environment) {
        if (!matched(host)) return [];
        const mains = mainSurfaces(host);
        return mains.length === 1 ? mains : [];
      },
      attributes: Object.freeze({ surfaceMarker: 'data-azhou-dsh-wallpaper-surface',
        observeFilter: ['data-slot', 'data-phase', 'data-ds-dark-theme', 'hidden', 'aria-hidden', 'class', 'style'] }),
      css: '\nhtml[data-azhou-wallpaper="active"] #root[data-azhou-dsh-wallpaper-surface="active"],html[data-azhou-wallpaper="active"] [data-slot="main"][data-azhou-dsh-wallpaper-surface="active"],html[data-azhou-wallpaper="active"] #root > [data-slot="root"],html[data-azhou-wallpaper="active"] #root [data-slot="root"] > *,html[data-azhou-wallpaper="active"] #root [data-phase],html[data-azhou-wallpaper="active"] #root [data-slot="root"] > * > *:has([data-slot="main"]){background-color:transparent!important;background-image:none!important}',
      scope: 'decoded image, viewport cover, unique validated DSH main surface; deeper layers separate',
    }),
  });
}
