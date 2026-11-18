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
  const DECODE_TIMEOUT_MS = 4000; // Existing decode anti-hang ceiling, not a presentation or recovery SLO.
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
  const MARKER_KEY = '__azhouWallpaperMarker_090';
  const SUSPEND_KEY = '__azhouWallpaperSuspend_090';
  const PENDING_KEY = '__azhouWallpaperPending_090';
  const DEACTIVATE_KEY = '__azhouWallpaperDeactivate_090';
  const transactional = offered?.transactional === true;

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
  directory.footerFade = directory.stickyShade + ' > ' + generatedLayer('_background_') + generatedLayer('_fade_')
    + ',' + directory.stickyShade + ' > [aria-hidden="true"].pointer-events-none'
    + generatedLayer('background-') + generatedLayer('fade-');
  directory.topFade = '[data-app-shell-main-surface] ' + generatedLayer('_MainContentTopFade_');
  directory.scrollLayers = directory.scrollTrack + ' :is('
    + generatedLayer('_background_') + ',' + generatedLayer('_fade_') + ','
    + generatedLayer('background-') + ',' + generatedLayer('fade-') + ')';

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
  const signal = slotValue(offered, 'signal');
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
  const workspaceObservation = slotValue(offered, 'workspaceObservation');
  const onWorkspaceInvalidated = slotValue(offered, 'onWorkspaceInvalidated');
  const onDecodeAdmitted = slotValue(offered, 'onDecodeAdmitted');
  const workspaceCheck = slotValue(hostAdapter, 'isWorkspaceCurrent');
  const workspaceWatch = slotValue(hostAdapter, 'watchWorkspace');
  let workspaceInvalidated = false;
  let workspaceLease;
  const workspaceDeclared = hostAdapter && ['object', 'function'].includes(typeof hostAdapter) && 'workspaceContract' in hostAdapter;
  const workspaceBound = !ports && slotValue(hostAdapter, 'workspaceContract') === 'codex-active-workspace/v1'
    && workspaceObservation?.kind === 'observed'
    && typeof slotValue(hostAdapter, 'observeWorkspace') === 'function' && typeof workspaceCheck === 'function'
    && typeof workspaceWatch === 'function'
    && Array.isArray(workspaceObservation.knownPaintPlanes) && workspaceObservation.knownPaintPlanes.length > 0;
  const workspaceCurrent = () => {
    try { return workspaceBound && !workspaceInvalidated && (!workspaceLease || workspaceLease.current()) && slotValue(hostAdapter, 'isWorkspaceCurrent') === workspaceCheck
      && slotValue(hostAdapter, 'watchWorkspace') === workspaceWatch
      && Reflect.apply(workspaceCheck, hostAdapter, [workspaceObservation, globalThis]); }
    catch { return false; }
  };
  if ((workspaceDeclared && !workspaceBound) || (hostAdapter && !hostBound && !workspaceBound)) throw deny('invalid-host-adapter');
  const surfaceMarker = hostBound ? binding.surfaceMarker : null;
  if (hostBound) controllerOwner = slotValue(slotValue(hostAdapter, 'controllerWallpaper'), 'owner') ?? controllerOwner;

  // ── Gate 2: page identity ───────────────────────────────────────────────
  function pageAdmitted() {
    if (window.top !== window) return false;
    if (workspaceBound) return workspaceCurrent();
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
    themeState: offered?.themeState, mainPaint: offered?.mainPaint,
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
  const dshCapture=slotValue(hostAdapter,'captureThemeSurface');
  const dshBound=hostBound && slotValue(hostAdapter,'themeSelectionContract')==='dsh-owned-main-paint/v2'
    && typeof dshCapture==='function';
  const dshSurface=dshBound && (transactional || brief.mainPaint!=null)
    ? Reflect.apply(dshCapture,hostAdapter,[globalThis]):null;
  const dshCurrent=()=>!!dshSurface && slotValue(hostAdapter,'captureThemeSurface')===dshCapture
    && dshSurface.current()===true;
  const paintNode=workspaceBound?workspaceObservation.mainPaint?.node:dshSurface?.node;
  let mainPaint = null;
  if (brief.mainPaint != null) {
    const value = brief.mainPaint;
    const exact = (object, keys) => !!object && typeof object === 'object' && !Array.isArray(object)
      && Object.keys(object).length === keys.length && keys.every(key => Object.hasOwn(object, key));
    if (!(workspaceBound && workspaceObservation.mainPaint?.contract === 'codex-owned-main-paint/v1'
      && workspaceObservation.mainPaint.node === workspaceObservation.activeMain || dshBound && dshCurrent()) || brief.themeState != null
      || !exact(value, ['profile','rgba','backgroundImage','sourceDeclarationCount'])
      || value.profile !== 'codex-main-literal-paint/v1' || value.backgroundImage !== 'none'
      || !Array.isArray(value.rgba) || value.rgba.length !== 4
      || !value.rgba.every((channel, index) => Number.isFinite(channel) && channel >= 0 && channel <= (index === 3 ? 1 : 255))
      || !Number.isInteger(value.sourceDeclarationCount) || value.sourceDeclarationCount < 1 || value.sourceDeclarationCount > 128) {
      throw deny('main-paint-unsupported');
    }
    mainPaint = Object.freeze({ rgba: Object.freeze([...value.rgba]), sourceDeclarationCount: value.sourceDeclarationCount });
  }
  let surfaceTint = typeof brief.surface === 'string' ? brief.surface.trim() : null;
  const encodedScene = typeof brief.image === 'string'
    && /^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$/.exec(brief.image);
  if (!encodedScene || brief.image.length > 16 * 1024 * 1024) throw deny('invalid-local-image');

  // ── Gate 4: shell ───────────────────────────────────────────────────────
  const shell = document.getElementById('root');
  const liveSurfaces = () => {
    if (!shell) return [];
    if (workspaceBound) return workspaceCurrent() ? workspaceObservation.knownPaintPlanes
      .filter(plane => plane.kind === 'surface').map(plane => plane.node) : [];
    if (!hostBound) return [...shell.querySelectorAll(directory.shellSurfaces)];
    const nominated = Reflect.apply(binding.surfaces, ports, [globalThis]);
    return Array.isArray(nominated) && nominated.length === 1 && nominated.every(node => node?.isConnected
      && shell.contains(node) && !node.closest('[role="dialog"],dialog,iframe,webview')) ? nominated : [];
  };
  const shellUsable = () => workspaceBound ? workspaceObservation.shell === shell
    && workspaceCurrent() && liveSurfaces().length > 0 : hostBound
    ? Reflect.apply(binding.shellState, ports, [isCurrent, globalThis]) === 'ready' && liveSurfaces().length === 1
    : !!shell?.querySelector('[data-app-shell-frame]')
      && !!shell?.querySelector('[data-app-shell-main-surface],[data-app-shell-page-surface]');
  if (!document.body || !shell || !shellUsable()) throw deny('unsupported-shell-no-surfaces');
  const geometryReader = slotValue(hostAdapter, 'readThemeGeometry');
  const readThemeGeometry = () => {
    try {
    if (!workspaceBound || slotValue(hostAdapter, 'themeGeometryContract') !== 'codex-theme-geometry/v1'
      || typeof geometryReader !== 'function' || slotValue(hostAdapter, 'readThemeGeometry') !== geometryReader) return null;
    const geometry = Reflect.apply(geometryReader, hostAdapter, [workspaceObservation, globalThis]);
    if (geometry?.kind !== 'observed' || geometry.contract !== 'codex-theme-geometry/v1'
      || geometry.documentToken !== workspaceObservation.documentToken
      || geometry.workspaceEpoch !== workspaceObservation.workspaceEpoch) return null;
    const rect = geometry.rect, viewport = geometry.viewport;
    if (!rect || !viewport || ![rect.x, rect.y, rect.width, rect.height, viewport.width, viewport.height].every(Number.isFinite)
      || rect.width <= 0 || rect.height <= 0 || viewport.width <= 0 || viewport.height <= 0
      || viewport.width !== innerWidth || viewport.height !== innerHeight
      || Object.values(rect).some(value => Math.abs(value) > 10000000)) return null;
    return geometry;
    } catch { return null; }
  };
  if (brief.themeState && !readThemeGeometry()) throw deny('theme-surface-unsupported');

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
  if (slotValue(incumbent, PENDING_KEY)?.() === true) throw deny('activation-in-progress');
  if (transactional && (!(workspaceBound || dshBound && dshCurrent()) || incumbent && typeof slotValue(incumbent, SUSPEND_KEY) !== 'function')) {
    throw deny('reversible-activation-unsupported');
  }
  const residentSheet = document.getElementById(SHEET_ID);
  if (residentSheet && (!incumbent || residentSheet.getAttribute(SHEET_OWNER_ATTRIBUTE) !== controllerOwner)) {
    throw deny('style-id-conflict');
  }

  if (transactional && brief.strength === 0 && !mainPaint) {
    if (brief.themeState != null) throw deny('theme-surface-unsupported');
    if (signal && (typeof signal.addEventListener!=='function' || typeof signal.removeEventListener!=='function' || signal.aborted)
      || typeof isCurrent==='function' && !isCurrent()) throw deny('operation-cancelled');
    const disableCurrent=()=> (!dshSurface || dshCurrent()) && (typeof isCurrent!=='function' || isCurrent());
    if(dshSurface && !dshSurface.watch(()=>{}))throw deny('main-paint-unsupported');
    const wrapDisabled=result=>{
      if(!dshSurface)return result;
      const original=result.transaction;let terminal=null,terminalResult=false;
      const cleanup=()=>{dshSurface.dispose();signal?.removeEventListener('abort',rollback);};
      const rollback=()=>{if(terminal)return terminal==='rollback'&&terminalResult;terminal='rollback';try{return terminalResult=original.rollback();}finally{cleanup();}};
      signal?.addEventListener('abort',rollback,{once:true});
      return {...result,transaction:Object.freeze({current:()=>disableCurrent()&&original.current(),rollback,
        finalize(){if(terminal)return terminal==='finalize'&&terminalResult;
          try{if(!disableCurrent()){terminal='rollback';terminalResult=original.rollback();return false;}terminal='finalize';return terminalResult=original.finalize();}finally{cleanup();}}})};
    };
    if (incumbent) {
      const deactivate=slotValue(incumbent,DEACTIVATE_KEY);
      if (typeof deactivate!=='function') throw deny('reversible-activation-unsupported');
      try{return wrapDisabled(deactivate(disableCurrent,signal));}catch(error){dshSurface?.dispose();throw error;}
    }
    let phase='pending';
    const current=()=>phase==='pending' && !signal?.aborted && disableCurrent()
      && document.documentElement===html && pageAdmitted() && shellUsable()
      && !Object.hasOwn(globalThis,CONTROLLER_SLOT) && !document.getElementById(SHEET_ID);
    return wrapDisabled({applied:true,disabled:true,imageDecoded:false,transaction:Object.freeze({current,
      finalize(){if(phase!=='pending')return phase==='finalized';if(!current()){phase='rolled-back';return false;}phase='finalized';return true;},
      rollback(){if(phase!=='pending')return phase==='rolled-back';phase='rolled-back';return true;},
    })});
  }

  // ── Lease: one Blob URL with a single owner ─────────────────────────────
  // A Blob URL also sidesteps the token-size cap browsers impose on custom
  // properties, so the host has to permit blob: images for a scene to land.
  let sceneBytes;
  try { sceneBytes = Uint8Array.from(atob(encodedScene[2]), character => character.charCodeAt(0)); }
  catch { throw deny('invalid-local-image'); }
  const sceneURL = URL.createObjectURL(new Blob([sceneBytes], { type: 'image/' + encodedScene[1] }));
  let scene, sheetCommitted = false, urlRelinquished = false;
  let invalidateWorkspace = () => {};
  let themeGeometry = null, geometrySubscribed = false;
  let geometryChanged = geometry => { themeGeometry = geometry; };
  let maskGeneration = 0;
  let cancelScene = () => {};
  let rollbackActivation = null;
  const abortPending = () => { cancelScene(); cancelMasks(); rollbackActivation?.(); };
  const maskJobs = new Set();
  const cancelMasks = () => { maskGeneration++; for (const cancel of [...maskJobs]) { try { cancel(); } catch {} } };
  const decodeMask = source => new Promise((resolve, reject) => {
    const image = new Image();
    let settled = false, timer;
    const finish = failure => {
      if (settled) return;
      settled = true; clearTimeout(timer); maskJobs.delete(cancel);
      try { image.src = ''; } catch {}
      if (failure) reject(failure); else resolve(source);
    };
    const cancel = () => finish(deny('theme-mask-cancelled'));
    maskJobs.add(cancel);
    timer = setTimeout(() => finish(deny('theme-mask-decode-timeout')), DECODE_TIMEOUT_MS);
    try { image.src = source; Promise.resolve(image.decode()).then(() => finish(), () => finish(deny('theme-mask-decode-failed'))); }
    catch { finish(deny('theme-mask-decode-failed')); }
  });
  const relinquishURL = () => {
    if (urlRelinquished) return;
    urlRelinquished = true;
    cancelMasks();
    dshSurface?.dispose();
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
        cancelScene = () => {};
        clearTimeout(crossCheck);
        clearTimeout(deadline);
        if (failure) reject(failure);
        else resolve(true);
      };
      cancelScene = () => { decide(deny('operation-cancelled')); try { element.src = ''; } catch {} };
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
      deadline = setTimeout(() => decide(deny('image-decode-timeout')), DECODE_TIMEOUT_MS);
    });
  }

  try {
    if (signal) {
      if (typeof signal.addEventListener !== 'function' || typeof signal.removeEventListener !== 'function' || signal.aborted) throw deny('operation-cancelled');
      signal.addEventListener('abort', abortPending, { once: true });
    }
    if(dshSurface && !dshSurface.watch(()=>{cancelMasks();invalidateWorkspace();}))throw deny('main-paint-unsupported');
    if (workspaceBound) workspaceLease = Reflect.apply(workspaceWatch, hostAdapter, [workspaceObservation,
      () => { workspaceInvalidated = true; cancelMasks(); invalidateWorkspace(); }, globalThis,
      brief.themeState ? { onThemeGeometry: geometry => { geometrySubscribed = true; geometryChanged(geometry); } } : {}]);
    if (brief.themeState && !geometrySubscribed) throw deny('theme-surface-unsupported');
    if (workspaceBound && typeof onDecodeAdmitted === 'function') {
      if (!workspaceLease || !workspaceCurrent() || (typeof isCurrent === 'function' && !isCurrent())) throw deny('operation-cancelled');
      const admittedLease = workspaceLease;
      onDecodeAdmitted(Object.freeze({ contract: 'codex-workspace-decode/v1',
        documentToken: workspaceObservation.documentToken, workspaceEpoch: workspaceObservation.workspaceEpoch,
        current: () => workspaceLease === admittedLease && workspaceCurrent() }));
    }
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
        || dshSurface && !dshCurrent() || !pageAdmitted() || !shell.isConnected
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
    let themeAlpha = null;
    if (brief.themeState != null) {
      const state = brief.themeState;
      const preference = state?.preferencesByTheme?.['azhou-q-v3'];
      const capability = workspaceObservation?.themeSurfaces;
      if (!workspaceBound || capability?.contract !== 'codex-theme-surfaces/v1'
        || capability.workspaceReadability !== workspaceObservation.activeMain
        || state.schemaVersion !== 1 || state.activeThemeId !== 'azhou-q-v3'
        || !preference || !['follow', 'override'].includes(preference.mode)
        || (preference.mode === 'override' && (!Number.isFinite(preference.value)
          || preference.value < 0 || preference.value > 100))) throw deny('theme-surface-unsupported');
      themeAlpha = preference.mode === 'follow' ? .7 : (100 - preference.value) / 100;
    }
    const tint = brief.strength ?? 42;
    const tintRatio = tint / 42;
    const tintRamp = [
      { mix: 24, at: '0%' }, { mix: 18, at: '22%' }, { mix: 12, at: '36%' },
      { mix: 16, at: '62%' }, { mix: 30, at: '73%' }, { mix: 65, at: '87%' }, { mix: 70, at: '100%' },
    ];
    let tintGradient = 'linear-gradient(90deg,' + tintRamp.map(({ mix, at }) => {
      const shown = Math.min(100, Math.round(mix * tintRatio));
      return 'color-mix(in srgb, var(--azhou-base) ' + (100 - shown) + '%, transparent) ' + at;
    }).join(',') + ')';
    if (mainPaint) tintGradient = 'linear-gradient(transparent,transparent)';
    const legacyGradient = tintGradient;
    const planeNodes = kind => workspaceObservation.knownPaintPlanes.filter(plane => plane.kind === kind).map(plane => plane.node);
    const markerNames = { surface: 'data-azhou-wallpaper-plane', workspace: 'data-azhou-wallpaper-pseudo',
      footer: 'data-azhou-wallpaper-decoration', fade: 'data-azhou-wallpaper-decoration', top: 'data-azhou-wallpaper-decoration' };
    const markerTargets = new Map();
    if (!hostBound) {
      const planes = workspaceBound ? workspaceObservation.knownPaintPlanes : [
        ...[shell, ...liveSurfaces()].map(node => ({ kind: 'surface', node })),
        ...[...shell.querySelectorAll(directory.workspace)].map(node => ({ kind: 'workspace', node })),
        ...[...shell.querySelectorAll(directory.threadFooter + ',' + directory.footerPlate + ',' + directory.footerFade + ',' + directory.topFade)]
          .filter(node => !node.closest(directory.protectedRegions)).map(node => ({ kind: 'footer', node })),
      ];
      for (const { node, kind } of planes) {
        const attribute = markerNames[kind];
        if (!attribute || !node?.isConnected || node !== shell && !shell.contains(node)) throw deny('unsupported-shell-no-surfaces');
        const marked = node.getAttribute(attribute);
        if (marked !== null && (marked !== slotValue(incumbent, MARKER_KEY)
          || !slotValue(incumbent, BASELINE_KEY)?.codexMarkers?.get(node)?.has(attribute))) throw deny('namespace-conflict');
        if (!markerTargets.has(node)) markerTargets.set(node, new Set());
        markerTargets.get(node).add(attribute);
      }
    }
    if (mainPaint) {
      const node = paintNode;
      const attribute = 'data-azhou-dream-main';
      const marked = node.getAttribute(attribute);
      if (marked !== null && (marked !== slotValue(incumbent, MARKER_KEY)
        || !slotValue(incumbent, BASELINE_KEY)?.codexMarkers?.get(node)?.has(attribute))) throw deny('namespace-conflict');
      if(dshBound && node===dshSurface.node && dshCurrent())markerTargets.set(node,new Set());
      if (!markerTargets.has(node)) throw deny('main-paint-unsupported');
      markerTargets.get(node).add(attribute);
    }
    let themeApplied = themeAlpha === null, themePending = false, themeFailure = '';
    const geometryKey = geometry => JSON.stringify([geometry.rect, geometry.viewport]);
    const maskSource = (geometry, color) => {
      if (!colorPlausible(color)) throw deny('theme-color-unsupported');
      const escaped = color.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
      const { rect, viewport } = geometry;
      const attributes = 'x="' + rect.x + '" y="' + rect.y + '" width="' + rect.width + '" height="' + rect.height + '"';
      const stops = tintRamp.map(({ mix, at }) => '<stop offset="' + at + '" stop-color="' + escaped
        + '" stop-opacity="' + (1 - Math.min(100, Math.round(mix * tintRatio)) / 100) + '"/>').join('');
      const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + viewport.width + '" height="' + viewport.height
        + '" viewBox="0 0 ' + viewport.width + ' ' + viewport.height + '"><defs><linearGradient id="g">' + stops
        + '</linearGradient><mask id="m"><rect width="100%" height="100%" fill="white"/><rect ' + attributes
        + ' fill="black"/></mask></defs><rect width="100%" height="100%" fill="url(#g)" mask="url(#m)"/><rect '
        + attributes + ' fill="' + escaped + '" fill-opacity="' + themeAlpha + '"/></svg>';
      return 'data:image/svg+xml,' + encodeURIComponent(svg);
    };
    const maskColor = () => surfaceTint ?? getComputedStyle(document.body).backgroundColor;
    if (themeAlpha !== null) {
      themeGeometry = readThemeGeometry();
      if (!themeGeometry) throw deny('theme-surface-unsupported');
      const admittedGeometry = geometryKey(themeGeometry);
      const source = await decodeMask(maskSource(themeGeometry, maskColor()));
      const fresh = readThemeGeometry();
      if (!fresh || admittedGeometry !== geometryKey(fresh) || !workspaceCurrent()
        || (typeof isCurrent === 'function' && !isCurrent()) || seatedController().seated !== activeNow) throw deny('theme-mask-stale');
      tintGradient = 'url(' + JSON.stringify(source) + ')';
      themeApplied = true;
    }
    const snapshotHostState = () => ({
      codexMarkers: new Map([...markerTargets].map(([node, attributes]) => [node,
        new Map([...attributes].map(attribute => [attribute, node.getAttribute(attribute)]))])),
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
      codexMarkers: new Map([...entrySnapshot.codexMarkers].map(([node, attributes]) => [node,
        new Map([...attributes].map(([attribute, value]) => [attribute,
          inheritedRaw.codexMarkers?.get(node)?.has(attribute) ? inheritedRaw.codexMarkers.get(node).get(attribute) : value]))])),
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
    const paintRule = mainPaint ? '\nhtml[data-azhou-wallpaper="active"] #root [data-azhou-dream-main][data-azhou-dream-main=' + JSON.stringify(sceneURL) + ']{background-color:rgba('
      + mainPaint.rgba.join(',') + ')!important;background-image:none!important;}' : '';
    const candidateText = brief.css.replaceAll('__AZHOU_WALLPAPER_INSTANCE__', JSON.stringify(sceneURL))
      + (hostBound ? binding.css : '') + paintRule;
    candidate.textContent = candidateText;

    // ── Controller state and verification probe ───────────────────────────
    let retired = false, suspended = false, controller, releaseAttempted = false, surfaceOwned = false;
    let disableOperation=null;
    let activationPhase = transactional ? 'preparing' : 'finalized';
    let suspendedGeometryKey = null;
    let restoreSnapshot = entrySnapshot;
    const attemptCleanup = operation => { try { operation(); } catch {} };
    const stopWatching = () => { attemptCleanup(() => workspaceLease?.dispose()); workspaceLease = null; };
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
      if (workspaceBound) {
        for (const { node, category, requirePositioning } of workspaceObservation.unknownCandidates) classify(node, category, requirePositioning);
        return [...flagged].sort();
      }
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
      if (dshSurface && sheetCommitted && !retired && !suspended && !dshCurrent()) return dispose();
      if (workspaceBound && sheetCommitted && !retired && !suspended && !workspaceCurrent()) return dispose();
      if (retired) return { version: BUILD, applied: false, imageDecoded: false,
        matchedSurfaces: 0, transparentSurfaces: 0, backgroundMatched: false,
        rootClear: false, workspaceBackgroundClear: false, coverMatched: false, fixedViewport: false,
        footerSurfaces: 0, footerBackgroundClear: false, footerFadeSurfaces: 0, footerFadeClear: false,
        topFadeSurfaces: 0, topFadeClear: false, decorationEffectsClear: false, unsupportedDecorations: [],
        reason: 'disposed', imageSHA256: brief.imageSHA256 };
      const surfaces = liveSurfaces().filter(node => node.isConnected);
      const bodyLayer = getComputedStyle(document.body);
      const themeMatched = themeAlpha === null || themeApplied;
      let mainPaintApplied = false;
      if (mainPaint) {
        const node = paintNode;
        const computed = getComputedStyle(node);
        const color = /^rgba?\(\s*([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)(?:\s*[,/]\s*([\d.]+))?\s*\)$/.exec(computed.backgroundColor);
        const rgba = color ? [+color[1],+color[2],+color[3],color[4] === undefined ? 1 : +color[4]] : null;
        mainPaintApplied = node.getAttribute('data-azhou-dream-main') === sceneURL
          && computed.backgroundImage === 'none' && !!rgba && rgba.every((channel, index) =>
            Math.abs(channel - (index === 3 ? mainPaint.rgba[index] : Math.round(mainPaint.rgba[index]))) < .001);
      }
      const clearSurfaces = mainPaint ? surfaces.filter(node => node !== paintNode) : surfaces;
      const transparentSurfaces = clearSurfaces.filter(node => {
        const computed = getComputedStyle(node);
        return isTransparent(computed.backgroundColor) && computed.backgroundImage === 'none';
      }).length;
      const workspacePanes = workspaceBound ? planeNodes('workspace') : [...shell.querySelectorAll(directory.workspace)];
      const workspaceBackgroundClear = workspacePanes.every(node => {
        const pseudo = getComputedStyle(node, '::before');
        return pseudo.display === 'none' || pseudo.content === 'none'
          || (isTransparent(pseudo.backgroundColor) && pseudo.backgroundImage === 'none');
      });
      // Scroll shading hangs on a sibling branch rather than inside the
      // footer, and the top fade rests on the same opaque-surface premise.
      // All three groups — generated planes included — are inspected while
      // the composer stays untouched.
      const footerSurfaces = workspaceBound ? planeNodes('footer') : decorativeWithin(directory.threadFooter + ',' + directory.footerPlate);
      const footerFadeSurfaces = workspaceBound ? planeNodes('fade') : decorativeWithin(directory.footerFade);
      const topFadeSurfaces = workspaceBound ? planeNodes('top') : decorativeWithin(directory.topFade);
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
        && (!mainPaint || mainPaintApplied) && surfaces.length > 0 && transparentSurfaces === clearSurfaces.length && themeMatched
        && rootClear && workspaceBackgroundClear && footerBackgroundClear && backgroundMatched
        && washMatched
        && footerFadeClear && topFadeClear && decorationEffectsClear && unknownLayers.length === 0
        && coverMatched && fixedViewport;
      return {
        version: BUILD, applied, imageDecoded, matchedSurfaces: surfaces.length,
        ...(mainPaint ? { mainPaintApplied, profile: 'codex-main-literal-paint/v1', sourceDeclarationCount: mainPaint.sourceDeclarationCount } : {}),
        backgroundMatched, washMatched, coverMatched, fixedViewport, transparentSurfaces, rootClear, themeMatched,
        ...(themeAlpha !== null ? { themeApplied, themePending, themeFailure, fallbackApplied: !themeApplied && backgroundMatched && washMatched } : {}),
        workspaceBackgroundClear,
        ...(workspaceBound ? { coverage: workspaceObservation.coverage, fullCoverage: false,
          workspaceEpoch: workspaceObservation.workspaceEpoch } : {}),
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
        verificationScope: workspaceBound ? 'observed active workspace paint planes only; unknown messaging and auxiliary coverage remains unverified' : hostBound ? binding.scope
          : 'decoded image, viewport cover, matched shell, footer and top fades, decorative planes and bounded unknown-layer checks; visual inspection is separate',
      };
    }

    // ── Controller lifecycle ──────────────────────────────────────────────
    function dispose() {
      if (activationPhase === 'pending') { rollback(); return probe(); }
      disableOperation?.abandon();
      if (retired) return probe();
      const ownsRootState = slotValue(globalThis, CONTROLLER_SLOT) === controller
        || (!sheetCommitted && slotValue(globalThis, CONTROLLER_SLOT) === incumbent);
      retired = true;
      stopWatching();
      cancelMasks();
      const sheetStillAuthored = candidate.isConnected && candidate.parentNode === document.head
        && candidate.id === SHEET_ID && candidate.disabled === false
        && candidate.getAttribute(SHEET_OWNER_ATTRIBUTE) === controllerOwner
        && candidate.textContent === candidateText;
      if (sheetStillAuthored) attemptCleanup(() => candidate.remove());
      for (const [node, attributes] of restoreSnapshot.codexMarkers ?? []) {
        for (const [attribute, previous] of attributes) attemptCleanup(() => {
          if (node.getAttribute(attribute) !== sceneURL) return;
          if (previous === null) node.removeAttribute(attribute);
          else node.setAttribute(attribute, previous);
        });
      }
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
      if (document.documentElement === html && (!(workspaceBound || dshSurface) || ownsRootState)) {
        attemptCleanup(() => {
          if (html.getAttribute(ACTIVATION) === 'active') {
            if (restoreSnapshot.attribute === null) html.removeAttribute(ACTIVATION);
            else html.setAttribute(ACTIVATION, restoreSnapshot.attribute);
          }
        });
        for (const [name, [value, priority]] of restoreSnapshot.properties) {
          const asWritten = name === SCENE_PROPERTY ? 'url(' + JSON.stringify(sceneURL) + ')'
            : name === TINT_PROPERTY ? tintGradient : surfaceTint;
          if (typeof asWritten !== 'string') continue;
          const uneditedSinceCommit = html.style.getPropertyValue(name) === asWritten
            && html.style.getPropertyPriority(name) === '';
          if (!uneditedSinceCommit) continue;
          attemptCleanup(() => {
            if (value) html.style.setProperty(name, value, priority);
            else html.style.removeProperty(name);
          });
        }
      }
      attemptCleanup(relinquishURL);
      if (globalThis[CONTROLLER_SLOT] === controller) delete globalThis[CONTROLLER_SLOT];
      return probe();
    }
    // Replacement path: the successor already took the slot, so this teardown
    // removes only what this controller verifiably still owns.
    const handOverForReplacement = () => {
      disableOperation?.abandon();
      retired = true;
      stopWatching();
      cancelMasks();
      for (const [node, attributes] of restoreSnapshot.codexMarkers ?? []) {
        for (const [attribute, previous] of attributes) attemptCleanup(() => {
          if (node.getAttribute(attribute) !== sceneURL) return;
          if (previous === null) node.removeAttribute(attribute);
          else node.setAttribute(attribute, previous);
        });
      }
      const sheetStillAuthored = candidate.isConnected && candidate.parentNode === document.head
        && (candidate.id === SHEET_ID && candidate.disabled === false
          || candidate.id === '' && candidate.disabled === true)
        && candidate.getAttribute(SHEET_OWNER_ATTRIBUTE) === controllerOwner
        && candidate.textContent === candidateText;
      if (sheetStillAuthored) candidate.remove();
      relinquishURL();
      if (globalThis[CONTROLLER_SLOT] === controller) delete globalThis[CONTROLLER_SLOT];
    };
    const refreshTheme = geometry => {
      if (themeAlpha === null || retired || suspended || !sheetCommitted || slotValue(globalThis, CONTROLLER_SLOT) !== controller) return;
      if (!workspaceCurrent() || !geometry) { invalidateWorkspace(); return; }
      cancelMasks();
      const generation = maskGeneration;
      const ownsWash = html.style.getPropertyValue(TINT_PROPERTY) === tintGradient
        && html.style.getPropertyPriority(TINT_PROPERTY) === '';
      if (!ownsWash) { themeApplied = false; themePending = false; themeFailure = 'theme-owner-lost'; return; }
      tintGradient = legacyGradient;
      html.style.setProperty(TINT_PROPERTY, tintGradient);
      themeApplied = false; themePending = true; themeFailure = '';
      const key = geometryKey(geometry);
      let source;
      try { source = maskSource(geometry, maskColor()); }
      catch { themePending = false; themeFailure = 'theme-color-unsupported'; return; }
      decodeMask(source).then(decoded => {
        const fresh = readThemeGeometry();
        if (retired || suspended || generation !== maskGeneration || slotValue(globalThis, CONTROLLER_SLOT) !== controller
          || !workspaceCurrent() || !fresh || geometryKey(fresh) !== key) return;
        if (html.style.getPropertyValue(TINT_PROPERTY) !== tintGradient || html.style.getPropertyPriority(TINT_PROPERTY) !== '') {
          themePending = false; themeFailure = 'theme-owner-lost'; return;
        }
        tintGradient = 'url(' + JSON.stringify(decoded) + ')';
        html.style.setProperty(TINT_PROPERTY, tintGradient);
        themeApplied = true; themePending = false; themeFailure = '';
      }, failure => {
        if (retired || generation !== maskGeneration) return;
        themeApplied = false; themePending = false; themeFailure = failure?.code ?? 'theme-mask-decode-failed';
      });
    };
    geometryChanged = geometry => { themeGeometry = geometry; refreshTheme(geometry); };
    function updateSurface(value) {
      if (mainPaint || retired || suspended || (workspaceBound && !workspaceCurrent()) || slotValue(globalThis, CONTROLLER_SLOT) !== controller
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
        if (themeAlpha !== null) refreshTheme(readThemeGeometry());
      }
      return surfaceOwned;
    }
    controller = { owner: controllerOwner, version: BUILD, status: probe, dispose, restore: dispose, updateSurface };
    Object.defineProperty(controller, RELEASE_KEY, { value: handOverForReplacement });
    Object.defineProperty(controller, MARKER_KEY, { value: sceneURL });
    Object.defineProperty(controller, PENDING_KEY, { value: () => activationPhase === 'pending' || disableOperation!==null });
    Object.defineProperty(controller, SUSPEND_KEY, { value: value => {
      if (retired) return false;
      if (value === true) {
        if (!probe().applied) return false;
        const geometry=themeAlpha === null?null:readThemeGeometry();
        suspendedGeometryKey=geometry?geometryKey(geometry):null;
        suspended=true;cancelMasks();
      } else {
        suspended=false;
        if (themeAlpha !== null) {
          const geometry=readThemeGeometry();
          if (!geometry || geometryKey(geometry)!==suspendedGeometryKey) return false;
        }
      }
      return !retired && (!dshSurface || dshCurrent()) && (!workspaceBound || workspaceCurrent());
    } });
    Object.defineProperty(controller,DEACTIVATE_KEY,{value:(isDisableCurrent,disableSignal)=>{
      if (disableOperation || activationPhase!=='finalized' || retired || disableSignal?.aborted
        || slotValue(globalThis,CONTROLLER_SLOT)!==controller || !controller[SUSPEND_KEY](true)) throw deny('incumbent-unavailable');
      let phase='pending';
      const token={abandon(){if(phase==='pending')phase='abandoned';detach();}};
      const detach=()=>{
        if(disableOperation===token)disableOperation=null;
        try{disableSignal?.removeEventListener('abort',rollbackDisable);}catch{}
      };
      const current=()=>phase==='pending' && disableOperation===token && !disableSignal?.aborted
        && (typeof isDisableCurrent!=='function' || isDisableCurrent())
        && slotValue(globalThis,CONTROLLER_SLOT)===controller && !retired
        && (!dshSurface || dshCurrent()) && (!workspaceBound || workspaceCurrent()) && probe().applied===true;
      function rollbackDisable(){
        if(phase!=='pending')return phase==='rolled-back';
        phase='rolled-back';detach();
        if(slotValue(globalThis,CONTROLLER_SLOT)===controller){
          if(controller[SUSPEND_KEY](false) && probe().applied===true)return true;
          dispose();
        }else handOverForReplacement();
        return false;
      }
      disableOperation=token;
      disableSignal?.addEventListener('abort',rollbackDisable,{once:true});
      return {applied:true,disabled:true,imageDecoded:true,transaction:Object.freeze({current,rollback:rollbackDisable,
        finalize(){
          if(phase!=='pending')return phase==='finalized';
          if(!current()){rollbackDisable();return false;}
          phase='finalized';detach();dispose();
          return retired && !Object.hasOwn(globalThis,CONTROLLER_SLOT);
        },
      })};
    }});
    const detachAbort = () => {
      rollbackActivation = null;
      try { signal?.removeEventListener('abort', abortPending); } catch {}
    };
    const residentIntact = () => !!settledSheet && settledSheet.isConnected
      && settledSheet.parentNode === document.head && settledSheet.id === '' && settledSheet.disabled === true
      && settledSheet.getAttribute(SHEET_OWNER_ATTRIBUTE) === controllerOwner && settledSheet.textContent === residentSheetText;
    const currentActivation = () => activationPhase === 'pending' && !signal?.aborted
      && (typeof isCurrent !== 'function' || isCurrent())
      && slotValue(globalThis, CONTROLLER_SLOT) === controller && probe().applied === true;
    function rollback() {
      if (activationPhase !== 'pending') return activationPhase === 'rolled-back';
      activationPhase = 'rolled-back';
      detachAbort();
      const canRevive = slotValue(globalThis, CONTROLLER_SLOT) === controller && residentIntact()
        && (!dshSurface || dshCurrent());
      if (canRevive) restoreSnapshot = entrySnapshot;
      dispose();
      if (canRevive && !Object.hasOwn(globalThis, CONTROLLER_SLOT)) {
        settledSheet.id = residentSheetID;
        settledSheet.disabled = residentSheetEnabled;
        Object.defineProperty(globalThis, CONTROLLER_SLOT, livePlacement);
        let usable = false;
        try { usable = activeNow[SUSPEND_KEY](false) && activeNow.status().applied === true; } catch {}
        if (!usable && slotValue(globalThis, CONTROLLER_SLOT) === activeNow) attemptCleanup(() => activeNow.dispose());
        return usable;
      }
      if (activeNow) attemptCleanup(() => activeNow[RELEASE_KEY]());
      return !activeNow && !Object.hasOwn(globalThis, CONTROLLER_SLOT);
    }
    function finalize() {
      if (activationPhase !== 'pending') return activationPhase === 'finalized';
      if (!currentActivation()) { rollback(); return false; }
      activationPhase = 'finalized';
      detachAbort();
      if (activeNow) activeNow[RELEASE_KEY]();
      return probe().applied === true;
    }

    invalidateWorkspace = () => {
      if (retired || suspended || !sheetCommitted || slotValue(globalThis, CONTROLLER_SLOT) !== controller) return;
      dispose();
      if (typeof onWorkspaceInvalidated === 'function') attemptCleanup(() => onWorkspaceInvalidated({
        api: controller, documentToken: workspaceObservation?.documentToken, workspaceEpoch: workspaceObservation?.workspaceEpoch,
      }));
    };

    // ── Transaction: one synchronous handover ─────────────────────────────
    try {
      // Nothing can paint between suspending the resident sheet and validating
      // the candidate. The resident sheet stays attached so a failed candidate
      // can bring it back without re-adding an inline style element that a
      // stricter content-security policy might reject.
      if (transactional && activeNow && !activeNow[SUSPEND_KEY](true)) throw deny('incumbent-unavailable');
      if (settledSheet) { settledSheet.disabled = true; settledSheet.removeAttribute('id'); }
      // Activate the surfaces recorded under the frozen `zcodeAttributes` key.
      for (const [node, attributes] of markerTargets) for (const attribute of attributes) node.setAttribute(attribute, sceneURL);
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
          if (!transactional) stepAside.call(activeNow);
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
      if (transactional) {
        activationPhase = 'pending';
        rollbackActivation = rollback;
        return { ...outcome, transaction: Object.freeze({ current: currentActivation, finalize, rollback }) };
      }
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
      if (transactional && activeNow && slotValue(globalThis, CONTROLLER_SLOT) === activeNow) {
        attemptCleanup(() => activeNow[SUSPEND_KEY](false));
      }
      throw error;
    }
  } finally {
    if (!rollbackActivation) { try { signal?.removeEventListener('abort', abortPending); } catch {} }
    if (!sheetCommitted) {
      try { workspaceLease?.dispose(); } finally { relinquishURL(); }
    }
  }
}
