# 启动行为契约草案

本文是待实现的类型与状态约束。符号为设计名，不声称现有 API 已提供。

## 调用者视角

```text
trusted entry -> existing CodexSkinDriver.launch(request)
  hot: validate existing host -> activate -> activatedExisting
  cold: admit owner -> show native cover -> open/attach host
        -> read validated snapshot -> play natively + prepare workspace
        -> reconcile independent outcomes -> reveal/release once

verified Codex bootstrap(presentationOwner = native)
  installs settings and wallpaper; never auto-starts page player

DSH early gate -> client adopts same gate identity
  -> existing DSH settings -> page animation + workspace preparation
  -> reveal/release once
```

不要新增用户可随意切换的 presentationOwner 配置。该值由当前宿主的可信装配决定，保持正式自动播放只有一个所有者。

## 数据形状

```text
LaunchBinding = { runNonce, hostIdentity, totalDeadline }
PageBinding = { processStartIdentity, targetID, connectionGeneration }
SettingsSnapshot = { snapshotID, schema, digest, validatedRecord,
                     resolvedAppearance, resolvedLocale, sourcePageBinding }

Presentation = covering | playing(snapshotID) |
               ended(completed | skipped | disabled | failed) | released
Workspace = pending | observed(pageBinding, supportedShellEvidence,
                              settingsControllerIdentity, wallpaperDisposition) |
            failed(reason)
WallpaperDisposition = disabled | applied(proof) | degraded(reason)
Terminal = activatedExisting | revealed(receipts) |
           releasedWithoutReady(reason, observedFacts) | refused(reason)
```

每次运行只有一个协调所有者。原生窗口、页面句柄和动画回执均绑定 runNonce。Workspace可以随页面代际变化，Presentation只能播放一次。过期事件忽略且释放其资源，不能回写当前状态。

## 转换与不变量

| 事件 | 状态动作 | 可见动作 |
| --- | --- | --- |
| admitted cold | 沿用 request.startedAt 起算的预算，创建cover | 确认自有首帧后才打开宿主 |
| validated snapshot | covering进入playing；disabled直接ended | 使用同一份快照启动12秒动画；disabled立即解除自有遮挡 |
| native complete | playing进入ended(completed) | 当前工作区已observed则交接，否则有界保留结束画面 |
| workspace observed | 更新当前代际工作区证据 | Presentation已自然结束时最终复核并显露 |
| page replaced | 废弃旧workspace和未完成快照 | 保留正在播放的已接受快照，不重播；后继页重新准备 |
| skip/close | 进入ended(skipped)并终止自有呈现 | 立即释放遮挡；未ready如实记录，不在skip之后继续困住用户 |
| deadline/failure | 进入失败终态并幂等清理 | 放开宿主或显示明确错误，不留下永久黑幕 |
| late event | 不改变终态 | 不重建窗口、不重新播放、不重复激活 |

正常 revealed 需要当前代际的工作区证据和自然结束的播放回执。跳过、disabled、错误释放不需要伪造工作区ready。若它们发生时工作区已被证明，可附带实际证据，但结果仍保留原触发原因。

工作区证据只证明当前支持的外壳、必要控制器与壁纸结果，不证明模型联网或对话加载完成。壁纸关闭是正常分支。壁纸失败是明确降级，不让用户无限等待，也不宣称完整外观成功。

## 期限

当前源码基线的预检上限是启动后15秒，总期限60秒，attach期限为进入attach后45秒与总期限的较早值。保留这些上限与单调时钟语义。预算从 request.startedAt 开始，预检、身份准入、首帧等待、快照读取、渲染准备和交接均消耗同一总预算；进入冷启分支时不得重新创建60秒期限。

动画保持 animation.js 的12000ms。动画开始前确认剩余时间足够播放与完成观察，否则不启动必然中断的一段动画。原页面25秒watchdog属于旧page播放器，不能被误当成原生播放证据。开发时把适用的原生完成watchdog绑定到真实播放器生命周期，并受总期限约束；不得复制多个可漂移常量。

超时不能因换页、读设置、重连、跳过或接管而补充预算。最终画面等待是否被原包允许仍须核对。即使允许，也只能持续至总期限。

## 设置读与页面换代

page export先将有效记录固定为不可变对象，再返回描述和有界块。禁止分块过程中每次重读数据库。内容摘要证明完整性，不证明比当前数据库更新。快照一旦被播放器接受，整次播放保持它；后续保存按下一次启动语义生效。

快照接受前的页面断开，清除部分数据和export句柄。只有既有旧target退休证明和新页身份成立后才能重试。接受后的页面替换不使已验证数据自动失效，但当前workspace证据必须失效。未保存草稿、用户聊天内容、凭据和任意本地路径均不属于导出字段。

## DSH 交接

早期 gate 与 client 共用一个本次文档的owner token。client 先完成自身可见呈现，再确认接管，最后移除早期gate。确认失败保持原gate直到独立watchdog释放。任何修改前记录原属性并按所有权恢复，避免覆盖宿主后续更新。

早期入口必须明确配置关闭、插件卸载、CSP拒绝、JS未加载和异常的释放路径。仅有客户端 finally 不足以保护客户端根本没执行的场景。服务端插件启用、浏览器设置中的动画关闭和一次文档内自动播放资格是不同事实，不能混成一个布尔值。
