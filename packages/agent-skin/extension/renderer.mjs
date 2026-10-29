const GLOBAL_NAME = '__azhouStartup';
const WALLPAPER_GLOBAL = '__azhouWallpaper';
const OWNER = 'azhou-codex-startup';
const VERSION = 1;
const LEGACY_WALLPAPER_OWNER = 'azhou.codex-startup-animation';
const WALLPAPER_VERSIONS = new Set(['0.7.1', '0.8.0', '0.9.0']);
const PAGE_REASON = 'page-unsupported';
const ASSET_REASON = 'asset-invalid';
const FIXED_PAGE_REASONS = new Set(['asset-invalid', 'storage-unavailable']);
const BACKGROUND_DATA_URL = /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/;
const WALLPAPER_STATUS_FIELDS = [
  'backgroundMatched', 'washMatched', 'coverMatched', 'fixedViewport', 'matchedSurfaces', 'transparentSurfaces',
  'rootClear', 'workspaceBackgroundClear', 'footerSurfaces', 'footerBackgroundClear',
  'footerFadeSurfaces', 'footerFadeClear', 'topFadeSurfaces', 'topFadeClear',
  'decorationEffectsClear', 'unsupportedDecorations', 'verificationScope',
];
const WALLPAPER_FAILURE_STAGES = Object.freeze({
  'shell-timeout': 'shell',
  'shell-unsupported': 'shell',
  'invalid-local-payload': 'input',
  'invalid-local-image': 'input',
  'image-decode-failed': 'decode',
  'image-decode-timeout': 'decode',
  'unsupported-shell-no-surfaces': 'surfaces',
  'page-changed-during-decode': 'page',
  'styles-not-effective': 'styles',
  'styles-not-effective-after-replacement': 'styles',
  'namespace-conflict': 'namespace',
  'namespace-changed-during-decode': 'namespace',
  'style-id-conflict': 'style',
  'style-id-conflict-after-decode': 'style',
  'apply-unavailable': 'apply',
  'apply-failed': 'apply',
  'retry-timeout': 'apply',
});
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
const WALLPAPER_RETRY_TIMEOUT_MS = 10_000;
let nextRunId = 1;

function dataProperty(object, name) {
  if (!object || (typeof object !== 'object' && typeof object !== 'function')) return undefined;
  const descriptor = Object.getOwnPropertyDescriptor(object, name);
  return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
}

function wallpaperFailure(value) {
  try {
    const raw = dataProperty(value, 'failureCode') ?? dataProperty(value, 'code');
    if (typeof raw !== 'string' || !Object.hasOwn(WALLPAPER_FAILURE_STAGES, raw)) return null;
    return { failureStage: WALLPAPER_FAILURE_STAGES[raw], failureCode: raw };
  } catch {
    return null;
  }
}

function wallpaperReason(value, fallback = 'wallpaper-unsupported') {
  try {
    const reason = dataProperty(value, 'reason');
    return ['wallpaper-unsupported', 'disabled', 'operation-cancelled', 'owner-conflict', 'not-installed'].includes(reason)
      ? reason : fallback;
  } catch {
    return fallback;
  }
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

function existingController(host) {
  const descriptor = Object.getOwnPropertyDescriptor(host, GLOBAL_NAME);
  if (!descriptor) return { present: false };
  if (!Object.hasOwn(descriptor, 'value') || !descriptor.value || typeof descriptor.value !== 'object') {
    return { present: true, owned: false };
  }
  const api = descriptor.value;
  return {
    present: true,
    owned: dataProperty(api, 'owner') === OWNER
      && dataProperty(api, 'version') === VERSION
      && typeof dataProperty(api, 'status') === 'function'
      && typeof dataProperty(api, 'openSettings') === 'function'
      && typeof dataProperty(api, 'dispose') === 'function',
  };
}

function wallpaperRecord(host) {
  const descriptor = Object.getOwnPropertyDescriptor(host, WALLPAPER_GLOBAL);
  if (!descriptor) return { present: false, supported: false, api: null };
  if (!Object.hasOwn(descriptor, 'value') || !descriptor.value || typeof descriptor.value !== 'object') {
    return { present: true, supported: false, api: null };
  }
  const api = descriptor.value;
  const supported = dataProperty(api, 'owner') === LEGACY_WALLPAPER_OWNER
    && WALLPAPER_VERSIONS.has(dataProperty(api, 'version'))
    && typeof dataProperty(api, 'status') === 'function'
    && typeof dataProperty(api, 'dispose') === 'function';
  return { present: true, supported, api: supported ? api : null };
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
  const navigationTargetSelector = 'nav a[href], nav > :first-child > [class~="group/nav-list"] > button';
  const isHomeNavigationButton = node => {
    if (tagName(node) !== 'BUTTON') return false;
    const container = node.parentElement ?? node.parentNode;
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
      if (display === 'none' || visibility === 'hidden' || visibility === 'collapse' || contentVisibility === 'hidden') return false;
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
      row = anchor;
      container = anchorParent;
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
      return Array.from(page.querySelectorAll('button, a[href], [role="button"], input, textarea, select'))
        .map(control => ({ control, bounds: control.getBoundingClientRect?.() }))
        .filter(({ bounds }) => bounds && bounds.width > 0 && bounds.height > 0
          && bounds.top < document.documentElement.clientHeight && bounds.bottom > 0);
    } catch {
      return [];
    }
  };
  const findFallbackTop = () => {
    if (!visible || typeof element.getBoundingClientRect !== 'function') return null;
    const viewportHeight = document.documentElement.clientHeight;
    if (!viewportHeight) return null;
    const rect = element.getBoundingClientRect();
    const height = rect.height || 44;
    const left = 10;
    const width = Math.max(rect.width || 0, hasAvatar ? 48 : 120);
    const controls = fallbackControls().filter(({ bounds }) => bounds.left < left + width && bounds.right > left);
    const desired = Math.max(8, Math.min(viewportHeight - height - 8, viewportHeight - 72 - height));
    const candidates = [desired, 8, viewportHeight - height - 8,
      ...controls.flatMap(({ bounds }) => [bounds.top - height - 8, bounds.bottom + 8])];
    const available = candidates.filter(top => top >= 8 && top + height <= viewportHeight - 8
      && controls.every(({ bounds }) => top + height + 8 <= bounds.top || top >= bounds.bottom + 8));
    if (!available.length) return null;
    return available.reduce((best, candidate) =>
      Math.abs(candidate - desired) < Math.abs(best - desired) ? candidate : best);
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
    let top = findFallbackTop();
    if (top === null && hasAvatar) {
      label.style.display = 'none';
      top = findFallbackTop();
    }
    if (top !== null) {
      element.style.top = `${top}px`;
      element.style.bottom = 'auto';
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
  position = () => {
    const target = findNavigationTarget();
    if (target) showNavigationRow(target);
    else showFallback();
  };
  const isPotentialNavigationNode = node => {
    if (!node) return false;
    if (tagName(node) === 'NAV') return true;
    if (isAppearanceNavigationNode(node)) return true;
    try { return Boolean(node.querySelector?.(navigationTargetSelector) || node.querySelector?.('a[href]')); } catch { return false; }
  };
  const touchesFallbackColumn = node => {
    if (typeof node?.getBoundingClientRect !== 'function') return false;
    try {
      const bounds = node.getBoundingClientRect();
      const entry = element.getBoundingClientRect?.();
      const width = Math.max(entry?.width ?? 0, hasAvatar ? 48 : 120);
      return bounds.width > 0 && bounds.left < 10 + width && bounds.right > 10;
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
    if (record.type === 'childList') {
      return [...(record.addedNodes ?? []), ...(record.removedNodes ?? [])]
        .some(node => isPotentialNavigationNode(node) || isNavigationRelatedNode(node)
          || (!currentTarget && touchesFallbackColumn(node)));
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
      attributeFilter: ['aria-label', 'href', 'class', 'style', 'hidden', 'aria-hidden'] });
  }
  host.addEventListener?.('resize', schedule);
  host.addEventListener?.('scroll', onScroll, true);
  position();
  return {
    element, button, setAppearance, setWallpaperFailure,
    update(value) { visible = value; applyEntryLayout(); button.disabled = !value; if (value) position(); },
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

function mountOverlay(host, payload, runId, intent, assets, receive, appearance) {
  const document = host.document;
  if (!document?.documentElement || typeof document.createElement !== 'function' || !document.body) {
    throw new TypeError('startup overlay host is unavailable');
  }
  const frame = document.createElement('iframe');
  const text = appearanceText(dataProperty(payload, 'createLocalization'), appearance);
  frame.setAttribute('title', text.t('overlayLabel'));
  frame.setAttribute('aria-label', text.t('overlayLabel'));
  frame.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;border:0;z-index:2147483647;background:transparent';
  frame.src = 'about:blank';
  const parent = typeof document.body.appendChild === 'function' ? document.body : document.documentElement;
  parent.appendChild(frame);
  const contentWindow = frame.contentWindow;
  if (!contentWindow) {
    frame.remove();
    throw new TypeError('startup overlay frame is unavailable');
  }
  const bind = (name) => typeof contentWindow[name] === 'function'
    ? contentWindow[name].bind(contentWindow)
    : contentWindow[name];
  const environment = Object.freeze({
    window: contentWindow,
    document: contentWindow.document,
    location: contentWindow.location,
    performance: contentWindow.performance,
    indexedDB: contentWindow.indexedDB,
    Image: contentWindow.Image,
    Path2D: contentWindow.Path2D,
    URL: contentWindow.URL ?? URL,
    requestAnimationFrame: bind('requestAnimationFrame'),
    cancelAnimationFrame: bind('cancelAnimationFrame'),
    setTimeout: bind('setTimeout'),
    clearTimeout: bind('clearTimeout'),
  });
  const frameSpec = Object.freeze({ runId, intent, protocolVersion: 1, assets, appearance });
  // Preserve the result so the settings panel can report wallpaper failures.
  const SEND = (data) => receive({ source: frame.contentWindow, data });
  return {
    element: frame,
    contentWindow,
    start() {
      return payload(
        environment.window, environment.document, environment.location,
        environment.performance, environment.indexedDB, environment.Image,
        environment.Path2D, environment.URL, environment.requestAnimationFrame,
        environment.cancelAnimationFrame, environment.setTimeout, environment.clearTimeout,
        undefined, SEND, frameSpec, dataProperty(payload, 'createImageSettings'), dataProperty(payload, 'createLocalization'),
      );
    },
    remove: () => frame.remove(),
  };
}

class PageController {
  constructor(host, payload) {
    this.host = host;
    this.document = host.document;
    this.payload = payload;
    this.assets = dataProperty(payload, 'assets') ?? null;
    this.wallpaperApply = dataProperty(payload, 'applyWallpaper');
    this.frame = null;
    this.frameHandle = null;
    this.wallpaperAPI = null;
    this.wallpaperGeneration = 0;
    this.wallpaperRequest = null;
    this.wallpaperDisabled = false;
    this.wallpaperRetryPromise = null;
    this.wallpaperRetryCancel = null;
    this.startupWallpaperFailure = null;
    this.startupWallpaperNoticeDismissed = false;
    this.installed = false;
    this.disposed = false;
    this.watchdog = null;
    this.bodyObserver = null;
    this.modalIsolation = null;
    this.appearanceEntry = null;
    this.appearanceObserver = null;
    this.motionQuery = null;
    this.onMotionChange = () => this.#updateAppearance();
    this.appearance = hostAppearance(host);
    this.savedFocus = this.document?.activeElement ?? null;
    this.intent = 'play';
    this.state = {
      phase: 'loading',
      runId: 0,
      ready: false,
      completed: false,
      overlay: false,
      reason: '',
      wallpaper: { applied: false, reason: '', imageDecoded: false },
      completion: null,
    };
    this.onMessage = (event) => this.#receive(event);
    this.api = Object.freeze({
      owner: OWNER,
      version: VERSION,
      install: (nextPayload) => this.#install(nextPayload),
      status: () => this.#status(),
      openSettings: () => this.#openSettings(),
      retryWallpaper: () => this.#retryWallpaper(),
      dispose: () => this.#dispose(),
    });
  }

  #install(payload) {
    if (this.disposed || this.installed || payload !== this.payload || typeof payload !== 'function') {
      return this.disposed || this.installed
        ? { installed: false, alreadyActive: false, reason: 'owner-conflict' }
        : { installed: false, alreadyActive: false, reason: ASSET_REASON };
    }
    const wallpaper = wallpaperRecord(this.host);
    if (wallpaper.present && !wallpaper.supported) {
      return { installed: false, alreadyActive: false, reason: 'owner-conflict' };
    }
    this.wallpaperAPI = wallpaper.api;
    this.installed = true;
    this.#observeAppearance();
    if (!this.#beginRun('play')) {
      this.installed = false;
      return { installed: false, alreadyActive: false, reason: PAGE_REASON };
    }
    return { installed: true, alreadyActive: false };
  }

  #beginRun(intent) {
    if (this.disposed) return false;
    if (intent === 'play') {
      this.startupWallpaperFailure = null;
      this.startupWallpaperNoticeDismissed = false;
    }
    this.wallpaperRetryCancel?.();
    this.wallpaperGeneration += 1;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    const focused = this.document?.activeElement === this.appearanceEntry?.element
      ? this.appearanceEntry.button : this.document?.activeElement;
    this.#rememberFocus(focused);
    this.#stopFrame();
    this.intent = intent;
    this.state.phase = 'loading';
    this.state.runId = nextRunId++;
    this.state.ready = false;
    this.state.completed = false;
    this.state.overlay = true;
    this.state.reason = '';
    this.state.completion = null;
    this.appearanceEntry?.update(false);
    if (intent === 'settings') this.#isolateHostPage();
    const runId = this.state.runId;
    this.host.addEventListener('message', this.onMessage);
    this.watchdog = this.host.setTimeout(() => this.expire(runId), 25_000);
    if (this.document?.body) {
      this.#mountRun(runId);
      return this.state.phase !== 'failed';
    }
    return this.#waitForBody(runId);
  }

  #waitForBody(runId) {
    const MutationObserver = this.host.MutationObserver;
    if (typeof MutationObserver !== 'function' || !this.document?.documentElement) {
      this.#fail(PAGE_REASON, runId);
      return false;
    }
    try {
      this.bodyObserver = new MutationObserver(() => {
        if (!this.#isLoading(runId) || !this.document.body) return;
        this.#disconnectBodyObserver();
        this.#mountRun(runId);
      });
      this.bodyObserver.observe(this.document.documentElement, { childList: true, subtree: true });
      if (this.document.body) {
        this.#disconnectBodyObserver();
        this.#mountRun(runId);
      }
      return this.state.phase !== 'failed';
    } catch {
      this.#fail(PAGE_REASON, runId);
      return false;
    }
  }

  #mountRun(runId) {
    if (!this.#isLoading(runId) || !this.document.body) return;
    try {
      if (!this.appearanceEntry) this.appearanceEntry = mountAppearanceEntry(this.document, () => this.#openSettings(),
        this.assets, dataProperty(this.payload, 'createLocalization'), this.appearance, this.host,
        () => this.#retryWallpaper(), () => { this.startupWallpaperNoticeDismissed = true; });
      this.frame = mountOverlay(
        this.host, this.payload, runId, this.intent, this.assets, this.onMessage, this.appearance,
      );
      const instance = this.frame.start();
      if (instance && typeof instance.then === 'function') {
        Promise.resolve(instance).then(
          (handle) => this.#acceptFrameHandle(handle, runId),
          () => this.#fail(ASSET_REASON, runId),
        );
      } else {
        this.#acceptFrameHandle(instance, runId);
      }
    } catch {
      this.#fail(ASSET_REASON, runId);
    }
  }

  #acceptFrameHandle(handle, runId) {
    if (!this.#isCurrentFrame(runId)) {
      try { handle?.dispose?.(); } catch {}
      return;
    }
    if (handle && typeof handle === 'object') {
      this.frameHandle = handle;
      this.#updateAppearance();
    }
  }

  #updateAppearance() {
    if (this.disposed) return;
    const appearance = hostAppearance(this.host);
    const surfaceChanged = appearance.colors.surface !== this.appearance?.colors.surface;
    this.appearance = appearance;
    const updateWallpaperSurface = dataProperty(this.wallpaperAPI, 'updateSurface');
    if (surfaceChanged && typeof updateWallpaperSurface === 'function') {
      try { updateWallpaperSurface.call(this.wallpaperAPI, this.appearance.colors.surface); } catch {}
    }
    this.appearanceEntry?.setAppearance(this.appearance);
    const text = appearanceText(dataProperty(this.payload, 'createLocalization'), this.appearance);
    this.frame?.element.setAttribute('title', text.t('overlayLabel'));
    this.frame?.element.setAttribute('aria-label', text.t('overlayLabel'));
    const update = dataProperty(this.frameHandle, 'updateAppearance');
    if (typeof update === 'function') {
      try { update.call(this.frameHandle, this.appearance); } catch {}
    }
  }

  #observeAppearance() {
    if (typeof this.host.matchMedia === 'function') {
      this.motionQuery = this.host.matchMedia('(prefers-reduced-motion: reduce)');
      this.motionQuery.addEventListener('change', this.onMotionChange);
    }
    const root = this.document.documentElement;
    if (typeof root.getAttribute !== 'function' || typeof this.host.MutationObserver !== 'function') return;
    this.appearanceObserver = new this.host.MutationObserver(() => this.#updateAppearance());
    this.appearanceObserver.observe(root, {
      attributes: true, attributeFilter: ['lang', 'data-theme', 'class', 'style'],
    });
  }

  #isLoading(runId) {
    return !this.disposed && runId === this.state.runId && this.state.phase === 'loading';
  }

  #rememberFocus(focused = this.document?.activeElement) {
    if (focused === this.appearanceEntry?.element) focused = this.appearanceEntry.button;
    if (focused !== this.frame?.element && focused?.isConnected && typeof focused.focus === 'function') {
      this.savedFocus = focused;
    }
  }

  #focusOverlayFrame() {
    const frame = this.frame?.element;
    if (!frame || this.document?.activeElement === frame || typeof frame.focus !== 'function') return;
    try { frame.focus({ preventScroll: true }); }
    catch { try { frame.focus(); } catch {} }
  }

  #isolateHostPage() {
    if (this.modalIsolation) return;
    const body = this.document?.body;
    if (!body) return;

    const owner = { body, targets: new Map(), childObserver: null, inertObserver: null };
    this.modalIsolation = owner;
    const setOwnedInert = (element, value) => {
      const state = owner.targets.get(element);
      if (!state) return;
      const before = Boolean(element.inert);
      element.inert = value;
      if (before !== Boolean(element.inert) && element.isConnected) state.pendingOwnedWrites++;
    };
    const lockNode = node => {
      if (!node || node.nodeType !== 1) return;
      const frame = this.frame?.element;
      if (node === frame || (frame && typeof node.contains === 'function' && node.contains(frame))) return;
      let state = owner.targets.get(node);
      if (state) {
        state.restoreInert = Boolean(node.inert);
        state.ownsInert = false;
      } else {
        state = { restoreInert: Boolean(node.inert), pendingOwnedWrites: 0, ownsInert: false };
        owner.targets.set(node, state);
      }
      if (!state.restoreInert) {
        setOwnedInert(node, true);
        state.ownsInert = true;
      }
    };
    const processMutations = records => {
      if (records.some(record => record.type === 'childList')) {
        const pendingInert = owner.inertObserver?.takeRecords?.() || [];
        if (pendingInert.length) processMutations(pendingInert);
      }
      const reassert = new Set();
      for (const record of records) {
        if (record.type === 'attributes') {
          const state = owner.targets.get(record.target);
          if (!state) continue;
          if (state.pendingOwnedWrites > 0) {
            state.pendingOwnedWrites--;
            continue;
          }
          state.restoreInert = Boolean(record.target.inert);
          state.ownsInert = false;
          if (!state.restoreInert) reassert.add(record.target);
        } else if (record.type === 'childList' && record.target === body) {
          for (const node of record.removedNodes) {
            if (!node || node.nodeType !== 1) continue;
            const state = owner.targets.get(node);
            if (!state) continue;
            if (state.ownsInert && node.inert === true) setOwnedInert(node, state.restoreInert);
            state.ownsInert = false;
          }
          for (const node of record.addedNodes) lockNode(node);
        }
      }
      for (const element of reassert) {
        if (this.modalIsolation === owner && element.parentNode === body && !element.inert) {
          setOwnedInert(element, true);
          const state = owner.targets.get(element);
          if (state) state.ownsInert = true;
        }
      }
    };

    const MutationObserver = this.host.MutationObserver;
    if (typeof MutationObserver === 'function') {
      owner.childObserver = new MutationObserver(processMutations);
      owner.childObserver.observe(body, { childList: true });
      if (this.document.documentElement) {
        owner.inertObserver = new MutationObserver(processMutations);
        owner.inertObserver.observe(this.document.documentElement, {
          attributes: true, attributeFilter: ['inert'], subtree: true,
        });
      }
    }
    for (const node of Array.from(body.children || [])) lockNode(node);
  }

  #releaseHostPage() {
    const owner = this.modalIsolation;
    if (!owner) return;
    if (owner.inertObserver) {
      for (const record of owner.inertObserver.takeRecords?.() || []) {
        if (record.type !== 'attributes') continue;
        const state = owner.targets.get(record.target);
        if (!state) continue;
        if (state.pendingOwnedWrites > 0) state.pendingOwnedWrites--;
        else state.restoreInert = Boolean(record.target.inert);
      }
    }
    owner.childObserver?.disconnect();
    owner.inertObserver?.disconnect();
    this.modalIsolation = null;
    for (const [element, state] of owner.targets) {
      if (state.ownsInert && element.inert === true) element.inert = state.restoreInert;
    }
  }

  #isCurrentFrame(runId, frame = this.frame) {
    return !this.disposed && runId === this.state.runId && frame !== null
      && frame === this.frame && !['complete', 'failed', 'timeout', 'disposed'].includes(this.state.phase);
  }

  #receive(event) {
    if (this.disposed || !this.frame || event.source !== this.frame.contentWindow) return;
    const message = event.data;
    if (!message || typeof message !== 'object' || Array.isArray(message)
      || message.type !== 'azhou-startup' || !Number.isSafeInteger(message.runId)
      || message.runId !== this.state.runId || typeof message.action !== 'string') return;

    if (message.action === 'ready') {
      if (this.state.phase !== 'loading' || this.state.ready) return;
      this.state.ready = true;
      this.state.phase = this.intent === 'play' ? 'playing' : 'settings';
      if (this.intent === 'settings') this.#focusOverlayFrame();
      if (this.intent === 'settings') this.#clearWatchdog();
      return;
    }
    if (message.action === 'complete') {
      const phase = this.state.phase;
      const settingsCancel = phase === 'settings' && message.skipped === true;
      const playCompletion = this.intent === 'play' && ['loading', 'playing'].includes(phase)
        && typeof message.skipped === 'boolean' && (message.skipped || this.state.ready);
      if (!settingsCancel && !playCompletion) return;
      this.state.phase = 'complete';
      this.state.completed = true;
      this.state.overlay = false;
      this.state.completion = settingsCancel
        ? { cause: 'settings-cancel', beforeReady: false }
        : { cause: message.skipped ? 'skip' : 'natural', beforeReady: !this.state.ready };
      this.appearanceEntry?.update(true);
      this.#updateStartupWallpaperNotice();
      this.#clearWatchdog();
      this.host.removeEventListener('message', this.onMessage);
      this.#stopFrame();
      return;
    }
    if (message.action === 'assetError') {
      if (this.state.phase !== 'loading' || !FIXED_PAGE_REASONS.has(message.reason)) return;
      this.#fail(message.reason);
      return;
    }
    if (message.action === 'settings-open') {
      if (this.state.ready && this.state.phase === 'playing') {
        this.#isolateHostPage();
        this.#focusOverlayFrame();
        this.state.phase = 'settings';
        this.#clearWatchdog();
      }
      return;
    }
    if (message.action === 'settings-close') {
      if (this.state.ready && this.state.phase === 'settings') {
        this.state.phase = 'complete';
        this.state.completed = true;
        this.state.overlay = false;
        this.state.completion = { cause: 'settings-save', beforeReady: false };
        this.appearanceEntry?.update(true);
        this.#updateStartupWallpaperNotice();
        this.#clearWatchdog();
        this.host.removeEventListener('message', this.onMessage);
        this.#stopFrame();
      }
      return;
    }
    if (message.action === 'background') {
      if (['loading', 'playing', 'settings'].includes(this.state.phase)) {
        return this.#applyWallpaper(message, this.state.runId, this.frame);
      }
      return Promise.resolve({ applied: false, reason: 'operation-cancelled', imageDecoded: false });
    }
    if (message.action === 'restore') this.#dispose();
  }

  #ownsStartupController() {
    const descriptor = Object.getOwnPropertyDescriptor(this.host, GLOBAL_NAME);
    return !!descriptor && Object.hasOwn(descriptor, 'value') && descriptor.value === this.api;
  }

  #isCurrentRetry(runId, generation) {
    return !this.disposed && generation === this.wallpaperGeneration && runId === this.state.runId
      && this.state.phase === 'complete' && this.state.completed && this.#ownsStartupController();
  }

  #setWallpaperFailure(code, reason = 'wallpaper-unsupported', imageDecoded = false) {
    const result = { applied: false, reason, imageDecoded };
    const failure = wallpaperFailure({ failureCode: code });
    if (failure) Object.assign(result, failure);
    this.state.wallpaper = result;
    if (this.intent === 'play') {
      this.startupWallpaperFailure = failure && this.wallpaperRequest && !this.wallpaperDisabled
        ? { ...result } : null;
      if (!this.wallpaperRetryPromise) this.startupWallpaperNoticeDismissed = false;
    }
    this.#updateStartupWallpaperNotice();
    return { ...result };
  }

  #updateStartupWallpaperNotice(announcementKey) {
    const cause = this.state.completion?.cause;
    const visible = !this.disposed && !this.startupWallpaperNoticeDismissed
      && !!this.startupWallpaperFailure && !!this.wallpaperRequest && !this.wallpaperDisabled
      && this.state.phase === 'complete' && this.state.completed
      && ['natural', 'skip', 'settings-cancel'].includes(cause);
    this.appearanceEntry?.setWallpaperFailure(visible ? this.startupWallpaperFailure : null,
      announcementKey);
  }

  #retryResult(retried, previousFailure, reason) {
    const result = {
      retried,
      wallpaper: { ...this.state.wallpaper },
      previousFailure: previousFailure ? { ...previousFailure } : null,
    };
    if (reason) result.reason = reason;
    return result;
  }

  #previousWallpaperFailure() {
    const current = this.state.wallpaper;
    if (!current.failureCode && current.reason !== 'wallpaper-unsupported') return null;
    const result = { reason: wallpaperReason(current) };
    const failure = wallpaperFailure(current);
    if (failure) Object.assign(result, failure);
    return result;
  }

  #retryWallpaper() {
    const previousFailure = this.#previousWallpaperFailure();
    if (this.disposed) return Promise.resolve(this.#retryResult(false, previousFailure, 'disposed'));
    if (this.wallpaperRetryPromise) return this.wallpaperRetryPromise;
    if (!this.#ownsStartupController()) return Promise.resolve(this.#retryResult(false, previousFailure, 'unknown-owner'));
    if (this.state.phase !== 'complete' || !this.state.completed) {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'busy'));
    }
    if (this.wallpaperDisabled || this.state.wallpaper.reason === 'disabled') {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'disabled'));
    }
    if (!this.wallpaperRequest) return Promise.resolve(this.#retryResult(false, previousFailure, 'no-request'));

    const current = wallpaperRecord(this.host);
    if ((current.present && (!current.supported || current.api !== this.wallpaperAPI))
      || (!current.present && this.wallpaperAPI)) {
      return Promise.resolve(this.#retryResult(false, previousFailure, 'unknown-owner'));
    }
    this.#refreshWallpaper();
    if (this.state.wallpaper.applied) {
      const hadFailure = !!this.startupWallpaperFailure;
      this.startupWallpaperFailure = null;
      this.#updateStartupWallpaperNotice(hadFailure ? 'applied' : undefined);
      return Promise.resolve(this.#retryResult(false, null, 'already-applied'));
    }

    this.startupWallpaperNoticeDismissed = false;
    this.#updateStartupWallpaperNotice('retrying');
    const runId = this.state.runId;
    const request = { ...this.wallpaperRequest };
    let operation;
    try {
      operation = this.#applyWallpaper(request, runId, null, true);
    } catch {
      operation = Promise.resolve(this.#setWallpaperFailure('apply-failed'));
    }
    const generation = this.wallpaperGeneration;
    let timer = null;
    const timeout = new Promise(resolve => {
      timer = this.host.setTimeout(() => resolve({ timedOut: true }), WALLPAPER_RETRY_TIMEOUT_MS);
    });
    let cancelRetry;
    const cancellation = new Promise(resolve => {
      cancelRetry = () => resolve({ cancelled: true });
    });
    const work = Promise.resolve(operation).then(
      wallpaper => ({ wallpaper }),
      () => ({ wallpaper: this.#isCurrentRetry(runId, generation)
        ? this.#setWallpaperFailure('apply-failed') : { ...this.state.wallpaper } }),
    );
    const bounded = Promise.race([work, timeout, cancellation]).then(result => {
      if (result.cancelled) return this.#retryResult(false, previousFailure, 'operation-cancelled');
      if (result.timedOut) {
        if (!this.#isCurrentRetry(runId, generation)) {
          return this.#retryResult(false, previousFailure, 'operation-cancelled');
        }
        this.wallpaperGeneration += 1;
        this.#setWallpaperFailure('retry-timeout');
        return this.#retryResult(true, previousFailure, 'timeout');
      }
      if (!this.#isCurrentRetry(runId, generation)) {
        return this.#retryResult(false, previousFailure, 'operation-cancelled');
      }
      return this.#retryResult(true, previousFailure);
    }).finally(() => {
      if (timer !== null) this.host.clearTimeout(timer);
      if (this.wallpaperRetryCancel === cancelRetry) this.wallpaperRetryCancel = null;
    });
    this.wallpaperRetryPromise = bounded;
    this.wallpaperRetryCancel = cancelRetry;
    const release = () => {
      if (this.wallpaperRetryPromise === bounded) this.wallpaperRetryPromise = null;
    };
    work.then(release, release);
    return bounded;
  }

  async #applyWallpaper(message, runId, frame, retry = false) {
    const generation = ++this.wallpaperGeneration;
    if (typeof message.image !== 'string' || message.image.length > 16 * 1024 * 1024
      || !BACKGROUND_DATA_URL.test(message.image) || !Number.isInteger(message.strength)
      || message.strength < 0 || message.strength > 75) {
      if (!retry) {
        this.wallpaperRequest = null;
        this.wallpaperDisabled = false;
      }
      return this.#setWallpaperFailure('invalid-local-payload');
    }
    if (message.strength === 0) {
      if (!retry) {
        this.wallpaperRequest = null;
        this.wallpaperDisabled = true;
      }
      this.#disposeWallpaper();
      this.state.wallpaper = { applied: false, reason: 'disabled', imageDecoded: false };
      this.startupWallpaperFailure = null;
      this.#updateStartupWallpaperNotice();
      return { ...this.state.wallpaper };
    }
    if (!retry) {
      this.wallpaperRequest = { image: message.image, strength: message.strength };
      this.wallpaperDisabled = false;
    }
    // The workspace may mount after the overlay closes. Skip, replacement and
    // disposal still cancel work, while completed playback or saving can finish.
    const isCurrent = () => generation === this.wallpaperGeneration
      && (retry ? this.#isCurrentRetry(runId, generation)
        : this.#isCurrentFrame(runId, frame) || (!this.disposed && runId === this.state.runId
          && this.state.phase === 'complete' && ['natural', 'settings-save'].includes(this.state.completion?.cause)
          && this.#ownsStartupController()));
    if (typeof this.wallpaperApply !== 'function') {
      if (isCurrent()) return this.#setWallpaperFailure('apply-unavailable');
      return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
    }
    try {
      this.appearance = hostAppearance(this.host);
      const result = await this.wallpaperApply(Object.freeze({
        image: message.image, strength: message.strength, surface: this.appearance.colors.surface,
      }), isCurrent);
      if (!isCurrent()) return { applied: false, reason: 'operation-cancelled', imageDecoded: false };
      if (dataProperty(result, 'applied') === false) {
        const reason = wallpaperReason(result);
        const failure = wallpaperFailure(result) ?? wallpaperFailure({ failureCode: 'apply-failed' });
        const current = wallpaperRecord(this.host);
        if (current.present && !current.supported) {
          this.state.wallpaper = { applied: false, reason: 'owner-conflict', imageDecoded: false };
          if (this.intent === 'play') this.startupWallpaperFailure = null;
          this.#updateStartupWallpaperNotice();
          return { ...this.state.wallpaper };
        }
        if (current.supported) this.wallpaperAPI = current.api;
        const imageDecoded = dataProperty(result, 'imageDecoded') === true;
        return this.#setWallpaperFailure(failure.failureCode, reason, imageDecoded);
      }
      const current = wallpaperRecord(this.host);
      if (!current.supported) {
        if (current.present) {
          this.state.wallpaper = { applied: false, reason: 'owner-conflict', imageDecoded: false };
          if (this.intent === 'play') this.startupWallpaperFailure = null;
          this.#updateStartupWallpaperNotice();
          return { ...this.state.wallpaper };
        }
        return this.#setWallpaperFailure('apply-unavailable');
      }
      this.wallpaperAPI = current.api;
      this.appearance = hostAppearance(this.host);
      const updateWallpaperSurface = dataProperty(current.api, 'updateSurface');
      if (typeof updateWallpaperSurface === 'function') {
        try { updateWallpaperSurface.call(current.api, this.appearance.colors.surface); } catch {}
      }
      this.state.wallpaper = this.#wallpaperStatus(current.api);
      if (!this.state.wallpaper.applied && !this.state.wallpaper.reason) {
        this.state.wallpaper.reason = 'wallpaper-unsupported';
      }
      if (this.state.wallpaper.applied) {
        const hadStartupFailure = !!this.startupWallpaperFailure;
        this.startupWallpaperFailure = null;
        this.#updateStartupWallpaperNotice(this.intent === 'play' && retry && hadStartupFailure
          ? 'applied' : undefined);
      } else {
        if (this.intent === 'play') {
          const failure = wallpaperFailure(this.state.wallpaper);
          this.startupWallpaperFailure = failure && this.wallpaperRequest && !this.wallpaperDisabled
            ? { ...this.state.wallpaper } : null;
        }
        this.#updateStartupWallpaperNotice();
      }
    } catch (error) {
      if (isCurrent()) {
        const failure = wallpaperFailure(error) ?? wallpaperFailure({ failureCode: 'apply-failed' });
        return this.#setWallpaperFailure(failure.failureCode);
      }
    }
    return { ...this.state.wallpaper };
  }

  #wallpaperStatus(api) {
    const status = dataProperty(api, 'status');
    try {
      const value = status.call(api);
      if (!value || typeof value !== 'object' || typeof value.applied !== 'boolean') {
        return { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
      }
      const result = {
        applied: value.applied,
        reason: value.applied ? '' : wallpaperReason(value),
        imageDecoded: value.imageDecoded === true,
      };
      const failure = !value.applied ? wallpaperFailure(value) : null;
      if (failure) Object.assign(result, failure);
      for (const field of WALLPAPER_STATUS_FIELDS) {
        const fieldValue = value[field];
        if (typeof fieldValue === 'boolean' || (Number.isSafeInteger(fieldValue) && fieldValue >= 0)
          || (typeof fieldValue === 'string' && field !== 'verificationScope')
          || (Array.isArray(fieldValue) && fieldValue.every((item) => typeof item === 'string'))) {
          result[field] = Array.isArray(fieldValue) ? [...fieldValue] : fieldValue;
        }
      }
      return result;
    } catch {
      return { applied: false, reason: 'wallpaper-unsupported', imageDecoded: false };
    }
  }

  #refreshWallpaper() {
    const current = wallpaperRecord(this.host);
    if (!current.present) {
      if (this.state.wallpaper.applied) {
        this.state.wallpaper = { applied: false, reason: 'not-installed', imageDecoded: false };
      }
      return;
    }
    if (!current.supported || current.api !== this.wallpaperAPI) {
      this.state.wallpaper = { applied: false, reason: 'owner-conflict', imageDecoded: false };
      return;
    }
    const status = this.#wallpaperStatus(current.api);
    if (!status.failureCode && this.state.wallpaper.failureCode) {
      const previousFailure = wallpaperFailure(this.state.wallpaper);
      if (previousFailure) {
        status.applied = false;
        status.reason = wallpaperReason(this.state.wallpaper);
        status.imageDecoded = this.state.wallpaper.imageDecoded === true;
        Object.assign(status, previousFailure);
      }
    }
    this.state.wallpaper = status;
  }

  #fail(reason, runId = this.state.runId) {
    if (this.disposed || runId !== this.state.runId || ['complete', 'failed', 'timeout', 'disposed'].includes(this.state.phase)) return;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    this.state.phase = 'failed';
    this.state.overlay = false;
    this.state.reason = reason;
    this.host.removeEventListener('message', this.onMessage);
    this.#stopFrame();
  }

  expire(runId) {
    if (this.disposed || runId !== this.state.runId || !['loading', 'playing'].includes(this.state.phase)) return false;
    this.watchdog = null;
    this.#disconnectBodyObserver();
    this.state.phase = 'timeout';
    this.state.overlay = false;
    this.state.reason = 'overlay-timeout';
    this.host.removeEventListener('message', this.onMessage);
    this.#stopFrame();
    return true;
  }

  #clearWatchdog() {
    if (this.watchdog === null) return;
    this.host.clearTimeout(this.watchdog);
    this.watchdog = null;
  }

  #disconnectBodyObserver() {
    const observer = this.bodyObserver;
    this.bodyObserver = null;
    try { observer?.disconnect(); } catch {}
  }

  #restoreFocus(frame) {
    const ownedFocus = this.document?.activeElement === frame.element;
    if (!ownedFocus) return;
    const candidates = [this.savedFocus, this.appearanceEntry?.button];
    try {
      const selectors = 'button:not([disabled]),a[href],input:not([disabled]):not([type="hidden"]),textarea:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';
      candidates.push(...Array.from(this.document.querySelectorAll(selectors)));
    } catch {}
    for (const candidate of new Set(candidates)) {
      if (!candidate?.isConnected || candidate.inert || candidate.disabled
        || typeof candidate.focus !== 'function' || candidate.hidden) continue;
      try {
        const style = this.host.getComputedStyle?.(candidate);
        if (style?.display === 'none' || style?.visibility === 'hidden'
          || (typeof candidate.getClientRects === 'function' && candidate.getClientRects().length === 0)) continue;
      } catch {}
      try { candidate.focus(); } catch { continue; }
      const root = candidate.getRootNode?.();
      if (this.document.activeElement === candidate
        || (root?.host === this.document.activeElement && root.activeElement === candidate)) return;
    }
  }

  #stopFrame() {
    const frame = this.frame;
    const handle = this.frameHandle;
    this.frame = null;
    this.frameHandle = null;
    this.#releaseHostPage();
    if (!frame) return;
    this.#restoreFocus(frame);
    try { handle?.dispose?.(); } catch {}
    try { frame.remove(); } catch {}
  }

  #invokeFrameSettings() {
    const openSettings = dataProperty(this.frameHandle, 'openSettings');
    if (this.disposed || this.state.phase !== 'playing' || !this.state.ready || typeof openSettings !== 'function') return false;
    try {
      const result = openSettings.call(this.frameHandle);
      if (result && typeof result.then === 'function') Promise.resolve(result).catch(() => {});
      return result !== false;
    } catch {
      return false;
    }
  }

  #openSettings() {
    if (this.disposed || !this.installed) return false;
    if (this.state.phase === 'complete') return this.#beginRun('settings');
    if (this.state.phase === 'settings') return false;
    if (this.state.phase === 'playing') {
      this.#rememberFocus();
      return this.#invokeFrameSettings();
    }
    return false;
  }

  #status() {
    this.#refreshWallpaper();
    return {
      owner: OWNER,
      version: VERSION,
      phase: this.state.phase,
      runId: this.state.runId,
      ready: this.state.ready,
      completed: this.state.completed,
      overlay: this.state.overlay,
      reason: this.state.reason,
      wallpaper: { ...this.state.wallpaper },
      completion: this.state.completion ? { ...this.state.completion } : null,
    };
  }

  #disposeWallpaper() {
    const current = wallpaperRecord(this.host);
    if (!current.supported || !this.wallpaperAPI || current.api !== this.wallpaperAPI) return;
    try { dataProperty(current.api, 'dispose').call(current.api); } catch {}
    this.wallpaperAPI = null;
  }

  #dispose() {
    if (this.disposed) return { disposed: true };
    this.disposed = true;
    this.wallpaperRetryCancel?.();
    this.wallpaperGeneration += 1;
    this.#clearWatchdog();
    this.#disconnectBodyObserver();
    this.state.phase = 'disposed';
    this.appearanceObserver?.disconnect();
    this.appearanceObserver = null;
    this.motionQuery?.removeEventListener('change', this.onMotionChange);
    this.motionQuery = null;
    this.state.overlay = false;
    this.host.removeEventListener('message', this.onMessage);
    this.#stopFrame();
    this.#disposeWallpaper();
    this.appearanceEntry?.remove();
    this.appearanceEntry = null;
    const current = Object.getOwnPropertyDescriptor(this.host, GLOBAL_NAME);
    if (current && Object.hasOwn(current, 'value') && current.value === this.api) {
      delete this.host[GLOBAL_NAME];
    }
    return { disposed: true };
  }
}

export function installStartup(payload, host = globalThis) {
  if (!host || !isMainPage(host)) return { installed: false, alreadyActive: false, reason: PAGE_REASON };
  const current = existingController(host);
  if (current.present) {
    return current.owned
      ? { installed: true, alreadyActive: true }
      : { installed: false, alreadyActive: false, reason: 'owner-conflict' };
  }
  if (typeof payload !== 'function') return { installed: false, alreadyActive: false, reason: ASSET_REASON };
  const controller = new PageController(host, payload);
  try {
    Object.defineProperty(host, GLOBAL_NAME, {
      value: controller.api, configurable: true, enumerable: false, writable: false,
    });
  } catch {
    return { installed: false, alreadyActive: false, reason: 'owner-conflict' };
  }
  const result = controller.api.install(payload);
  if (!result.installed) controller.api.dispose();
  return result;
}
