#!/bin/sh
set -eu

package=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH='' cd -- "$package/../.." && pwd)
if [ "$(uname -s)" != Darwin ]; then
    echo 'Build the Azhou Cursor Pendant on macOS.' >&2
    exit 1
fi

swift build --package-path "$package" --configuration release >&2
bin=$(swift build --package-path "$package" --configuration release --show-bin-path)
bundle_dir=$(mktemp -d "$package/.build/azhou-cursor-app.XXXXXX")
bundle="$bundle_dir/Azhou Cursor Pendant.app"
mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources"
cp "$package/Info.plist" "$bundle/Contents/Info.plist"
cp "$bin/AzhouCursorPendant" "$bundle/Contents/MacOS/AzhouCursorPendant"
cp "$repo/site/assets/cursors/grabbing@2x.png" "$bundle/Contents/Resources/Pendant.png"
cp "$repo/LICENSE" "$bundle/Contents/Resources/Code-LICENSE"
cp "$repo/assets/azhou/LICENSE" "$bundle/Contents/Resources/Artwork-LICENSE"
cp "$repo/assets/azhou/NOTICE.md" "$bundle/Contents/Resources/Artwork-NOTICE.md"
plutil -lint "$bundle/Contents/Info.plist" >&2
codesign --sign - --timestamp=none "$bundle"
codesign --verify --strict "$bundle"
printf '%s\n' "$bundle"
