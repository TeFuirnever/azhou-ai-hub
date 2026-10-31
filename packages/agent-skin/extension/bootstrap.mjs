export function bootstrapStartup({
  installStartup,
  installAnimation,
  createLocalization,
  createImageSettings,
  createWallpaperApplicator,
  installRenderer,
  version,
  css,
  assets,
  host,
  pageAdapter,
}) {
  const applyWallpaper = createWallpaperApplicator(installRenderer, { version, css }, host);
  // Static properties below carry animation-owned factories only. The host page
  // strategy (pageAdapter) is passed explicitly to installStartup and must never
  // ride this static surface to bypass the verifier's entry predicate.
  Object.defineProperties(installAnimation, {
    assets: { value: assets },
    createLocalization: { value: createLocalization },
    createImageSettings: { value: createImageSettings },
    applyWallpaper: { value: applyWallpaper },
  });
  return installStartup(installAnimation, host, pageAdapter);
}
