# 0.5.2 应用图标验收

> 历史范围：本文记录0.5.2/build4的图标与安装验收。当前版本与壁纸行为见 [项目 README](../README.md) 和 [0.6.0壁纸记录](azhou-wallpaper-0.6.0-verification.md)。

日期：2026-10-24。当前应用版本0.5.2/build4，唯一入口：
`/Users/guanxueliang/Applications/阿舟启动 Codex.app`。

## 指定源图与实现

用户指定原图为 `/Users/guanxueliang/Desktop/Tilted fox-robot face avatar.png`。实际打开确认1254×1254、RGB PNG、不透明深色背景，保留原有倾斜近景构图。原图SHA256：

`fd0d4bfd7b394f45c8724436e765be5ecfa9f675a2a9214619a65e32eebbf21d`

逐字节私有副本在 `assets/private/app-icon/source.png`，来源记录在同目录 `provenance.json`。源图在桌面的SHA及修改时间均未变。后续构建读取项目私有副本，不依赖桌面文件继续存在。

`tools/build-macos.sh` 使用现有macOS `sips` 等比例降采样，生成16、32、128、256、512点的1×/2×共10份PNG，再用 `iconutil` 打包。没有重绘、改色或额外裁切。图标写入 `Contents/Resources/AzhouAppIcon.icns`，由 `CFBundleIconFile` 声明，在签名前进入应用包。系统自身的圆角和图标外观由macOS显示处理。

`tools/verify-artifacts.py` 同步版本，核对图标键、资源文件及ICNS容器；兼容升级旧0.5.1无图标包。图标源被纳入现有构建输入摘要；网页资源仅复制原有working.png与scene.js，避免把图标源重复打入网页目录。

## 实际检查

证据目录：`.local/evidence/20261024-icon/`。

| 检查 | 结果与证据 |
| --- | --- |
| 正常构建安装 | 成功升级0.5.2/build4，签名与安装指纹校验通过；见 `install.log`。 |
| 再次正常构建安装 | 图标仍保留、结果current；见 `repeat-install.log`。 |
| ICNS可解码 | 从实际安装包解出10份PNG，尺寸与文件名一致，最大1024×1024；见 `decoded.iconset/`、`verification.json`。 |
| 系统实际图标 | 使用 `NSWorkspace.icon(forFile:)` 读取实际安装路径，保存32/64/128/512像素图；已查看32及512像素结果，确认新头像显示。 |
| Finder显示 | 显式打开用户Applications目录，实际截图中“阿舟启动 Codex”左侧显示新头像；见 `finder-installed-icon.png`。 |
| 唯一性 | 安装目录项目应用1个、dist应用0个、系统登记1条，Spotlight只返回规范路径；见 `verification.json`。 |
| 实际启动 | 新应用完整运行一次，一次播放、完成、交接和退出；复用真实主程序，没有target-open-request，failure为0；见 `launch.jsonl`、`launch-result.json`。 |
| 原图及动画 | 桌面原图SHA/mtime未变；HTML、CSS、JS、女性Q版工作图及scene.js的SHA均与本轮修改前一致，安装版也一致。 |
| 私有范围 | 图标源、ICNS与截图均在忽略范围内；私有跟踪文件及暂存列表为空，没有commit或push。 |

安装包ICNS的SHA256为：
`16e3f2f5e3c85792d70bd850aceba4e89e7a05a6d8b971ffcaa341245c1c7ec7`。

未改动动画设计、主程序身份或安装路径。没有新增独立审美评审；以上是源图检查、系统读取、Finder截图及真实启动验证。最初默认第三方文件查看器没有定位到目标应用，其无关诊断截图已删除，不作为图标证据。

## 后续使用

正常更新仍使用：

```sh
bash tools/install-macos.sh
bash tools/install-macos.sh --check
```

首次在缺少私有副本的本机副本中准备图标，可将已获授权的这张PNG复制到 `assets/private/app-icon/source.png`。不要将私有源图或其衍生产物加入公开仓库。

## 官方依据

- [Apple CFBundleIconFile](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html#//apple_ref/doc/uid/TP40009249-SW10)：图标文件位于应用主Resources目录，并由Info.plist声明。
- [Apple Icon Set Type](https://developer.apple.com/library/archive/documentation/Xcode/Reference/xcode_ref-Asset_Catalog_Format/IconSetType.html)：标准iconset文件名与1×/2×尺寸。
- [Apple高分辨率图标打包](https://developer.apple.com/library/archive/documentation/GraphicsAnimation/Conceptual/HighResolutionOSX/Optimizing/Optimizing.html)：用iconutil生成可部署ICNS。
