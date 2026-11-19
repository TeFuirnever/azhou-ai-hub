export function bootstrapStartup({
  installStartup,
  installAnimation,
  createLocalization,
  createImageSettings,
  createDreamThemeStyle,
  createWallpaperApplicator,
  installRenderer,
  version,
  css,
  assets,
  host,
  pageAdapter,
  playbackOwner = 'page',
}) {
  const wallpaperOptions = { version, css };
  const workspaceDeclared = pageAdapter && ['object', 'function'].includes(typeof pageAdapter) && 'workspaceContract' in pageAdapter;
  if (workspaceDeclared || pageAdapter?.wallpaper || typeof pageAdapter?.observeWorkspace === 'function') wallpaperOptions.pageAdapter = pageAdapter;
  const applyWallpaper = createWallpaperApplicator(installRenderer, wallpaperOptions, host);
  // Static properties below carry animation-owned factories only. The host page
  // strategy (pageAdapter) is passed explicitly to installStartup and must never
  // ride this static surface to bypass the verifier's entry predicate.
  Object.defineProperties(installAnimation, {
    assets: { value: assets },
    createLocalization: { value: createLocalization },
    createImageSettings: { value: createImageSettings },
    applyWallpaper: { value: applyWallpaper },
  });
  if (typeof createDreamThemeStyle === 'function') Object.defineProperty(installAnimation,'createDreamThemeStyle',{value:createDreamThemeStyle});
  if (playbackOwner === 'page') return installStartup(installAnimation, host, pageAdapter);
  return installStartup(installAnimation, host, pageAdapter, playbackOwner);
}
