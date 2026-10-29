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
}) {
  const applyWallpaper = createWallpaperApplicator(installRenderer, { version, css }, host);
  Object.defineProperties(installAnimation, {
    assets: { value: assets },
    createLocalization: { value: createLocalization },
    createImageSettings: { value: createImageSettings },
    applyWallpaper: { value: applyWallpaper },
  });
  return installStartup(installAnimation, host);
}
