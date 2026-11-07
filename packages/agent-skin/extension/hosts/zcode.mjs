// ZCode 3.17.2 packaged renderer adapter. No Codex URL/DOM strategy is used.
// Source anchors: desktopHostProcess Hc/loadFile, shared/test-ids sidebar and
// task-settings-button, WorkspaceSidebarFooter and ProjectSidebar (versioned
// source/install parity is local only; live capability evidence stays separate).
export function createZCodePageAdapter(environment = globalThis, configuration = {}, dependencies = {}) {
  const path = '/Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html';
  const keys = new Set(['restoreSession', 'supportsSettings', 'initialWorkspacePath',
    'initialWorkspacePurpose', 'unavailableWorkspacePath', 'windowKind', 'locale', 'zcodeLaunchMarks']);
  const namespace = Object.freeze({ databaseName: 'azhou-zcode-startup', databaseVersion: 1,
    storeName: 'settings', settingsKey: 'images' });
  let lastDocumentURL, documentNonce;
  function identify(host) {
    try {
      if (host !== host.top) return { kind: 'unmatched', reason: 'not-top-level' };
      const url = new URL(host.location.href);
      if (url.protocol !== 'file:' || url.hostname || url.username || url.password || url.hash
        || decodeURIComponent(url.pathname) !== path) return { kind: 'unmatched', reason: 'page-unsupported' };
      const seen = new Set();
      for (const key of url.searchParams.keys()) {
        if (!keys.has(key) || seen.has(key)) return { kind: 'unmatched', reason: 'bootstrap-query-unsupported' };
        seen.add(key);
      }
      if (url.searchParams.has('windowKind') && url.searchParams.get('windowKind') !== 'main') {
        return { kind: 'unmatched', reason: 'auxiliary-window' };
      }
      // URL remains inside this closure. Native metadata carries the actual CDP
      // uniqueContextID; a standalone selector probe uses a separate page nonce.
      if (lastDocumentURL !== host.location.href) {
        documentNonce = host.crypto.randomUUID();lastDocumentURL = host.location.href;
      }
      return { kind: 'matched', documentToken: configuration.controllerMetadata?.documentToken ?? documentNonce };
    } catch { return { kind: 'unmatched', reason: 'page-unsupported' }; }
  }
  function appearance(host) {
    const root = host.document.documentElement;
    const style = host.getComputedStyle(root);
    const theme = root.classList?.contains('dark') || /dark/.test(root.getAttribute?.('data-theme') || '')
      || style.colorScheme === 'dark' ? 'dark' : 'light';
    const colors = {};
    for (const [name, token] of Object.entries({ surface: '--color-background', text: '--color-foreground',
      muted: '--color-foreground-subtle', border: '--color-border' })) {
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
    const messages = { characterName: zh ? '阿舟' : 'Azhou',
      openAppearance: zh ? '打开主题与外观' : 'Open appearance settings',
      appearanceLabel: zh ? '阿舟主题与外观' : 'Azhou appearance settings',
      overlayLabel: zh ? '阿舟启动动画' : 'Azhou startup animation',
      'appearance.wallpaper.failure.retry': zh ? '重试背景' : 'Retry wallpaper',
      'appearance.wallpaper.failure.close': zh ? '关闭提示' : 'Dismiss notice' };
    return { t: key => messages[key] ?? String(key) };
  }
  function mountEntry(document, openSettings, assets, factory, current, host, retryWallpaper, dismissFailure) {
    const element = document.createElement('span');
    element.setAttribute('data-agent-skin-entry', 'appearance');
    element.style.cssText = 'display:none;flex:none;position:relative;box-sizing:border-box;app-region:no-drag';
    const shadow = element.attachShadow({ mode: 'open' });
    const style = document.createElement('style');
    // Mirror the ChatGPT-desktop (Codex host) entry chrome exactly — same
    // avatar/label proportions, surface chip and shadow — per the maintainer's
    // style-parity call; only the CSS variable names differ per host.
    style.textContent = ':host{all:initial}button{all:initial;display:flex;align-items:center;justify-content:flex-start;gap:7px;width:100%;box-sizing:border-box;min-height:44px;padding:5px 9px 5px 5px;cursor:pointer;border:1px solid var(--entry-border,transparent);border-radius:14px;background:var(--entry-bg,transparent);color:var(--entry-fg,#111);box-shadow:0 2px 8px #0002;font:12px/18px -apple-system,BlinkMacSystemFont,sans-serif;white-space:nowrap;text-align:left;outline:2px solid transparent;outline-offset:3px}button:focus-visible{outline-color:currentColor}img{display:block;width:32px;height:32px;border-radius:10px;object-fit:cover;flex:none}.lbl{overflow:hidden;text-overflow:ellipsis}[hidden]{display:none!important}';
    const button = document.createElement('button');button.type = 'button';button.style.minWidth = '44px';
    const label = document.createElement('span');label.className = 'lbl';
    const avatar = assets?.entryAvatar;
    if (typeof avatar === 'string' && avatar.length <= 2 * 1024 * 1024
      && /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(avatar)) {
      const avatarImage = document.createElement('img');avatarImage.alt = '';
      avatarImage.src = avatar;button.append(avatarImage);
    }
    button.append(label);
    const recovery = document.createElement('span');recovery.hidden = true;recovery.setAttribute('role', 'status');
    const retry = document.createElement('button');retry.type = 'button';
    const close = document.createElement('button');close.type = 'button';
    recovery.append(retry, close);shadow.append(style, button, recovery);
    let visible = false, removed = false, timer, failure = null;
    const setAppearance = next => {
      current = next;const t = text(factory, current);
      // Same label formula as the ChatGPT-desktop entry: character name plus
      // the locale-specific Appearance suffix.
      const entryLabel = `${t.t('characterName')}${current.locale === 'zh-CN' ? '外观' : ' Appearance'}`;
      label.textContent = entryLabel;button.setAttribute('aria-label', entryLabel);
      button.title = t.t('openAppearance');
      retry.textContent = t.t('appearance.wallpaper.failure.retry');close.textContent = t.t('appearance.wallpaper.failure.close');
      for (const [key, value] of Object.entries({ '--entry-bg': current.colors.surface, '--entry-fg': current.colors.text,
        '--entry-border': current.colors.border })) if (value) element.style.setProperty(key, value);
    };
    // Stable navigation-label anchor: the entry sits directly beneath the
    // marketplace row in the sidebar's top action group (the placement approved
    // for the ZCode host), never over the account row at the tail. When the
    // label cannot be found — renamed host, other locale, mock DOM without the
    // lookup — the entry falls back to the sidebar tail.
    function marketAnchor(side) {
      const labels = ['Plugin Marketplace', '插件市场'];
      let items;
      try { items = side.querySelectorAll('button, a, [role="button"], [role="menuitem"]'); } catch { return null; }
      for (const node of items) {
        const text = String(node.textContent || '').replace(/\s+/g, ' ').trim();
        if (labels.some(label => text === label || text.includes(label))) return node;
      }
      return null;
    }
    function position() {
      timer = undefined;if (removed) return;
      const sides = document.querySelectorAll('aside[data-testid="sidebar"]');
      if (!visible || sides.length !== 1) { element.style.display = 'none';return; }
      // Own in-flow row: consumes layout space instead of covering controls.
      // Placement is idempotent against the anchor's actual parent (the
      // marketplace row may live inside a nested action group), so a settled
      // entry never re-inserts and never feeds the document observer its own
      // mutation — the self-sustaining position loop the rc38 review caught.
      const anchor = marketAnchor(sides[0]);
      const anchorParent = anchor ? anchor.parentElement : null;
      if (anchor && anchorParent && typeof anchor.insertAdjacentElement === 'function') {
        if (element.parentElement !== anchorParent || anchor.nextSibling !== element) anchor.insertAdjacentElement('afterend', element);
      } else if (element.parentElement !== sides[0]) sides[0].appendChild(element);
      element.style.display = 'block';
      const rect = element.getBoundingClientRect(), side = sides[0].getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0 || rect.left < side.left || rect.right > side.right
        || rect.top < side.top || rect.bottom > side.bottom) element.style.display = 'none';
    }
    const schedule = () => { if (!removed && timer === undefined) timer = host.setTimeout(position, 0); };
    const onRetry = () => retryWallpaper?.();const onClose = () => { dismissFailure?.();recovery.hidden = true; };
    button.addEventListener('click', openSettings);retry.addEventListener('click', onRetry);close.addEventListener('click', onClose);
    const observer = typeof host.MutationObserver === 'function' ? new host.MutationObserver(records => {
      if (records.some(r => r.target !== element && !element.contains(r.target))) schedule();
    }) : null;
    observer?.observe(document.documentElement, { subtree: true, childList: true, attributes: true,
      attributeFilter: ['class', 'hidden', 'aria-hidden'] });
    host.addEventListener?.('resize', schedule);setAppearance(current);
    return { element, button, setAppearance,
      setWallpaperFailure(value) { failure = value;recovery.hidden = !value;retry.disabled = !!value?.retrying;schedule(); },
      update(value) { visible = !!value;button.disabled = !visible;position(); },
      remove() { if (removed) return;removed = true;observer?.disconnect();if (timer !== undefined) host.clearTimeout(timer);
        host.removeEventListener?.('resize', schedule);button.removeEventListener('click', openSettings);
        retry.removeEventListener('click', onRetry);close.removeEventListener('click', onClose);element.remove();failure = null; },
    };
  }
  return Object.freeze({
    controllerOwner: 'azhou-zcode-startup',
    controllerMetadata: configuration.controllerMetadata,
    controllerWallpaper: Object.freeze({ owner: 'azhou.zcode-startup-animation', requiresControllerMetadata: true }),
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
    // Explicit ZCode source selectors for the shared wallpaper assembly port.
    // Live geometry/origin/atomic persistence remain 08 acceptance obligations.
    wallpaper: Object.freeze({
      validPage(host = environment) {
        if (host !== host.top) return false;
        const url = new URL(host.location.href);
        return url.protocol === 'file:' && !url.hostname && !url.username && !url.password && !url.hash
          && decodeURIComponent(url.pathname) === path && identify(host).kind === 'matched';
      },
      shellState(isCurrent, host = environment) {
        if (typeof isCurrent === 'function' && !isCurrent()) return 'cancelled';
        if (identify(host).kind !== 'matched') return null;
        const root = host.document.getElementById('root');
        if (!root || root.querySelectorAll('main').length !== 1 || root.querySelectorAll('aside[data-testid="sidebar"]').length !== 1) return null;
        return 'ready';
      },
      surfaces(host = environment) {
        if (identify(host).kind !== 'matched') return [];
        const root = host.document.getElementById('root');
        return root && root.querySelectorAll('main').length === 1 && root.querySelectorAll('aside[data-testid="sidebar"]').length === 1 ? Array.from(root.querySelectorAll('main')).filter(node => !node.closest('[role="dialog"],iframe,webview')) : [];
      },
      attributes: Object.freeze({ surfaceMarker: 'data-azhou-zcode-wallpaper-surface',
        observeFilter: ['data-testid', 'hidden', 'aria-hidden', 'class', 'style'] }),
      css: '\nhtml[data-azhou-wallpaper="active"] #root[data-azhou-zcode-wallpaper-surface="active"],html[data-azhou-wallpaper="active"] #root main[data-azhou-zcode-wallpaper-surface="active"],html[data-azhou-wallpaper="active"] #root :has(main){background-color:transparent!important;background-image:none!important}',
      scope: 'decoded image, viewport cover, unique validated ZCode main and root surfaces; deeper content layers and visual inspection are separate',
    }),
  });
}
