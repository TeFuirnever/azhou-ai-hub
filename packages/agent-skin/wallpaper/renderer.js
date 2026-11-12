/* Built for one-shot serialization by the local builder: a single function,
   no imports, nothing evaluated at module scope. Installation restyles this
   page and nothing else — chat text, storage and the network stay unread.

   Every installRenderer call walks one explicit request lifecycle:
     admit    – five admission gates (host binding, page, brief, shell, incumbent controller)
     lease    – one Blob URL whose ownership never outlives the attempt
     decode   – native decode with a pixel-checked bitmap cross-examination
     reconfirm– the world the brief was admitted to is re-checked after the await
     compose  – wash gradient, host-state snapshots, candidate stylesheet
     probe    – a named set of verification checks, assembled into the receipt
     transact – one synchronous handover (suspend, style, verify, replace/inherit)
     recover  – a ladder that revives or suspends the resident sheet on failure
   Nothing reaches the page before the probe accepts the composed candidate. */
export async function installRenderer(offered) {
  'use strict';

  const BUILD = '0.9.0';
  const SUPERSEDED = new Set(['0.8.0', '0.7.1']);
  let controllerOwner = 'azhou.codex-startup-animation';

  // Names this build answers to: the sheet identity, the activation attribute,
  // the three root custom properties and the two controller handshake keys.
  const SHEET_ID = 'azhou-wallpaper-style';
  const SHEET_OWNER_ATTRIBUTE = 'data-azhou-owner';
  const ACTIVATION = 'data-azhou-wallpaper';
  const SCENE_PROPERTY = '--azhou-wallpaper-image';
  const TINT_PROPERTY = '--azhou-wallpaper-wash';
  const SURFACE_PROPERTY = '--azhou-wallpaper-surface';
  const CONTROLLER_SLOT = '__azhouWallpaper';
  const BASELINE_KEY = '__azhouWallpaperBaseline_071';
  const RELEASE_KEY = '__azhouWallpaperRelease_071';

  const html = document.documentElement;

  // Selector directory. Host shells are located only through these anchors;
  // anything the anchors do not name is diagnosed, never styled.
  const directory = {
    shellSurfaces: '[data-app-shell-frame],[data-app-shell-main-surface],[data-app-shell-page-surface]',
    workspace: '[data-app-shell-main-surface] :is([class^="_WorkspaceContent_"],[class*=" _WorkspaceContent_"])',
    threadFooter: '[data-app-shell-main-surface] [data-thread-scroll-footer]',
    scrollTrack: '[data-app-shell-main-surface] .thread-scroll-container',
    protectedRegions: '[data-composer-layout],pre,code,[role="menu"],[role="dialog"],'
      + '[contenteditable="true"],textarea,input,button,select',
  };
  const generatedLayer = prefix => ':is([class^="' + prefix + '"],[class*=" ' + prefix + '"])';
  // Current ChatGPT builds use hyphenated CSS-module names. Admit only the
  // observed hidden, non-interactive direct footer plate; unknown layers still fail.
  directory.footerPlate = directory.threadFooter + ' > ' + generatedLayer('_background_')
    + ',' + directory.threadFooter + ' > [aria-hidden="true"].pointer-events-none' + generatedLayer('background-');
  directory.stickyShade = directory.scrollTrack + ' .pointer-events-none.sticky.bottom-0';
  directory.footerFade = directory.stickyShade + ' > ' + generatedLayer('_background_') + generatedLayer('_fade_');
  directory.topFade = '[data-app-shell-main-surface] ' + generatedLayer('_MainContentTopFade_');
  directory.scrollLayers = directory.scrollTrack + ' :is('
    + generatedLayer('_background_') + ',' + generatedLayer('_fade_') + ')';

  const deny = reason => Object.assign(new Error('AZHOU_WALLPAPER: ' + reason), {
    code: reason.split(':', 1)[0],
  });
  // Own-property read that deliberately ignores accessors: a throwing getter on
  // the controller slot must be observed as "no controller", never as a crash.
  const slotValue = (holder, key) => {
    if (!holder || typeof holder !== 'object') return undefined;
    const own = Object.getOwnPropertyDescriptor(holder, key);
    return own && Object.hasOwn(own, 'value') ? own.value : undefined;
  };

  // ── Gate 1: host binding ────────────────────────────────────────────────
  // A host adapter must arrive complete: half a port bundle is treated as a
  // foreign installation, so the whole adapter is refused rather than patched.
  const previewFlag = offered?.preview;
  const isCurrent = slotValue(offered, 'isCurrent');
  const hostAdapter = slotValue(offered, 'pageAdapter');
  const ports = slotValue(hostAdapter, 'wallpaper');
  const portAttributes = slotValue(ports, 'attributes');
  const binding = {
    validPage: slotValue(ports, 'validPage'), shellState: slotValue(ports, 'shellState'),
    surfaces: slotValue(ports, 'surfaces'), css: slotValue(ports, 'css'), scope: slotValue(ports, 'scope'),
    surfaceMarker: slotValue(portAttributes, 'surfaceMarker'),
    observeFilter: slotValue(portAttributes, 'observeFilter'),
  };
  const hostBound = !!ports && typeof ports === 'object'
    && typeof binding.validPage === 'function' && typeof binding.shellState === 'function'
    && typeof binding.surfaces === 'function' && typeof binding.css === 'string'
    && typeof binding.scope === 'string' && !!portAttributes && typeof binding.surfaceMarker === 'string'
    && Array.isArray(binding.observeFilter);
  if (hostAdapter && !hostBound) throw deny('invalid-host-adapter');
  const surfaceMarker = hostBound ? binding.surfaceMarker : null;
  if (hostBound) controllerOwner = slotValue(slotValue(hostAdapter, 'controllerWallpaper'), 'owner') ?? controllerOwner;

  // ── Gate 2: page identity ───────────────────────────────────────────────
  function pageAdmitted() {
    if (window.top !== window) return false;
    if (hostBound) return Reflect.apply(binding.validPage, ports, [globalThis]);
    const here = new URL(location.href), route = here.searchParams.get('initialRoute') || '/';
    if (here.protocol === 'app:' && here.hostname === '-' && here.pathname === '/index.html') {
      return !/avatar|quick.chat|detached|mini|popover|notification/i.test(route);
    }
    // Generated production payloads never set this flag; it exists so the two
    // fixture routes below can opt in.
    return previewFlag === true && (
      (here.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(here.hostname))
      || (here.protocol === 'file:' && here.pathname.endsWith('/wallpaper/preview.html'))
    );
  }
  if (!pageAdmitted()) throw deny('unexpected-page');

  // ── Gate 3: the brief ───────────────────────────────────────────────────
  // The brief is copied once, so caller mutations during the asynchronous
  // decode can no longer influence what gets installed or reported.
  const brief = {
    version: offered?.version, css: offered?.css, image: offered?.image,
    imageSHA256: offered?.imageSHA256, strength: offered?.strength, surface: offered?.surface,
  };
  const rejectedColorShapes = [
    /[;{}]/,                                                         // style delimiters
    /\bvar\s*\(/i,                                                   // custom-property indirection
    /^(?:currentcolor|inherit|initial|unset|revert(?:-layer)?)$/i,   // non-literal keywords
  ];
  const colorPlausible = value => {
    if (typeof value !== 'string') return false;
    const color = value.trim();
    if (!color || color.length > 100) return false;
    if (rejectedColorShapes.some(shape => shape.test(color))) return false;
    let hostAccepts = false;
    try {
      hostAccepts = typeof globalThis.CSS?.supports === 'function' && globalThis.CSS.supports('color', color);
    } catch { hostAccepts = false; }
    return hostAccepts;
  };
  if (!offered || brief.version !== BUILD || typeof brief.css !== 'string'
      || !brief.css.includes('[data-azhou-wallpaper="active"]')
      || !brief.css.includes('--azhou-style-ready')
      || /@import\b|url\(\s*['"]?(?:https?:|\/\/)/i.test(brief.css)
      || typeof brief.imageSHA256 !== 'string' || !/^[0-9a-f]{64}$/.test(brief.imageSHA256)
      || (brief.surface !== undefined && !colorPlausible(brief.surface))
      || (brief.strength !== undefined && (!Number.isInteger(brief.strength) || brief.strength < 0 || brief.strength > 75))) {
    throw deny('invalid-local-payload');
  }
  let surfaceTint = typeof brief.surface === 'string' ? brief.surface.trim() : null;
  const encodedScene = typeof brief.image === 'string'
    && /^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$/.exec(brief.image);
  if (!encodedScene || brief.image.length > 16 * 1024 * 1024) throw deny('invalid-local-image');

  // ── Gate 4: shell ───────────────────────────────────────────────────────
  const shell = document.getElementById('root');
  const liveSurfaces = () => {
    if (!shell) return [];
    if (!hostBound) return [...shell.querySelectorAll(directory.shellSurfaces)];
    const nominated = Reflect.apply(binding.surfaces, ports, [globalThis]);
    return Array.isArray(nominated) && nominated.length === 1 && nominated.every(node => node?.isConnected
      && shell.contains(node) && !node.closest('[role="dialog"],dialog,iframe,webview')) ? nominated : [];
  };
  const shellUsable = () => hostBound
    ? Reflect.apply(binding.shellState, ports, [isCurrent, globalThis]) === 'ready' && liveSurfaces().length === 1
    : !!shell?.querySelector('[data-app-shell-frame]')
      && !!shell?.querySelector('[data-app-shell-main-surface],[data-app-shell-page-surface]');
  if (!document.body || !shell || !shellUsable()) throw deny('unsupported-shell-no-surfaces');

  // ── Gate 5: incumbent controller ────────────────────────────────────────
  const acceptsVersion = version => version === BUILD || (!hostBound && SUPERSEDED.has(version));
  const seatedController = () => {
    const placement = Object.getOwnPropertyDescriptor(globalThis, CONTROLLER_SLOT);
    return {
      placement,
      seated: placement && Object.hasOwn(placement, 'value') ? placement.value : null,
    };
  };
  const controllerLegible = seated => !!seated && slotValue(seated, 'owner') === controllerOwner
    && acceptsVersion(slotValue(seated, 'version'))
    && typeof slotValue(seated, 'dispose') === 'function' && typeof slotValue(seated, 'status') === 'function';
  const { placement: incumbentPlacement, seated: incumbent } = seatedController();
  if (incumbentPlacement && !controllerLegible(incumbent)) throw deny('namespace-conflict');
  const markersAccounted = seated => {
    if (!hostBound) return true;
    // Frozen baseline key name (`zcodeAttributes`), kept verbatim for 0.9.0 installs.
    const ledger = slotValue(slotValue(seated, BASELINE_KEY), 'zcodeAttributes');
    return [shell, ...liveSurfaces()].every(node => {
      const marked = node.getAttribute(surfaceMarker);
      return marked === null || (marked === 'active' && ledger instanceof Map && ledger.has(node));
    });
  };
  if (!markersAccounted(incumbent)) throw deny('namespace-conflict');
  const residentSheet = document.getElementById(SHEET_ID);
  if (residentSheet && (!incumbent || residentSheet.getAttribute(SHEET_OWNER_ATTRIBUTE) !== controllerOwner)) {
    throw deny('style-id-conflict');
  }

  // ── Lease: one Blob URL with a single owner ─────────────────────────────
  // A Blob URL also sidesteps the token-size cap browsers impose on custom
  // properties, so the host has to permit blob: images for a scene to land.
  let sceneBytes;
  try { sceneBytes = Uint8Array.from(atob(encodedScene[2]), character => character.charCodeAt(0)); }
  catch { throw deny('invalid-local-image'); }
  const sceneURL = URL.createObjectURL(new Blob([sceneBytes], { type: 'image/' + encodedScene[1] }));
  let scene, sheetCommitted = false, urlRelinquished = false;
  const relinquishURL = () => {
    if (urlRelinquished) return;
    urlRelinquished = true;
    URL.revokeObjectURL(sceneURL);
    if (scene) scene.src = '';
  };

  // ── Decode: native promise first, pixel evidence second, deadline third ─
  // Evidence, never a styling decision: a stuck native decode may be
  // corroborated by drawing a bitmap onto a one-pixel scratch canvas and
  // reading that pixel back.
  function bitmapEvidence(element, bitmap) {
    let scratch = null;
    try {
      const measurable = !!bitmap && typeof bitmap.close === 'function'
        && bitmap.width === element.naturalWidth && bitmap.height === element.naturalHeight;
      if (!measurable) return false;
      scratch = document.createElement('canvas');
      scratch.width = 1;
      scratch.height = 1;
      const raster = scratch.getContext('2d', { willReadFrequently: true });
      if (!raster) return false;
      raster.drawImage(bitmap, 0, 0, 1, 1);
      const sample = raster.getImageData(0, 0, 1, 1)?.data ?? [];
      return sample.length >= 4
        && [sample[0], sample[1], sample[2], sample[3]].every(Number.isFinite);
    } catch { return false; }
    finally {
      if (scratch) { scratch.width = 0; scratch.height = 0; }
      try { bitmap?.close?.(); } catch {}
    }
  }
  function decodeWithCrossCheck(element) {
    return new Promise((resolve, reject) => {
      let decided = false;
      let crossCheck, deadline;
      const decide = (failure = null) => {
        if (decided) return;
        decided = true;
        clearTimeout(crossCheck);
        clearTimeout(deadline);
        if (failure) reject(failure);
        else resolve(true);
      };
      let native;
      try { native = element.decode(); }
      catch (failure) { native = Promise.reject(failure); }
      Promise.resolve(native).then(() => decide(), failure => decide(failure || deny('image-decode-failed')));
      if (typeof globalThis.createImageBitmap === 'function') {
        crossCheck = setTimeout(() => {
          const readyForEvidence = !decided && element.complete
            && element.naturalWidth > 0 && element.naturalHeight > 0;
          if (!readyForEvidence) return;
          let attempt;
          try { attempt = globalThis.createImageBitmap(element); }
          catch { return; }
          Promise.resolve(attempt).then(bitmap => {
            if (bitmapEvidence(element, bitmap)) decide();
          }, () => {});
        }, 250);
      }
      deadline = setTimeout(() => decide(deny('image-decode-timeout')), 4000);
    });
  }

  try {
    // ── Decode the leased scene ───────────────────────────────────────────
    scene = new Image();
    try {
      scene.src = sceneURL;
      await decodeWithCrossCheck(scene);
      if (!scene.naturalWidth || !scene.naturalHeight) throw deny('scene-without-extent');
    } catch (failure) {
      relinquishURL();
      throw deny(failure?.code === 'image-decode-timeout' ? 'image-decode-timeout' : 'image-decode-failed');
    }

    // ── Reconfirm: the page the brief was admitted to still exists ────────
    if ((typeof isCurrent === 'function' && !isCurrent())
        || !pageAdmitted() || !shell.isConnected
        || !shellUsable()) {
      relinquishURL();
      throw deny('page-changed-during-decode');
    }
    // The await left a window: read the slot again in case another apply
    // settled inside it. Both readings must agree with admission time — a
    // seat that vanished mid-decode is as much a change as a foreign one.
    const { placement: livePlacement, seated: activeNow } = seatedController();
    if (livePlacement && !controllerLegible(activeNow)) {
      relinquishURL();
      throw deny('namespace-changed-during-decode');
    }
    if (activeNow !== incumbent) {
      relinquishURL();
      throw deny('namespace-changed-during-decode');
    }
    if (!markersAccounted(activeNow)) {
      relinquishURL();
      throw deny('namespace-changed-during-decode');
    }
    const settledSheet = document.getElementById(SHEET_ID);
    if (settledSheet && (!activeNow || settledSheet.getAttribute(SHEET_OWNER_ATTRIBUTE) !== controllerOwner)) {
      relinquishURL();
      throw deny('style-id-conflict-after-decode');
    }

    // ── Compose: wash, snapshots, candidate sheet ─────────────────────────
    const tint = brief.strength ?? 42;
    const tintRatio = tint / 42;
    const tintRamp = [
      { mix: 24, at: '0%' }, { mix: 18, at: '22%' }, { mix: 12, at: '36%' },
      { mix: 16, at: '62%' }, { mix: 30, at: '73%' }, { mix: 65, at: '87%' }, { mix: 70, at: '100%' },
    ];
    const tintGradient = 'linear-gradient(90deg,' + tintRamp.map(({ mix, at }) => {
      const shown = Math.min(100, Math.round(mix * tintRatio));
      return 'color-mix(in srgb, var(--azhou-base) ' + (100 - shown) + '%, transparent) ' + at;
    }).join(',') + ')';
    const snapshotHostState = () => ({
      attribute: html.getAttribute(ACTIVATION),
      // The snapshot field is named `zcodeAttributes` on purpose: replacements
      // inherit recorded baselines from live 0.9.0 ZCode installs through
      // that exact key.
      zcodeAttributes: hostBound
        ? new Map([shell, ...liveSurfaces()].map(node => [node, node.getAttribute(surfaceMarker)]))
        : undefined,
      properties: new Map([SCENE_PROPERTY, TINT_PROPERTY, SURFACE_PROPERTY].map(name => [
        name, [html.style.getPropertyValue(name), html.style.getPropertyPriority(name)],
      ])),
    });
    const entrySnapshot = snapshotHostState();
    const inheritedRaw = incumbent ? slotValue(incumbent, BASELINE_KEY) ?? entrySnapshot : entrySnapshot;
    const inheritedSnapshot = {
      attribute: inheritedRaw.attribute,
      properties: new Map(inheritedRaw.properties),
      // Same frozen `zcodeAttributes` baseline key as above; inherited maps keep it.
      zcodeAttributes: hostBound ? new Map([...(inheritedRaw.zcodeAttributes ?? []),
        ...[...(entrySnapshot.zcodeAttributes ?? [])].filter(([node]) => !inheritedRaw.zcodeAttributes?.has(node))]) : undefined,
    };
    if (!inheritedSnapshot.properties.has(SURFACE_PROPERTY)) {
      inheritedSnapshot.properties.set(SURFACE_PROPERTY,
        [...entrySnapshot.properties.get(SURFACE_PROPERTY)]);
    }
    const residentSheetID = settledSheet?.id;
    const residentSheetEnabled = settledSheet?.disabled;
    const residentSheetText = settledSheet?.textContent;
    const candidate = document.createElement('style');
    candidate.id = SHEET_ID;
    candidate.setAttribute(SHEET_OWNER_ATTRIBUTE, controllerOwner);
    const candidateText = brief.css + (hostBound ? binding.css : '');
    candidate.textContent = candidateText;

    // ── Controller state and verification probe ───────────────────────────
    let retired = false, controller, releaseAttempted = false, surfaceOwned = false;
    let restoreSnapshot = entrySnapshot;
    const publishSurface = value => {
      html.style.setProperty(SURFACE_PROPERTY, value);
      surfaceOwned = html.style.getPropertyValue(SURFACE_PROPERTY) === value
        && html.style.getPropertyPriority(SURFACE_PROPERTY) === '';
    };
    const zeroAlphaColor = [/^rgba\([^)]*,\s*0(?:\.0+)?\)$/, /^color\([^)]*\/\s*0(?:\.0+)?\)$/];
    const isTransparent = color => color === 'transparent'
      || zeroAlphaColor.some(shape => shape.test(color));
    const isNeutral = value => !value || value === 'none';
    const insideProtectedRegion = node => !!node.closest(directory.protectedRegions);
    const decorativeWithin = selector => [...shell.querySelectorAll(selector)]
      .filter(node => node.isConnected && !insideProtectedRegion(node));
    // Diagnostics read only the named decorative layers and their generated
    // planes; selector text, typed values and image links never enter the
    // report.
    const layerPainted = layer => layer.display !== 'none' && layer.visibility !== 'hidden'
      && Number(layer.opacity) !== 0;
    const generatedContent = layer => layer.content !== 'none' && layer.content !== 'normal';
    function paintedPlanes(node) {
      const primary = getComputedStyle(node);
      if (!layerPainted(primary) || node.getClientRects().length === 0) return [];
      const generated = ['::before', '::after'].map(pseudo => getComputedStyle(node, pseudo))
        .filter(generatedContent)
        .filter(layerPainted);
      return [primary, ...generated];
    }
    const backgroundQuiet = layer => isTransparent(layer.backgroundColor) && isNeutral(layer.backgroundImage);
    const effectsQuiet = layer => isNeutral(layer.boxShadow) && isNeutral(layer.filter)
      && isNeutral(layer.backdropFilter) && isNeutral(layer.webkitBackdropFilter)
      && isNeutral(layer.maskImage) && isNeutral(layer.webkitMaskImage);
    const backgroundsQuiet = nodes => nodes.every(node => paintedPlanes(node).every(backgroundQuiet));
    const planesFullyQuiet = nodes => nodes.every(node => paintedPlanes(node)
      .every(layer => backgroundQuiet(layer) && effectsQuiet(layer)));
    function unclassifiedLayers(accounted) {
      const flagged = new Set();
      const classify = (node, category, requirePositioning = true) => {
        if (accounted.has(node) || insideProtectedRegion(node) || node.querySelector(directory.protectedRegions)) return;
        const computed = getComputedStyle(node);
        if (computed.pointerEvents !== 'none'
            || (requirePositioning && !['absolute', 'fixed', 'sticky'].includes(computed.position))) return;
        if (paintedPlanes(node).some(layer => !backgroundQuiet(layer) || !effectsQuiet(layer))) flagged.add(category);
      };
      // The wrapper sweep intentionally ignores the selector that already
      // matched: a child renamed inside the sticky wrapper has to fail its own
      // check instead of inheriting this pass.
      for (const wrapper of shell.querySelectorAll(directory.stickyShade)) {
        classify(wrapper, 'unmatched-sticky-decoration', false);
        for (const child of wrapper.children) classify(child, 'unmatched-sticky-decoration', false);
      }
      for (const plate of shell.querySelectorAll(directory.threadFooter)) {
        for (const child of plate.children) classify(child, 'unmatched-footer-decoration');
      }
      for (const node of shell.querySelectorAll(directory.scrollLayers)) {
        classify(node, 'unmatched-scroll-decoration');
      }
      // The catalogue stops at these three names; anything unrecognized is
      // reported, never papered over with CSS.
      return [...flagged].sort();
    }
    function probe() {
      if (retired) return { version: BUILD, applied: false, imageDecoded: false,
        matchedSurfaces: 0, transparentSurfaces: 0, backgroundMatched: false,
        rootClear: false, workspaceBackgroundClear: false, coverMatched: false, fixedViewport: false,
        footerSurfaces: 0, footerBackgroundClear: false, footerFadeSurfaces: 0, footerFadeClear: false,
        topFadeSurfaces: 0, topFadeClear: false, decorationEffectsClear: false, unsupportedDecorations: [],
        reason: 'disposed', imageSHA256: brief.imageSHA256 };
      const surfaces = liveSurfaces().filter(node => node.isConnected);
      const bodyLayer = getComputedStyle(document.body);
      const transparentSurfaces = surfaces.filter(node => {
        const computed = getComputedStyle(node);
        return isTransparent(computed.backgroundColor) && computed.backgroundImage === 'none';
      }).length;
      const workspacePanes = [...shell.querySelectorAll(directory.workspace)];
      const workspaceBackgroundClear = workspacePanes.every(node => {
        const pseudo = getComputedStyle(node, '::before');
        return pseudo.display === 'none' || pseudo.content === 'none'
          || (isTransparent(pseudo.backgroundColor) && pseudo.backgroundImage === 'none');
      });
      // Scroll shading hangs on a sibling branch rather than inside the
      // footer, and the top fade rests on the same opaque-surface premise.
      // All three groups — generated planes included — are inspected while
      // the composer stays untouched.
      const footerSurfaces = decorativeWithin(directory.threadFooter + ',' + directory.footerPlate);
      const footerFadeSurfaces = decorativeWithin(directory.footerFade);
      const topFadeSurfaces = decorativeWithin(directory.topFade);
      const footerBackgroundClear = backgroundsQuiet(footerSurfaces);
      const footerFadeClear = backgroundsQuiet(footerFadeSurfaces);
      const topFadeClear = backgroundsQuiet(topFadeSurfaces);
      const decorations = new Set([...footerSurfaces, ...footerFadeSurfaces, ...topFadeSurfaces]);
      const decorationEffectsClear = planesFullyQuiet([...decorations]);
      const unknownLayers = unclassifiedLayers(decorations);
      const imageDecoded = scene.complete && scene.naturalWidth > 0 && scene.naturalHeight > 0;
      const backgroundMatched = bodyLayer.backgroundImage.includes(sceneURL)
        && bodyLayer.getPropertyValue('--azhou-style-ready').trim() === 'ready';
      const washMatched = html.style.getPropertyValue(TINT_PROPERTY) === tintGradient
        && html.style.getPropertyPriority(TINT_PROPERTY) === '';
      // Background layer two is the scene itself: successful decoding says
      // nothing about whether the scene covers the viewport or still sits in
      // some earlier corner-sized box.
      const coverMatched = bodyLayer.backgroundSize.split(',')[1]?.trim() === 'cover';
      const fixedViewport = bodyLayer.backgroundAttachment.split(',').every(value => value.trim() === 'fixed');
      const shellLayer = getComputedStyle(shell);
      const rootClear = isTransparent(shellLayer.backgroundColor) && shellLayer.backgroundImage === 'none';
      const styleCount = document.querySelectorAll('#' + SHEET_ID).length;
      const applied = pageAdmitted() && imageDecoded && candidate.isConnected && styleCount === 1
        && html.getAttribute(ACTIVATION) === 'active'
        && surfaces.length > 0 && transparentSurfaces === surfaces.length
        && rootClear && workspaceBackgroundClear && footerBackgroundClear && backgroundMatched
        && washMatched
        && footerFadeClear && topFadeClear && decorationEffectsClear && unknownLayers.length === 0
        && coverMatched && fixedViewport;
      return {
        version: BUILD, applied, imageDecoded, matchedSurfaces: surfaces.length,
        backgroundMatched, washMatched, coverMatched, fixedViewport, transparentSurfaces, rootClear,
        workspaceBackgroundClear,
        footerSurfaces: footerSurfaces.length, footerBackgroundClear,
        footerFadeSurfaces: footerFadeSurfaces.length, footerFadeClear,
        topFadeSurfaces: topFadeSurfaces.length, topFadeClear, decorationEffectsClear,
        unsupportedDecorations: unknownLayers,
        imageSHA256: brief.imageSHA256,
        image: { width: scene.naturalWidth, height: scene.naturalHeight, displayMode: 'cover',
          viewport: { width: innerWidth, height: innerHeight },
          devicePixelRatio: devicePixelRatio || 1,
          rasterScale: Math.max(innerWidth / scene.naturalWidth, innerHeight / scene.naturalHeight)
            * Math.max(1, devicePixelRatio || 1),
          position: bodyLayer.backgroundPosition.split(',')[1]?.trim() },
        styleCount,
        persistentAnimation: false,
        verificationScope: hostBound ? binding.scope
          : 'decoded image, viewport cover, matched shell, footer and top fades, decorative planes and bounded unknown-layer checks; visual inspection is separate',
      };
    }

    // ── Controller lifecycle ──────────────────────────────────────────────
    function dispose() {
      if (retired) return probe();
      retired = true;
      const sheetStillAuthored = candidate.isConnected && candidate.parentNode === document.head
        && candidate.id === SHEET_ID && candidate.disabled === false
        && candidate.getAttribute(SHEET_OWNER_ATTRIBUTE) === controllerOwner
        && candidate.textContent === candidateText;
      if (sheetStillAuthored) candidate.remove();
      const shellStillCurrent = !hostBound || (shell.isConnected && document.getElementById('root') === shell);
      // Restore the frozen `zcodeAttributes` baseline records exactly as captured.
      for (const [node, marked] of restoreSnapshot.zcodeAttributes ?? []) {
        const markerRestorable = shellStillCurrent && node.isConnected
          && (node === shell || shell.contains(node))
          && node.getAttribute(surfaceMarker) === 'active';
        if (!markerRestorable) continue;
        if (marked === null) node.removeAttribute(surfaceMarker);
        else node.setAttribute(surfaceMarker, marked);
      }
      if (document.documentElement === html) {
        if (html.getAttribute(ACTIVATION) === 'active') {
          if (restoreSnapshot.attribute === null) html.removeAttribute(ACTIVATION);
          else html.setAttribute(ACTIVATION, restoreSnapshot.attribute);
        }
        for (const [name, [value, priority]] of restoreSnapshot.properties) {
          const asWritten = name === SCENE_PROPERTY ? 'url(' + JSON.stringify(sceneURL) + ')'
            : name === TINT_PROPERTY ? tintGradient : surfaceTint;
          if (typeof asWritten !== 'string') continue;
          const uneditedSinceCommit = html.style.getPropertyValue(name) === asWritten
            && html.style.getPropertyPriority(name) === '';
          if (!uneditedSinceCommit) continue;
          if (value) html.style.setProperty(name, value, priority);
          else html.style.removeProperty(name);
        }
      }
      relinquishURL();
      if (globalThis[CONTROLLER_SLOT] === controller) delete globalThis[CONTROLLER_SLOT];
      return probe();
    }
    // Replacement path: the successor already took the slot, so this teardown
    // removes only what this controller verifiably still owns.
    const handOverForReplacement = () => {
      retired = true;
      const sheetStillAuthored = candidate.isConnected && candidate.parentNode === document.head
        && (candidate.id === SHEET_ID && candidate.disabled === false
          || candidate.id === '' && candidate.disabled === true)
        && candidate.getAttribute(SHEET_OWNER_ATTRIBUTE) === controllerOwner
        && candidate.textContent === candidateText;
      if (sheetStillAuthored) candidate.remove();
      relinquishURL();
      if (globalThis[CONTROLLER_SLOT] === controller) delete globalThis[CONTROLLER_SLOT];
    };
    function updateSurface(value) {
      if (retired || slotValue(globalThis, CONTROLLER_SLOT) !== controller
          || document.documentElement !== html || !shell.isConnected
          || document.getElementById('root') !== shell || !colorPlausible(value)) return false;
      const valueNow = html.style.getPropertyValue(SURFACE_PROPERTY);
      const priorityNow = html.style.getPropertyPriority(SURFACE_PROPERTY);
      const untouched = entrySnapshot.properties.get(SURFACE_PROPERTY);
      const stillOurs = surfaceOwned
        ? valueNow === surfaceTint && priorityNow === ''
        : valueNow === untouched[0] && priorityNow === untouched[1];
      if (!stillOurs) return false;
      const next = value.trim();
      if (next !== surfaceTint || !surfaceOwned) {
        publishSurface(next);
        surfaceTint = next;
      }
      return surfaceOwned;
    }
    controller = { owner: controllerOwner, version: BUILD, status: probe, dispose, restore: dispose, updateSurface };
    Object.defineProperty(controller, RELEASE_KEY, { value: handOverForReplacement });

    // ── Transaction: one synchronous handover ─────────────────────────────
    try {
      // Nothing can paint between suspending the resident sheet and validating
      // the candidate. The resident sheet stays attached so a failed candidate
      // can bring it back without re-adding an inline style element that a
      // stricter content-security policy might reject.
      if (settledSheet) { settledSheet.disabled = true; settledSheet.removeAttribute('id'); }
      // Activate the surfaces recorded under the frozen `zcodeAttributes` key.
      for (const node of entrySnapshot.zcodeAttributes?.keys() ?? []) node.setAttribute(surfaceMarker, 'active');
      html.style.setProperty(SCENE_PROPERTY, 'url(' + JSON.stringify(sceneURL) + ')');
      html.style.setProperty(TINT_PROPERTY, tintGradient);
      if (surfaceTint !== null) publishSurface(surfaceTint);
      html.setAttribute(ACTIVATION, 'active');
      document.head.appendChild(candidate);
      let outcome = probe();
      if (!outcome.applied) throw deny('styles-not-effective: ' + JSON.stringify(outcome));
      if (activeNow) {
        const stepAside = activeNow[RELEASE_KEY];
        if (typeof stepAside === 'function') {
          restoreSnapshot = inheritedSnapshot;
          Object.defineProperty(controller, BASELINE_KEY, { value: restoreSnapshot });
          globalThis[CONTROLLER_SLOT] = controller;
          releaseAttempted = true;
          stepAside.call(activeNow);
        } else {
          activeNow.dispose();
          // A legacy install from before conditional restore remains a known
          // owner: its own dispose just restored the host baseline it
          // remembered, so the snapshot is retaken from the live page.
          restoreSnapshot = snapshotHostState();
          restoreSnapshot.properties.set(TINT_PROPERTY, [...entrySnapshot.properties.get(TINT_PROPERTY)]);
          restoreSnapshot.properties.set(SURFACE_PROPERTY, [...entrySnapshot.properties.get(SURFACE_PROPERTY)]);
          html.style.setProperty(SCENE_PROPERTY, 'url(' + JSON.stringify(sceneURL) + ')');
          html.style.setProperty(TINT_PROPERTY, tintGradient);
          if (surfaceTint !== null) publishSurface(surfaceTint);
          html.setAttribute(ACTIVATION, 'active');
          outcome = probe();
          if (!outcome.applied) throw deny('styles-not-effective-after-replacement');
          Object.defineProperty(controller, BASELINE_KEY, { value: restoreSnapshot });
          globalThis[CONTROLLER_SLOT] = controller;
        }
      }
      if (!activeNow) {
        Object.defineProperty(controller, BASELINE_KEY, { value: restoreSnapshot });
        globalThis[CONTROLLER_SLOT] = controller;
      } else if (typeof slotValue(controller, BASELINE_KEY) !== 'object') {
        Object.defineProperty(controller, BASELINE_KEY, { value: restoreSnapshot });
      }
      sheetCommitted = true;
      return outcome;
    } catch (error) {
      // Recovery ladder. Revival is offered only when the resident sheet was
      // verifiably suspended by this attempt and the slot still points here;
      // otherwise the incumbent is left exactly as the failure left it.
      const residentSuspendedIntact = !!settledSheet && settledSheet.isConnected
        && settledSheet.parentNode === document.head && settledSheet.id === ''
        && settledSheet.disabled === true
        && settledSheet.getAttribute(SHEET_OWNER_ATTRIBUTE) === controllerOwner
        && settledSheet.textContent === residentSheetText;
      const canRevive = releaseAttempted && globalThis[CONTROLLER_SLOT] === controller
        && residentSuspendedIntact;
      if (canRevive) restoreSnapshot = entrySnapshot;
      dispose();
      if (canRevive && !Object.hasOwn(globalThis, CONTROLLER_SLOT)) {
        settledSheet.id = residentSheetID;
        settledSheet.disabled = residentSheetEnabled;
        let incumbentUsable = false;
        try { incumbentUsable = Reflect.apply(slotValue(activeNow, 'status'), activeNow, [])?.applied === true; } catch {}
        const residentRevivedIntact = settledSheet.isConnected && settledSheet.parentNode === document.head
          && settledSheet.id === residentSheetID && settledSheet.disabled === residentSheetEnabled
          && settledSheet.getAttribute(SHEET_OWNER_ATTRIBUTE) === controllerOwner
          && settledSheet.textContent === residentSheetText;
        if (incumbentUsable && !Object.hasOwn(globalThis, CONTROLLER_SLOT)) {
          // Re-seat the incumbent under its original descriptor, not a plain
          // assignment: observers may be watching how the slot is defined.
          Object.defineProperty(globalThis, CONTROLLER_SLOT, livePlacement);
        } else if (!Object.hasOwn(globalThis, CONTROLLER_SLOT) && residentRevivedIntact) {
          settledSheet.disabled = true;
          settledSheet.removeAttribute('id');
        }
      } else if (!releaseAttempted && !sheetCommitted && activeNow
          && globalThis[CONTROLLER_SLOT] === activeNow && !!settledSheet?.isConnected
          && settledSheet.id === '' && settledSheet.disabled === true) {
        settledSheet.id = residentSheetID;
        settledSheet.disabled = residentSheetEnabled;
      }
      throw error;
    }
  } finally {
    if (!sheetCommitted) relinquishURL();
  }
}
