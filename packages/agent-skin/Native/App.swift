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
                  ["natural", "skip", "settings-cancel"].contains(cause),
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
    private var continuation: CheckedContinuation<NSRunningApplication, Error>?
    private var completed = false
    private var timeout: DispatchWorkItem?

    init(_ continuation: CheckedContinuation<NSRunningApplication, Error>) {
        self.continuation = continuation
    }

    func setTimeout(_ timeout: DispatchWorkItem) {
        lock.lock()
        if completed { lock.unlock(); timeout.cancel(); return }
        self.timeout = timeout
        lock.unlock()
    }

    func finish(_ result: Result<NSRunningApplication, Error>) {
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
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    private let launcherID = "local.azhou.codex-startup", targetID = "com.openai.codex"
    private let args = CommandLine.arguments
    private let epoch = ProcessInfo.processInfo.systemUptime
    private let logLock = NSLock()
    private var window: NSWindow!, webView: WKWebView!
    private var webRoot: URL?, targetURL: URL?, target: NSRunningApplication?
    private var logFile: FileHandle?, watchdog: Timer?
    private var lockFD: Int32 = -1
    private var lockFailureReason: String?
    private var ready = false, opening = false, requested = false, done = false
    private var terminating = false, failed = false, activated = false, promoted = false
    private var startupRequested = false, processExitCode: Int32 = 0
    private var startupEventStream: NativeStartupEventStream?
    private var startupCapture: NativeStartupCapture?
    private var smokeResultSucceeded = false
    private var snapshots: [DispatchWorkItem] = []
    private var preview: Bool { !promoted && (args.contains("--preview") || args.contains("--smoke-test")) }
    private var smokeTest: Bool { args.contains("--smoke-test") }
    private lazy var nativeEventWriter = NativeEventWriter(
        startedAt: epoch,
        launcherPID: Int(ProcessInfo.processInfo.processIdentifier),
        launcherPath: real(Bundle.main.bundleURL).path,
        sink: { [weak self] in self?.writeLogRecord($0) }
    )
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
        writeLogRecord(data)
    }
    private func writeLogRecord(_ data: [String: Any]) {
        logLock.lock()
        defer { logLock.unlock() }
        guard let json = try? JSONSerialization.data(withJSONObject: data, options: [.sortedKeys, .withoutEscapingSlashes]),
              let line = String(data: json, encoding: .utf8) else { return }
        print(line); fflush(stdout)
        try? logFile?.write(contentsOf: json + Data([10]))
    }
    private func beginStartupEvents() {
        guard startupEventStream == nil else { return }
        let stream = NativeStartupEventStream(writer: nativeEventWriter)
        startupEventStream = stream
        stream.begin(at: ProcessInfo.processInfo.systemUptime)
    }
    private func logSmokeEvent(_ event: String, _ fields: [String: Any] = [:]) {
        guard smokeTest else { return }
        nativeEventWriter.emit(event, fields: fields)
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
    private func targetForCurrentMode() -> URL? {
        StartupModePolicy.resolveTarget(arguments: args, promoted: promoted) { [weak self] in
            self?.resolveTarget()
        }
    }
    private func lockInstance() -> Bool {
        let path = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("\(launcherID)-\(getuid()).lock").path
        lockFD = Darwin.open(path, O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, S_IRUSR | S_IWUSR)
        guard lockFD >= 0 else {
            lockFailureReason = "protocol-error"
            log("lock-error", ["errno": errno])
            return false
        }
        guard flock(lockFD, LOCK_EX | LOCK_NB) == 0 else {
            lockFailureReason = "startup-active"
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
            log("probe", ["launcherPath": real(Bundle.main.bundleURL).path, "targetPath": targetURL?.path ?? "",
                          "targetBundleID": targetURL.flatMap { Bundle(url: $0)?.bundleIdentifier } ?? "",
                          "running": NSRunningApplication.runningApplications(withBundleIdentifier: targetID).map { appInfo($0) },
                          "frontmost": appInfo(NSWorkspace.shared.frontmostApplication)])
            terminating = true; NSApp.terminate(nil); return
        }
        if !preview { beginStartupEvents() }
        guard lockInstance() else {
            if let stream = startupEventStream {
                processExitCode = stream.resolve(.failed(reason: lockFailureReason ?? "protocol-error"),
                                                 observation: nil, at: ProcessInfo.processInfo.systemUptime)?.exitCode ?? 1
            } else if smokeTest {
                failed = true
                processExitCode = 1
            }
            terminating = true; NSApp.terminate(nil); return
        }
        if !preview {
            startTrustedSession()
            return
        }
        if smokeTest { logSmokeEvent("player-start", ["mode": "smoke"]) }
        else { log("player-start", ["mode": "preview", "targetPath": targetURL?.path ?? ""]) }
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
        let nativeMode = preview ? "preview" : "launch"
        configuration.userContentController.addUserScript(WKUserScript(
            source: "window.__agentSkinNativeMode = '\(nativeMode)';",
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        ))
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
                watchdog?.invalidate()
                let completionSkipped = body["skipped"]
                // Native preview is deliberately one-shot: it cannot retain the
                // application's identity and accidentally swallow a later launch.
                webView.evaluateJavaScript("JSON.stringify(window.launcherUI.report())") { [weak self] result, error in
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
                    self.terminating = true; NSApp.terminate(nil)
                }
            } else { finishIfReady("animation-complete") }
        case "close":
            if smokeTest && !smokeResultSucceeded { failed = true; processExitCode = 1 }
            if startupEventStream?.isPending == true { startupEventStream?.latchInterruption() }
            terminating = true; NSApp.terminate(nil)
        case "jsError": fail(body["message"] as? String ?? "动画脚本运行失败。", "javascript-error")
        case "assetError": fail(body["message"] as? String ?? "阿舟素材加载失败，请检查本地私有素材并重新构建。", "asset-error")
        default: log("unhandled-message", ["action": action])
        }
    }
    private func startupFacts(_ app: NSRunningApplication) throws -> StartupTargetFacts {
        guard !app.isTerminated, let bundle = app.bundleURL, let executable = app.executableURL,
              let bundleID = app.bundleIdentifier else {
            throw StartupFailure(reason: "target-identity", message: "系统没有返回完整的 Codex 进程身份。")
        }
        return StartupTargetFacts(pid: app.processIdentifier, bundle: real(bundle), executable: real(executable),
                                  bundleID: bundleID, launchTime: app.launchDate?.timeIntervalSince1970)
    }

    private func startupPayload() throws -> String {
        guard let resources = Bundle.main.resourceURL else {
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
        let running = NSRunningApplication.runningApplications(withBundleIdentifier: targetID).filter { !$0.isTerminated }
        let matching = running.filter { $0.bundleURL.map({ real($0) }) == url }
        guard running.isEmpty || (running.count == 1 && matching.count == 1) else {
            finishStartup(.failed(reason: "target-identity"), promoted: promoted); return
        }
        let existing: StartupTargetFacts?
        if let app = matching.first {
            guard let facts = try? startupFacts(app) else {
                finishStartup(.failed(reason: "target-identity"), promoted: promoted); return
            }
            existing = facts
        } else { existing = nil }

        let system = CodexStartupTargetSystem()
        let budget = StartupBudget(startedAt: ProcessInfo.processInfo.systemUptime)
        Task { @MainActor [weak self] in
            guard let self else { return }
            let outcome: StartupOutcome
            do {
                outcome = try await StartupLaunchFlow.run(
                    existing: existing,
                    preflightBundle: {
                        do { try system.preflightBundle(url, deadline: budget.preflightDeadline) }
                        catch let error as WallpaperFailure where error.state == "inspection-timeout" {
                            throw StartupFailure(reason: "attach-timeout", message: "Codex 签名预检未能在启动预算内完成。")
                        } catch let error as WallpaperFailure where error.state == "signature-refused" {
                            throw StartupFailure(reason: "target-identity", message: "Codex 应用未通过 OpenAI 应用签名核验。")
                        } catch {
                            throw error
                        }
                    },
                    validate: { try system.validate($0, deadline: budget.preflightDeadline) },
                    activate: { facts in
                        guard let app = NSRunningApplication(processIdentifier: facts.pid), !app.isTerminated,
                              app.bundleIdentifier == facts.bundleID,
                              app.bundleURL.map({ self.real($0) }) == facts.bundle,
                              app.executableURL.map({ self.real($0) }) == facts.executable,
                              app.launchDate?.timeIntervalSince1970 == facts.launchTime else {
                            throw StartupFailure(reason: "target-identity", message: "已核验的 Codex 进程发生变化。")
                        }
                        self.target = app
                        let activated = app.activate(options: [])
                        self.activated = activated
                        return activated
                    },
                    coldStart: {
                        let payload = try self.startupPayload()
                        guard ProcessInfo.processInfo.systemUptime < budget.totalDeadline else {
                            throw StartupFailure(reason: "attach-timeout", message: "Codex 启动已超过 60 秒总预算。")
                        }
                        let port = try self.prepareStartupPort()
                        let attachDeadline = budget.attachDeadline(startedAt: ProcessInfo.processInfo.systemUptime)
                        self.opening = true
                        let app = try await self.openCodex(url, port: port, deadline: attachDeadline, system: system)
                        self.opening = false
                        self.target = app
                        let facts = try self.startupFacts(app)
                        let capture = NativeStartupCapture(targetPID: facts.pid)
                        self.startupCapture = capture
                        self.startupEventStream?.targetOpened(pid: facts.pid, at: ProcessInfo.processInfo.systemUptime)
                        guard let eventStream = self.startupEventStream else {
                            throw StartupFailure(reason: "protocol-error", message: "原生启动事件流不可用。")
                        }
                        return await StartupConnector(target: facts, expectedPort: port, system: system,
                                                      transport: NativeStartupEventTransport(
                                                        base: WallpaperTransport(), capture: capture, events: eventStream
                                                      ))
                            .run(payload: payload, deadline: attachDeadline)
                    }
                )
            } catch let error as StartupFailure { outcome = .failed(reason: error.reason) }
            catch { outcome = .failed(reason: "protocol-error") }
            self.opening = false
            self.finishStartup(outcome, promoted: self.promoted)
        }
    }

    private func prepareStartupPort() throws -> Int {
        func refused(_ operation: String) -> StartupFailure {
            let code = errno
            if let stream = startupEventStream {
                stream.portError(operation: operation, errno: code, at: ProcessInfo.processInfo.systemUptime)
            } else {
                nativeEventWriter.emit("startup-port-error", fields: ["reason": "listener-mismatch",
                                                                        "operation": operation, "errno": Int(code)])
            }
            return StartupFailure(reason: "listener-mismatch", message: "未能准备 Codex 本机回环调试端口。")
        }
        let descriptor = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else { throw refused("socket") }
        defer { Darwin.close(descriptor) }
        guard fcntl(descriptor, F_SETFD, FD_CLOEXEC) == 0 else { throw refused("close-on-exec") }
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
        guard bound == 0 else { throw refused("bind-loopback") }
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.getsockname(descriptor, $0, &length) }
        }
        guard named == 0 else { throw refused("getsockname") }
        let port = Int(UInt16(bigEndian: address.sin_port))
        guard (1...65535).contains(port), address.sin_family == sa_family_t(AF_INET),
              address.sin_addr.s_addr == inet_addr("127.0.0.1") else {
            throw StartupFailure(reason: "listener-mismatch", message: "分配的 Codex 回环端口无效。")
        }
        log("startup-port-selected", ["port": port, "requiresTargetListenerVerification": true])
        return port
    }

    private func openCodex(_ url: URL, port: Int, deadline: TimeInterval,
                           system: CodexStartupTargetSystem) async throws -> NSRunningApplication {
        let openTimeout = try StartupBudget.boundedTimeout(
            maximum: 45, stageDeadline: deadline, totalDeadline: deadline,
            now: ProcessInfo.processInfo.systemUptime
        )
        return try await withCheckedThrowingContinuation { continuation in
            let waiter = StartupApplicationWaiter(continuation)
            let timeout = DispatchWorkItem {
                waiter.finish(.failure(StartupFailure(reason: "attach-timeout", message: "Codex 启动接入超过当前阶段预算。")))
            }
            waiter.setTimeout(timeout)
            DispatchQueue.main.asyncAfter(deadline: .now() + openTimeout, execute: timeout)
            let configuration = NSWorkspace.OpenConfiguration()
            configuration.activates = false; configuration.hides = false; configuration.hidesOthers = false
            configuration.createsNewApplicationInstance = false; configuration.allowsRunningApplicationSubstitution = false
            configuration.addsToRecentItems = false
            configuration.arguments = ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=\(port)"]
            log("target-open-request", ["path": url.path, "bundleID": targetID, "debuggingPort": port])
            NSWorkspace.shared.openApplication(at: url, configuration: configuration) { [weak self] app, error in
                DispatchQueue.main.async {
                    guard let self else {
                        waiter.finish(.failure(StartupFailure(reason: "target-identity", message: "启动入口已结束。")))
                        return
                    }
                    guard ProcessInfo.processInfo.systemUptime < deadline else {
                        waiter.finish(.failure(StartupFailure(reason: "attach-timeout", message: "Codex 启动接入超过当前阶段预算。")))
                        return
                    }
                    if error != nil {
                        waiter.finish(.failure(StartupFailure(reason: "target-missing", message: "Codex 启动失败。")))
                        return
                    }
                    guard let app, !app.isTerminated, app.bundleURL.map({ self.real($0) }) == url,
                          app.bundleIdentifier == self.targetID else {
                        waiter.finish(.failure(StartupFailure(reason: "target-identity", message: "系统返回的应用与核验路径不符。")))
                        return
                    }
                    do {
                        try system.validate(self.startupFacts(app), deadline: deadline)
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
            outcome, observation: startupCapture?.snapshot(), at: ProcessInfo.processInfo.systemUptime
        ) else { return }
        processExitCode = final.exitCode
        switch final {
        case .activated:
            break
        case .ready:
            if let target, !target.isTerminated {
                activated = target.activate(options: [])
                log("target-activation-after-startup", ["allowed": activated, "targetPID": Int(target.processIdentifier)])
            }
        case .skipped:
            if let target, !target.isTerminated { activated = target.activate(options: []) }
        case .partial(let reason), .behaviorNotProven(let reason):
            if promoted { fail(startupMessage(reason), reason) }
            else { terminating = true; NSApp.terminate(nil) }
            return
        }
        if promoted {
            if done { finishIfReady("startup-ready") }
            return
        }
        terminating = true
        NSApp.terminate(nil)
    }

    private func startupMessage(_ reason: String) -> String {
        switch reason {
        case "target-missing": return "没有找到有效的 Codex 主程序。"
        case "target-identity": return "Codex 进程身份或签名核验未通过。"
        case "listener-mismatch": return "Codex 调试端口不属于已核验的主进程。"
        case "page-pending": return "Codex 主页面尚未准备好。"
        case "page-unsupported": return "当前 Codex 页面不符合启动接入要求。"
        case "ambiguous-main-page": return "找到多个 Codex 主页面，本次启动接入已拒绝。"
        case "owner-conflict", "startup-active": return "Codex 页面已有启动控制器，本次没有覆盖或重播。"
        case "startup-interrupted": return "Codex 页面在启动接入期间发生变化。"
        case "attach-timeout": return "Codex 启动接入超过阶段或总预算。"
        case "asset-invalid": return "缺少有效的 startup/install.js 生产载荷；本次不会启动或注入 Codex。"
        default: return "Codex 启动接入未完成；Codex 进程保持运行。"
        }
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
        terminating = true; watchdog?.invalidate(); snapshots.forEach { $0.cancel() }
        log("handoff-fade-start", ["frontmost": appInfo(NSWorkspace.shared.frontmostApplication)])
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
        log("failure", ["reason": reason, "targetPID": target.map { Int($0.processIdentifier) } ?? 0])
        if smokeTest {
            processExitCode = 1
            terminating = true; NSApp.terminate(nil); return
        }
        if startupRequested { startupEventStream?.latchFailure(reason) }
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
                self.log("preview-promoted-to-launch"); self.startTrustedSession()
            }
        }
        return false
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if preview || failed {
            if smokeTest && !smokeResultSucceeded { failed = true; processExitCode = 1 }
            if startupEventStream?.isPending == true { startupEventStream?.latchInterruption() }
            terminating = true; NSApp.terminate(nil)
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
        watchdog?.invalidate(); snapshots.forEach { $0.cancel() }
        if smokeTest {
            if !smokeResultSucceeded { failed = true; processExitCode = max(processExitCode, 1) }
            logSmokeEvent("player-terminated", ["completed": done && smokeResultSucceeded && !failed,
                                                 "failed": failed || !smokeResultSucceeded])
        } else {
            log("player-terminated", ["failed": failed, "completed": done, "frontmost": appInfo(NSWorkspace.shared.frontmostApplication)])
            if let final = startupEventStream?.finish(at: ProcessInfo.processInfo.systemUptime) {
                processExitCode = final.exitCode
            }
        }
        webView?.stopLoading(); webView?.configuration.userContentController.removeScriptMessageHandler(forName: "launcher")
        if lockFD >= 0 { flock(lockFD, LOCK_UN); close(lockFD); lockFD = -1 }
        try? logFile?.close()
        if processExitCode != 0 { Darwin.exit(processExitCode) }
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url, url.isFileURL, let root = webRoot else { decisionHandler(.cancel); return }
        decisionHandler(real(url).path.hasPrefix(root.path + "/") ? .allow : .cancel)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { fail(error.localizedDescription, "navigation-error") }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { fail(error.localizedDescription, "navigation-error") }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { fail("WebKit 渲染进程已结束。", "renderer-terminated") }
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
