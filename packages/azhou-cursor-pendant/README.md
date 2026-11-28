# 阿舟跟随挂件 · Azhou Cursor Pendant

阿舟在 macOS 上跟着鼠标移动，切到其他应用也会继续跟随。你可以照常点击、选字和拖拽。打开后，从菜单栏的阿舟图标暂停跟随、恢复或退出。「减少动态效果」开启时，应用会暂停跟随。

默认值来自[官网试玩](../../docs/design/azhou-cursor-pendant.md)。80% 跟随对应 40 毫秒缓出，最大摆幅 20°，弹簧以 1.2 倍速度回稳。桌面版按屏幕位置采样鼠标，靠近边缘时把挂件放到另一侧。暂停后位置停止更新，挂件用 160 毫秒淡出。再次开启时接着当前透明度出现。

## 在这台 Mac 上体验

使用 macOS 和 Swift 6，打开仓库根目录。构建命令输出一个本地签名的 `.app` 路径。

```sh
(
  set -e
  app="$HOME/Applications/Azhou Cursor Pendant.app"
  if [ -e "$app" ] || [ -L "$app" ]; then
    if [ ! -L "$app" ] &&
      [ "$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$app/Contents/Info.plist" 2>/dev/null)" = 'lab.azhou.cursor-pendant' ] &&
      codesign --verify --strict "$app" 2>/dev/null; then
      printf '已有桌面挂件。升级请先退出挂件，再用新构建的应用替换旧版。\n'
      exit 0
    fi
    printf '安装位置已有其他文件，或原挂件不完整。请在个人「应用程序」中移走该项目，再重试。\n' >&2
    exit 1
  fi

  bundle=$(./packages/azhou-cursor-pendant/build-app.sh)
  mkdir -p "$HOME/Applications"
  staging=$(mktemp -d "$HOME/Applications/.azhou-pendant.XXXXXXXX")
  trap 'rm -rf "$staging"' EXIT
  trap 'exit 1' HUP INT TERM
  staged_app="$staging/Azhou Cursor Pendant.app"
  ditto "$bundle" "$staged_app"
  codesign --verify --strict "$staged_app"
  mv -n "$staged_app" "$HOME/Applications/"
  if [ -e "$staged_app" ]; then
    printf '安装位置刚被占用，请查看个人「应用程序」后重试。\n' >&2
    exit 1
  fi
  open "$app"
)
```

已有旧版时，先从菜单栏退出，再在 Finder 中用新构建的应用替换旧版。需要移除时，先退出挂件，再把个人「应用程序」中的该应用移到废纸篓。首次体验范围见[支持矩阵](../../docs/support-matrix.md#azhou-cursor-pendant)。

## 验证与来源

使用 Xcode 提供的 Swift 工具链运行 `swift test --package-path packages/azhou-cursor-pendant`，核对跟随、摆幅、回稳和屏幕边缘。安装后在 Finder 和另一款应用之间移动鼠标，检查跟随和点击，再从菜单栏暂停并恢复。

位置计算与弹簧由 `CursorPendantMotion` 持有。AppKit 控制器读取鼠标和屏幕坐标，用不接收鼠标事件的浮窗显示现有阿舟素材。挂件为当前用户运行，启动由用户控制。代码与素材来源见[来源记录](../../docs/integration-provenance.md#azhou-cursor-pendant)。

The standalone menu bar app follows the mouse across macOS apps. Build it from the repository with the command above, then open the resulting app. The Azhou icon in the menu bar can pause, resume, or quit the pendant.
