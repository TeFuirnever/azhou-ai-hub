#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
system_bin="${AZHOU_BUILD_SYSTEM_BIN:-/usr/bin}"
if [[ -n "${AZHOU_BUILD_SYSTEM_BIN:-}" && ! -d "$system_bin" ]]; then
  printf '%s\n' 'AZHOU_BUILD_SYSTEM_BIN must name an existing directory.' >&2
  exit 1
fi
if [[ ! -d assets/private || ! -f assets/private/working.png || ! -f assets/private/scene.js || ! -f assets/private/wallpaper-scene-q-v3.png ]]; then
  printf '%s\n' '缺少本地阿舟素材（working.png、scene.js、wallpaper-scene-q-v3.png）。请先准备本地私有素材。' >&2
  exit 1
fi
theme_json="$(python3 tools/build-preflight.py)"
theme_icon_input="$(THEME_JSON="$theme_json" python3 -c 'import json,os; print(json.loads(os.environ["THEME_JSON"])["identity"]["iconInput"])')"
theme_installation_name="$(THEME_JSON="$theme_json" python3 -c 'import json,os; print(json.loads(os.environ["THEME_JSON"])["identity"]["installationName"])')"
mkdir -p .build/module-cache
stage_root="$(mktemp -d "$PWD/.build/azhou-stage.XXXXXX")"
cleanup_stage() {
  if [[ -f "$stage_root/.preserve-original" ]]; then
    printf '原子回滚未完成，原包临时副本保留在：%s\n' "$stage_root" >&2
  else
    rm -rf -- "$stage_root"
  fi
}
trap cleanup_stage EXIT
bundle="$stage_root/azhou-payload"
mkdir -p "$bundle/Contents/MacOS"
python3 tools/verify-artifacts.py --write-bundle-info "$bundle"
python3 tools/verify-artifacts.py --write-marker "$bundle"
"$system_bin/xcrun" --sdk macosx swiftc -O -target "$(uname -m)-apple-macos13.0" -module-cache-path .build/module-cache \
  Native/App.swift Native/Wallpaper.swift Native/SkinHostContract.swift Native/CodexSkinDriver.swift \
  -o "$bundle/Contents/MacOS/AzhouCodexStartup" -framework AppKit -framework WebKit
"$system_bin/xcrun" --sdk macosx swiftc -O -target "$(uname -m)-apple-macos13.0" -module-cache-path .build/module-cache Native/InstallRegistry.swift Native/InstallRegistryCore.swift -o "$stage_root/azhou-install-registry" -framework AppKit -framework CoreServices
python3 tools/build-wallpaper.py --bundle "$bundle"
python3 tools/build-startup.py --bundle "$bundle"
icon_source="$PWD/$theme_icon_input"
iconset="$stage_root/AzhouAppIcon.iconset"
mkdir -p "$iconset"
for icon_size in 16 32 128 256 512; do
  "$system_bin/sips" -z "$icon_size" "$icon_size" "$icon_source" --out "$iconset/icon_${icon_size}x${icon_size}.png" >/dev/null
  icon_pixels=$((icon_size * 2))
  "$system_bin/sips" -z "$icon_pixels" "$icon_pixels" "$icon_source" --out "$iconset/icon_${icon_size}x${icon_size}@2x.png" >/dev/null
done
"$system_bin/iconutil" -c icns "$iconset" -o "$bundle/Contents/Resources/AzhouAppIcon.icns"
python3 tools/verify-artifacts.py --check-inputs "$bundle"
plutil -lint "$bundle/Contents/Info.plist"
codesign --force --sign - "$bundle"
codesign --verify --strict "$bundle"
python3 tools/verify-artifacts.py --publish "$bundle"
mv -f "$stage_root/azhou-install-registry" .build/azhou-install-registry
printf '%s\n' '构建完成：.build/azhou-payload（隐藏构建载荷，不是日常启动入口）。' "请运行 bash tools/install-macos.sh 安装到 ~/Applications/$theme_installation_name 并清理已核实的旧项目入口。"
