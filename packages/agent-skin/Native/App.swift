import AppKit
import WebKit
import Darwin
import CoreFoundation

final class NativeEventWriter: @unchecked Sendable {
    static let schema = "azhou-startup.event.v1"

    private let startedAt: TimeInterval
    private let launcherPID: Int
    private let launcherPath: String
    private let now: () -> TimeInterval
    private let sink: ([String: Any]) -> Void
    private let lock = NSLock()
    private var lastSeconds: Double = 0

    init(startedAt: TimeInterval, launcherPID: Int, launcherPath: String,
         now: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime },
         sink: @escaping ([String: Any]) -> Void) {
        self.startedAt = startedAt
        self.launcherPID = launcherPID
        self.launcherPath = launcherPath
        self.now = now
        self.sink = sink
    }

    func emit(_ event: String, fields: [String: Any] = [:], at uptime: TimeInterval? = nil) {
        lock.lock()
        defer { lock.unlock() }

        let elapsed = (uptime ?? now()) - startedAt
        let seconds = elapsed.isFinite ? max(lastSeconds, max(0, elapsed)) : lastSeconds
        lastSeconds = seconds
        var record = fields
        record["schema"] = Self.schema
        record["event"] = event
        record["seconds"] = seconds
        record["launcherPID"] = launcherPID
        record["launcherPath"] = launcherPath
        sink(record)
    }

    func emitProbe(targetPath: String, targetBundleID: String, running: [[String: Any]],
                   frontmost: [String: Any], at uptime: TimeInterval? = nil) {
        emit("probe", fields: ["targetPath": targetPath, "targetBundleID": targetBundleID,
                               "running": running, "frontmost": frontmost], at: uptime)
    }
}

struct NativeStartupStatus {
    let runID: Int
    let phase: String
    let ready: Bool
    let completed: Bool
    let overlay: Bool
    let completionCause: String?
    let completionBeforeReady: Bool?

    static func parse(_ value: Any?) -> NativeStartupStatus? {
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
              wallpaperReason.isEmpty || wallpaperReason == "disabled" || validReasons.contains(wallpaperReason),
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
        case "playing", "settings": guard ready, !completed, overlay else { return nil }
        case "complete": guard completed, !overlay else { return nil }
        case "failed", "timeout": guard !overlay, !reason.isEmpty else { return nil }
        case "disposed": guard !overlay else { return nil }
        default: return nil
        }
        return NativeStartupStatus(runID: runID, phase: phase, ready: ready, completed: completed,
                                   overlay: overlay, completionCause: completionCause,
                                   completionBeforeReady: completionBeforeReady)
    }

    static func boolean(_ value: Any?) -> Bool? {
        guard let number = value as? NSNumber, CFGetTypeID(number) == CFBooleanGetTypeID() else { return nil }
        return number.boolValue
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
}

struct NativeStartupObservation {
    let targetPID: Int32
    let installedAt: TimeInterval?
    let status: NativeStartupStatus?
    let statusAt: TimeInterval?
}

final class NativeStartupCapture: @unchecked Sendable {
    private let lock = NSLock()
    let targetPID: Int32
    private var installAt: TimeInterval?
    private var installedRunID: Int?
    private var status: NativeStartupStatus?
    private var statusAt: TimeInterval?

    init(targetPID: Int32) { self.targetPID = targetPID }

    func observe(_ response: [String: Any], at uptime: TimeInterval) -> (runID: Int, installedAt: TimeInterval)? {
        lock.lock()
        defer { lock.unlock() }

        if NativeStartupStatus.boolean(response["installed"]) == true,
           NativeStartupStatus.boolean(response["alreadyActive"]) == false,
           installAt == nil {
            installAt = uptime
        }
        guard let rawStatus = response["status"], let observed = NativeStartupStatus.parse(rawStatus),
              let installAt else { return nil }

        if installedRunID == nil {
            installedRunID = observed.runID
            status = observed
            statusAt = uptime
            return (observed.runID, installAt)
        }
        guard installedRunID == observed.runID else { return nil }
        status = observed
        statusAt = uptime
        return nil
    }

    func snapshot() -> NativeStartupObservation {
        lock.lock()
        defer { lock.unlock() }
        return NativeStartupObservation(targetPID: targetPID, installedAt: installAt,
                                        status: status, statusAt: statusAt)
    }
}

enum NativeStartupFinalOutcome: Equatable {
    case activated
    case ready
    case skipped
    case partial(reason: String)
    case behaviorNotProven(reason: String)

    var exitCode: Int32 {
        switch self {
        case .activated, .ready, .skipped: return 0
        case .partial: return 2
        case .behaviorNotProven: return 1
        }
    }

    var event: String {
        switch self {
        case .activated: return "target-activated"
        case .ready: return "startup-ready"
        case .skipped: return "startup-skipped"
        case .partial: return "startup-interrupted"
        case .behaviorNotProven: return "startup-failed"
        }
    }

    var exitName: String {
        switch self {
        case .activated: return "activated"
        case .ready: return "startup-ready"
        case .skipped: return "skipped"
        case .partial: return "partial"
        case .behaviorNotProven: return "behavior-not-proven"
        }
    }

    var reason: String? {
        switch self {
        case .partial(let reason), .behaviorNotProven(let reason): return reason
        default: return nil
        }
    }
}

final class NativeStartupEventStream: @unchecked Sendable {
    private let lock = NSLock()
    private let writer: NativeEventWriter
    private var begun = false
    private var finalOutcome: NativeStartupFinalOutcome?
    private var pendingFailure: String?
    private var pendingInterruption: String?
    private var openedPID: Int32?
    private var installedPID: Int32?
    private var installedRunID: Int?
    private var exitEmitted = false

    init(writer: NativeEventWriter) { self.writer = writer }

    func begin(at uptime: TimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        guard !begun else { return }
        begun = true
        writer.emit("launcher-start", at: uptime)
    }

    func targetOpened(pid: Int32, at uptime: TimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        guard begun, finalOutcome == nil, !exitEmitted, pid > 0 else { return }
        if let openedPID {
            guard openedPID == pid else { return }
            return
        }
        openedPID = pid
        writer.emit("target-opened", fields: ["targetPID": Int(pid)], at: uptime)
    }

    func startupInstalled(pid: Int32, runID: Int, at uptime: TimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        guard begun, finalOutcome == nil, !exitEmitted, pid > 0, runID > 0,
              openedPID == pid, installedPID == nil else { return }
        installedPID = pid
        installedRunID = runID
        writer.emit("startup-installed", fields: ["targetPID": Int(pid), "runId": runID], at: uptime)
    }

    func portError(operation: String, errno: Int32, at uptime: TimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        guard begun, finalOutcome == nil, !exitEmitted else { return }
        pendingFailure = "listener-mismatch"
        writer.emit("startup-port-error", fields: ["reason": "listener-mismatch",
                                                     "operation": operation, "errno": Int(errno)], at: uptime)
    }

    func latchFailure(_ reason: String) {
        lock.lock()
        defer { lock.unlock() }
        guard begun, finalOutcome == nil, !exitEmitted, pendingFailure == nil else { return }
        pendingFailure = Self.fixedReason(reason)
    }

    func latchInterruption(_ reason: String = "startup-interrupted") {
        lock.lock()
        defer { lock.unlock() }
        guard begun, finalOutcome == nil, !exitEmitted, pendingFailure == nil, pendingInterruption == nil else { return }
        pendingInterruption = reason == "startup-interrupted" ? reason : "startup-interrupted"
    }

    var isPending: Bool {
        lock.lock()
        defer { lock.unlock() }
        return begun && finalOutcome == nil && !exitEmitted
    }

    @discardableResult
    func resolve(_ outcome: StartupOutcome, observation: NativeStartupObservation?, at uptime: TimeInterval) -> NativeStartupFinalOutcome? {
        lock.lock()
        defer { lock.unlock() }
        guard begun, finalOutcome == nil, !exitEmitted else { return nil }

        let resolved: NativeStartupFinalOutcome
        if let pendingFailure {
            resolved = .behaviorNotProven(reason: pendingFailure)
        } else if let pendingInterruption {
            resolved = .partial(reason: pendingInterruption)
        } else {
            resolved = Self.finalOutcome(for: outcome, observation: observation,
                                         openedPID: openedPID, installedPID: installedPID,
                                         installedRunID: installedRunID)
        }
        finalOutcome = resolved
        emitFinal(resolved, outcome: outcome, observation: observation, at: uptime)
        return resolved
    }

    @discardableResult
    func finish(at uptime: TimeInterval) -> NativeStartupFinalOutcome? {
        lock.lock()
        defer { lock.unlock() }
        guard begun, !exitEmitted else { return finalOutcome }
        if finalOutcome == nil {
            if let pendingFailure {
                finalOutcome = .behaviorNotProven(reason: pendingFailure)
            } else if let pendingInterruption {
                finalOutcome = .partial(reason: pendingInterruption)
            } else {
                finalOutcome = .partial(reason: "startup-interrupted")
            }
            emitFinal(finalOutcome!, outcome: nil, observation: nil, at: uptime)
        }
        guard let finalOutcome else { return nil }
        writer.emit("launcher-exit", fields: ["outcome": finalOutcome.exitName, "exitCode": Int(finalOutcome.exitCode)], at: uptime)
        exitEmitted = true
        return finalOutcome
    }

    private func emitFinal(_ final: NativeStartupFinalOutcome, outcome: StartupOutcome?,
                           observation: NativeStartupObservation?, at uptime: TimeInterval) {
        switch final {
        case .activated:
            if case .activated(let pid)? = outcome {
                writer.emit("target-activated", fields: ["targetPID": Int(pid)], at: uptime)
            }
        case .ready:
            guard let observation, let status = observation.status, let runID = installedRunID else { return }
            writer.emit("startup-ready", fields: ["targetPID": Int(observation.targetPID), "runId": runID,
                                                    "ready": true, "phase": status.phase],
                        at: observation.statusAt ?? uptime)
        case .skipped:
            guard let observation, let status = observation.status, let runID = installedRunID,
                  let beforeReady = status.completionBeforeReady else { return }
            writer.emit("startup-skipped", fields: ["targetPID": Int(observation.targetPID), "runId": runID,
                                                      "completed": true,
                                                      "completion": ["cause": "skip", "beforeReady": beforeReady],
                                                      "overlay": false],
                        at: observation.statusAt ?? uptime)
        case .partial(let reason), .behaviorNotProven(let reason):
            writer.emit(final.event, fields: ["reason": reason], at: uptime)
        }
    }

    private static func finalOutcome(for outcome: StartupOutcome, observation: NativeStartupObservation?,
                                     openedPID: Int32?, installedPID: Int32?, installedRunID: Int?) -> NativeStartupFinalOutcome {
        switch outcome {
        case .activated(let pid):
            return pid > 0 ? .activated : .behaviorNotProven(reason: "target-identity")
        case .ready(let runID):
            guard let observation, let status = observation.status,
                  observation.targetPID > 0, openedPID == observation.targetPID,
                  installedPID == observation.targetPID, installedRunID == runID,
                  runID > 0, status.runID == runID, status.ready,
                  ["playing", "settings", "complete"].contains(status.phase) else {
                return .behaviorNotProven(reason: "protocol-error")
            }
            return .ready
        case .skipped(let runID, let beforeReady):
            guard let observation, let status = observation.status,
                  observation.targetPID > 0, openedPID == observation.targetPID,
                  installedPID == observation.targetPID, installedRunID == runID,
                  runID > 0, status.runID == runID, status.completed, !status.overlay,
                  status.completionCause == "skip", status.completionBeforeReady == beforeReady else {
                return .behaviorNotProven(reason: "protocol-error")
            }
            return .skipped
        case .partial(let reason) where reason == "startup-interrupted":
            return .partial(reason: reason)
        case .partial(let reason):
            return .behaviorNotProven(reason: Self.fixedReason(reason))
        case .failed(let reason):
            return .behaviorNotProven(reason: Self.fixedReason(reason))
        }
    }

    private static func fixedReason(_ reason: String) -> String {
        let allowed: Set<String> = [
            "target-missing", "target-identity", "listener-mismatch", "page-pending", "page-unsupported",
            "owner-conflict", "protocol-error", "attach-timeout", "asset-invalid", "storage-unavailable",
            "wallpaper-unsupported", "overlay-timeout", "ambiguous-main-page", "startup-active",
            "startup-interrupted", "settings-conflict", "operation-timeout"
        ]
        return allowed.contains(reason) ? reason : "protocol-error"
    }
}

final class NativeStartupEventTransport: StartupTransport, @unchecked Sendable {
    private let base: any StartupTransport
    private let capture: NativeStartupCapture
    private let events: NativeStartupEventStream
    private let now: () -> TimeInterval

    init(base: any StartupTransport, capture: NativeStartupCapture, events: NativeStartupEventStream,
         now: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }) {
        self.base = base
        self.capture = capture
        self.events = events
        self.now = now
    }

    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        try await base.pages(port: port, timeout: timeout)
    }

    func connect(to url: URL, timeout: TimeInterval) throws {
        try base.connect(to: url, timeout: timeout)
    }

    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        let response = try await base.evaluate(source, timeout: timeout)
        if let installation = capture.observe(response, at: now()) {
            events.startupInstalled(pid: capture.targetPID, runID: installation.runID, at: installation.installedAt)
        }
        return response
    }

    func close() { base.close() }
}

enum NativeSmokeReportValidator {
    private static let resourceCounters = [
        "createdImages", "releasedImages", "liveImages",
        "createdBitmaps", "releasedBitmaps", "liveBitmaps",
        "createdCanvases", "releasedCanvases", "liveCanvases",
        "createdPaths", "releasedPaths", "livePaths",
        "createdRAF", "cancelledRAF", "liveRAF",
        "createdObjectURLs", "revokedObjectURLs", "liveObjectURLs",
        "framesPending"
    ]

    static func isSuccessfulCompletion(skipped: Any?, reportJSON: String?, evaluationFailed: Bool) -> Bool {
        guard !evaluationFailed,
              NativeStartupStatus.boolean(skipped) == false,
              let reportJSON, let data = reportJSON.data(using: .utf8),
              let raw = try? JSONSerialization.jsonObject(with: data),
              let report = raw as? [String: Any],
              NativeStartupStatus.boolean(report["completed"]) == true,
              NativeStartupStatus.boolean(report["skipped"]) == false,
              NativeStartupStatus.boolean(report["reduced"]) != nil,
              let elapsed = finiteNumber(report["elapsed"]),
              let duration = finiteNumber(report["duration"]),
              duration > 0, elapsed >= duration,
              report["stage"] as? String == "complete",
              finiteNumber(report["animationProgress"]) == 1,
              let viewport = report["viewport"] as? [String: Any],
              positiveNumber(viewport["width"]), positiveNumber(viewport["height"]),
              positiveNumber(viewport["dpr"]),
              let coordinateSize = report["coordinateSize"] as? [String: Any],
              positiveNumber(coordinateSize["width"]), positiveNumber(coordinateSize["height"]),
              let resources = report["resources"] as? [String: Any],
              resourceCounters.allSatisfy({ finiteNumber(resources[$0]) != nil }),
              finiteNumber(resources["framesPending"]) == 0,
              let jsFrame = report["jsFrame"] as? [String: Any],
              jsFrame["scope"] as? String == "JavaScript rAF interval and 2D canvas submission; excludes GPU/compositor/presentation timing",
              validStats(jsFrame["rafIntervalMs"]), validStats(jsFrame["renderSubmissionMs"]) else {
            return false
        }
        return true
    }

    private static func positiveNumber(_ value: Any?) -> Bool {
        guard let number = finiteNumber(value) else { return false }
        return number > 0
    }

    private static func finiteNumber(_ value: Any?) -> Double? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let value = number.doubleValue
        return value.isFinite ? value : nil
    }

    private static func validStats(_ value: Any?) -> Bool {
        guard let value else { return false }
        if value is NSNull { return true }
        guard let stats = value as? [String: Any],
              let count = finiteNumber(stats["count"]), count > 0, count.rounded() == count,
              finiteNumber(stats["median"]) != nil,
              finiteNumber(stats["p95"]) != nil,
              finiteNumber(stats["max"]) != nil else { return false }
        return true
    }
}

private final class StartupApplicationWaiter: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<any NativeApplication, Error>?
    private var completed = false
    private var timeout: DispatchWorkItem?

    init(_ continuation: CheckedContinuation<any NativeApplication, Error>) {
        self.continuation = continuation
    }

    func setTimeout(_ timeout: DispatchWorkItem) {
        lock.lock()
        if completed { lock.unlock(); timeout.cancel(); return }
        self.timeout = timeout
        lock.unlock()
    }

    func finish(_ result: Result<any NativeApplication, Error>) {
        lock.lock()
        guard !completed, let continuation else { lock.unlock(); return }
        completed = true
        self.continuation = nil
        let timeout = self.timeout
        self.timeout = nil
        lock.unlock()
        timeout?.cancel()
        continuation.resume(with: result)
    }
}

// The native window is retained only for explicit preview and smoke runs.
enum NativeDisplayLocale: Equatable {
    case chinese
    case english

    static func systemFallback(preferredLanguages: [String] = Locale.preferredLanguages) -> NativeDisplayLocale {
        let language = (preferredLanguages.first ?? Locale.current.identifier).lowercased()
        return language.hasPrefix("zh") ? .chinese : .english
    }

    static func verifiedReadyLocale(_ value: Any?) -> NativeDisplayLocale? {
        switch value as? String {
        case "zh-CN": return .chinese
        case "en": return .english
        default: return nil
        }
    }

    var identifier: String {
        switch self {
        case .chinese: return "zh-CN"
        case .english: return "en"
        }
    }

    var displayName: String {
        displayName(in: .main)
    }

    func displayName(in bundle: Bundle) -> String {
        let fallback = bundle.infoDictionary?["CFBundleDisplayName"] as? String ?? "Azhou"
        let language = self == .chinese ? "zh-Hans" : "en"
        guard let path = bundle.path(forResource: language, ofType: "lproj"),
              let localized = Bundle(path: path) else { return fallback }
        return localized.localizedString(forKey: "CFBundleDisplayName", value: fallback, table: "InfoPlist")
    }

    var quitTitle: String {
        switch self {
        case .chinese: return "退出\(displayName)"
        case .english: return "Quit \(displayName)"
        }
    }

    var closeTitle: String {
        switch self {
        case .chinese: return "关闭"
        case .english: return "Close"
        }
    }

    func message(for reason: String) -> String {
        switch reason {
        case "resources-missing":
            return self == .chinese ? "资源目录不可用。" : "The resource directory is unavailable."
        case "page-missing":
            return self == .chinese ? "动画页面缺失，请重新构建应用。" : "The animation page is missing. Rebuild the app."
        case "target-launch-timeout":
            return self == .chinese ? "等待 Codex 启动超时，请检查原应用入口。" : "Timed out waiting for Codex to launch. Check its original app entry."
        case "renderer-ready-timeout":
            return self == .chinese ? "动画播放器未能及时准备好，请关闭后重试。" : "The animation did not become ready in time. Close this window and try again."
        case "renderer-complete-timeout":
            return self == .chinese ? "动画未能按时完成，请关闭后重试。" : "The animation did not finish in time. Close this window and try again."
        case "playback-start-error":
            return self == .chinese ? "动画预览无法启动。" : "The animation preview could not be started."
        case "javascript-error":
            return self == .chinese ? "动画脚本运行失败。" : "The animation script failed."
        case "asset-error":
            return self == .chinese ? "阿舟素材加载失败，请检查本地素材并重新构建。" : "Azhou assets could not be loaded. Check the local assets and rebuild."
        case "target-exited":
            return self == .chinese ? "Codex 在交接前已经退出。" : "Codex exited before control was handed off."
        case "activation-rejected":
            return self == .chinese ? "系统没有接受 Codex 激活请求。请关闭此窗口，再从原应用入口打开。" : "macOS did not activate Codex. Close this window, then open it from the original app entry."
        case "renderer-terminated":
            return self == .chinese ? "WebKit 渲染进程已结束。" : "The WebKit rendering process ended."
        case "target-missing":
            return self == .chinese ? "没有找到有效的 Codex 主程序。" : "A valid Codex app was not found."
        case "target-identity":
            return self == .chinese ? "Codex 进程身份或签名核验未通过。" : "Codex process identity or signature verification failed."
        case "listener-mismatch":
            return self == .chinese ? "Codex 调试端口不属于已核验的主进程。" : "The Codex debug port does not belong to the verified process."
        case "page-pending":
            return self == .chinese ? "Codex 主页面尚未准备好。" : "The Codex main page is not ready."
        case "page-unsupported":
            return self == .chinese ? "当前 Codex 页面不符合启动接入要求。" : "This Codex page does not meet the startup requirements."
        case "ambiguous-main-page":
            return self == .chinese ? "找到多个 Codex 主页面，本次启动接入已拒绝。" : "Multiple Codex main pages were found. Startup integration was rejected."
        case "owner-conflict", "startup-active":
            return self == .chinese ? "Codex 页面已有启动控制器，本次没有覆盖或重播。" : "This Codex page already has a startup controller. It was not replaced or replayed."
        case "startup-interrupted":
            return self == .chinese ? "Codex 页面在启动接入期间发生变化。" : "The Codex page changed during startup integration."
        case "attach-timeout":
            return self == .chinese ? "Codex 启动接入超过阶段或总时间限制。" : "Codex startup integration exceeded its stage or total time limit."
        case "asset-invalid":
            return self == .chinese ? "缺少有效的 startup/install.js 生产载荷；本次不会启动或注入 Codex。" : "The production startup/install.js payload is missing or invalid. Codex was not opened or injected."
        case "preview-promotion-error":
            return self == .chinese ? "无法从预览切换到启动。" : "Could not switch from preview to launch."
        case "navigation-error":
            return self == .chinese ? "无法打开动画页面。" : "The animation page could not be opened."
        default:
            return self == .chinese ? "Codex 启动接入未完成；Codex 进程保持运行。" : "Codex startup integration did not finish. The Codex process remains running."
        }
    }
}

@MainActor
protocol NativeApplication: AnyObject {
    var processIdentifier: Int32 { get }
    var bundleIdentifier: String? { get }
    var bundleURL: URL? { get }
    var executableURL: URL? { get }
    var launchTime: TimeInterval? { get }
    var isTerminated: Bool { get }
    var isActive: Bool { get }
    var isHidden: Bool { get }
    @discardableResult func activate() -> Bool
}

@MainActor
final class SystemNativeApplication: NativeApplication {
    let application: NSRunningApplication
    private let activateBody: () -> Bool
    init(_ application: NSRunningApplication, activate: (() -> Bool)? = nil) {
        self.application = application
        self.activateBody = activate ?? { application.activate(options: []) }
    }
    var processIdentifier: Int32 { application.processIdentifier }
    var bundleIdentifier: String? { application.bundleIdentifier }
    var bundleURL: URL? { application.bundleURL }
    var executableURL: URL? { application.executableURL }
    var launchTime: TimeInterval? { application.launchDate?.timeIntervalSince1970 }
    var isTerminated: Bool { application.isTerminated }
    var isActive: Bool { application.isActive }
    var isHidden: Bool { application.isHidden }
    func activate() -> Bool { activateBody() }
}

@MainActor
protocol NativeInstanceLock: AnyObject {
    func release()
}

@MainActor
private final class FileDescriptorNativeInstanceLock: NativeInstanceLock {
    private var descriptor: Int32
    init(_ descriptor: Int32) { self.descriptor = descriptor }
    func release() {
        guard descriptor >= 0 else { return }
        flock(descriptor, LOCK_UN)
        Darwin.close(descriptor)
        descriptor = -1
    }
}

enum NativeLockAcquisition {
    case acquired(any NativeInstanceLock)
    case busy
    case failed(Int32)
}

struct NativeLoopbackPortError: Error {
    let operation: String
    let code: Int32
}

@MainActor
protocol NativeAppRuntime: AnyObject {
    var arguments: [String] { get }
    var epoch: TimeInterval { get }
    var uptime: TimeInterval { get }
    var processIdentifier: Int { get }
    var bundleURL: URL { get }
    var resourceURL: URL? { get }
    func appearanceTheme() -> String
    var frontmostApplication: (any NativeApplication)? { get }
    func runningApplications(bundleIdentifier: String) -> [any NativeApplication]
    func application(processIdentifier: Int32) -> (any NativeApplication)?
    func urlForApplication(bundleIdentifier: String) -> URL?
    func openApplication(at url: URL, debuggingPort: Int,
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void)
    func acquireInstanceLock(identifier: String) -> NativeLockAcquisition
    func allocateLoopbackPort() throws -> Int
    func makeStartupTargetSystem() -> any StartupTargetSystem
    func makeStartupTransport(capture: NativeStartupCapture, events: NativeStartupEventStream) -> any StartupTransport
    func systemFallbackLocale() -> NativeDisplayLocale
    func setAccessoryPolicy()
    func activateIgnoringOtherApps()
    func terminate()
    func exit(code: Int32)
    func writeStandardOutput(_ line: String)
}

@MainActor
final class SystemNativeAppRuntime: NativeAppRuntime {
    private let openApplicationBody: (URL, NSWorkspace.OpenConfiguration,
                                      @escaping (NSRunningApplication?, Error?) -> Void) -> Void
    private let setAccessoryPolicyBody: () -> Void
    private let activateIgnoringOtherAppsBody: () -> Void
    private let terminateBody: () -> Void
    private let exitBody: (Int32) -> Void
    private let standardOutputBody: (String) -> Void

    init(openApplication: ((URL, NSWorkspace.OpenConfiguration,
                           @escaping (NSRunningApplication?, Error?) -> Void) -> Void)? = nil,
         setAccessoryPolicy: (() -> Void)? = nil,
         activateIgnoringOtherApps: (() -> Void)? = nil,
         terminate: (() -> Void)? = nil,
         exit: ((Int32) -> Void)? = nil,
         standardOutput: ((String) -> Void)? = nil) {
        self.openApplicationBody = openApplication ?? { url, configuration, completion in
            NSWorkspace.shared.openApplication(at: url, configuration: configuration) { application, error in
                DispatchQueue.main.async { completion(application, error) }
            }
        }
        self.setAccessoryPolicyBody = setAccessoryPolicy ?? { NSApp.setActivationPolicy(.accessory) }
        self.activateIgnoringOtherAppsBody = activateIgnoringOtherApps ?? { NSApp.activate(ignoringOtherApps: true) }
        self.terminateBody = terminate ?? { NSApp.terminate(nil) }
        self.exitBody = exit ?? { Darwin.exit($0) }
        self.standardOutputBody = standardOutput ?? { print($0); fflush(stdout) }
    }

    var arguments: [String] { CommandLine.arguments }
    var epoch: TimeInterval { ProcessInfo.processInfo.systemUptime }
    var uptime: TimeInterval { ProcessInfo.processInfo.systemUptime }
    var processIdentifier: Int { Int(ProcessInfo.processInfo.processIdentifier) }
    var bundleURL: URL { Bundle.main.bundleURL }
    var resourceURL: URL? { Bundle.main.resourceURL }
    func appearanceTheme() -> String {
        NSApp.effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua ? "dark" : "light"
    }
    var frontmostApplication: (any NativeApplication)? {
        NSWorkspace.shared.frontmostApplication.map { SystemNativeApplication($0) }
    }
    func runningApplications(bundleIdentifier: String) -> [any NativeApplication] {
        NSRunningApplication.runningApplications(withBundleIdentifier: bundleIdentifier).map { SystemNativeApplication($0) }
    }
    func application(processIdentifier: Int32) -> (any NativeApplication)? {
        NSRunningApplication(processIdentifier: processIdentifier).map { SystemNativeApplication($0) }
    }
    func urlForApplication(bundleIdentifier: String) -> URL? {
        NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleIdentifier)
    }
    func openApplication(at url: URL, debuggingPort: Int,
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void) {
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = false; configuration.hides = false; configuration.hidesOthers = false
        configuration.createsNewApplicationInstance = false; configuration.allowsRunningApplicationSubstitution = false
        configuration.addsToRecentItems = false
        configuration.arguments = ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=\(debuggingPort)"]
        openApplicationBody(url, configuration) { application, error in
            completion(application.map { SystemNativeApplication($0) }, error)
        }
    }
    func acquireInstanceLock(identifier: String) -> NativeLockAcquisition {
        let path = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("\(identifier)-\(getuid()).lock").path
        let descriptor = Darwin.open(path, O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, S_IRUSR | S_IWUSR)
        guard descriptor >= 0 else { return .failed(errno) }
        guard flock(descriptor, LOCK_EX | LOCK_NB) == 0 else {
            let code = errno
            Darwin.close(descriptor)
            return (code == EWOULDBLOCK || code == EAGAIN) ? .busy : .failed(code)
        }
        return .acquired(FileDescriptorNativeInstanceLock(descriptor))
    }
    func allocateLoopbackPort() throws -> Int {
        func failure(_ operation: String) -> NativeLoopbackPortError { NativeLoopbackPortError(operation: operation, code: errno) }
        let descriptor = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else { throw failure("socket") }
        defer { Darwin.close(descriptor) }
        guard fcntl(descriptor, F_SETFD, FD_CLOEXEC) == 0 else { throw failure("close-on-exec") }
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = 0
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bound = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(descriptor, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bound == 0 else { throw failure("bind-loopback") }
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.getsockname(descriptor, $0, &length) }
        }
        guard named == 0 else { throw failure("getsockname") }
        let port = Int(UInt16(bigEndian: address.sin_port))
        guard (1...65535).contains(port), address.sin_family == sa_family_t(AF_INET),
              address.sin_addr.s_addr == inet_addr("127.0.0.1") else {
            throw NativeLoopbackPortError(operation: "verify-loopback", code: 0)
        }
        return port
    }
    func makeStartupTargetSystem() -> any StartupTargetSystem { CodexStartupTargetSystem() }
    func makeStartupTransport(capture: NativeStartupCapture, events: NativeStartupEventStream) -> any StartupTransport {
        NativeStartupEventTransport(base: WallpaperTransport(), capture: capture, events: events)
    }
    func systemFallbackLocale() -> NativeDisplayLocale { NativeDisplayLocale.systemFallback() }
    func setAccessoryPolicy() { setAccessoryPolicyBody() }
    func activateIgnoringOtherApps() { activateIgnoringOtherAppsBody() }
    func terminate() { terminateBody() }
    func exit(code: Int32) { exitBody(code) }
    func writeStandardOutput(_ line: String) { standardOutputBody(line) }
}

@MainActor
protocol NativeScheduledAction: AnyObject {
    func cancel()
}

@MainActor
protocol NativePlayerPresentation: AnyObject {
    var geometry: [String: Any] { get }
    func createPlayer(locale: NativeDisplayLocale, mode: String, theme: String, inspect: Bool,
                      messageHandler: WKScriptMessageHandler, navigationDelegate: WKNavigationDelegate)
    func loadPlayer(page: URL, allowingReadAccessTo root: URL)
    func updateLabels(_ locale: NativeDisplayLocale)
    func showReady()
    func setNormalLevel()
    func makeVisible()
    func orderOut()
    func evaluateJavaScript(_ source: String, completion: ((Any?, Error?) -> Void)?)
    func fadeOut(duration: TimeInterval, completion: @escaping () -> Void)
    func schedule(after delay: TimeInterval, _ action: @escaping () -> Void) -> any NativeScheduledAction
    func takeSnapshot(_ completion: @escaping (NSImage?, Error?) -> Void)
    func stopLoading()
    func removeMessageHandler(named name: String)
    func showError(title: String, message: String, closeTitle: String)
}

@MainActor
private final class NativeTimerAction: NativeScheduledAction {
    private let timer: Timer
    init(_ timer: Timer) { self.timer = timer }
    func cancel() { timer.invalidate() }
}

@MainActor
final class AppKitNativePlayerPresentation: NativePlayerPresentation {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var appMenuItem: NSMenuItem?
    private var quitMenuItem: NSMenuItem?
    private let activateApp: () -> Void
    private let makeVisibleBody: (NSWindow) -> Void
    private let runAlert: (NSAlert) -> Void

    init(activateApp: (() -> Void)? = nil,
         makeVisible: ((NSWindow) -> Void)? = nil,
         runAlert: ((NSAlert) -> Void)? = nil) {
        self.activateApp = activateApp ?? { NSApp.activate(ignoringOtherApps: true) }
        self.makeVisibleBody = makeVisible ?? { $0.makeKeyAndOrderFront(nil) }
        self.runAlert = runAlert ?? { _ = $0.runModal() }
    }

    var geometry: [String: Any] {
        guard let window else { return [:] }
        func rectInfo(_ rect: NSRect) -> [String: Double] {
            ["x": Double(rect.origin.x), "y": Double(rect.origin.y),
             "width": Double(rect.width), "height": Double(rect.height)]
        }
        let screen = window.screen ?? NSScreen.main
        return ["frame": rectInfo(window.frame),
                "visibleFrame": screen.map { rectInfo($0.visibleFrame) } ?? [:],
                "contentBounds": rectInfo(window.contentView?.bounds ?? .zero),
                "screen": screen?.localizedName ?? "", "backingScale": window.backingScaleFactor]
    }

    func createPlayer(locale: NativeDisplayLocale, mode: String, theme: String, inspect: Bool,
                      messageHandler: WKScriptMessageHandler, navigationDelegate: WKNavigationDelegate) {
        let menu = NSMenu(), item = NSMenuItem(), submenu = NSMenu()
        menu.addItem(item); item.submenu = submenu; appMenuItem = item
        quitMenuItem = submenu.addItem(withTitle: locale.quitTitle,
                                       action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        NSApp.mainMenu = menu
        let screen = NSScreen.main ?? NSScreen.screens.first
        let available = screen?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let window = NSWindow(contentRect: available,
                              styleMask: [.titled, .closable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        self.window = window
        window.title = locale.displayName; window.titleVisibility = .hidden; window.titlebarAppearsTransparent = true
        window.isReleasedWhenClosed = false
        window.delegate = messageHandler as? NSWindowDelegate
        window.backgroundColor = NSColor(srgbRed: 241/255, green: 234/255, blue: 223/255, alpha: 1)
        window.minSize = NSSize(width: min(640, available.width), height: min(420, available.height))
        window.setFrame(available, display: false)
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(messageHandler, name: "launcher")
        let nativeAppearance: [String: String] = ["locale": locale.identifier, "theme": theme]
        let nativeAppearanceJSON = (try? JSONSerialization.data(withJSONObject: nativeAppearance, options: [.sortedKeys]))
            .flatMap { String(data: $0, encoding: .utf8) } ?? "{\"locale\":\"en\",\"theme\":\"light\"}"
        configuration.userContentController.addUserScript(WKUserScript(
            source: "window.__agentSkinNativeMode = '\(mode)'; window.__agentSkinAppearance = Object.freeze(\(nativeAppearanceJSON));",
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        ))
        let webView = WKWebView(frame: window.contentView!.bounds, configuration: configuration)
        self.webView = webView
        webView.autoresizingMask = [.width, .height]; webView.navigationDelegate = navigationDelegate
        webView.underPageBackgroundColor = window.backgroundColor
        if #available(macOS 13.3, *), inspect { webView.isInspectable = true }
        window.contentView!.addSubview(webView)
    }
    func loadPlayer(page: URL, allowingReadAccessTo root: URL) {
        webView?.loadFileURL(page, allowingReadAccessTo: root)
    }

    func updateLabels(_ locale: NativeDisplayLocale) {
        appMenuItem?.title = locale.displayName
        quitMenuItem?.title = locale.quitTitle
        window?.title = locale.displayName
    }
    func showReady() {
        window?.level = .floating
        if let window { makeVisibleBody(window) }
        activateApp()
    }
    func setNormalLevel() { window?.level = .normal }
    func makeVisible() { if let window { makeVisibleBody(window) } }
    func orderOut() { window?.orderOut(nil) }
    func evaluateJavaScript(_ source: String, completion: ((Any?, Error?) -> Void)?) {
        guard let webView else { completion?(nil, CocoaError(.fileNoSuchFile)); return }
        webView.evaluateJavaScript(source, completionHandler: completion)
    }
    func fadeOut(duration: TimeInterval, completion: @escaping () -> Void) {
        guard let window else { completion(); return }
        NSAnimationContext.runAnimationGroup({ context in
            context.duration = duration
            window.animator().alphaValue = 0
        }, completionHandler: completion)
    }
    func schedule(after delay: TimeInterval, _ action: @escaping () -> Void) -> any NativeScheduledAction {
        NativeTimerAction(Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { _ in action() })
    }
    func takeSnapshot(_ completion: @escaping (NSImage?, Error?) -> Void) {
        guard let webView else { completion(nil, CocoaError(.fileNoSuchFile)); return }
        webView.takeSnapshot(with: nil, completionHandler: completion)
    }
    func stopLoading() { webView?.stopLoading() }
    func removeMessageHandler(named name: String) {
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: name)
    }
    func showError(title: String, message: String, closeTitle: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.addButton(withTitle: closeTitle)
        activateApp()
        runAlert(alert)
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    private let launcherID = "local.azhou.codex-startup", targetID = "com.openai.codex"
    private let runtime: any NativeAppRuntime
    private let args: [String]
    private let epoch: TimeInterval
    private let logLock = NSLock()
    private var presentation: (any NativePlayerPresentation)?
    private var displayLocale: NativeDisplayLocale
    private var webRoot: URL?, targetURL: URL?, target: (any NativeApplication)?
    private var logFile: FileHandle?, watchdog: (any NativeScheduledAction)?
    private var instanceLock: (any NativeInstanceLock)?
    private var lockFailureReason: String?
    private var ready = false, opening = false, requested = false, done = false
    private var terminating = false, failed = false, activated = false, promoted = false
    private var startupRequested = false, processExitCode: Int32 = 0
    private var startupEventStream: NativeStartupEventStream?
    private var startupCapture: NativeStartupCapture?
    private var smokeResultSucceeded = false
    private var snapshots: [any NativeScheduledAction] = []
    private var preview: Bool { !promoted && (args.contains("--preview") || args.contains("--smoke-test")) }
    private var smokeTest: Bool { args.contains("--smoke-test") }
    private lazy var nativeEventWriter = NativeEventWriter(
        startedAt: epoch,
        launcherPID: runtime.processIdentifier,
        launcherPath: real(runtime.bundleURL).path,
        sink: { [weak self] in self?.writeLogRecord($0) }
    )
    init(runtime: (any NativeAppRuntime)? = nil,
         presentation: (any NativePlayerPresentation)? = nil) {
        let runtime = runtime ?? SystemNativeAppRuntime()
        self.runtime = runtime
        self.args = runtime.arguments
        self.epoch = runtime.epoch
        self.displayLocale = runtime.systemFallbackLocale()
        self.presentation = presentation
        super.init()
    }
    private func option(_ key: String) -> String? {
        guard let i = args.firstIndex(of: key), i + 1 < args.count else { return nil }
        return args[i + 1]
    }
    private func real(_ url: URL) -> URL { url.resolvingSymlinksInPath().standardizedFileURL }
    private func updateNativeDisplayLabels() {
        presentation?.updateLabels(displayLocale)
    }
    private func windowGeometry() -> [String: Any] {
        presentation?.geometry ?? [:]
    }
    private func appInfo(_ app: (any NativeApplication)?) -> [String: Any] {
        guard let app else { return [:] }
        return ["pid": Int(app.processIdentifier), "bundleID": app.bundleIdentifier ?? "",
                "path": app.bundleURL.map { real($0).path } ?? "", "active": app.isActive,
                "hidden": app.isHidden, "terminated": app.isTerminated]
    }
    private func log(_ event: String, _ fields: [String: Any] = [:]) {
        var data = fields
        data["event"] = event
        data["seconds"] = ((runtime.uptime - epoch) * 1000).rounded() / 1000
        data["launcherPID"] = runtime.processIdentifier
        data["launcherPath"] = real(runtime.bundleURL).path
        writeLogRecord(data)
    }
    private func writeLogRecord(_ data: [String: Any]) {
        logLock.lock()
        defer { logLock.unlock() }
        guard let json = try? JSONSerialization.data(withJSONObject: data, options: [.sortedKeys, .withoutEscapingSlashes]),
              let line = String(data: json, encoding: .utf8) else { return }
        runtime.writeStandardOutput(line)
        try? logFile?.write(contentsOf: json + Data([10]))
    }
    private func beginStartupEvents() {
        guard startupEventStream == nil else { return }
        let stream = NativeStartupEventStream(writer: nativeEventWriter)
        startupEventStream = stream
        stream.begin(at: runtime.uptime)
    }
    private func logSmokeEvent(_ event: String, _ fields: [String: Any] = [:]) {
        guard smokeTest else { return }
        nativeEventWriter.emit(event, fields: fields)
    }
    private func validTarget(_ candidate: URL) -> URL? {
        let url = real(candidate)
        guard url.pathExtension.lowercased() == "app", url != real(runtime.bundleURL),
              !url.deletingLastPathComponent().pathComponents.contains(where: { $0.lowercased().hasSuffix(".app") }),
              let bundle = Bundle(url: url), bundle.bundleIdentifier == targetID,
              let executable = bundle.executableURL.map({ real($0) }),
              executable.path.hasPrefix(url.appendingPathComponent("Contents/MacOS").path + "/"),
              FileManager.default.isExecutableFile(atPath: executable.path) else { return nil }
        return url
    }
    private func resolveTarget() -> URL? {
        var candidates = runtime.runningApplications(bundleIdentifier: targetID).compactMap { $0.bundleURL }
        candidates += [URL(fileURLWithPath: "/Applications/ChatGPT.app"), URL(fileURLWithPath: "/Applications/Codex.app")]
        if let url = runtime.urlForApplication(bundleIdentifier: targetID) { candidates.append(url) }
        return candidates.compactMap { validTarget($0) }.first
    }
    private func targetForCurrentMode() -> URL? {
        StartupModePolicy.resolveTarget(arguments: args, promoted: promoted) { [weak self] in
            self?.resolveTarget()
        }
    }
    private func lockInstance() -> Bool {
        switch runtime.acquireInstanceLock(identifier: launcherID) {
        case .acquired(let lock):
            instanceLock = lock
            return true
        case .failed(let code):
            lockFailureReason = "protocol-error"
            log("lock-error", ["errno": Int(code)])
            return false
        case .busy:
            lockFailureReason = "startup-active"
            let existing = runtime.runningApplications(bundleIdentifier: launcherID)
                .first { $0.processIdentifier != runtime.processIdentifier && !$0.isTerminated }
            let result = existing?.activate() ?? false
            log("duplicate-entry", ["existing": appInfo(existing), "activationRequested": result])
            return false
        }
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        runtime.setAccessoryPolicy()
        if let path = StartupLogPolicy.filePath(arguments: args) {
            do {
                let url = URL(fileURLWithPath: path)
                try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
                if !FileManager.default.fileExists(atPath: path) { FileManager.default.createFile(atPath: path, contents: nil) }
                logFile = try FileHandle(forWritingTo: url); try logFile?.seekToEnd()
            } catch { print("LOG ERROR: \(error.localizedDescription)") }
        }
        if args.contains("--probe") {
            targetURL = targetForCurrentMode()
            nativeEventWriter.emitProbe(
                targetPath: targetURL?.path ?? "",
                targetBundleID: targetURL.flatMap { Bundle(url: $0)?.bundleIdentifier } ?? "",
                running: runtime.runningApplications(bundleIdentifier: targetID).map { appInfo($0) },
                frontmost: appInfo(runtime.frontmostApplication)
            )
            terminating = true; runtime.terminate(); return
        }
        if !preview { beginStartupEvents() }
        guard lockInstance() else {
            if let stream = startupEventStream {
                processExitCode = stream.resolve(.failed(reason: lockFailureReason ?? "protocol-error"),
                                                 observation: nil, at: runtime.uptime)?.exitCode ?? 1
            } else if smokeTest {
                failed = true
                processExitCode = 1
            }
            terminating = true; runtime.terminate(); return
        }
        if !preview {
            startTrustedSession()
            return
        }
        if smokeTest { logSmokeEvent("player-start", ["mode": "smoke"]) }
        else { log("player-start", ["mode": "preview", "targetPath": targetURL?.path ?? ""]) }
        if presentation == nil { presentation = AppKitNativePlayerPresentation() }
        let nativeMode = preview ? "preview" : "launch"
        presentation?.createPlayer(locale: displayLocale, mode: nativeMode, theme: runtime.appearanceTheme(),
                                   inspect: args.contains("--inspect"), messageHandler: self, navigationDelegate: self)
        guard let resources = runtime.resourceURL else { fail(displayLocale.message(for: "resources-missing"), "resources-missing"); return }
        let root = resources.appendingPathComponent("web", isDirectory: true)
        webRoot = real(root)
        let page = root.appendingPathComponent("index.html")
        guard FileManager.default.fileExists(atPath: page.path) else { fail(displayLocale.message(for: "page-missing"), "page-missing"); return }
        // Keep the window invisible until the renderer reports decoded assets.
        presentation?.loadPlayer(page: page, allowingReadAccessTo: root)
        armWatchdog(20, "renderer-ready-timeout")
        log("window-created", windowGeometry())
    }
    private func armWatchdog(_ seconds: Double, _ reason: String) {
        watchdog?.cancel()
        watchdog = presentation?.schedule(after: seconds) { [weak self] in
            guard let self, !self.terminating else { return }
            let failureReason = self.done ? "target-launch-timeout" : reason
            self.fail(self.displayLocale.message(for: failureReason), failureReason)
        }
    }
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        receivePlayerMessage(body: message.body, isMainFrame: message.frameInfo.isMainFrame)
    }

    func receivePlayerMessage(body: Any, isMainFrame: Bool) {
        guard isMainFrame, !terminating else { return }
        let rawBody = body
        let body = rawBody as? [String: Any] ?? [:]
        let action = rawBody as? String ?? body["action"] as? String ?? ""
        switch action {
        case "ready":
            guard !ready else { log("duplicate-ready-ignored"); return }
            if let locale = NativeDisplayLocale.verifiedReadyLocale(body["locale"]) {
                displayLocale = locale
                updateNativeDisplayLabels()
            }
            ready = true
            let milliseconds = (body["duration"] as? NSNumber)?.doubleValue ?? 0
            let duration = milliseconds.isFinite && milliseconds > 0 ? milliseconds / 1000 : 0
            presentation?.showReady()
            presentation?.evaluateJavaScript(preview ? "window.launcherUI.replay()" : "window.launcherUI.beginLaunch()") { [weak self] _, error in
                guard let self, !self.terminating else { return }
                if let error { self.fail(error.localizedDescription, "playback-start-error"); return }
                if self.smokeTest { self.logSmokeEvent("playback-start", ["durationSeconds": duration]) }
                else { self.log("playback-start", ["durationSeconds": duration, "window": self.windowGeometry()]) }
                self.armWatchdog(max(25, duration + 12), "renderer-complete-timeout")
                self.scheduleSnapshots(duration)
                if !self.preview { self.startTrustedSession() }
            }
        case "complete":
            guard ready, !done, !failed else { return }
            done = true
            if smokeTest { logSmokeEvent("animation-complete") }
            else { log("animation-complete", ["report": body["report"] ?? [:]]) }
            if preview {
                watchdog?.cancel()
                let completionSkipped = body["skipped"]
                // Native preview is deliberately one-shot: it cannot retain the
                // application's identity and accidentally swallow a later launch.
                presentation?.evaluateJavaScript("JSON.stringify(window.launcherUI.report())") { [weak self] result, error in
                    guard let self else { return }
                    let succeeded: Bool
                    if self.smokeTest {
                        succeeded = NativeSmokeReportValidator.isSuccessfulCompletion(
                            skipped: completionSkipped,
                            reportJSON: result as? String,
                            evaluationFailed: error != nil
                        )
                    } else {
                        succeeded = error == nil && (result as? String)?.isEmpty == false
                    }
                    if self.smokeTest {
                        self.smokeResultSucceeded = succeeded
                        if !succeeded { self.failed = true; self.processExitCode = 1 }
                        self.logSmokeEvent("preview-result", ["success": succeeded])
                    } else {
                        self.log("preview-result", ["success": succeeded,
                                                     "measurementScope": "front-end JS/rAF only, not GPU/presentation timing"])
                    }
                    self.terminating = true; self.runtime.terminate()
                }
            } else { finishIfReady("animation-complete") }
        case "close":
            if smokeTest && !smokeResultSucceeded { failed = true; processExitCode = 1 }
            if startupEventStream?.isPending == true { startupEventStream?.latchInterruption() }
            terminating = true; runtime.terminate()
        case "jsError": fail(displayLocale.message(for: "javascript-error"), "javascript-error")
        case "assetError": fail(displayLocale.message(for: "asset-error"), "asset-error")
        default: log("unhandled-message", ["action": action])
        }
    }
    private func startupFacts(_ app: any NativeApplication) throws -> StartupTargetFacts {
        guard !app.isTerminated, let bundle = app.bundleURL, let executable = app.executableURL,
              let bundleID = app.bundleIdentifier else {
            throw StartupFailure(reason: "target-identity", message: "系统没有返回完整的 Codex 进程身份。")
        }
        return StartupTargetFacts(pid: app.processIdentifier, bundle: real(bundle), executable: real(executable),
                                  bundleID: bundleID, launchTime: app.launchTime)
    }

    private func startupPayload() throws -> String {
        guard let resources = runtime.resourceURL else {
            throw StartupFailure(reason: "asset-invalid", message: "缺少 Agent Skin 资源目录；本次不会启动或注入 Codex。")
        }
        let root = real(resources)
        let source = root.appendingPathComponent("startup/install.js")
        guard source.path.hasPrefix(root.path + "/"),
              (try? source.resourceValues(forKeys: [.isSymbolicLinkKey, .isRegularFileKey]).isSymbolicLink) != true,
              (try? source.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true,
              let bytes = try? Data(contentsOf: source), !bytes.isEmpty, bytes.count < 24 * 1024 * 1024,
              let text = String(data: bytes, encoding: .utf8) else {
            throw StartupFailure(reason: "asset-invalid", message: "缺少有效的 startup/install.js 生产载荷；本次不会启动或注入 Codex。")
        }
        return text
    }

    @MainActor
    private func startTrustedSession() {
        guard !startupRequested, !terminating else { return }
        beginStartupEvents()
        startupRequested = true; requested = true
        targetURL = targetForCurrentMode()
        guard let url = targetURL, validTarget(url) == url else {
            finishStartup(.failed(reason: "target-missing"), promoted: promoted); return
        }
        guard let expectedApplication = startupHostKey(for: url) else {
            finishStartup(.failed(reason: "target-identity"), promoted: promoted); return
        }
        let running = runtime.runningApplications(bundleIdentifier: targetID).filter { !$0.isTerminated }
        let matching = running.filter { $0.bundleURL.map({ real($0) }) == url }
        guard running.isEmpty || (running.count == 1 && matching.count == 1) else {
            finishStartup(.failed(reason: "target-identity"), promoted: promoted); return
        }
        Task { @MainActor [weak self] in
            guard let self else { return }
            let result = await self.launchThroughSkinHost(expectedApplication: expectedApplication)
            self.opening = false
            self.finishStartup(startupLegacyOutcome(from: result), promoted: self.promoted)
        }
    }

    /// Installation identity for the verified target bundle. The executable hash
    /// stays an explicit empty placeholder in C0: this chain attests identity via
    /// codesign validation inside each operation branch and never fabricates a
    /// digest it did not compute.
    private func startupHostKey(for url: URL) -> HostApplicationKey? {
        guard let bundle = Bundle(url: url), let bundleID = bundle.bundleIdentifier,
              let executable = bundle.executableURL.map({ real($0) }),
              executable.path.hasPrefix(real(url).appendingPathComponent("Contents/MacOS").path + "/") else { return nil }
        let info = bundle.infoDictionary ?? [:]
        return HostApplicationKey(
            host: .codex, bundleURL: real(url), executableURL: executable,
            bundleIdentifier: bundleID,
            version: (info["CFBundleShortVersionString"] as? String) ?? "",
            build: (info["CFBundleVersion"] as? String) ?? "",
            executableSHA256: "")
    }

    /// Honest per-capability evidence for the shipped Codex chain. Each entry keeps
    /// .verified only where a named, real verification source exists: the launcher's
    /// own live observation for identity, and the specific regression suites that
    /// exercise each capability. Nothing here claims codesign — signature validation
    /// runs inside the preflight/validate branches, not at assembly time. ZCode must
    /// supply its own independently verified findings before a driver exists.
    private func codexCapabilityFindings(for key: HostApplicationKey,
                                         contractVersion: String) -> [CapabilityFinding] {
        let evidence: [SkinCapability: (IDs: [String], reason: String)] = [
            .applicationIdentity: (["workspace-bundle-identity", "tools/test-startup-native.py"],
                                   "identity observed this launch from the verified target bundle and workspace"),
            .activateExistingApplication: (["tools/test-startup-native.py"],
                                           "hot-branch validate→activate order and activation result checks"),
            .mainWindowAttachment: (["tools/test-startup-native.py"],
                                    "connector attach with single main-page selection and port ownership"),
            .mainPageIdentification: (["tools/test-startup-native.py", "tools/test-startup-browser.mjs"],
                                      "main-page identification against injected and real pages"),
            .ownedAppearanceSurface: (["tools/startup.test.mjs", "tools/test-startup-browser.mjs"],
                                      "appearance tokens, entry mounting and fallback placement"),
            .persistentSettings: (["tools/settings-save.unit.test.mjs", "tools/image-settings.test.mjs"],
                                  "IndexedDB save/apply two-phase transactions and namespace contract"),
            .lifecycleInvalidation: (["tools/startup.test.mjs"],
                                     "dispose generation invalidation; late callbacks cannot revive a run"),
            .ownedResourceRemoval: (["Native/WallpaperValidationTests.swift", "tools/startup.test.mjs"],
                                    "owned controller disposal via restore/retry receipts"),
        ]
        return SkinCapability.allCases.map { capability in
            let entry = evidence[capability] ?? ([], "no recorded evidence for this capability")
            return CapabilityFinding(
                subject: CapabilityEvidenceSubject(
                    application: key, surface: SkinHostContract.surface(for: capability),
                    contractVersion: contractVersion),
                capability: capability,
                state: entry.IDs.isEmpty ? .unverified : .verified,
                evidenceIDs: entry.IDs, reason: entry.reason)
        }
    }

    /// Assembles the shared skin host factory and runs the Codex driver. The
    /// hot/cold branch strategy moved verbatim into CodexSkinDriver; this method
    /// only binds identity, evidence and the App-owned assembly ports.
    @MainActor
    private func launchThroughSkinHost(expectedApplication: HostApplicationKey) async -> SkinLaunchResult {
        let contractVersion = SkinHostContract.version
        // Workspace-observed identity only: codesign has not run at assembly time;
        // signature validation happens inside the preflight/validate branches.
        let observed = HostIdentityEvidence(key: expectedApplication,
                                            signingIdentity: "workspace-observed; codesign validated per operation branch",
                                            evidenceID: "workspace-bundle-identity")
        let installObservation = CodexInstallObservation()
        let system = runtime.makeStartupTargetSystem()
        let budget = StartupBudget(startedAt: runtime.uptime)
        let runtime = self.runtime
        let assembly = CodexSkinAssembly(
            preflightBundle: { bundle, startupBudget in
                do { try system.preflightBundle(bundle, deadline: startupBudget.preflightDeadline) }
                catch let error as WallpaperFailure where error.state == "inspection-timeout" {
                    throw StartupFailure(reason: "attach-timeout", message: "Codex 签名预检未能在启动预算内完成。")
                } catch let error as WallpaperFailure where error.state == "signature-refused" {
                    throw StartupFailure(reason: "target-identity", message: "Codex 应用未通过 OpenAI 应用签名核验。")
                } catch {
                    throw error
                }
            },
            activateExisting: { [weak self] facts in
                guard let self else {
                    throw StartupFailure(reason: "target-identity", message: "启动入口已结束。")
                }
                guard let app = self.runtime.application(processIdentifier: facts.pid), !app.isTerminated,
                      app.bundleIdentifier == facts.bundleID,
                      app.bundleURL.map({ self.real($0) }) == facts.bundle,
                      app.executableURL.map({ self.real($0) }) == facts.executable,
                      app.launchTime == facts.launchTime else {
                    throw StartupFailure(reason: "target-identity", message: "已核验的 Codex 进程发生变化。")
                }
                self.target = app
                let activated = app.activate()
                self.activated = activated
                return activated
            },
            preparePort: { [weak self] in
                guard let self else { throw StartupFailure(reason: "listener-mismatch", message: "启动入口已结束。") }
                return try self.prepareStartupPort()
            },
            openApplication: { [weak self] url, port, deadline, openSystem in
                guard let self else { throw StartupFailure(reason: "target-identity", message: "启动入口已结束。") }
                return try await self.openCodex(url, port: port, deadline: deadline, system: openSystem)
            },
            onTargetOpened: { [weak self] app in self?.target = app },
            onCaptureReady: { [weak self] capture in self?.startupCapture = capture },
            eventStream: { [weak self] in self?.startupEventStream },
            onOpeningChanged: { [weak self] value in self?.opening = value },
            startupFacts: { [weak self] app in
                guard let self else { throw StartupFailure(reason: "target-identity", message: "启动入口已结束。") }
                return try self.startupFacts(app)
            },
            performDisable: nil)
        let dependencies = SkinAssemblyDependencies(
            // This launcher path never probes identities through the dependency: it
            // observes the verified target bundle directly. Report that honestly
            // instead of fabricating an observation no caller made.
            inspectIdentity: { host, _ in
                .unavailable(HostRefusal(
                    host: host, reason: .identityUnavailable, findings: [],
                    detail: "the launcher observes the verified target bundle directly; no separate identity probe is wired",
                    nextProbe: nil))
            },
            capabilityEvidence: { [weak self] evidence in
                self?.codexCapabilityFindings(for: evidence.key, contractVersion: contractVersion) ?? []
            },
            makeCodexDriver: { inputs in
                CodexSkinDriver(
                    inputs: inputs, runtime: runtime,
                    readPayload: { [weak self] in
                        guard let self else { throw StartupFailure(reason: "asset-invalid", message: "启动入口已结束。") }
                        return try self.startupPayload()
                    },
                    makeTargetSystem: { runtime.makeStartupTargetSystem() },
                    makeConnector: { facts, port, connectorSystem, capture, events in
                        StartupConnector(
                            target: facts, expectedPort: port, system: connectorSystem,
                            transport: InstallObservingStartupTransport(
                                base: runtime.makeStartupTransport(capture: capture, events: events),
                                recorder: installObservation))
                    },
                    installObservation: installObservation, assembly: assembly)
            },
            makeZCodeDriver: nil) // No verified ZCode entry exists; C0 never fakes one.
        switch SkinHostFactory.make(host: .codex,
                                    expectedApplication: expectedApplication,
                                    observed: observed,
                                    findings: codexCapabilityFindings(for: expectedApplication,
                                                                      contractVersion: contractVersion),
                                    contractVersion: contractVersion,
                                    dependencies: dependencies) {
        case .unavailable(let refusal):
            return .refused(refusal)
        case .ready(let driver):
            return await driver.launch(
                SkinLaunchRequest(expectedApplication: expectedApplication, operationID: UUID(),
                                  startedAt: budget.startedAt, deadline: budget.totalDeadline))
        }
    }

    private func prepareStartupPort() throws -> Int {
        do {
            let port = try runtime.allocateLoopbackPort()
            log("startup-port-selected", ["port": port, "requiresTargetListenerVerification": true])
            return port
        } catch let error as NativeLoopbackPortError {
            if let stream = startupEventStream {
                stream.portError(operation: error.operation, errno: error.code, at: runtime.uptime)
            } else {
                nativeEventWriter.emit("startup-port-error", fields: ["reason": "listener-mismatch",
                                                                        "operation": error.operation, "errno": Int(error.code)])
            }
            throw StartupFailure(reason: "listener-mismatch", message: "未能准备 Codex 本机回环调试端口。")
        } catch {
            throw StartupFailure(reason: "listener-mismatch", message: "未能准备 Codex 本机回环调试端口。")
        }
    }

    private func openCodex(_ url: URL, port: Int, deadline: TimeInterval,
                           system: any StartupTargetSystem) async throws -> any NativeApplication {
        try await Self.openTargetApplication(runtime: runtime, targetBundleID: targetID, url: url,
                                             port: port, deadline: deadline, system: system,
                                             log: { [weak self] event, fields in self?.log(event, fields) })
    }

    /// Shared bounded application-open routine (same order and failures as the
    /// previous inline implementation, extracted so contract tests drive the
    /// identical path).
    @MainActor
    static func openTargetApplication(
        runtime: any NativeAppRuntime, targetBundleID: String, url: URL, port: Int,
        deadline: TimeInterval, system: any StartupTargetSystem,
        log: @escaping (String, [String: Any]) -> Void
    ) async throws -> any NativeApplication {
        let openTimeout = try StartupBudget.boundedTimeout(
            maximum: 45, stageDeadline: deadline, totalDeadline: deadline,
            now: runtime.uptime
        )
        return try await withCheckedThrowingContinuation { continuation in
            let waiter = StartupApplicationWaiter(continuation)
            let timeout = DispatchWorkItem {
                waiter.finish(.failure(StartupFailure(reason: "attach-timeout", message: "Codex 启动接入超过当前阶段预算。")))
            }
            waiter.setTimeout(timeout)
            DispatchQueue.main.asyncAfter(deadline: .now() + openTimeout, execute: timeout)
            log("target-open-request", ["path": url.path, "bundleID": targetBundleID, "debuggingPort": port])
            runtime.openApplication(at: url, debuggingPort: port) { app, error in
                DispatchQueue.main.async {
                    guard runtime.uptime < deadline else {
                        waiter.finish(.failure(StartupFailure(reason: "attach-timeout", message: "Codex 启动接入超过当前阶段预算。")))
                        return
                    }
                    if error != nil {
                        waiter.finish(.failure(StartupFailure(reason: "target-missing", message: "Codex 启动失败。")))
                        return
                    }
                    guard let app, !app.isTerminated, let bundle = app.bundleURL, let executable = app.executableURL,
                          let bundleID = app.bundleIdentifier,
                          bundle.resolvingSymlinksInPath().standardizedFileURL == url,
                          bundleID == targetBundleID else {
                        waiter.finish(.failure(StartupFailure(reason: "target-identity", message: "系统返回的应用与核验路径不符。")))
                        return
                    }
                    do {
                        try system.validate(
                            StartupTargetFacts(pid: app.processIdentifier,
                                               bundle: bundle.resolvingSymlinksInPath().standardizedFileURL,
                                               executable: executable.resolvingSymlinksInPath().standardizedFileURL,
                                               bundleID: bundleID, launchTime: app.launchTime),
                            deadline: deadline)
                        waiter.finish(.success(app))
                    } catch let error as StartupFailure where error.reason == "attach-timeout" {
                        waiter.finish(.failure(error))
                    } catch let error as WallpaperFailure where error.state == "inspection-timeout" {
                        waiter.finish(.failure(StartupFailure(reason: "attach-timeout", message: "Codex 进程核验超过当前阶段预算。")))
                    } catch {
                        waiter.finish(.failure(StartupFailure(reason: "target-identity", message: "Codex 进程或签名核验未通过。")))
                    }
                }
            }
        }
    }

    private func finishStartup(_ outcome: StartupOutcome, promoted: Bool) {
        beginStartupEvents()
        guard let final = startupEventStream?.resolve(
            outcome, observation: startupCapture?.snapshot(), at: runtime.uptime
        ) else { return }
        processExitCode = final.exitCode
        switch final {
        case .activated:
            break
        case .ready:
            if let target, !target.isTerminated {
                activated = target.activate()
                log("target-activation-after-startup", ["allowed": activated, "targetPID": Int(target.processIdentifier)])
            }
        case .skipped:
            if let target, !target.isTerminated { activated = target.activate() }
        case .partial(let reason), .behaviorNotProven(let reason):
            if promoted { fail(startupMessage(reason), reason) }
            else { terminating = true; runtime.terminate() }
            return
        }
        if promoted {
            if done { finishIfReady("startup-ready") }
            return
        }
        terminating = true
        runtime.terminate()
    }

    private func startupMessage(_ reason: String) -> String {
        displayLocale.message(for: reason)
    }
    @discardableResult
    private func activateOnce(_ reason: String) -> Bool {
        if activated { return true }
        guard let target, !target.isTerminated else { return false }
        let result = target.activate()
        activated = result
        log("target-activation-request", ["reason": reason, "allowed": result, "target": appInfo(target)])
        return result
    }
    private func finishIfReady(_ reason: String) {
        guard done, !preview, !terminating, !failed else { return }
        if let target, target.isTerminated { fail(displayLocale.message(for: "target-exited"), "target-exited"); return }
        guard !opening, let target, !target.isTerminated else {
            presentation?.evaluateJavaScript("window.launcherUI.waiting()", completion: nil)
            log("waiting-for-target"); return
        }
        guard activateOnce(reason) else {
            fail(displayLocale.message(for: "activation-rejected"), "activation-rejected"); return
        }
        terminating = true; watchdog?.cancel(); snapshots.forEach { $0.cancel() }
        log("handoff-fade-start", ["frontmost": appInfo(runtime.frontmostApplication)])
        presentation?.fadeOut(duration: 0.28) {
            self.log("handoff-fade-complete", ["frontmost": self.appInfo(self.runtime.frontmostApplication), "target": self.appInfo(self.target)])
            self.presentation?.orderOut(); self.runtime.terminate()
        }
    }
    private func fail(_ message: String, _ reason: String) {
        guard !failed, !terminating else { return }; failed = true
        watchdog?.cancel(); snapshots.forEach { $0.cancel() }; presentation?.setNormalLevel()
        log("failure", ["reason": reason, "targetPID": target.map { Int($0.processIdentifier) } ?? 0])
        if smokeTest {
            processExitCode = 1
            terminating = true; runtime.terminate(); return
        }
        if startupRequested { startupEventStream?.latchFailure(reason) }
        if ready, let data = try? JSONSerialization.data(withJSONObject: [message]), let json = String(data: data, encoding: .utf8) {
            presentation?.makeVisible()
            presentation?.evaluateJavaScript("window.launcherUI.error(\(json)[0])") { [weak self] _, error in
                if error != nil { self?.nativeError(message) }
            }
        } else { nativeError(message) }
    }
    private func nativeError(_ message: String) {
        presentation?.showError(title: displayLocale.displayName, message: message, closeTitle: displayLocale.closeTitle)
        terminating = true; runtime.terminate()
    }
    private func scheduleSnapshots(_ duration: Double) {
        guard let directory = option("--snapshot") else { return }
        do { try FileManager.default.createDirectory(atPath: directory, withIntermediateDirectories: true) }
        catch { log("snapshot-error", ["message": error.localizedDescription]); return }
        let times = (option("--snapshot-times") ?? "0.4,1.4,2.3,3.5,5.5,7.3").split(separator: ",").compactMap { Double($0) }
        for (i, seconds) in times.enumerated() where seconds.isFinite && seconds >= 0 && (duration == 0 || seconds < duration) {
            let work = presentation?.schedule(after: seconds) { [weak self] in
                guard let self, !self.terminating else { return }
                let base = URL(fileURLWithPath: directory).appendingPathComponent(String(format: "%02d-%.2fs", i + 1, seconds))
                self.presentation?.evaluateJavaScript("JSON.stringify(window.launcherUI.report())") { result, _ in
                    if let report = result as? String { try? report.write(to: base.appendingPathExtension("json"), atomically: true, encoding: .utf8) }
                }
                self.presentation?.takeSnapshot { [weak self] image, error in
                    guard let data = image?.tiffRepresentation, let bitmap = NSBitmapImageRep(data: data),
                          let png = bitmap.representation(using: .png, properties: [:]) else {
                        self?.log("snapshot-error", ["message": error?.localizedDescription ?? "no image"]); return
                    }
                    do { try png.write(to: base.appendingPathExtension("png")); self?.log("snapshot-saved", ["path": base.path + ".png", "scheduledSeconds": seconds]) }
                    catch { self?.log("snapshot-error", ["message": error.localizedDescription]) }
                }
            }
            if let work { snapshots.append(work) }
        }
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        guard !terminating else { return false }
        if ready || failed { presentation?.makeVisible() }
        log("reopen-existing-player", ["launchRequested": requested, "completed": done])
        if preview && !done && !failed && !args.contains("--smoke-test") {
            promoted = true
            guard ready else { log("preview-launch-pending"); return false }
            presentation?.evaluateJavaScript("window.launcherUI.promoteLaunch()") { [weak self] _, error in
                guard let self else { return }
                if let error { self.fail(error.localizedDescription, "preview-promotion-error"); return }
                self.log("preview-promoted-to-launch"); self.startTrustedSession()
            }
        }
        return false
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if preview || failed {
            if smokeTest && !smokeResultSucceeded { failed = true; processExitCode = 1 }
            if startupEventStream?.isPending == true { startupEventStream?.latchInterruption() }
            terminating = true; runtime.terminate()
        }
        else { done = true; log("window-close-as-skip"); finishIfReady("window-close") }
        return false
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if !terminating {
            if smokeTest && !smokeResultSucceeded { failed = true; processExitCode = 1 }
            if startupEventStream?.isPending == true { startupEventStream?.latchInterruption() }
            else if !preview && !failed { activateOnce("user-quit") }
            terminating = true
        }
        return .terminateNow
    }
    func applicationWillTerminate(_ notification: Notification) {
        watchdog?.cancel(); snapshots.forEach { $0.cancel() }
        if smokeTest {
            if !smokeResultSucceeded { failed = true; processExitCode = max(processExitCode, 1) }
            logSmokeEvent("player-terminated", ["completed": done && smokeResultSucceeded && !failed,
                                                 "failed": failed || !smokeResultSucceeded])
        } else {
            log("player-terminated", ["failed": failed, "completed": done, "frontmost": appInfo(runtime.frontmostApplication)])
            if let final = startupEventStream?.finish(at: runtime.uptime) {
                processExitCode = final.exitCode
            }
        }
        presentation?.stopLoading(); presentation?.removeMessageHandler(named: "launcher")
        instanceLock?.release(); instanceLock = nil
        try? logFile?.close()
        if processExitCode != 0 { runtime.exit(code: processExitCode) }
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url, url.isFileURL, let root = webRoot else { decisionHandler(.cancel); return }
        decisionHandler(real(url).path.hasPrefix(root.path + "/") ? .allow : .cancel)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { fail(error.localizedDescription, "navigation-error") }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { fail(error.localizedDescription, "navigation-error") }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { fail(displayLocale.message(for: "renderer-terminated"), "renderer-terminated") }
}
/// Maps a shared skin host launch result back onto the existing StartupOutcome
/// contract. Old consumers must never receive unrecognized reasons, so refusal
/// reasons fold into the two existing failure identities and every failure or
/// partial keeps its exact legacy reason string in `detail`.
func startupLegacyOutcome(from result: SkinLaunchResult) -> StartupOutcome {
    switch result {
    case .activated(let generation): return .activated(pid: generation.pid)
    case .ready(_, let runID): return .ready(runID: runID)
    case .skipped(_, let runID, let beforeReady): return .skipped(runID: runID, beforeReady: beforeReady)
    case .partial(let failure, _, _): return .partial(reason: failure.detail)
    case .failed(let failure, _, _): return .failed(reason: failure.detail)
    case .refused(let refusal):
        switch refusal.reason {
        case .identityUnavailable, .identityMismatch, .capabilityUnverified:
            return .failed(reason: "target-identity")
        case .evidenceMismatch, .implementationUnavailable, .capabilityUnsupported:
            return .failed(reason: "protocol-error")
        }
    }
}

#if !AGENT_SKIN_NATIVE_EVENT_TESTS
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
#endif
