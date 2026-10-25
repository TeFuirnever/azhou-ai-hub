#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -d assets/private || ! -f assets/private/working.png || ! -f assets/private/scene.js ]]; then
  printf '%s\n' '缺少本地阿舟素材。请先运行 python3 tools/prepare-azhou-assets.py。' >&2
  exit 1
fi
python3 - <<'PRIVATE_CHECK'
import struct
import subprocess
from pathlib import Path
for name in ['.build', '.build/module-cache', '.build/azhou-payload', '.build/azhou-install-registry', 'dist', 'assets/private', 'assets/private/app-icon']:
    if Path(name).is_symlink():
        raise SystemExit('拒绝通过符号链接构建：' + name)
tracked = subprocess.check_output(['git', 'ls-files', '--', 'assets/private', 'dist', '.build', '.local']).decode().strip()
if tracked:
    raise SystemExit('私有素材、构建或验收产物进入 Git 跟踪范围，停止构建：\n' + tracked)
for name in ['assets/private/working.png', 'assets/private/working-v2.png', 'assets/private/wallpaper-scene-q-v3.png', 'assets/private/scene.js', 'assets/private/app-icon/source.png', 'dist/check.app', '.build/check.app', '.local/check']:
    if subprocess.run(['git', 'check-ignore', '-q', '--', name]).returncode:
        raise SystemExit('缺少私有产物 ignore 规则：' + name)
icon_source = Path('assets/private/app-icon/source.png')
if icon_source.is_symlink() or not icon_source.is_file():
    raise SystemExit('缺少实体私有图标源图 assets/private/app-icon/source.png。')
with icon_source.open('rb') as stream:
    header = stream.read(24)
if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
    raise SystemExit('图标源图必须是有效 PNG。')
icon_width, icon_height = struct.unpack('>II', header[16:24])
if icon_width != icon_height or icon_width < 1024:
    raise SystemExit(f'图标源图须为至少 1024×1024 的方形 PNG，实际 {icon_width}×{icon_height}。')
PRIVATE_CHECK
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
mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources/web/assets/private"
cat > "$bundle/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>AzhouCodexStartup</string>
<key>CFBundleIdentifier</key><string>local.azhou.codex-startup</string>
<key>CFBundleName</key><string>阿舟启动 Codex</string>
<key>CFBundleDisplayName</key><string>阿舟启动 Codex</string>
<key>CFBundleIconFile</key><string>AzhouAppIcon.icns</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.7.1</string>
<key>CFBundleVersion</key><string>8</string>
<key>LSMinimumSystemVersion</key><string>13.0</string>
<key>LSUIElement</key><true/>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
python3 tools/verify-artifacts.py --write-marker "$bundle"
/usr/bin/xcrun --sdk macosx swiftc -O -target "$(uname -m)-apple-macos13.0" -module-cache-path .build/module-cache \
  Native/App.swift Native/Wallpaper.swift -o "$bundle/Contents/MacOS/AzhouCodexStartup" -framework AppKit -framework WebKit
/usr/bin/xcrun --sdk macosx swiftc -O -target "$(uname -m)-apple-macos13.0" -module-cache-path .build/module-cache \
  Native/InstallRegistry.swift -o "$stage_root/azhou-install-registry" -framework AppKit -framework CoreServices
cp index.html style.css animation.js "$bundle/Contents/Resources/web/"
cp assets/private/working.png assets/private/scene.js "$bundle/Contents/Resources/web/assets/private/"
python3 tools/build-wallpaper.py --bundle "$bundle"
icon_source="$PWD/assets/private/app-icon/source.png"
iconset="$stage_root/AzhouAppIcon.iconset"
mkdir -p "$iconset"
for icon_size in 16 32 128 256 512; do
  /usr/bin/sips -z "$icon_size" "$icon_size" "$icon_source" \
    --out "$iconset/icon_${icon_size}x${icon_size}.png" >/dev/null
  icon_pixels=$((icon_size * 2))
  /usr/bin/sips -z "$icon_pixels" "$icon_pixels" "$icon_source" \
    --out "$iconset/icon_${icon_size}x${icon_size}@2x.png" >/dev/null
done
/usr/bin/iconutil -c icns "$iconset" -o "$bundle/Contents/Resources/AzhouAppIcon.icns"
python3 tools/verify-artifacts.py --check-inputs "$bundle"
plutil -lint "$bundle/Contents/Info.plist"
codesign --force --sign - "$bundle"
codesign --verify --strict "$bundle"
python3 tools/verify-artifacts.py --publish "$bundle"
mv -f "$stage_root/azhou-install-registry" .build/azhou-install-registry
printf '%s\n' '构建完成：.build/azhou-payload（隐藏构建载荷，不是日常启动入口）。' \
  '请运行 bash tools/install-macos.sh 安装到 ~/Applications/阿舟启动 Codex.app 并清理已核实的旧项目入口。'
