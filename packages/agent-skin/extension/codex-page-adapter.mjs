// Codex page adapter (agent-skin-zcode-contract/v0.1).
// The Codex host strategy previously inlined in extension/renderer.mjs moved here
// unchanged: main-page identification, host appearance tokens with their existing
// fallbacks, the appearance entry with its navigation-anchor discovery, and the
// settings (IndexedDB) environment injection. The controller receives an instance
// explicitly through bootstrap → installStartup; no imports, no static injection.
export function createCodexPageAdapter(environment = globalThis, configuration = {}, dependencies = {}) {
  // Construction only stores references: no DOM mounting, listeners, observers or
  // database opens happen here. `configuration` carries verified constants only;
  // `dependencies` carries explicit functions such as installRenderer or
  // createWallpaperApplicator when a caller needs them.
  const hostEnvironment = environment;
  const hostConfiguration = configuration;
  const hostDependencies = dependencies;

  const WALLPAPER_FAILURE_MESSAGE_KEYS = Object.freeze({
    'shell-timeout': 'appearance.wallpaper.failure.reason.shellTimeout',
    'shell-unsupported': 'appearance.wallpaper.failure.reason.shellUnsupported',
    'invalid-local-payload': 'appearance.wallpaper.failure.reason.input',
    'invalid-local-image': 'appearance.wallpaper.failure.reason.input',
    'image-decode-failed': 'appearance.wallpaper.failure.reason.decode',
    'image-decode-timeout': 'appearance.wallpaper.failure.reason.decode',
    'unsupported-shell-no-surfaces': 'appearance.wallpaper.failure.reason.surfaces',
    'page-changed-during-decode': 'appearance.wallpaper.failure.reason.page',
    'styles-not-effective': 'appearance.wallpaper.failure.reason.styles',
    'styles-not-effective-after-replacement': 'appearance.wallpaper.failure.reason.styles',
    'namespace-conflict': 'appearance.wallpaper.failure.reason.namespace',
    'namespace-changed-during-decode': 'appearance.wallpaper.failure.reason.namespace',
    'style-id-conflict': 'appearance.wallpaper.failure.reason.style',
    'style-id-conflict-after-decode': 'appearance.wallpaper.failure.reason.style',
    'apply-unavailable': 'appearance.wallpaper.failure.reason.apply',
    'apply-failed': 'appearance.wallpaper.failure.reason.apply',
    'retry-timeout': 'appearance.wallpaper.failure.reason.apply',
  });

  function dataProperty(object, name) {
    if (!object || (typeof object !== 'object' && typeof object !== 'function')) return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(object, name);
    return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
  }
  function isMainPage(host) {
    try {
      const url = new URL(host.location.href);
      if (url.protocol !== 'app:' || url.hostname !== '-' || url.pathname !== '/index.html'
        || url.username || url.password || url.port) return false;
      const route = url.searchParams.get('initialRoute') ?? '/';
      return !/(avatar|quick.?chat|detached|mini|popover|notification)/i.test(route);
    } catch {
      return false;
    }
  }
  // Official settings are reflected on the host root. Read only these attributes
  // and color tokens; never read or maintain a competing preference store.
  function supportedHostColor(host, value) {
    if (typeof value !== 'string') return false;
    const color = value.trim();
    if (!color || color.length > 100 || /[;{}]/.test(color) || /\bvar\s*\(/i.test(color)
      || /^(?:currentcolor|inherit|initial|unset|revert(?:-layer)?)$/i.test(color)) return false;
    try { return typeof host.CSS?.supports === 'function' && host.CSS.supports('color', color); }
    catch { return false; }
  }
  function hostAppearance(host) {
    const root = host.document.documentElement;
    const locale = /^zh(?:-|$)/i.test(root.lang || host.navigator?.language || 'zh-CN') ? 'zh-CN' : 'en';
    let style;
    try { style = host.getComputedStyle?.(root); } catch {}
    const theme = root.dataset?.theme === 'dark' || (!root.dataset?.theme && style?.colorScheme === 'dark')
      ? 'dark' : 'light';
    const colors = {};
    for (const [key, tokens] of Object.entries({
      surface: ['--app-color-background-surface', '--color-surface'],
      text: ['--app-color-text-foreground', '--color-text', '--color-text-primary'],
      muted: ['--app-color-text-foreground-secondary', '--color-text-secondary'],
      border: ['--app-color-border', '--color-border'],
    })) {
      const values = tokens.map(token => style?.getPropertyValue?.(token)?.trim()).filter(Boolean);
      const value = key === 'surface'
        ? values.find(candidate => supportedHostColor(host, candidate)) : values[0];
      if (value) colors[key] = value;
    }
    colors.surface ??= theme === 'light' ? '#ffffff' : '#10121c';
    const reducedMotion = typeof host.matchMedia === 'function'
      ? host.matchMedia('(prefers-reduced-motion: reduce)').matches : undefined;
    return Object.freeze({ locale, theme, colors: Object.freeze(colors), reducedMotion });
  }
  function appearanceText(factory, appearance, themeConfig) {
    if (typeof factory === 'function') return factory({ locale: appearance.locale, themeConfig });
    // Minimal payloads remain supported without a localization factory.
    const messages = appearance.locale === 'zh-CN' ? {
      characterName: '阿舟', openAppearance: '打开主题与外观', appearanceLabel: '阿舟主题与外观',
      overlayLabel: '阿舟启动动画', 'appearance.wallpaper.failure.title': '启动背景未应用',
      'appearance.wallpaper.failure.retry': '重试', 'appearance.wallpaper.failure.retrying': '正在重试…',
      'appearance.wallpaper.failure.retryLabel': '重试启动背景',
      'appearance.wallpaper.failure.retryingLabel': '正在重试启动背景',
      'appearance.wallpaper.failure.close': '关闭提示',
      'appearance.wallpaper.failure.closeLabel': '关闭启动背景失败提示',
      'appearance.wallpaper.failure.reason.shellTimeout': '仍未检测到工作区外壳。',
      'appearance.wallpaper.failure.reason.shellUnsupported': '当前页面暂时无法监测可用的工作区背景区域。',
      'appearance.wallpaper.failure.reason.input': '启动背景设置无效。',
      'appearance.wallpaper.failure.reason.decode': '启动背景图片读取失败。',
      'appearance.wallpaper.failure.reason.surfaces': '当前工作区没有可应用背景的区域。',
      'appearance.wallpaper.failure.reason.page': '页面在应用背景期间发生变化。',
      'appearance.wallpaper.failure.reason.styles': '当前页面未能应用背景样式。',
      'appearance.wallpaper.failure.reason.namespace': '页面中的背景组件发生冲突。',
      'appearance.wallpaper.failure.reason.style': '页面中的背景样式资源发生冲突。',
      'appearance.wallpaper.failure.reason.apply': '当前无法应用背景。',
      'appearance.wallpaper.failure.announcement': '{title}。原因：{reason}你可以重试或关闭提示。',
      'appearance.wallpaper.failure.retryingAnnouncement': '正在重试启动背景。',
      'appearance.wallpaper.failure.appliedAnnouncement': '启动背景已应用。',
      'appearance.wallpaper.failure.closedAnnouncement': '已关闭启动背景失败提示，应用仍可使用。',
      'appearance.wallpaper.failure.retryUnavailableAnnouncement': '未能开始重试。你可以打开主题与外观检查背景设置。',
    } : {
      characterName: 'Azhou', openAppearance: 'Open appearance settings',
      appearanceLabel: 'Azhou appearance settings', overlayLabel: 'Azhou startup animation',
      'appearance.wallpaper.failure.title': 'Startup background not applied',
      'appearance.wallpaper.failure.retry': 'Retry', 'appearance.wallpaper.failure.retrying': 'Retrying…',
      'appearance.wallpaper.failure.retryLabel': 'Retry startup background',
      'appearance.wallpaper.failure.retryingLabel': 'Retrying startup background',
      'appearance.wallpaper.failure.close': 'Dismiss notice',
      'appearance.wallpaper.failure.closeLabel': 'Close startup background notice',
      'appearance.wallpaper.failure.reason.shellTimeout': 'The workspace shell has not appeared yet.',
      'appearance.wallpaper.failure.reason.shellUnsupported': 'This page cannot currently monitor a supported workspace background area.',
      'appearance.wallpaper.failure.reason.input': 'The startup background settings are invalid.',
      'appearance.wallpaper.failure.reason.decode': 'The startup background image could not be read.',
      'appearance.wallpaper.failure.reason.surfaces': 'This workspace has no supported background area.',
      'appearance.wallpaper.failure.reason.page': 'The page changed while the background was being applied.',
      'appearance.wallpaper.failure.reason.styles': 'The page did not apply the background styles.',
      'appearance.wallpaper.failure.reason.namespace': 'The page has a conflicting background component.',
      'appearance.wallpaper.failure.reason.style': 'A background style resource conflicts with another page resource.',
      'appearance.wallpaper.failure.reason.apply': 'The background could not be applied right now.',
      'appearance.wallpaper.failure.announcement': '{title}. Reason: {reason} You can retry or close this notice.',
      'appearance.wallpaper.failure.retryingAnnouncement': 'Retrying the startup background.',
      'appearance.wallpaper.failure.appliedAnnouncement': 'Startup background applied.',
      'appearance.wallpaper.failure.closedAnnouncement': 'Startup background notice closed. The app is still available.',
      'appearance.wallpaper.failure.retryUnavailableAnnouncement': 'The retry could not start. Open appearance settings to check the background.',
    };
    return { t: (key, params) => {
      const template = messages[key] ?? String(key);
      if (!params || typeof params !== 'object') return template;
      return template.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g, (placeholder, name) =>
        Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder);
    } };
  }
  function mountAppearanceEntry(document, openSettings, assets, factory, appearance, host,
    retryWallpaper, dismissWallpaperFailure) {
    const element = document.createElement('div');
    element.setAttribute('data-agent-skin-entry', 'appearance');
    element.style.cssText = 'all:initial;position:fixed;left:10px;bottom:72px;right:auto;top:auto;z-index:2147483646;display:none';
    const shadow = element.attachShadow({ mode: 'open' });
    const button = document.createElement('button');
    // Match the animation's CSSOM path: a host may reject inline <style> blocks.
    // System colors keep this owned control readable in either color scheme.
    button.style.cssText = 'all:initial;visibility:inherit;box-sizing:border-box;display:flex;align-items:center;justify-content:flex-start;gap:7px;cursor:pointer;width:100%;min-height:44px;padding:5px 9px 5px 5px;border:1px solid var(--app-color-border,var(--color-border,transparent));border-radius:14px;background:var(--app-color-background-surface,var(--color-surface,Canvas));color:var(--app-color-text-foreground,var(--color-text,CanvasText));box-shadow:0 2px 8px #0002;font:12px/18px -apple-system,BlinkMacSystemFont,sans-serif;white-space:nowrap;outline:2px solid transparent;outline-offset:3px';
    button.type = 'button';
    button.style.minWidth = '44px';
    const avatar = assets?.entryAvatar;
    let hasAvatar = false;
    if (typeof avatar === 'string' && avatar.length <= 2 * 1024 * 1024
      && /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(avatar)) {
      const image = document.createElement('img');
      image.src = avatar;
      image.setAttribute('alt', '');
      image.style.cssText = 'display:block;width:32px;height:32px;border-radius:10px;object-fit:cover;flex:none';
      button.appendChild(image);
      hasAvatar = true;
    }
    const label = document.createElement('span');
    button.appendChild(label);
    let position = () => {};
    let visible = false;
    let currentTarget = null;
    let activeAppearance = appearance;
    let activeWallpaperFailure = null;
    let retryingWallpaper = false;
    let recoveryVisible = false;
    let renderWallpaperRecovery = () => {};
    const setAppearance = value => {
      activeAppearance = value;
      const text = appearanceText(factory, value, assets?.themeConfig);
      const characterName = text.t('characterName');
      const entryLabel = `${characterName}${value.locale === 'zh-CN' ? '外观' : ' Appearance'}`;
      label.textContent = entryLabel;
      button.title = text.t('openAppearance');
      button.setAttribute('aria-label', entryLabel);
      button.style.colorScheme = value.theme;
      element.setAttribute('lang', value.locale);
      renderWallpaperRecovery();
      position();
    };
    setAppearance(appearance);
    button.setAttribute('aria-haspopup', 'dialog');
    const onFocus = () => { button.style.outlineColor = '#9670bb'; };
    const onBlur = () => { button.style.outlineColor = 'transparent'; };
    button.addEventListener('click', openSettings);
    button.addEventListener('focus', onFocus);
    button.addEventListener('blur', onBlur);

    const recovery = document.createElement('section');
    recovery.setAttribute('data-agent-skin-wallpaper-recovery', '');
    recovery.setAttribute('role', 'group');
    recovery.setAttribute('aria-labelledby', 'agent-skin-wallpaper-recovery-title');
    recovery.setAttribute('aria-describedby', 'agent-skin-wallpaper-recovery-reason');
    recovery.style.cssText = 'display:none;box-sizing:border-box;width:min(280px,calc(100vw - 20px));max-width:calc(100vw - 20px);padding:11px 12px;border:1px solid var(--app-color-border,var(--color-border,#8888));border-radius:12px;background:var(--app-color-background-surface,var(--color-surface,Canvas));color:var(--app-color-text-foreground,var(--color-text,CanvasText));box-shadow:0 4px 14px #0003;font:12px/17px -apple-system,BlinkMacSystemFont,sans-serif;white-space:normal';
    recovery.style.colorScheme = appearance.theme;
    const recoveryTitle = document.createElement('strong');
    recoveryTitle.id = 'agent-skin-wallpaper-recovery-title';
    recoveryTitle.setAttribute('data-agent-skin-wallpaper-title', '');
    recoveryTitle.style.cssText = 'display:block;margin:0 0 4px;font:600 13px/18px -apple-system,BlinkMacSystemFont,sans-serif';
    const recoveryReason = document.createElement('p');
    recoveryReason.id = 'agent-skin-wallpaper-recovery-reason';
    recoveryReason.setAttribute('data-agent-skin-wallpaper-reason', '');
    recoveryReason.style.cssText = 'margin:0 0 9px;font:inherit;white-space:normal';
    const recoveryActions = document.createElement('div');
    recoveryActions.style.cssText = 'display:flex;align-items:center;gap:8px';
    const retryButton = document.createElement('button');
    retryButton.type = 'button';
    retryButton.setAttribute('data-agent-skin-wallpaper-retry', '');
    retryButton.style.cssText = 'all:initial;box-sizing:border-box;min-height:32px;padding:5px 10px;border:1px solid var(--app-color-border,var(--color-border,#8888));border-radius:8px;background:var(--app-color-background-surface,var(--color-surface,Canvas));color:inherit;cursor:pointer;font:600 12px/18px -apple-system,BlinkMacSystemFont,sans-serif;outline:2px solid transparent;outline-offset:2px';
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.setAttribute('data-agent-skin-wallpaper-close', '');
    closeButton.style.cssText = 'all:initial;box-sizing:border-box;min-height:32px;padding:5px 8px;border:1px solid transparent;border-radius:8px;background:transparent;color:inherit;cursor:pointer;font:12px/18px -apple-system,BlinkMacSystemFont,sans-serif;outline:2px solid transparent;outline-offset:2px';
    const onRecoveryFocus = event => { event.currentTarget.style.outlineColor = '#9670bb'; };
    const onRecoveryBlur = event => { event.currentTarget.style.outlineColor = 'transparent'; };
    for (const control of [retryButton, closeButton]) {
      control.addEventListener('focus', onRecoveryFocus);
      control.addEventListener('blur', onRecoveryBlur);
    }
    const announcement = document.createElement('span');
    announcement.setAttribute('data-agent-skin-wallpaper-live', '');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.style.cssText = 'position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0';
    recovery.appendChild(recoveryTitle);
    recovery.appendChild(recoveryReason);
    recoveryActions.appendChild(retryButton);
    recoveryActions.appendChild(closeButton);
    recovery.appendChild(recoveryActions);
    shadow.appendChild(button);
    shadow.appendChild(recovery);
    shadow.appendChild(announcement);
    element.style.display = 'none';
    document.documentElement.appendChild(element);

    const currentText = () => appearanceText(factory, activeAppearance, assets?.themeConfig);
    const setAnnouncement = (key, params) => {
      announcement.textContent = key ? currentText().t(key, params) : '';
    };
    const renderRecoveryControls = () => {
      const text = currentText();
      const failure = activeWallpaperFailure;
      const messageKey = failure && WALLPAPER_FAILURE_MESSAGE_KEYS[failure.failureCode];
      recoveryVisible = !!messageKey;
      recovery.style.display = recoveryVisible ? 'block' : 'none';
      recovery.style.colorScheme = activeAppearance.theme;
      retryButton.textContent = text.t(retryingWallpaper
        ? 'appearance.wallpaper.failure.retrying' : 'appearance.wallpaper.failure.retry');
      retryButton.setAttribute('aria-label', text.t(retryingWallpaper
        ? 'appearance.wallpaper.failure.retryingLabel' : 'appearance.wallpaper.failure.retryLabel'));
      retryButton.disabled = retryingWallpaper || !recoveryVisible;
      closeButton.textContent = text.t('appearance.wallpaper.failure.close');
      closeButton.setAttribute('aria-label', text.t('appearance.wallpaper.failure.closeLabel'));
      closeButton.disabled = !recoveryVisible;
      if (!recoveryVisible) return;
      const title = text.t('appearance.wallpaper.failure.title');
      const reason = text.t(messageKey);
      recoveryTitle.textContent = title;
      recoveryReason.textContent = reason;
    };
    renderWallpaperRecovery = (announcementKey, announceFailure = true) => {
      renderRecoveryControls();
      if (announcementKey === 'retrying') {
        setAnnouncement('appearance.wallpaper.failure.retryingAnnouncement');
      } else if (announcementKey === 'applied') {
        setAnnouncement('appearance.wallpaper.failure.appliedAnnouncement');
      } else if (announcementKey === 'closed') {
        setAnnouncement('appearance.wallpaper.failure.closedAnnouncement');
      } else if (announcementKey === 'retryUnavailable') {
        setAnnouncement('appearance.wallpaper.failure.retryUnavailableAnnouncement');
      } else if (recoveryVisible && announceFailure) {
        const text = currentText();
        setAnnouncement('appearance.wallpaper.failure.announcement', {
          title: recoveryTitle.textContent, reason: recoveryReason.textContent,
        });
      } else if (!recoveryVisible && announcementKey !== 'preserve') {
        setAnnouncement('');
      }
    };
    const setWallpaperFailure = (failure, announcementKey) => {
      activeWallpaperFailure = failure && WALLPAPER_FAILURE_MESSAGE_KEYS[failure.failureCode]
        ? { failureCode: failure.failureCode } : null;
      renderWallpaperRecovery(announcementKey);
      position();
    };
    const setRetrying = value => {
      retryingWallpaper = value;
      renderWallpaperRecovery(value ? 'retrying' : 'preserve', false);
    };
    const focusAppearanceButton = () => {
      try { button.focus({ preventScroll: true }); } catch { try { button.focus(); } catch {} }
    };
    const recoveryOwnsFocus = () => shadow.activeElement === retryButton || shadow.activeElement === closeButton;
    const focusWasLostByDisablingRetry = () => [element, document.body, document.documentElement]
      .includes(document.activeElement);
    const onRetry = () => {
      if (retryingWallpaper || !activeWallpaperFailure) return;
      const retryHadFocus = recoveryOwnsFocus();
      setRetrying(true);
      let result;
      try { result = retryWallpaper?.(); }
      catch { result = Promise.reject(new Error('wallpaper retry failed')); }
      Promise.resolve(result).then(value => {
        setRetrying(false);
        if (value?.wallpaper?.applied) {
          const restoreFocus = recoveryOwnsFocus() || (retryHadFocus && focusWasLostByDisablingRetry());
          setWallpaperFailure(null, 'applied');
          if (restoreFocus) focusAppearanceButton();
        } else if (!value?.retried && value?.reason
          && !['operation-cancelled', 'disposed'].includes(value.reason)) {
          renderWallpaperRecovery('retryUnavailable');
        }
      }, () => {
        setRetrying(false);
        renderWallpaperRecovery('retryUnavailable');
      });
    };
    const onCloseRecovery = () => {
      const restoreFocus = recoveryOwnsFocus();
      dismissWallpaperFailure?.();
      setWallpaperFailure(null, 'closed');
      if (restoreFocus) focusAppearanceButton();
    };
    retryButton.addEventListener('click', onRetry);
    closeButton.addEventListener('click', onCloseRecovery);
    setAppearance(appearance);
    const page = document.documentElement.ownerDocument ?? document;
    let observer, pending;
    const tagName = node => String(node?.tagName ?? '').toUpperCase();
    const getNavAncestor = node => {
      for (let current = node; current; current = current.parentElement ?? current.parentNode) {
        if (tagName(current) === 'NAV') return current;
      }
      return null;
    };
    const navigationTargetSelector = 'nav a[href], nav > :first-child > [class~="group/nav-list"] button';
    const isHomeNavigationButton = node => {
      if (tagName(node) !== 'BUTTON') return false;
      let container = node.parentElement ?? node.parentNode;
      while (container && tagName(container) !== 'NAV') {
        const classes = container.getAttribute?.('class') ?? container.className ?? '';
        if (String(classes).split(/\s+/).includes('group/nav-list')) break;
        container = container.parentElement ?? container.parentNode;
      }
      const header = container?.parentElement ?? container?.parentNode;
      const nav = getNavAncestor(node);
      const classes = container?.getAttribute?.('class') ?? container?.className ?? '';
      return !!nav && (nav.firstElementChild ?? nav.children?.[0]) === header
        && String(classes).split(/\s+/).includes('group/nav-list');
    };
    const isAppearanceNavigationNode = node => {
      const name = node.getAttribute?.('aria-label') ?? node.textContent ?? '';
      if (!isAppearanceAnchorName(name)) return false;
      return tagName(node) === 'A' ? Boolean(getNavAncestor(node)) : isHomeNavigationButton(node);
    };
    const isVisibleNavigation = node => {
      for (let current = node; current; current = current.parentElement ?? current.parentNode) {
        if (current.hidden || current.getAttribute?.('aria-hidden') === 'true') return false;
        let style;
        try { style = host.getComputedStyle?.(current); } catch {}
        const display = style?.getPropertyValue?.('display') || style?.display;
        const visibility = style?.getPropertyValue?.('visibility') || style?.visibility;
        const contentVisibility = style?.getPropertyValue?.('content-visibility') || style?.contentVisibility;
        const opacity = style?.getPropertyValue?.('opacity') || style?.opacity;
        if (display === 'none' || visibility === 'hidden' || visibility === 'collapse'
          || contentVisibility === 'hidden' || (opacity !== '' && Number(opacity) === 0)) return false;
        // display: contents ancestors have no box; their children can still be visible.
        if (display !== 'contents' && typeof current.getBoundingClientRect === 'function') {
          try {
            const bounds = current.getBoundingClientRect();
            if (bounds.width <= 0 || bounds.height <= 0) return false;
          } catch { return false; }
        }
        if (current === document.documentElement) break;
      }
      return true;
    };
    const hostControlSelector = 'button, a[href], [role="button"], [role="textbox"], input, textarea, select, [contenteditable="true"], [data-composer-layout]';
    const hasUsableHostControl = () => {
      // Shell markers can lag or change while the host is loading. Reveal a fallback
      // only when a page control has visible geometry, no hidden ancestor, and can receive a hit;
      // mutations retry it when the host replaces or reveals its shell.
      let appRoot = page.getElementById?.('root') ?? document.body;
      if (typeof appRoot?.querySelectorAll !== 'function') appRoot = page;
      if (typeof appRoot?.querySelectorAll !== 'function') return false;
      let controls;
      try { controls = Array.from(appRoot.querySelectorAll(hostControlSelector)); } catch { return false; }
      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = document.documentElement.clientHeight;
      return controls.some(control => {
        for (let current = control; current; current = current.parentElement ?? current.parentNode) {
          if (current.hidden || current.getAttribute?.('aria-hidden') === 'true') return false;
          let style;
          try { style = host.getComputedStyle?.(current); } catch {}
          const display = style?.getPropertyValue?.('display') || style?.display;
          const visibility = style?.getPropertyValue?.('visibility') || style?.visibility;
          const contentVisibility = style?.getPropertyValue?.('content-visibility') || style?.contentVisibility;
          const opacity = style?.getPropertyValue?.('opacity') || style?.opacity;
          if (display === 'none' || visibility === 'hidden' || visibility === 'collapse'
            || contentVisibility === 'hidden' || (opacity !== '' && Number(opacity) === 0)) return false;
          if (current === document.documentElement) break;
        }
        let bounds;
        try { bounds = control.getBoundingClientRect(); } catch { return false; }
        if (!bounds || bounds.width <= 0 || bounds.height <= 0
          || bounds.left >= viewportWidth || bounds.right <= 0
          || bounds.top >= viewportHeight || bounds.bottom <= 0) return false;
        if (typeof page.elementFromPoint !== 'function') return true;
        const insetX = Math.min(3, bounds.width / 4);
        const insetY = Math.min(3, bounds.height / 4);
        const points = [
          [bounds.left + bounds.width / 2, bounds.top + bounds.height / 2],
          [bounds.left + insetX, bounds.top + insetY],
          [bounds.right - insetX, bounds.bottom - insetY],
        ];
        return points.some(([x, y]) => {
          let target;
          try { target = page.elementFromPoint(x, y); } catch { return false; }
          return target === control || control.contains?.(target) === true;
        });
      });
    };
    const applyEntryLayout = () => {
      element.style.display = visible ? (recoveryVisible ? 'flex' : 'block') : 'none';
      element.style.flexDirection = recoveryVisible ? 'column-reverse' : '';
      element.style.alignItems = recoveryVisible ? 'flex-start' : '';
      element.style.gap = recoveryVisible ? '8px' : '';
      button.style.width = recoveryVisible ? 'max-content' : '100%';
      button.style.alignSelf = recoveryVisible ? 'flex-start' : '';
    };
    const isAppearanceAnchorName = value => {
      const name = String(value).trim().replace(/\s+/g, ' ').toLocaleLowerCase();
      return name === 'your dot' || name === '你的 dot';
    };
    const findNavigationTarget = () => {
      if (typeof page.querySelectorAll !== 'function') return null;
      let anchors;
      try { anchors = Array.from(page.querySelectorAll(navigationTargetSelector)); } catch { return null; }
      const matches = anchors.filter(anchor => {
        return isAppearanceNavigationNode(anchor) && isVisibleNavigation(anchor);
      });
      if (matches.length !== 1) return null;
      const anchor = matches[0];
      const nav = getNavAncestor(anchor);
      const anchorParent = anchor.parentElement ?? anchor.parentNode;
      let row, container;
      if (isHomeNavigationButton(anchor)) {
        const listItem = anchor.closest?.('[role="listitem"]');
        const list = listItem?.parentElement;
        const group = list?.parentElement;
        const groupClasses = group?.getAttribute?.('class') ?? group?.className ?? '';
        if (list?.getAttribute?.('role') === 'list'
          && String(groupClasses).split(/\s+/).includes('group/nav-list')) {
          row = listItem;
          container = list;
        } else if (String(anchorParent?.getAttribute?.('class') ?? anchorParent?.className ?? '')
          .split(/\s+/).includes('group/nav-list')) {
          row = anchor;
          container = anchorParent;
        }
      } else if (anchorParent === nav) {
        row = anchor;
        container = nav;
      } else if ((anchorParent?.parentElement ?? anchorParent?.parentNode) === nav) {
        row = anchorParent;
        container = nav;
      } else if (tagName(anchorParent) === 'LI') {
        const list = anchorParent.parentElement ?? anchorParent.parentNode;
        if (tagName(list) === 'UL' && (list.parentElement ?? list.parentNode) === nav) {
          row = anchorParent;
          container = list;
        }
      }
      if (!row || !container || typeof container.insertBefore !== 'function') return null;
      return { anchor, nav, row, container };
    };
    const fallbackControls = () => {
      try {
        return Array.from(page.querySelectorAll(hostControlSelector))
          .map(control => ({ control, bounds: control.getBoundingClientRect?.() }))
          .filter(({ control, bounds }) => {
            if (!bounds || bounds.width <= 0 || bounds.height <= 0
              || bounds.top >= document.documentElement.clientHeight || bounds.bottom <= 0) return false;
            const style = host.getComputedStyle?.(control);
            const visibility = style?.getPropertyValue?.('visibility') || style?.visibility;
            if (visibility === 'hidden' || visibility === 'collapse') return false;
            // A control whose own content is hidden can still receive pointer events.
            for (let current = control.parentElement; current; current = current.parentElement) {
              const currentStyle = host.getComputedStyle?.(current);
              const contentVisibility = currentStyle?.getPropertyValue?.('content-visibility') || currentStyle?.contentVisibility;
              if (contentVisibility === 'hidden') return false;
            }
            return true;
          });
      } catch {
        return [];
      }
    };
    const findFallbackPosition = () => {
      if (!visible || typeof element.getBoundingClientRect !== 'function') return null;
      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = document.documentElement.clientHeight;
      if (!viewportWidth || !viewportHeight) return null;
      const rect = element.getBoundingClientRect();
      const height = rect.height || 44;
      const width = Math.max(rect.width || 0, hasAvatar ? 48 : 120);
      const controls = fallbackControls();
      const desired = Math.max(8, Math.min(viewportHeight - height - 8, viewportHeight - 72 - height));
      const columns = [10, ...controls.map(({ bounds }) => bounds.right + 8)]
        .filter(left => left >= 8 && left + width <= viewportWidth - 8)
        .sort((a, b) => a - b);
      for (const left of columns) {
        const columnControls = controls.filter(({ bounds }) => bounds.left < left + width + 8 && bounds.right + 8 > left);
        const candidates = [desired, 8, viewportHeight - height - 8,
          ...columnControls.flatMap(({ bounds }) => [bounds.top - height - 8, bounds.bottom + 8])];
        const available = candidates.filter(top => top >= 8 && top + height <= viewportHeight - 8
          && columnControls.every(({ bounds }) => top + height + 8 <= bounds.top || top >= bounds.bottom + 8));
        if (available.length) {
          const top = available.reduce((best, candidate) =>
            Math.abs(candidate - desired) < Math.abs(best - desired) ? candidate : best);
          return { left, top };
        }
      }
      return null;
    };
    const showFallback = () => {
      currentTarget = null;
      element.style.position = 'fixed';
      element.style.left = '10px';
      element.style.right = 'auto';
      element.style.top = 'auto';
      element.style.bottom = '72px';
      element.style.zIndex = '2147483646';
      element.style.width = 'max-content';
      applyEntryLayout();
      label.style.display = '';
      if (element.parentNode !== document.documentElement) document.documentElement.appendChild(element);
      let placement = findFallbackPosition();
      if (placement === null && hasAvatar) {
        label.style.display = 'none';
        placement = findFallbackPosition();
      }
      if (placement !== null) {
        element.style.left = `${placement.left}px`;
        element.style.top = `${placement.top}px`;
        element.style.bottom = 'auto';
      } else {
        // No unobstructed position exists; retry when the layout changes.
        element.style.display = 'none';
      }
    };
    const showNavigationRow = target => {
      currentTarget = target;
      element.style.position = 'static';
      element.style.left = '';
      element.style.right = '';
      element.style.top = '';
      element.style.bottom = '';
      element.style.zIndex = '';
      element.style.width = '100%';
      applyEntryLayout();
      const next = target.row.nextSibling ?? null;
      if (element.parentNode !== target.container || next !== element) {
        target.container.insertBefore(element, next);
      }
      let width = 0;
      try { width = target.container.getBoundingClientRect?.().width ?? target.nav.getBoundingClientRect?.().width ?? 0; } catch {}
      label.style.display = width > 0 && width < 116 ? 'none' : '';
    };
    const hideUntilHostIsUsable = () => {
      currentTarget = null;
      element.style.position = 'fixed';
      element.style.left = '10px';
      element.style.right = 'auto';
      element.style.top = 'auto';
      element.style.bottom = '72px';
      element.style.zIndex = '2147483646';
      element.style.width = 'max-content';
      label.style.display = '';
      element.style.display = 'none';
      if (element.parentNode !== document.documentElement) document.documentElement.appendChild(element);
    };
    position = () => {
      const target = findNavigationTarget();
      if (target) {
        showNavigationRow(target);
        return;
      }
      if (!visible) {
        hideUntilHostIsUsable();
        return;
      }
      // The host-usability gate defers only the plain floating entry. Two states
      // keep the entry revealed without host controls: a pending wallpaper
      // failure notice (its message — "the workspace shell has not appeared" —
      // is precisely about the host not being ready, so hiding it would swallow
      // the failure), and keyboard focus inside this entry (hiding a focused
      // control would dump focus to the body and strand keyboard users).
      if (hasUsableHostControl() || recoveryVisible
        || shadow.activeElement === button || recoveryOwnsFocus()) showFallback();
      else hideUntilHostIsUsable();
    };
    const isPotentialNavigationNode = node => {
      if (!node) return false;
      if (tagName(node) === 'NAV') return true;
      if (isAppearanceNavigationNode(node)) return true;
      try { return Boolean(node.querySelector?.(navigationTargetSelector) || node.querySelector?.('a[href]')); } catch { return false; }
    };
    const isPotentialHostControlNode = node => {
      if (!node || node === element) return false;
      try { return Boolean(node.matches?.(hostControlSelector) || node.querySelector?.(hostControlSelector)); }
      catch { return false; }
    };
    const touchesFallbackColumn = node => {
      if (typeof node?.getBoundingClientRect !== 'function') return false;
      try {
        if (element.style.display === 'none'
          && (node.matches?.('button, a[href], [role="button"], input, textarea, select')
            || node.querySelector?.('button, a[href], [role="button"], input, textarea, select'))) return true;
        const bounds = node.getBoundingClientRect();
        const entry = element.getBoundingClientRect?.();
        const width = Math.max(entry?.width ?? 0, hasAvatar ? 48 : 120);
        const preferredColumn = bounds.left < 10 + width && bounds.right > 10;
        const currentPosition = entry?.width > 0 && entry?.height > 0
          && bounds.left < entry.right + 8 && bounds.right + 8 > entry.left
          && bounds.top < entry.bottom + 8 && bounds.bottom + 8 > entry.top;
        return bounds.width > 0 && (preferredColumn || currentPosition);
      } catch { return false; }
    };
    const isNavigationRelatedNode = node => {
      if (!node) return false;
      if (tagName(node) === 'NAV') return true;
      try {
        return Array.from(page.querySelectorAll(navigationTargetSelector)).some(anchor => {
          for (let current = anchor; current; current = current.parentElement ?? current.parentNode) {
            if (current === node) return true;
          }
          return false;
        });
      } catch { return false; }
    };
    const isNavigationMutation = record => {
      const target = record.target;
      if (target === element) return false;
      if (target === currentTarget?.anchor || target === currentTarget?.row
        || target === currentTarget?.container || target === currentTarget?.nav
        || target === currentTarget?.nav.parentNode || target === document.documentElement) return true;
      if (currentTarget && (currentTarget.nav.contains?.(target) || target?.contains?.(currentTarget.nav))) return true;
      if (isNavigationRelatedNode(target)) return true;
      if (!currentTarget && touchesFallbackColumn(target)) return true;
      if (!currentTarget && record.type === 'attributes'
        && isPotentialHostControlNode(target)) return true;
      if (record.type === 'childList') {
        return [...(record.addedNodes ?? []), ...(record.removedNodes ?? [])]
          .some(node => isPotentialNavigationNode(node) || isNavigationRelatedNode(node)
            || (!currentTarget && (touchesFallbackColumn(node) || isPotentialHostControlNode(node))));
      }
      if (record.type === 'attributes') return target === currentTarget?.anchor;
      return false;
    };
    const schedule = () => {
      if (pending !== undefined || !visible) return;
      pending = host.setTimeout(() => { pending = undefined; position(); }, 80);
    };
    const onScroll = () => schedule();
    if (typeof host.MutationObserver === 'function') {
      observer = new host.MutationObserver(records => {
        if (records.some(isNavigationMutation)) schedule();
      });
      observer.observe(document.documentElement, { subtree: true, childList: true, attributes: true,
        attributeFilter: ['aria-label', 'href', 'class', 'style', 'hidden', 'aria-hidden', 'role', 'contenteditable', 'data-composer-layout'] });
    }
    host.addEventListener?.('resize', schedule);
    host.addEventListener?.('scroll', onScroll, true);
    position();
    return {
      element, button, setAppearance, setWallpaperFailure,
      update(value) {
        visible = value;
        button.disabled = !value;
        if (value) position();
        else applyEntryLayout();
      },
      remove() {
        observer?.disconnect();
        if (pending !== undefined) host.clearTimeout(pending);
        host.removeEventListener?.('resize', schedule);
        host.removeEventListener?.('scroll', onScroll, true);
        button.removeEventListener('click', openSettings);
        button.removeEventListener('focus', onFocus);
        button.removeEventListener('blur', onBlur);
        retryButton.removeEventListener('click', onRetry);
        closeButton.removeEventListener('click', onCloseRecovery);
        for (const control of [retryButton, closeButton]) {
          control.removeEventListener('focus', onRecoveryFocus);
          control.removeEventListener('blur', onRecoveryBlur);
        }
        element.remove();
      },
    };
  }
  return Object.freeze({
    identify(host = hostEnvironment) {
      if (!host || !isMainPage(host)) return { kind: 'unmatched', reason: 'page-unsupported' };
      let documentToken = '';
      try { documentToken = String(host.location?.href ?? ''); } catch { documentToken = ''; }
      return { kind: 'matched', documentToken };
    },
    observeAppearance(host = hostEnvironment) {
      return hostAppearance(host);
    },
    appearanceText(factory, appearance, themeConfig) {
      return appearanceText(factory, appearance, themeConfig);
    },
    // Known limit (C0): the entry node's cleanup stays owned directly by the page
    // controller's existing dispose path; mountEntry deliberately takes no cleanup
    // registry so the adapter cannot claim a second lifecycle of the same node
    // (spec §6.4). Adapter-created resources use registerCleanup below instead.
    mountEntry(document, openSettings, assets, factory, appearance, host,
      retryWallpaper, dismissWallpaperFailure) {
      return mountAppearanceEntry(document, openSettings, assets, factory, appearance, host,
        retryWallpaper, dismissWallpaperFailure);
    },
    settingsEnvironment(source = hostEnvironment) {
      // Returning the environment opens no database; callers inject it into their
      // own settings factory.
      return Object.freeze({ indexedDB: source?.indexedDB });
    },
    registerCleanup(resource) {
      // Forward adapter-created resources to the controller-owned registry when
      // one was provided in dependencies; refuse (false) instead of accumulating a
      // second ownership list.
      const register = hostDependencies?.registerCleanup;
      if (typeof register !== 'function'
          || !resource || typeof resource.key !== 'string' || typeof resource.dispose !== 'function') {
        return false;
      }
      register(resource);
      return true;
    },
  });
}
