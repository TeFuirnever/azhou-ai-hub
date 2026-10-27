# 0.6.0 阿舟壁纸接入与工作姿态升级

> 历史路径已按[迁移清单](../MIGRATION-INVENTORY.md)脱敏；变量仅定位原项目环境，原始证据仍留在本地，不证明本包当前已安装或生效。

> 后续实机回归（2026-10-24）：本记录保留 0.6.0 / build 5 当时的结果。正常启动后，用户截图暴露了底部整行装饰背景截断人物的问题；它未被本版模拟宿主和 applied 判定覆盖，不属于窄窗口输入框正常叠放的限制。修复后的当前版本为 0.6.1 / build 6，实机证据与测试范围见 [0.6.1验收](azhou-wallpaper-0.6.1-verification.md)。

日期：2026-10-24。项目：`$ORIGINAL_PROJECT_ROOT`。

**状态：实现与0.6.0/build5安装完成；新图的模拟界面验收、原生预览、已有Codex的交接与重复打开已完成。真实Codex页面内的壁纸成功接入仍待一次正常冷启动验证，不能标记为全部通过。** 当前主进程PID35120没有CDP监听，实时检查为 `needs-restart / applied:false`。没有替用户退出当前工作会话。

## 1. 已确认的原因与本次实现

0.5.2的正常构建只使用独立的 `Native/App.swift` / WKWebView 动画。旧 `Native/Extension.swift`、`extension/` 的CDP壁纸链路没有进入当前构建。因此，用户从阿舟入口启动后看不到Codex内部壁纸，不能归因于用户点错入口。

0.6.0保留7.8秒独立动画、最大化可用屏幕区域和280ms原生淡出，在同一可执行文件内增加有界的壁纸辅助模式。冷启动申请明确的正整数回环端口，通过原有NSWorkspace调用启动真实Codex；仍使用 `createsNewApplicationInstance=false`。已有进程只复用。无端口时明确报告未应用，不把动画完成当作壁纸成功，也不重新打开第二个官方实例。

辅助模式最多30秒，核对主PID、启动时间、真实路径、UID、主可执行文件、OpenAI签名和IPv4回环监听，再筛选 `app://-/index.html` 主页面。资源解码及计算样式确认后，还会独立执行一次实时状态查询。连接失败只影响壁纸，正常Codex交接继续。无后台常驻服务；调试端口仍随Codex主进程存续，辅助进程退出不会关闭端口。

壁纸只局部调整已核实的外壳背景，保留全局官方颜色变量。无聊天文本读取、存储修改、远程图片请求或持续动画循环。源码观察基于当前安装的26.1021.31345包；这不是对真实运行DOM的替代验证。

## 2. 新阿舟素材与视觉判断

用户要求提升女性Q版工作姿态的表现力。本次使用内置ImageGen，直接提供两张正式参考：女性v2身份图和Q版 `04-working.png`；没有仅沿着上一张衍生图继续推演，也没有更换成Bot形象。

| 项目 | 事实 |
| --- | --- |
| 新图 | `assets/private/working-v2.png`，1254×1254 RGBA PNG，1,808,354字节 |
| 新图SHA-256 | `50775f0351a741019308c1e56074baa0e39c0e4525b80839fbcbe6055b33b431` |
| 正式工作原图SHA-256 | `34dc9a8e9c06c226ec0cc80878548f118ff4a23b4a87d160674e66db4a905e58` |
| 女性v2身份参考SHA-256 | `967aeb5072d90e1997bc19ad8ecf1fbe5fbf14fed4508950b0267810712f2c9a` |
| 生成与来源记录 | `assets/private/wallpaper-provenance.json`；完整提示词 `.local/evidence/20261024-wallpaper/working-v2-prompt.txt` |
| 使用边界 | 本项目私有衍生，未覆写素材库、未正式入库、未公开发布 |

新图通过侧倾、张口笑、一手落键一手悬停、上扬的尾巴和前后错开的双脚增加动作表达。橙色长卷发、暖棕眼、双狐耳、单条白尖尾巴、角色左侧发饰、狐脸胸针、奶白橙色服装与书封尾巴徽记均保留。手势能够辨识，但没有把小尺寸截图当作逐指结构验收；腰包自然被遮挡，未标记为完整可见核验。

原图可见轮廓以alpha≥8计为 `(37,27,1233,1229)`，没有触碰画布边界。实际留白约2–3%，没有达到提示词中的8%；当前静态显示带额外窗口留边，未观察到主体裁断。根代理与独立素材审读代理实际查看了生成图以及Mac Chrome的深色、浅色和窄窗截图，没有把这项审读称为独立人工认证。

1512×889点、2×模拟界面中，人物显示460点宽，所需920px低于原图1254px。完整耳、尾、桌椅及靴子可见，表情和不同手势在显示尺寸下仍可辨，深浅底均未见明显矩形底或宽色边。正文、代码块与输入区保持清楚。**840×900点窄窗中，输入框会覆盖手部、电脑和下半身；这是背景处于内容下层的限制，不能声称所有窗口尺寸都完整展示人物。**

启动动画继续使用原 `working.png / scene.js`，其局部网格已按旧图位置校准。本次没有直接把新图塞入旧网格，因此也没有声称新工作图已成为动态角色素材。

## 3. 修改文件

| 文件 | 作用 |
| --- | --- |
| `Native/App.swift` | 冷启动参数、同一可执行文件辅助模式分流、warm实例复用、真实壁纸状态提示与收尾 |
| `Native/Wallpaper.swift` | 目标身份/端口核验、Foundation WebSocket CDP、有界连接、应用/状态/恢复与脱敏记录 |
| `Native/WallpaperValidationTests.swift` | 42项不接触Codex的纯校验边界检查 |
| `wallpaper/renderer.js` | 解码、局部安装、计算样式复查、重复应用、失败更新回滚与恢复 |
| `wallpaper/wallpaper.css` | 静态阿舟、暖橙/淡紫背景及局部外壳透明规则 |
| `wallpaper/preview.html` | 明确标识的模拟宿主源码预览 |
| `tools/build-wallpaper.py` | 将新图、样式与代码打包到私有应用资源，并记录摘要 |
| `tools/build-macos.sh` | 编译新原生文件、打包壁纸；通过xcrun明确选择macOS SDK |
| `tools/verify-artifacts.py` | 验证当前包必含壁纸脚本、素材清单及对应构建输入摘要 |
| `tools/test-wallpaper.mjs` | 独立临时Chrome配置的模拟DOM、CSP、生命周期与截图检查 |
| `README.md`、`AGENTS.md`、`extension/README.md`、`docs/references.md` | 当前行为、素材范围、操作步骤与旧链路边界同步 |
| `docs/app-icon-0.5.2-verification.md` | 为历史验收增加版本范围指针，不改写历史结果 |

私有新图、来源记录和播放证据均在Git忽略范围内；没有执行提交或推送。

## 4. 实际工程验收

| 检查 | 实际结果及范围 |
| --- | --- |
| 原生编译与纯校验 | Mac上编译成功；42项纯验证通过。修复了Swift可抛出短路条件的编译错误；显式SDK解决直接调用CLT编译器无法找到标准库的问题。 |
| 浏览器模拟 | Node v24.22.1、Chrome156.0.8078.47、独立临时配置；8组检查通过，临时浏览器和服务器清理完成。不是正式Codex接入。 |
| 失败及恢复 | 坏图、坏CSS、CSP拒绝路径准确失败；失败更新保留旧有效实例；重复应用只有一份样式，恢复后Blob/resize监听/样式均为0。 |
| 原生预览 | 从最终安装包运行 `--preview`，完整7.8秒并退出；窗口1512×889点、2×，三项文案准确，前端无错误。 |
| warm正常启动 | 同一官方PID35120被复用；仅一次壁纸helper，准确返回needs-restart；动画后激活同一PID，约280ms淡出，启动器退出。 |
| 播放期间再次打开 | 出现一次 `reopen-existing-player`，未创建第二个启动器，也未再次打开Codex或重复helper。 |
| 运行残留 | 核对本轮两个正常启动、预览及其helper的已知PID，均已退出；官方Codex仍运行。 |
| 正常安装与重复安装 | 两次 `bash tools/install-macos.sh` 均成功；第二次status=current、内容指纹相同。安装应用1个、dist应用0个、项目登记路径1个。 |
| 安装隔离回归 | 当前源码的21项测试通过；其codesign、登记、复制和原子系统调用为模拟，不能替代以上实机安装。 |
| 实时只读状态 | 安装包 `--wallpaper-status` 返回needs-restart、applied=false、正确目标路径/PID；查询前后壁纸日志SHA及mtime不变。 |
| 素材保护 | 两张正式参考原文件SHA与读取时一致；受保护路径无Git跟踪项，暂存区为空。 |
| 官方包 | 当前路径 `/Applications/ChatGPT.app`，ID `com.openai.codex`，Team ID `2DC432GLL2`；`codesign --verify --strict` 成功。 |
| 真实冷启动壁纸 | **未验证。** 现有进程没有CDP端口，且用户要求不打断当前工作；未替用户退出、未强制多开、未绕过辅助功能权限。 |

安装应用：`$HOME/Applications/阿舟启动 Codex.app`。身份 `local.azhou.codex-startup / AzhouCodexStartup`，0.6.0/build5，LSUIElement=true，图标继续为AzhouAppIcon.icns。

最终应用树摘要：`e3d8c324dcc67d44f07a07c23e70c81aa8f1bf4a324e3b90d4b9abca03066ea0`。
构建输入摘要：`233da02d61d593644dbc50922b6784eda40f36cb31a427f6fb225663b29f1302`。

最初记录与当前官方Info.plist/app.asar的SHA不同，见 `official-integrity.json`。当前读取版本为26.1021.31345，工作期间曾观察到官方PID变化；没有追溯变化来源，也没有把“官方包前后哈希相等”标记为通过。本轮对官方包只做读取和正常应用激活，所有实现写入位于本项目或既定阿舟安装入口。

## 5. 播放与时序证据

所有本轮证据位于 `.local/evidence/20261024-wallpaper/`，不得公开提交或发布。

- **最终完整录屏：** `installed-warm-clean.mov`，3024×1964显示器原始录屏，12.013秒、659帧；含启动前、完整动画和回到真实Codex的过程。当前warm会话无壁纸，此录像不能用作壁纸已生效证据。
- **便于播放的副本：** `installed-warm-clean.mp4`，1512px宽。原始MOV保留。
- **从录屏取出的关键帧：** `recording-frames/01-entry.png`、`02-working.png`、`03-reading.png`、`04-settle.png`、`05-handoff.png`。截图只证明对应时刻。
- **真实运行日志：** `installed-warm-clean.jsonl`、`installed-warm-reopen.jsonl`、`preview-clean.jsonl`。
- **模拟壁纸画面与报告：** `fixture/01-dark-1512.png`、`02-light-1512.png`、`03-dark-840.png`、`fixture/report.json`。
- **构建与安装：** `build-1.log`、`install-1.log`、`install-2.log`、`installed-entry.txt`、`final-checks.json`。

首轮录制同时调用6次WKWebView.takeSnapshot，前端记录出现12个大于50ms的间隔，最大149ms，位置紧随抓图任务。为排除验收工具干扰，随后停止播放中抓图，改为外部完整录屏后取帧：原生预览最大rAF间隔22ms；正常warm录屏最大25ms，两者大于50ms的间隔均为0。该对照支持抓图开销造成首轮停顿的判断。没有据此宣称GPU或合成器全程60fps，也没有将关键帧审读称为独立人工完整播放评审。

最终warm日志：playback-start约0.365秒，animation-complete约8.161秒，淡出约8.171–8.452秒，退出约8.466秒。角色与三项文案的前端边界均在1512×889视口内。

## 6. 可复现命令与恢复边界

```sh
cd "$ORIGINAL_PROJECT_ROOT"
bash tools/install-macos.sh
bash tools/install-macos.sh --check
"$HOME/Applications/阿舟启动 Codex.app/Contents/MacOS/AzhouCodexStartup" --preview
"$HOME/Applications/阿舟启动 Codex.app/Contents/MacOS/AzhouCodexStartup" --wallpaper-status
```

模拟壁纸复核使用本机已经验证存在的Node：

```sh
"/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node" \
  tools/test-wallpaper.mjs --image working-v2.png \
  --out .local/evidence/wallpaper-fixture-next
```

源码交互预览：在项目根运行 `python3 -m http.server 8765 --bind 127.0.0.1`，再打开 `http://127.0.0.1:8765/wallpaper/preview.html?image=working-v2.png`；该页面明确标为模拟宿主。

实际壁纸最后验收需要先保存当前工作，正常完整退出Codex，再从唯一阿舟入口打开。macOS只把配置的命令行参数交给新启动的实例；重新点击入口无法给现存进程补上启动参数。之后需要实时确认applied=true、实际看主界面、记录完整交接，再测试已有CDP实例的重复应用。本记录目前没有提前填写这些结果。

移除本次页面外观可使用已实现的helper restore，需先通过状态命令取得并核对当前PID，再提供 `--action restore --target-pid 当前PID --target-bundle /Applications/ChatGPT.app`；它只恢复页面样式，不关闭调试端口。完整退出Codex后直接打开官方应用，也不会保留这次运行时注入的壁纸或启动调试端口。下次由阿舟入口冷启动则重新应用。

未重建旧.app或ZIP应用备份。旧源码的局部对照保存在本轮私有 `source-before-wallpaper/`，用于追溯与恢复实现，不是并列日常启动入口。不要用历史已删除应用的恢复命令。

## 7. 官方依据

- [Apple NSWorkspace.OpenConfiguration](https://developer.apple.com/documentation/appkit/nsworkspace/openconfiguration)：`arguments`用于新实例启动，配置控制激活、替代与打开行为。
- [Apple createsNewApplicationInstance](https://developer.apple.com/documentation/appkit/nsworkspace/openconfiguration/createsnewapplicationinstance)：false复用已有应用，true会要求另起实例。
- [Electron支持的命令行开关](https://www.electronjs.org/docs/latest/api/command-line-switches#--remote-debugging-portport)：在指定端口启用调试；本项目不把启动完成回调当作renderer就绪。
- [Chromium runtime_features.cc](https://chromium.googlesource.com/chromium/src/+/HEAD/content/child/runtime_features.cc)：port=0会开启AutomationControlled；正式宿主因此使用明确正整数端口。此为平台源码依据，没有声称当前宿主已经出现某种自动化UI异常。
- [Chrome DevTools Protocol Runtime](https://chromedevtools.github.io/devtools-protocol/tot/Runtime/)：使用Runtime.evaluate的awaitPromise与returnByValue获取脚本实际结果；执行成功仍不能替代截图和真实视觉确认。
