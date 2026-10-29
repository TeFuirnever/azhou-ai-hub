# Agent Skin 测试与功能验收

用户要求覆盖整个 `packages/agent-skin/` 的生产代码，UT 行覆盖率至少 95%。这是一项失败即阻断的验收条件；配置了门禁、测试数量增加或功能截图通过，都不表示已经达到覆盖率。

## UT 范围与判定

`tools/test-unit-coverage.py` 自动发现 JavaScript、Python、Swift、Bash 和 `.command` 生产源码。生产构建与安装工具、Pet 工具、原生适配器和新加入的源码都在统计范围内。测试程序、生成产物、私有素材、文档和测试夹具不进入生产代码分母。`wallpaper/preview.html` 是带自检按钮的合成宿主测试夹具；生产预览使用 `index.html` 加载已计入的独立 JS。CSS、HTML 标记和 JSON 配置没有可执行行覆盖率，分别通过浏览器、构建和功能用例验收。

每种语言及整个包都须达到 **95% 行覆盖率**。判定使用原始计数，不以四舍五入后的百分比放行；分支和函数统计可用于诊断，但不代替行覆盖率。缺失报告、漏算生产文件、工具失败或 UT 失败均阻断。Node LCOV、Coverage.py、LLVM 和 Bash 覆盖率保留各自原始结果；不把浏览器 E2E、实机启动或人工审阅混入 UT。

Swift 生成的 8 段 CDP JavaScript 另计为 `generated/Native-Wallpaper.<expression>.js`，由当前源码编译出的 UT 程序导出原始字符串，再由 Node VM 执行并测量。只执行 Swift 的字符串赋值不能算这些脚本的 UT。生成器、表达式和独立 JS 模块均不得漏算；缺少任何一段的执行报告会阻断。

启动载荷中的工厂接线和只读属性安装使用规范模块 `extension/bootstrap.mjs`，由生成器原样嵌入，并独立执行 UT。素材数据与模块调用包装不重复统计；生成器内部不得隐藏未经测量的手写函数。

被复制到临时夹具的 Python 源码，只有在执行前确认与规范源码字节相同后才合并覆盖率。发生源码修改的夹具不能冒充规范源码。Bash 通过实际源码和外部工具边界运行；测试不能改写生产命令路径后把副本算作规范源码。

在包目录运行：

```sh
python3 -m pip install coverage==7.16.2 Pillow==12.3.0
python3 -B tools/test-setup-unit-tools.py
python3 -B tools/test-coverage-policy.py
python3 -B tools/test-functional-verdict.py
python3 -B tools/test-unit-coverage.py
```

需要 macOS 的 AppKit、WebKit、Xcode 命令行工具及 Node 24；Pet UT 还需 `Pillow==12.3.0`。工具准备脚本将固定版本 GNU Bash 5.2.37 和 Bashcov 1.7.0 放入忽略的 `.build/`，不会替换系统 Bash/Ruby 或安装 Homebrew 包。覆盖率工具仅用于开发测试，不是用户应用依赖。`--language javascript|python|swift|shell` 用于单组开发复验，只证明该组，不能用它宣称整个包通过。总报告在 `.build/unit-coverage/report.json`；报告为失败时不得写“UT 95% 已完成”。

## 功能用例

每项都规定触发、期望和验收入口。模拟或单元测试通过不自动关闭实机验收。

| ID | 触发与操作 | 期望 | 自动看护 / 实机验收 |
|---|---|---|---|
| FT-LOCALE | 官方页面英文、浏览器语言中文；切换官方页面语言 | 页面语言优先；文案、bot、设置和动画同步，不新增语言偏好 | `localization.test.mjs`、`startup.test.mjs`、生成载荷浏览器测试；实机观察官方界面 |
| FT-FINDER | 按当前 macOS 语言查看已安装应用；检查中英资源 | 英文显示 `Azhou AI Lab`，中文显示主题指定名称；真实安装文件名不充当本地化结论 | `test-startup-build.py`、`test-installed-acceptance.py` 的 Finder API；真实 Finder 窗口检查 |
| FT-DOCK | 将旧版固定到 Dock，升级后再查看标签和启动目标 | 标签符合 macOS 语言，只启动唯一新入口；旧固定项或缓存不能算新版本已通过 | 安装归属 UT；Dock 实际标签与目标需现场验收。没有入口时保留 pending，不能以空列表通过 |
| FT-COLD | 用户完整退出官方宿主，再从阿舟入口启动 | 恰好一次冷启动、控制器就绪、动画结束和壁纸生效；没有第二个宿主 | 原生协议 UT、生成载荷测试；`test-installed-acceptance.py --cold-start` 加视觉审阅 |
| FT-HOT | 官方宿主保持运行，再打开阿舟入口 | 激活同一 PID；不重播、不覆盖控制器、不退出宿主 | 原生事件 UT；实机对照前后 PID、事件和页面 |
| FT-LATE-SHELL | 页面外壳晚于 12 秒动画出现 | 动画准时结束，壁纸继续等待并生效，不重播动画 | `startup.test.mjs`、`test-startup-browser.mjs` 的生成载荷延迟场景 |
| FT-SHELL-TIMEOUT | 60 秒内始终没有支持的页面外壳 | 返回 `shell-timeout`；临时观察器清理；不伪造成功 | 生成载荷完整超时测试 |
| FT-CANCEL | 等待或解码时跳过、重新开始、禁用或释放 | 旧请求失效；迟到回调不能重装背景或复活控制器 | 控制器与渲染器 UT、浏览器取消/乱序测试 |
| FT-RETRY | 壁纸失败后重试；并发重试；健康状态重复调用 | 最多一个尝试、10 秒上限；保留已过滤的先前原因；不重播动画；健康状态只复查 | 控制器及编译后的 helper 表达式测试 |
| FT-SURFACES | 深浅色、窄窗、CSP 拒绝图片或样式、未知遮罩 | 真实图片解码；保留输入框、菜单和代码块；失败可见；未知层不被擅自清除 | 渲染器 UT、CSP/布局浏览器测试；实机检查裁切、人物及文字可读性 |
| FT-SETTINGS | 保存/取消/恢复草稿、并发冲突、配额或超时、强度为零 | 保存成功才应用；取消保留旧值；失败可恢复；零强度关闭背景 | `image-settings.test.mjs`、存储浏览器测试、保存与草稿预览场景 |
| FT-SIDEBAR | Home 导航可见；更新下载按钮或头像出现、侧栏滚动、窄窗或导航重建 | 存在唯一可见的 Your dot 时，阿舟入口在 Home 导航正常流中紧随其后、位于 Pinned 前，避开宿主控件并保持可点击；无法确定唯一目标时使用不遮挡控件的备用位置 | `startup.test.mjs`、`test-startup-browser.mjs` 的几何、点击、窄栏、重建及生成载荷场景；同一运行版本的真实宿主位置需现场验收 |
| FT-INSTALL | 旧名称升级、跨来源接管、失败中断后重试、未知同名应用 | 先验证新入口；保留归属与签名边界；唯一实体和登记；未知对象不被删除 | `test-install-macos.py`、构建 UT、实际 `install-macos.py --check` |
| FT-ASSETS | 缺图、非法路径、符号链接、错误尺寸、旧构建输入 | 构建拒绝并保留原有效入口；私有素材不进入 Git | preflight、构建器、校验器、资源处理及 shell UT |

Finder/Dock 使用 **macOS 语言**；注入的动画和外观使用 **官方宿主页面语言**。这两条合同分别验收，不能用应用内按钮为英文推断 Finder/Dock 已通过。

## 实机执行与保留项

```sh
# 只读检查当前安装、Finder API、Dock 条目和壁纸；不启动或退出官方宿主。
python3 -B tools/test-installed-acceptance.py --out .local/functional-acceptance

# 先由用户保存工作并完整退出官方宿主，再执行。
# 脚本发现宿主仍在运行就保留 pending，不自动退出或重启它。
python3 -B tools/test-installed-acceptance.py --cold-start --out .local/cold-acceptance
```

实机报告明确标记 `unitCoverageInput: false`。Dock 没有固定入口、冷启动未执行或尚缺视觉审阅都不能输出全通过。报告包含当前检查结果和日志路径；历史截图或旧 build 记录不能替代当前安装的结果。

宿主布局回归以脱敏的实际结构为依据：核对目标控件、影响可见性和尺寸的祖先样式、滚动容器与重建行为，不复制聊天内容。合成夹具需断言目标顺序和实际几何；选择器命中或备用入口可见不能代替目标位置通过。交付分别记录测试载荷版本、安装版本和页面实际运行版本；实机结果仅在同版页面检查后判定，无法核实时保持待验收。

`CI / Agent Skin full production UT coverage` 运行完整 UT 门禁，并进入聚合 Required 判定；现有 macOS 作业继续运行生成载荷浏览器功能回归。仓库通用 `python3 scripts/verify.py` 仍执行其原有完整检查，不能替代本页的包级覆盖率命令。提交/推送状态与远端 CI 结果另行报告，不因本地通过而推断远端已通过。
