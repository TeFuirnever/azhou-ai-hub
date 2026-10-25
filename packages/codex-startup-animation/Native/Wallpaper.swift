import AppKit
import Foundation
import CoreFoundation
import Darwin

// A bounded, runtime-only wallpaper client. It never opens or terminates Codex.
// The launcher invokes this mode in the same executable, without a second .app.
enum WallpaperAction: String, Sendable { case apply, doctor, status, restore }

struct WallpaperFailure: LocalizedError {
    let state: String
    let message: String
    var errorDescription: String? { message }
}

enum WallpaperValidation {
    static func loopbackPorts(_ records: String, pid: Int32) throws -> [Int] {
        var owner: Int32?, addresses: [Int: Set<String>] = [:]
        for row in records.split(separator: "\n") {
            if row.first == "p" {
                owner = Int32(row.dropFirst())
                guard owner == pid else { throw WallpaperFailure(state: "target-mismatch", message: "监听端口不属于已核实的 Codex 进程。") }
            } else if row.first == "n" {
                guard owner == pid else { throw WallpaperFailure(state: "target-mismatch", message: "监听记录缺少已核实的进程身份。") }
                let address = String(row.dropFirst())
                guard let colon = address.lastIndex(of: ":"), let port = Int(address[address.index(after: colon)...]),
                      (1...65535).contains(port) else { continue }
                addresses[port, default: []].insert(address)
            }
        }
        return addresses.compactMap { port, values in values == ["127.0.0.1:\(port)"] ? port : nil }.sorted()
    }

    static func mainPage(_ entry: [String: Any]) -> Bool {
        guard entry["type"] as? String == "page", let raw = entry["url"] as? String,
              let url = URLComponents(string: raw), url.scheme == "app", url.host == "-",
              url.path == "/index.html", url.user == nil, url.password == nil, url.port == nil else { return false }
        let route = url.queryItems?.first(where: { $0.name == "initialRoute" })?.value ?? "/"
        return route.range(of: "avatar|quick.?chat|detached|mini|popover|notification", options: [.regularExpression, .caseInsensitive]) == nil
    }

    static func pageSocket(_ raw: String, port: Int) throws -> URL {
        guard let parts = URLComponents(string: raw), parts.scheme == "ws", parts.host == "127.0.0.1",
              parts.port == port, parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
              parts.path.range(of: "^/devtools/page/[A-Za-z0-9._-]+$", options: .regularExpression) != nil,
              let url = parts.url else { throw WallpaperFailure(state: "endpoint-refused", message: "拒绝非本机、非目标端口或非页面调试地址。") }
        return url
    }

    static func trueBoolean(_ value: Any?) -> Bool {
        guard let number = value as? NSNumber, CFGetTypeID(number) == CFBooleanGetTypeID() else { return false }
        return number.boolValue
    }
    static func surfaceCount(_ value: Any?) -> Int? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(), number.doubleValue.isFinite,
              number.doubleValue.rounded(.towardZero) == number.doubleValue, (0.0...1_000_000.0).contains(number.doubleValue) else { return nil }
        return number.intValue
    }
    static func versionString(_ value: Any?) -> String? {
        guard let text = value as? String, text.count <= 32,
              text.range(of: "^[0-9]+(?:\\.[0-9]+){1,3}$", options: .regularExpression) != nil else { return nil }
        return text
    }
    // Validate the full renderer contract. A self-reported applied flag must
    // not hide a failed/omitted decorative-layer check in a newer host layout.
    static let inspectionFlags = ["imageDecoded", "backgroundMatched", "coverMatched", "fixedViewport",
                                  "rootClear", "workspaceBackgroundClear", "footerBackgroundClear",
                                  "footerFadeClear", "topFadeClear", "decorationEffectsClear"]
    static func verificationIssues(_ state: [String: Any], version: String?) -> [String] {
        var issues = (["applied"] + inspectionFlags).filter { !trueBoolean(state[$0]) }
            .map { $0 + "-not-confirmed" }
        let surfaces = surfaceCount(state["matchedSurfaces"])
        if surfaces == nil || surfaces == 0 { issues.append("invalid-matched-surfaces") }
        if let count = surfaceCount(state["transparentSurfaces"]), count == surfaces {
            // Exact shell coverage, not just at least one transparent surface.
        } else { issues.append("incomplete-transparent-surfaces") }
        for key in ["footerSurfaces", "footerFadeSurfaces", "topFadeSurfaces"] {
            if surfaceCount(state[key]) == nil { issues.append("invalid-" + key) }
        }
        if let unsupported = state["unsupportedDecorations"] as? [String] {
            if !unsupported.isEmpty { issues.append("unsupported-decorations") }
        } else { issues.append("unreported-unsupported-decorations") }
        if let actual = versionString(state["version"]) {
            if let version, actual != version { issues.append("renderer-version-mismatch") }
        } else { issues.append("invalid-renderer-version") }
        return issues
    }
    static func verifiedState(_ state: [String: Any], version: String?) -> Bool {
        verificationIssues(state, version: version).isEmpty
    }
    static func verifiedPages(_ states: [[String: Any]], version: String?) -> Bool {
        guard !states.isEmpty, states.count <= 12,
              states.allSatisfy({ verifiedState($0, version: version) }) else { return false }
        return Set(states.compactMap { versionString($0["version"]) }).count == 1
    }
    static func diagnostic(_ state: [String: Any], index: Int, version: String?) -> [String: Any] {
        var result: [String: Any] = [
            "pageIndex": index, "version": versionString(state["version"]) ?? "",
            "applied": verifiedState(state, version: version),
            "verificationIssues": verificationIssues(state, version: version),
            // Forward only validated counts and fixed field names; never page
            // text, selectors, URLs or arbitrary renderer error strings.
            "unsupportedDecorationCount": (state["unsupportedDecorations"] as? [String]).map { min($0.count, 1_000_000) } ?? -1,
        ]
        for key in inspectionFlags { result[key] = trueBoolean(state[key]) }
        for key in ["matchedSurfaces", "transparentSurfaces", "footerSurfaces", "footerFadeSurfaces", "topFadeSurfaces"] {
            result[key] = surfaceCount(state[key]) ?? -1
        }
        return result
    }

    static func applicationFailure(priorStates: [[String: Any]], failedState: [String: Any]?,
                                   totalPages: Int, version: String?, failureState: String) -> [String: Any] {
        var pages = priorStates.enumerated().map {
            diagnostic($0.element, index: $0.offset, version: version)
        }
        var failed = diagnostic(failedState ?? [:], index: priorStates.count, version: version)
        if failedState == nil { failed["verificationIssues"] = ["renderer-state-unavailable"] }
        // Caller supplies only internal categories. Never forward an exception
        // description: it may contain the injected private image or page text.
        let category = ["renderer-not-applied", "renderer-rejected", "verification-failed"].contains(failureState)
            ? failureState : "renderer-not-applied"
        failed["failureState"] = category
        failed["applied"] = false
        pages.append(failed)
        let issues = Set(pages.flatMap { $0["verificationIssues"] as? [String] ?? [] })
        return [
            "state": category, "applied": false, "pageCount": totalPages,
            "attemptedPageCount": priorStates.count + 1,
            "completedPageCount": priorStates.count,
            "verifiedPageCount": priorStates.filter { verifiedState($0, version: version) }.count,
            "uninspectedPageCount": max(0, totalPages - priorStates.count - 1),
            "pages": pages, "verificationIssues": issues.sorted(),
            "message": "壁纸应用未完成，已停止后续页面；已处理页面与失败原因见 pages。",
        ]
    }

}

enum WallpaperJournal {
    static var directory: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/AzhouCodexStartup", isDirectory: true)
    }
    private static func isLink(_ url: URL) -> Bool { (try? url.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) == true }
    static func latest(requestID: String) -> [String: Any]? {
        let url = directory.appendingPathComponent("latest.json")
        guard !isLink(directory), !isLink(url), let data = try? Data(contentsOf: url),
              let result = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              result["requestID"] as? String == requestID else { return nil }
        return result
    }
    static func record(_ result: [String: Any]) {
        do {
            guard !isLink(directory) else { return }
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true,
                                                    attributes: [.posixPermissions: 0o700])
            let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys, .withoutEscapingSlashes]) + Data([10])
            let destination = directory.appendingPathComponent("latest.json")
            guard !isLink(destination) else { return }
            try data.write(to: destination, options: [.atomic])
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: destination.path)
            let path = directory.appendingPathComponent("wallpaper.jsonl").path
            let descriptor = Darwin.open(path, O_CREAT | O_WRONLY | O_APPEND | O_CLOEXEC | O_NOFOLLOW, S_IRUSR | S_IWUSR)
            guard descriptor >= 0 else { return }
            let stream = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
            if ((try? stream.seekToEnd()) ?? 0) > 2 * 1024 * 1024 { try stream.truncate(atOffset: 0) }
            try stream.write(contentsOf: data); try stream.close()
        } catch { /* A logging failure cannot interrupt the user's Codex session. */ }
    }
}

private struct WallpaperTarget: Sendable {
    let pid: Int32, bundle: URL, executable: URL, launchDate: Date?
    private static func real(_ url: URL) -> URL { url.resolvingSymlinksInPath().standardizedFileURL }
    init(pid: Int32, bundle: URL, launchTime: TimeInterval?) throws {
        let realBundle = Self.real(bundle)
        guard pid > 0, realBundle.pathExtension.lowercased() == "app",
              realBundle != Self.real(Bundle.main.bundleURL),
              !realBundle.deletingLastPathComponent().pathComponents.contains(where: { $0.lowercased().hasSuffix(".app") }),
              let package = Bundle(url: realBundle), package.bundleIdentifier == "com.openai.codex",
              let binary = package.executableURL.map(Self.real),
              binary.path.hasPrefix(realBundle.appendingPathComponent("Contents/MacOS").path + "/"),
              FileManager.default.isExecutableFile(atPath: binary.path),
              let app = NSRunningApplication(processIdentifier: pid), !app.isTerminated,
              app.bundleIdentifier == "com.openai.codex", app.bundleURL.map(Self.real) == realBundle,
              app.executableURL.map(Self.real) == binary else {
            throw WallpaperFailure(state: "target-mismatch", message: "目标 PID、真实应用路径或主可执行文件不匹配；未连接壁纸。")
        }
        if let launchTime {
            guard let date = app.launchDate, abs(date.timeIntervalSince1970 - launchTime) < 0.01 else {
                throw WallpaperFailure(state: "target-changed", message: "Codex 进程已变化；未连接壁纸。")
            }
        }
        self.pid = pid; self.bundle = realBundle; self.executable = binary; self.launchDate = app.launchDate
        try validate()
    }
    func validate() throws {
        guard let app = NSRunningApplication(processIdentifier: pid), !app.isTerminated,
              app.bundleIdentifier == "com.openai.codex", app.bundleURL.map(Self.real) == bundle,
              app.executableURL.map(Self.real) == executable,
              launchDate == nil || app.launchDate == launchDate else {
            throw WallpaperFailure(state: "target-changed", message: "已核实的 Codex 进程已退出或发生变化。")
        }
        let process = try WallpaperCommand.run("/bin/ps", ["-ww", "-p", String(pid), "-o", "uid=", "-o", "comm="])
        let fields = process.trimmingCharacters(in: .whitespacesAndNewlines).split(maxSplits: 1, whereSeparator: { $0.isWhitespace })
        guard fields.count == 2, UInt32(fields[0]) == getuid(),
              Self.real(URL(fileURLWithPath: String(fields[1]))) == executable else {
            throw WallpaperFailure(state: "target-mismatch", message: "目标进程用户或执行路径与已核实的 Codex 不符。")
        }
    }
    func validateSignature() throws {
        _ = try WallpaperCommand.run("/usr/bin/codesign", ["--verify", "--strict", bundle.path], timeout: 6)
        let signature = try WallpaperCommand.run("/usr/bin/codesign", ["-dv", "--verbose=4", bundle.path], timeout: 3)
        guard signature.split(separator: "\n").contains("TeamIdentifier=2DC432GLL2") else {
            throw WallpaperFailure(state: "signature-refused", message: "目标签名不属于已核实的 OpenAI 应用；未连接壁纸。")
        }
        try validate()
    }
    func ports() throws -> [Int] {
        try validate()
        let records = try WallpaperCommand.run("/usr/sbin/lsof", ["-nP", "-a", "-p", String(pid), "-iTCP", "-sTCP:LISTEN", "-Fpn"], emptyExit: 1)
        return try WallpaperValidation.loopbackPorts(records, pid: pid)
    }
}

private enum WallpaperCommand {
    private final class State: @unchecked Sendable {
        let lock = NSLock()
        var active: [Process] = []
        var cancelled = false
    }
    private static let state = State()
    static func cancelAll() {
        state.lock.lock(); state.cancelled = true; let processes = state.active; state.lock.unlock()
        // These are only our own short-lived inspection commands. SIGTERM may
        // be inherited as ignored from the helper's dispatch-source handler.
        for process in processes where process.isRunning { kill(process.processIdentifier, SIGKILL) }
    }
    static func run(_ file: String, _ arguments: [String], timeout: TimeInterval = 2, emptyExit: Int32? = nil) throws -> String {
        state.lock.lock(); let cancelled = state.cancelled; state.lock.unlock()
        if cancelled { throw WallpaperFailure(state: "cancelled", message: "壁纸任务已取消。") }
        let process = Process(), pipe = Pipe(), stopped = DispatchSemaphore(value: 0)
        process.executableURL = URL(fileURLWithPath: file); process.arguments = arguments
        process.standardOutput = pipe; process.standardError = pipe
        process.terminationHandler = { _ in stopped.signal() }
        try process.run()
        state.lock.lock()
        if state.cancelled {
            state.lock.unlock(); if process.isRunning { kill(process.processIdentifier, SIGKILL) }
            throw WallpaperFailure(state: "cancelled", message: "壁纸任务已取消。")
        }
        state.active.append(process); state.lock.unlock()
        defer { state.lock.lock(); state.active.removeAll { $0 === process }; state.lock.unlock() }
        if stopped.wait(timeout: .now() + timeout) == .timedOut {
            process.terminate()
            if stopped.wait(timeout: .now() + 0.2) == .timedOut { kill(process.processIdentifier, SIGKILL) }
            throw WallpaperFailure(state: "inspection-timeout", message: "目标进程核查超时；未继续连接壁纸。")
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard process.terminationStatus == 0 else {
            if process.terminationStatus == emptyExit { return "" }
            throw WallpaperFailure(state: "inspection-failed", message: "目标进程或签名核查未通过。")
        }
        return String(data: data, encoding: .utf8) ?? ""
    }
}

private final class WallpaperTransport: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    private lazy var session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil; configuration.httpCookieStorage = nil; configuration.urlCredentialStorage = nil
        configuration.httpShouldSetCookies = false; configuration.connectionProxyDictionary = [:]
        configuration.timeoutIntervalForRequest = 2; configuration.timeoutIntervalForResource = 30
        return URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
    }()
    private var serial = 0
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
    func close() { session.invalidateAndCancel() }
    func pages(port: Int) async throws -> [[String: Any]] {
        let url = URL(string: "http://127.0.0.1:\(port)/json/list")!
        var request = URLRequest(url: url); request.cachePolicy = .reloadIgnoringLocalCacheData; request.timeoutInterval = 2
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse, response.statusCode == 200, response.url == url,
              data.count < 2 * 1024 * 1024,
              let entries = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw WallpaperFailure(state: "endpoint-unavailable", message: "该本机端口没有返回有效的页面调试列表。")
        }
        return entries.filter(WallpaperValidation.mainPage)
    }
    func socket(_ url: URL) -> URLSessionWebSocketTask {
        // The 2s HTTP-list timeout must not cut off the renderer's bounded 4s
        // image decode. Each CDP exchange still has its own 6s cancellation.
        var request = URLRequest(url: url); request.timeoutInterval = 30
        let task = session.webSocketTask(with: request); task.maximumMessageSize = 2 * 1024 * 1024; task.resume(); return task
    }
    func evaluate(_ source: String, on socket: URLSessionWebSocketTask) async throws -> [String: Any] {
        serial += 1; let id = serial
        let request: [String: Any] = ["id": id, "method": "Runtime.evaluate", "params": [
            "expression": source, "returnByValue": true, "awaitPromise": true, "userGesture": false, "timeout": 5000]]
        let data = try JSONSerialization.data(withJSONObject: request)
        let timeout = DispatchWorkItem { socket.cancel(with: .goingAway, reason: nil) }
        DispatchQueue.global().asyncAfter(deadline: .now() + 6, execute: timeout)
        defer { timeout.cancel() }
        try await socket.send(.string(String(decoding: data, as: UTF8.self)))
        while true {
            let message = try await socket.receive()
            let incoming: Data
            switch message { case .string(let text): incoming = Data(text.utf8); case .data(let bytes): incoming = bytes; @unknown default: continue }
            guard let answer = try JSONSerialization.jsonObject(with: incoming) as? [String: Any], answer["id"] as? Int == id else { continue }
            if let result = answer["result"] as? [String: Any], let details = result["exceptionDetails"] as? [String: Any] {
                // Keep only our fixed error categories; never log page contents,
                // a JavaScript stack, or the embedded private-image expression.
                let description = (details["exception"] as? [String: Any])?["description"] as? String ?? ""
                let categories = ["unsupported-shell-no-surfaces", "page-changed-during-decode", "invalid-local-payload", "invalid-local-image",
                                  "image-decode-failed", "styles-not-effective", "namespace-conflict", "style-id-conflict"]
                let category = description.contains("AZHOU_WALLPAPER:") ? categories.first(where: { description.contains($0) }) : nil
                let pending = category == "unsupported-shell-no-surfaces" || category == "page-changed-during-decode"
                throw WallpaperFailure(state: pending ? "renderer-not-ready" : "renderer-rejected",
                                       message: pending ? "Codex 主界面尚未准备好，正在有限等待。" : "壁纸脚本未通过页面验证：\(category ?? "renderer-exception")。")
            }
            guard answer["error"] == nil, let result = answer["result"] as? [String: Any],
                  let value = (result["result"] as? [String: Any])?["value"] as? [String: Any] else {
                throw WallpaperFailure(state: "renderer-rejected", message: "Codex 页面没有确认壁纸操作；未标记应用成功。")
            }
            return value
        }
    }
}

private struct WallpaperRequest: Sendable {
    let action: WallpaperAction, target: WallpaperTarget, port: Int?, cold: Bool, requestID: String
    init(_ arguments: [String]) throws {
        func option(_ name: String) -> String? {
            guard let index = arguments.firstIndex(of: name), index + 1 < arguments.count else { return nil }
            return arguments[index + 1]
        }
        let shortcut = arguments.contains("--wallpaper-status")
        guard let action = WallpaperAction(rawValue: shortcut ? "status" : option("--action") ?? "apply") else {
            throw WallpaperFailure(state: "invalid-request", message: "壁纸操作必须为 apply、doctor、status 或 restore。")
        }
        var suppliedPID = option("--target-pid"), suppliedBundle = option("--target-bundle")
        var launchTime = option("--target-start-time").flatMap(Double.init)
        if shortcut, suppliedPID == nil, suppliedBundle == nil {
            let candidates = NSRunningApplication.runningApplications(withBundleIdentifier: "com.openai.codex").filter { !$0.isTerminated }
            guard candidates.count == 1, let app = candidates.first, let bundle = app.bundleURL else {
                throw WallpaperFailure(state: "target-unavailable", message: "未找到唯一的正在运行的 Codex；状态检查不会启动应用。")
            }
            suppliedPID = String(app.processIdentifier); suppliedBundle = bundle.path; launchTime = app.launchDate?.timeIntervalSince1970
        }
        guard let textPID = suppliedPID, let pid = Int32(textPID), pid > 0,
              let path = suppliedBundle, path.hasPrefix("/") else {
            throw WallpaperFailure(state: "invalid-request", message: "壁纸操作需要明确的目标 PID 和绝对应用路径。")
        }
        if let rawPort = option("--port") {
            guard option("--target-pid") != nil, let value = Int(rawPort), (1...65535).contains(value) else {
                throw WallpaperFailure(state: "invalid-request", message: "指定端口时必须同时指定并核实目标 PID；端口范围为 1–65535。")
            }
            port = value
        } else { port = nil }
        self.action = action; self.target = try WallpaperTarget(pid: pid, bundle: URL(fileURLWithPath: path), launchTime: launchTime)
        self.cold = arguments.contains("--cold"); self.requestID = option("--request-id") ?? UUID().uuidString
    }
}

enum WallpaperCLI {
    static func handles(_ arguments: [String]) -> Bool { arguments.contains("--wallpaper-helper") || arguments.contains("--wallpaper-status") }
    private static let statusSource = """
    (() => { const u = new URL(location.href);
      if (window.top !== window || u.protocol !== 'app:' || u.hostname !== '-' || u.pathname !== '/index.html'
          || /avatar|quick.?chat|detached|mini|popover|notification/i.test(u.searchParams.get('initialRoute') || '/')) return {applied:false,reason:'wrong-page'};
      return globalThis.__azhouWallpaper?.status?.() || {applied:false,imageDecoded:false,matchedSurfaces:0,backgroundMatched:false,reason:'not-installed'};
    })()
    """
    private static let restoreSource = """
    (() => { const u = new URL(location.href);
      if (window.top !== window || u.protocol !== 'app:' || u.hostname !== '-' || u.pathname !== '/index.html'
          || /avatar|quick.?chat|detached|mini|popover|notification/i.test(u.searchParams.get('initialRoute') || '/')) return {restored:false,reason:'wrong-page'};
      globalThis.__azhouWallpaper?.dispose?.();
      const state = globalThis.__azhouWallpaper?.status?.();
      return {restored:!state || state.applied === false,applied:state?.applied === true};
    })()
    """
    private final class Completion: @unchecked Sendable {
        let signal = DispatchSemaphore(value: 0)
        private let lock = NSLock()
        private var value: [String: Any]?
        func finish(_ result: [String: Any]) { lock.lock(); defer { lock.unlock() }; if value == nil { value = result; signal.signal() } }
        func result() -> [String: Any] { lock.lock(); defer { lock.unlock() }; return value ?? [:] }
    }
    static func run(_ arguments: [String]) -> Int32 {
        let began = ProcessInfo.processInfo.systemUptime
        var action = arguments.contains("--wallpaper-status") ? "status" : "apply"
        if !arguments.contains("--wallpaper-status"), let index = arguments.firstIndex(of: "--action"), index + 1 < arguments.count { action = arguments[index + 1] }
        var base: [String: Any] = ["event": "wallpaper-result", "action": action, "applied": false,
                                  "helperPID": Int(getpid()), "deadlineSeconds": 30,
                                  "version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""]
        let completion = Completion()
        // User cancellation stops only this helper and its own inspection tools.
        signal(SIGTERM, SIG_IGN)
        let cancellation = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .global())
        cancellation.setEventHandler { completion.finish(["state": "cancelled", "applied": false, "message": "本次壁纸任务已取消；Codex 保持运行。"] ) }
        cancellation.resume()
        // The process itself returns after this deadline, even if an OS request
        // stops responding. No timer or detached worker survives process exit.
        let timeout = DispatchWorkItem { completion.finish(["state": "timeout", "applied": false, "message": "壁纸连接超过 30 秒，已停止；Codex 保持运行。"] ) }
        DispatchQueue.global().asyncAfter(deadline: .now() + 30, execute: timeout)
        let task = Task.detached {
            do {
                let request = try WallpaperRequest(arguments)
                var result: [String: Any]
                do { result = try await perform(request, began: began) }
                catch let error as WallpaperFailure { result = ["state": error.state, "applied": false, "message": error.message] }
                catch { result = ["state": "connection-failed", "applied": false, "message": "壁纸连接未完成；Codex 保持运行。"] }
                result["targetPID"] = Int(request.target.pid); result["targetPath"] = request.target.bundle.path
                result["requestID"] = request.requestID; result["action"] = request.action.rawValue
                completion.finish(result)
            } catch let error as WallpaperFailure { completion.finish(["state": error.state, "applied": false, "message": error.message]) }
            catch { completion.finish(["state": "invalid-request", "applied": false, "message": "无法核实壁纸操作目标。"] ) }
        }
        completion.signal.wait(); timeout.cancel(); task.cancel(); cancellation.cancel(); WallpaperCommand.cancelAll()
        base.merge(completion.result()) { _, value in value }
        if base["requestID"] == nil, let index = arguments.firstIndex(of: "--request-id"), index + 1 < arguments.count { base["requestID"] = arguments[index + 1] }
        base["seconds"] = ((ProcessInfo.processInfo.systemUptime - began) * 1000).rounded() / 1000
        base["timestamp"] = ISO8601DateFormatter().string(from: Date())
        if action == "apply" || action == "restore" { WallpaperJournal.record(base) }
        if let data = try? JSONSerialization.data(withJSONObject: base, options: [.sortedKeys, .withoutEscapingSlashes]) {
            try? FileHandle.standardOutput.write(contentsOf: data + Data([10]))
        }
        return ["applied", "restored", "ready"].contains(base["state"] as? String ?? "") ? 0 : 2
    }

    private static func perform(_ request: WallpaperRequest, began: TimeInterval) async throws -> [String: Any] {
        let target = request.target, transport = WallpaperTransport()
        defer { transport.close() }
        var lock: Int32 = -1
        if request.action == .apply || request.action == .restore {
            let path = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("local.azhou.wallpaper-\(getuid())-\(target.pid).lock").path
            lock = Darwin.open(path, O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, S_IRUSR | S_IWUSR)
            guard lock >= 0, flock(lock, LOCK_EX | LOCK_NB) == 0 else {
                if lock >= 0 { close(lock) }; throw WallpaperFailure(state: "busy", message: "该 Codex 进程已有壁纸操作，未重复注入。")
            }
        }
        defer { if lock >= 0 { flock(lock, LOCK_UN); close(lock) } }
        if !request.cold, request.port == nil, try target.ports().isEmpty {
            return ["state": "needs-restart", "applied": false,
                    "message": "当前 Codex 未开放壁纸连接。请自行完全退出 Codex，再从阿舟入口启动；本次没有重启或更改工作会话。"]
        }
        try target.validateSignature()
        let expectedVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
        var source = ""
        if request.action == .apply {
            guard let url = Bundle.main.resourceURL?.appendingPathComponent("wallpaper/install.js"),
                  (try? url.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) != true,
                  let bytes = try? Data(contentsOf: url), bytes.count < 24 * 1024 * 1024,
                  let text = String(data: bytes, encoding: .utf8), !text.isEmpty else {
                throw WallpaperFailure(state: "resource-missing", message: "缺少已打包的阿舟壁纸脚本，请重新构建并安装。")
            }
            source = text
        }
        var sawEndpoint = false, lastState = "endpoint-unavailable"
        while ProcessInfo.processInfo.systemUptime - began < 28 {
            try Task.checkCancellation(); try target.validate()
            let owned = try target.ports()
            if let port = request.port, !owned.contains(port) {
                throw WallpaperFailure(state: "endpoint-refused", message: "指定端口不是该 Codex 主进程独占的 IPv4 回环监听端口。")
            }
            let ports = request.port.map { [$0] } ?? owned
            if ports.isEmpty && !request.cold {
                return ["state": "needs-restart", "applied": false,
                        "message": "当前 Codex 未开放壁纸连接。请自行完全退出 Codex，再从阿舟入口启动；本次没有重启或更改工作会话。"]
            }
            for port in ports.prefix(12) {
                do {
                    let pages = try await transport.pages(port: port); sawEndpoint = true
                    if pages.isEmpty { lastState = "main-page-unavailable"; continue }
                    guard pages.count <= 12 else { throw WallpaperFailure(state: "page-count-refused", message: "主页面数量超出本次有限壁纸操作范围。") }
                    if request.action == .doctor {
                        return ["state": "ready", "applied": false, "canApply": true, "port": port, "pageCount": pages.count,
                                "message": "已找到已核实 Codex 的本机主页面；此诊断没有注入壁纸。"]
                    }
                    var states: [[String: Any]] = []
                    for page in pages {
                        try Task.checkCancellation(); try target.validate()
                        guard try target.ports().contains(port), let raw = page["webSocketDebuggerUrl"] as? String else {
                            throw WallpaperFailure(state: "endpoint-changed", message: "目标监听或页面地址已变化，停止本次壁纸操作。")
                        }
                        let socket = transport.socket(try WallpaperValidation.pageSocket(raw, port: port))
                        defer { socket.cancel(with: .normalClosure, reason: nil) }
                        if request.action == .apply {
                            let applied: [String: Any]
                            do { applied = try await transport.evaluate(source, on: socket) }
                            catch let error as WallpaperFailure where error.state == "renderer-rejected" {
                                var result = WallpaperValidation.applicationFailure(
                                    priorStates: states, failedState: nil, totalPages: pages.count,
                                    version: expectedVersion, failureState: error.state)
                                result["port"] = port
                                return result
                            }
                            guard WallpaperValidation.verifiedState(applied, version: expectedVersion) else {
                                var result = WallpaperValidation.applicationFailure(
                                    priorStates: states, failedState: applied, totalPages: pages.count,
                                    version: expectedVersion, failureState: "renderer-not-applied")
                                result["port"] = port
                                return result
                            }
                        } else if request.action == .restore {
                            let restored = try await transport.evaluate(restoreSource, on: socket)
                            guard restored["restored"] as? Bool == true else { throw WallpaperFailure(state: "restore-unconfirmed", message: "页面没有确认移除壁纸。") }
                        }
                        let state: [String: Any]
                        do { state = try await transport.evaluate(statusSource, on: socket) }
                        catch let error as WallpaperFailure where request.action == .apply && error.state == "renderer-rejected" {
                            var result = WallpaperValidation.applicationFailure(
                                priorStates: states, failedState: nil, totalPages: pages.count,
                                version: expectedVersion, failureState: error.state)
                            result["port"] = port
                            return result
                        }
                        try target.validate()
                        if request.action == .apply && !WallpaperValidation.verifiedState(state, version: expectedVersion) {
                            var result = WallpaperValidation.applicationFailure(
                                priorStates: states, failedState: state, totalPages: pages.count,
                                version: expectedVersion, failureState: "verification-failed")
                            result["port"] = port
                            return result
                        }
                        states.append(state)
                    }
                    if request.action == .restore {
                        guard states.allSatisfy({ $0["applied"] as? Bool != true }) else { throw WallpaperFailure(state: "restore-unconfirmed", message: "复查时壁纸仍存在。") }
                        return ["state": "restored", "applied": false, "restored": true, "port": port, "pageCount": states.count,
                                "message": "已移除本次运行中的阿舟壁纸；Codex 与调试端口保持原状态。"]
                    }
                    let requiredVersion = request.action == .apply ? expectedVersion : nil
                    let verified = WallpaperValidation.verifiedPages(states, version: requiredVersion)
                    let pageDiagnostics = states.enumerated().map {
                        WallpaperValidation.diagnostic($0.element, index: $0.offset, version: requiredVersion)
                    }
                    var issues = Set(pageDiagnostics.flatMap { $0["verificationIssues"] as? [String] ?? [] })
                    let versions = Set(states.compactMap { WallpaperValidation.versionString($0["version"]) })
                    if versions.count != 1 { issues.insert("mixed-renderer-versions") }
                    var result: [String: Any] = [
                        "state": verified ? "applied" : (request.action == .apply ? "verification-failed" : "not-applied"),
                        "applied": verified, "port": port, "pageCount": states.count,
                        "version": versions.count == 1 ? versions.first! : "",
                        "pages": pageDiagnostics, "verificationIssues": issues.sorted(),
                        "verificationScope": "runtime image and decorative-layer checks; visual inspection is separate",
                        "message": verified ? "已复查当前 Codex 页面中的阿舟壁纸。"
                            : "当前页面未通过壁纸图层核查；请查看 verificationIssues 与 pages。",
                    ]
                    for key in WallpaperValidation.inspectionFlags {
                        result[key] = states.allSatisfy { WallpaperValidation.trueBoolean($0[key]) }
                    }
                    for key in ["matchedSurfaces", "transparentSurfaces", "footerSurfaces", "footerFadeSurfaces", "topFadeSurfaces"] {
                        result[key] = states.reduce(0) { $0 + (WallpaperValidation.surfaceCount($1[key]) ?? 0) }
                    }
                    return result
                } catch let error as WallpaperFailure {
                    if ["target-mismatch", "target-changed", "endpoint-refused", "endpoint-changed", "page-count-refused",
                        "renderer-rejected", "renderer-not-applied", "verification-failed", "restore-unconfirmed"].contains(error.state) { throw error }
                    lastState = error.state
                } catch { lastState = "connection-failed" }
            }
            if !request.cold && !sawEndpoint {
                return ["state": "needs-restart", "applied": false,
                        "message": "当前 Codex 没有可核实的页面调试连接。请自行完全退出后再从阿舟入口启动；未重启当前会话。"]
            }
            try await Task.sleep(nanoseconds: 250_000_000)
        }
        return ["state": "timeout", "applied": false, "reason": lastState,
                "message": "在有限等待时间内未完成壁纸确认；Codex 保持运行，动画交接不受影响。"]
    }
}
