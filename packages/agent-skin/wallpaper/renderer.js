/* Serialized by the local builder; the function has no module-scope dependency.
   Only this page's appearance is changed. No chat text, storage or network is read. */
export async function installRenderer(payload) {
  'use strict';
  const VERSION = '0.9.0', LEGACY_VERSIONS = new Set(['0.8.0', '0.7.1']);
  let OWNER = 'azhou.codex-startup-animation';
  const STYLE_ID = 'azhou-wallpaper-style', ATTRIBUTE = 'data-azhou-wallpaper';
  const IMAGE_PROPERTY = '--azhou-wallpaper-image', WASH_PROPERTY = '--azhou-wallpaper-wash';
  const SURFACE_PROPERTY = '--azhou-wallpaper-surface';
  const BASELINE_KEY = '__azhouWallpaperBaseline_071', RELEASE_KEY = '__azhouWallpaperRelease_071';
  const root = document.documentElement;
  const surfaceSelector = '[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]';
  const workspaceSelector = '[data-app-shell-main-surface] :is([class^="_WorkspaceContent_"],[class*=" _WorkspaceContent_"])';
  const footerSelector = '[data-app-shell-main-surface] [data-thread-scroll-footer]';
  const token = prefix => ':is([class^="' + prefix + '"],[class*=" ' + prefix + '"])';
  // Current ChatGPT builds use hyphenated CSS-module names. Admit only the
  // observed hidden, non-interactive direct footer plate; unknown layers still fail.
  const footerBackgroundSelector = footerSelector + ' > ' + token('_background_')
    + ',' + footerSelector + ' > [aria-hidden="true"].pointer-events-none' + token('background-');
  const scrollSelector = '[data-app-shell-main-surface] .thread-scroll-container';
  const stickySelector = scrollSelector + ' .pointer-events-none.sticky.bottom-0';
  const footerFadeSelector = stickySelector + ' > ' + token('_background_') + token('_fade_');
  const topFadeSelector = '[data-app-shell-main-surface] ' + token('_MainContentTopFade_');
  const protectedSelector = '[data-composer-layout],pre,code,[role="menu"],[role="dialog"],'
    + '[contenteditable="true"],textarea,input,button,select';
  const problem = reason => Object.assign(new Error('AZHOU_WALLPAPER: ' + reason), {
    code: reason.split(':', 1)[0],
  });
  function decodeBitmapPixels(image, bitmap) {
    let canvas;
    try {
      if (!bitmap || typeof bitmap.close !== 'function'
          || bitmap.width !== image.naturalWidth || bitmap.height !== image.naturalHeight) return false;
      canvas = document.createElement('canvas');
      canvas.width = 1;
      canvas.height = 1;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      if (!context) return false;
      context.drawImage(bitmap, 0, 0, 1, 1);
      const pixel = context.getImageData(0, 0, 1, 1)?.data;
      return !!pixel && pixel.length >= 4
        && [pixel[0], pixel[1], pixel[2], pixel[3]].every(Number.isFinite);
    } catch { return false; }
    finally {
      if (canvas) { canvas.width = 0; canvas.height = 0; }
      try { bitmap?.close?.(); } catch {}
    }
  }
  function decodeImage(image) {
    return new Promise((resolve, reject) => {
      let finished = false;
      let fallbackTimer, deadlineTimer;
      const finish = error => {
        if (finished) return;
        finished = true;
        clearTimeout(fallbackTimer);
        clearTimeout(deadlineTimer);
        if (error) reject(error);
        else resolve(true);
      };
      let nativeResult;
      try { nativeResult = image.decode(); }
      catch (error) { nativeResult = Promise.reject(error); }
      Promise.resolve(nativeResult).then(() => finish(), error => finish(error || problem('image-decode-failed')));
      if (typeof globalThis.createImageBitmap === 'function') {
        fallbackTimer = setTimeout(() => {
          if (finished || !image.complete || image.naturalWidth <= 0 || image.naturalHeight <= 0) return;
          let bitmapResult;
          try { bitmapResult = globalThis.createImageBitmap(image); }
          catch { return; }
          Promise.resolve(bitmapResult).then(bitmap => {
            if (decodeBitmapPixels(image, bitmap)) finish();
          }, () => {});
        }, 250);
      }
      deadlineTimer = setTimeout(() => finish(problem('image-decode-timeout')), 4000);
    });
  }
  function validSurface(value) {
    if (typeof value !== 'string') return false;
    const color = value.trim();
    if (!color || color.length > 100 || /[;{}]/.test(color) || /\bvar\s*\(/i.test(color)
      || /^(?:currentcolor|inherit|initial|unset|revert(?:-layer)?)$/i.test(color)) return false;
    try { return typeof globalThis.CSS?.supports === 'function' && globalThis.CSS.supports('color', color); }
    catch { return false; }
  }
  const ownValue = (object, name) => {
    if (!object || typeof object !== 'object') return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(object, name);
    return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
  };
  const preview = payload?.preview;
  const isCurrent = ownValue(payload, 'isCurrent');
  const pageAdapter = ownValue(payload, 'pageAdapter');
  const ports = ownValue(pageAdapter, 'wallpaper');
  // The ports group is atomic: an adapter that declares it must supply every
  // member, and the neutral renderer refuses the whole adapter otherwise.
  const attributes = ownValue(ports, 'attributes');
  const adapterPorts = {
    validPage: ownValue(ports, 'validPage'), shellState: ownValue(ports, 'shellState'),
    surfaces: ownValue(ports, 'surfaces'), css: ownValue(ports, 'css'), scope: ownValue(ports, 'scope'),
    surfaceMarker: ownValue(attributes, 'surfaceMarker'), observeFilter: ownValue(attributes, 'observeFilter'),
  };
  const adapter = !!ports && typeof ports === 'object'
    && typeof adapterPorts.validPage === 'function' && typeof adapterPorts.shellState === 'function'
    && typeof adapterPorts.surfaces === 'function' && typeof adapterPorts.css === 'string'
    && typeof adapterPorts.scope === 'string' && !!attributes && typeof adapterPorts.surfaceMarker === 'string'
    && Array.isArray(adapterPorts.observeFilter);
  if (pageAdapter && !adapter) throw problem('invalid-host-adapter');
  const surfaceMarker = adapter ? adapterPorts.surfaceMarker : null;
  if (adapter) OWNER = ownValue(ownValue(pageAdapter, 'controllerWallpaper'), 'owner') ?? OWNER;
  const knownVersion = version => version === VERSION || (!adapter && LEGACY_VERSIONS.has(version));
  function validPage() {
    if (window.top !== window) return false;
    if (adapter) return Reflect.apply(adapterPorts.validPage, ports, [globalThis]);
    const url = new URL(location.href), route = url.searchParams.get('initialRoute') || '/';
    if (url.protocol === 'app:' && url.hostname === '-' && url.pathname === '/index.html') {
      return !/avatar|quick.chat|detached|mini|popover|notification/i.test(route);
    }
    // The generated production payload never contains this fixture-only flag.
    return preview === true && (
      (url.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(url.hostname))
      || (url.protocol === 'file:' && url.pathname.endsWith('/wallpaper/preview.html'))
    );
  }
  if (!validPage()) throw problem('unexpected-page');
  const request = {
    version: payload?.version, css: payload?.css, image: payload?.image,
    imageSHA256: payload?.imageSHA256, strength: payload?.strength, surface: payload?.surface,
  };
  if (!payload || request.version !== VERSION || typeof request.css !== 'string'
      || !request.css.includes('[data-azhou-wallpaper="active"]')
      || !request.css.includes('--azhou-style-ready')
      || /@import\b|url\(\s*['"]?(?:https?:|\/\/)/i.test(request.css)
      || typeof request.imageSHA256 !== 'string' || !/^[0-9a-f]{64}$/.test(request.imageSHA256)
      || (request.surface !== undefined && !validSurface(request.surface))
      || (request.strength !== undefined && (!Number.isInteger(request.strength) || request.strength < 0 || request.strength > 75))) {
    throw problem('invalid-local-payload');
  }
  let surface = typeof request.surface === 'string' ? request.surface.trim() : null;
  let surfaceOwned = false;
  const imageMatch = typeof request.image === 'string'
    && /^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$/.exec(request.image);
  if (!imageMatch || request.image.length > 16 * 1024 * 1024) throw problem('invalid-local-image');
  const applicationRoot = document.getElementById('root');
  const currentSurfaces = () => {
    if (!applicationRoot) return [];
    if (!adapter) return [...applicationRoot.querySelectorAll(surfaceSelector)];
    const nodes = Reflect.apply(adapterPorts.surfaces, ports, [globalThis]);
    return Array.isArray(nodes) && nodes.length === 1 && nodes.every(node => node?.isConnected
      && applicationRoot.contains(node) && !node.closest('[role="dialog"],dialog,iframe,webview')) ? nodes : [];
  };
  const shellReady = () => adapter
    ? Reflect.apply(adapterPorts.shellState, ports, [isCurrent, globalThis]) === 'ready' && currentSurfaces().length === 1
    : !!applicationRoot?.querySelector('[data-app-shell-frame]')
      && !!applicationRoot?.querySelector('[data-app-shell-main-surface],[data-app-shell-page-surface]');
  if (!document.body || !applicationRoot
      || !shellReady()) {
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
  const ownsSurfaceMarkers = current => {
    if (!adapter) return true;
    const recorded = ownValue(ownValue(current, BASELINE_KEY), 'zcodeAttributes');
    return [applicationRoot, ...currentSurfaces()].every(node => {
      const value = node.getAttribute(surfaceMarker);
      return value === null || (value === 'active' && recorded instanceof Map && recorded.has(node));
    });
  };
  if (!ownsSurfaceMarkers(previous)) throw problem('namespace-conflict');
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
  let image, committed = false, released = false;
  const releaseImage = () => {
    if (released) return;
    released = true;
    URL.revokeObjectURL(imageURL);
    if (image) image.src = '';
  };
  try {
    image = new Image();
    try {
      image.src = imageURL;
      await decodeImage(image);
      if (!image.naturalWidth || !image.naturalHeight) throw problem('empty-image');
    } catch (error) {
      releaseImage();
      if (error?.code === 'image-decode-timeout') throw problem('image-decode-timeout');
      throw problem('image-decode-failed');
    }

    if ((typeof isCurrent === 'function' && !isCurrent())
        || !validPage() || !applicationRoot.isConnected
        || !shellReady()) {
      releaseImage();
      throw problem('page-changed-during-decode');
    }
    // Re-read after the async decode: another apply may have completed meanwhile.
    const activeDescriptor = Object.getOwnPropertyDescriptor(globalThis, '__azhouWallpaper');
    const active = activeDescriptor && Object.hasOwn(activeDescriptor, 'value') ? activeDescriptor.value : null;
    if (activeDescriptor && (!active || ownValue(active, 'owner') !== OWNER
        || !knownVersion(ownValue(active, 'version'))
        || typeof ownValue(active, 'dispose') !== 'function' || typeof ownValue(active, 'status') !== 'function')) {
      releaseImage();
      throw problem('namespace-changed-during-decode');
    }
    if (active !== previous) {
      releaseImage();
      throw problem('namespace-changed-during-decode');
    }
    if (!ownsSurfaceMarkers(active)) {
      releaseImage();
      throw problem('namespace-changed-during-decode');
    }
    const latestStyle = document.getElementById(STYLE_ID);
    if (latestStyle && (!active || latestStyle.getAttribute('data-azhou-owner') !== OWNER)) {
      releaseImage();
      throw problem('style-id-conflict-after-decode');
    }
    const strength = request.strength ?? 42;
    const washStops = [24, 18, 12, 16, 30, 65, 70];
    const washScale = strength / 42;
    const wash = 'linear-gradient(90deg,' + washStops.map((opacity, index) => {
      const visible = Math.min(100, Math.round(opacity * washScale));
      return 'color-mix(in srgb, var(--azhou-base) ' + (100 - visible) + '%, transparent) '
        + ['0%', '22%', '36%', '62%', '73%', '87%', '100%'][index];
    }).join(',') + ')';
    const captureOriginal = () => ({
      attribute: root.getAttribute(ATTRIBUTE),
      // The baseline key stays `zcodeAttributes` verbatim: live 0.9.0 ZCode
      // installs must transfer their recorded baselines across a replacement.
      zcodeAttributes: adapter ? new Map([applicationRoot, ...currentSurfaces()].map(node => [node, node.getAttribute(surfaceMarker)])) : undefined,
      properties: new Map([IMAGE_PROPERTY, WASH_PROPERTY, SURFACE_PROPERTY].map(name => [
        name, [root.style.getPropertyValue(name), root.style.getPropertyPriority(name)],
      ])),
    });
    const rollbackOriginal = captureOriginal();
    const previousOriginal = previous ? ownValue(previous, BASELINE_KEY) ?? rollbackOriginal : rollbackOriginal;
    const transferredOriginal = {
      attribute: previousOriginal.attribute,
      properties: new Map(previousOriginal.properties),
      zcodeAttributes: adapter ? new Map([...(previousOriginal.zcodeAttributes ?? []),
        ...[...(rollbackOriginal.zcodeAttributes ?? [])].filter(([node]) => !previousOriginal.zcodeAttributes?.has(node))]) : undefined,
    };
    if (!transferredOriginal.properties.has(SURFACE_PROPERTY)) {
      transferredOriginal.properties.set(SURFACE_PROPERTY,
        [...rollbackOriginal.properties.get(SURFACE_PROPERTY)]);
    }
    const priorStyleID = latestStyle?.id;
    const priorStyleDisabled = latestStyle?.disabled;
    const priorStyleText = latestStyle?.textContent;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.setAttribute('data-azhou-owner', OWNER);
    const styleText = request.css + (adapter ? adapterPorts.css : '');
    style.textContent = styleText;
    let disposed = false, api, releaseAttempted = false;
    let original = rollbackOriginal;
    const transparent = color => color === 'transparent'
      || /^rgba\([^)]*,\s*0(?:\.0+)?\)$/.test(color)
      || /^color\([^)]*\/\s*0(?:\.0+)?\)$/.test(color);
    const noEffect = value => !value || value === 'none';
    const writeSurface = value => {
      root.style.setProperty(SURFACE_PROPERTY, value);
      surfaceOwned = root.style.getPropertyValue(SURFACE_PROPERTY) === value
        && root.style.getPropertyPriority(SURFACE_PROPERTY) === '';
    };
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
        reason: 'disposed', imageSHA256: request.imageSHA256 };
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
        imageSHA256: request.imageSHA256,
        image: { width: image.naturalWidth, height: image.naturalHeight, displayMode: 'cover',
          viewport: { width: innerWidth, height: innerHeight },
          devicePixelRatio: devicePixelRatio || 1,
          rasterScale: Math.max(innerWidth / image.naturalWidth, innerHeight / image.naturalHeight)
            * Math.max(1, devicePixelRatio || 1),
          position: bodyStyle.backgroundPosition.split(',')[1]?.trim() },
        styleCount,
        persistentAnimation: false,
        verificationScope: adapter ? adapterPorts.scope
          : 'decoded image, viewport cover, matched shell, footer and top fades, decorative planes and bounded unknown-layer checks; visual inspection is separate',
      };
    }
    function dispose() {
      if (disposed) return status();
      disposed = true;
      if (style.isConnected && style.parentNode === document.head && style.id === STYLE_ID && style.disabled === false
          && style.getAttribute('data-azhou-owner') === OWNER && style.textContent === styleText) style.remove();
      const liveApplicationRoot = !adapter || (applicationRoot.isConnected && document.getElementById('root') === applicationRoot);
      for (const [node, value] of original.zcodeAttributes ?? []) {
        if (!liveApplicationRoot || !node.isConnected
            || (node !== applicationRoot && !applicationRoot.contains(node))
            || node.getAttribute(surfaceMarker) !== 'active') continue;
        if (value === null) node.removeAttribute(surfaceMarker);
        else node.setAttribute(surfaceMarker, value);
      }
      if (document.documentElement === root) {
        if (root.getAttribute(ATTRIBUTE) === 'active') {
          if (original.attribute === null) root.removeAttribute(ATTRIBUTE);
          else root.setAttribute(ATTRIBUTE, original.attribute);
        }
        for (const [name, [value, priority]] of original.properties) {
          const writtenValue = name === IMAGE_PROPERTY ? 'url(' + JSON.stringify(imageURL) + ')'
            : name === WASH_PROPERTY ? wash : surface;
          if (typeof writtenValue !== 'string') continue;
          if (root.style.getPropertyValue(name) !== writtenValue || root.style.getPropertyPriority(name) !== '') continue;
          if (value) root.style.setProperty(name, value, priority);
          else root.style.removeProperty(name);
        }
      }
      releaseImage();
      if (globalThis.__azhouWallpaper === api) delete globalThis.__azhouWallpaper;
      return status();
    }
    const releaseForReplacement = () => {
      disposed = true;
      const temporarilyRenamed = style.id === '' && style.disabled === true;
      if (style.isConnected && style.parentNode === document.head && (style.id === STYLE_ID && style.disabled === false || temporarilyRenamed)
          && style.getAttribute('data-azhou-owner') === OWNER && style.textContent === styleText) style.remove();
      releaseImage();
      if (globalThis.__azhouWallpaper === api) delete globalThis.__azhouWallpaper;
    };
    function updateSurface(value) {
      if (disposed || !validSurface(value)) return false;
      const currentValue = root.style.getPropertyValue(SURFACE_PROPERTY);
      const currentPriority = root.style.getPropertyPriority(SURFACE_PROPERTY);
      const originalSurface = rollbackOriginal.properties.get(SURFACE_PROPERTY);
      const stillOwned = surfaceOwned
        ? currentValue === surface && currentPriority === ''
        : currentValue === originalSurface[0] && currentPriority === originalSurface[1];
      if (!stillOwned) return false;
      const nextSurface = value.trim();
      if (nextSurface !== surface || !surfaceOwned) {
        writeSurface(nextSurface);
        surface = nextSurface;
      }
      return surfaceOwned;
    }
    api = { owner: OWNER, version: VERSION, status, dispose, restore: dispose, updateSurface };
    Object.defineProperty(api, RELEASE_KEY, { value: releaseForReplacement });
    try {
      // This synchronous transaction cannot paint between disabling and validation.
      // Keep the old sheet attached, so a failed candidate can restore it without
      // re-inserting an inline stylesheet under a potentially stricter CSP.
      if (latestStyle) { latestStyle.disabled = true; latestStyle.removeAttribute('id'); }
      for (const node of rollbackOriginal.zcodeAttributes?.keys() ?? []) node.setAttribute(surfaceMarker, 'active');
      root.style.setProperty(IMAGE_PROPERTY, 'url(' + JSON.stringify(imageURL) + ')');
      root.style.setProperty(WASH_PROPERTY, wash);
      if (surface !== null) writeSurface(surface);
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
          releaseAttempted = true;
          release.call(active);
        } else {
          active.dispose();
          // An installed 0.7.1 payload predating conditional restore remains a
          // known legacy owner. Let its own dispose restore the host baseline.
          original = captureOriginal();
          original.properties.set(WASH_PROPERTY, [...rollbackOriginal.properties.get(WASH_PROPERTY)]);
          original.properties.set(SURFACE_PROPERTY, [...rollbackOriginal.properties.get(SURFACE_PROPERTY)]);
          root.style.setProperty(IMAGE_PROPERTY, 'url(' + JSON.stringify(imageURL) + ')');
          root.style.setProperty(WASH_PROPERTY, wash);
          if (surface !== null) writeSurface(surface);
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
      const recover = releaseAttempted && globalThis.__azhouWallpaper === api
        && latestStyle?.isConnected && latestStyle.parentNode === document.head
        && latestStyle.id === '' && latestStyle.disabled === true
        && latestStyle.getAttribute('data-azhou-owner') === OWNER && latestStyle.textContent === priorStyleText;
      if (recover) original = rollbackOriginal;
      dispose();
      if (recover && !Object.hasOwn(globalThis, '__azhouWallpaper')) {
        latestStyle.id = priorStyleID;
        latestStyle.disabled = priorStyleDisabled;
        let usable = false;
        try { usable = Reflect.apply(ownValue(active, 'status'), active, [])?.applied === true; } catch {}
        if (usable && !Object.hasOwn(globalThis, '__azhouWallpaper')) {
          Object.defineProperty(globalThis, '__azhouWallpaper', activeDescriptor);
        } else if (!Object.hasOwn(globalThis, '__azhouWallpaper')
            && latestStyle.isConnected && latestStyle.parentNode === document.head
            && latestStyle.id === priorStyleID && latestStyle.disabled === priorStyleDisabled
            && latestStyle.getAttribute('data-azhou-owner') === OWNER && latestStyle.textContent === priorStyleText) {
          latestStyle.disabled = true;
          latestStyle.removeAttribute('id');
        }
      } else if (!releaseAttempted && !committed && active && globalThis.__azhouWallpaper === active && latestStyle?.isConnected
          && latestStyle.id === '' && latestStyle.disabled === true) {
        latestStyle.id = priorStyleID;
        latestStyle.disabled = priorStyleDisabled;
      }
      throw error;
    }
  } finally {
    if (!committed) releaseImage();
  }
}
