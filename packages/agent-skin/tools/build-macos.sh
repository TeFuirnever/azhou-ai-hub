#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# != 0 ]]; then
  printf '%s\n' 'Usage: build-macos.sh' >&2;exit 2
fi
native_executable=AzhouCodexStartup
payload_name=azhou-payload
system_bin="${AZHOU_BUILD_SYSTEM_BIN:-/usr/bin}"
if [[ -n "${AZHOU_BUILD_SYSTEM_BIN:-}" && ! -d "$system_bin" ]]; then
  printf '%s\n' 'AZHOU_BUILD_SYSTEM_BIN must name an existing directory.' >&2
  exit 1
fi
theme_json="$(python3 tools/build-preflight.py)"
theme_icon_source="$(python3 tools/build-preflight.py --icon-path)"
theme_installation_name="$(THEME_JSON="$theme_json" python3 -c 'import json,os; print(json.loads(os.environ["THEME_JSON"])["identity"]["installationName"])')"
if [[ -z "${_AZHOU_BUILD_LOCK_FD:-}" ]]; then
  exec python3 tools/build-lock.py --run
fi
python3 tools/build-lock.py --verify "$_AZHOU_BUILD_LOCK_FD"
mkdir -p .build/module-cache
stage_root="$(mktemp -d "$PWD/.build/azhou-stage.XXXXXX")"
stage_identity=''
stage_receipt=''
build_succeeded=0
cleanup_stage() {
  local result=$?
  trap - EXIT
  if [[ "$build_succeeded" == 1 && -n "$stage_receipt" ]]; then
    if ! python3 tools/build-lock.py --verify "$_AZHOU_BUILD_LOCK_FD" || ! printf '%s' "$stage_receipt" | python3 tools/verify-artifacts.py --cleanup-stage "$stage_root"; then
      printf '暂存无法确认安全清理，请核对：%s\n' "$stage_root" >&2
      [[ "$result" != 0 ]] || result=1
    fi
  else
    printf '构建未完成，暂存保留待核对：%s\n' "$stage_root" >&2
  fi
  exit "$result"
}
trap cleanup_stage EXIT
stage_identity="$(python3 tools/verify-artifacts.py --stage-identity "$stage_root")"
bundle="$stage_root/$payload_name"
mkdir -p "$bundle/Contents/MacOS"
python3 tools/verify-artifacts.py --write-bundle-info "$bundle"
python3 tools/verify-artifacts.py --write-marker "$bundle"
"$system_bin/xcrun" --sdk macosx swiftc -O -target "$(uname -m)-apple-macos13.0" -module-cache-path .build/module-cache \
  Native/App.swift Native/Wallpaper.swift Native/SkinHostContract.swift Native/CodexSkinDriver.swift \
  -o "$bundle/Contents/MacOS/$native_executable" -framework AppKit -framework WebKit
"$system_bin/xcrun" --sdk macosx swiftc -O -target "$(uname -m)-apple-macos13.0" -module-cache-path .build/module-cache Native/InstallRegistry.swift Native/InstallRegistryCore.swift -o "$stage_root/azhou-install-registry" -framework AppKit -framework CoreServices
python3 tools/build-wallpaper.py --bundle "$bundle"
python3 tools/build-startup.py --bundle "$bundle"
icon_source="$theme_icon_source"
if [[ -n "${AZHOU_APPROVED_ICON_SHA256:-}" ]]; then
  icon_source="$stage_root/approved-icon.png"
fi
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
stage_receipt="$(printf '%s' "$stage_identity" | python3 tools/verify-artifacts.py --seal-stage "$stage_root")"
python3 tools/build-lock.py --verify "$_AZHOU_BUILD_LOCK_FD"
printf '%s' "$stage_receipt" | python3 tools/verify-artifacts.py --publish-build "$bundle"
build_succeeded=1
printf '%s\n' '构建完成：.build/azhou-payload（隐藏构建载荷，不是日常启动入口）。' "请运行 bash tools/install-macos.sh 安装到 ~/Applications/$theme_installation_name 并清理已核实的旧项目入口。"
