import AppKit
import WebKit
import Darwin

// Local, short-lived player. Wallpaper is a separate bounded runtime-only task.
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    private let launcherID = "local.azhou.codex-startup", targetID = "com.openai.codex"
    private let args = CommandLine.arguments
    private let epoch = ProcessInfo.processInfo.systemUptime
    private var window: NSWindow!, webView: WKWebView!
    private var webRoot: URL?, targetURL: URL?, target: NSRunningApplication?
    private var logFile: FileHandle?, watchdog: Timer?
    private var lockFD: Int32 = -1
    private var ready = false, opening = false, requested = false, done = false
    private var terminating = false, failed = false, activated = false, promoted = false
    private var wallpaperProcess: Process?, wallpaperResult: [String: Any]?
    private var wallpaperStarted = false, wallpaperMayFinish = false
    private var snapshots: [DispatchWorkItem] = []
    private var preview: Bool { !promoted && (args.contains("--preview") || args.contains("--smoke-test")) }
    private func option(_ key: String) -> String? {
        guard let i = args.firstIndex(of: key), i + 1 < args.count else { return nil }
        return args[i + 1]
    }
    private func real(_ url: URL) -> URL { url.resolvingSymlinksInPath().standardizedFileURL }
    private func rectInfo(_ rect: NSRect) -> [String: Double] {
        ["x": Double(rect.origin.x), "y": Double(rect.origin.y),
         "width": Double(rect.width), "height": Double(rect.height)]
    }
    private func windowGeometry() -> [String: Any] {
        guard let window else { return [:] }
        let screen = window.screen ?? NSScreen.main
        return ["frame": rectInfo(window.frame),
                "visibleFrame": screen.map { rectInfo($0.visibleFrame) } ?? [:],
                "contentBounds": rectInfo(window.contentView?.bounds ?? .zero),
                "screen": screen?.localizedName ?? "", "backingScale": window.backingScaleFactor]
    }
    private func appInfo(_ app: NSRunningApplication?) -> [String: Any] {
        guard let app else { return [:] }
        return ["pid": Int(app.processIdentifier), "bundleID": app.bundleIdentifier ?? "",
                "path": app.bundleURL.map { real($0).path } ?? "", "active": app.isActive,
                "hidden": app.isHidden, "terminated": app.isTerminated]
    }
    private func log(_ event: String, _ fields: [String: Any] = [:]) {
        var data = fields
        data["event"] = event
        data["seconds"] = ((ProcessInfo.processInfo.systemUptime - epoch) * 1000).rounded() / 1000
        data["launcherPID"] = Int(ProcessInfo.processInfo.processIdentifier)
        data["launcherPath"] = real(Bundle.main.bundleURL).path
        guard let json = try? JSONSerialization.data(withJSONObject: data, options: [.sortedKeys, .withoutEscapingSlashes]),
              let line = String(data: json, encoding: .utf8) else { return }
        print(line); fflush(stdout)
        try? logFile?.write(contentsOf: json + Data([10]))
    }
    private func validTarget(_ candidate: URL) -> URL? {
        let url = real(candidate)
        guard url.pathExtension.lowercased() == "app", url != real(Bundle.main.bundleURL),
              !url.deletingLastPathComponent().pathComponents.contains(where: { $0.lowercased().hasSuffix(".app") }),
              let bundle = Bundle(url: url), bundle.bundleIdentifier == targetID,
              let executable = bundle.executableURL.map({ real($0) }),
              executable.path.hasPrefix(url.appendingPathComponent("Contents/MacOS").path + "/"),
              FileManager.default.isExecutableFile(atPath: executable.path) else { return nil }
        return url
    }
    private func resolveTarget() -> URL? {
        var candidates = NSRunningApplication.runningApplications(withBundleIdentifier: targetID).compactMap { $0.bundleURL }
        candidates += [URL(fileURLWithPath: "/Applications/ChatGPT.app"), URL(fileURLWithPath: "/Applications/Codex.app")]
        if let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: targetID) { candidates.append(url) }
        return candidates.compactMap { validTarget($0) }.first
    }
    private func lockInstance() -> Bool {
        let path = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("\(launcherID)-\(getuid()).lock").path
        lockFD = Darwin.open(path, O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, S_IRUSR | S_IWUSR)
        guard lockFD >= 0 else { log("lock-error", ["errno": errno]); return false }
        guard flock(lockFD, LOCK_EX | LOCK_NB) == 0 else {
            let existing = NSRunningApplication.runningApplications(withBundleIdentifier: launcherID)
                .first { $0.processIdentifier != ProcessInfo.processInfo.processIdentifier && !$0.isTerminated }
            let result = existing?.activate(options: []) ?? false
            log("duplicate-entry", ["existing": appInfo(existing), "activationRequested": result])
            close(lockFD); lockFD = -1; return false
        }
        return true
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        if let path = option("--log") {
            do {
                let url = URL(fileURLWithPath: path)
                try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
                if !FileManager.default.fileExists(atPath: path) { FileManager.default.createFile(atPath: path, contents: nil) }
                logFile = try FileHandle(forWritingTo: url); try logFile?.seekToEnd()
            } catch { print("LOG ERROR: \(error.localizedDescription)") }
        }
        targetURL = resolveTarget()
        if args.contains("--probe") {
            log("probe", ["launcherPath": real(Bundle.main.bundleURL).path, "targetPath": targetURL?.path ?? "",
                          "targetBundleID": targetURL.flatMap { Bundle(url: $0)?.bundleIdentifier } ?? "",
                          "running": NSRunningApplication.runningApplications(withBundleIdentifier: targetID).map { appInfo($0) },
                          "frontmost": appInfo(NSWorkspace.shared.frontmostApplication)])
            terminating = true; NSApp.terminate(nil); return
        }
        guard lockInstance() else { terminating = true; NSApp.terminate(nil); return }
        log("player-start", ["mode": preview ? "preview" : "launch", "targetPath": targetURL?.path ?? ""])
        let menu = NSMenu(), item = NSMenuItem(), submenu = NSMenu()
        menu.addItem(item); item.submenu = submenu
        submenu.addItem(withTitle: "退出阿舟启动 Codex", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        NSApp.mainMenu = menu
        let screen = NSScreen.main ?? NSScreen.screens.first
        let available = screen?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        window = NSWindow(contentRect: available,
                          styleMask: [.titled, .closable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        window.title = "阿舟启动 Codex"; window.titleVisibility = .hidden; window.titlebarAppearsTransparent = true
        window.isReleasedWhenClosed = false; window.delegate = self
        window.backgroundColor = NSColor(srgbRed: 241/255, green: 234/255, blue: 223/255, alpha: 1)
        window.minSize = NSSize(width: min(640, available.width), height: min(420, available.height))
        // Maximize this player's entire frame inside the usable screen area.
        // This does not invoke macOS full-screen mode or create another Space.
        window.setFrame(available, display: false)
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(self, name: "launcher")
        webView = WKWebView(frame: window.contentView!.bounds, configuration: configuration)
        webView.autoresizingMask = [.width, .height]; webView.navigationDelegate = self
        webView.underPageBackgroundColor = window.backgroundColor
        if #available(macOS 13.3, *), args.contains("--inspect") { webView.isInspectable = true }
        window.contentView!.addSubview(webView)
        guard let resources = Bundle.main.resourceURL else { fail("资源目录不存在。", "resources-missing"); return }
        let root = resources.appendingPathComponent("web", isDirectory: true)
        webRoot = real(root)
        let page = root.appendingPathComponent("index.html")
        guard FileManager.default.fileExists(atPath: page.path) else { fail("动画文件不存在，请重新构建。", "page-missing"); return }
        // Keep the window invisible until the renderer reports decoded assets.
        webView.loadFileURL(page, allowingReadAccessTo: root)
        armWatchdog(20, "renderer-ready-timeout")
        log("window-created", windowGeometry())
    }
    private func armWatchdog(_ seconds: Double, _ reason: String) {
        watchdog?.invalidate()
        watchdog = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { [weak self] _ in
            guard let self, !self.terminating else { return }
            self.fail(self.done ? "Codex 启动等待超时，请从原应用入口检查。" : "动画播放器没有按时完成，请关闭后重试。",
                      self.done ? "target-launch-timeout" : reason)
        }
    }
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, !terminating else { return }
        let body = message.body as? [String: Any] ?? [:]
        let action = message.body as? String ?? body["action"] as? String ?? ""
        switch action {
        case "ready":
            guard !ready else { log("duplicate-ready-ignored"); return }
            ready = true
            let milliseconds = (body["duration"] as? NSNumber)?.doubleValue ?? 0
            let duration = milliseconds.isFinite && milliseconds > 0 ? milliseconds / 1000 : 0
            window.level = .floating; window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
            webView.evaluateJavaScript(preview ? "window.launcherUI.replay()" : "window.launcherUI.beginLaunch()") { [weak self] _, error in
                guard let self, !self.terminating else { return }
                if let error { self.fail(error.localizedDescription, "playback-start-error"); return }
                self.log("playback-start", ["durationSeconds": duration, "window": self.windowGeometry()])
                self.armWatchdog(max(25, duration + 12), "renderer-complete-timeout")
                self.scheduleSnapshots(duration)
                if !self.preview { self.startTarget() }
            }
        case "complete":
            guard ready, !done, !failed else { return }
            done = true
            log("animation-complete", ["report": body["report"] ?? [:]])
            if preview {
                watchdog?.invalidate()
                // Native preview is deliberately one-shot: it cannot retain the
                // application's identity and accidentally swallow a later launch.
                webView.evaluateJavaScript("JSON.stringify(window.launcherUI.report())") { [weak self] result, error in
                    self?.log("preview-result", ["reportJSON": result as? String ?? "", "error": error?.localizedDescription ?? "",
                                                 "measurementScope": "front-end JS/rAF only, not GPU/presentation timing"])
                    self?.terminating = true; NSApp.terminate(nil)
                }
            } else { finishIfReady("animation-complete") }
        case "close":
            terminating = true; NSApp.terminate(nil)
        case "jsError": fail(body["message"] as? String ?? "动画脚本运行失败。", "javascript-error")
        case "assetError": fail(body["message"] as? String ?? "阿舟素材加载失败，请检查本地私有素材并重新构建。", "asset-error")
        default: log("unhandled-message", ["action": action])
        }
    }
    private func startTarget() {
        guard !requested, !terminating else { return }; requested = true
        guard let url = targetURL, validTarget(url) == url else { fail("没有找到有效的 Codex 主程序。", "target-missing"); return }
        if let existing = NSRunningApplication.runningApplications(withBundleIdentifier: targetID)
            .first(where: { !$0.isTerminated && $0.bundleURL.map({ real($0) }) == url }) {
            target = existing; log("target-reused", ["target": appInfo(existing)])
            startWallpaper(existing, cold: false); finishIfReady("target-reused"); return
        }
        opening = true
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = false; configuration.hides = false; configuration.hidesOthers = false
        configuration.createsNewApplicationInstance = false; configuration.allowsRunningApplicationSubstitution = false
        configuration.addsToRecentItems = false
        let wallpaperPort = prepareWallpaperPort()
        if let port = wallpaperPort {
            // Pass a positive port: Chromium's port=0 also enables its
            // AutomationControlled runtime feature. Never use zero as fallback.
            configuration.arguments = ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=\(port)"]
        } else {
            let result: [String: Any] = ["state": "port-unavailable", "applied": false,
                                        "message": "未能准备壁纸连接端口；Codex 将正常启动，本次不应用壁纸。"]
            wallpaperStarted = true; wallpaperResult = result
            log("wallpaper-port-unavailable", result); showWallpaperStatus(result)
        }
        log("target-open-request", ["path": url.path, "bundleID": targetID])
        NSWorkspace.shared.openApplication(at: url, configuration: configuration) { [weak self] app, error in
            DispatchQueue.main.async {
                guard let self, !self.terminating else { return }; self.opening = false
                if let error { self.fail("Codex 启动失败：\(error.localizedDescription)", "target-open-error"); return }
                guard let app, !app.isTerminated, app.bundleIdentifier == self.targetID,
                      app.bundleURL.map({ self.real($0) }) == url else { self.fail("系统返回的应用与核实路径不符。", "target-mismatch"); return }
                self.target = app
                self.log("target-launch-completion", ["target": self.appInfo(app), "rendererReadiness": "not-measured"])
                if wallpaperPort != nil { self.startWallpaper(app, cold: true) }
                self.finishIfReady("target-launch-completion")
            }
        }
    }
    private func prepareWallpaperPort() -> Int? {
        func refused(_ operation: String) -> Int? {
            let code = errno
            log("wallpaper-port-error", ["operation": operation, "errno": Int(code)]); return nil
        }
        let descriptor = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else { return refused("socket") }
        defer { Darwin.close(descriptor) }
        guard fcntl(descriptor, F_SETFD, FD_CLOEXEC) == 0 else { return refused("close-on-exec") }
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = 0
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bound = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.bind(descriptor, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
        }
        guard bound == 0 else { return refused("bind-loopback") }
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.getsockname(descriptor, $0, &length) }
        }
        guard named == 0 else { return refused("getsockname") }
        let port = Int(UInt16(bigEndian: address.sin_port))
        guard (1...65535).contains(port), address.sin_family == sa_family_t(AF_INET),
              address.sin_addr.s_addr == inet_addr("127.0.0.1") else {
            log("wallpaper-port-error", ["operation": "validate-selected-port"]); return nil
        }
        // The reservation closes on return, before NSWorkspace launches Codex.
        // Another process may win the bind-close race; the helper must still
        // discover and verify Codex's actual PID-owned listener, with no retry
        // that launches another app instance or terminates an existing one.
        log("wallpaper-port-selected", ["port": port, "requiresTargetListenerVerification": true])
        return port
    }
    private func startWallpaper(_ app: NSRunningApplication, cold: Bool) {
        guard !wallpaperStarted, !preview, !terminating, let executable = Bundle.main.executableURL,
              let bundle = app.bundleURL, validTarget(bundle) == real(bundle) else { return }
        wallpaperStarted = true
        let requestID = UUID().uuidString, helper = Process()
        helper.executableURL = executable
        helper.arguments = ["--wallpaper-helper", "--action", "apply", "--target-pid", String(app.processIdentifier),
                            "--target-bundle", real(bundle).path, "--request-id", requestID]
        if let date = app.launchDate { helper.arguments?.append(contentsOf: ["--target-start-time", String(date.timeIntervalSince1970)]) }
        if cold { helper.arguments?.append("--cold") }
        helper.standardOutput = FileHandle.nullDevice; helper.standardError = FileHandle.nullDevice
        helper.terminationHandler = { [weak self] task in
            let result = WallpaperJournal.latest(requestID: requestID) ?? ["state": "unconfirmed", "applied": false,
                "message": "壁纸辅助任务已结束，但没有可核实的完成记录。", "exitCode": Int(task.terminationStatus)]
            DispatchQueue.main.async {
                guard let self else { return }
                self.wallpaperResult = result
                self.log("wallpaper-helper-complete", ["result": result, "exitCode": Int(task.terminationStatus)])
                if !self.terminating { self.showWallpaperStatus(result) }
            }
        }
        wallpaperProcess = helper
        do {
            try helper.run()
            log("wallpaper-helper-start", ["helperPID": Int(helper.processIdentifier), "target": appInfo(app),
                                           "mode": cold ? "cold" : "warm", "deadlineSeconds": 30, "requestID": requestID])
        } catch {
            let result: [String: Any] = ["state": "helper-failed", "applied": false, "message": "壁纸辅助任务未能启动。"]
            wallpaperResult = result; log("wallpaper-helper-failed", ["message": error.localizedDescription]); showWallpaperStatus(result)
        }
    }
    private func showWallpaperStatus(_ result: [String: Any]) {
        guard ready else { return }
        let state = result["state"] as? String ?? "unconfirmed"
        let message = state == "applied" ? "阿舟壁纸已应用" : state == "needs-restart"
            ? "壁纸未应用：请自行完全退出 Codex，再从阿舟入口启动。"
            : "壁纸本次未确认生效；Codex 将正常打开。"
        guard let data = try? JSONSerialization.data(withJSONObject: [message]), let json = String(data: data, encoding: .utf8) else { return }
        // A separate text node survives the animation's normal phase updates.
        // It adds no dialog, focus change, replay, or delay to the 7.8s sequence.
        webView.evaluateJavaScript("""
        (() => { const phase = document.getElementById('phase'); if (!phase) return;
          let note = document.getElementById('wallpaper-status');
          if (!note) { note = document.createElement('span'); note.id = 'wallpaper-status'; note.setAttribute('role','status');
            note.style.letterSpacing = '0'; note.style.color = '#795f78'; phase.parentElement.appendChild(note); }
          note.textContent = ' · ' + \(json)[0];
        })()
        """, completionHandler: nil)
    }
    @discardableResult
    private func activateOnce(_ reason: String) -> Bool {
        if activated { return true }
        guard let target, !target.isTerminated else { return false }
        let result = target.activate(options: [])
        activated = result
        log("target-activation-request", ["reason": reason, "allowed": result, "target": appInfo(target)])
        return result
    }
    private func finishIfReady(_ reason: String) {
        guard done, !preview, !terminating, !failed else { return }
        if let target, target.isTerminated { fail("Codex 在交接前已经退出。", "target-exited"); return }
        guard !opening, let target, !target.isTerminated else {
            webView.evaluateJavaScript("window.launcherUI.waiting()"); log("waiting-for-target"); return
        }
        guard activateOnce(reason) else {
            fail("系统没有接受 Codex 激活请求。请关闭此窗口后，从原应用入口打开。", "activation-rejected"); return
        }
        terminating = true; wallpaperMayFinish = true; watchdog?.invalidate(); snapshots.forEach { $0.cancel() }
        log("handoff-fade-start", ["frontmost": appInfo(NSWorkspace.shared.frontmostApplication),
                                   "wallpaper": wallpaperResult ?? ["state": "pending", "applied": false],
                                   "wallpaperHelperStillFinishing": wallpaperProcess?.isRunning ?? false])
        NSAnimationContext.runAnimationGroup({ context in
            context.duration = 0.28; self.window.animator().alphaValue = 0
        }, completionHandler: {
            self.log("handoff-fade-complete", ["frontmost": self.appInfo(NSWorkspace.shared.frontmostApplication), "target": self.appInfo(self.target)])
            self.window.orderOut(nil); NSApp.terminate(nil)
        })
    }
    private func fail(_ message: String, _ reason: String) {
        guard !failed, !terminating else { return }; failed = true
        watchdog?.invalidate(); snapshots.forEach { $0.cancel() }; window?.level = .normal
        log("failure", ["reason": reason, "message": message, "target": appInfo(target)])
        if args.contains("--smoke-test") { terminating = true; NSApp.terminate(nil); return }
        if ready, let data = try? JSONSerialization.data(withJSONObject: [message]), let json = String(data: data, encoding: .utf8) {
            window.makeKeyAndOrderFront(nil)
            webView.evaluateJavaScript("window.launcherUI.error(\(json)[0])") { [weak self] _, error in
                if error != nil { self?.nativeError(message) }
            }
        } else { nativeError(message) }
    }
    private func nativeError(_ message: String) {
        let alert = NSAlert(); alert.messageText = "阿舟启动 Codex"; alert.informativeText = message
        alert.addButton(withTitle: "关闭"); NSApp.activate(ignoringOtherApps: true); alert.runModal()
        terminating = true; NSApp.terminate(nil)
    }
    private func scheduleSnapshots(_ duration: Double) {
        guard let directory = option("--snapshot") else { return }
        do { try FileManager.default.createDirectory(atPath: directory, withIntermediateDirectories: true) }
        catch { log("snapshot-error", ["message": error.localizedDescription]); return }
        let times = (option("--snapshot-times") ?? "0.4,1.4,2.3,3.5,5.5,7.3").split(separator: ",").compactMap { Double($0) }
        for (i, seconds) in times.enumerated() where seconds.isFinite && seconds >= 0 && (duration == 0 || seconds < duration) {
            let work = DispatchWorkItem { [weak self] in
                guard let self, !self.terminating else { return }
                let base = URL(fileURLWithPath: directory).appendingPathComponent(String(format: "%02d-%.2fs", i + 1, seconds))
                self.webView.evaluateJavaScript("JSON.stringify(window.launcherUI.report())") { result, _ in
                    if let report = result as? String { try? report.write(to: base.appendingPathExtension("json"), atomically: true, encoding: .utf8) }
                }
                self.webView.takeSnapshot(with: nil) { [weak self] image, error in
                    guard let data = image?.tiffRepresentation, let bitmap = NSBitmapImageRep(data: data),
                          let png = bitmap.representation(using: .png, properties: [:]) else {
                        self?.log("snapshot-error", ["message": error?.localizedDescription ?? "no image"]); return
                    }
                    do { try png.write(to: base.appendingPathExtension("png")); self?.log("snapshot-saved", ["path": base.path + ".png", "scheduledSeconds": seconds]) }
                    catch { self?.log("snapshot-error", ["message": error.localizedDescription]) }
                }
            }
            snapshots.append(work); DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: work)
        }
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        guard !terminating else { return false }
        if ready || failed { window?.makeKeyAndOrderFront(nil) }
        log("reopen-existing-player", ["launchRequested": requested, "completed": done])
        if preview && !done && !failed && !args.contains("--smoke-test") {
            promoted = true
            guard ready else { log("preview-launch-pending"); return false }
            webView.evaluateJavaScript("window.launcherUI.promoteLaunch()") { [weak self] _, error in
                guard let self else { return }
                if let error { self.fail(error.localizedDescription, "preview-promotion-error"); return }
                self.log("preview-promoted-to-launch"); self.startTarget()
            }
        }
        return false
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if preview || failed { terminating = true; NSApp.terminate(nil) }
        else { done = true; log("window-close-as-skip"); finishIfReady("window-close") }
        return false
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if !terminating { if !preview && !failed { activateOnce("user-quit") }; terminating = true }
        return .terminateNow
    }
    func applicationWillTerminate(_ notification: Notification) {
        watchdog?.invalidate(); snapshots.forEach { $0.cancel() }
        if let helper = wallpaperProcess, helper.isRunning {
            if wallpaperMayFinish { log("wallpaper-helper-finishing-after-handoff", ["helperPID": Int(helper.processIdentifier), "deadlineSeconds": 30]) }
            else { helper.terminate(); log("wallpaper-helper-cancelled", ["helperPID": Int(helper.processIdentifier), "reason": "player-cancelled"]) }
        }
        log("player-terminated", ["failed": failed, "completed": done, "frontmost": appInfo(NSWorkspace.shared.frontmostApplication)])
        webView?.stopLoading(); webView?.configuration.userContentController.removeScriptMessageHandler(forName: "launcher")
        if lockFD >= 0 { flock(lockFD, LOCK_UN); close(lockFD); lockFD = -1 }
        try? logFile?.close()
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url, url.isFileURL, let root = webRoot else { decisionHandler(.cancel); return }
        decisionHandler(real(url).path.hasPrefix(root.path + "/") ? .allow : .cancel)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { fail(error.localizedDescription, "navigation-error") }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { fail(error.localizedDescription, "navigation-error") }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { fail("WebKit 渲染进程已结束。", "renderer-terminated") }
}
@main
struct AzhouStartupMain {
    static func main() {
        if WallpaperCLI.handles(CommandLine.arguments) {
            // This mode creates no NSApplication, player window or launch request.
            exit(WallpaperCLI.run(CommandLine.arguments))
        }
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        // NSApplication.delegate is weak; keep the player delegate alive for
        // the complete run loop even in the optimized production build.
        withExtendedLifetime(delegate) { app.run() }
    }
}
