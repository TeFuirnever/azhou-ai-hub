/* Serialized by the local builder; the function has no module-scope dependency.
   Only this page's appearance is changed. No chat text, storage or network is read. */
export async function installRenderer(payload) {
  'use strict';
  const VERSION = '0.9.0', LEGACY_VERSIONS = new Set(['0.8.0', '0.7.1']), OWNER = 'azhou.codex-startup-animation';
  const STYLE_ID = 'azhou-wallpaper-style', ATTRIBUTE = 'data-azhou-wallpaper';
  const IMAGE_PROPERTY = '--azhou-wallpaper-image', WASH_PROPERTY = '--azhou-wallpaper-wash';
  const BASELINE_KEY = '__azhouWallpaperBaseline_071', RELEASE_KEY = '__azhouWallpaperRelease_071';
  const root = document.documentElement;
  const surfaceSelector = '[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]';
  const workspaceSelector = '[data-app-shell-main-surface] :is([class^="_WorkspaceContent_"],[class*=" _WorkspaceContent_"])';
  const footerSelector = '[data-app-shell-main-surface] [data-thread-scroll-footer]';
  const token = prefix => ':is([class^="' + prefix + '"],[class*=" ' + prefix + '"])';
  const footerBackgroundSelector = footerSelector + ' > ' + token('_background_');
  const scrollSelector = '[data-app-shell-main-surface] .thread-scroll-container';
  const stickySelector = scrollSelector + ' .pointer-events-none.sticky.bottom-0';
  const footerFadeSelector = stickySelector + ' > ' + token('_background_') + token('_fade_');
  const topFadeSelector = '[data-app-shell-main-surface] ' + token('_MainContentTopFade_');
  const protectedSelector = '[data-composer-layout],pre,code,[role="menu"],[role="dialog"],'
    + '[contenteditable="true"],textarea,input,button,select';
  const problem = reason => new Error('AZHOU_WALLPAPER: ' + reason);
  const ownValue = (object, name) => {
    if (!object || typeof object !== 'object') return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(object, name);
    return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
  };
  const knownVersion = version => version === VERSION || LEGACY_VERSIONS.has(version);
  function validPage() {
    if (window.top !== window) return false;
    const url = new URL(location.href), route = url.searchParams.get('initialRoute') || '/';
    if (url.protocol === 'app:' && url.hostname === '-' && url.pathname === '/index.html') {
      return !/avatar|quick.chat|detached|mini|popover|notification/i.test(route);
    }
    // The generated production payload never contains this fixture-only flag.
    return payload?.preview === true && (
      (url.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(url.hostname))
      || (url.protocol === 'file:' && url.pathname.endsWith('/wallpaper/preview.html'))
    );
  }
  if (!validPage()) throw problem('unexpected-page');
  if (!payload || payload.version !== VERSION || typeof payload.css !== 'string'
      || !payload.css.includes('[data-azhou-wallpaper="active"]')
      || !payload.css.includes('--azhou-style-ready')
      || /@import\b|url\(\s*['"]?(?:https?:|\/\/)/i.test(payload.css)
      || typeof payload.imageSHA256 !== 'string' || !/^[0-9a-f]{64}$/.test(payload.imageSHA256)
      || (payload.strength !== undefined && (!Number.isInteger(payload.strength) || payload.strength < 0 || payload.strength > 75))) {
    throw problem('invalid-local-payload');
  }
  const imageMatch = typeof payload.image === 'string'
    && /^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$/.exec(payload.image);
  if (!imageMatch || payload.image.length > 16 * 1024 * 1024) throw problem('invalid-local-image');
  const applicationRoot = document.getElementById('root');
  const currentSurfaces = () => applicationRoot
    ? [...applicationRoot.querySelectorAll(surfaceSelector)] : [];
  if (!document.body || !applicationRoot
      || !applicationRoot.querySelector('[data-app-shell-frame]')
      || !applicationRoot.querySelector('[data-app-shell-main-surface],[data-app-shell-page-surface]')) {
    throw problem('unsupported-shell-no-surfaces');
  }
  const previousDescriptor = Object.getOwnPropertyDescriptor(globalThis, '__azhouWallpaper');
  const previous = previousDescriptor && Object.hasOwn(previousDescriptor, 'value')
    ? previousDescriptor.value : null;
  if (previousDescriptor && (!previous || ownValue(previous, 'owner') !== OWNER
      || !knownVersion(ownValue(previous, 'version'))
      || typeof ownValue(previous, 'dispose') !== 'function' || typeof ownValue(previous, 'status') !== 'function')) {
    throw problem('namespace-conflict');
  }
  const existingStyle = document.getElementById(STYLE_ID);
  if (existingStyle && (!previous || existingStyle.getAttribute('data-azhou-owner') !== OWNER)) {
    throw problem('style-id-conflict');
  }
  // Decode before replacing a working installation. Blob URLs keep the image
  // out of CSS custom-property token-size limits; the host must allow blob: images.
  let bytes;
  try { bytes = Uint8Array.from(atob(imageMatch[2]), char => char.charCodeAt(0)); }
  catch { throw problem('invalid-local-image'); }
  const imageURL = URL.createObjectURL(new Blob([bytes], { type: 'image/' + imageMatch[1] }));
  const image = new Image();
  let decodeTimer;
  try {
    image.src = imageURL;
    await Promise.race([
      image.decode(),
      new Promise((_, reject) => { decodeTimer = setTimeout(() => reject(problem('image-decode-timeout')), 4000); }),
    ]);
    if (!image.naturalWidth || !image.naturalHeight) throw problem('empty-image');
  } catch (error) {
    URL.revokeObjectURL(imageURL);
    image.src = '';
    throw problem('image-decode-failed: ' + (error?.message || String(error)));
  } finally { clearTimeout(decodeTimer); }

  if ((typeof ownValue(payload, 'isCurrent') === 'function' && !ownValue(payload, 'isCurrent')())
      || !validPage() || !applicationRoot.isConnected
      || !applicationRoot.querySelector('[data-app-shell-frame]')
      || !applicationRoot.querySelector('[data-app-shell-main-surface],[data-app-shell-page-surface]')) {
    URL.revokeObjectURL(imageURL); image.src = '';
    throw problem('page-changed-during-decode');
  }
  // Re-read after the async decode: another apply may have completed meanwhile.
  const activeDescriptor = Object.getOwnPropertyDescriptor(globalThis, '__azhouWallpaper');
  const active = activeDescriptor && Object.hasOwn(activeDescriptor, 'value') ? activeDescriptor.value : null;
  if (activeDescriptor && (!active || ownValue(active, 'owner') !== OWNER
      || !knownVersion(ownValue(active, 'version'))
      || typeof ownValue(active, 'dispose') !== 'function' || typeof ownValue(active, 'status') !== 'function')) {
    URL.revokeObjectURL(imageURL); image.src = '';
    throw problem('namespace-changed-during-decode');
  }
  if (active !== previous) {
    URL.revokeObjectURL(imageURL); image.src = '';
    throw problem('namespace-changed-during-decode');
  }
  const latestStyle = document.getElementById(STYLE_ID);
  if (latestStyle && (!active || latestStyle.getAttribute('data-azhou-owner') !== OWNER)) {
    URL.revokeObjectURL(imageURL); image.src = '';
    throw problem('style-id-conflict-after-decode');
  }
  const strength = payload.strength ?? 42;
  const washStops = [24, 18, 12, 16, 30, 65, 70];
  const washScale = strength / 42;
  const wash = 'linear-gradient(90deg,' + washStops.map((opacity, index) => {
    const visible = Math.min(100, Math.round(opacity * washScale));
    return 'color-mix(in srgb, var(--azhou-base) ' + (100 - visible) + '%, transparent) '
      + ['0%', '22%', '36%', '62%', '73%', '87%', '100%'][index];
  }).join(',') + ')';
  const captureOriginal = () => ({
    attribute: root.getAttribute(ATTRIBUTE),
    properties: new Map([IMAGE_PROPERTY, WASH_PROPERTY].map(name => [
      name, [root.style.getPropertyValue(name), root.style.getPropertyPriority(name)],
    ])),
  });
  const rollbackOriginal = captureOriginal();
  const transferredOriginal = previous ? ownValue(previous, BASELINE_KEY) ?? rollbackOriginal : rollbackOriginal;
  const priorStyleID = latestStyle?.id;
  const priorStyleDisabled = latestStyle?.disabled;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.setAttribute('data-azhou-owner', OWNER);
  const styleText = payload.css;
  style.textContent = styleText;
  let disposed = false, committed = false, api;
  let original = rollbackOriginal;
  const transparent = color => color === 'transparent'
    || /^rgba\([^)]*,\s*0(?:\.0+)?\)$/.test(color)
    || /^color\([^)]*\/\s*0(?:\.0+)?\)$/.test(color);
  const noEffect = value => !value || value === 'none';
  const protectedNode = node => !!node.closest(protectedSelector);
  const decorativeNodes = selector => [...applicationRoot.querySelectorAll(selector)]
    .filter(node => node.isConnected && !protectedNode(node));
  // Read only known decorative nodes and their generated planes. No selectors,
  // text, input values or image URLs are included in the diagnostic result.
  function planes(node) {
    const own = getComputedStyle(node);
    if (own.display === 'none' || own.visibility === 'hidden' || Number(own.opacity) === 0
        || node.getClientRects().length === 0) return [];
    return [own, ...['::before', '::after'].map(pseudo => getComputedStyle(node, pseudo))
      .filter(style => style.content !== 'none' && style.content !== 'normal'
        && style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0)];
  }
  const backgroundClear = style => transparent(style.backgroundColor) && noEffect(style.backgroundImage);
  const effectsClear = style => noEffect(style.boxShadow) && noEffect(style.filter)
    && noEffect(style.backdropFilter) && noEffect(style.webkitBackdropFilter)
    && noEffect(style.maskImage) && noEffect(style.webkitMaskImage);
  const clearBackgrounds = nodes => nodes.every(node => planes(node).every(backgroundClear));
  const clearEffects = nodes => nodes.every(node => planes(node)
    .every(style => backgroundClear(style) && effectsClear(style)));
  function unsupportedDecorations(known) {
    const unsupported = new Set();
    const inspect = (node, category, requirePosition = true) => {
      if (known.has(node) || protectedNode(node) || node.querySelector(protectedSelector)) return;
      const computed = getComputedStyle(node);
      if (computed.pointerEvents !== 'none'
          || (requirePosition && !['absolute', 'fixed', 'sticky'].includes(computed.position))) return;
      if (planes(node).some(style => !backgroundClear(style) || !effectsClear(style))) unsupported.add(category);
    };
    // This second check deliberately does not reuse the successful fade selector:
    // a renamed child in the inspected sticky wrapper must not self-certify.
    for (const parent of applicationRoot.querySelectorAll(stickySelector)) {
      inspect(parent, 'unmatched-sticky-decoration', false);
      for (const child of parent.children) inspect(child, 'unmatched-sticky-decoration', false);
    }
    for (const parent of applicationRoot.querySelectorAll(footerSelector)) {
      for (const child of parent.children) inspect(child, 'unmatched-footer-decoration');
    }
    for (const node of applicationRoot.querySelectorAll(scrollSelector + ' :is('
        + token('_background_') + ',' + token('_fade_') + ')')) {
      inspect(node, 'unmatched-scroll-decoration');
    }
    // Three fixed categories at most. Unknown layers are diagnosed, never styled.
    return [...unsupported].sort();
  }
  function status() {
    if (disposed) return { version: VERSION, applied: false, imageDecoded: false,
      matchedSurfaces: 0, transparentSurfaces: 0, backgroundMatched: false,
      rootClear: false, workspaceBackgroundClear: false, coverMatched: false, fixedViewport: false,
      footerSurfaces: 0, footerBackgroundClear: false, footerFadeSurfaces: 0, footerFadeClear: false,
      topFadeSurfaces: 0, topFadeClear: false, decorationEffectsClear: false, unsupportedDecorations: [],
      reason: 'disposed', imageSHA256: payload.imageSHA256 };
    const surfaces = currentSurfaces().filter(node => node.isConnected);
    const bodyStyle = getComputedStyle(document.body);
    const transparentSurfaces = surfaces.filter(node => {
      const computed = getComputedStyle(node);
      return transparent(computed.backgroundColor) && computed.backgroundImage === 'none';
    }).length;
    const workspace = [...applicationRoot.querySelectorAll(workspaceSelector)];
    const workspaceBackgroundClear = workspace.every(node => {
      const pseudo = getComputedStyle(node, '::before');
      return pseudo.display === 'none' || pseudo.content === 'none'
        || (transparent(pseudo.backgroundColor) && pseudo.backgroundImage === 'none');
    });
    // The 32px scroll fade is a sibling branch, not a footer descendant. The
    // separate top fade has the same opaque-surface assumption. Inspect all
    // three groups, including generated planes, without touching the composer.
    const footerSurfaces = decorativeNodes(footerSelector + ',' + footerBackgroundSelector);
    const footerFadeSurfaces = decorativeNodes(footerFadeSelector);
    const topFadeSurfaces = decorativeNodes(topFadeSelector);
    const footerBackgroundClear = clearBackgrounds(footerSurfaces);
    const footerFadeClear = clearBackgrounds(footerFadeSurfaces);
    const topFadeClear = clearBackgrounds(topFadeSurfaces);
    const decorations = new Set([...footerSurfaces, ...footerFadeSurfaces, ...topFadeSurfaces]);
    const decorationEffectsClear = clearEffects([...decorations]);
    const unsupported = unsupportedDecorations(decorations);
    const imageDecoded = image.complete && image.naturalWidth > 0 && image.naturalHeight > 0;
    const backgroundMatched = bodyStyle.backgroundImage.includes(imageURL)
      && bodyStyle.getPropertyValue('--azhou-style-ready').trim() === 'ready';
    const washMatched = root.style.getPropertyValue(WASH_PROPERTY) === wash
      && root.style.getPropertyPriority(WASH_PROPERTY) === '';
    // The second layer is the scene. A decoded image alone does not establish
    // that it fills the viewport rather than retaining the old corner size.
    const coverMatched = bodyStyle.backgroundSize.split(',')[1]?.trim() === 'cover';
    const fixedViewport = bodyStyle.backgroundAttachment.split(',').every(value => value.trim() === 'fixed');
    const rootStyle = getComputedStyle(applicationRoot);
    const rootClear = transparent(rootStyle.backgroundColor) && rootStyle.backgroundImage === 'none';
    const styleCount = document.querySelectorAll('#' + STYLE_ID).length;
    const applied = validPage() && imageDecoded && style.isConnected && styleCount === 1 && root.getAttribute(ATTRIBUTE) === 'active'
      && surfaces.length > 0 && transparentSurfaces === surfaces.length
      && rootClear && workspaceBackgroundClear && footerBackgroundClear && backgroundMatched
      && washMatched
      && footerFadeClear && topFadeClear && decorationEffectsClear && unsupported.length === 0
      && coverMatched && fixedViewport;
    return {
      version: VERSION, applied, imageDecoded, matchedSurfaces: surfaces.length,
      backgroundMatched, washMatched, coverMatched, fixedViewport, transparentSurfaces, rootClear, workspaceBackgroundClear,
      footerSurfaces: footerSurfaces.length, footerBackgroundClear,
      footerFadeSurfaces: footerFadeSurfaces.length, footerFadeClear,
      topFadeSurfaces: topFadeSurfaces.length, topFadeClear, decorationEffectsClear,
      unsupportedDecorations: unsupported,
      imageSHA256: payload.imageSHA256,
      image: { width: image.naturalWidth, height: image.naturalHeight, displayMode: 'cover',
        viewport: { width: innerWidth, height: innerHeight },
        devicePixelRatio: devicePixelRatio || 1,
        rasterScale: Math.max(innerWidth / image.naturalWidth, innerHeight / image.naturalHeight)
          * Math.max(1, devicePixelRatio || 1),
        position: bodyStyle.backgroundPosition.split(',')[1]?.trim() },
      styleCount,
      persistentAnimation: false,
      verificationScope: 'decoded image, viewport cover, matched shell, footer and top fades, decorative planes and bounded unknown-layer checks; visual inspection is separate',
    };
  }
  function dispose() {
    if (disposed) return status();
    disposed = true;
    if (style.isConnected && style.parentNode === document.head && style.id === STYLE_ID && style.disabled === false
        && style.getAttribute('data-azhou-owner') === OWNER && style.textContent === styleText) style.remove();
    if (root.getAttribute(ATTRIBUTE) === 'active') {
      if (original.attribute === null) root.removeAttribute(ATTRIBUTE);
      else root.setAttribute(ATTRIBUTE, original.attribute);
    }
    for (const [name, [value, priority]] of original.properties) {
      const writtenValue = name === IMAGE_PROPERTY ? 'url(' + JSON.stringify(imageURL) + ')' : wash;
      if (root.style.getPropertyValue(name) !== writtenValue || root.style.getPropertyPriority(name) !== '') continue;
      if (value) root.style.setProperty(name, value, priority);
      else root.style.removeProperty(name);
    }
    URL.revokeObjectURL(imageURL);
    image.src = '';
    if (globalThis.__azhouWallpaper === api) delete globalThis.__azhouWallpaper;
    return status();
  }
  const releaseForReplacement = () => {
    disposed = true;
    const temporarilyRenamed = style.id === '' && style.disabled === true;
    if (style.isConnected && style.parentNode === document.head && (style.id === STYLE_ID && style.disabled === false || temporarilyRenamed)
        && style.getAttribute('data-azhou-owner') === OWNER && style.textContent === styleText) style.remove();
    URL.revokeObjectURL(imageURL);
    image.src = '';
    if (globalThis.__azhouWallpaper === api) delete globalThis.__azhouWallpaper;
  };
  api = { owner: OWNER, version: VERSION, status, dispose, restore: dispose };
  Object.defineProperty(api, RELEASE_KEY, { value: releaseForReplacement });
  try {
    // This synchronous transaction cannot paint between disabling and validation.
    // Keep the old sheet attached, so a failed candidate can restore it without
    // re-inserting an inline stylesheet under a potentially stricter CSP.
    if (latestStyle) { latestStyle.disabled = true; latestStyle.removeAttribute('id'); }
    root.style.setProperty(IMAGE_PROPERTY, 'url(' + JSON.stringify(imageURL) + ')');
    root.style.setProperty(WASH_PROPERTY, wash);
    root.setAttribute(ATTRIBUTE, 'active');
    document.head.appendChild(style);
    let result = status();
    if (!result.applied) throw problem('styles-not-effective: ' + JSON.stringify(result));
    if (active) {
      const release = active[RELEASE_KEY];
      if (typeof release === 'function') {
        original = transferredOriginal;
        Object.defineProperty(api, BASELINE_KEY, { value: original });
        globalThis.__azhouWallpaper = api;
        release.call(active);
      } else {
        active.dispose();
        // An installed 0.7.1 payload predating conditional restore remains a
        // known legacy owner. Let its own dispose restore the host baseline.
        original = captureOriginal();
        original.properties.set(WASH_PROPERTY, [...rollbackOriginal.properties.get(WASH_PROPERTY)]);
        root.style.setProperty(IMAGE_PROPERTY, 'url(' + JSON.stringify(imageURL) + ')');
        root.style.setProperty(WASH_PROPERTY, wash);
        root.setAttribute(ATTRIBUTE, 'active');
        result = status();
        if (!result.applied) throw problem('styles-not-effective-after-replacement');
        Object.defineProperty(api, BASELINE_KEY, { value: original });
        globalThis.__azhouWallpaper = api;
      }
    }
    if (!active) {
      Object.defineProperty(api, BASELINE_KEY, { value: original });
      globalThis.__azhouWallpaper = api;
    } else if (typeof ownValue(api, BASELINE_KEY) !== 'object') {
      Object.defineProperty(api, BASELINE_KEY, { value: original });
    }
    committed = true;
    return result;
  } catch (error) {
    dispose();
    if (!committed && active && globalThis.__azhouWallpaper === active && latestStyle?.isConnected
        && latestStyle.id === '' && latestStyle.disabled === true) {
      latestStyle.id = priorStyleID;
      latestStyle.disabled = priorStyleDisabled;
    }
    throw error;
  }
}
