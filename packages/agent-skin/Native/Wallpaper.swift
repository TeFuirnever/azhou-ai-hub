import AppKit
import Foundation
import CoreFoundation
import CFNetwork
import Darwin

// A bounded, runtime-only wallpaper client. It never opens or terminates Codex.
// The launcher invokes this mode in the same executable, without a second .app.
enum WallpaperMessages {
    private static let systemLocale = WallpaperMessageLocale(preferredLanguages: Locale.preferredLanguages)

    static func localized(chinese: String, english: String) -> String {
        systemLocale.localized(chinese: chinese, english: english)
    }

    static func localized(chinese: String, english: String, preferredLanguages: [String]) -> String {
        WallpaperMessageLocale(preferredLanguages: preferredLanguages).localized(chinese: chinese, english: english)
    }

    static func prepareForRun() { _ = systemLocale }
}

private struct WallpaperMessageLocale {
    private let isChinese: Bool

    init(preferredLanguages: [String]) {
        isChinese = preferredLanguages.lazy.compactMap { language -> Bool? in
            let normalized = language.replacingOccurrences(of: "_", with: "-").lowercased()
            if normalized == "zh" || normalized.hasPrefix("zh-") { return true }
            if normalized == "en" || normalized.hasPrefix("en-") { return false }
            return nil
        }.first ?? false
    }

    func localized(chinese: String, english: String) -> String { isChinese ? chinese : english }
}

enum WallpaperAction: String, Sendable { case apply, retry, doctor, status, restore }

struct WallpaperFailure: LocalizedError {
    let state: String
    let message: String

    init(state: String, chinese: String, english: String) {
        self.state = state
        self.message = WallpaperMessages.localized(chinese: chinese, english: english)
    }

    var errorDescription: String? { message }
}

enum WallpaperValidation {
    static func loopbackPorts(_ records: String, pid: Int32) throws -> [Int] {
        var owner: Int32?, addresses: [Int: Set<String>] = [:]
        for row in records.split(separator: "\n") {
            if row.first == "p" {
                owner = Int32(row.dropFirst())
                guard owner == pid else { throw WallpaperFailure(state: "target-mismatch", chinese: "监听端口不属于已核实的 Codex 进程。", english: "The listening port does not belong to the verified Codex process.") }
            } else if row.first == "n" {
                guard owner == pid else { throw WallpaperFailure(state: "target-mismatch", chinese: "监听记录缺少已核实的进程身份。", english: "The listener record has no verified process identity.") }
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
              let url = parts.url else { throw WallpaperFailure(state: "endpoint-refused", chinese: "拒绝非本机、非目标端口或非页面调试地址。", english: "Refused a non-loopback, wrong-port, or non-page debugging address.") }
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
    static func failureDiagnostic(_ state: [String: Any]) -> [String: String] {
        let stages = [
            "shell-timeout": "shell", "shell-unsupported": "shell",
            "invalid-local-payload": "input", "invalid-local-image": "input",
            "image-decode-failed": "decode", "image-decode-timeout": "decode",
            "unsupported-shell-no-surfaces": "surfaces", "page-changed-during-decode": "page",
            "styles-not-effective": "styles", "styles-not-effective-after-replacement": "styles",
            "namespace-conflict": "namespace", "namespace-changed-during-decode": "namespace",
            "style-id-conflict": "style", "style-id-conflict-after-decode": "style",
            "apply-unavailable": "apply", "apply-failed": "apply", "retry-timeout": "apply",
        ]
        guard let code = state["failureCode"] as? String, let stage = stages[code] else { return [:] }
        return ["failureCode": code, "failureStage": stage]
    }
    static func retryFailure(_ recovery: [String: Any]) -> String? {
        let succeeded = (recovery["wallpaper"] as? [String: Any]).map { trueBoolean($0["applied"]) } ?? false
        if trueBoolean(recovery["retried"]) { return succeeded ? nil : "retry-failed" }
        let reason = recovery["reason"] as? String ?? "retry-failed"
        if reason == "already-applied" && succeeded { return nil }
        let refusals = ["busy", "disabled", "no-request", "disposed", "unknown-owner", "owner-conflict", "timeout", "operation-cancelled"]
        return refusals.contains(reason) ? reason : "retry-failed"
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
        result.merge(failureDiagnostic(state)) { _, value in value }
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
            "message": WallpaperMessages.localized(
                chinese: "壁纸应用未完成，已停止后续页面；已处理页面与失败原因见 pages。",
                english: "Wallpaper application did not finish. Remaining pages were skipped; see pages for completed pages and the failure reason."
            ),
        ]
    }

}

enum WallpaperJournal {
    static var directory: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/AzhouCodexStartup", isDirectory: true)
    }
    private static func isLink(_ url: URL) -> Bool { (try? url.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) == true }
    static func latest(requestID: String) -> [String: Any]? {
        latest(requestID: requestID, directory: directory)
    }
    static func latest(requestID: String, directory: URL) -> [String: Any]? {
        let url = directory.appendingPathComponent("latest.json")
        guard !isLink(directory), !isLink(url), let data = try? Data(contentsOf: url),
              let result = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              result["requestID"] as? String == requestID else { return nil }
        return result
    }
    static func record(_ result: [String: Any]) {
        record(result, directory: directory)
    }
    static func record(_ result: [String: Any], directory: URL) {
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

struct CodexBundleFacts: Sendable {
    let identifier: String?
    let executableURL: URL?
}

struct CodexProcessFacts: Sendable {
    let processIdentifier: Int32
    let isTerminated: Bool
    let bundleIdentifier: String?
    let bundleURL: URL?
    let executableURL: URL?
    let launchDate: Date?
}

struct CodexTargetEnvironment: @unchecked Sendable {
    let mainBundleURL: URL
    let bundleFacts: (URL) -> CodexBundleFacts?
    let processFacts: (Int32) -> CodexProcessFacts?
    let runningProcesses: (String) -> [CodexProcessFacts]
    let isExecutableFile: (URL) -> Bool
    let runCommand: (_ file: String, _ arguments: [String], _ timeout: TimeInterval, _ emptyExit: Int32?) throws -> String
    let currentUID: () -> UInt32
    let now: () -> TimeInterval

    static var live: CodexTargetEnvironment {
        CodexTargetEnvironment(
            mainBundleURL: Bundle.main.bundleURL,
            bundleFacts: { url in
                guard let bundle = Bundle(url: url) else { return nil }
                return CodexBundleFacts(identifier: bundle.bundleIdentifier, executableURL: bundle.executableURL)
            },
            processFacts: { pid in
                NSRunningApplication(processIdentifier: pid).map(Self.facts)
            },
            runningProcesses: { identifier in
                NSRunningApplication.runningApplications(withBundleIdentifier: identifier).map(Self.facts)
            },
            isExecutableFile: { FileManager.default.isExecutableFile(atPath: $0.path) },
            runCommand: { file, arguments, timeout, emptyExit in
                try WallpaperCommand.run(file, arguments, timeout: timeout, emptyExit: emptyExit)
            },
            currentUID: { getuid() },
            now: { ProcessInfo.processInfo.systemUptime }
        )
    }

    private static func facts(_ app: NSRunningApplication) -> CodexProcessFacts {
        CodexProcessFacts(processIdentifier: app.processIdentifier, isTerminated: app.isTerminated,
                          bundleIdentifier: app.bundleIdentifier, bundleURL: app.bundleURL,
                          executableURL: app.executableURL, launchDate: app.launchDate)
    }
}

private struct WallpaperTarget: Sendable {
    let pid: Int32, bundle: URL, executable: URL, launchDate: Date?
    let commandDeadline: TimeInterval?
    private let environment: CodexTargetEnvironment
    private static func real(_ url: URL) -> URL { url.resolvingSymlinksInPath().standardizedFileURL }
    init(pid: Int32, bundle: URL, launchTime: TimeInterval?, commandDeadline: TimeInterval? = nil,
         environment: CodexTargetEnvironment = .live) throws {
        let realBundle = Self.real(bundle)
        guard pid > 0, realBundle.pathExtension.lowercased() == "app",
              realBundle != Self.real(environment.mainBundleURL),
              !realBundle.deletingLastPathComponent().pathComponents.contains(where: { $0.lowercased().hasSuffix(".app") }),
              let package = environment.bundleFacts(realBundle), package.identifier == "com.openai.codex",
              let binary = package.executableURL.map(Self.real),
              binary.path.hasPrefix(realBundle.appendingPathComponent("Contents/MacOS").path + "/"),
              environment.isExecutableFile(binary),
              let app = environment.processFacts(pid), !app.isTerminated,
              app.bundleIdentifier == "com.openai.codex", app.bundleURL.map(Self.real) == realBundle,
              app.executableURL.map(Self.real) == binary else {
            throw WallpaperFailure(state: "target-mismatch", chinese: "目标 PID、真实应用路径或主可执行文件不匹配；未连接壁纸。", english: "The target PID, real app path, or main executable did not match; wallpaper was not connected.")
        }
        if let launchTime {
            guard let date = app.launchDate, abs(date.timeIntervalSince1970 - launchTime) < 0.01 else {
                throw WallpaperFailure(state: "target-changed", chinese: "Codex 进程已变化；未连接壁纸。", english: "The Codex process changed; wallpaper was not connected.")
            }
        }
        self.pid = pid; self.bundle = realBundle; self.executable = binary; self.launchDate = app.launchDate
        self.commandDeadline = commandDeadline
        self.environment = environment
        try validate(deadline: commandDeadline)
    }
    private func commandTimeout(_ maximum: TimeInterval, deadline: TimeInterval? = nil) throws -> TimeInterval {
        guard let deadline = deadline ?? commandDeadline else { return maximum }
        return try StartupBudget.boundedTimeout(maximum: maximum, stageDeadline: deadline,
                                                totalDeadline: deadline, now: environment.now())
    }
    func validate(deadline: TimeInterval? = nil) throws {
        guard let app = environment.processFacts(pid), !app.isTerminated,
              app.bundleIdentifier == "com.openai.codex", app.bundleURL.map(Self.real) == bundle,
              app.executableURL.map(Self.real) == executable,
              launchDate == nil || app.launchDate == launchDate else {
            throw WallpaperFailure(state: "target-changed", chinese: "已核实的 Codex 进程已退出或发生变化。", english: "The verified Codex process exited or changed.")
        }
        let process = try environment.runCommand("/bin/ps", ["-ww", "-p", String(pid), "-o", "uid=", "-o", "comm="],
                                                 try commandTimeout(2, deadline: deadline), nil)
        let fields = process.trimmingCharacters(in: .whitespacesAndNewlines).split(maxSplits: 1, whereSeparator: { $0.isWhitespace })
        guard fields.count == 2, UInt32(fields[0]) == environment.currentUID(),
              Self.real(URL(fileURLWithPath: String(fields[1]))) == executable else {
            throw WallpaperFailure(state: "target-mismatch", chinese: "目标进程用户或执行路径与已核实的 Codex 不符。", english: "The target process user or executable path does not match the verified Codex.")
        }
    }
    func validateSignature(deadline: TimeInterval? = nil) throws {
        try StartupBundleSignature.verify(bundle, deadline: deadline ?? commandDeadline, environment: environment)
        try validate(deadline: deadline)
    }
    func ports(deadline: TimeInterval? = nil) throws -> [Int] {
        try validate(deadline: deadline)
        let records = try environment.runCommand("/usr/sbin/lsof", ["-nP", "-a", "-p", String(pid), "-iTCP", "-sTCP:LISTEN", "-Fpn"],
                                                 try commandTimeout(3, deadline: deadline), 1)
        return try WallpaperValidation.loopbackPorts(records, pid: pid)
    }
}

private enum StartupBundleSignature {
    private static let requirement = "=anchor apple generic and identifier \"com.openai.codex\" and certificate leaf[subject.OU] = \"2DC432GLL2\""

    static func verify(_ bundle: URL, deadline: TimeInterval?, environment: CodexTargetEnvironment = .live) throws {
        let resolved = bundle.resolvingSymlinksInPath().standardizedFileURL
        guard resolved.pathExtension.lowercased() == "app",
              let package = environment.bundleFacts(resolved), package.identifier == "com.openai.codex" else {
            throw WallpaperFailure(state: "signature-refused", chinese: "Codex 应用路径或 Bundle ID 无效。", english: "The Codex app path or bundle ID is invalid.")
        }
        let timeout: TimeInterval
        if let deadline {
            timeout = try StartupBudget.boundedTimeout(maximum: 12, stageDeadline: deadline,
                                                       totalDeadline: deadline, now: environment.now())
        } else { timeout = 12 }
        do {
            _ = try environment.runCommand("/usr/bin/codesign",
                                           ["--verify", "--deep", "--strict", "-R", requirement, resolved.path],
                                           timeout, nil)
        } catch let error as WallpaperFailure where error.state == "inspection-timeout" {
            throw error
        } catch {
            throw WallpaperFailure(state: "signature-refused", chinese: "Codex 应用签名未通过 Apple 锚点、Bundle ID 和 Team ID 核验。", english: "The Codex app signature did not pass Apple anchor, bundle ID, and team ID verification.")
        }
    }
}

struct StartupTargetFacts: Sendable {
    let pid: Int32
    let bundle: URL
    let executable: URL
    let bundleID: String
    let launchTime: TimeInterval?
}

enum StartupOutcome: Equatable {
    case activated(pid: Int32)
    case ready(runID: Int)
    case skipped(runID: Int, beforeReady: Bool)
    case partial(reason: String)
    case failed(reason: String)
}

struct StartupFailure: LocalizedError {
    let reason: String
    let message: String
    var errorDescription: String? { message }
}

struct StartupBudget {
    let startedAt: TimeInterval
    let preflightDeadline: TimeInterval
    let totalDeadline: TimeInterval

    init(startedAt: TimeInterval) {
        self.startedAt = startedAt
        preflightDeadline = startedAt + 15
        totalDeadline = startedAt + 60
    }

    func attachDeadline(startedAt: TimeInterval) -> TimeInterval {
        min(startedAt + 45, totalDeadline)
    }

    func timeout(maximum: TimeInterval, stageDeadline: TimeInterval, now: TimeInterval) throws -> TimeInterval {
        try Self.boundedTimeout(maximum: maximum, stageDeadline: stageDeadline,
                                totalDeadline: totalDeadline, now: now)
    }

    static func boundedTimeout(maximum: TimeInterval, stageDeadline: TimeInterval,
                               totalDeadline: TimeInterval, now: TimeInterval) throws -> TimeInterval {
        let remaining = min(stageDeadline, totalDeadline) - now
        guard maximum.isFinite, maximum > 0, remaining.isFinite, remaining > 0 else {
            throw StartupFailure(reason: "attach-timeout", message: "Codex 启动已超过当前阶段预算。")
        }
        return min(maximum, remaining)
    }

    static func requestTimeoutMilliseconds(_ timeout: TimeInterval) throws -> Int {
        let milliseconds = floor(timeout * 1_000)
        guard timeout.isFinite, milliseconds >= 1, milliseconds <= Double(Int.max) else {
            throw StartupFailure(reason: "attach-timeout", message: "剩余启动预算不足以发送 CDP 请求。")
        }
        return Int(milliseconds)
    }
}

enum StartupLogPolicy {
    static func filePath(arguments: [String]) -> String? {
        guard !arguments.contains("--probe"),
              let index = arguments.firstIndex(of: "--log"), index + 1 < arguments.count else { return nil }
        return arguments[index + 1]
    }
}

enum StartupModePolicy {
    static func resolveTarget(arguments: [String], promoted: Bool, lookup: () -> URL?) -> URL? {
        let explicitProbe = arguments.contains("--probe")
        let previewMode = arguments.contains("--preview") || arguments.contains("--smoke-test")
        guard explicitProbe || promoted || !previewMode else { return nil }
        return lookup()
    }
}

enum StartupFailureDelivery {
    @discardableResult
    static func deliver(
        _ outcome: StartupOutcome,
        previewUI: Bool,
        message: (String) -> String,
        log: (String, String) -> Void,
        setExitCode: (Int32) -> Void,
        showPreviewError: (String, String) -> Void,
        terminate: (Int32) -> Void
    ) -> Bool {
        let reason: String
        let event: String
        let exitCode: Int32
        switch outcome {
        case .failed(let value): reason = value; event = "startup-failed"; exitCode = 1
        case .partial(let value): reason = value; event = "startup-partial"; exitCode = 2
        default: return false
        }
        log(event, reason)
        setExitCode(exitCode)
        if previewUI {
            showPreviewError(message(reason), reason)
        } else {
            terminate(exitCode)
        }
        return true
    }
}

enum StartupLaunchFlow {
    @MainActor
    static func run(
        existing: StartupTargetFacts?,
        preflightBundle: () throws -> Void,
        validate: (StartupTargetFacts) throws -> Void,
        activate: (StartupTargetFacts) throws -> Bool,
        coldStart: () async throws -> StartupOutcome
    ) async throws -> StartupOutcome {
        guard let existing else {
            try preflightBundle()
            return try await coldStart()
        }
        try validate(existing)
        guard try activate(existing) else {
            throw StartupFailure(reason: "target-identity", message: "已运行的 Codex 会话无法被确认激活。")
        }
        return .activated(pid: existing.pid)
    }
}

protocol StartupOperationLock: AnyObject {
    func release()
}

protocol StartupTargetSystem {
    func preflightBundle(_ bundle: URL, deadline: TimeInterval) throws
    func validate(_ target: StartupTargetFacts, deadline: TimeInterval) throws
    func listeningPorts(_ target: StartupTargetFacts, deadline: TimeInterval) throws -> [Int]
    func acquireOperationLock(pid: Int32) throws -> any StartupOperationLock
}

extension StartupTargetSystem {
    func validateProcess(_ target: StartupTargetFacts, deadline: TimeInterval) throws {
        try validate(target, deadline: deadline)
    }
}

final class WallpaperOperationLock: StartupOperationLock {
    private let descriptor: Int32
    private let stateLock = NSLock()
    private var released = false

    static func path(uid: UInt32, pid: Int32) -> String {
        URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("local.azhou.wallpaper-\(uid)-\(pid).lock").path
    }

    static func acquire(pid: Int32) throws -> WallpaperOperationLock {
        let descriptor = Darwin.open(path(uid: getuid(), pid: pid), O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, S_IRUSR | S_IWUSR)
        guard descriptor >= 0 else {
            throw WallpaperFailure(state: "busy", chinese: "该 Codex 进程已有壁纸或启动接入操作。", english: "A wallpaper or startup attachment operation is already active for this Codex process.")
        }
        guard flock(descriptor, LOCK_EX | LOCK_NB) == 0 else {
            close(descriptor)
            throw WallpaperFailure(state: "busy", chinese: "该 Codex 进程已有壁纸或启动接入操作。", english: "A wallpaper or startup attachment operation is already active for this Codex process.")
        }
        return WallpaperOperationLock(descriptor: descriptor)
    }

    private init(descriptor: Int32) { self.descriptor = descriptor }

    func release() {
        stateLock.lock()
        defer { stateLock.unlock() }
        guard !released else { return }
        released = true
        flock(descriptor, LOCK_UN)
        close(descriptor)
    }

    deinit { release() }
}

struct CodexStartupTargetSystem: StartupTargetSystem {
    private let environment: CodexTargetEnvironment

    init(environment: CodexTargetEnvironment = .live) { self.environment = environment }

    private func target(_ facts: StartupTargetFacts, deadline: TimeInterval? = nil) throws -> WallpaperTarget {
        guard facts.bundleID == "com.openai.codex" else {
            throw StartupFailure(reason: "target-identity", message: "目标 Bundle ID 与 Codex 不符。")
        }
        let target = try WallpaperTarget(pid: facts.pid, bundle: facts.bundle, launchTime: facts.launchTime,
                                         commandDeadline: deadline, environment: environment)
        guard target.executable == facts.executable else {
            throw StartupFailure(reason: "target-identity", message: "目标主可执行文件与核验路径不符。")
        }
        return target
    }

    func preflightBundle(_ bundle: URL, deadline: TimeInterval) throws {
        try StartupBundleSignature.verify(bundle, deadline: deadline, environment: environment)
    }

    func validate(_ facts: StartupTargetFacts, deadline: TimeInterval) throws {
        try target(facts, deadline: deadline).validateSignature(deadline: deadline)
    }

    func validateProcess(_ facts: StartupTargetFacts, deadline: TimeInterval) throws {
        try target(facts, deadline: deadline).validate(deadline: deadline)
    }

    func listeningPorts(_ facts: StartupTargetFacts, deadline: TimeInterval) throws -> [Int] {
        try target(facts, deadline: deadline).ports(deadline: deadline)
    }

    func acquireOperationLock(pid: Int32) throws -> any StartupOperationLock {
        try WallpaperOperationLock.acquire(pid: pid)
    }
}

protocol WallpaperTargetResolver {
    func resolveTarget(pid: Int32?, bundle: URL?, launchTime: TimeInterval?) throws -> StartupTargetFacts
}

extension CodexStartupTargetSystem: WallpaperTargetResolver {
    func resolveTarget(pid: Int32?, bundle: URL?, launchTime: TimeInterval?) throws -> StartupTargetFacts {
        let resolvedPID: Int32
        let resolvedBundle: URL
        let resolvedLaunchTime: TimeInterval?
        if pid == nil, bundle == nil, launchTime == nil {
            let candidates = environment.runningProcesses("com.openai.codex").filter { !$0.isTerminated }
            guard candidates.count == 1, let app = candidates.first, let appBundle = app.bundleURL else {
                throw WallpaperFailure(state: "target-unavailable", chinese: "未找到唯一的正在运行的 Codex；状态检查不会启动应用。", english: "Could not identify exactly one running Codex app; the status check will not launch it.")
            }
            resolvedPID = app.processIdentifier
            resolvedBundle = appBundle
            resolvedLaunchTime = app.launchDate?.timeIntervalSince1970
        } else {
            guard let pid, let bundle else {
                throw WallpaperFailure(state: "invalid-request", chinese: "壁纸操作需要明确的目标 PID 和绝对应用路径。", english: "A wallpaper action requires an explicit target PID and absolute app path.")
            }
            resolvedPID = pid
            resolvedBundle = bundle
            resolvedLaunchTime = launchTime
        }
        let target = try WallpaperTarget(pid: resolvedPID, bundle: resolvedBundle, launchTime: resolvedLaunchTime,
                                        environment: environment)
        return StartupTargetFacts(pid: target.pid, bundle: target.bundle, executable: target.executable,
                                  bundleID: "com.openai.codex", launchTime: target.launchDate?.timeIntervalSince1970)
    }
}

enum WallpaperCommand {
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
        if cancelled { throw WallpaperFailure(state: "cancelled", chinese: "壁纸任务已取消。", english: "The wallpaper task was cancelled.") }
        let process = Process(), pipe = Pipe(), stopped = DispatchSemaphore(value: 0)
        process.executableURL = URL(fileURLWithPath: file); process.arguments = arguments
        process.standardOutput = pipe; process.standardError = pipe
        process.terminationHandler = { _ in stopped.signal() }
        try process.run()
        state.lock.lock()
        if state.cancelled {
            state.lock.unlock(); if process.isRunning { kill(process.processIdentifier, SIGKILL) }
            throw WallpaperFailure(state: "cancelled", chinese: "壁纸任务已取消。", english: "The wallpaper task was cancelled.")
        }
        state.active.append(process); state.lock.unlock()
        defer { state.lock.lock(); state.active.removeAll { $0 === process }; state.lock.unlock() }
        if stopped.wait(timeout: .now() + timeout) == .timedOut {
            process.terminate()
            if stopped.wait(timeout: .now() + 0.2) == .timedOut { kill(process.processIdentifier, SIGKILL) }
            throw WallpaperFailure(state: "inspection-timeout", chinese: "目标进程核查超时；未继续连接壁纸。", english: "The target process inspection timed out; wallpaper was not connected.")
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard process.terminationStatus == 0 else {
            if process.terminationStatus == emptyExit { return "" }
            throw WallpaperFailure(state: "inspection-failed", chinese: "目标进程或签名核查未通过。", english: "The target process or signature did not pass verification.")
        }
        return String(data: data, encoding: .utf8) ?? ""
    }
}

protocol StartupTransport: AnyObject {
    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]]
    func connect(to url: URL, timeout: TimeInterval) throws
    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any]
    func close()
}

final class StartupCDPRequestState {
    private let lock = NSLock()
    private var serial = 0
    private var pending = false

    func begin() throws -> Int {
        lock.lock()
        defer { lock.unlock() }
        guard !pending, serial < Int.max else {
            throw StartupFailure(reason: "protocol-error", message: "CDP 只允许一个待处理请求，且请求序号不可耗尽。")
        }
        pending = true
        serial += 1
        return serial
    }

    func finish() {
        lock.lock()
        pending = false
        lock.unlock()
    }
}

enum StartupCDPReply {
    case event
    case result([String: Any])
}

enum StartupCDPProtocol {
    static func decode(_ data: Data, expectedID: Int) throws -> StartupCDPReply {
        guard data.count <= 2 * 1024 * 1024,
              let answer = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw StartupFailure(reason: "protocol-error", message: "CDP 返回了无效或超限消息。")
        }
        guard let responseID = answer["id"] else {
            guard answer["method"] is String else {
                throw StartupFailure(reason: "protocol-error", message: "CDP 返回了无法识别的事件。")
            }
            return .event
        }
        guard integer(responseID) == expectedID else {
            throw StartupFailure(reason: "protocol-error", message: "CDP 响应序号与当前待处理请求不匹配。")
        }
        guard answer["error"] == nil,
              let result = answer["result"] as? [String: Any],
              result["exceptionDetails"] == nil,
              let value = (result["result"] as? [String: Any])?["value"] as? [String: Any] else {
            throw StartupFailure(reason: "protocol-error", message: "Codex 页面没有返回有效的启动协议结果。")
        }
        return .result(value)
    }

    private static func integer(_ value: Any?) -> Int? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let value = number.doubleValue
        guard value.isFinite, value.rounded() == value, value >= 0, value <= Double(Int.max) else { return nil }
        return number.intValue
    }
}

protocol WallpaperPageSession: AnyObject {
    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any]
    func close()
}

protocol WallpaperOperationTransport: AnyObject {
    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]]
    func pageSession(_ url: URL) -> any WallpaperPageSession
    func close()
}

protocol WallpaperSocketTask: AnyObject {
    var maximumMessageSize: Int { get set }
    func resume()
    func send(_ message: URLSessionWebSocketTask.Message) async throws
    func receive() async throws -> URLSessionWebSocketTask.Message
    func cancel(with closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?)
}

extension URLSessionWebSocketTask: WallpaperSocketTask {}

private final class URLSessionWallpaperPageSession: WallpaperPageSession {
    private let transport: WallpaperTransport
    private let socket: any WallpaperSocketTask
    init(transport: WallpaperTransport, socket: any WallpaperSocketTask) {
        self.transport = transport
        self.socket = socket
    }
    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        try await transport.evaluate(source, on: socket, timeout: timeout)
    }
    func close() { socket.cancel(with: .normalClosure, reason: nil) }
}

final class WallpaperTransport: NSObject, URLSessionTaskDelegate, StartupTransport, WallpaperOperationTransport, @unchecked Sendable {
    private let sessionOverride: URLSession?
    private let socketFactory: ((URLRequest) -> any WallpaperSocketTask)?
    private lazy var session: URLSession = {
        if let sessionOverride { return sessionOverride }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil; configuration.httpCookieStorage = nil; configuration.urlCredentialStorage = nil
        configuration.httpShouldSetCookies = false
        configuration.connectionProxyDictionary = [
            kCFNetworkProxiesHTTPEnable as String: 0,
            kCFNetworkProxiesHTTPSEnable as String: 0,
            kCFNetworkProxiesSOCKSEnable as String: 0,
            kCFNetworkProxiesProxyAutoConfigEnable as String: 0,
            kCFNetworkProxiesProxyAutoDiscoveryEnable as String: 0,
        ]
        configuration.timeoutIntervalForRequest = 2; configuration.timeoutIntervalForResource = 30
        return URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
    }()
    private var serial = 0
    private var startupSocket: (any WallpaperSocketTask)?
    private let startupRequests = StartupCDPRequestState()
    override convenience init() { self.init(session: nil, socketFactory: nil) }
    init(session: URLSession?, socketFactory: ((URLRequest) -> any WallpaperSocketTask)? = nil) {
        sessionOverride = session
        self.socketFactory = socketFactory
        super.init()
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
    func close() {
        startupSocket?.cancel(with: .normalClosure, reason: nil)
        startupSocket = nil
        session.invalidateAndCancel()
    }
    func pages(port: Int) async throws -> [[String: Any]] {
        try await pages(port: port, timeout: 2)
    }
    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        let url = URL(string: "http://127.0.0.1:\(port)/json/list")!
        var request = URLRequest(url: url); request.cachePolicy = .reloadIgnoringLocalCacheData; request.timeoutInterval = timeout
        let data: Data
        let response: URLResponse
        do { (data, response) = try await session.data(for: request) }
        catch let error as CancellationError { throw error }
        catch { throw WallpaperFailure(state: "endpoint-unavailable", chinese: "本机 Codex 调试端口暂时没有响应。", english: "The local Codex debugging port did not respond.") }
        guard let response = response as? HTTPURLResponse, response.statusCode == 200, response.url == url,
              data.count < 2 * 1024 * 1024,
              let entries = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw WallpaperFailure(state: "endpoint-unavailable", chinese: "该本机端口没有返回有效的页面调试列表。", english: "The local port did not return a valid page debugging list.")
        }
        return entries.filter(WallpaperValidation.mainPage)
    }
    private func socketTask(for request: URLRequest) -> any WallpaperSocketTask {
        let task = socketFactory?(request) ?? session.webSocketTask(with: request)
        task.maximumMessageSize = 2 * 1024 * 1024
        task.resume()
        return task
    }
    func socket(_ url: URL) -> any WallpaperSocketTask {
        // The 2s HTTP-list timeout must not cut off the renderer's bounded 4s
        // image decode. Each CDP exchange still has its own 6s cancellation.
        var request = URLRequest(url: url); request.timeoutInterval = 30
        return socketTask(for: request)
    }
    func pageSession(_ url: URL) -> any WallpaperPageSession {
        URLSessionWallpaperPageSession(transport: self, socket: socket(url))
    }
    func connect(to url: URL, timeout: TimeInterval) throws {
        guard startupSocket == nil, timeout > 0 else {
            throw StartupFailure(reason: "protocol-error", message: "本次启动只允许一个已核验页面连接。")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = min(30, timeout)
        startupSocket = socketTask(for: request)
    }

    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        let id = try startupRequests.begin()
        defer { startupRequests.finish() }
        guard let socket = startupSocket, timeout > 0 else {
            throw StartupFailure(reason: "protocol-error", message: "启动页面连接不可用。")
        }
        let timeoutMilliseconds = try StartupBudget.requestTimeoutMilliseconds(min(timeout, 10))
        let request: [String: Any] = ["id": id, "method": "Runtime.evaluate", "params": [
            "expression": source, "returnByValue": true, "awaitPromise": true,
            "userGesture": false, "timeout": timeoutMilliseconds]]
        let data = try JSONSerialization.data(withJSONObject: request)
        let expired = StartupTimeoutFlag()
        let timeoutWork = DispatchWorkItem {
            expired.set()
            socket.cancel(with: .goingAway, reason: nil)
        }
        DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: timeoutWork)
        defer { timeoutWork.cancel() }
        do {
            try await socket.send(.string(String(decoding: data, as: UTF8.self)))
            while true {
                let message = try await socket.receive()
                let incoming: Data
                switch message {
                case .string(let text): incoming = Data(text.utf8)
                case .data(let bytes): incoming = bytes
                @unknown default: throw StartupFailure(reason: "protocol-error", message: "CDP 返回了未知消息类型。")
                }
                switch try StartupCDPProtocol.decode(incoming, expectedID: id) {
                case .event: continue
                case .result(let value): return value
                }
            }
        } catch let failure as StartupFailure {
            throw failure
        } catch {
            throw StartupFailure(reason: expired.get() ? "attach-timeout" : "protocol-error",
                                 message: expired.get() ? "CDP 请求超过本轮剩余时间。" : "CDP 连接或消息交换失败。")
        }
    }

    func evaluate(_ source: String, on socket: any WallpaperSocketTask, timeout: TimeInterval = 5) async throws -> [String: Any] {
        serial += 1; let id = serial
        let request: [String: Any] = ["id": id, "method": "Runtime.evaluate", "params": [
            "expression": source, "returnByValue": true, "awaitPromise": true, "userGesture": false, "timeout": Int(timeout * 1000)]]
        let data = try JSONSerialization.data(withJSONObject: request)
        let cancellation = DispatchWorkItem { socket.cancel(with: .goingAway, reason: nil) }
        DispatchQueue.global().asyncAfter(deadline: .now() + timeout + 1, execute: cancellation)
        defer { cancellation.cancel() }
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
                let failure = category ?? "renderer-exception"
                throw WallpaperFailure(
                    state: pending ? "renderer-not-ready" : "renderer-rejected",
                    chinese: pending ? "Codex 主界面尚未准备好，正在有限等待。" : "壁纸脚本未通过页面验证：\(failure)。",
                    english: pending ? "The Codex main window is not ready; waiting briefly." : "The wallpaper script failed page verification: \(failure)."
                )
            }
            guard answer["error"] == nil, let result = answer["result"] as? [String: Any],
                  let value = (result["result"] as? [String: Any])?["value"] as? [String: Any] else {
                throw WallpaperFailure(state: "renderer-rejected", chinese: "Codex 页面没有确认壁纸操作；未标记应用成功。", english: "The Codex page did not confirm the wallpaper operation; it was not marked as applied.")
            }
            return value
        }
    }
}

private final class StartupTimeoutFlag {
    private let lock = NSLock()
    private var expired = false
    func set() { lock.lock(); expired = true; lock.unlock() }
    func get() -> Bool { lock.lock(); defer { lock.unlock() }; return expired }
}

private struct StartupStatus {
    let runID: Int
    let phase: String
    let ready: Bool
    let completed: Bool
    let overlay: Bool
    let reason: String
    let completionCause: String?
    let completionBeforeReady: Bool?

    static func parse(_ value: Any?) -> StartupStatus? {
        guard let raw = value as? [String: Any],
              raw["owner"] as? String == "azhou-codex-startup",
              integer(raw["version"]) == 1,
              let phase = raw["phase"] as? String,
              ["loading", "playing", "settings", "complete", "failed", "timeout", "disposed"].contains(phase),
              let runID = integer(raw["runId"]), runID > 0,
              let ready = boolean(raw["ready"]),
              let completed = boolean(raw["completed"]),
              let overlay = boolean(raw["overlay"]),
              let reason = raw["reason"] as? String,
              reason.isEmpty || validReasons.contains(reason),
              let wallpaper = raw["wallpaper"] as? [String: Any],
              boolean(wallpaper["applied"]) != nil,
              let wallpaperReason = wallpaper["reason"] as? String,
              wallpaperReason.isEmpty || validReasons.contains(wallpaperReason),
              boolean(wallpaper["imageDecoded"]) != nil,
              let completionRaw = raw["completion"] else { return nil }
        let completionCause: String?
        let completionBeforeReady: Bool?
        if completionRaw is NSNull {
            completionCause = nil
            completionBeforeReady = nil
        } else {
            guard let completion = completionRaw as? [String: Any],
                  let cause = completion["cause"] as? String,
                  ["natural", "skip", "settings-cancel", "settings-save"].contains(cause),
                  let beforeReady = boolean(completion["beforeReady"]) else { return nil }
            completionCause = cause
            completionBeforeReady = beforeReady
        }
        guard completed == (completionCause != nil) else { return nil }
        switch phase {
        case "loading": guard !ready, !completed, overlay else { return nil }
        case "playing": guard ready, !completed, overlay else { return nil }
        case "settings": guard ready, !completed, overlay else { return nil }
        case "complete": guard completed, !overlay else { return nil }
        case "failed", "timeout": guard !overlay, !reason.isEmpty else { return nil }
        case "disposed": guard !overlay else { return nil }
        default: return nil
        }
        return StartupStatus(runID: runID, phase: phase, ready: ready, completed: completed,
                             overlay: overlay, reason: reason, completionCause: completionCause,
                             completionBeforeReady: completionBeforeReady)
    }

    private static let validReasons: Set<String> = [
        "target-missing", "target-identity", "listener-mismatch", "page-pending", "page-unsupported",
        "owner-conflict", "protocol-error", "attach-timeout", "asset-invalid", "storage-unavailable",
        "wallpaper-unsupported", "overlay-timeout", "ambiguous-main-page", "startup-active",
        "startup-interrupted", "settings-conflict", "operation-timeout"
    ]

    private static func integer(_ value: Any?) -> Int? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let value = number.doubleValue
        guard value.isFinite, value.rounded() == value, value >= 0, value <= Double(Int.max) else { return nil }
        return number.intValue
    }

    private static func boolean(_ value: Any?) -> Bool? {
        guard let number = value as? NSNumber, CFGetTypeID(number) == CFBooleanGetTypeID() else { return nil }
        return number.boolValue
    }
}

struct StartupConnector {
    let target: StartupTargetFacts
    let expectedPort: Int
    let system: any StartupTargetSystem
    let transport: any StartupTransport
    let now: () -> TimeInterval
    let sleep: (TimeInterval) async throws -> Void

    init(
        target: StartupTargetFacts,
        expectedPort: Int,
        system: any StartupTargetSystem,
        transport: any StartupTransport,
        now: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime },
        sleep: @escaping (TimeInterval) async throws -> Void = { seconds in
            try await Task.sleep(nanoseconds: UInt64(max(0, seconds) * 1_000_000_000))
        }
    ) {
        self.target = target
        self.expectedPort = expectedPort
        self.system = system
        self.transport = transport
        self.now = now
        self.sleep = sleep
    }

    func run(payload: String, deadline: TimeInterval) async -> StartupOutcome {
        do { return try await attach(payload: payload, deadline: deadline) }
        catch let error as StartupFailure { return .failed(reason: error.reason) }
        catch let error as WallpaperFailure {
            if error.state == "busy" { return .partial(reason: "startup-active") }
            if error.state == "inspection-timeout" { return .failed(reason: "attach-timeout") }
            if ["target-mismatch", "target-changed", "signature-refused"].contains(error.state) {
                return .failed(reason: "target-identity")
            }
            return .failed(reason: "protocol-error")
        } catch { return .failed(reason: "protocol-error") }
    }

    private func attach(payload: String, deadline: TimeInterval) async throws -> StartupOutcome {
        defer { transport.close() }
        func requireBudget() throws {
            guard now() < deadline else {
                throw StartupFailure(reason: "attach-timeout", message: "Codex 启动接入超过阶段或总预算。")
            }
        }
        guard (1...65535).contains(expectedPort), !payload.isEmpty,
              payload.utf8.count < 24 * 1024 * 1024 else {
            throw StartupFailure(reason: "asset-invalid", message: "缺少有效的本地启动载荷。")
        }
        let operationLock = try system.acquireOperationLock(pid: target.pid)
        defer { operationLock.release() }
        try requireBudget()
        try system.validate(target, deadline: deadline)
        try requireBudget()
        guard try system.listeningPorts(target, deadline: deadline).contains(expectedPort) else {
            throw StartupFailure(reason: "listener-mismatch", message: "指定调试端口不属于已核验的 Codex 主进程。")
        }
        try requireBudget()

        var selectedPage: [String: Any]?
        while now() < deadline {
            try requireBudget()
            guard try system.listeningPorts(target, deadline: deadline).contains(expectedPort) else {
                throw StartupFailure(reason: "listener-mismatch", message: "Codex 调试端口归属已变化。")
            }
            try requireBudget()
            let remaining = deadline - now()
            guard remaining > 0 else { break }
            let pages: [[String: Any]]
            do { pages = try await transport.pages(port: expectedPort, timeout: min(1.2, remaining)) }
            catch let error as WallpaperFailure where error.state == "endpoint-unavailable" {
                try await sleep(min(0.15, max(0, deadline - now())))
                continue
            }
            let mainPages = pages.filter(WallpaperValidation.mainPage)
            guard mainPages.count <= 1 else {
                throw StartupFailure(reason: "ambiguous-main-page", message: "找到多个 Codex 主页面，本次启动接入已拒绝。")
            }
            if let page = mainPages.first { selectedPage = page; break }
            try await sleep(min(0.15, max(0, deadline - now())))
        }
        guard let page = selectedPage else {
            throw StartupFailure(reason: now() >= deadline ? "attach-timeout" : "page-pending",
                                 message: "在本轮预算内未找到唯一的 Codex 主页面。")
        }
        guard let rawSocket = page["webSocketDebuggerUrl"] as? String else {
            throw StartupFailure(reason: "page-unsupported", message: "Codex 主页面没有可核验的调试连接。")
        }
        let pageSocket = try WallpaperValidation.pageSocket(rawSocket, port: expectedPort)
        try system.validate(target, deadline: deadline)
        try requireBudget()
        guard try system.listeningPorts(target, deadline: deadline).contains(expectedPort) else {
            throw StartupFailure(reason: "listener-mismatch", message: "选中主页面后调试端口归属已变化。")
        }
        try requireBudget()
        try transport.connect(to: pageSocket, timeout: min(5, deadline - now()))

        let inspected = try await transport.evaluate(Self.inspectExpression, timeout: min(10, deadline - now()))
        guard let href = inspected["href"] as? String,
              WallpaperValidation.mainPage(["type": "page", "url": href]),
              let controllerPresent = Self.boolean(inspected["controllerPresent"]) else {
            throw StartupFailure(reason: "page-unsupported", message: "Codex 主页面在建立连接后已导航或不受支持。")
        }
        guard !controllerPresent else {
            return .partial(reason: "startup-active")
        }
        try system.validate(target, deadline: deadline)
        try requireBudget()
        guard try system.listeningPorts(target, deadline: deadline).contains(expectedPort) else {
            throw StartupFailure(reason: "listener-mismatch", message: "发送启动载荷前调试端口归属已变化。")
        }
        try requireBudget()
        let install = try await transport.evaluate(try Self.installExpression(payload, expectedHref: href), timeout: min(10, deadline - now()))
        guard let installed = Self.boolean(install["installed"]) else {
            throw StartupFailure(reason: "protocol-error", message: "启动载荷没有返回有效安装结果。")
        }
        guard installed else {
            let reportedReason = install["reason"] as? String
            let reason = reportedReason.flatMap { value in
                ["owner-conflict", "page-unsupported", "asset-invalid", "storage-unavailable"].contains(value) ? value : nil
            } ?? "protocol-error"
            throw StartupFailure(reason: reason, message: "页面没有安装有效的启动控制器，本次未继续。")
        }
        guard let alreadyActive = Self.boolean(install["alreadyActive"]) else {
            await disposeOwnedController(href: href, deadline: deadline)
            throw StartupFailure(reason: "protocol-error", message: "启动载荷没有返回有效安装状态。")
        }
        guard !alreadyActive else { return .partial(reason: "startup-active") }

        var runID: Int?
        do {
            while now() < deadline {
                let remaining = deadline - now()
                guard remaining > 0 else { break }
                let response = try await transport.evaluate(Self.statusExpression, timeout: min(10, remaining))
                guard response["href"] as? String == href else {
                    return .partial(reason: "startup-interrupted")
                }
                guard let missing = Self.boolean(response["missing"]) else {
                    throw StartupFailure(reason: "protocol-error", message: "页面没有返回有效的控制器状态标记。")
                }
                if missing { return .partial(reason: "startup-interrupted") }
                guard let status = StartupStatus.parse(response["status"]) else {
                    throw StartupFailure(reason: "protocol-error", message: "启动控制器状态不符合协议 Schema。")
                }
                if let runID, status.runID != runID { return .partial(reason: "startup-interrupted") }
                if runID == nil { runID = status.runID }
                if status.phase == "failed" || status.phase == "timeout" {
                    return .failed(reason: status.reason)
                }
                if status.completionCause == "skip", status.completed, !status.overlay {
                    return .skipped(runID: status.runID, beforeReady: status.completionBeforeReady ?? false)
                }
                if status.ready, ["playing", "settings", "complete"].contains(status.phase) {
                    return .ready(runID: status.runID)
                }
                if status.phase == "disposed" { return .partial(reason: "startup-interrupted") }
                try await sleep(min(0.1, max(0, deadline - now())))
            }
        } catch {
            await disposeOwnedController(href: href, deadline: deadline)
            throw error
        }
        return .failed(reason: "attach-timeout")
    }

    private func disposeOwnedController(href: String, deadline: TimeInterval) async {
        guard now() < deadline else { return }
        do {
            try system.validate(target, deadline: deadline)
            guard now() < deadline,
                  try system.listeningPorts(target, deadline: deadline).contains(expectedPort),
                  now() < deadline else { return }
            let timeout = try StartupBudget.boundedTimeout(maximum: 2, stageDeadline: deadline,
                                                           totalDeadline: deadline, now: now())
            _ = try await transport.evaluate(try Self.disposeExpression(href), timeout: timeout)
        } catch { /* Cleanup is best effort and never delays closing past the budget. */ }
    }

    static let inspectExpression = """
    (() => { const d = Object.getOwnPropertyDescriptor(globalThis, '__azhouStartup'); return {href: location.href, controllerPresent: Boolean(d)}; })()
    """
    static let statusExpression = """
    (() => { const href = location.href; const d = Object.getOwnPropertyDescriptor(globalThis, '__azhouStartup'); if (!d || !("value" in d) || !d.value || typeof d.value.status !== "function") return {href, missing: true}; return {href, missing: false, status: d.value.status()}; })()
    """

    static func disposeExpression(_ href: String) throws -> String {
        let encoded = try JSONSerialization.data(withJSONObject: [href])
        let array = String(decoding: encoded, as: UTF8.self)
        guard array.first == "[", array.last == "]" else {
            throw StartupFailure(reason: "protocol-error", message: "当前页面无法安全验证启动控制器。")
        }
        let literal = String(array.dropFirst().dropLast())
        return """
        (() => { if (location.href !== \(literal)) return {disposed:false}; const d = Object.getOwnPropertyDescriptor(globalThis, '__azhouStartup'); if (!d || !("value" in d) || !d.value) return {disposed:false}; const api = d.value; const owner = Object.getOwnPropertyDescriptor(api, 'owner'); const version = Object.getOwnPropertyDescriptor(api, 'version'); const dispose = Object.getOwnPropertyDescriptor(api, 'dispose'); if (owner?.value !== 'azhou-codex-startup' || version?.value !== 1 || typeof dispose?.value !== 'function') return {disposed:false}; return dispose.value.call(api); })()
        """
    }

    static func installExpression(_ payload: String, expectedHref: String) throws -> String {
        // The trusted builder emits one self-contained installer expression;
        // keep it inside the single bounded CDP evaluation instead of reparsing it.
        let encoded = try JSONSerialization.data(withJSONObject: [expectedHref])
        let array = String(decoding: encoded, as: UTF8.self)
        guard array.first == "[", array.last == "]" else {
            throw StartupFailure(reason: "protocol-error", message: "当前页面地址无法安全编码。")
        }
        let literal = String(array.dropFirst().dropLast())
        return """
        (() => { if (location.href !== \(literal)) return {installed: false, alreadyActive: false, reason: 'page-unsupported'}; return Promise.resolve((\(payload))).then(result => result); })()
        """
    }

    private static func boolean(_ value: Any?) -> Bool? {
        guard let number = value as? NSNumber, CFGetTypeID(number) == CFBooleanGetTypeID() else { return nil }
        return number.boolValue
    }
}

struct WallpaperRequest: Sendable {
    let action: WallpaperAction, target: StartupTargetFacts, port: Int?, cold: Bool, requestID: String
    init(_ arguments: [String], resolver: any WallpaperTargetResolver) throws {
        func option(_ name: String) -> String? {
            guard let index = arguments.firstIndex(of: name), index + 1 < arguments.count else { return nil }
            return arguments[index + 1]
        }
        let shortcut = arguments.contains("--wallpaper-status")
        guard let action = WallpaperAction(rawValue: shortcut ? "status" : option("--action") ?? "apply") else {
            throw WallpaperFailure(state: "invalid-request", chinese: "壁纸操作必须为 apply、retry、doctor、status 或 restore。", english: "The wallpaper action must be apply, retry, doctor, status, or restore.")
        }
        let suppliedPID = option("--target-pid")
        let suppliedBundle = option("--target-bundle")
        let launchTime = option("--target-start-time").flatMap(Double.init)
        let target: StartupTargetFacts
        if shortcut, suppliedPID == nil, suppliedBundle == nil {
            target = try resolver.resolveTarget(pid: nil, bundle: nil, launchTime: nil)
        } else {
            guard let textPID = suppliedPID, let pid = Int32(textPID), pid > 0,
                  let path = suppliedBundle, path.hasPrefix("/") else {
                throw WallpaperFailure(state: "invalid-request", chinese: "壁纸操作需要明确的目标 PID 和绝对应用路径。", english: "A wallpaper action requires an explicit target PID and absolute app path.")
            }
            target = try resolver.resolveTarget(pid: pid, bundle: URL(fileURLWithPath: path), launchTime: launchTime)
        }
        if let rawPort = option("--port") {
            guard suppliedPID != nil, let value = Int(rawPort), (1...65535).contains(value) else {
                throw WallpaperFailure(state: "invalid-request", chinese: "指定端口时必须同时指定并核实目标 PID；端口范围为 1–65535。", english: "When specifying a port, also specify and verify the target PID; the port range is 1–65535.")
            }
            port = value
        } else { port = nil }
        self.action = action; self.target = target
        self.cold = arguments.contains("--cold"); self.requestID = option("--request-id") ?? UUID().uuidString
    }
}

enum WallpaperCLI {
    // The page's retry settles within 10s; transport gets 1s to return its receipt.
    static let retryEvaluationTimeout: TimeInterval = 11
    static func handles(_ arguments: [String]) -> Bool { arguments.contains("--wallpaper-helper") || arguments.contains("--wallpaper-status") }
    static func exitCode(for state: String) -> Int32 {
        ["applied", "restored", "ready"].contains(state) ? 0 : 2
    }
    static var restoreMessage: String {
        WallpaperMessages.localized(
            chinese: "已移除本页启动美化及设置入口；已保存值保留；Codex 与调试端口保持原状态。",
            english: "Removed startup decoration and settings entry from this page. Saved values were preserved. Codex and its debug port were left unchanged."
        )
    }
    static let statusSource = """
    (() => { const u = new URL(location.href);
      if (window.top !== window || u.protocol !== 'app:' || u.hostname !== '-' || u.pathname !== '/index.html'
          || /avatar|quick.?chat|detached|mini|popover|notification/i.test(u.searchParams.get('initialRoute') || '/')) return {applied:false,imageDecoded:false,matchedSurfaces:0,backgroundMatched:false,reason:'wrong-page',startup:{installed:false}};
      const value=(object,key)=>{const d=object&&Object.getOwnPropertyDescriptor(object,key);return d&&Object.hasOwn(d,'value')?d.value:undefined;};
      const wallpaperDescriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouWallpaper');
      const wallpaper=wallpaperDescriptor&&Object.hasOwn(wallpaperDescriptor,'value')?wallpaperDescriptor.value:null;
      let result={applied:false,imageDecoded:false,matchedSurfaces:0,backgroundMatched:false,reason:wallpaperDescriptor?'owner-conflict':'not-installed'};
      if(wallpaper&&value(wallpaper,'owner')==='azhou.codex-startup-animation'&&['0.7.1','0.8.0','0.9.0'].includes(value(wallpaper,'version'))&&typeof value(wallpaper,'status')==='function'){
        try{const state=value(wallpaper,'status').call(wallpaper);if(state&&typeof state==='object'&&typeof state.applied==='boolean')result=state;}
        catch{result={applied:false,imageDecoded:false,matchedSurfaces:0,backgroundMatched:false,reason:'owner-conflict'};}
      }
      const startupDescriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouStartup');
      const api=startupDescriptor&&Object.hasOwn(startupDescriptor,'value')?startupDescriptor.value:null;
      let startup={installed:false};
      if(api&&value(api,'owner')==='azhou-codex-startup'&&value(api,'version')===1&&typeof value(api,'status')==='function'){
        try{
          const state=value(api,'status').call(api);
          if(state&&state.owner==='azhou-codex-startup'&&state.version===1&&typeof state.phase==='string'&&Number.isSafeInteger(state.runId)
            &&typeof state.ready==='boolean'&&typeof state.completed==='boolean'&&typeof state.overlay==='boolean'){
            const completion=state.completion;
            const validCompletion=completion===null||(completion&&['natural','skip','settings-cancel','settings-save'].includes(completion.cause)&&typeof completion.beforeReady==='boolean');
            startup={installed:true,owner:state.owner,version:state.version,phase:state.phase,runId:state.runId,
              ready:state.ready,completed:state.completed,overlay:state.overlay,completion:validCompletion?completion:null};
            const failure=value(state,'wallpaper');
            if(failure&&value(failure,'applied')===false){
              const code=value(failure,'failureCode');
              if(typeof code==='string'){result.applied=false;result.failureCode=code;}
            }
          }
        } catch {}
      }
      result.startup=startup;
      return result;
    })()
    """
    static let applyGuardSource = """
    (() => {
      const value=(object,key)=>{const d=object&&Object.getOwnPropertyDescriptor(object,key);return d&&Object.hasOwn(d,'value')?d.value:undefined;};
      const startupDescriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouStartup');
      if(startupDescriptor){
        const api=Object.hasOwn(startupDescriptor,'value')?startupDescriptor.value:null;
        if(api&&value(api,'owner')==='azhou-codex-startup'&&value(api,'version')===1&&typeof value(api,'status')==='function')return {state:'startup-active',applied:false};
        return {state:'owner-conflict',applied:false};
      }
      const wallpaperDescriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouWallpaper');
      if(wallpaperDescriptor){
        const api=Object.hasOwn(wallpaperDescriptor,'value')?wallpaperDescriptor.value:null;
        if(!api||value(api,'owner')!=='azhou.codex-startup-animation'||!['0.7.1','0.8.0','0.9.0'].includes(value(api,'version'))
          ||typeof value(api,'status')!=='function'||typeof value(api,'dispose')!=='function')return {state:'owner-conflict',applied:false};
      }
      return {state:'ready',applied:false};
    })()
    """
    static let retrySource = """
    (async () => {
      const u=new URL(location.href);
      if(window.top!==window||u.protocol!=='app:'||u.hostname!=='-'||u.pathname!=='/index.html'
        ||/avatar|quick.?chat|detached|mini|popover|notification/i.test(u.searchParams.get('initialRoute')||'/'))return {state:'owner-conflict',applied:false};
      const value=(object,key)=>{const d=object&&Object.getOwnPropertyDescriptor(object,key);return d&&Object.hasOwn(d,'value')?d.value:undefined;};
      const descriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouStartup');
      if(!descriptor)return {state:'retry-unavailable',applied:false};
      const api=Object.hasOwn(descriptor,'value')?descriptor.value:null;
      if(!api||value(api,'owner')!=='azhou-codex-startup'||value(api,'version')!==1
        ||typeof value(api,'status')!=='function')return {state:'owner-conflict',applied:false};
      const retry=value(api,'retryWallpaper');
      if(typeof retry!=='function')return {state:'retry-unavailable',applied:false};
      try{return await retry.call(api);}catch{return {state:'retry-failed',applied:false};}
    })()
    """
    static let restoreSource = """
    (() => { const u = new URL(location.href);
      if (window.top !== window || u.protocol !== 'app:' || u.hostname !== '-' || u.pathname !== '/index.html'
          || /avatar|quick.?chat|detached|mini|popover|notification/i.test(u.searchParams.get('initialRoute') || '/')) return {restored:false,reason:'wrong-page'};
      const value=(object,key)=>{const d=object&&Object.getOwnPropertyDescriptor(object,key);return d&&Object.hasOwn(d,'value')?d.value:undefined;};
      const startupDescriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouStartup');
      if(startupDescriptor){
        const api=Object.hasOwn(startupDescriptor,'value')?startupDescriptor.value:null;
        if(!api||value(api,'owner')!=='azhou-codex-startup'||value(api,'version')!==1
          ||typeof value(api,'dispose')!=='function'||typeof value(api,'status')!=='function')return {restored:false,reason:'owner-conflict'};
        try{const result=value(api,'dispose').call(api);const state=value(api,'status').call(api);
          return {restored:result?.disposed===true&&state?.phase==='disposed',applied:false,startup:true};}
        catch{return {restored:false,reason:'owner-conflict'};}
      }
      const wallpaperDescriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouWallpaper');
      if(!wallpaperDescriptor)return {restored:true,applied:false};
      const api=Object.hasOwn(wallpaperDescriptor,'value')?wallpaperDescriptor.value:null;
      if(!api||value(api,'owner')!=='azhou.codex-startup-animation'||!['0.7.1','0.8.0','0.9.0'].includes(value(api,'version'))
        ||typeof value(api,'dispose')!=='function'||typeof value(api,'status')!=='function')return {restored:false,reason:'owner-conflict'};
      try{value(api,'dispose').call(api);const state=value(api,'status').call(api);
        return {restored:state?.applied===false,applied:state?.applied===true};}
      catch{return {restored:false,reason:'restore-failed'};}
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
        let system = CodexStartupTargetSystem()
        return run(
            arguments, resolver: system, system: system, transportFactory: { WallpaperTransport() },
            now: { ProcessInfo.processInfo.systemUptime },
            expectedVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "",
            sourceLoader: packagedWallpaperSource,
            sleep: { seconds in try await Task.sleep(nanoseconds: UInt64(max(0, seconds) * 1_000_000_000)) },
            journal: { WallpaperJournal.record($0) },
            output: { data in try? FileHandle.standardOutput.write(contentsOf: data) }
        )
    }

    static func run(
        _ arguments: [String],
        resolver: any WallpaperTargetResolver,
        system: any StartupTargetSystem,
        transportFactory: @escaping () -> any WallpaperOperationTransport,
        now: @escaping () -> TimeInterval,
        expectedVersion: String,
        sourceLoader: @escaping () throws -> String,
        sleep: @escaping (TimeInterval) async throws -> Void,
        journal: ([String: Any]) -> Void,
        output: (Data) -> Void
    ) -> Int32 {
        WallpaperMessages.prepareForRun()
        let began = now()
        var action = arguments.contains("--wallpaper-status") ? "status" : "apply"
        if !arguments.contains("--wallpaper-status"), let index = arguments.firstIndex(of: "--action"), index + 1 < arguments.count { action = arguments[index + 1] }
        var base: [String: Any] = ["event": "wallpaper-result", "action": action, "applied": false,
                                  "helperPID": Int(getpid()), "deadlineSeconds": 30,
                                  "version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""]
        let completion = Completion()
        // User cancellation stops only this helper and its own inspection tools.
        signal(SIGTERM, SIG_IGN)
        let cancellation = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .global())
        cancellation.setEventHandler { completion.finish(["state": "cancelled", "applied": false, "message": WallpaperMessages.localized(chinese: "本次壁纸任务已取消；Codex 保持运行。", english: "This wallpaper task was cancelled; Codex remains running.")]) }
        cancellation.resume()
        // The process itself returns after this deadline, even if an OS request
        // stops responding. No timer or detached worker survives process exit.
        let timeout = DispatchWorkItem { completion.finish(["state": "timeout", "applied": false, "message": WallpaperMessages.localized(chinese: "壁纸连接超过 30 秒，已停止；Codex 保持运行。", english: "The wallpaper connection exceeded 30 seconds and stopped; Codex remains running.")]) }
        DispatchQueue.global().asyncAfter(deadline: .now() + 30, execute: timeout)
        let task = Task.detached {
            do {
                let request = try WallpaperRequest(arguments, resolver: resolver)
                var result: [String: Any]
                do {
                    result = try await perform(
                        request, began: began, system: system, transport: transportFactory(),
                        now: now, expectedVersion: expectedVersion, sourceLoader: sourceLoader, sleep: sleep
                    )
                }
                catch let error as WallpaperFailure { result = ["state": error.state, "applied": false, "message": error.message] }
                catch { result = ["state": "connection-failed", "applied": false, "message": WallpaperMessages.localized(chinese: "壁纸连接未完成；Codex 保持运行。", english: "The wallpaper connection did not finish; Codex remains running.")] }
                result["targetPID"] = Int(request.target.pid); result["targetPath"] = request.target.bundle.path
                result["requestID"] = request.requestID; result["action"] = request.action.rawValue
                completion.finish(result)
            } catch let error as WallpaperFailure { completion.finish(["state": error.state, "applied": false, "message": error.message]) }
            catch { completion.finish(["state": "invalid-request", "applied": false, "message": WallpaperMessages.localized(chinese: "无法核实壁纸操作目标。", english: "Could not verify the wallpaper operation target.")]) }
        }
        completion.signal.wait(); timeout.cancel(); task.cancel(); cancellation.cancel(); WallpaperCommand.cancelAll()
        base.merge(completion.result()) { _, value in value }
        if base["requestID"] == nil, let index = arguments.firstIndex(of: "--request-id"), index + 1 < arguments.count { base["requestID"] = arguments[index + 1] }
        base["seconds"] = ((ProcessInfo.processInfo.systemUptime - began) * 1000).rounded() / 1000
        base["timestamp"] = ISO8601DateFormatter().string(from: Date())
        if action == "apply" || action == "retry" || action == "restore" { journal(base) }
        if let data = try? JSONSerialization.data(withJSONObject: base, options: [.sortedKeys, .withoutEscapingSlashes]) {
            output(data + Data([10]))
        }
        return exitCode(for: base["state"] as? String ?? "")
    }

    private static func packagedWallpaperSource() throws -> String {
        guard let url = Bundle.main.resourceURL?.appendingPathComponent("wallpaper/install.js"),
              (try? url.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) != true,
              let bytes = try? Data(contentsOf: url), bytes.count < 24 * 1024 * 1024,
              let text = String(data: bytes, encoding: .utf8), !text.isEmpty else {
            throw WallpaperFailure(state: "resource-missing", chinese: "缺少已打包的阿舟壁纸脚本，请重新构建并安装。", english: "The bundled Azhou wallpaper script is missing; rebuild and install the app.")
        }
        return text
    }

    static func perform(
        _ request: WallpaperRequest,
        began: TimeInterval,
        system: any StartupTargetSystem,
        transport: any WallpaperOperationTransport,
        now: () -> TimeInterval,
        expectedVersion: String,
        sourceLoader: () throws -> String,
        sleep: (TimeInterval) async throws -> Void
    ) async throws -> [String: Any] {
        let target = request.target
        defer { transport.close() }
        var operationLock: (any StartupOperationLock)?
        if request.action == .apply || request.action == .retry || request.action == .restore {
            operationLock = try system.acquireOperationLock(pid: target.pid)
        }
        defer { operationLock?.release() }
        if !request.cold, request.port == nil, try system.listeningPorts(target, deadline: began + 30).isEmpty {
            return ["state": "needs-restart", "applied": false,
                    "message": WallpaperMessages.localized(chinese: "当前 Codex 未开放壁纸连接。请自行完全退出 Codex，再从阿舟入口启动；本次没有重启或更改工作会话。", english: "The current Codex session has no wallpaper connection. Quit Codex completely, then launch it from the Azhou entry; this operation did not restart Codex or change the work session.")]
        }
        try system.validate(target, deadline: began + 30)
        var source = ""
        if request.action == .apply {
            source = try sourceLoader()
        }
        var sawEndpoint = false, lastState = "endpoint-unavailable"
        while now() - began < 28 {
            try Task.checkCancellation(); try system.validateProcess(target, deadline: began + 30)
            let owned = try system.listeningPorts(target, deadline: began + 30)
            if let port = request.port, !owned.contains(port) {
                throw WallpaperFailure(state: "endpoint-refused", chinese: "指定端口不是该 Codex 主进程独占的 IPv4 回环监听端口。", english: "The specified port is not an IPv4 loopback listener owned exclusively by this Codex main process.")
            }
            let ports = request.port.map { [$0] } ?? owned
            if ports.isEmpty && !request.cold {
                return ["state": "needs-restart", "applied": false,
                        "message": WallpaperMessages.localized(chinese: "当前 Codex 未开放壁纸连接。请自行完全退出 Codex，再从阿舟入口启动；本次没有重启或更改工作会话。", english: "The current Codex session has no wallpaper connection. Quit Codex completely, then launch it from the Azhou entry; this operation did not restart Codex or change the work session.")]
            }
            for port in ports.prefix(12) {
                do {
                    let pages = try await transport.pages(port: port, timeout: 2); sawEndpoint = true
                    if pages.isEmpty { lastState = "main-page-unavailable"; continue }
                    guard pages.count <= 12 else { throw WallpaperFailure(state: "page-count-refused", chinese: "主页面数量超出本次有限壁纸操作范围。", english: "The number of main pages exceeds this bounded wallpaper operation's limit.") }
                    if request.action == .doctor {
                        return ["state": "ready", "applied": false, "canApply": true, "port": port, "pageCount": pages.count,
                                "message": WallpaperMessages.localized(chinese: "已找到已核实 Codex 的本机主页面；此诊断没有注入壁纸。", english: "Found the verified Codex main page on this device; this diagnostic did not inject wallpaper.")]
                    }
                    var states: [[String: Any]] = []
                    var retries: [[String: Any]] = []
                    for page in pages {
                        try Task.checkCancellation(); try system.validateProcess(target, deadline: began + 30)
                        guard try system.listeningPorts(target, deadline: began + 30).contains(port), let raw = page["webSocketDebuggerUrl"] as? String else {
                            throw WallpaperFailure(state: "endpoint-changed", chinese: "目标监听或页面地址已变化，停止本次壁纸操作。", english: "The target listener or page address changed; this wallpaper operation has stopped.")
                        }
                        let socket = transport.pageSession(try WallpaperValidation.pageSocket(raw, port: port))
                        defer { socket.close() }
                        if request.action == .apply {
                            let ownership = try await socket.evaluate(applyGuardSource, timeout: 6)
                            if ownership["state"] as? String == "startup-active" {
                                throw WallpaperFailure(state: "startup-active", chinese: "当前页面已有 Agent Skin 启动控制器；独立壁纸应用已拒绝。", english: "This page already has the Agent Skin startup controller; standalone wallpaper application was refused.")
                            }
                            if ownership["state"] as? String == "owner-conflict" {
                                throw WallpaperFailure(state: "owner-conflict", chinese: "当前页面的壁纸或启动所有者未知；本次未覆盖。", english: "The wallpaper or startup owner on this page is unknown; nothing was overwritten.")
                            }
                            guard ownership["state"] as? String == "ready" else {
                                throw WallpaperFailure(state: "owner-conflict", chinese: "当前页面没有返回可核验的壁纸所有权状态；本次未覆盖。", english: "This page did not return verifiable wallpaper ownership state; nothing was overwritten.")
                            }
                            let applied: [String: Any]
                            do { applied = try await socket.evaluate(source, timeout: 6) }
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
                        } else if request.action == .retry {
                            // Do not start page work that could outlive this helper's total deadline.
                            guard 28 - (now() - began) >= retryEvaluationTimeout + 1 else {
                                return ["state": "timeout", "applied": false, "reason": "retry-budget-exhausted",
                                        "pageCount": pages.count, "completedPageCount": states.count, "retries": retries]
                            }
                            let recovery = try await socket.evaluate(retrySource, timeout: retryEvaluationTimeout)
                            if let state = recovery["state"] as? String {
                                let category = ["owner-conflict", "retry-unavailable", "retry-failed"].contains(state)
                                    ? state : "retry-failed"
                                return ["state": category, "applied": false, "port": port,
                                        "pageCount": pages.count, "completedPageCount": states.count, "retries": retries,
                                        "message": WallpaperMessages.localized(
                                            chinese: "当前控制器无法安全重试壁纸；未重建控制器或重播动画。",
                                            english: "The current controller cannot safely retry wallpaper; it was not recreated and the animation was not replayed.")]
                            }
                            guard let wallpaper = recovery["wallpaper"] as? [String: Any],
                                  let retried = recovery["retried"] as? Bool else {
                                throw WallpaperFailure(state: "retry-failed", chinese: "控制器未返回可核验的重试结果。", english: "The controller did not return a verifiable retry result.")
                            }
                            var receipt: [String: Any] = ["pageIndex": states.count, "retried": retried]
                            if let previous = recovery["previousFailure"] as? [String: Any] {
                                var failure: [String: Any] = WallpaperValidation.failureDiagnostic(previous)
                                if let reason = previous["reason"] as? String,
                                   ["wallpaper-unsupported", "not-installed", "owner-conflict", "disabled"].contains(reason) {
                                    failure["reason"] = reason
                                }
                                receipt["previousFailure"] = failure
                            }
                            retries.append(receipt)
                            if let reason = WallpaperValidation.retryFailure(recovery) {
                                let inspected = try await socket.evaluate(statusSource, timeout: 6)
                                var failedPage = WallpaperValidation.diagnostic(inspected, index: states.count, version: nil)
                                failedPage.merge(WallpaperValidation.failureDiagnostic(wallpaper)) { _, value in value }
                                return ["state": retried ? "retry-failed" : "retry-refused", "applied": false,
                                        "reason": reason, "port": port,
                                        "pageCount": pages.count, "retries": retries,
                                        "pages": [failedPage]]
                            }
                        } else if request.action == .restore {
                            let restored = try await socket.evaluate(restoreSource, timeout: 6)
                            guard restored["restored"] as? Bool == true else {
                                if restored["reason"] as? String == "owner-conflict" {
                                    throw WallpaperFailure(state: "owner-conflict", chinese: "当前页面的壁纸或启动所有者未知；本次未覆盖或删除。", english: "The wallpaper or startup owner on this page is unknown; nothing was overwritten or removed.")
                                }
                                throw WallpaperFailure(state: "restore-unconfirmed", chinese: "页面没有确认移除壁纸。", english: "The page did not confirm wallpaper removal.")
                            }
                        }
                        let state: [String: Any]
                        do { state = try await socket.evaluate(statusSource, timeout: 6) }
                        catch let error as WallpaperFailure where request.action == .apply && error.state == "renderer-rejected" {
                            var result = WallpaperValidation.applicationFailure(
                                priorStates: states, failedState: nil, totalPages: pages.count,
                                version: expectedVersion, failureState: error.state)
                            result["port"] = port
                            return result
                        }
                        try system.validateProcess(target, deadline: began + 30)
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
                        guard states.allSatisfy({ $0["applied"] as? Bool != true }) else { throw WallpaperFailure(state: "restore-unconfirmed", chinese: "复查时壁纸仍存在。", english: "The wallpaper was still present during recheck.") }
                        return ["state": "restored", "applied": false, "restored": true, "port": port, "pageCount": states.count,
                                "message": restoreMessage]
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
                        "state": verified ? "applied" : ((request.action == .apply || request.action == .retry) ? "verification-failed" : "not-applied"),
                        "applied": verified, "port": port, "pageCount": states.count,
                        "version": versions.count == 1 ? versions.first! : "",
                        "pages": pageDiagnostics, "verificationIssues": issues.sorted(),
                        "verificationScope": WallpaperMessages.localized(
                            chinese: "运行时检查图像与装饰图层；视觉效果需另行检查。",
                            english: "Runtime image and decorative-layer checks; visual inspection is separate."
                        ),
                        "message": verified
                            ? WallpaperMessages.localized(chinese: "已复查当前 Codex 页面中的阿舟壁纸。", english: "Rechecked the Azhou wallpaper on the current Codex pages.")
                            : WallpaperMessages.localized(chinese: "当前页面未通过壁纸图层核查；请查看 verificationIssues 与 pages。", english: "The current pages did not pass wallpaper layer verification; see verificationIssues and pages."),
                    ]
                    for key in WallpaperValidation.inspectionFlags {
                        result[key] = states.allSatisfy { WallpaperValidation.trueBoolean($0[key]) }
                    }
                    for key in ["matchedSurfaces", "transparentSurfaces", "footerSurfaces", "footerFadeSurfaces", "topFadeSurfaces"] {
                        result[key] = states.reduce(0) { $0 + (WallpaperValidation.surfaceCount($1[key]) ?? 0) }
                    }
                    if request.action == .retry { result["retries"] = retries }
                    return result
                } catch let error as WallpaperFailure {
                    if ["target-mismatch", "target-changed", "endpoint-refused", "endpoint-changed", "page-count-refused",
                        "renderer-rejected", "renderer-not-applied", "verification-failed", "restore-unconfirmed",
                        "owner-conflict", "startup-active", "retry-failed"].contains(error.state) { throw error }
                    lastState = error.state
                } catch { lastState = "connection-failed" }
            }
            if !request.cold && !sawEndpoint {
                return ["state": "needs-restart", "applied": false,
                        "message": WallpaperMessages.localized(chinese: "当前 Codex 没有可核实的页面调试连接。请自行完全退出后再从阿舟入口启动；未重启当前会话。", english: "The current Codex session has no verifiable page debugging connection. Quit it completely, then relaunch from the Azhou entry; the session was not restarted.")]
            }
            try await sleep(0.25)
        }
        return ["state": "timeout", "applied": false, "reason": lastState,
                "message": WallpaperMessages.localized(chinese: "在有限等待时间内未完成壁纸确认；Codex 保持运行，动画交接不受影响。", english: "Wallpaper confirmation did not finish within the bounded wait. Codex remains running, and animation handoff is unaffected.")]
    }
}
