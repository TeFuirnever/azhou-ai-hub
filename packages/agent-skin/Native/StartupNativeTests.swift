// Compile separately from the application; fake host operations never launch or kill Codex.
// python3 -B tools/test-startup-native.py
import Foundation
import Darwin
import AppKit
import WebKit
import CryptoKit

@MainActor
private final class FakeNativeApplication: NativeApplication {
    let processIdentifier: Int32
    let bundleIdentifier: String?
    let bundleURL: URL?
    let executableURL: URL?
    let launchTime: TimeInterval?
    var isTerminated = false
    var isActive = false
    var isHidden = false
    var activationResult = true
    private(set) var activationCount = 0

    init(pid: Int32, bundleIdentifier: String?, bundleURL: URL?, executableURL: URL? = nil,
         launchTime: TimeInterval? = nil) {
        self.processIdentifier = pid
        self.bundleIdentifier = bundleIdentifier
        self.bundleURL = bundleURL
        self.executableURL = executableURL
        self.launchTime = launchTime
    }
    func activate() -> Bool { activationCount += 1; return activationResult }
}

@MainActor
private final class FakeNativeInstanceLock: NativeInstanceLock {
    private(set) var releaseCount = 0
    func release() { releaseCount += 1 }
}

@MainActor
private final class FakeNativeAppRuntime: NativeAppRuntime {
    let arguments: [String]
    let epoch: TimeInterval = 100
    var uptime: TimeInterval = 101
    let processIdentifier = 42
    var bundleURL = URL(fileURLWithPath: "/Applications/Agent Skin.app")
    let resourceURL: URL?
    var frontmostApplication: (any NativeApplication)?
    var applications: [any NativeApplication] = []
    var installedTargetURL: URL?
    var openedApplication: (any NativeApplication)?
    var openError: Error?
    var beforeOpenCompletion: (() -> Void)?
    var deferOpenCompletion = false
    private var pendingOpenCompletion: (((any NativeApplication)?, Error?) -> Void)?
    private(set) var openCount = 0
    private(set) var openedPorts: [Int] = []
    private(set) var openedEnvironments: [[String: String]] = []
    var startupTargetSystem: (any StartupTargetSystem)?
    var startupTransportFactory: ((NativeStartupCapture, NativeStartupEventStream) -> any StartupTransport)?
    var lockBusy = false
    var lockError: Int32?
    private(set) var allocationCount = 0
    var allocatedPort = 45678
    var allocatedPortError: NativeLoopbackPortError?
    var allocationError: Error?
    private(set) var acquiredLock: FakeNativeInstanceLock?
    private(set) var terminated = 0
    private(set) var activated = 0
    private(set) var accessoryPolicyChanges = 0
    private(set) var output: [String] = []

    init(arguments: [String], resourceURL: URL? = nil) {
        self.arguments = arguments
        self.resourceURL = resourceURL
    }
    func appearanceTheme() -> String { "light" }
    func runningApplications(bundleIdentifier: String) -> [any NativeApplication] {
        applications.filter { $0.bundleIdentifier == bundleIdentifier }
    }
    var applicationOverride: ((Int32) -> (any NativeApplication)?)?
    func application(processIdentifier: Int32) -> (any NativeApplication)? {
        applicationOverride?(processIdentifier) ?? applications.first { $0.processIdentifier == processIdentifier }
    }
    func urlForApplication(bundleIdentifier: String) -> URL? { installedTargetURL }
    func openApplication(at url: URL, debuggingPort: Int,
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void) {
        openCount += 1; openedPorts.append(debuggingPort)
        beforeOpenCompletion?()
        if deferOpenCompletion {
            pendingOpenCompletion = completion
            return
        }
        completion(openedApplication, openError)
    }
    func openApplication(at url: URL, debuggingPort: Int, environment: [String: String],
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void) {
        openedEnvironments.append(environment)
        openApplication(at: url, debuggingPort: debuggingPort, completion: completion)
    }
    func completePendingOpen() {
        let completion = pendingOpenCompletion
        pendingOpenCompletion = nil
        completion?(openedApplication, openError)
    }
    func acquireInstanceLock(identifier: String) -> NativeLockAcquisition {
        if let lockError { return .failed(lockError) }
        if lockBusy { return .busy }
        let lock = FakeNativeInstanceLock(); acquiredLock = lock
        return .acquired(lock)
    }
    func allocateLoopbackPort() throws -> Int {
        allocationCount += 1
        if let allocatedPortError { throw allocatedPortError }
        if let allocationError { throw allocationError }
        return allocatedPort
    }
    func makeStartupTargetSystem() -> any StartupTargetSystem { startupTargetSystem ?? CodexStartupTargetSystem() }
    func makeStartupTransport(capture: NativeStartupCapture, events: NativeStartupEventStream) -> any StartupTransport {
        if let startupTransportFactory { return startupTransportFactory(capture, events) }
        return NativeStartupEventTransport(base: WallpaperTransport(), capture: capture, events: events)
    }
    func systemFallbackLocale() -> NativeDisplayLocale { .english }
    func setAccessoryPolicy() { accessoryPolicyChanges += 1 }
    func activateIgnoringOtherApps() { activated += 1 }
    func terminate() { terminated += 1 }
    func exit(code: Int32) { processExitCode = code }
    func writeStandardOutput(_ line: String) { output.append(line) }
    private(set) var processExitCode: Int32 = 0
}

/// Old conformers deliberately implement only the original open method.
@MainActor
private final class LegacyOnlyNativeRuntime: NativeAppRuntime {
    let base = FakeNativeAppRuntime(arguments: ["synthetic-legacy"])
    var arguments: [String] { base.arguments }
    var epoch: TimeInterval { base.epoch }
    var uptime: TimeInterval { base.uptime }
    var processIdentifier: Int { base.processIdentifier }
    var bundleURL: URL { base.bundleURL }
    var resourceURL: URL? { base.resourceURL }
    var frontmostApplication: (any NativeApplication)? { base.frontmostApplication }
    func appearanceTheme() -> String { base.appearanceTheme() }
    func runningApplications(bundleIdentifier: String) -> [any NativeApplication] { base.runningApplications(bundleIdentifier: bundleIdentifier) }
    func application(processIdentifier: Int32) -> (any NativeApplication)? { base.application(processIdentifier: processIdentifier) }
    func urlForApplication(bundleIdentifier: String) -> URL? { base.urlForApplication(bundleIdentifier: bundleIdentifier) }
    func openApplication(at url: URL, debuggingPort: Int, completion: @escaping ((any NativeApplication)?, Error?) -> Void) {
        base.openApplication(at: url, debuggingPort: debuggingPort, completion: completion)
    }
    func acquireInstanceLock(identifier: String) -> NativeLockAcquisition { base.acquireInstanceLock(identifier: identifier) }
    func allocateLoopbackPort() throws -> Int { try base.allocateLoopbackPort() }
    func makeStartupTargetSystem() -> any StartupTargetSystem { base.makeStartupTargetSystem() }
    func makeStartupTransport(capture: NativeStartupCapture, events: NativeStartupEventStream) -> any StartupTransport { base.makeStartupTransport(capture: capture, events: events) }
    func systemFallbackLocale() -> NativeDisplayLocale { base.systemFallbackLocale() }
    func setAccessoryPolicy() { base.setAccessoryPolicy() }
    func activateIgnoringOtherApps() { base.activateIgnoringOtherApps() }
    func terminate() { base.terminate() }
    func exit(code: Int32) { base.exit(code: code) }
    func writeStandardOutput(_ line: String) { base.writeStandardOutput(line) }
}

@MainActor
private final class FakeScheduledAction: NativeScheduledAction {
    let delay: TimeInterval
    private let action: () -> Void
    private(set) var cancelled = false
    init(delay: TimeInterval, action: @escaping () -> Void) { self.delay = delay; self.action = action }
    func cancel() { cancelled = true }
    func fire() { if !cancelled { action() } }
}

@MainActor
private final class FakeNativePlayerPresentation: NativePlayerPresentation {
    var geometry: [String: Any] = [:]
    private(set) var updatedLocales: [NativeDisplayLocale] = []
    private(set) var readyCount = 0
    private(set) var normalLevelCount = 0
    private(set) var visibleCount = 0
    private(set) var orderedOutCount = 0
    private(set) var evaluations: [String] = []
    private(set) var fadeDurations: [TimeInterval] = []
    private(set) var schedules: [FakeScheduledAction] = []
    private(set) var stopCount = 0
    private(set) var removedHandlers: [String] = []
    private(set) var errors: [(String, String, String)] = []
    private(set) var createdPlayers: [(NativeDisplayLocale, String, String, Bool)] = []
    private(set) var loadedPlayers: [(URL, URL)] = []
    var evaluationResult: (Any?, Error?) = ("{}", nil)
    var snapshotResult: (NSImage?, Error?) = (nil, nil)

    func createPlayer(locale: NativeDisplayLocale, mode: String, theme: String, inspect: Bool,
                      messageHandler: WKScriptMessageHandler, navigationDelegate: WKNavigationDelegate) {
        createdPlayers.append((locale, mode, theme, inspect))
    }
    func loadPlayer(page: URL, allowingReadAccessTo root: URL) { loadedPlayers.append((page, root)) }
    func updateLabels(_ locale: NativeDisplayLocale) { updatedLocales.append(locale) }
    func showReady() { readyCount += 1 }
    func setNormalLevel() { normalLevelCount += 1 }
    func makeVisible() { visibleCount += 1 }
    func orderOut() { orderedOutCount += 1 }
    func evaluateJavaScript(_ source: String, completion: ((Any?, Error?) -> Void)?) {
        evaluations.append(source)
        completion?(evaluationResult.0, evaluationResult.1)
    }
    func fadeOut(duration: TimeInterval, completion: @escaping () -> Void) {
        fadeDurations.append(duration)
        completion()
    }
    func schedule(after delay: TimeInterval, _ action: @escaping () -> Void) -> any NativeScheduledAction {
        let scheduled = FakeScheduledAction(delay: delay, action: action)
        schedules.append(scheduled)
        return scheduled
    }
    func takeSnapshot(_ completion: @escaping (NSImage?, Error?) -> Void) {
        completion(snapshotResult.0, snapshotResult.1)
    }
    func stopLoading() { stopCount += 1 }
    func removeMessageHandler(named name: String) { removedHandlers.append(name) }
    func showError(title: String, message: String, closeTitle: String) {
        errors.append((title, message, closeTitle))
    }
}

@main
struct StartupNativeTests {
    private static func emitEventSamples(to outputDirectory: URL) throws {
        try FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)

        func makeWriter(startedAt: TimeInterval, launcherPID: Int) -> (NativeEventWriter, () -> [[String: Any]]) {
            var records: [[String: Any]] = []
            let writer = NativeEventWriter(
                startedAt: startedAt, launcherPID: launcherPID,
                launcherPath: "/Applications/Agent Skin.app",
                now: { startedAt + 100 }, sink: { records.append($0) }
            )
            return (writer, { records })
        }

        func write(_ name: String, _ records: [[String: Any]]) throws {
            let lines = try records.map { record -> String in
                let data = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys, .withoutEscapingSlashes])
                guard let line = String(data: data, encoding: .utf8) else {
                    throw StartupFailure(reason: "protocol-error", message: "event sample is not UTF-8")
                }
                return line
            }
            let file = outputDirectory.appendingPathComponent(name).appendingPathExtension("jsonl")
            try Data((lines.joined(separator: "\n") + "\n").utf8).write(to: file)
            print(file.path)
        }

        do {
            let (writer, records) = makeWriter(startedAt: 10, launcherPID: 110)
            let stream = NativeStartupEventStream(writer: writer)
            stream.begin(at: 10)
            stream.targetOpened(pid: 2110, at: 11)
            stream.startupInstalled(pid: 2110, runID: 1, at: 12)
            let observation = NativeStartupObservation(
                targetPID: 2110, installedAt: 12,
                status: NativeStartupStatus(runID: 1, phase: "playing", ready: true, completed: false,
                                            overlay: true, completionCause: nil, completionBeforeReady: nil),
                statusAt: 13
            )
            _ = stream.resolve(.ready(runID: 1), observation: observation, at: 13)
            _ = stream.finish(at: 14)
            try write("startup-ready", records())
        }

        do {
            let (writer, records) = makeWriter(startedAt: 20, launcherPID: 120)
            let stream = NativeStartupEventStream(writer: writer)
            stream.begin(at: 20)
            _ = stream.resolve(.activated(pid: 2120), observation: nil, at: 21)
            _ = stream.finish(at: 22)
            try write("target-activated", records())
        }

        do {
            let (writer, records) = makeWriter(startedAt: 24, launcherPID: 124)
            writer.emitProbe(targetPath: "/Applications/Codex.app", targetBundleID: "com.openai.codex",
                             running: [], frontmost: [:], at: 25)
            try write("probe-success", records())
        }

        do {
            let (writer, records) = makeWriter(startedAt: 26, launcherPID: 126)
            writer.emitProbe(targetPath: "", targetBundleID: "", running: [], frontmost: [:], at: 27)
            try write("probe-failure", records())
        }

        do {
            let (writer, records) = makeWriter(startedAt: 30, launcherPID: 130)
            let stream = NativeStartupEventStream(writer: writer)
            stream.begin(at: 30)
            stream.targetOpened(pid: 2130, at: 31)
            stream.startupInstalled(pid: 2130, runID: 3, at: 32)
            let observation = NativeStartupObservation(
                targetPID: 2130, installedAt: 32,
                status: NativeStartupStatus(runID: 3, phase: "complete", ready: false, completed: true,
                                            overlay: false, completionCause: "skip", completionBeforeReady: true),
                statusAt: 33
            )
            _ = stream.resolve(.skipped(runID: 3, beforeReady: true), observation: observation, at: 33)
            _ = stream.finish(at: 34)
            try write("startup-skipped", records())
        }

        do {
            let (writer, records) = makeWriter(startedAt: 40, launcherPID: 140)
            let stream = NativeStartupEventStream(writer: writer)
            stream.begin(at: 40)
            stream.targetOpened(pid: 2140, at: 41)
            stream.startupInstalled(pid: 2140, runID: 4, at: 42)
            _ = stream.resolve(.partial(reason: "startup-interrupted"), observation: nil, at: 43)
            _ = stream.finish(at: 44)
            try write("startup-interrupted", records())
        }

        do {
            let (writer, records) = makeWriter(startedAt: 50, launcherPID: 150)
            let stream = NativeStartupEventStream(writer: writer)
            stream.begin(at: 50)
            stream.portError(operation: "bind-loopback", errno: 48, at: 51)
            _ = stream.resolve(.failed(reason: "listener-mismatch"), observation: nil, at: 52)
            _ = stream.finish(at: 53)
            try write("startup-port-error", records())
        }

        do {
            let (writer, records) = makeWriter(startedAt: 60, launcherPID: 160)
            writer.emit("player-start", fields: ["mode": "smoke"], at: 60)
            writer.emit("playback-start", fields: ["durationSeconds": 12], at: 61)
            writer.emit("animation-complete", at: 62)
            writer.emit("preview-result", fields: ["success": true], at: 63)
            writer.emit("player-terminated", fields: ["completed": true, "failed": false], at: 64)
            try write("smoke", records())
        }
    }

    @MainActor
    static func main() async throws {
        if let index = CommandLine.arguments.firstIndex(of: "--probe-startup-handshake"),
           index + 1 < CommandLine.arguments.count,
           let url = URL(string: CommandLine.arguments[index + 1]), let port = url.port {
            let socket = try WallpaperValidation.pageSocket(url.absoluteString, port: port)
            let transport = WallpaperTransport()
            defer { transport.close() }
            try transport.connect(to: socket, timeout: 2)
            do {
                _ = try await transport.evaluate("({probe:true})", timeout: 2)
                fatalError("a refused handshake must not evaluate JavaScript")
            } catch let failure as StartupFailure {
                let result: [String: Any] = ["candidate": failure.pageConnectionLost,
                    "reason": failure.reason, "host": false,
                    "errorDomain": failure.transportError?.domain ?? "",
                    "errorCode": failure.transportError?.code ?? 0,
                    "httpStatus": failure.transportError?.httpStatus ?? 0]
                print(String(decoding: try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]), as: UTF8.self))
            }
            return
        }
        if CommandLine.arguments.contains("--probe-page-replacement") {
            let results = try await startupPageReplacementProbe()
            for result in results {
                print(String(decoding: try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]), as: UTF8.self))
            }
            exit(results.allSatisfy { $0["recovered"] as? Bool == true } ? 0 : 1)
        }
        if let index = CommandLine.arguments.firstIndex(of: "--zcode-driver-interleave"),
           index + 1 < CommandLine.arguments.count, let port = Int(CommandLine.arguments[index + 1]) {
            try await zcodeDriverInterleave(port: port)
            return
        }
        if let index = CommandLine.arguments.firstIndex(of: "--zcode-runtime-fixture"),
           index + 1 < CommandLine.arguments.count, let port = Int(CommandLine.arguments[index + 1]) {
            let checks = try await zcodeRuntimeFixtureChecks(port: port)
            print("{\"syntheticRuntimeChecks\":\(checks),\"host\":false,\"realOSQueries\":true,\"OSQueryScope\":\"self-PID listener metadata only\"}")
            return
        }
        if let index = CommandLine.arguments.firstIndex(of: "--wallpaper-transport-fixture"),
           index + 2 < CommandLine.arguments.count,
           let url = URL(string: CommandLine.arguments[index + 1]), let port = url.port {
            let socketURL = try WallpaperValidation.pageSocket(url.absoluteString, port: port)
            let slowTimeout = CommandLine.arguments[index + 2] == "timeout"
            let milliseconds = slowTimeout ? 10_000 : 7_000
            let state = slowTimeout ? "retry-timeout" : "fixture-complete"
            let transport = WallpaperTransport()
            defer { transport.close() }
            let socket = transport.socket(socketURL)
            let result = try await transport.evaluate(
                "new Promise(resolve => setTimeout(() => resolve({state:'\(state)'}),\(milliseconds)))", on: socket,
                timeout: WallpaperCLI.retryEvaluationTimeout)
            print(String(decoding: try JSONSerialization.data(withJSONObject: result), as: UTF8.self))
            return
        }
        if let index = CommandLine.arguments.firstIndex(of: "--emit-event-jsonl") {
            let path = index + 1 < CommandLine.arguments.count
                ? CommandLine.arguments[index + 1] : ".build/native-event-samples"
            try emitEventSamples(to: URL(fileURLWithPath: path, isDirectory: true))
            return
        }
        if CommandLine.arguments.dropFirst().contains("--emit-helper-expressions") {
            let expressions = [
                "statusSource": WallpaperCLI.statusSource,
                "applyGuardSource": WallpaperCLI.applyGuardSource,
                "retrySource": WallpaperCLI.retrySource,
                "restoreSource": WallpaperCLI.restoreSource,
            ]
            let bytes = try JSONSerialization.data(withJSONObject: expressions, options: [.sortedKeys])
            guard let text = String(data: bytes, encoding: .utf8) else { fatalError("helper expressions are not UTF-8") }
            print(text)
            return
        }
        if CommandLine.arguments.dropFirst().contains("--emit-unit-expressions") {
            let href = "app://-/index.html?initialRoute=%2F"
            let expressions = [
                "statusSource": WallpaperCLI.statusSource,
                "applyGuardSource": WallpaperCLI.applyGuardSource,
                "retrySource": WallpaperCLI.retrySource,
                "restoreSource": WallpaperCLI.restoreSource,
                "inspectExpression": StartupConnector.inspectExpression,
                "statusExpression": StartupConnector.statusExpression,
                "controllerReferenceExpression": WallpaperTransport.controllerReferenceExpression,
                "boundStatusExpression": WallpaperTransport.boundStatusExpression,
                "disposeExpression": try StartupConnector.disposeExpression(href),
                "installExpression": try StartupConnector.installExpression("({installed:true})", expectedHref: href),
            ]
            let bytes = try JSONSerialization.data(withJSONObject: expressions, options: [.sortedKeys])
            guard let text = String(data: bytes, encoding: .utf8) else { fatalError("unit expressions are not UTF-8") }
            print(text)
            return
        }

        var checks = 0
        checks += zcodeRuntimeEventEnvelopeChecks()
        checks += zcodeTypedEventContractChecks()
        func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
            guard condition() else { fatalError("FAILED: \(label)") }
            checks += 1
        }
        if let failure = ZCodeNativeRuntime.normalizedAttachFailure(ZCodeBoundCDP.Failure.deadline, deadline: 110, now: 105, cancelled: false) as? ZCodeAttachFailure {
            if case .deadline = failure { expect(true, "CDP deadline maps to typed attach deadline") } else { fatalError("wrong CDP deadline mapping") }
        } else { fatalError("missing CDP deadline mapping") }
        if let failure = ZCodeNativeRuntime.normalizedAttachFailure(CancellationError(), deadline: 110, now: 105, cancelled: false) as? ZCodeAttachFailure {
            if case .cancelled = failure { expect(true, "cancellation maps to typed attach cancellation") } else { fatalError("wrong cancellation mapping") }
        } else { fatalError("missing cancellation mapping") }
        if let failure = ZCodeNativeRuntime.normalizedAttachFailure(StartupFailure(reason: "attach-timeout", message: "fixture"), deadline: 110, now: 110, cancelled: false) as? ZCodeAttachFailure {
            if case .deadline = failure { expect(true, "listener deadline maps to typed attach deadline") } else { fatalError("wrong listener deadline mapping") }
        } else { fatalError("missing listener deadline mapping") }
        if let failure = ZCodeNativeRuntime.normalizedAttachFailure(URLError(.timedOut), deadline: 110, now: 110, cancelled: false) as? ZCodeAttachFailure {
            if case .deadline = failure { expect(true, "URL timeout at deadline maps to timeout") } else { fatalError("wrong URL timeout mapping") }
        } else { fatalError("missing expired URL timeout mapping") }
        expect(ZCodeNativeRuntime.normalizedAttachFailure(URLError(.timedOut), deadline: 110, now: 105, cancelled: false) is URLError,
               "early URL timeout remains a transport error")
        if let failure = ZCodeNativeRuntime.normalizedAttachFailure(URLError(.cancelled), deadline: 110, now: 105, cancelled: true) as? ZCodeAttachFailure {
            if case .cancelled = failure { expect(true, "cancelled task maps URL cancellation to cancellation") } else { fatalError("wrong cancelled URL mapping") }
        } else { fatalError("missing cancelled URL mapping") }
        expect(ZCodeNativeRuntime.normalizedAttachFailure(URLError(.cancelled), deadline: 110, now: 105, cancelled: false) is URLError,
               "URL cancellation without task cancellation remains transport error")
        if let failure = ZCodeBoundCDP.normalizedBoundaryFailure(URLError(.cancelled), deadline: 110, now: 110, cancelled: false) as? ZCodeBoundCDP.Failure {
            if case .deadline = failure { expect(true, "socket cancellation at RPC deadline maps to deadline") } else { fatalError("socket race misclassified") }
        } else { fatalError("socket race lost deadline type") }
        if let failure = ZCodeBoundCDP.normalizedBoundaryFailure(URLError(.cancelled), deadline: 110, now: 110, cancelled: true) as? ZCodeBoundCDP.Failure {
            if case .cancelled = failure { expect(true, "task cancellation takes precedence at deadline") } else { fatalError("task cancel misclassified") }
        } else { fatalError("socket race lost cancel type") }
        expect(ZCodeBoundCDP.normalizedBoundaryFailure(URLError(.cancelled), deadline: 110, now: 105, cancelled: false) is URLError,
               "early unsolicited socket cancellation remains transport error")
        if let failure = ZCodeBoundCDP.normalizedBoundaryFailure(NSError(domain: "fixture", code: 1), deadline: 110, now: 111, cancelled: false) as? ZCodeBoundCDP.Failure {
            if case .deadline = failure { expect(true, "guard error after deadline maps to deadline") } else { fatalError("guard race misclassified") }
        } else { fatalError("guard race lost deadline type") }
        let failureDiagnostic = WallpaperValidation.diagnostic([
            "failureCode": "shell-timeout", "failureStage": "private renderer text",
        ], index: 0, version: nil)
        expect(failureDiagnostic["failureCode"] as? String == "shell-timeout"
               && failureDiagnostic["failureStage"] as? String == "shell",
               "wallpaper diagnostics derive a fixed failure stage from the failure code")
        let unsafeDiagnostic = WallpaperValidation.diagnostic([
            "failureCode": "private renderer text", "failureStage": "shell",
        ], index: 0, version: nil)
        expect(unsafeDiagnostic["failureCode"] == nil && unsafeDiagnostic["failureStage"] == nil,
               "wallpaper diagnostics discard arbitrary renderer text")
        for reason in ["busy", "unknown-owner", "disabled", "operation-cancelled"] {
            let refusal = WallpaperValidation.retryFailure([
                "retried": false, "reason": reason, "wallpaper": ["applied": true],
            ])
            expect(refusal == reason, "healthy prior wallpaper does not hide a refused retry: \(reason)")
        }
        expect(WallpaperValidation.retryFailure([
            "retried": false, "reason": "already-applied", "wallpaper": ["applied": true],
        ]) == nil, "an explicit healthy retry no-op can proceed to independent verification")
        expect(WallpaperValidation.retryFailure([
            "retried": true, "wallpaper": ["applied": false, "failureCode": "image-decode-failed"],
        ]) == "retry-failed", "a failed request cannot be certified by retained healthy wallpaper")

        let themeBundleURL = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".bundle")
        defer { try? FileManager.default.removeItem(at: themeBundleURL) }
        for (language, name) in [("en", "Azhou Test Lab"), ("zh-Hans", "阿舟测试实验室")] {
            let folder = themeBundleURL.appendingPathComponent("Contents/Resources/" + language + ".lproj")
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let data = try PropertyListSerialization.data(fromPropertyList: ["CFBundleDisplayName": name], format: .xml, options: 0)
            try data.write(to: folder.appendingPathComponent("InfoPlist.strings"))
        }
        let themeInfo = try PropertyListSerialization.data(fromPropertyList: [
            "CFBundleIdentifier": "local.azhou.theme-test", "CFBundlePackageType": "BNDL",
            "CFBundleDisplayName": "Azhou Test Fallback", "CFBundleDevelopmentRegion": "en",
        ], format: .xml, options: 0)
        try themeInfo.write(to: themeBundleURL.appendingPathComponent("Contents/Info.plist"))
        let themeBundle = Bundle(url: themeBundleURL)!
        expect(NativeDisplayLocale.chinese.displayName(in: themeBundle) == "阿舟测试实验室"
            && NativeDisplayLocale.english.displayName(in: themeBundle) == "Azhou Test Lab",
            "native UI reads configured bundle names for the verified locale")

        expect(NativeDisplayLocale.systemFallback(preferredLanguages: ["zh-Hans-CN"]) == .chinese,
               "native preview follows the macOS Chinese locale before an official host locale is ready")
        expect(NativeDisplayLocale.systemFallback(preferredLanguages: ["en-US"]) == .english,
               "native preview follows the macOS English locale before an official host locale is ready")
        expect(NativeDisplayLocale.verifiedReadyLocale("zh-CN") == .chinese
               && NativeDisplayLocale.verifiedReadyLocale("en") == .english
               && NativeDisplayLocale.verifiedReadyLocale("fr-FR") == nil,
               "native labels accept only a supported locale from the trusted ready message")
        expect(NativeDisplayLocale.chinese.closeTitle == "关闭"
               && NativeDisplayLocale.english.closeTitle == "Close",
               "native error dialogs use the active locale for their close button")
        let localizedErrorReasons = [
            "resources-missing", "page-missing", "target-launch-timeout", "renderer-ready-timeout",
            "renderer-complete-timeout", "playback-start-error", "javascript-error", "asset-error", "target-exited",
            "activation-rejected", "renderer-terminated", "target-missing", "target-identity",
            "listener-mismatch", "page-pending", "page-unsupported", "ambiguous-main-page",
            "owner-conflict", "startup-active", "startup-interrupted", "attach-timeout", "asset-invalid",
            "preview-promotion-error", "navigation-error", "unrecognized-native-failure",
        ]
        let containsHan: (String) -> Bool = { text in
            text.unicodeScalars.contains { (0x4e00...0x9fff).contains($0.value) }
        }
        expect(localizedErrorReasons.allSatisfy { !containsHan(NativeDisplayLocale.english.message(for: $0)) },
               "native startup and preview failure messages have English labels for every supported failure reason")
        func refuses(_ label: String, _ operation: () throws -> Void) {
            do { try operation(); fatalError("FAILED: \(label)") }
            catch { checks += 1 }
        }

        var successfulProbeRecords: [[String: Any]] = []
        let successfulProbeWriter = NativeEventWriter(
            startedAt: 700, launcherPID: 170,
            launcherPath: "/Applications/Agent Skin.app",
            now: { 701 }, sink: { successfulProbeRecords.append($0) }
        )
        successfulProbeWriter.emitProbe(
            targetPath: "/Applications/Codex.app", targetBundleID: "com.openai.codex",
            running: [], frontmost: [:], at: 701
        )
        expect(successfulProbeRecords.count == 1
               && successfulProbeRecords[0]["event"] as? String == "probe"
               && successfulProbeRecords[0]["schema"] as? String == NativeEventWriter.schema
               && successfulProbeRecords[0]["seconds"] as? Double == 1
               && successfulProbeRecords[0]["launcherPID"] as? Int == 170
               && successfulProbeRecords[0]["launcherPath"] as? String == "/Applications/Agent Skin.app"
               && successfulProbeRecords[0]["targetBundleID"] as? String == "com.openai.codex",
               "successful read-only probe uses the v1 writer envelope and verified identity fields")

        var missingProbeRecords: [[String: Any]] = []
        let missingProbeWriter = NativeEventWriter(
            startedAt: 710, launcherPID: 171,
            launcherPath: "/Applications/Agent Skin.app",
            now: { 711 }, sink: { missingProbeRecords.append($0) }
        )
        missingProbeWriter.emitProbe(targetPath: "", targetBundleID: "", running: [], frontmost: [:], at: 711)
        expect(missingProbeRecords.count == 1
               && missingProbeRecords[0]["event"] as? String == "probe"
               && missingProbeRecords[0]["schema"] as? String == NativeEventWriter.schema
               && missingProbeRecords[0]["targetPath"] as? String == ""
               && missingProbeRecords[0]["targetBundleID"] as? String == "",
               "a missing target remains a schema-valid but unsuccessful read-only probe")

        let existing = StartupTargetFacts(
            pid: 4123,
            bundle: URL(fileURLWithPath: "/Applications/Codex.app"),
            executable: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
            bundleID: "com.openai.codex",
            launchTime: 123.0
        )
        var validatedPID: Int32?
        var activatedPID: Int32?
        var coldStartCount = 0
        let outcome = try await StartupLaunchFlow.run(
            existing: existing,
            preflightBundle: {},
            validate: { validatedPID = $0.pid },
            activate: { activatedPID = $0.pid; return true },
            coldStart: { coldStartCount += 1; return .failed(reason: "unexpected-cold-start") }
        )
        expect(validatedPID == 4123, "hot start validates the existing process")
        expect(activatedPID == 4123, "hot start activates the same process")
        expect(coldStartCount == 0, "hot start does not launch or replay a session")
        expect(outcome == .activated(pid: 4123), "hot start is reported as activated")

        expect(WallpaperCLI.statusSource.contains("let startup={installed:false}")
               && WallpaperCLI.statusSource.contains("azhou-codex-startup")
               && WallpaperCLI.statusSource.contains("azhou.codex-startup-animation")
               && WallpaperCLI.statusSource.contains("0.9.0"),
               "wallpaper status reads only supported owner tuples and includes startup status")
        expect(WallpaperCLI.applyGuardSource.contains("startup-active")
               && WallpaperCLI.applyGuardSource.contains("owner-conflict")
               && WallpaperCLI.applyGuardSource.contains("0.9.0"),
               "explicit helper apply refuses an active or unknown page owner before injection")
        expect(WallpaperCLI.restoreSource.contains("azhou-codex-startup")
               && WallpaperCLI.restoreSource.contains("azhou.codex-startup-animation")
               && WallpaperCLI.restoreSource.contains("0.7.1")
               && WallpaperCLI.restoreSource.contains("0.9.0"),
               "explicit restore supports the controller and current/known legacy wallpaper versions")
        expect(WallpaperCLI.exitCode(for: "applied") == 0
               && WallpaperCLI.exitCode(for: "restored") == 0
               && WallpaperCLI.exitCode(for: "ready") == 0
               && WallpaperCLI.exitCode(for: "not-applied") == 2,
               "helper status keeps its established success and not-applied exit codes")
        expect(WallpaperCLI.restoreMessage == WallpaperMessages.localized(
            chinese: "已移除本页启动美化及设置入口；已保存值保留；Codex 与调试端口保持原状态。",
            english: "Removed startup decoration and settings entry from this page. Saved values were preserved. Codex and its debug port were left unchanged.",
            preferredLanguages: Locale.preferredLanguages
        ),
               "restore receipt scopes page cleanup and confirms saved-value and Codex preservation")

        let lockPID = Int32.max
        let lockPath = WallpaperOperationLock.path(uid: Darwin.getuid(), pid: lockPID)
        defer { try? FileManager.default.removeItem(atPath: lockPath) }
        let sharedLock = try WallpaperOperationLock.acquire(pid: lockPID)
        do {
            _ = try WallpaperOperationLock.acquire(pid: lockPID)
            fatalError("FAILED: a second startup or helper operation acquired the same PID lock")
        } catch let error as WallpaperFailure {
            expect(error.state == "busy", "startup and helper use one nonblocking PID lock")
        }
        sharedLock.release()
        let helperAfterStartup = try WallpaperOperationLock.acquire(pid: lockPID)
        helperAfterStartup.release()
        checks += 1

        var preflightOrder: [String] = []
        var preflightColdStartCount = 0
        do {
            _ = try await StartupLaunchFlow.run(
                existing: nil,
                preflightBundle: { preflightOrder.append("signature"); throw StartupFailure(reason: "target-identity", message: "bad signature") },
                validate: { _ in preflightOrder.append("running-process") },
                activate: { _ in true },
                coldStart: { preflightColdStartCount += 1; return .ready(runID: 1) }
            )
            fatalError("FAILED: failed signature preflight refuses cold start")
        } catch let error as StartupFailure {
            expect(error.reason == "target-identity", "signature preflight returns a fixed identity error")
        }
        expect(preflightOrder == ["signature"], "signature preflight runs before any cold-start work")
        expect(preflightColdStartCount == 0, "a failed signature preflight never reaches open or evaluation")

        let budget = StartupBudget(startedAt: 100)
        expect(budget.preflightDeadline == 115 && budget.totalDeadline == 160,
               "startup uses absolute 15 second preflight and 60 second total limits")
        let attachDeadline = budget.attachDeadline(startedAt: 112)
        expect(attachDeadline == 157, "attach has its own absolute 45 second stage deadline")
        let stageLimitedTimeout = try budget.timeout(maximum: 10, stageDeadline: attachDeadline, now: 155)
        expect(stageLimitedTimeout == 2,
               "request timeout is truncated to the nearer stage deadline")
        let totalLimitedTimeout = try budget.timeout(maximum: 10, stageDeadline: 170, now: 158)
        expect(totalLimitedTimeout == 2,
               "request timeout is truncated to the overall deadline")
        let cdpTimeoutMilliseconds = try StartupBudget.requestTimeoutMilliseconds(0.0029)
        expect(cdpTimeoutMilliseconds == 2,
               "fractional CDP timeouts round down so they cannot outlive the remaining budget")
        refuses("exhausted startup budget refuses another request") {
            _ = try budget.timeout(maximum: 10, stageDeadline: attachDeadline, now: 157)
        }
        refuses("sub-millisecond remaining budget refuses a CDP request") {
            _ = try StartupBudget.requestTimeoutMilliseconds(0.0009)
        }

        var failureEvents: [String] = []
        var deliveredExitCode: Int32?
        let handledFailure = StartupFailureDelivery.deliver(
            .failed(reason: "protocol-error"), previewUI: false, message: { _ in "fixed message" },
            log: { event, reason in failureEvents.append("\(event):\(reason)") },
            setExitCode: { deliveredExitCode = $0 },
            showPreviewError: { _, _ in failureEvents.append("gui") },
            terminate: { failureEvents.append("exit:\($0)") }
        )
        expect(handledFailure, "ordinary startup failure is handled by the production exit decision")
        expect(failureEvents == ["startup-failed:protocol-error", "exit:1"],
               "ordinary failure fixed-logs and terminates without invoking preview UI")
        expect(deliveredExitCode == 1, "ordinary failure preserves the launcher process exit status")
        failureEvents.removeAll()
        _ = StartupFailureDelivery.deliver(
            .partial(reason: "startup-interrupted"), previewUI: false, message: { _ in "fixed message" },
            log: { event, reason in failureEvents.append("\(event):\(reason)") },
            setExitCode: { deliveredExitCode = $0 },
            showPreviewError: { _, _ in failureEvents.append("gui") },
            terminate: { failureEvents.append("exit:\($0)") }
        )
        expect(failureEvents == ["startup-partial:startup-interrupted", "exit:2"],
               "ordinary partial outcomes fixed-log and use exit status two")
        expect(deliveredExitCode == 2, "ordinary partial outcomes preserve exit status two")
        failureEvents.removeAll()
        _ = StartupFailureDelivery.deliver(
            .failed(reason: "protocol-error"), previewUI: true, message: { _ in "fixed message" },
            log: { event, reason in failureEvents.append("\(event):\(reason)") },
            setExitCode: { deliveredExitCode = $0 },
            showPreviewError: { _, _ in failureEvents.append("gui") },
            terminate: { failureEvents.append("exit:\($0)") }
        )
        expect(failureEvents == ["startup-failed:protocol-error", "gui"],
               "promoted preview startup failure retains its visible error path")
        expect(deliveredExitCode == 1, "preview UI keeps the prior failure exit status")

        expect(StartupLogPolicy.filePath(arguments: ["Agent Skin", "--probe", "--log", "/tmp/probe.jsonl"]) == nil,
               "probe mode does not initialize a requested log file")
        expect(StartupLogPolicy.filePath(arguments: ["Agent Skin", "--log", "/tmp/startup.jsonl"]) == "/tmp/startup.jsonl",
               "non-probe modes keep their requested log file")

        let dailyEvents = URL(fileURLWithPath: "/tmp/daily")
        expect(StartupLogPolicy.filePath(arguments: ["Agent Skin", "--log", "/tmp/startup.jsonl"],
                                         dailyEventDirectory: dailyEvents) == "/tmp/startup.jsonl",
               "explicit --log keeps priority over the daily event sink")
        expect(StartupLogPolicy.filePath(arguments: ["Agent Skin"],
                                         dailyEventDirectory: dailyEvents) == "/tmp/daily/events.jsonl",
               "plain launches fall back to the daily event sink")
        expect(StartupLogPolicy.filePath(arguments: ["Agent Skin", "--preview"], dailyEventDirectory: dailyEvents) == nil,
               "preview does not open the daily event sink")
        expect(StartupLogPolicy.filePath(arguments: ["Agent Skin", "--smoke-test"], dailyEventDirectory: dailyEvents) == nil,
               "smoke tests do not open the daily event sink")
        expect(StartupEventJournal.directory(host: .zcode).lastPathComponent == "AzhouZCodeStartup",
               "ZCode daily events land in the ZCode log directory")
        expect(StartupEventJournal.directory(host: nil).lastPathComponent == "AzhouCodexStartup",
               "an unknown host falls back to the Codex log directory")

        do {
            let journal = URL(fileURLWithPath: NSTemporaryDirectory())
                .appendingPathComponent("azhou-startup-journal-\(getuid())-\(UUID().uuidString)", isDirectory: true)
            let path = journal.appendingPathComponent("events.jsonl").path
            if let first = StartupEventJournal.appendHandle(path: path) {
                try? first.write(contentsOf: Data("first\n".utf8)); try? first.close()
            }
            if let second = StartupEventJournal.appendHandle(path: path) {
                try? second.write(contentsOf: Data("second\n".utf8)); try? second.close()
            }
            expect((try? String(contentsOfFile: path, encoding: .utf8)) == "first\nsecond\n",
                   "the daily event sink appends across launches instead of truncating")
            if let big = StartupEventJournal.appendHandle(path: path) {
                try? big.truncate(atOffset: 2 * 1024 * 1024 + 1); try? big.close()
            }
            if let capped = StartupEventJournal.appendHandle(path: path) {
                expect((try? capped.seekToEnd()) == 0,
                       "the daily event sink truncates itself once it exceeds the 2 MiB bound")
                try? capped.close()
            }
            let link = journal.appendingPathComponent("linked-events.jsonl")
            try? FileManager.default.createSymbolicLink(atPath: link.path, withDestinationPath: "/etc/passwd")
            expect(StartupEventJournal.appendHandle(path: link.path) == nil,
                   "the daily event sink refuses a symlinked sink path")
            try? FileManager.default.removeItem(atPath: journal.path)
        }

        let discoveredTarget = URL(fileURLWithPath: "/Applications/Codex.app")
        var targetLookupCalls = 0
        func targetLookup(arguments: [String], promoted: Bool = false) -> URL? {
            StartupModePolicy.resolveTarget(arguments: arguments, promoted: promoted) {
                targetLookupCalls += 1
                return discoveredTarget
            }
        }
        expect(targetLookup(arguments: ["Agent Skin", "--preview"]) == nil && targetLookupCalls == 0,
               "preview mode does not discover the official application")
        expect(targetLookup(arguments: ["Agent Skin", "--smoke-test"]) == nil && targetLookupCalls == 0,
               "smoke mode does not discover the official application")
        expect(targetLookup(arguments: ["Agent Skin", "--probe"]) == discoveredTarget && targetLookupCalls == 1,
               "probe performs read-only target discovery")
        expect(targetLookup(arguments: ["Agent Skin"]) == discoveredTarget && targetLookupCalls == 2,
               "normal launch discovers the target before trusted startup")
        expect(targetLookup(arguments: ["Agent Skin", "--preview"], promoted: true) == discoveredTarget
               && targetLookupCalls == 3,
               "an explicitly promoted preview discovers the target when trusted startup begins")

        let wrongPIDSystem = FakeStartupSystem(expectedPID: 9999, ports: [9222])
        let wrongPIDTransport = FakeStartupTransport()
        let wrongPID = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: wrongPIDSystem,
            transport: wrongPIDTransport,
            now: { 0 },
            sleep: { _ in }
        ).run(payload: "test-only-probe", deadline: 60)
        expect(wrongPID == .failed(reason: "target-identity"), "wrong PID fails closed")
        expect(wrongPIDTransport.evaluateCount == 0, "wrong PID sends no startup payload")

        let wrongPortTransport = FakeStartupTransport()
        let wrongPort = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9223]),
            transport: wrongPortTransport,
            now: { 0 },
            sleep: { _ in }
        ).run(payload: "test-only-probe", deadline: 60)
        expect(wrongPort == .failed(reason: "listener-mismatch"), "a port owned by another listener fails closed")
        expect(wrongPortTransport.pagesCount == 0 && wrongPortTransport.evaluateCount == 0,
               "wrong listener ownership is rejected before page lookup or payload")

        var fakeNow: TimeInterval = 0
        let startupURL = "app://-/index.html?initialRoute=%2F"
        let successfulTransport = FakeStartupTransport(
            pages: [[
                "type": "page", "id": "selected-page", "url": startupURL,
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"
            ]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": [
                    "owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": 7,
                    "ready": true, "completed": false, "overlay": true, "reason": "",
                    "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
                    "completion": NSNull()
                ]]
            ],
            pageFailures: 1
        )
        let successful = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: successfulTransport,
            now: { fakeNow },
            sleep: { fakeNow += $0 }
        ).run(payload: "test-only-probe", deadline: 1)
        expect(successful == .ready(runID: 7), "a controlled main page reaches startup-ready")
        expect(successfulTransport.pagesCount == 4, "page discovery retries and rechecks identity before install and ready within the shared budget")
        expect(successfulTransport.connectCount == 1, "startup uses one selected page socket")
        expect(successfulTransport.payloadCount == 1, "startup installs its payload once")
        expect(successfulTransport.closeCount == 1, "startup closes its socket on readiness")
        expect(successfulTransport.disposeCount == 0, "successful startup is not disposed")

        var skippedNow: TimeInterval = 0
        let skippedTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": [
                    "owner": "azhou-codex-startup", "version": 1, "phase": "complete", "runId": 8,
                    "ready": false, "completed": true, "overlay": false, "reason": "",
                    "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
                    "completion": ["cause": "skip", "beforeReady": true]
                ]]
            ]
        )
        let skipped = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: skippedTransport,
            now: { skippedNow },
            sleep: { skippedNow += $0 }
        ).run(payload: "test-only-probe", deadline: 1)
        expect(skipped == .skipped(runID: 8, beforeReady: true), "a pre-ready skip stays distinct from readiness")
        expect(skippedTransport.payloadCount == 1 && skippedTransport.closeCount == 1,
               "skip does not replay and closes its page socket")

        var savedNow: TimeInterval = 0
        let savedTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": [
                    "owner": "azhou-codex-startup", "version": 1, "phase": "complete", "runId": 9,
                    "ready": true, "completed": true, "overlay": false, "reason": "",
                    "wallpaper": ["applied": true, "reason": "", "imageDecoded": true],
                    "completion": ["cause": "settings-save", "beforeReady": false]
                ]]
            ]
        )
        let saved = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: savedTransport,
            now: { savedNow },
            sleep: { savedNow += $0 }
        ).run(payload: "test-only-probe", deadline: 1)
        expect(saved == .ready(runID: 9), "a completed settings save remains a valid ready attachment")
        expect(savedTransport.payloadCount == 1 && savedTransport.disposeCount == 0,
               "settings save does not cause the connector to dispose the installed controller")

        var navigationNow: TimeInterval = 0
        let navigationTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": "app://-/index.html?initialRoute=%2Fsettings", "missing": false]
            ]
        )
        let navigation = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: navigationTransport,
            now: { navigationNow },
            sleep: { navigationNow += $0 }
        ).run(payload: "test-only-probe", deadline: 1)
        expect(navigation == .partial(reason: "startup-interrupted"), "navigation interrupts the owned startup run")
        expect(navigationTransport.payloadCount == 1 && navigationTransport.closeCount == 1,
               "navigation does not reinject and closes its page socket")
        expect(navigationTransport.disposeCount == 0, "navigation does not dispose an untrusted document")

        var driftNow: TimeInterval = 0
        func loadingStatus(_ runID: Int) -> [String: Any] {
            ["owner": "azhou-codex-startup", "version": 1, "phase": "loading", "runId": runID,
             "ready": false, "completed": false, "overlay": true, "reason": "",
             "wallpaper": ["applied": false, "reason": "", "imageDecoded": false], "completion": NSNull()]
        }
        let driftTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": loadingStatus(9)],
                ["href": startupURL, "missing": false, "status": [
                    "owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": 10,
                    "ready": true, "completed": false, "overlay": true, "reason": "",
                    "wallpaper": ["applied": false, "reason": "", "imageDecoded": false], "completion": NSNull()
                ]]
            ]
        )
        let drift = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: driftTransport,
            now: { driftNow },
            sleep: { driftNow += $0 }
        ).run(payload: "test-only-probe", deadline: 1)
        expect(drift == .partial(reason: "startup-interrupted"), "a status run ID change interrupts the owned startup run")
        expect(driftTransport.disposeCount == 0, "a changed status run ID does not dispose another run")

        var stalledNow: TimeInterval = 0
        let stalledTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": loadingStatus(11)]
            ],
            repeatLastEvaluation: true
        )
        let stalled = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: stalledTransport,
            now: { stalledNow },
            sleep: { stalledNow += $0 }
        ).run(payload: "test-only-probe", deadline: 0.35)
        expect(stalled == .failed(reason: "attach-timeout"), "never-ready polling ends at the shared deadline")
        expect(stalledTransport.payloadCount == 1 && stalledTransport.closeCount == 1,
               "never-ready polling does not reinstall and closes the session")
        expect(stalledTransport.requestTimeouts.allSatisfy { $0 <= 0.35 },
               "page lookup, WebSocket connect, and evaluation requests stay inside the absolute budget")
        expect(stalledTransport.requestTimeouts.contains { $0 < 0.1 },
               "the final status request is truncated to the remaining stage time")

        var malformedNow: TimeInterval = 0
        let malformedStatusTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": [
                    "owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": true,
                    "ready": true, "completed": false, "overlay": true, "reason": "",
                    "wallpaper": ["applied": false, "reason": "", "imageDecoded": false], "completion": NSNull()
                ]]
            ]
        )
        let malformedStatus = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: malformedStatusTransport,
            now: { malformedNow },
            sleep: { malformedNow += $0 }
        ).run(payload: "test-only-probe", deadline: 1)
        expect(malformedStatus == .failed(reason: "protocol-error"), "a malformed required status field is rejected")
        expect(malformedStatusTransport.disposeCount == 1 && malformedStatusTransport.closeCount == 1,
               "malformed status on the trusted installed controller attempts disposal before closing")
        expect(malformedStatusTransport.disposalHrefs == [startupURL],
               "cleanup passes only the inspected document URL to the controller-bound transport")

        var expiredNow: TimeInterval = 0
        let expiredMalformedStatusTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": ["owner": "unknown"]]
            ],
            afterEvaluation: { _, index in if index == 2 { expiredNow = 1 } }
        )
        let expiredMalformedStatus = await StartupConnector(
            target: existing, expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: expiredMalformedStatusTransport,
            now: { expiredNow }, sleep: { expiredNow += $0 }
        ).run(payload: "test-only-probe", deadline: 1)
        expect(expiredMalformedStatus == .failed(reason: "protocol-error"),
               "malformed status remains a protocol failure when its response exhausts the budget")
        expect(expiredMalformedStatusTransport.disposeCount == 0 && expiredMalformedStatusTransport.closeCount == 1,
               "deadline exhaustion closes without starting cleanup work")

        let requestState = StartupCDPRequestState()
        let firstRequestID = try requestState.begin()
        expect(firstRequestID == 1, "CDP request IDs begin at one")
        refuses("CDP allows only one pending request") { _ = try requestState.begin() }
        requestState.finish()
        let secondRequestID = try requestState.begin()
        expect(secondRequestID == 2, "CDP request IDs increase monotonically")
        requestState.finish()
        let validReply = try StartupCDPProtocol.decode(
            Data(#"{"id":2,"result":{"result":{"value":{"installed":true}}}}"#.utf8), expectedID: 2
        )
        if case .result(let value) = validReply {
            expect(value["installed"] as? Bool == true, "CDP returns only the matching by-value result")
        } else { fatalError("FAILED: matching CDP response is decoded") }
        let event = try StartupCDPProtocol.decode(Data(#"{"method":"Page.frameStartedLoading"}"#.utf8), expectedID: 3)
        if case .event = event { checks += 1 } else { fatalError("FAILED: CDP events do not complete a request") }
        refuses("late CDP IDs are rejected") {
            _ = try StartupCDPProtocol.decode(Data(#"{"id":2,"result":{"result":{"value":{}}}}"#.utf8), expectedID: 3)
        }
        refuses("remote CDP errors are rejected") {
            _ = try StartupCDPProtocol.decode(Data(#"{"id":3,"error":{"code":-1}}"#.utf8), expectedID: 3)
        }
        refuses("CDP JavaScript exceptions are rejected") {
            _ = try StartupCDPProtocol.decode(Data(#"{"id":3,"result":{"exceptionDetails":{}}}"#.utf8), expectedID: 3)
        }

        #if AGENT_SKIN_NATIVE_EVENT_TESTS
        checks += try await startupIdentityDiagnosticChecks()
        checks += try await startupPageReplacementChecks()
        checks += try await startupControllerBindingChecks()
        checks += try await nativeEventContractChecks()
        checks += try await skinHostContractChecks()
        checks += try await zcodeRuntimeReviewChecks()
        checks += nativePureStatusContractChecks()
        #endif

        print("Startup native checks passed: \(checks). Scope: injected host facts and transport only; no real open/kill.")
    }
}

private final class FakeStartupSystem: StartupTargetSystem {
    let expectedPID: Int32
    let ports: [Int]
    var preflightError: Error?
    var validationError: Error?
    var afterPreflight: (() -> Void)?
    var afterValidation: (() -> Void)?
    private(set) var preflightBundles: [URL] = []
    private(set) var validatedPIDs: [Int32] = []
    init(expectedPID: Int32, ports: [Int]) { self.expectedPID = expectedPID; self.ports = ports }
    func preflightBundle(_ bundle: URL, deadline: TimeInterval) throws {
        preflightBundles.append(bundle)
        if let preflightError { throw preflightError }
        afterPreflight?()
    }
    func validate(_ target: StartupTargetFacts, deadline: TimeInterval) throws {
        validatedPIDs.append(target.pid)
        afterValidation?()
        if let validationError { throw validationError }
        guard target.pid == expectedPID else {
            throw StartupFailure(reason: "target-identity", message: "fake target mismatch")
        }
    }
    func listeningPorts(_ target: StartupTargetFacts, deadline: TimeInterval) throws -> [Int] { ports }
    func acquireOperationLock(pid: Int32) throws -> any StartupOperationLock { FakeStartupLock() }
}

private final class FakeStartupLock: StartupOperationLock {
    func release() {}
}

private final class FakeStartupTransport: StartupTransport {
    private(set) var evaluateCount = 0
    private(set) var pagesCount = 0
    private(set) var connectCount = 0
    private(set) var closeCount = 0
    private(set) var payloadCount = 0
    private(set) var requestTimeouts: [TimeInterval] = []
    private(set) var disposeCount = 0
    private(set) var disposalHrefs: [String] = []
    private var pageResponses: [[String: Any]]
    private var evaluationResponses: [[String: Any]]
    private var pageFailures: Int
    private var repeatLastEvaluation: Bool
    private var lastEvaluation: [String: Any]?
    private let afterEvaluation: ((String, Int) -> Void)?

    init(pages: [[String: Any]] = [], evaluations: [[String: Any]] = [], pageFailures: Int = 0,
         repeatLastEvaluation: Bool = false, afterEvaluation: ((String, Int) -> Void)? = nil) {
        pageResponses = pages
        evaluationResponses = evaluations
        self.pageFailures = pageFailures
        self.repeatLastEvaluation = repeatLastEvaluation
        self.afterEvaluation = afterEvaluation
    }

    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        pagesCount += 1
        requestTimeouts.append(timeout)
        if pageFailures > 0 {
            pageFailures -= 1
            throw WallpaperFailure(state: "endpoint-unavailable", chinese: "临时错误", english: "Temporary error.")
        }
        return pageResponses
    }
    func connect(to url: URL, timeout: TimeInterval) throws {
        connectCount += 1
        requestTimeouts.append(timeout)
    }
    func evaluate(_ expression: String, timeout: TimeInterval) async throws -> [String: Any] {
        let index = evaluateCount
        evaluateCount += 1
        requestTimeouts.append(timeout)
        if expression.contains("test-only-probe") { payloadCount += 1 }
        if expression.contains("dispose.value.call(api)") {
            disposeCount += 1
        }
        afterEvaluation?(expression, index)
        if !evaluationResponses.isEmpty {
            lastEvaluation = evaluationResponses.removeFirst()
            return lastEvaluation!
        }
        return repeatLastEvaluation ? lastEvaluation ?? [:] : [:]
    }
    func disposeController(href: String, timeout: TimeInterval) async throws -> [String: Any] {
        disposalHrefs.append(href)
        return try await evaluate(try StartupConnector.disposeExpression(href), timeout: timeout)
    }
    func close() { closeCount += 1 }
}

#if AGENT_SKIN_NATIVE_EVENT_TESTS
@MainActor
private func nativeEventContractChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }

    func validStatus(_ runID: Int, phase: String, ready: Bool, completed: Bool,
                     overlay: Bool, completion: Any) -> [String: Any] {
        ["owner": "azhou-codex-startup", "version": 1, "phase": phase, "runId": runID,
         "ready": ready, "completed": completed, "overlay": overlay, "reason": "",
         "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
         "completion": completion]
    }

    var disabledWallpaper = validStatus(1, phase: "playing", ready: true, completed: false,
                                        overlay: true, completion: NSNull())
    disabledWallpaper["wallpaper"] = ["applied": false, "reason": "disabled", "imageDecoded": false]
    expect(NativeStartupStatus.parse(disabledWallpaper) != nil,
           "a disabled wallpaper remains a valid ready startup status")
    disabledWallpaper["reason"] = "disabled"
    expect(NativeStartupStatus.parse(disabledWallpaper) == nil,
           "disabled is not accepted as a startup failure reason")

    var now = 100.0
    var records: [[String: Any]] = []
    let writer = NativeEventWriter(startedAt: 100, launcherPID: 77,
                                   launcherPath: "/Applications/Agent Skin.app",
                                   now: { now }, sink: { records.append($0) })
    let stream = NativeStartupEventStream(writer: writer)
    stream.begin(at: 100)
    stream.targetOpened(pid: 4123, at: 101)
    let capture = NativeStartupCapture(targetPID: 4123)
    let fake = FakeStartupTransport(evaluations: [
        ["installed": true, "alreadyActive": false],
        ["href": "app://-/index.html?initialRoute=%2F", "missing": false,
         "status": validStatus(23, phase: "loading", ready: false, completed: false, overlay: true,
                                completion: NSNull())],
        ["href": "app://-/index.html?initialRoute=%2F", "missing": false,
         "status": validStatus(23, phase: "playing", ready: true, completed: false, overlay: true,
                                completion: NSNull())]
    ], afterEvaluation: { _, index in now = 102 + Double(index) })
    let observer = NativeStartupEventTransport(base: fake, capture: capture, events: stream, now: { now })
    _ = try await observer.evaluate("test install", timeout: 1)
    _ = try await observer.evaluate("test loading status", timeout: 1)
    _ = try await observer.evaluate("test ready status", timeout: 1)
    let readyResolution = stream.resolve(.ready(runID: 23), observation: capture.snapshot(), at: 104)
    expect(readyResolution == .ready, "the native observer preserves the verified runId and final phase")
    _ = stream.finish(at: 105)
    expect(records.map { $0["event"] as? String ?? "" } == [
        "launcher-start", "target-opened", "startup-installed", "startup-ready", "launcher-exit"
    ], "cold readiness emits the contract sequence")
    expect(records[2]["targetPID"] as? Int == 4123 && records[2]["runId"] as? Int == 23,
           "startup-installed carries the observed target PID and status runId")
    expect(records[3]["targetPID"] as? Int == 4123 && records[3]["runId"] as? Int == 23
           && records[3]["ready"] as? Bool == true && records[3]["phase"] as? String == "playing",
           "startup-ready carries a matching PID, runId, ready flag, and actual phase")
    expect(records[4]["outcome"] as? String == "startup-ready" && records[4]["exitCode"] as? Int == 0,
           "startup-ready exit outcome and code agree")
    let elapsed = records.compactMap { ($0["seconds"] as? NSNumber)?.doubleValue }
    expect(elapsed.count == records.count && elapsed.allSatisfy { $0.isFinite && $0 >= 0 }
           && zip(elapsed, elapsed.dropFirst()).allSatisfy { $0 <= $1 },
           "native event envelope seconds are finite, nonnegative, and monotonic")
    expect(records.allSatisfy {
        $0["schema"] as? String == NativeEventWriter.schema
            && $0["launcherPID"] as? Int == 77
            && $0["launcherPath"] as? String == "/Applications/Agent Skin.app"
    }, "every consumed event has the v1 envelope")

    var skipNow = 200.0
    var skipRecords: [[String: Any]] = []
    let skipWriter = NativeEventWriter(startedAt: 200, launcherPID: 78,
                                       launcherPath: "/Applications/Agent Skin.app",
                                       now: { skipNow }, sink: { skipRecords.append($0) })
    let skipStream = NativeStartupEventStream(writer: skipWriter)
    skipStream.begin(at: 200)
    skipStream.targetOpened(pid: 4124, at: 201)
    skipStream.startupInstalled(pid: 4124, runID: 24, at: 202)
    let skippedStatus = NativeStartupStatus.parse(validStatus(
        24, phase: "complete", ready: false, completed: true, overlay: false,
        completion: ["cause": "skip", "beforeReady": true]
    ))
    let savedStatus = NativeStartupStatus.parse(validStatus(
        24, phase: "complete", ready: true, completed: true, overlay: false,
        completion: ["cause": "settings-save", "beforeReady": false]
    ))
    expect(savedStatus?.completionCause == "settings-save", "native status accepts a completed settings save without animation replay")
    let skippedObservation = NativeStartupObservation(targetPID: 4124, installedAt: 202,
                                                       status: skippedStatus, statusAt: 203)
    let skipResolution = skipStream.resolve(.skipped(runID: 24, beforeReady: true),
                                              observation: skippedObservation, at: 204)
    skipNow = 205
    _ = skipStream.finish(at: 205)
    expect(skipResolution == .skipped
           && skipRecords.map { $0["event"] as? String ?? "" } == [
            "launcher-start", "target-opened", "startup-installed", "startup-skipped", "launcher-exit"
           ], "pre-ready skip is distinct and keeps its own ordered result")
    expect((skipRecords[3]["completion"] as? [String: Any])?["cause"] as? String == "skip"
           && (skipRecords[3]["completion"] as? [String: Any])?["beforeReady"] as? Bool == true
           && skipRecords[3]["completed"] as? Bool == true && skipRecords[3]["overlay"] as? Bool == false,
           "startup-skipped reports only the observed skip completion")
    expect(skipRecords[4]["outcome"] as? String == "skipped" && skipRecords[4]["exitCode"] as? Int == 0,
           "skip exit outcome and code agree")

    var failureRecords: [[String: Any]] = []
    let failureWriter = NativeEventWriter(startedAt: 300, launcherPID: 79,
                                          launcherPath: "/Applications/Agent Skin.app",
                                          now: { 302 }, sink: { failureRecords.append($0) })
    let failureStream = NativeStartupEventStream(writer: failureWriter)
    failureStream.begin(at: 300)
    let failed = failureStream.resolve(.failed(reason: "protocol-error"), observation: nil, at: 301)
    let overwritten = failureStream.resolve(.ready(runID: 25), observation: nil, at: 302)
    _ = failureStream.finish(at: 303)
    expect(failed == .behaviorNotProven(reason: "protocol-error") && overwritten == nil
           && failureRecords.map { $0["event"] as? String ?? "" } == [
            "launcher-start", "startup-failed", "launcher-exit"
           ], "a later success cannot overwrite a startup failure")
    expect(failureRecords[2]["outcome"] as? String == "behavior-not-proven"
           && failureRecords[2]["exitCode"] as? Int == 1,
           "failure exit outcome and code agree")

    var portErrorRecords: [[String: Any]] = []
    let portErrorWriter = NativeEventWriter(startedAt: 320, launcherPID: 85,
                                            launcherPath: "/Applications/Agent Skin.app",
                                            now: { 324 }, sink: { portErrorRecords.append($0) })
    let portErrorStream = NativeStartupEventStream(writer: portErrorWriter)
    portErrorStream.begin(at: 320)
    portErrorStream.portError(operation: "bind-loopback", errno: 48, at: 321)
    let portErrorResolution = portErrorStream.resolve(.ready(runID: 28), observation: nil, at: 322)
    let portErrorOverwritten = portErrorStream.resolve(.ready(runID: 28), observation: nil, at: 323)
    _ = portErrorStream.finish(at: 324)
    expect(portErrorResolution == .behaviorNotProven(reason: "listener-mismatch")
           && portErrorOverwritten == nil
           && portErrorRecords.map { $0["event"] as? String ?? "" } == [
            "launcher-start", "startup-port-error", "startup-failed", "launcher-exit"
           ], "a port failure is retained and cannot be overwritten by a later ready outcome")
    expect(portErrorRecords[1]["schema"] as? String == NativeEventWriter.schema
           && portErrorRecords[1]["reason"] as? String == "listener-mismatch"
           && portErrorRecords[1]["operation"] as? String == "bind-loopback"
           && portErrorRecords[1]["errno"] as? Int == 48
           && portErrorRecords[3]["exitCode"] as? Int == 1,
           "the port failure carries its v1 envelope, fixed reason, and bounded diagnostic fields")

    var latchedFailureRecords: [[String: Any]] = []
    let latchedFailureWriter = NativeEventWriter(startedAt: 350, launcherPID: 83,
                                                 launcherPath: "/Applications/Agent Skin.app",
                                                 now: { 354 }, sink: { latchedFailureRecords.append($0) })
    let latchedFailureStream = NativeStartupEventStream(writer: latchedFailureWriter)
    latchedFailureStream.begin(at: 350)
    latchedFailureStream.latchFailure("javascript-error")
    latchedFailureStream.targetOpened(pid: 4127, at: 351)
    latchedFailureStream.startupInstalled(pid: 4127, runID: 27, at: 352)
    let latchedStatus = NativeStartupStatus.parse(validStatus(
        27, phase: "playing", ready: true, completed: false, overlay: true, completion: NSNull()
    ))
    let latchedObservation = NativeStartupObservation(targetPID: 4127, installedAt: 352,
                                                      status: latchedStatus, statusAt: 353)
    let latchedFailure = latchedFailureStream.resolve(.ready(runID: 27), observation: latchedObservation, at: 354)
    _ = latchedFailureStream.finish(at: 355)
    expect(latchedFailure == .behaviorNotProven(reason: "protocol-error")
           && latchedFailureRecords.map { $0["event"] as? String ?? "" } == [
            "launcher-start", "target-opened", "startup-installed", "startup-failed", "launcher-exit"
           ], "a latched failure retains real milestones but suppresses a later ready event")
    expect(latchedFailureRecords[4]["outcome"] as? String == "behavior-not-proven"
           && latchedFailureRecords[4]["exitCode"] as? Int == 1,
           "a latched failure keeps the nonzero exit code")

    var activeRecords: [[String: Any]] = []
    let activeWriter = NativeEventWriter(startedAt: 375, launcherPID: 84,
                                         launcherPath: "/Applications/Agent Skin.app",
                                         now: { 377 }, sink: { activeRecords.append($0) })
    let activeStream = NativeStartupEventStream(writer: activeWriter)
    activeStream.begin(at: 375)
    activeStream.targetOpened(pid: 4128, at: 376)
    let active = activeStream.resolve(.partial(reason: "startup-active"), observation: nil, at: 377)
    _ = activeStream.finish(at: 378)
    expect(active == .behaviorNotProven(reason: "startup-active")
           && activeRecords.map { $0["event"] as? String ?? "" } == [
            "launcher-start", "target-opened", "startup-failed", "launcher-exit"
           ] && activeRecords[3]["outcome"] as? String == "behavior-not-proven"
           && activeRecords[3]["exitCode"] as? Int == 1,
           "an existing startup controller is a controlled refusal, not an interruption")

    var interruptedRecords: [[String: Any]] = []
    let interruptedWriter = NativeEventWriter(startedAt: 400, launcherPID: 80,
                                              launcherPath: "/Applications/Agent Skin.app",
                                              now: { 404 }, sink: { interruptedRecords.append($0) })
    let interruptedStream = NativeStartupEventStream(writer: interruptedWriter)
    interruptedStream.begin(at: 400)
    interruptedStream.targetOpened(pid: 4125, at: 401)
    interruptedStream.startupInstalled(pid: 4125, runID: 26, at: 402)
    let interrupted = interruptedStream.resolve(.partial(reason: "startup-interrupted"), observation: nil, at: 403)
    _ = interruptedStream.finish(at: 404)
    expect(interrupted == .partial(reason: "startup-interrupted")
           && interruptedRecords.map { $0["event"] as? String ?? "" } == [
            "launcher-start", "target-opened", "startup-installed", "startup-interrupted", "launcher-exit"
           ], "a real install prefix is retained before an interruption")
    expect(interruptedRecords[4]["outcome"] as? String == "partial"
           && interruptedRecords[4]["exitCode"] as? Int == 2,
           "partial exit outcome and code agree")

    var hotRecords: [[String: Any]] = []
    let hotWriter = NativeEventWriter(startedAt: 500, launcherPID: 81,
                                      launcherPath: "/Applications/Agent Skin.app",
                                      now: { 502 }, sink: { hotRecords.append($0) })
    let hotStream = NativeStartupEventStream(writer: hotWriter)
    hotStream.begin(at: 500)
    _ = hotStream.resolve(.activated(pid: 4126), observation: nil, at: 501)
    _ = hotStream.finish(at: 502)
    expect(hotRecords.map { $0["event"] as? String ?? "" } == [
        "launcher-start", "target-activated", "launcher-exit"
    ] && hotRecords[1]["targetPID"] as? Int == 4126,
           "hot activation reports the checked target PID without installation events")
    expect(hotRecords[2]["outcome"] as? String == "activated" && hotRecords[2]["exitCode"] as? Int == 0,
           "activation exit outcome and code agree")

    var interruptedByUserRecords: [[String: Any]] = []
    let interruptedByUserWriter = NativeEventWriter(startedAt: 520, launcherPID: 86,
                                                     launcherPath: "/Applications/Agent Skin.app",
                                                     now: { .nan }, sink: { interruptedByUserRecords.append($0) })
    interruptedByUserWriter.emit("nonfinite-clock", at: .infinity)
    interruptedByUserWriter.emit("clock-regressed", at: 510)
    let interruptedByUserStream = NativeStartupEventStream(writer: interruptedByUserWriter)
    interruptedByUserStream.begin(at: 520)
    interruptedByUserStream.targetOpened(pid: 0, at: 521)
    interruptedByUserStream.targetOpened(pid: 4129, at: 521)
    interruptedByUserStream.targetOpened(pid: 4129, at: 522)
    interruptedByUserStream.targetOpened(pid: 4130, at: 522)
    expect(interruptedByUserStream.isPending, "a begun startup event stream reports pending")
    interruptedByUserStream.latchInterruption("untrusted interruption text")
    interruptedByUserStream.latchInterruption()
    let interruptedByUser = interruptedByUserStream.resolve(.ready(runID: 1), observation: nil, at: 523)
    expect(interruptedByUser == .partial(reason: "startup-interrupted")
           && interruptedByUser?.reason == "startup-interrupted",
           "a latched interruption overrides an unverified ready result with a fixed partial reason")
    _ = interruptedByUserStream.finish(at: 524)
    expect(interruptedByUserRecords.filter { $0["event"] as? String == "target-opened" }.count == 1
           && interruptedByUserRecords.allSatisfy { ($0["seconds"] as? Double)?.isFinite == true },
           "invalid or duplicate target-open events are ignored and nonfinite elapsed time stays finite")
    expect(!interruptedByUserStream.isPending,
           "a finished startup event stream no longer reports pending")

    var interruptedAtTeardownRecords: [[String: Any]] = []
    let interruptedAtTeardown = NativeStartupEventStream(writer: NativeEventWriter(
        startedAt: 530, launcherPID: 87, launcherPath: "/Applications/Agent Skin.app",
        sink: { interruptedAtTeardownRecords.append($0) }
    ))
    interruptedAtTeardown.begin(at: 530)
    interruptedAtTeardown.targetOpened(pid: 4131, at: 531)
    interruptedAtTeardown.latchInterruption()
    expect(interruptedAtTeardown.finish(at: 532) == .partial(reason: "startup-interrupted")
           && interruptedAtTeardownRecords.last?["outcome"] as? String == "partial",
           "teardown converts a latched interruption into one final partial event")

    var unresolvedRecords: [[String: Any]] = []
    let unresolved = NativeStartupEventStream(writer: NativeEventWriter(
        startedAt: 540, launcherPID: 88, launcherPath: "/Applications/Agent Skin.app",
        sink: { unresolvedRecords.append($0) }
    ))
    unresolved.begin(at: 540)
    expect(unresolved.finish(at: 541) == .partial(reason: "startup-interrupted")
           && unresolvedRecords.last?["exitCode"] as? Int == 2,
           "teardown without a resolved outcome fails closed as partial")

    var invalidOutcomeRecords: [[String: Any]] = []
    let invalidReady = NativeStartupEventStream(writer: NativeEventWriter(
        startedAt: 550, launcherPID: 89, launcherPath: "/Applications/Agent Skin.app",
        sink: { invalidOutcomeRecords.append($0) }
    ))
    invalidReady.begin(at: 550)
    expect(invalidReady.resolve(.ready(runID: 1), observation: nil, at: 551)
           == .behaviorNotProven(reason: "protocol-error"),
           "readiness without a matching observed run fails closed")
    let invalidSkip = NativeStartupEventStream(writer: NativeEventWriter(
        startedAt: 560, launcherPID: 90, launcherPath: "/Applications/Agent Skin.app",
        sink: { invalidOutcomeRecords.append($0) }
    ))
    invalidSkip.begin(at: 560)
    expect(invalidSkip.resolve(.skipped(runID: 2, beforeReady: true), observation: nil, at: 561)
           == .behaviorNotProven(reason: "protocol-error"),
           "skip without an observed completion fails closed")
    var pendingFailureRecords: [[String: Any]] = []
    let pendingFailure = NativeStartupEventStream(writer: NativeEventWriter(
        startedAt: 570, launcherPID: 91, launcherPath: "/Applications/Agent Skin.app",
        sink: { pendingFailureRecords.append($0) }
    ))
    pendingFailure.begin(at: 570)
    pendingFailure.latchFailure("asset-invalid")
    expect(pendingFailure.finish(at: 571) == .behaviorNotProven(reason: "asset-invalid")
           && pendingFailureRecords.last?["outcome"] as? String == "behavior-not-proven",
           "teardown preserves a latched startup failure when no resolution arrived")

    var smokeResources: [String: Int] = [:]
    for key in [
        "createdImages", "releasedImages", "liveImages",
        "createdBitmaps", "releasedBitmaps", "liveBitmaps",
        "createdCanvases", "releasedCanvases", "liveCanvases",
        "createdPaths", "releasedPaths", "livePaths",
        "createdRAF", "cancelledRAF", "liveRAF",
        "createdObjectURLs", "revokedObjectURLs", "liveObjectURLs",
        "framesPending"
    ] { smokeResources[key] = 0 }
    var smokeReport: [String: Any] = [
        "elapsed": 12, "duration": 12, "completed": true, "skipped": false,
        "reduced": false, "stage": "complete", "animationProgress": 1,
        "viewport": ["width": 1440, "height": 900, "dpr": 1],
        "coordinateSize": ["width": 1536, "height": 1024],
        "resources": smokeResources,
        "jsFrame": [
            "rafIntervalMs": NSNull(), "renderSubmissionMs": NSNull(),
            "scope": "JavaScript rAF interval and 2D canvas submission; excludes GPU/compositor/presentation timing"
        ]
    ]
    func smokeReportJSON(_ value: [String: Any]) throws -> String {
        let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
        guard let json = String(data: data, encoding: .utf8) else { throw StartupFailure(reason: "protocol-error", message: "test") }
        return json
    }
    let validSmokeReport = try smokeReportJSON(smokeReport)
    expect(NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: false, reportJSON: validSmokeReport, evaluationFailed: false
    ), "smoke accepts a complete non-skipped renderer report")
    var measuredSmokeReport = smokeReport
    measuredSmokeReport["jsFrame"] = [
        "scope": "JavaScript rAF interval and 2D canvas submission; excludes GPU/compositor/presentation timing",
        "rafIntervalMs": ["count": 12, "median": 16.7, "p95": 17.1, "max": 18.0],
        "renderSubmissionMs": ["count": 12, "median": 1.2, "p95": 1.8, "max": 2.0],
    ]
    let measuredSmokeJSON = try smokeReportJSON(measuredSmokeReport)
    expect(NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: false, reportJSON: measuredSmokeJSON, evaluationFailed: false
    ), "smoke accepts finite frame statistics when the renderer reports measurements")
    expect(!NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: true, reportJSON: validSmokeReport, evaluationFailed: false
    ), "the reachable Skip/Esc completion cannot pass smoke")
    expect(!NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: nil, reportJSON: validSmokeReport, evaluationFailed: false
    ), "smoke rejects a completion message without its explicit skip state")
    expect(!NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: false, reportJSON: "{", evaluationFailed: false
    ) && !NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: false, reportJSON: nil, evaluationFailed: false
    ), "smoke rejects malformed or missing report JSON")
    expect(!NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: false, reportJSON: validSmokeReport, evaluationFailed: true
    ), "smoke rejects a failed report evaluation")
    for invalidStats in [
        [String: Any](),
        ["count": 0, "median": 1, "p95": 1, "max": 1] as [String: Any],
        ["count": 1.5, "median": 1, "p95": 1, "max": 1] as [String: Any],
        ["count": 1, "median": "bad", "p95": 1, "max": 1] as [String: Any],
        ["count": 1, "median": 1, "p95": "bad", "max": 1] as [String: Any],
        ["count": 1, "median": 1, "p95": 1, "max": "bad"] as [String: Any],
    ] {
        var invalidStatsReport = smokeReport
        invalidStatsReport["jsFrame"] = [
            "scope": "JavaScript rAF interval and 2D canvas submission; excludes GPU/compositor/presentation timing",
            "rafIntervalMs": invalidStats, "renderSubmissionMs": NSNull(),
        ]
        let invalidStatsJSON = try smokeReportJSON(invalidStatsReport)
        expect(!NativeSmokeReportValidator.isSuccessfulCompletion(
            skipped: false, reportJSON: invalidStatsJSON, evaluationFailed: false
        ), "smoke rejects invalid frame percentile statistics")
    }
    smokeReport.removeValue(forKey: "resources")
    let incompleteSmokeReport = try smokeReportJSON(smokeReport)
    expect(!NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: false, reportJSON: incompleteSmokeReport, evaluationFailed: false
    ), "smoke rejects an incomplete renderer report")
    smokeReport["resources"] = smokeResources
    smokeReport["skipped"] = true
    let skippedSmokeReport = try smokeReportJSON(smokeReport)
    expect(!NativeSmokeReportValidator.isSuccessfulCompletion(
        skipped: false, reportJSON: skippedSmokeReport, evaluationFailed: false
    ), "smoke rejects a report that records a skipped completion")

    var smokeRecords: [[String: Any]] = []
    let smokeWriter = NativeEventWriter(startedAt: 600, launcherPID: 82,
                                        launcherPath: "/Applications/Agent Skin.app",
                                        now: { 601 }, sink: { smokeRecords.append($0) })
    for event in ["player-start", "playback-start", "animation-complete", "preview-result"] {
        smokeWriter.emit(event)
    }
    smokeWriter.emit("player-terminated", fields: ["completed": true, "failed": false])
    expect(smokeRecords.map { $0["event"] as? String ?? "" } == [
        "player-start", "playback-start", "animation-complete", "preview-result", "player-terminated"
    ] && smokeRecords.last?["completed"] as? Bool == true && smokeRecords.last?["failed"] as? Bool == false,
           "smoke keeps the independent five-event sequence and completion fields")
    expect(smokeRecords.allSatisfy { $0["schema"] as? String == NativeEventWriter.schema },
           "smoke events also carry the v1 envelope")

    let snapshotDirectory = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-player-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: snapshotDirectory) }
    let playerRuntime = FakeNativeAppRuntime(arguments: [
        "agent-skin", "--smoke-test", "--snapshot", snapshotDirectory.path,
        "--snapshot-times", "0,1,NaN,-1,3"
    ])
    let playerPresentation = FakeNativePlayerPresentation()
    playerPresentation.evaluationResult = (validSmokeReport, nil)
    let player = AppDelegate(runtime: playerRuntime, presentation: playerPresentation)
    player.receivePlayerMessage(body: ["action": "ready", "locale": "zh-CN", "duration": 3_000], isMainFrame: false)
    expect(playerPresentation.readyCount == 0 && playerPresentation.evaluations.isEmpty,
           "player ignores ready messages from a subframe")
    player.receivePlayerMessage(body: ["action": "ready", "locale": "zh-CN", "duration": 3_000], isMainFrame: true)
    expect(playerPresentation.readyCount == 1 && playerPresentation.updatedLocales == [.chinese]
           && playerPresentation.evaluations.first == "window.launcherUI.replay()",
           "verified main-frame ready message localizes and starts the preview renderer")
    expect(playerPresentation.schedules.map(\.delay) == [25, 0, 1],
           "ready schedules the completion watchdog and only finite in-range snapshots")
    playerPresentation.schedules[1].fire()
    expect(playerRuntime.output.contains { $0.contains("snapshot-error") && $0.contains("no image") },
           "a failed native snapshot is reported without failing the animation")
    let evaluationsBeforeDuplicate = playerPresentation.evaluations.count
    player.receivePlayerMessage(body: ["action": "ready", "locale": "en", "duration": 1_000], isMainFrame: true)
    expect(playerPresentation.readyCount == 1 && playerPresentation.evaluations.count == evaluationsBeforeDuplicate,
           "duplicate ready messages are ignored")
    player.receivePlayerMessage(body: ["action": "complete", "skipped": false], isMainFrame: true)
    let playerEvents = playerRuntime.output.compactMap { line -> (String, Bool?)? in
        guard let data = line.data(using: .utf8), let record = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let event = record["event"] as? String else { return nil }
        return (event, record["success"] as? Bool)
    }
    expect(playerRuntime.terminated == 1 && playerEvents.contains { $0.0 == "preview-result" && $0.1 == true },
           "a verified complete smoke report succeeds and terminates through the fake runtime")
    let evaluationCountAtEnd = playerPresentation.evaluations.count
    player.receivePlayerMessage(body: "close", isMainFrame: true)
    player.receivePlayerMessage(body: ["action": "jsError"], isMainFrame: true)
    expect(playerRuntime.terminated == 1 && playerPresentation.evaluations.count == evaluationCountAtEnd,
           "messages after completion cannot re-enter the terminated player flow")

    let failureRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    let failurePresentation = FakeNativePlayerPresentation()
    let failurePlayer = AppDelegate(runtime: failureRuntime, presentation: failurePresentation)
    failurePlayer.receivePlayerMessage(body: "jsError", isMainFrame: true)
    expect(failurePresentation.errors.count == 1 && failurePresentation.errors[0].2 == "Close"
           && failureRuntime.terminated == 1,
           "a renderer error before readiness displays a localized native error and terminates")

    let failedPage = WKWebView(frame: .zero)
    let provisionalFailureRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    let provisionalFailurePresentation = FakeNativePlayerPresentation()
    let provisionalFailureDelegate = AppDelegate(runtime: provisionalFailureRuntime,
                                                  presentation: provisionalFailurePresentation)
    provisionalFailureDelegate.webView(failedPage, didFailProvisionalNavigation: nil,
                                       withError: NSError(domain: "NativeStartupTests", code: 10,
                                                          userInfo: [NSLocalizedDescriptionKey: "fixture provisional failure"]))
    expect(provisionalFailureRuntime.terminated == 1
           && provisionalFailurePresentation.errors.first?.1 == "fixture provisional failure"
           && provisionalFailureRuntime.output.contains { $0.contains("navigation-error") },
           "a provisional page-navigation failure reaches the native error path")

    let navigationFailureRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    let navigationFailurePresentation = FakeNativePlayerPresentation()
    let navigationFailureDelegate = AppDelegate(runtime: navigationFailureRuntime,
                                                  presentation: navigationFailurePresentation)
    navigationFailureDelegate.webView(failedPage, didFail: nil,
                                      withError: NSError(domain: "NativeStartupTests", code: 11,
                                                         userInfo: [NSLocalizedDescriptionKey: "fixture navigation failure"]))
    expect(navigationFailureRuntime.terminated == 1
           && navigationFailurePresentation.errors.first?.1 == "fixture navigation failure"
           && navigationFailureRuntime.output.contains { $0.contains("navigation-error") },
           "a committed page-navigation failure reaches the native error path")

    let terminatedRendererRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    let terminatedRendererPresentation = FakeNativePlayerPresentation()
    let terminatedRendererDelegate = AppDelegate(runtime: terminatedRendererRuntime,
                                                  presentation: terminatedRendererPresentation)
    terminatedRendererDelegate.webViewWebContentProcessDidTerminate(failedPage)
    expect(terminatedRendererRuntime.terminated == 1
           && terminatedRendererPresentation.errors.first?.1 == NativeDisplayLocale.english.message(for: "renderer-terminated")
           && terminatedRendererRuntime.output.contains { $0.contains("renderer-terminated") },
           "a terminated WebKit content process displays the localized renderer failure")

    let unhandledRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    let unhandledPlayer = AppDelegate(runtime: unhandledRuntime, presentation: FakeNativePlayerPresentation())
    unhandledPlayer.receivePlayerMessage(body: ["action": "unknown"], isMainFrame: true)
    expect(unhandledRuntime.output.contains { $0.contains("unhandled-message") && $0.contains("unknown") },
           "unrecognized player messages are retained in the native event log")
    let ignoredRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    let ignoredPlayerPresentation = FakeNativePlayerPresentation()
    let ignoredPlayer = AppDelegate(runtime: ignoredRuntime, presentation: ignoredPlayerPresentation)
    ignoredPlayer.receivePlayerMessage(body: "close", isMainFrame: false)
    _ = ignoredPlayer.applicationShouldTerminate(NSApplication.shared)
    expect(ignoredRuntime.terminated == 0 && ignoredPlayerPresentation.errors.isEmpty,
           "non-main-frame close and a user-initiated preview termination do not request a host activation")

    let previewResources = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-preview-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: previewResources) }
    let previewWebRoot = previewResources.appendingPathComponent("web", isDirectory: true)
    try FileManager.default.createDirectory(at: previewWebRoot, withIntermediateDirectories: true)
    try Data("<!doctype html><title>synthetic preview</title>".utf8)
        .write(to: previewWebRoot.appendingPathComponent("index.html"))
    let previewRuntime = FakeNativeAppRuntime(arguments: [
        "agent-skin", "--preview", "--inspect", "--snapshot", snapshotDirectory.path,
        "--snapshot-times", "0,1"
    ], resourceURL: previewResources)
    let previewPresentation = FakeNativePlayerPresentation()
    let previewPlayer = AppDelegate(runtime: previewRuntime, presentation: previewPresentation)
    previewPlayer.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    expect(previewRuntime.accessoryPolicyChanges == 1 && previewPresentation.createdPlayers.count == 1
           && previewPresentation.createdPlayers[0].0 == .english
           && previewPresentation.createdPlayers[0].1 == "preview"
           && previewPresentation.createdPlayers[0].2 == "light"
           && previewPresentation.createdPlayers[0].3,
           "preview launch configures the injected player with locale, theme, and inspect state")
    expect(previewPresentation.loadedPlayers.count == 1
           && previewPresentation.loadedPlayers[0].0 == previewWebRoot.appendingPathComponent("index.html")
           && previewPresentation.loadedPlayers[0].1 == previewWebRoot
           && previewPresentation.schedules.count == 1 && previewPresentation.schedules[0].delay == 20,
           "preview launch loads only its local page and arms the renderer-ready watchdog")
    _ = previewPlayer.windowShouldClose(NSWindow())
    previewPlayer.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(previewRuntime.terminated == 1 && previewRuntime.acquiredLock?.releaseCount == 1
           && previewPresentation.stopCount == 1 && previewPresentation.removedHandlers == ["launcher"],
           "preview close releases its owned lock and removes the local WebKit handler")

    let missingPageResources = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-missing-page-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: missingPageResources) }
    try FileManager.default.createDirectory(at: missingPageResources, withIntermediateDirectories: true)
    let missingPageRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"], resourceURL: missingPageResources)
    let missingPagePresentation = FakeNativePlayerPresentation()
    AppDelegate(runtime: missingPageRuntime, presentation: missingPagePresentation)
        .applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    expect(missingPagePresentation.createdPlayers.count == 1 && missingPagePresentation.loadedPlayers.isEmpty
           && missingPagePresentation.errors.first?.1.contains("page") == true && missingPageRuntime.terminated == 1,
           "preview launch refuses a resource bundle with no local index page")

    let missingResourceRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--smoke-test"])
    let missingResourcePresentation = FakeNativePlayerPresentation()
    let missingResourcePlayer = AppDelegate(runtime: missingResourceRuntime, presentation: missingResourcePresentation)
    missingResourcePlayer.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    missingResourcePlayer.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(missingResourcePresentation.createdPlayers.count == 1 && missingResourcePresentation.loadedPlayers.isEmpty
           && missingResourceRuntime.terminated == 1 && missingResourceRuntime.processExitCode == 1,
           "smoke startup fails closed when the app bundle has no resource directory")

    let duplicateRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    duplicateRuntime.lockBusy = true
    let duplicate = FakeNativeApplication(pid: 43, bundleIdentifier: "local.azhou.codex-startup",
                                          bundleURL: URL(fileURLWithPath: "/Applications/Agent Skin.app"))
    duplicateRuntime.applications = [duplicate]
    AppDelegate(runtime: duplicateRuntime, presentation: FakeNativePlayerPresentation())
        .applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    expect(duplicate.activationCount == 1 && duplicateRuntime.terminated == 1,
           "a second entry activates the running launcher and exits without creating another player")

    let lockErrorRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    lockErrorRuntime.lockError = 13
    AppDelegate(runtime: lockErrorRuntime, presentation: FakeNativePlayerPresentation())
        .applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    expect(lockErrorRuntime.terminated == 1
           && lockErrorRuntime.output.contains { $0.contains("lock-error") && $0.contains("13") },
           "instance-lock errors are logged and abort the preview before UI creation")

    let startupLockErrorRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"])
    startupLockErrorRuntime.lockError = 13
    let startupLockError = AppDelegate(runtime: startupLockErrorRuntime, presentation: FakeNativePlayerPresentation())
    startupLockError.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    startupLockError.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    let startupLockErrorEvents = startupLockErrorRuntime.output.compactMap { line -> [String: Any]? in
        guard let data = line.data(using: .utf8) else { return nil }
        return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    }
    let lockFailureEvent = startupLockErrorEvents.first { $0["event"] as? String == "startup-failed" }
    let lockExitEvent = startupLockErrorEvents.first { $0["event"] as? String == "launcher-exit" }
    expect(startupLockErrorRuntime.terminated == 1 && startupLockErrorRuntime.processExitCode == 1
           && lockFailureEvent?["reason"] as? String == "protocol-error"
           && lockExitEvent?["outcome"] as? String == "behavior-not-proven"
           && lockExitEvent?["exitCode"] as? Int == 1,
           "normal startup reports its instance-lock protocol failure and failing exit record")

    let smokeLockErrorRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--smoke-test"])
    smokeLockErrorRuntime.lockError = 13
    let smokeLockErrorPresentation = FakeNativePlayerPresentation()
    let smokeLockError = AppDelegate(runtime: smokeLockErrorRuntime, presentation: smokeLockErrorPresentation)
    smokeLockError.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    smokeLockError.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    let smokeLockTermination = smokeLockErrorRuntime.output.compactMap { line -> [String: Any]? in
        guard let data = line.data(using: .utf8) else { return nil }
        return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    }.first { $0["event"] as? String == "player-terminated" }
    expect(smokeLockErrorRuntime.terminated == 1 && smokeLockErrorRuntime.processExitCode == 1
           && smokeLockErrorPresentation.createdPlayers.isEmpty
           && smokeLockTermination?["failed"] as? Bool == true
           && smokeLockTermination?["completed"] as? Bool == false,
           "smoke mode records a failing exit when the instance lock is unavailable before UI setup")

    let syntheticCodex = FileManager.default.temporaryDirectory
        .appendingPathComponent("Synthetic Codex-" + UUID().uuidString + ".app", isDirectory: true)
    defer { try? FileManager.default.removeItem(at: syntheticCodex) }
    let executable = syntheticCodex.appendingPathComponent("Contents/MacOS/Codex")
    try FileManager.default.createDirectory(at: executable.deletingLastPathComponent(), withIntermediateDirectories: true)
    let codexInfo = try PropertyListSerialization.data(fromPropertyList: [
        "CFBundleIdentifier": "com.openai.codex", "CFBundlePackageType": "APPL", "CFBundleExecutable": "Codex"
    ], format: .xml, options: 0)
    try codexInfo.write(to: syntheticCodex.appendingPathComponent("Contents/Info.plist"))
    try Data("#!/bin/sh\nexit 0\n".utf8).write(to: executable)
    try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: executable.path)
    let probeRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--probe"])
    probeRuntime.installedTargetURL = syntheticCodex
    probeRuntime.applications = [FakeNativeApplication(
        pid: 44, bundleIdentifier: "com.openai.codex", bundleURL: syntheticCodex,
        executableURL: executable, launchTime: 20
    )]
    AppDelegate(runtime: probeRuntime, presentation: FakeNativePlayerPresentation())
        .applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    let probeEvent = probeRuntime.output.compactMap { line -> [String: Any]? in
        guard let data = line.data(using: .utf8) else { return nil }
        return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    }.first { $0["event"] as? String == "probe" }
    expect(probeEvent?["targetPath"] as? String == syntheticCodex.path
           && probeEvent?["targetBundleID"] as? String == "com.openai.codex"
           && probeRuntime.terminated == 1 && probeRuntime.acquiredLock == nil,
           "read-only probe resolves synthetic app target path=\(probeEvent?["targetPath"] as? String ?? "<none>") bundle=\(probeEvent?["targetBundleID"] as? String ?? "<none>") without acquiring the launch lock")

    func settleLaunch(_ runtime: FakeNativeAppRuntime) async throws {
        for _ in 0..<30 where runtime.terminated == 0 {
            try await Task.sleep(nanoseconds: 1_000_000)
        }
    }
    func eventNames(_ runtime: FakeNativeAppRuntime) -> [String] {
        runtime.output.compactMap { line in
            guard let data = line.data(using: .utf8),
                  let record = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
            return record["event"] as? String
        }
    }

    let coldResources = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-cold-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: coldResources) }
    let startupPayloadURL = coldResources.appendingPathComponent("startup/install.js")
    try FileManager.default.createDirectory(at: startupPayloadURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    try Data("test-only-probe".utf8).write(to: startupPayloadURL)
    let coldRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"], resourceURL: coldResources)
    coldRuntime.uptime = ProcessInfo.processInfo.systemUptime
    coldRuntime.installedTargetURL = syntheticCodex
    let coldTarget = FakeNativeApplication(pid: 45, bundleIdentifier: "com.openai.codex",
                                           bundleURL: syntheticCodex, executableURL: executable, launchTime: 21)
    coldRuntime.openedApplication = coldTarget
    let retiredTarget = FakeNativeApplication(pid: 46, bundleIdentifier: "com.openai.codex",
                                               bundleURL: syntheticCodex, executableURL: executable, launchTime: 19)
    retiredTarget.isTerminated = true
    coldRuntime.applications = [retiredTarget]
    let coldTargetSystem = FakeStartupSystem(expectedPID: 45, ports: [45678])
    coldRuntime.startupTargetSystem = coldTargetSystem
    let coldStartupURL = "app://-/index.html?initialRoute=%2F"
    let coldTransport = FakeStartupTransport(
        pages: [["type": "page", "id": "cold-main", "url": coldStartupURL,
                 "webSocketDebuggerUrl": "ws://127.0.0.1:45678/devtools/page/cold-main"]],
        evaluations: [
            ["href": coldStartupURL, "controllerPresent": false],
            ["installed": true, "alreadyActive": false],
            ["href": coldStartupURL, "missing": false, "status": [
                "owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": 31,
                "ready": true, "completed": false, "overlay": true, "reason": "",
                "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
                "completion": NSNull()
            ]]
        ]
    )
    coldRuntime.startupTransportFactory = { capture, events in
        NativeStartupEventTransport(base: coldTransport, capture: capture, events: events,
                                    now: { coldRuntime.uptime })
    }
    let coldDelegate = AppDelegate(runtime: coldRuntime, presentation: FakeNativePlayerPresentation())
    coldDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(coldRuntime)
    coldDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    let coldFailureEvent = coldRuntime.output.first(where: { $0.contains("startup-failed") }) ?? "none"
    let coldTargetLocation = [coldTarget.bundleURL?.path ?? "nil", coldTarget.executableURL?.path ?? "nil"].joined(separator: "/")
    let coldOpenRequest = coldRuntime.output.first(where: { $0.contains("target-open-request") }) ?? "none"
    expect(coldRuntime.openCount == 1 && coldRuntime.openedPorts == [45678],
           "cold startup opens only the verified synthetic target with its allocated loopback port")
    expect(coldTransport.payloadCount == 1,
           "cold startup evaluates its installation payload once (evaluations=\(coldTransport.evaluateCount), failed=\(coldFailureEvent), open=\(coldOpenRequest), validated=\(coldTargetSystem.validatedPIDs), app=\(coldTargetLocation))")
    expect(coldTransport.closeCount == 1, "cold startup closes the injected transport")
    expect(coldTarget.activationCount == 1, "verified readiness activates the same target once")
    expect(coldRuntime.terminated == 1 && coldRuntime.acquiredLock?.releaseCount == 1,
           "cold startup terminates after readiness and releases its instance lock")
    expect(eventNames(coldRuntime).contains("startup-installed") && eventNames(coldRuntime).contains("startup-ready")
           && eventNames(coldRuntime).contains("launcher-exit") && coldRuntime.processExitCode == 0,
           "cold startup emits installed, ready, and successful teardown events")

    let missingPayloadRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"])
    missingPayloadRuntime.installedTargetURL = syntheticCodex
    missingPayloadRuntime.startupTargetSystem = FakeStartupSystem(expectedPID: 45, ports: [45678])
    let missingPayloadDelegate = AppDelegate(runtime: missingPayloadRuntime, presentation: FakeNativePlayerPresentation())
    missingPayloadDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(missingPayloadRuntime)
    missingPayloadDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(missingPayloadRuntime.openCount == 0 && missingPayloadRuntime.terminated == 1
           && missingPayloadRuntime.processExitCode == 1
           && eventNames(missingPayloadRuntime).contains("startup-failed"),
           "cold startup refuses a missing packaged payload before opening the target")

    let missingTargetRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"])
    missingTargetRuntime.bundleURL = URL(fileURLWithPath: "/Applications/ChatGPT.app")
    AppDelegate(runtime: missingTargetRuntime, presentation: FakeNativePlayerPresentation())
        .applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    expect(missingTargetRuntime.openCount == 0 && missingTargetRuntime.terminated == 1
           && eventNames(missingTargetRuntime).contains("startup-failed"),
           "normal startup reports a missing target without opening any application")

    func makeColdRuntime(pid: Int32, resourceURL: URL?) -> (FakeNativeAppRuntime, FakeNativeApplication, FakeStartupSystem) {
        let runtime = FakeNativeAppRuntime(arguments: ["agent-skin"], resourceURL: resourceURL)
        runtime.uptime = ProcessInfo.processInfo.systemUptime
        runtime.installedTargetURL = syntheticCodex
        let retiredTarget = FakeNativeApplication(pid: pid + 1, bundleIdentifier: "com.openai.codex",
                                                  bundleURL: syntheticCodex, executableURL: executable)
        retiredTarget.isTerminated = true
        runtime.applications = [retiredTarget]
        let target = FakeNativeApplication(pid: pid, bundleIdentifier: "com.openai.codex",
                                           bundleURL: syntheticCodex, executableURL: executable,
                                           launchTime: TimeInterval(pid))
        runtime.openedApplication = target
        let system = FakeStartupSystem(expectedPID: pid, ports: [45678])
        runtime.startupTargetSystem = system
        return (runtime, target, system)
    }

    let hotRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"], resourceURL: coldResources)
    hotRuntime.installedTargetURL = syntheticCodex
    let hotTarget = FakeNativeApplication(pid: 47, bundleIdentifier: "com.openai.codex",
                                          bundleURL: syntheticCodex, executableURL: executable, launchTime: 47)
    hotRuntime.applications = [hotTarget]
    hotRuntime.startupTargetSystem = FakeStartupSystem(expectedPID: 47, ports: [])
    let hotDelegate = AppDelegate(runtime: hotRuntime, presentation: FakeNativePlayerPresentation())
    hotDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(hotRuntime)
    hotDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(hotRuntime.openCount == 0 && hotTarget.activationCount == 1
           && eventNames(hotRuntime).contains("target-activated")
           && hotRuntime.terminated == 1 && hotRuntime.processExitCode == 0,
           "hot startup validates and activates the one matching synthetic target without opening another app")

    let changedIdentityRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"], resourceURL: coldResources)
    changedIdentityRuntime.installedTargetURL = syntheticCodex
    let previouslyValidatedTarget = FakeNativeApplication(
        pid: 52, bundleIdentifier: "com.openai.codex", bundleURL: syntheticCodex,
        executableURL: executable, launchTime: 52
    )
    changedIdentityRuntime.applications = [previouslyValidatedTarget]
    let changedIdentitySystem = FakeStartupSystem(expectedPID: 52, ports: [])
    changedIdentitySystem.afterValidation = {
        changedIdentityRuntime.applications = [FakeNativeApplication(
            pid: 52, bundleIdentifier: "com.example.replaced", bundleURL: syntheticCodex,
            executableURL: executable, launchTime: 52
        )]
    }
    changedIdentityRuntime.startupTargetSystem = changedIdentitySystem
    let changedIdentityDelegate = AppDelegate(runtime: changedIdentityRuntime,
                                               presentation: FakeNativePlayerPresentation())
    changedIdentityDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(changedIdentityRuntime)
    changedIdentityDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    let identityFailureEvent = changedIdentityRuntime.output.compactMap { line -> [String: Any]? in
        guard let data = line.data(using: .utf8) else { return nil }
        return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    }.first { $0["event"] as? String == "startup-failed" }
    expect(changedIdentityRuntime.openCount == 0 && previouslyValidatedTarget.activationCount == 0
           && changedIdentityRuntime.terminated == 1 && changedIdentityRuntime.processExitCode == 1
           && identityFailureEvent?["reason"] as? String == "target-identity",
           "hot startup refuses a process whose identity changes after target validation")

    let factsRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"], resourceURL: coldResources)
    factsRuntime.installedTargetURL = syntheticCodex
    factsRuntime.applications = [FakeNativeApplication(pid: 48, bundleIdentifier: "com.openai.codex",
                                                       bundleURL: syntheticCodex, executableURL: nil)]
    let factsDelegate = AppDelegate(runtime: factsRuntime, presentation: FakeNativePlayerPresentation())
    factsDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(factsRuntime)
    factsDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(factsRuntime.openCount == 0 && factsRuntime.terminated == 1
           && eventNames(factsRuntime).contains("startup-failed"),
           "hot startup rejects a matching app that lacks a verified executable identity")

    let ambiguousRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"], resourceURL: coldResources)
    ambiguousRuntime.installedTargetURL = syntheticCodex
    ambiguousRuntime.applications = [
        FakeNativeApplication(pid: 49, bundleIdentifier: "com.openai.codex", bundleURL: syntheticCodex,
                              executableURL: executable),
        FakeNativeApplication(pid: 50, bundleIdentifier: "com.openai.codex", bundleURL: syntheticCodex,
                              executableURL: executable),
    ]
    let ambiguousDelegate = AppDelegate(runtime: ambiguousRuntime, presentation: FakeNativePlayerPresentation())
    ambiguousDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    ambiguousDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(ambiguousRuntime.openCount == 0 && ambiguousRuntime.terminated == 1
           && eventNames(ambiguousRuntime).contains("startup-failed"),
           "startup refuses multiple matching running app identities")

    let emptyPayloadResources = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-empty-payload-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: emptyPayloadResources) }
    let emptyPayloadURL = emptyPayloadResources.appendingPathComponent("startup/install.js")
    try FileManager.default.createDirectory(at: emptyPayloadURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    try Data().write(to: emptyPayloadURL)
    let (emptyPayloadRuntime, _, _) = makeColdRuntime(pid: 51, resourceURL: emptyPayloadResources)
    let emptyPayloadDelegate = AppDelegate(runtime: emptyPayloadRuntime, presentation: FakeNativePlayerPresentation())
    emptyPayloadDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(emptyPayloadRuntime)
    emptyPayloadDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(emptyPayloadRuntime.openCount == 0 && emptyPayloadRuntime.terminated == 1
           && eventNames(emptyPayloadRuntime).contains("startup-failed"),
           "cold startup rejects an empty packaged payload before opening the target")

    func runConfiguredStartup(_ runtime: FakeNativeAppRuntime) async throws {
        let delegate = AppDelegate(runtime: runtime, presentation: FakeNativePlayerPresentation())
        delegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
        try await settleLaunch(runtime)
        delegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    }
    func hasEvent(_ runtime: FakeNativeAppRuntime, _ name: String, reason: String? = nil) -> Bool {
        runtime.output.contains { line in
            guard let data = line.data(using: .utf8),
                  let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  event["event"] as? String == name else { return false }
            return reason == nil || event["reason"] as? String == reason
        }
    }

    let preflightFailures: [(String, Error, String)] = [
        ("inspection timeout", WallpaperFailure(state: "inspection-timeout", chinese: "timeout", english: "timeout"), "attach-timeout"),
        ("signature refusal", WallpaperFailure(state: "signature-refused", chinese: "refused", english: "refused"), "target-identity"),
        ("unexpected preflight error", NSError(domain: "NativeStartupTests", code: 1), "protocol-error"),
    ]
    for (label, error, reason) in preflightFailures {
        let (runtime, _, system) = makeColdRuntime(pid: 52, resourceURL: coldResources)
        system.preflightError = error
        try await runConfiguredStartup(runtime)
        expect(runtime.openCount == 0 && runtime.terminated == 1 && hasEvent(runtime, "startup-failed", reason: reason),
               "cold startup maps the \(label) before opening the target")
    }

    let exhaustedRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"], resourceURL: coldResources)
    exhaustedRuntime.installedTargetURL = syntheticCodex
    let exhaustedRetiredTarget = FakeNativeApplication(pid: 60, bundleIdentifier: "com.openai.codex",
                                                       bundleURL: syntheticCodex, executableURL: executable)
    exhaustedRetiredTarget.isTerminated = true
    exhaustedRuntime.applications = [exhaustedRetiredTarget]
    let exhaustedSystem = FakeStartupSystem(expectedPID: 53, ports: [45678])
    exhaustedRuntime.startupTargetSystem = exhaustedSystem
    exhaustedSystem.afterPreflight = { exhaustedRuntime.uptime += 60 }
    try await runConfiguredStartup(exhaustedRuntime)
    expect(exhaustedRuntime.openCount == 0 && exhaustedRuntime.terminated == 1
           && hasEvent(exhaustedRuntime, "startup-failed", reason: "attach-timeout"),
           "cold startup does not open a target after its overall time budget expires")

    let nativePortFailure = NativeLoopbackPortError(operation: "bind-loopback", code: 48)
    let (portFailureRuntime, _, _) = makeColdRuntime(pid: 54, resourceURL: coldResources)
    portFailureRuntime.allocatedPortError = nativePortFailure
    try await runConfiguredStartup(portFailureRuntime)
    expect(portFailureRuntime.openCount == 0 && hasEvent(portFailureRuntime, "startup-port-error")
           && hasEvent(portFailureRuntime, "startup-failed", reason: "listener-mismatch"),
           "a loopback allocation failure is recorded and blocks cold open")

    let (genericPortFailureRuntime, _, _) = makeColdRuntime(pid: 55, resourceURL: coldResources)
    genericPortFailureRuntime.allocationError = NSError(domain: "NativeStartupTests", code: 2)
    try await runConfiguredStartup(genericPortFailureRuntime)
    expect(genericPortFailureRuntime.openCount == 0
           && hasEvent(genericPortFailureRuntime, "startup-failed", reason: "listener-mismatch"),
           "an unexpected loopback allocation error also blocks cold open")

    let (openFailureRuntime, _, _) = makeColdRuntime(pid: 56, resourceURL: coldResources)
    openFailureRuntime.openError = NSError(domain: "NativeStartupTests", code: 3)
    try await runConfiguredStartup(openFailureRuntime)
    expect(openFailureRuntime.openCount == 1 && openFailureRuntime.terminated == 1
           && hasEvent(openFailureRuntime, "startup-failed", reason: "target-missing"),
           "the open completion error maps to a missing target without a second open")

    let (wrongOpenRuntime, _, _) = makeColdRuntime(pid: 57, resourceURL: coldResources)
    wrongOpenRuntime.openedApplication = FakeNativeApplication(
        pid: 57, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/tmp/Unrelated.app"), executableURL: URL(fileURLWithPath: "/tmp/Unrelated"))
    try await runConfiguredStartup(wrongOpenRuntime)
    expect(wrongOpenRuntime.openCount == 1 && hasEvent(wrongOpenRuntime, "startup-failed", reason: "target-identity"),
           "a completion for a different app bundle fails identity validation")

    let (lateOpenRuntime, _, _) = makeColdRuntime(pid: 58, resourceURL: coldResources)
    lateOpenRuntime.beforeOpenCompletion = { lateOpenRuntime.uptime += 45 }
    try await runConfiguredStartup(lateOpenRuntime)
    expect(lateOpenRuntime.openCount == 1 && hasEvent(lateOpenRuntime, "startup-failed", reason: "attach-timeout"),
           "a target that finishes opening after the attach deadline is rejected")

    let validationFailures: [(String, Error, String)] = [
        ("startup timeout", StartupFailure(reason: "attach-timeout", message: "test"), "attach-timeout"),
        ("inspection timeout", WallpaperFailure(state: "inspection-timeout", chinese: "timeout", english: "timeout"), "attach-timeout"),
        ("identity error", NSError(domain: "NativeStartupTests", code: 4), "target-identity"),
    ]
    for (label, error, reason) in validationFailures {
        let (runtime, _, system) = makeColdRuntime(pid: 59, resourceURL: coldResources)
        system.validationError = error
        try await runConfiguredStartup(runtime)
        expect(runtime.openCount == 1 && runtime.terminated == 1 && hasEvent(runtime, "startup-failed", reason: reason),
               "open completion with a \(label) is refused after identity checking (opens=\(runtime.openCount), terminated=\(runtime.terminated), output=\(runtime.output))")
    }

    guard let currentApplication = NSRunningApplication(processIdentifier: Int32(ProcessInfo.processInfo.processIdentifier)) else {
        fatalError("FAILED: current process is available as a read-only app fixture")
    }
    var wrappedActivationCount = 0
    let wrappedApplication = SystemNativeApplication(currentApplication, activate: {
        wrappedActivationCount += 1
        return false
    })
    _ = wrappedApplication.launchTime
    expect(wrappedApplication.processIdentifier == currentApplication.processIdentifier
           && wrappedApplication.bundleIdentifier == currentApplication.bundleIdentifier
           && wrappedApplication.bundleURL == currentApplication.bundleURL
           && wrappedApplication.executableURL == currentApplication.executableURL
           && wrappedApplication.isTerminated == currentApplication.isTerminated
           && wrappedApplication.isActive == currentApplication.isActive
           && wrappedApplication.isHidden == currentApplication.isHidden,
           "system application wrapper preserves the current process identity and state")
    expect(!wrappedApplication.activate() && wrappedActivationCount == 1,
           "the system application wrapper routes activation through its injected host boundary")

    var systemOperations: [String] = []
    var openedURL: URL?
    var openedConfiguration: NSWorkspace.OpenConfiguration?
    var openCompletionSucceeded = false
    var observedExit: Int32?
    let systemRuntime = SystemNativeAppRuntime(
        openApplication: { url, configuration, completion in
            openedURL = url; openedConfiguration = configuration
            completion(nil, nil)
        },
        setAccessoryPolicy: { systemOperations.append("accessory") },
        activateIgnoringOtherApps: { systemOperations.append("activate") },
        terminate: { systemOperations.append("terminate") },
        exit: { observedExit = $0 },
        standardOutput: { systemOperations.append("stdout:" + $0) }
    )
    let launchURL = URL(fileURLWithPath: "/tmp/Synthetic Codex.app")
    systemRuntime.openApplication(at: launchURL, debuggingPort: 49221) { app, error in
        openCompletionSucceeded = app == nil && error == nil
    }
    expect(openedURL == launchURL && openedConfiguration?.activates == false
           && openedConfiguration?.hides == false && openedConfiguration?.hidesOthers == false
           && openedConfiguration?.createsNewApplicationInstance == false
           && openedConfiguration?.allowsRunningApplicationSubstitution == false
           && openedConfiguration?.addsToRecentItems == false
           && openedConfiguration?.arguments == ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=49221"]
           && openCompletionSucceeded,
           "system runtime configures a nonactivating single-instance launch with only the verified loopback port")
    _ = systemRuntime.arguments; _ = systemRuntime.epoch; _ = systemRuntime.uptime
    _ = systemRuntime.processIdentifier; _ = systemRuntime.bundleURL; _ = systemRuntime.resourceURL
    _ = systemRuntime.appearanceTheme(); _ = systemRuntime.frontmostApplication
    _ = systemRuntime.runningApplications(bundleIdentifier: "local.azhou.native-test-no-such-app")
    _ = systemRuntime.application(processIdentifier: Int32(ProcessInfo.processInfo.processIdentifier))
    _ = systemRuntime.urlForApplication(bundleIdentifier: "local.azhou.native-test-no-such-app")
    _ = systemRuntime.makeStartupTargetSystem()
    let eventWriter = NativeEventWriter(startedAt: 1, launcherPID: 2, launcherPath: "/tmp/test",
                                        now: { 2 }, sink: { _ in })
    let eventStream = NativeStartupEventStream(writer: eventWriter)
    _ = systemRuntime.makeStartupTransport(capture: NativeStartupCapture(targetPID: 2), events: eventStream)
    _ = systemRuntime.systemFallbackLocale()
    systemRuntime.setAccessoryPolicy(); systemRuntime.activateIgnoringOtherApps()
    systemRuntime.terminate(); systemRuntime.exit(code: 7); systemRuntime.writeStandardOutput("receipt")
    expect(systemOperations == ["accessory", "activate", "terminate", "stdout:receipt"] && observedExit == 7,
           "system runtime routes lifecycle and process output actions through injected side effects")
    let lockIdentifier = "agent-skin-native-test-" + UUID().uuidString
    let lockPath = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("\(lockIdentifier)-\(getuid()).lock")
    switch systemRuntime.acquireInstanceLock(identifier: lockIdentifier) {
    case .acquired(let lock):
        switch systemRuntime.acquireInstanceLock(identifier: lockIdentifier) {
        case .busy:
            expect(true, "a second runtime instance cannot acquire a held lock")
        case .acquired(let duplicateLock):
            duplicateLock.release()
            expect(false, "a second runtime instance cannot acquire a held lock")
        case .failed(let code):
            expect(false, "a second runtime instance is busy rather than failing with errno \(code)")
        }
        lock.release()
        expect(true, "system runtime acquires and releases one uniquely named temporary instance lock")
    case .busy, .failed:
        expect(false, "system runtime acquires and releases one uniquely named temporary instance lock")
    }
    try? FileManager.default.removeItem(at: lockPath)
    let symlinkLockIdentifier = "agent-skin-native-test-symlink-" + UUID().uuidString
    let symlinkLockPath = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("\(symlinkLockIdentifier)-\(getuid()).lock")
    try FileManager.default.createSymbolicLink(at: symlinkLockPath, withDestinationURL: URL(fileURLWithPath: "/dev/null"))
    defer { try? FileManager.default.removeItem(at: symlinkLockPath) }
    if case .failed(let code) = systemRuntime.acquireInstanceLock(identifier: symlinkLockIdentifier) {
        expect(code != 0, "runtime refuses a symbolic-link instance-lock path without following it")
    } else {
        expect(false, "runtime refuses a symbolic-link instance-lock path without following it")
    }
    let localPort = try systemRuntime.allocateLoopbackPort()
    expect((1...65535).contains(localPort), "system runtime allocates an ephemeral loopback port")

    let priorMainMenu = NSApp.mainMenu
    let presentationActivationCount = UnsafeMutablePointer<Int>.allocate(capacity: 1)
    presentationActivationCount.initialize(to: 0)
    defer { presentationActivationCount.deinitialize(count: 1); presentationActivationCount.deallocate() }
    var presentedAlert: NSAlert?
    let nativePresentation = AppKitNativePlayerPresentation(
        activateApp: { presentationActivationCount.pointee += 1 },
        makeVisible: { _ in },
        runAlert: { presentedAlert = $0 }
    )
    let emptyPresentation = AppKitNativePlayerPresentation(
        activateApp: { presentationActivationCount.pointee += 1 },
        makeVisible: { _ in },
        runAlert: { _ in }
    )
    var emptyEvaluationError: Error?
    emptyPresentation.loadPlayer(page: URL(fileURLWithPath: "/tmp/local-preview.html"),
                                 allowingReadAccessTo: URL(fileURLWithPath: "/tmp"))
    emptyPresentation.updateLabels(.chinese)
    emptyPresentation.showReady(); emptyPresentation.setNormalLevel(); emptyPresentation.makeVisible()
    emptyPresentation.orderOut(); emptyPresentation.stopLoading()
    emptyPresentation.removeMessageHandler(named: "launcher")
    emptyPresentation.evaluateJavaScript("window.fixture = true") { _, error in emptyEvaluationError = error }
    var emptySnapshotError: Error?
    emptyPresentation.takeSnapshot { image, error in
        expect(image == nil, "snapshot before player creation has no image")
        emptySnapshotError = error
    }
    var emptyFadeCompleted = false
    emptyPresentation.fadeOut(duration: 0) { emptyFadeCompleted = true }
    expect(emptyPresentation.geometry.isEmpty && emptyEvaluationError != nil && emptySnapshotError != nil
           && emptyFadeCompleted,
           "presentation methods handle calls made before a local player window exists")
    let systemPreviewDelegate = AppDelegate(runtime: FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"]))
    nativePresentation.createPlayer(locale: .english, mode: "preview", theme: "dark", inspect: true,
                                    messageHandler: systemPreviewDelegate, navigationDelegate: systemPreviewDelegate)
    nativePresentation.loadPlayer(page: previewWebRoot.appendingPathComponent("index.html"), allowingReadAccessTo: previewWebRoot)
    nativePresentation.evaluateJavaScript("void 0", completion: nil)
    nativePresentation.takeSnapshot { _, _ in }
    let nativeGeometry = nativePresentation.geometry
    nativePresentation.updateLabels(.chinese)
    nativePresentation.showReady(); nativePresentation.setNormalLevel(); nativePresentation.makeVisible()
    nativePresentation.fadeOut(duration: 0) {}
    let scheduledNativeAction = nativePresentation.schedule(after: 3_600) {}
    scheduledNativeAction.cancel()
    nativePresentation.removeMessageHandler(named: "launcher")
    nativePresentation.stopLoading()
    nativePresentation.orderOut()
    nativePresentation.showError(title: "Fixture", message: "A local renderer error", closeTitle: "Close")
    NSApp.mainMenu = priorMainMenu
    expect(nativeGeometry["frame"] != nil && nativeGeometry["visibleFrame"] != nil
           && presentationActivationCount.pointee == 3
           && presentedAlert?.messageText == "Fixture" && presentedAlert?.informativeText == "A local renderer error"
           && presentedAlert?.buttons.first?.title == "Close",
           "AppKit player adapter configures an isolated window and alert while activation and modal display stay injected")

    let pendingReopenRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"], resourceURL: previewResources)
    let pendingReopenPresentation = FakeNativePlayerPresentation()
    let pendingReopenDelegate = AppDelegate(runtime: pendingReopenRuntime, presentation: pendingReopenPresentation)
    pendingReopenDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    expect(!pendingReopenDelegate.applicationShouldHandleReopen(NSApplication.shared, hasVisibleWindows: false)
           && pendingReopenRuntime.output.contains { $0.contains("preview-launch-pending") }
           && pendingReopenRuntime.openCount == 0,
           "reopening preview before renderer readiness records a pending promotion without target discovery")
    pendingReopenDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))

    let promotionRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"], resourceURL: previewResources)
    promotionRuntime.installedTargetURL = syntheticCodex
    let promotionTarget = FakeNativeApplication(pid: 61, bundleIdentifier: "com.openai.codex",
                                                bundleURL: syntheticCodex, executableURL: executable, launchTime: 61)
    promotionRuntime.applications = [promotionTarget]
    promotionRuntime.startupTargetSystem = FakeStartupSystem(expectedPID: 61, ports: [])
    let promotionPresentation = FakeNativePlayerPresentation()
    let promotionDelegate = AppDelegate(runtime: promotionRuntime, presentation: promotionPresentation)
    promotionDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    promotionDelegate.receivePlayerMessage(body: ["action": "ready", "duration": 1_000], isMainFrame: true)
    expect(!promotionDelegate.applicationShouldHandleReopen(NSApplication.shared, hasVisibleWindows: false),
           "reopening a ready preview requests launch promotion and keeps the current window")
    promotionDelegate.receivePlayerMessage(body: ["action": "complete"], isMainFrame: true)
    try await settleLaunch(promotionRuntime)
    expect(promotionTarget.activationCount == 1 && promotionPresentation.fadeDurations == [0.28]
           && promotionPresentation.orderedOutCount == 1 && promotionRuntime.terminated == 1,
           "promoted preview hands off to the validated hot target after the animation completes")
    promotionDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))

    let promotionFailureRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"], resourceURL: previewResources)
    let promotionFailurePresentation = FakeNativePlayerPresentation()
    let promotionFailureDelegate = AppDelegate(runtime: promotionFailureRuntime, presentation: promotionFailurePresentation)
    promotionFailureDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    promotionFailureDelegate.receivePlayerMessage(body: ["action": "ready"], isMainFrame: true)
    promotionFailurePresentation.evaluationResult = (nil, NSError(domain: "NativeStartupTests", code: 5))
    _ = promotionFailureDelegate.applicationShouldHandleReopen(NSApplication.shared, hasVisibleWindows: false)
    expect(promotionFailureRuntime.openCount == 0 && promotionFailureRuntime.terminated == 1
           && promotionFailurePresentation.visibleCount == 2 && promotionFailurePresentation.errors.count == 1
           && promotionFailureRuntime.output.contains { $0.contains("preview-promotion-error") },
           "a failed renderer promotion displays a native error and does not start the target (open=\(promotionFailureRuntime.openCount), terminate=\(promotionFailureRuntime.terminated), visible=\(promotionFailurePresentation.visibleCount), errors=\(promotionFailurePresentation.errors.count), output=\(promotionFailureRuntime.output))")
    promotionFailureDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))

    let completionRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"], resourceURL: previewResources)
    let completionPresentation = FakeNativePlayerPresentation()
    let completionDelegate = AppDelegate(runtime: completionRuntime, presentation: completionPresentation)
    completionDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    completionDelegate.receivePlayerMessage(body: ["action": "ready"], isMainFrame: true)
    completionDelegate.receivePlayerMessage(body: ["action": "complete", "skipped": false], isMainFrame: true)
    expect(completionRuntime.terminated == 1
           && completionRuntime.output.contains { $0.contains("preview-result") && $0.contains("\"success\":true") },
           "an ordinary preview records completion without using the smoke report gate")
    completionDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))

    let watchdogRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"], resourceURL: previewResources)
    let watchdogPresentation = FakeNativePlayerPresentation()
    let watchdogDelegate = AppDelegate(runtime: watchdogRuntime, presentation: watchdogPresentation)
    watchdogDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    watchdogPresentation.schedules[0].fire()
    expect(watchdogRuntime.terminated == 1 && watchdogPresentation.errors.first?.1.contains("ready") == true
           && watchdogRuntime.output.contains { $0.contains("renderer-ready-timeout") },
           "the renderer-ready watchdog reports a stalled local page and terminates preview")
    watchdogDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))

    let earlyCloseRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--smoke-test"], resourceURL: previewResources)
    let earlyClosePresentation = FakeNativePlayerPresentation()
    let earlyCloseDelegate = AppDelegate(runtime: earlyCloseRuntime, presentation: earlyClosePresentation)
    earlyCloseDelegate.receivePlayerMessage(body: "close", isMainFrame: true)
    earlyCloseDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(earlyCloseRuntime.terminated == 1 && earlyCloseRuntime.processExitCode == 1,
           "closing smoke mode before a validated completion sets a failing exit code")

    let logDirectory = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-log-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: logDirectory) }
    let logPath = logDirectory.appendingPathComponent("player.jsonl")
    let logRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview", "--log", logPath.path],
                                          resourceURL: previewResources)
    let logDelegate = AppDelegate(runtime: logRuntime, presentation: FakeNativePlayerPresentation())
    logDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    _ = logDelegate.windowShouldClose(NSWindow())
    logDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    let logLines = try String(contentsOf: logPath, encoding: .utf8).split(whereSeparator: \.isNewline)
    expect(logLines.contains { $0.contains("player-start") && $0.contains("preview") },
           "launcher appends structured preview events to a requested local log file")

    let blockedLogParent = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-log-parent-" + UUID().uuidString)
    defer { try? FileManager.default.removeItem(at: blockedLogParent) }
    try Data("not a directory".utf8).write(to: blockedLogParent)
    let blockedLogRuntime = FakeNativeAppRuntime(
        arguments: ["agent-skin", "--preview", "--log", blockedLogParent.appendingPathComponent("player.jsonl").path],
        resourceURL: previewResources
    )
    let blockedLogDelegate = AppDelegate(runtime: blockedLogRuntime, presentation: FakeNativePlayerPresentation())
    blockedLogDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    _ = blockedLogDelegate.windowShouldClose(NSWindow())
    blockedLogDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(blockedLogRuntime.terminated == 1 && blockedLogRuntime.output.contains { $0.contains("player-start") },
           "an unusable optional log path is reported while the preview still opens normally")


    let sampleBitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 2, pixelsHigh: 2,
                                        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                        isPlanar: false, colorSpaceName: .deviceRGB,
                                        bytesPerRow: 0, bitsPerPixel: 0)!
    sampleBitmap.setColor(NSColor(calibratedRed: 0.15, green: 0.3, blue: 0.9, alpha: 1), atX: 0, y: 0)
    let sampleImage = NSImage(size: NSSize(width: 2, height: 2))
    sampleImage.addRepresentation(sampleBitmap)
    let savedSnapshotDirectory = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-snapshot-success-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: savedSnapshotDirectory) }
    let savedSnapshotRuntime = FakeNativeAppRuntime(
        arguments: ["agent-skin", "--preview", "--snapshot", savedSnapshotDirectory.path, "--snapshot-times", "0"],
        resourceURL: previewResources
    )
    let savedSnapshotPresentation = FakeNativePlayerPresentation()
    savedSnapshotPresentation.snapshotResult = (sampleImage, nil)
    let savedSnapshotDelegate = AppDelegate(runtime: savedSnapshotRuntime, presentation: savedSnapshotPresentation)
    savedSnapshotDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    savedSnapshotDelegate.receivePlayerMessage(body: ["action": "ready", "duration": 1_000], isMainFrame: true)
    savedSnapshotPresentation.schedules.last?.fire()
    let savedSnapshotBase = savedSnapshotDirectory.appendingPathComponent("01-0.00s")
    expect(FileManager.default.fileExists(atPath: savedSnapshotBase.appendingPathExtension("png").path)
           && FileManager.default.fileExists(atPath: savedSnapshotBase.appendingPathExtension("json").path)
           && savedSnapshotRuntime.output.contains { $0.contains("snapshot-saved") },
           "a local renderer snapshot saves both PNG pixels and its report with a receipt")
    savedSnapshotDelegate.receivePlayerMessage(body: ["action": "close"], isMainFrame: true)
    savedSnapshotDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))

    let blockedSnapshotPath = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-snapshot-blocked-" + UUID().uuidString)
    defer { try? FileManager.default.removeItem(at: blockedSnapshotPath) }
    try Data("file blocks directory".utf8).write(to: blockedSnapshotPath)
    let blockedSnapshotRuntime = FakeNativeAppRuntime(
        arguments: ["agent-skin", "--preview", "--snapshot", blockedSnapshotPath.path],
        resourceURL: previewResources
    )
    let blockedSnapshotPresentation = FakeNativePlayerPresentation()
    let blockedSnapshotDelegate = AppDelegate(runtime: blockedSnapshotRuntime, presentation: blockedSnapshotPresentation)
    blockedSnapshotDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    blockedSnapshotDelegate.receivePlayerMessage(body: ["action": "ready"], isMainFrame: true)
    expect(blockedSnapshotRuntime.output.contains { $0.contains("snapshot-error") }
           && blockedSnapshotPresentation.schedules.count == 2,
           "an unwritable snapshot directory reports an error without scheduling images")
    blockedSnapshotDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))

    let pngFailureDirectory = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-native-snapshot-png-failure-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: pngFailureDirectory) }
    try FileManager.default.createDirectory(at: pngFailureDirectory, withIntermediateDirectories: true)
    try FileManager.default.createDirectory(at: pngFailureDirectory.appendingPathComponent("01-0.00s.png"),
                                            withIntermediateDirectories: true)
    let pngFailureRuntime = FakeNativeAppRuntime(
        arguments: ["agent-skin", "--preview", "--snapshot", pngFailureDirectory.path, "--snapshot-times", "0"],
        resourceURL: previewResources
    )
    let pngFailurePresentation = FakeNativePlayerPresentation()
    pngFailurePresentation.snapshotResult = (sampleImage, nil)
    let pngFailureDelegate = AppDelegate(runtime: pngFailureRuntime, presentation: pngFailurePresentation)
    pngFailureDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    pngFailureDelegate.receivePlayerMessage(body: ["action": "ready", "duration": 1_000], isMainFrame: true)
    pngFailurePresentation.schedules.last?.fire()
    expect(pngFailureRuntime.output.contains { $0.contains("snapshot-error") }
           && FileManager.default.fileExists(atPath: pngFailureDirectory.appendingPathComponent("01-0.00s.json").path),
           "a PNG write failure is reported while the text renderer report remains available")
    pngFailureDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))

    return checks
}
#endif

// MARK: - Shared skin host contract checks (agent-skin-zcode-contract/v0.1)

#if AGENT_SKIN_NATIVE_EVENT_TESTS
@MainActor
private func skinHostContractChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    let contractVersion = SkinHostContract.version
    expect(contractVersion == "agent-skin-zcode-contract/v0.1",
           "the shared skin host contract carries its declared version")

    func applicationKey(host: SkinHostID = .codex,
                        bundle: String = "/Applications/Codex.app",
                        executable: String = "/Applications/Codex.app/Contents/MacOS/Codex",
                        identifier: String = "com.openai.codex",
                        sha: String = "codex-executable-sha") -> HostApplicationKey {
        HostApplicationKey(host: host, bundleURL: URL(fileURLWithPath: bundle).resolvingSymlinksInPath().standardizedFileURL,
                           executableURL: URL(fileURLWithPath: executable).resolvingSymlinksInPath().standardizedFileURL,
                           bundleIdentifier: identifier, version: "1.9.0", build: "137",
                           executableSHA256: sha)
    }
    func finding(_ capability: SkinCapability, _ state: EvidenceState,
                 application: HostApplicationKey? = nil, surface: SkinSurface? = nil,
                 contract: String? = nil, evidence: [String] = ["codex-chain-evidence"]) -> CapabilityFinding {
        CapabilityFinding(
            subject: CapabilityEvidenceSubject(application: application ?? applicationKey(),
                                               surface: surface ?? SkinHostContract.surface(for: capability),
                                               contractVersion: contract ?? contractVersion),
            capability: capability, state: state,
            evidenceIDs: state == .verified ? evidence : [], reason: "contract-test")
    }
    func identity(_ key: HostApplicationKey? = nil) -> HostIdentityEvidence {
        HostIdentityEvidence(key: key ?? applicationKey(), signingIdentity: "contract-test-signer",
                             evidenceID: "contract-test-evidence")
    }
    func verifiedCodexFindings(_ application: HostApplicationKey) -> [CapabilityFinding] {
        SkinCapability.allCases.map { finding($0, .verified, application: application) }
    }
    func hotOnlyFindings(_ application: HostApplicationKey) -> [CapabilityFinding] {
        [finding(.applicationIdentity, .verified, application: application),
         finding(.activateExistingApplication, .verified, application: application),
         finding(.persistentSettings, .unverified, application: application),
         finding(.mainWindowAttachment, .unverified, application: application)]
    }
    // Factory step 1: identity binding across host, expected application and observed evidence.
    let codexKey = applicationKey()
    let otherApplication = applicationKey(bundle: "/Applications/OtherHost.app",
                                          executable: "/Applications/OtherHost.app/Contents/MacOS/OtherHost",
                                          identifier: "other.host.app", sha: "other-sha")
    var codexDrivers = 0
    func dependencies(codex: ((BoundHostInputs) -> any SkinHostDriver)? = nil,
                      zcode: ((BoundHostInputs) -> any SkinHostDriver)? = nil) -> SkinAssemblyDependencies {
        SkinAssemblyDependencies(
            inspectIdentity: { _, _ in .observed(identity()) },
            capabilityEvidence: { verifiedCodexFindings($0.key) },
            makeCodexDriver: codex ?? { _ in
                codexDrivers += 1
                return PlaceholderSkinHostDriver(inputs: nil)
            },
            makeZCodeDriver: zcode)
    }
    if case .unavailable(let refusal) = SkinHostFactory.make(
        host: .codex, expectedApplication: otherApplication, observed: identity(codexKey),
        findings: [], contractVersion: contractVersion, dependencies: dependencies()) {
        expect(refusal.reason == .identityMismatch && refusal.host == .codex,
               "a factory refuses an expected application that differs from the observed identity")
    } else { fatalError("FAILED: mismatched application must not assemble a driver") }
    if case .unavailable(let refusal) = SkinHostFactory.make(
        host: .zcode, expectedApplication: codexKey, observed: identity(codexKey),
        findings: [], contractVersion: contractVersion, dependencies: dependencies()) {
        expect(refusal.reason == .identityMismatch && refusal.host == .zcode,
               "a factory refuses a host that differs from the application identity")
    } else { fatalError("FAILED: host mismatch must not assemble a driver") }

    // Factory step 2: findings must bind this application, this contract and the fixed capability surface.
    func expectEvidenceMismatch(_ findings: [CapabilityFinding], _ label: String) {
        if case .unavailable(let refusal) = SkinHostFactory.make(
            host: .codex, expectedApplication: codexKey, observed: identity(codexKey),
            findings: findings, contractVersion: contractVersion, dependencies: dependencies()) {
            expect(refusal.reason == .evidenceMismatch, label)
        } else { fatalError("FAILED: \(label) must be refused") }
    }
    expectEvidenceMismatch([finding(.applicationIdentity, .verified, application: otherApplication)],
        "a finding for another application cannot support this installation identity")
    expectEvidenceMismatch([finding(.applicationIdentity, .verified, contract: "agent-skin-zcode-contract/v0.0")],
        "a finding from another contract version is rejected")
    expectEvidenceMismatch([finding(.mainWindowAttachment, .verified, surface: .application)],
        "an application-surface (plugin page) record cannot impersonate main-window evidence")

    // Factory step 3: duplicates, conflicts and unsupported verified-without-evidence records are rejected.
    expectEvidenceMismatch([finding(.applicationIdentity, .verified), finding(.applicationIdentity, .verified)],
        "duplicate records for one capability are rejected")
    expectEvidenceMismatch([finding(.applicationIdentity, .verified), finding(.applicationIdentity, .unverified)],
        "conflicting states for one capability are rejected")
    expectEvidenceMismatch([finding(.applicationIdentity, .verified, evidence: [])],
        "a verified record without source evidence references is rejected")

    // Factory step 4: unverified or unsupported records do not block assembly.
    if case .ready = SkinHostFactory.make(
        host: .codex, expectedApplication: codexKey, observed: identity(codexKey),
        findings: [finding(.persistentSettings, .unverified), finding(.ownedResourceRemoval, .unsupported)],
        contractVersion: contractVersion, dependencies: dependencies()) {
        checks += 1
    } else { fatalError("FAILED: unused unverified capabilities must not block the factory") }

    // Factory step 5: no ZCode constructor means an explicit refusal, never a Codex fallback.
    codexDrivers = 0
    if case .unavailable(let refusal) = SkinHostFactory.make(
        host: .zcode, expectedApplication: applicationKey(host: .zcode),
        observed: identity(applicationKey(host: .zcode)),
        findings: verifiedCodexFindings(applicationKey(host: .zcode)),
        contractVersion: contractVersion, dependencies: dependencies()) {
        expect(refusal.reason == .implementationUnavailable && refusal.host == .zcode,
               "a missing ZCode constructor refuses with implementationUnavailable")
    } else { fatalError("FAILED: missing constructor must refuse") }
    expect(codexDrivers == 0, "a refused ZCode assembly never falls back to the Codex constructor")

    // Factory step 6: a Codex assembly binds the driver to immutable bound inputs.
    codexDrivers = 0
    var capturedInputs: BoundHostInputs?
    let codexDependencies = dependencies(codex: { inputs in
        codexDrivers += 1
        capturedInputs = inputs
        return PlaceholderSkinHostDriver(inputs: inputs)
    })
    if case .ready(let driver) = SkinHostFactory.make(
        host: .codex, expectedApplication: codexKey, observed: identity(codexKey),
        findings: verifiedCodexFindings(codexKey), contractVersion: contractVersion,
        dependencies: codexDependencies) {
        expect(codexDrivers == 1 && driver is PlaceholderSkinHostDriver,
               "the Codex constructor assembles exactly one driver")
        expect(capturedInputs?.identity.key == codexKey && capturedInputs?.contractVersion == contractVersion,
               "the driver receives immutable bound inputs for this installation identity")
    } else { fatalError("FAILED: a consistent Codex assembly must produce a driver") }

    // Per-operation capability gates.
    func boundInputs(_ findings: [CapabilityFinding]) -> BoundHostInputs {
        BoundHostInputs(identity: identity(codexKey), findings: findings, contractVersion: contractVersion)
    }
    expect(capabilityRefusal(for: .activateExisting, inputs: boundInputs(hotOnlyFindings(codexKey))) == nil,
           "hot activation only requires identity and existing-instance activation evidence")
    let identityGapRefusal = capabilityRefusal(for: .activateExisting, inputs: boundInputs(
        [finding(.applicationIdentity, .unverified), finding(.activateExistingApplication, .verified)]))
    if identityGapRefusal != nil {
        expect(identityGapRefusal?.reason == .capabilityUnverified, "an unverified identity capability blocks its operation")
    } else { fatalError("FAILED: unverified identity must refuse") }
    let coldGapRefusal = capabilityRefusal(for: .coldLaunchSkin, inputs: boundInputs(hotOnlyFindings(codexKey)))
    if let refusal = coldGapRefusal {
        expect(refusal.reason == .capabilityUnverified
               && refusal.findings.contains { $0.capability == .mainWindowAttachment },
               "a cold launch missing main-window attachment is refused as unverified")
    } else { fatalError("FAILED: cold launch without main-window capability must refuse") }
    expect(capabilityRefusal(for: .inspectApplication, inputs: boundInputs(hotOnlyFindings(codexKey))) == nil,
           "application-only inspection is not blocked by missing page or storage capabilities")
    let pageInspectionRefusal = capabilityRefusal(for: .inspectPage, inputs: boundInputs(hotOnlyFindings(codexKey)))
    if let refusal = pageInspectionRefusal {
        expect(refusal.reason == .capabilityUnverified, "page inspection requires verified page identification")
    } else { fatalError("FAILED: page inspection without identification must refuse") }
    let unsupportedRemovalRefusal = capabilityRefusal(for: .disableSkin, inputs: boundInputs(
        [finding(.applicationIdentity, .verified), finding(.mainPageIdentification, .verified),
         finding(.ownedResourceRemoval, .unsupported)]))
    if let refusal = unsupportedRemovalRefusal {
        expect(refusal.reason == .capabilityUnsupported, "an unsupported removal capability is refused as unsupported")
    } else { fatalError("FAILED: unsupported removal must refuse") }

    // Driver hot path: identity + activate only; no port, transport, payload or opening side effects.
    let hotRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    let hotApp = FakeNativeApplication(
        pid: 4123, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 123.0)
    hotRuntime.applications = [hotApp]
    let hotSystem = FakeStartupSystem(expectedPID: 4123, ports: [9222])
    var hotPayloadReads = 0
    var hotOpeningChanges: [Bool] = []
    let hotTransport = FakeStartupTransport()
    var hotConnectorBuilt = false
    let hotObservation = CodexInstallObservation()
    let hotAssembly = CodexSkinAssembly(
        preflightBundle: { _, _ in },
        activateExisting: { facts in
            guard let app = hotRuntime.application(processIdentifier: facts.pid), !app.isTerminated,
                  app.bundleIdentifier == facts.bundleID,
                  app.bundleURL.map({ $0.resolvingSymlinksInPath().standardizedFileURL }) == facts.bundle,
                  app.executableURL.map({ $0.resolvingSymlinksInPath().standardizedFileURL }) == facts.executable,
                  app.launchTime == facts.launchTime else { return false }
            return app.activate()
        },
        preparePort: { try hotRuntime.allocateLoopbackPort() },
        openApplication: { _, _, _, _ in
            throw StartupFailure(reason: "protocol-error", message: "hot path must not open Codex")
        },
        onTargetOpened: { _ in fatalError("FAILED: hot activation must not record a cold-open target") },
        onCaptureReady: { _ in fatalError("FAILED: hot activation must not create a capture") },
        eventStream: { nil },
        onOpeningChanged: { hotOpeningChanges.append($0) },
        startupFacts: { app in
            StartupTargetFacts(pid: app.processIdentifier,
                               bundle: app.bundleURL!.resolvingSymlinksInPath().standardizedFileURL,
                               executable: app.executableURL!.resolvingSymlinksInPath().standardizedFileURL,
                               bundleID: app.bundleIdentifier!, launchTime: app.launchTime)
        },
        performDisable: nil)
    let hotDriver = CodexSkinDriver(
        inputs: boundInputs(hotOnlyFindings(codexKey)), runtime: hotRuntime,
        readPayload: { hotPayloadReads += 1; return "hot-payload" },
        makeTargetSystem: { hotSystem },
        makeConnector: { _, _, _, _, _ in
            hotConnectorBuilt = true
            return StartupConnector(target: .init(pid: 4123, bundle: codexKey.bundleURL,
                                                  executable: codexKey.executableURL,
                                                  bundleID: codexKey.bundleIdentifier, launchTime: nil),
                                    expectedPort: 9222, system: hotSystem, transport: hotTransport,
                                    now: { 0 }, sleep: { _ in })
        },
        installObservation: hotObservation, assembly: hotAssembly)
    let hotResult = await hotDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160))
    if case .activated(let generation) = hotResult {
        expect(generation.pid == 4123, "hot activation reports the activated process generation")
    } else { fatalError("FAILED: verified hot activation must activate") }
    expect(hotRuntime.openCount == 0 && hotRuntime.openedPorts.isEmpty,
           "hot activation opens no application and allocates no debugging port")
    expect(hotConnectorBuilt == false && hotTransport.evaluateCount == 0 && hotTransport.pagesCount == 0,
           "hot activation creates no transport, page lookup or payload evaluation")
    expect(hotPayloadReads == 0, "hot activation never reads the production startup payload")
    expect(hotOpeningChanges == [false],
           "hot activation never opens; it only runs the terminal opening reset like the previous launcher")
    expect(startupLegacyOutcome(from: hotResult) == .activated(pid: 4123),
           "the bridge maps an activated generation back to the legacy outcome")

    // Driver cold path refused before any side effect when main-window capability is unverified.
    let coldRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    coldRuntime.applications = []
    let coldSystem = FakeStartupSystem(expectedPID: 5321, ports: [9333])
    var coldPayloadReads = 0
    let coldTransport = FakeStartupTransport()
    let coldAssembly = CodexSkinAssembly(
        preflightBundle: { _, _ in },
        activateExisting: { _ in false },
        preparePort: { try coldRuntime.allocateLoopbackPort() },
        openApplication: { _, _, _, _ in throw StartupFailure(reason: "protocol-error", message: "unreachable") },
        onTargetOpened: { _ in }, onCaptureReady: { _ in }, eventStream: { nil },
        onOpeningChanged: { _ in fatalError("FAILED: refused cold launch must not change opening state") },
        startupFacts: { app in
            StartupTargetFacts(pid: app.processIdentifier, bundle: codexKey.bundleURL,
                               executable: codexKey.executableURL, bundleID: codexKey.bundleIdentifier,
                               launchTime: app.launchTime)
        },
        performDisable: nil)
    let coldDriver = CodexSkinDriver(
        inputs: boundInputs(hotOnlyFindings(codexKey)), runtime: coldRuntime,
        readPayload: { coldPayloadReads += 1; return "cold-payload" },
        makeTargetSystem: { coldSystem },
        makeConnector: { _, _, _, _, _ in
            StartupConnector(target: .init(pid: 5321, bundle: codexKey.bundleURL,
                                           executable: codexKey.executableURL,
                                           bundleID: codexKey.bundleIdentifier, launchTime: nil),
                             expectedPort: 9333, system: coldSystem, transport: coldTransport,
                             now: { 0 }, sleep: { _ in })
        },
        installObservation: CodexInstallObservation(), assembly: coldAssembly)
    if case .refused(let refusal) = await coldDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160)) {
        expect(refusal.reason == .capabilityUnverified,
               "a cold launch without the required main-window capability is refused")
    } else { fatalError("FAILED: capability-gap cold launch must refuse") }
    expect(coldRuntime.openCount == 0 && coldPayloadReads == 0 && coldTransport.pagesCount == 0
           && coldTransport.evaluateCount == 0 && coldTransport.connectCount == 0,
           "a refused cold launch starts nothing, creates no transport, writes no page and opens no database")

    // Cold launch with verified capabilities installs through the connector and keeps legacy outcomes.
    let installURL = "app://-/index.html?initialRoute=%2F"
    func pageEntry() -> [String: Any] {
        ["type": "page", "id": "selected-page", "url": installURL,
         "webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/page/selected-page"]
    }
    func statusBody(runID: Int, phase: String, ready: Bool) -> [String: Any] {
        ["owner": "azhou-codex-startup", "version": 1, "phase": phase, "runId": runID,
         "ready": ready, "completed": false, "overlay": true, "reason": "",
         "wallpaper": ["applied": false, "reason": "", "imageDecoded": false], "completion": NSNull()]
    }
    let installedApp = FakeNativeApplication(
        pid: 5321, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 200.0)
    let readyRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    readyRuntime.openedApplication = installedApp
    let readySystem = FakeStartupSystem(expectedPID: 5321, ports: [9333])
    let readyTransport = FakeStartupTransport(
        pages: [pageEntry()],
        evaluations: [
            ["href": installURL, "controllerPresent": false],
            ["installed": true, "alreadyActive": false],
            ["href": installURL, "missing": false, "status": statusBody(runID: 7, phase: "playing", ready: true)],
        ])
    var readyOpening: [Bool] = []
    let readyObservation = CodexInstallObservation()
    func contractEventStream(pid: Int) -> NativeStartupEventStream {
        NativeStartupEventStream(writer: NativeEventWriter(
            startedAt: 900, launcherPID: pid, launcherPath: "/Applications/Agent Skin.app",
            now: { 901 }, sink: { _ in }))
    }
    let readyEvents = contractEventStream(pid: 4242)
    let readyAssembly = CodexSkinAssembly(
        preflightBundle: { _, _ in },
        activateExisting: { _ in false },
        preparePort: { try readyRuntime.allocateLoopbackPort() },
        openApplication: { url, port, deadline, system in
            try await AppDelegate.openTargetApplication(runtime: readyRuntime, targetBundleID: "com.openai.codex",
                                                         url: url, port: port, deadline: deadline, system: system,
                                                         log: { _, _ in })
        },
        onTargetOpened: { _ in }, onCaptureReady: { _ in }, eventStream: { readyEvents },
        onOpeningChanged: { readyOpening.append($0) },
        startupFacts: { app in
            StartupTargetFacts(pid: app.processIdentifier,
                               bundle: app.bundleURL!.resolvingSymlinksInPath().standardizedFileURL,
                               executable: app.executableURL!.resolvingSymlinksInPath().standardizedFileURL,
                               bundleID: app.bundleIdentifier!, launchTime: app.launchTime)
        },
        performDisable: nil)
    let readyDriver = CodexSkinDriver(
        inputs: boundInputs(verifiedCodexFindings(codexKey)), runtime: readyRuntime,
        readPayload: { "test-only-probe-ready" },
        makeTargetSystem: { readySystem },
        makeConnector: { _, _, _, _, _ in
            StartupConnector(target: .init(pid: 5321, bundle: codexKey.bundleURL,
                                           executable: codexKey.executableURL,
                                           bundleID: codexKey.bundleIdentifier, launchTime: nil),
                             expectedPort: 9333, system: readySystem,
                             transport: InstallObservingStartupTransport(base: readyTransport, recorder: readyObservation),
                             now: { 0 }, sleep: { _ in })
        },
        installObservation: readyObservation, assembly: readyAssembly)
    let readyRequest = SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(),
                                         startedAt: 100, deadline: 160)
    let readyResult = await readyDriver.launch(readyRequest)
    if case .ready(let receipt, let runID) = readyResult {
        expect(runID == 7, "a successful cold launch keeps the controller runID")
        expect(receipt.controllerInstanceID == SkinHostContract.legacyUnreportedInstanceID
               && receipt.createdByOperationID == readyRequest.operationID,
               "legacy v1 receipts stay explicitly unreported instead of fabricated")
    } else { fatalError("FAILED: verified cold launch must reach ready") }
    expect(readyObservation.installSentCount == 1 && readyTransport.payloadCount == 1,
           "the install observation sees exactly one payload send")
    expect(readyOpening == [true, false, false],
           "the cold launch opens once, resets after the open and runs the terminal opening reset")
    expect(startupLegacyOutcome(from: readyResult) == .ready(runID: 7),
           "the bridge keeps legacy startup-ready consumers unchanged")

    // Lost reply after sending the install expression is installation-unknown, never fully-clean.
    let lostApp = FakeNativeApplication(
        pid: 5322, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 201.0)
    let lostRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    lostRuntime.openedApplication = lostApp
    let lostSystem = FakeStartupSystem(expectedPID: 5322, ports: [9333])
    let lostTransport = LostReplyStartupTransport(pages: [pageEntry()],
                                                  payloadMarker: "test-only-probe-lost")
    let lostAssembly = CodexSkinAssembly(
        preflightBundle: { _, _ in }, activateExisting: { _ in false },
        preparePort: { try lostRuntime.allocateLoopbackPort() },
        openApplication: { url, port, deadline, system in
            try await AppDelegate.openTargetApplication(runtime: lostRuntime, targetBundleID: "com.openai.codex",
                                                         url: url, port: port, deadline: deadline, system: system,
                                                         log: { _, _ in })
        },
        onTargetOpened: { _ in }, onCaptureReady: { _ in }, eventStream: { contractEventStream(pid: 4343) },
        onOpeningChanged: { _ in },
        startupFacts: { app in
            StartupTargetFacts(pid: app.processIdentifier,
                               bundle: app.bundleURL!.resolvingSymlinksInPath().standardizedFileURL,
                               executable: app.executableURL!.resolvingSymlinksInPath().standardizedFileURL,
                               bundleID: app.bundleIdentifier!, launchTime: app.launchTime)
        },
        performDisable: nil)
    let lostObservation = CodexInstallObservation()
    let lostDriver = CodexSkinDriver(
        inputs: boundInputs(verifiedCodexFindings(codexKey)), runtime: lostRuntime,
        readPayload: { "test-only-probe-lost" },
        makeTargetSystem: { lostSystem },
        makeConnector: { _, _, _, _, _ in
            StartupConnector(target: .init(pid: 5322, bundle: codexKey.bundleURL,
                                           executable: codexKey.executableURL,
                                           bundleID: codexKey.bundleIdentifier, launchTime: nil),
                             expectedPort: 9333, system: lostSystem,
                             transport: InstallObservingStartupTransport(base: lostTransport, recorder: lostObservation),
                             now: { 0 }, sleep: { _ in })
        },
        installObservation: lostObservation, assembly: lostAssembly)
    let lostResult = await lostDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160))
    if case .failed(let failure, let page, let cleanup) = lostResult {
        expect(page.isInstallationUnknown, "a lost install reply reports the page as unknown")
        expect(cleanup.state == .unknown && cleanup.unconfirmed.contains("page-controller"),
               "a lost install reply never claims a fully-clean cleanup")
        expect(failure.detail == "protocol-error", "the lost-reply failure keeps its legacy reason")
    } else { fatalError("FAILED: a lost install reply must fail with unknown installation state") }
    expect(lostTransport.disposeEvaluations == 0,
           "a lost reply does not blindly roll back a possibly-installed controller")

    // alreadyActive keeps the existing controller: partial(startup-active), no rollback authority.
    let activeRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    let activeApp = FakeNativeApplication(
        pid: 5323, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 202.0)
    activeRuntime.openedApplication = activeApp
    let activeSystem = FakeStartupSystem(expectedPID: 5323, ports: [9333])
    let activeTransport = FakeStartupTransport(
        pages: [pageEntry()],
        evaluations: [
            ["href": installURL, "controllerPresent": false],
            ["installed": true, "alreadyActive": true],
        ])
    let activeAssembly = CodexSkinAssembly(
        preflightBundle: { _, _ in }, activateExisting: { _ in false },
        preparePort: { try activeRuntime.allocateLoopbackPort() },
        openApplication: { url, port, deadline, system in
            try await AppDelegate.openTargetApplication(runtime: activeRuntime, targetBundleID: "com.openai.codex",
                                                         url: url, port: port, deadline: deadline, system: system,
                                                         log: { _, _ in })
        },
        onTargetOpened: { _ in }, onCaptureReady: { _ in }, eventStream: { contractEventStream(pid: 4343) },
        onOpeningChanged: { _ in },
        startupFacts: { app in
            StartupTargetFacts(pid: app.processIdentifier,
                               bundle: app.bundleURL!.resolvingSymlinksInPath().standardizedFileURL,
                               executable: app.executableURL!.resolvingSymlinksInPath().standardizedFileURL,
                               bundleID: app.bundleIdentifier!, launchTime: app.launchTime)
        },
        performDisable: nil)
    let activeDriver = CodexSkinDriver(
        inputs: boundInputs(verifiedCodexFindings(codexKey)), runtime: activeRuntime,
        readPayload: { "active-codex-payload" },
        makeTargetSystem: { activeSystem },
        makeConnector: { _, _, _, _, _ in
            StartupConnector(target: .init(pid: 5323, bundle: codexKey.bundleURL,
                                           executable: codexKey.executableURL,
                                           bundleID: codexKey.bundleIdentifier, launchTime: nil),
                             expectedPort: 9333, system: activeSystem, transport: activeTransport,
                             now: { 0 }, sleep: { _ in })
        },
        installObservation: CodexInstallObservation(), assembly: activeAssembly)
    let activeResult = await activeDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160))
    if case .partial(let failure, let page, let cleanup) = activeResult {
        expect(page.isPresentsLegacyAlreadyActive(owner: "azhou-codex-startup", protocolVersion: 1),
               "an already-active controller is reported as a legacy v1 present observation")
        expect(failure.detail == "startup-active" && cleanup.state == .notNeeded
               && cleanup.intentionallyRetained.contains("existing-startup-controller"),
               "an existing controller is intentionally retained without rollback authority")
    } else { fatalError("FAILED: alreadyActive must stay a partial legacy result") }
    expect(activeTransport.disposeCount == 0,
           "an already-active attempt never disposes the pre-existing controller")
    expect(startupLegacyOutcome(from: activeResult) == .partial(reason: "startup-active"),
           "the bridge keeps the partial(startup-active) mapping for old consumers")

    // Re-entrant page-changing operations on one driver return operation-busy.
    let busyRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    let busyApp = FakeNativeApplication(
        pid: 5324, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 203.0)
    busyRuntime.openedApplication = busyApp
    busyRuntime.deferOpenCompletion = true
    let busySystem = FakeStartupSystem(expectedPID: 5324, ports: [9333])
    let busyTransport = FakeStartupTransport(
        pages: [pageEntry()],
        evaluations: [
            ["href": installURL, "controllerPresent": false],
            ["installed": true, "alreadyActive": false],
            ["href": installURL, "missing": false, "status": statusBody(runID: 11, phase: "playing", ready: true)],
        ])
    let busyAssembly = CodexSkinAssembly(
        preflightBundle: { _, _ in }, activateExisting: { _ in false },
        preparePort: { try busyRuntime.allocateLoopbackPort() },
        openApplication: { url, port, deadline, system in
            try await AppDelegate.openTargetApplication(runtime: busyRuntime, targetBundleID: "com.openai.codex",
                                                         url: url, port: port, deadline: deadline, system: system,
                                                         log: { _, _ in })
        },
        onTargetOpened: { _ in }, onCaptureReady: { _ in }, eventStream: { contractEventStream(pid: 4343) },
        onOpeningChanged: { _ in },
        startupFacts: { app in
            StartupTargetFacts(pid: app.processIdentifier,
                               bundle: app.bundleURL!.resolvingSymlinksInPath().standardizedFileURL,
                               executable: app.executableURL!.resolvingSymlinksInPath().standardizedFileURL,
                               bundleID: app.bundleIdentifier!, launchTime: app.launchTime)
        },
        performDisable: nil)
    let busyDriver = CodexSkinDriver(
        inputs: boundInputs(verifiedCodexFindings(codexKey)), runtime: busyRuntime,
        readPayload: { "busy-codex-payload" },
        makeTargetSystem: { busySystem },
        makeConnector: { _, _, _, _, _ in
            StartupConnector(target: .init(pid: 5324, bundle: codexKey.bundleURL,
                                           executable: codexKey.executableURL,
                                           bundleID: codexKey.bundleIdentifier, launchTime: nil),
                             expectedPort: 9333, system: busySystem, transport: busyTransport,
                             now: { 0 }, sleep: { _ in })
        },
        installObservation: CodexInstallObservation(), assembly: busyAssembly)
    let busyRequest = SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(),
                                        startedAt: 100, deadline: 160)
    async let firstLaunch = busyDriver.launch(busyRequest)
    try await Task.sleep(nanoseconds: 150_000_000)
    if case .partial(let failure, _, _) = await busyDriver.launch(busyRequest) {
        expect(failure.reason == .operationBusy,
               "a re-entrant page-changing operation returns operation-busy")
    } else { fatalError("FAILED: re-entrant launch must return operation-busy") }
    busyRuntime.completePendingOpen()
    if case .ready(_, let runID) = await firstLaunch {
        expect(runID == 11, "the in-flight launch completes after its deferred open")
    } else { fatalError("FAILED: the first launch must still complete") }

    // Cross-driver disable/launch interleaving keeps one lock owner per target process.
    let interleavePID = Int32.max - 7
    let interleaveLockPath = WallpaperOperationLock.path(uid: Darwin.getuid(), pid: interleavePID)
    defer { try? FileManager.default.removeItem(atPath: interleaveLockPath) }
    let interleaveRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    let interleaveApp = FakeNativeApplication(
        pid: interleavePID, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 204.0)
    interleaveRuntime.applications = [interleaveApp]
    let interleaveSystem = LockingStartupSystem(FakeStartupSystem(expectedPID: interleavePID, ports: [9333]))
    var disableCalls: [Int32] = []
    let disableAssembly = CodexSkinAssembly(
        preflightBundle: { _, _ in }, activateExisting: { _ in false },
        preparePort: { try interleaveRuntime.allocateLoopbackPort() },
        openApplication: { _, _, _, _ in throw StartupFailure(reason: "protocol-error", message: "unreachable") },
        onTargetOpened: { _ in }, onCaptureReady: { _ in }, eventStream: { contractEventStream(pid: 4343) }, onOpeningChanged: { _ in },
        startupFacts: { app in
            StartupTargetFacts(pid: app.processIdentifier,
                               bundle: app.bundleURL!.resolvingSymlinksInPath().standardizedFileURL,
                               executable: app.executableURL!.resolvingSymlinksInPath().standardizedFileURL,
                               bundleID: app.bundleIdentifier!, launchTime: app.launchTime)
        },
        performDisable: { facts, _, _ in
            disableCalls.append(facts.pid)
            return ["disposed": true]
        })
    let disableDriver = CodexSkinDriver(
        inputs: boundInputs(verifiedCodexFindings(codexKey)), runtime: interleaveRuntime,
        readPayload: { "disable-payload" },
        makeTargetSystem: { interleaveSystem },
        makeConnector: { _, _, _, _, _ in
            StartupConnector(target: .init(pid: interleavePID, bundle: codexKey.bundleURL,
                                           executable: codexKey.executableURL,
                                           bundleID: codexKey.bundleIdentifier, launchTime: nil),
                             expectedPort: 9333, system: interleaveSystem, transport: FakeStartupTransport(),
                             now: { 0 }, sleep: { _ in })
        },
        installObservation: CodexInstallObservation(), assembly: disableAssembly)
    func disableRequest(pid: Int32, owner: String = "azhou-codex-startup") -> SkinDisableRequest {
        SkinDisableRequest(
            expectedApplication: codexKey, operationID: UUID(), deadline: 160,
            expectedPage: .legacyV1(LegacyV1Observation(
                location: PageLocation(application: codexKey,
                                       process: HostProcessGeneration(pid: pid, launchTime: nil,
                                                                      executableURL: codexKey.executableURL),
                                       documentToken: installURL),
                owner: owner, protocolVersion: 1)))
    }
    func contractDriver(runtime: FakeNativeAppRuntime, system: FakeStartupSystem,
                        transport: StartupTransport, findings: [CapabilityFinding],
                        performDisable: ((StartupTargetFacts, String, TimeInterval) async throws -> [String: Any])? = nil) -> CodexSkinDriver {
        let observation = CodexInstallObservation()
        runtime.allocatedPort = 9333
        let assembly = CodexSkinAssembly(
            preflightBundle: { _, _ in },
            activateExisting: { _ in false },
            preparePort: { try runtime.allocateLoopbackPort() },
            openApplication: { url, port, deadline, openSystem in
                try await AppDelegate.openTargetApplication(runtime: runtime, targetBundleID: "com.openai.codex",
                                                            url: url, port: port, deadline: deadline, system: openSystem,
                                                            log: { _, _ in })
            },
            onTargetOpened: { _ in }, onCaptureReady: { _ in },
            eventStream: { contractEventStream(pid: 4444) },
            onOpeningChanged: { _ in },
            startupFacts: { app in
                guard !app.isTerminated, let bundle = app.bundleURL, let executable = app.executableURL,
                      let bundleID = app.bundleIdentifier else {
                    throw StartupFailure(reason: "target-identity", message: "incomplete identity")
                }
                return StartupTargetFacts(pid: app.processIdentifier,
                                          bundle: bundle.resolvingSymlinksInPath().standardizedFileURL,
                                          executable: executable.resolvingSymlinksInPath().standardizedFileURL,
                                          bundleID: bundleID, launchTime: app.launchTime)
            },
            performDisable: performDisable)
        return CodexSkinDriver(
            inputs: boundInputs(findings), runtime: runtime,
            readPayload: { "test-only-probe-contract" },
            makeTargetSystem: { system },
            makeConnector: { facts, port, connectorSystem, _, _ in
                StartupConnector(target: facts, expectedPort: port, system: connectorSystem,
                                 transport: InstallObservingStartupTransport(base: transport, recorder: observation),
                                 now: { 0 }, sleep: { _ in })
            },
            installObservation: observation, assembly: assembly)
    }
    let heldLock = try WallpaperOperationLock.acquire(pid: interleavePID)
    if case .refused(let failure, _) = await disableDriver.disable(disableRequest(pid: interleavePID)) {
        expect(failure.reason == .operationBusy,
               "a driver disable refuses while another owner holds the per-process operation lock")
    } else { fatalError("FAILED: interleaved disable must refuse with operation-busy") }
    expect(disableCalls.isEmpty, "a refused interleave performs no page work")
    heldLock.release()
    if case .removed(let report) = await disableDriver.disable(disableRequest(pid: interleavePID)) {
        expect(report.state == .complete && report.released.contains("legacy-page-controller"),
               "an owned disable reports a complete bounded cleanup")
    } else { fatalError("FAILED: an owned disable must remove") }
    expect(disableCalls == [interleavePID], "the disable delegation runs exactly once under the lock")
    if case .alreadyAbsent(let location) = await disableDriver.disable(disableRequest(pid: 31_337)) {
        expect(location.process.pid == 31_337,
               "a disable for a vanished process reports already-absent instead of touching the page")
    } else { fatalError("FAILED: a vanished target must report already-absent") }

    // A request for another application never reaches any operation branch.
    if case .refused(let refusal) = await hotDriver.launch(
        SkinLaunchRequest(expectedApplication: otherApplication, operationID: UUID(), startedAt: 100, deadline: 160)) {
        expect(refusal.reason == .identityMismatch,
               "a driver refuses a request bound to another application identity")
    } else { fatalError("FAILED: cross-application requests must refuse") }

    // A startup-interrupted run after a confirmed install is installation-unknown,
    // never notObserved and never a fully-clean cleanup (spec §7.3).
    let interruptedApp = FakeNativeApplication(
        pid: 5329, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 208.0)
    let interruptedRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    interruptedRuntime.openedApplication = interruptedApp
    let interruptedTransport = FakeStartupTransport(
        pages: [pageEntry()],
        evaluations: [
            ["href": installURL, "controllerPresent": false],
            ["installed": true, "alreadyActive": false],
            ["href": "app://-/index.html?initialRoute=%2Fsettings", "missing": false],
        ])
    let interruptedDriver = contractDriver(runtime: interruptedRuntime,
                                           system: FakeStartupSystem(expectedPID: 5329, ports: [9333]),
                                           transport: interruptedTransport,
                                           findings: verifiedCodexFindings(codexKey))
    if case .partial(let failure, let page, let cleanup) = await interruptedDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160)) {
        expect(failure.detail == "startup-interrupted",
               "an interrupted run keeps its legacy partial reason")
        expect(page.isInstallationUnknown,
               "a sent install followed by a lost status observation is installation-unknown, not notObserved")
        expect(cleanup.state == .unknown && cleanup.unconfirmed.contains("page-controller"),
               "an interrupted install never claims a fully-clean cleanup")
        expect(startupLegacyOutcome(from: .partial(failure, page: page, cleanup: cleanup))
               == .partial(reason: "startup-interrupted"),
               "the bridge still maps the interrupted partial back to its legacy reason")
    } else { fatalError("FAILED: an interrupted install must stay a partial result") }

    // The bridge keeps every remaining legacy shape for old consumers.
    expect(startupLegacyOutcome(from: .skipped(.notObserved(reason: "legacy-v1-status-polling"),
                                                  runID: 5, beforeReady: true))
           == .skipped(runID: 5, beforeReady: true),
           "the bridge keeps skipped runID and beforeReady data")
    for reason in [HostRefusalReason.identityUnavailable, .identityMismatch, .capabilityUnverified] {
        expect(startupLegacyOutcome(from: .refused(HostRefusal(host: .codex, reason: reason,
                                                               findings: [], detail: "", nextProbe: nil)))
               == .failed(reason: "target-identity"),
               "identity-family refusals fold into the legacy target-identity reason (\(reason.rawValue))")
    }
    for reason in [HostRefusalReason.evidenceMismatch, .implementationUnavailable, .capabilityUnsupported] {
        expect(startupLegacyOutcome(from: .refused(HostRefusal(host: .zcode, reason: reason,
                                                               findings: [], detail: "", nextProbe: nil)))
               == .failed(reason: "protocol-error"),
               "contract-family refusals fold into the legacy protocol-error reason (\(reason.rawValue))")
    }

    // A cold launch whose connector fails keeps the legacy failure and no unknown claim.
    let failedApp = FakeNativeApplication(
        pid: 5326, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 205.0)
    let failedRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    failedRuntime.openedApplication = failedApp
    let failedDriver = contractDriver(runtime: failedRuntime,
                                      system: FakeStartupSystem(expectedPID: 9999, ports: [9333]),
                                      transport: FakeStartupTransport(),
                                      findings: verifiedCodexFindings(codexKey))
    if case .failed(let failure, let page, let cleanup) = await failedDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160)) {
        expect(failure.detail == "target-identity" && page.isNotObserved && cleanup.state == .notNeeded,
               "a pre-install connector failure keeps the legacy reason and a clean no-op cleanup")
        expect(startupLegacyOutcome(from: .failed(failure, page: page, cleanup: cleanup))
               == .failed(reason: "target-identity"),
               "the bridge maps connector identity failures back unchanged")
    } else { fatalError("FAILED: a failing cold launch must report a failure") }

    // A skipped controller run keeps its runID and before-ready flag.
    let skippedApp = FakeNativeApplication(
        pid: 5327, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 206.0)
    let skippedRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    skippedRuntime.openedApplication = skippedApp
    let skippedTransport = FakeStartupTransport(
        pages: [pageEntry()],
        evaluations: [
            ["href": installURL, "controllerPresent": false],
            ["installed": true, "alreadyActive": false],
            ["href": installURL, "missing": false, "status": [
                "owner": "azhou-codex-startup", "version": 1, "phase": "complete", "runId": 8,
                "ready": false, "completed": true, "overlay": false, "reason": "",
                "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
                "completion": ["cause": "skip", "beforeReady": true]]],
        ])
    let skippedDriver = contractDriver(runtime: skippedRuntime,
                                       system: FakeStartupSystem(expectedPID: 5327, ports: [9333]),
                                       transport: skippedTransport,
                                       findings: verifiedCodexFindings(codexKey))
    if case .skipped(_, let runID, let beforeReady) = await skippedDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160)) {
        expect(runID == 8 && beforeReady == true,
               "a skipped controller run keeps runID and beforeReady through the bridge")
    } else { fatalError("FAILED: a skipped run must stay skipped") }

    // Ambiguous or incomplete running identities refuse before any side effect.
    let ambiguousRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    ambiguousRuntime.applications = [
        FakeNativeApplication(pid: 61, bundleIdentifier: "com.openai.codex",
                              bundleURL: URL(fileURLWithPath: "/Applications/Codex-beta.app")),
        FakeNativeApplication(pid: 62, bundleIdentifier: "com.openai.codex",
                              bundleURL: URL(fileURLWithPath: "/Applications/Codex-gamma.app")),
    ]
    let ambiguousDriver = contractDriver(runtime: ambiguousRuntime,
                                         system: FakeStartupSystem(expectedPID: 61, ports: [9333]),
                                         transport: FakeStartupTransport(),
                                         findings: verifiedCodexFindings(codexKey))
    if case .refused(let refusal) = await ambiguousDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160)) {
        expect(refusal.reason == .identityMismatch,
               "an ambiguous set of running Codex processes refuses identity")
    } else { fatalError("FAILED: ambiguous processes must refuse") }
    expect(ambiguousRuntime.openCount == 0, "an ambiguous identity never opens the target")

    let incompleteRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    incompleteRuntime.applications = [
        FakeNativeApplication(pid: 63, bundleIdentifier: "com.openai.codex",
                              bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"), executableURL: nil),
    ]
    let incompleteDriver = contractDriver(runtime: incompleteRuntime,
                                          system: FakeStartupSystem(expectedPID: 63, ports: [9333]),
                                          transport: FakeStartupTransport(),
                                          findings: verifiedCodexFindings(codexKey))
    if case .refused(let refusal) = await incompleteDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160)) {
        expect(refusal.reason == .identityMismatch,
               "a running process without a complete identity refuses launch")
    } else { fatalError("FAILED: an incomplete identity must refuse") }

    // Disable keeps the strict legacy owner binding and refuses without delegation.
    let strictRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    strictRuntime.applications = [hotApp]
    let strictSystem = FakeStartupSystem(expectedPID: 4123, ports: [])
    var delegated: [Int32] = []
    let strictDriver = contractDriver(runtime: strictRuntime, system: strictSystem,
                                      transport: FakeStartupTransport(),
                                      findings: verifiedCodexFindings(codexKey),
                                      performDisable: { facts, _, _ in
                                          delegated.append(facts.pid)
                                          return ["disposed": true]
                                      })
    if case .refused(let failure, _) = await strictDriver.disable(
        disableRequest(pid: 4123, owner: "foreign-owner")) {
        expect(failure.reason == .ownerConflict,
               "only the legacy azhou-codex-startup v1 controller may be disabled")
    } else { fatalError("FAILED: a foreign owner must be refused") }
    expect(delegated.isEmpty, "a refused owner check performs no page disposal")
    let hooklessDriver = contractDriver(runtime: strictRuntime, system: strictSystem,
                                        transport: FakeStartupTransport(),
                                        findings: verifiedCodexFindings(codexKey),
                                        performDisable: nil)
    if case .refused(let failure, _) = await hooklessDriver.disable(disableRequest(pid: 4123)) {
        expect(failure.reason == .protocolError && failure.detail.contains("WallpaperCLI"),
               "without an explicit disposal assembly the driver refuses instead of degrading")
    } else { fatalError("FAILED: a missing disposal assembly must refuse explicitly") }
    var unconfirmedResults: [SkinDisableResult] = []
    for behavior in ["unconfirmed", "throwing"] {
        let driver = contractDriver(runtime: strictRuntime, system: strictSystem,
                                    transport: FakeStartupTransport(),
                                    findings: verifiedCodexFindings(codexKey),
                                    performDisable: { _, _, _ in
                                        if behavior == "unconfirmed" {
                                            return ["disposed": false, "reason": "owner-conflict"]
                                        }
                                        throw StartupFailure(reason: "protocol-error", message: "dispose failed")
                                    })
        unconfirmedResults.append(await driver.disable(disableRequest(pid: 4123)))
    }
    for (index, result) in unconfirmedResults.enumerated() {
        if case .partial(let failure, _, let cleanup) = result {
            expect(failure.reason == .protocolError && cleanup.state == .unknown
                   && cleanup.unconfirmed.contains("page-controller"),
                   "an unconfirmed or throwing disposal stays partial with unknown cleanup (\(index))")
        } else { fatalError("FAILED: unconfirmed disposal must stay partial") }
    }

    // A disable during an in-flight page-changing operation is operation-busy.
    let busyDisableRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    let busyDisableApp = FakeNativeApplication(
        pid: 5328, bundleIdentifier: "com.openai.codex",
        bundleURL: URL(fileURLWithPath: "/Applications/Codex.app"),
        executableURL: URL(fileURLWithPath: "/Applications/Codex.app/Contents/MacOS/Codex"),
        launchTime: 207.0)
    busyDisableRuntime.openedApplication = busyDisableApp
    busyDisableRuntime.deferOpenCompletion = true
    let busyDisableDriver = contractDriver(runtime: busyDisableRuntime,
                                           system: FakeStartupSystem(expectedPID: 5328, ports: [9333]),
                                           transport: FakeStartupTransport(pages: [pageEntry()], evaluations: [
                                               ["href": installURL, "controllerPresent": false],
                                               ["installed": true, "alreadyActive": false],
                                               ["href": installURL, "missing": false,
                                                "status": statusBody(runID: 12, phase: "playing", ready: true)],
                                           ]),
                                           findings: verifiedCodexFindings(codexKey))
    async let busyFirstLaunch = busyDisableDriver.launch(
        SkinLaunchRequest(expectedApplication: codexKey, operationID: UUID(), startedAt: 100, deadline: 160))
    try await Task.sleep(nanoseconds: 150_000_000)
    if case .refused(let failure, _) = await busyDisableDriver.disable(disableRequest(pid: 5328)) {
        expect(failure.reason == .operationBusy, "disable refuses while a launch owns the page operation")
    } else { fatalError("FAILED: interleaved disable must refuse with operation-busy") }
    busyDisableRuntime.completePendingOpen()
    if case .ready(_, let runID) = await busyFirstLaunch {
        expect(runID == 12, "the in-flight launch still completes")
    } else { fatalError("FAILED: the in-flight launch must complete") }

    // The shared bounded open routine keeps its fixed failure mapping.
    let openErrorRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    openErrorRuntime.openError = StartupFailure(reason: "target-missing", message: "open failed")
    do {
        _ = try await AppDelegate.openTargetApplication(
            runtime: openErrorRuntime, targetBundleID: "com.openai.codex",
            url: codexKey.bundleURL, port: 9333, deadline: 200,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9333]), log: { _, _ in })
        fatalError("FAILED: an open error must fail the bounded open")
    } catch let error as StartupFailure {
        expect(error.reason == "target-missing", "an open error maps to the fixed target-missing failure")
    }
    do {
        _ = try await AppDelegate.openTargetApplication(
            runtime: openErrorRuntime, targetBundleID: "com.openai.codex",
            url: codexKey.bundleURL, port: 9333, deadline: 50,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9333]), log: { _, _ in })
        fatalError("FAILED: an exhausted deadline must fail the bounded open")
    } catch let error as StartupFailure {
        expect(error.reason == "attach-timeout", "an exhausted stage deadline maps to attach-timeout")
    }

    // Read-only inspection keeps application observation without page capabilities.
    let inspectRuntime = FakeNativeAppRuntime(arguments: ["Agent Skin"])
    inspectRuntime.applications = [hotApp]
    let inspectAssembly = CodexSkinAssembly(
        preflightBundle: { _, _ in }, activateExisting: { _ in false },
        preparePort: { try inspectRuntime.allocateLoopbackPort() },
        openApplication: { _, _, _, _ in throw StartupFailure(reason: "protocol-error", message: "inspect never opens") },
        onTargetOpened: { _ in }, onCaptureReady: { _ in }, eventStream: { contractEventStream(pid: 4343) }, onOpeningChanged: { _ in },
        startupFacts: { app in
            StartupTargetFacts(pid: app.processIdentifier,
                               bundle: app.bundleURL!.resolvingSymlinksInPath().standardizedFileURL,
                               executable: app.executableURL!.resolvingSymlinksInPath().standardizedFileURL,
                               bundleID: app.bundleIdentifier!, launchTime: app.launchTime)
        },
        performDisable: nil)
    let inspectDriver = CodexSkinDriver(
        inputs: boundInputs(hotOnlyFindings(codexKey)), runtime: inspectRuntime,
        readPayload: { "inspect-payload" },
        makeTargetSystem: { FakeStartupSystem(expectedPID: 4123, ports: []) },
        makeConnector: { _, _, _, _, _ in
            StartupConnector(target: .init(pid: 4123, bundle: codexKey.bundleURL,
                                           executable: codexKey.executableURL,
                                           bundleID: codexKey.bundleIdentifier, launchTime: nil),
                             expectedPort: 9222, system: FakeStartupSystem(expectedPID: 4123, ports: []),
                             transport: FakeStartupTransport(), now: { 0 }, sleep: { _ in })
        },
        installObservation: CodexInstallObservation(), assembly: inspectAssembly)
    if case .observed(let process, let page) = await inspectDriver.inspect(
        SkinInspectRequest(expectedApplication: codexKey, operationID: UUID(), deadline: 160,
                           includePage: false, previousObservation: nil)) {
        expect(process?.pid == 4123, "application inspection observes the live process generation")
        expect(page.isNotObserved, "page state stays explicitly unobserved without page capabilities")
    } else { fatalError("FAILED: application inspection must observe") }
    expect(inspectRuntime.openCount == 0, "inspection never implicitly cold-starts the host")
    if case .unavailable(let refusal) = await inspectDriver.inspect(
        SkinInspectRequest(expectedApplication: codexKey, operationID: UUID(), deadline: 160,
                           includePage: true, previousObservation: nil)) {
        expect(refusal.reason == .capabilityUnverified,
               "page inspection refuses when page identification is unverified")
    } else { fatalError("FAILED: page inspection without capability must refuse") }

    return checks
}

@MainActor
private final class PlaceholderSkinHostDriver: SkinHostDriver {
    let inputs: BoundHostInputs?
    init(inputs: BoundHostInputs?) { self.inputs = inputs }
    func launch(_ request: SkinLaunchRequest) async -> SkinLaunchResult { .refused(HostRefusal(host: .codex, reason: .implementationUnavailable, findings: [], detail: "placeholder", nextProbe: nil)) }
    func inspect(_ request: SkinInspectRequest) async -> SkinInspectResult { .unavailable(HostRefusal(host: .codex, reason: .implementationUnavailable, findings: [], detail: "placeholder", nextProbe: nil)) }
    func disable(_ request: SkinDisableRequest) async -> SkinDisableResult { .unavailable(HostRefusal(host: .codex, reason: .implementationUnavailable, findings: [], detail: "placeholder", nextProbe: nil)) }
}

/// Fake target system whose operation lock is the real per-process WallpaperOperationLock.
private final class LockingStartupSystem: StartupTargetSystem {
    private let inner: FakeStartupSystem
    init(_ inner: FakeStartupSystem) { self.inner = inner }
    func preflightBundle(_ bundle: URL, deadline: TimeInterval) throws { try inner.preflightBundle(bundle, deadline: deadline) }
    func validate(_ target: StartupTargetFacts, deadline: TimeInterval) throws { try inner.validate(target, deadline: deadline) }
    func listeningPorts(_ target: StartupTargetFacts, deadline: TimeInterval) throws -> [Int] { try inner.listeningPorts(target, deadline: deadline) }
    func acquireOperationLock(pid: Int32) throws -> any StartupOperationLock { try WallpaperOperationLock.acquire(pid: pid) }
}

/// Transport fixture whose install evaluation is sent but its reply is lost.
private final class LostReplyStartupTransport: StartupTransport {
    private let pagesResponse: [[String: Any]]
    private let payloadMarker: String
    private(set) var evaluateCount = 0
    private(set) var disposeEvaluations = 0
    init(pages: [[String: Any]], payloadMarker: String) {
        self.pagesResponse = pages
        self.payloadMarker = payloadMarker
    }
    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] { pagesResponse }
    func connect(to url: URL, timeout: TimeInterval) throws {}
    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        evaluateCount += 1
        if source.contains(payloadMarker) {
            throw WallpaperFailure(state: "endpoint-unavailable", chinese: "丢失回复", english: "lost reply")
        }
        if source.contains("dispose.value.call(api)") { disposeEvaluations += 1 }
        if source.contains("controllerPresent") { return ["href": "app://-/index.html?initialRoute=%2F", "controllerPresent": false] }
        return [:]
    }
    func close() {}
}
#endif


@MainActor
private func zcodeRuntimeReviewChecks() async throws -> Int {
    var checks = 0
    func expect(_ value: Bool, _ message: String) { precondition(value, message);checks += 1 }
    expect(NativeEntryIdentity.host(bundleIdentifier: "local.azhou.zcode-startup", declaredHost: nil) == nil, "ZCode missing host must not choose Codex")
    expect(NativeEntryIdentity.host(bundleIdentifier: "local.azhou.zcode-startup", declaredHost: "codex") == nil, "ZCode wrong host must refuse")
    expect(NativeEntryIdentity.host(bundleIdentifier: "local.azhou.codex-startup", declaredHost: nil) == .codex, "legacy Codex default preserved")
    expect(NativeEntryIdentity.host(bundleIdentifier: "local.azhou.zcode-startup", declaredHost: "zcode") == .zcode, "explicit ZCode identity bound")
    let row = Data("p123\nn127.0.0.1:45678\n".utf8)
    expect(try ZCodeNativeRuntime.validatedListenerOutput(status: 0, stdout: row, stderr: Data()) == String(decoding: row, as: UTF8.self), "clean listener output retained")
    do { _ = try ZCodeNativeRuntime.validatedListenerOutput(status: 0, stdout: row, stderr: Data("warning".utf8));preconditionFailure("warning must refuse") } catch { checks += 1 }
    expect(try ZCodeNativeRuntime.validatedListenerOutput(status: 1, stdout: Data(), stderr: Data()) == "", "clean empty not-ready distinct")
    let temporary = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString).resolvingSymlinksInPath()
    try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: temporary) }
    let key = HostApplicationKey(host: .zcode, bundleURL: URL(fileURLWithPath: "/Applications/ZCode.app"),
        executableURL: URL(fileURLWithPath: "/Applications/ZCode.app/Contents/MacOS/ZCode"), bundleIdentifier: "dev.zcode.app",
        version: "3.17.2", build: "3.17.2.9661", executableSHA256: "a9279c2cb198fa58efe564b417ff6717cff388c5fa391c17fc2766a6b1b2121d")
    let proof: [String: Any] = ["schema": "agent-skin-zcode-ui-evidence/v1", "contractVersion": SkinHostContract.version,
        "recordID": "SYNTHETIC-only", "recordSHA256": String(repeating: "b", count: 64), "observedAt": "2026-11-02T14:00:00Z",
        "infoSHA256": "aa29610c3c02fb37416d8a12322adf58bf1a27270718f07bbbc5ea3efe77c593",
        "version": "3.17.2.9661", "executableSHA256": key.executableSHA256,
        "appAsarSHA256": "12a2fc939df2fcb4188699772590f5151f1f2b90556bd34ecb6d44cf0d793cc6",
        "payloadSHA256": String(repeating: "a", count: 64), "evidenceIDs": ["SYNTHETIC-fixture-not-host"],
        "ownedAppearanceSurface": true, "persistentSettings": true]
    try JSONSerialization.data(withJSONObject: proof).write(to: temporary.appendingPathComponent("zcode-validation.json"))
    // A real Bundle returns resources relative to its bundle base. The exact
    // same physical proof must work through that URL form, without accepting a
    // real symlink or relaxing any proof/installed-identity field.
    let fixtureBundleURL = temporary.appendingPathComponent("ProofResources.app", isDirectory: true)
    let fixtureContents = fixtureBundleURL.appendingPathComponent("Contents", isDirectory: true)
    let fixtureResources = fixtureContents.appendingPathComponent("Resources", isDirectory: true)
    try FileManager.default.createDirectory(at: fixtureResources, withIntermediateDirectories: true)
    let fixtureInfo: [String: Any] = ["CFBundleIdentifier": "local.azhou.synthetic.proof-resources",
        "CFBundleExecutable": "SyntheticNotExecutable", "CFBundlePackageType": "APPL", "CFBundleVersion": "1"]
    try PropertyListSerialization.data(fromPropertyList: fixtureInfo, format: .xml, options: 0)
        .write(to: fixtureContents.appendingPathComponent("Info.plist"))
    let fixtureBundle = Bundle(url: fixtureBundleURL)!
    let bundleResources = fixtureBundle.resourceURL!
    let bundleProof = bundleResources.appendingPathComponent("zcode-validation.json")
    let proofBytes = try JSONSerialization.data(withJSONObject: proof)
    try proofBytes.write(to: bundleProof)
    expect(bundleProof.baseURL != nil && bundleProof.path == bundleProof.resolvingSymlinksInPath().path,
           "real Bundle fixture reproduces the same physical file with a retained base URL")
    func hasUIEvidence(_ resources: URL) -> Bool {
        ZCodeNativeRuntime.findings(for: key, resources: resources)
            .filter { $0.capability == .ownedAppearanceSurface || $0.capability == .persistentSettings }
            .allSatisfy { $0.state == .verified && $0.evidenceIDs == ["SYNTHETIC-fixture-not-host"] }
    }
    expect(hasUIEvidence(bundleResources), "actual Bundle resources accept the physical valid proof without a representation false refusal")
    let invalidProofs: [[String: Any]] = [["schema": "wrong"], ["contractVersion": "wrong"],
        ["version": "wrong"], ["infoSHA256": String(repeating: "0", count: 64)],
        ["executableSHA256": String(repeating: "0", count: 64)], ["appAsarSHA256": String(repeating: "0", count: 64)],
        ["recordSHA256": "short"], ["payloadSHA256": "short"], ["observedAt": "not-a-time"], ["evidenceIDs": []]]
    for overrides in invalidProofs {
        var invalid = proof;invalid.merge(overrides) { _, replacement in replacement }
        try JSONSerialization.data(withJSONObject: invalid).write(to: bundleProof)
        expect(!hasUIEvidence(bundleResources), "Bundle URL normalization preserves schema/hash/installation/time/evidence refusal")
    }
    try proofBytes.write(to: bundleProof)
    let alternateProof = temporary.appendingPathComponent("other-owned-proof.json")
    try proofBytes.write(to: alternateProof)
    try FileManager.default.removeItem(at: bundleProof)
    try FileManager.default.createSymbolicLink(at: bundleProof, withDestinationURL: alternateProof)
    expect(!hasUIEvidence(bundleResources), "real proof-file symlink remains refused through Bundle resources")
    try FileManager.default.removeItem(at: bundleProof);try proofBytes.write(to: bundleProof)
    let physicalResources = fixtureContents.appendingPathComponent("PhysicalResources", isDirectory: true)
    try FileManager.default.moveItem(at: fixtureResources, to: physicalResources)
    try FileManager.default.createSymbolicLink(at: fixtureResources, withDestinationURL: physicalResources)
    expect(!hasUIEvidence(bundleResources), "a symlinked Resources ancestor remains refused even with identical proof bytes")
    let fake = FakeNativeAppRuntime(arguments: [], resourceURL: temporary)
    let inputs = BoundHostInputs(identity: HostIdentityEvidence(key: key, signingIdentity: "synthetic", evidenceID: "synthetic"), findings: [], contractVersion: SkinHostContract.version)
    let state = temporary.appendingPathComponent("must-not-create")
    var proofFailureEvents: [[String: Any]] = []
    let bridge = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "different-real-bytes" }, stateRoot: state,
        onEvent: { proofFailureEvents.append($0) }, installationProbe: {})
    do { _ = try await bridge.makeAssembly().openApplication(110);preconditionFailure("stale proof must refuse before open") } catch { checks += 1 }
    expect(fake.openCount == 0 && fake.allocationCount == 0 && !FileManager.default.fileExists(atPath: state.path), "stale proof takes no host/port/directory effects")
    expect(proofFailureEvents.count == 1 && Set(proofFailureEvents[0].keys) == ["stage", "point", "reason"]
        && proofFailureEvents[0]["stage"] as? String == "zcode-runtime-failed"
        && proofFailureEvents[0]["point"] as? String == "open-proof"
        && proofFailureEvents[0]["reason"] as? String == "asset-invalid",
        "stale proof reports only the actual bounded failure point and fixed reason before any open effect")
    let listenerState = temporary.appendingPathComponent("listener-fixture")
    try FileManager.default.createDirectory(at: listenerState, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    let listenerApp = FakeNativeApplication(pid: 654321, bundleIdentifier: key.bundleIdentifier,
        bundleURL: key.bundleURL, executableURL: key.executableURL, launchTime: 50)
    let process = HostProcessGeneration(pid: listenerApp.processIdentifier, launchTime: 50, executableURL: key.executableURL)
    fake.applications = [listenerApp]
    let record: [String: Any] = ["pid": process.pid, "launchTime": 50.0, "port": 45678, "executableSHA256": key.executableSHA256]
    try JSONSerialization.data(withJSONObject: record).write(to: listenerState.appendingPathComponent("launch-receipt.json"))
    let invalidListeners: [ZCodeNativeRuntime.ListenerCommandResult] = [
        .init(status: 0, stdout: Data("p654321\nn127.0.0.1:45678\n".utf8), stderr: Data("warning".utf8)),
        .init(status: 2, stdout: Data(), stderr: Data()),
        .init(status: 0, stdout: Data([255]), stderr: Data()),
        .init(status: 0, stdout: Data(repeating: 65, count: 65536), stderr: Data()),
        .init(status: 0, stdout: Data("p999999\nn127.0.0.1:45678\n".utf8), stderr: Data()),
        .init(status: 0, stdout: Data("p654321\nn0.0.0.0:45678\n".utf8), stderr: Data()),
        .init(status: 0, stdout: Data("n127.0.0.1:45678\n".utf8), stderr: Data()),
    ]
    for (index, result) in invalidListeners.enumerated() {
        var calls: [Int32] = []
        var listenerFailureEvents: [[String: Any]] = []
        let checked = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "unused" }, stateRoot: listenerState,
            onEvent: { listenerFailureEvents.append($0) }, installationProbe: {}, listenerCommand: { pid in calls.append(pid);return result })
        do { _ = try await checked.makeAssembly().attach(process, 110, .existingPage);preconditionFailure("invalid listener evidence accepted") }
        catch { checks += 1 }
        expect(calls == [process.pid], "only the bound synthetic process is queried once before refusal")
        expect(listenerFailureEvents.count == 1 && Set(listenerFailureEvents[0].keys) == ["stage", "point", "reason"]
            && listenerFailureEvents[0]["stage"] as? String == "zcode-runtime-failed"
            && listenerFailureEvents[0]["point"] as? String == "listener"
            && listenerFailureEvents[0]["reason"] as? String == (index < 4 ? "inspection-failed" : "listener-mismatch"),
            "listener inspection failure retains its actual stage and bounded reason without raw command output")
    }
    var cleanNotReadyCalls = 0
    let notReady = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "unused" }, stateRoot: listenerState,
        onEvent: { _ in }, installationProbe: {}, listenerCommand: { _ in
            cleanNotReadyCalls += 1;fake.uptime = 111
            return .init(status: 1, stdout: Data(), stderr: Data())
        })
    do { _ = try await notReady.makeAssembly().attach(process, 110, .existingPage);preconditionFailure("clean empty inspection cannot mean ready") }
    catch { checks += 1 }
    expect(cleanNotReadyCalls == 1, "empty successful query remains not-ready until bounded deadline")
    fake.uptime = 101
    let absent = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "unused" }, stateRoot: listenerState,
        onEvent: { _ in }, installationProbe: {}, listenerCommand: { _ in preconditionFailure("stale process must refuse before listener query") },
        identityWaitBudget: 0.2)
    fake.applications = []
    do { try await absent.makeAssembly().validateProcess(process, 999);preconditionFailure("missing process accepted") }
    catch { checks += 1 }
    fake.applications = [listenerApp]

    // A freshly opened host may still be completing its LaunchServices
    // registration when the assembly re-queries it (the 2026-11-08 16:44
    // transient); the identity wait rides out that window instead of failing
    // on the first snapshot, while a confirmed mismatch still refuses fast.
    let lateProcess = HostProcessGeneration(pid: listenerApp.processIdentifier, launchTime: 50, executableURL: key.executableURL)
    var lateCalls = 0
    fake.applications = []
    fake.applicationOverride = { _ in
        lateCalls += 1
        return lateCalls >= 2 ? listenerApp : nil
    }
    let lateIdentity = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "unused" }, stateRoot: listenerState,
        onEvent: { _ in }, installationProbe: {}, listenerCommand: { _ in preconditionFailure("identity wait must not query the listener") })
    try await lateIdentity.makeAssembly().validateProcess(lateProcess, 999)
    expect(lateCalls >= 2, "an unregistered fresh host is awaited, not refused")
    fake.applicationOverride = nil

    let impostor = FakeNativeApplication(pid: listenerApp.processIdentifier, bundleIdentifier: "com.other.impostor",
        bundleURL: key.bundleURL, executableURL: key.executableURL, launchTime: 50)
    fake.applications = [impostor]
    let impostorRuntime = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "unused" }, stateRoot: listenerState,
        onEvent: { _ in }, installationProbe: {}, listenerCommand: { _ in preconditionFailure("wrong bundle must refuse before listener query") })
    do { try await impostorRuntime.makeAssembly().validateProcess(lateProcess, 999);preconditionFailure("wrong-bundle identity accepted") } catch { checks += 1 }
    fake.applications = []

    var refusedEvents: [[String: Any]] = []
    let missingRuntime = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "unused" }, stateRoot: listenerState,
        onEvent: { refusedEvents.append($0) }, installationProbe: {}, listenerCommand: { _ in preconditionFailure("missing host must not reach the listener") },
        identityWaitBudget: 0.3)
    do { try await missingRuntime.makeAssembly().validateProcess(lateProcess, 999);preconditionFailure("missing host accepted") } catch { checks += 1 }
    expect(refusedEvents.contains { $0["stage"] as? String == "zcode-validate-identity-refused" && $0["observed"] as? String == "missing" },
           "identity wait reports its final observed state before refusing")
    fake.uptime = 101

    var exhaustedEvents: [[String: Any]] = []
    let exhaustedRuntime = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "unused" }, stateRoot: listenerState,
        onEvent: { exhaustedEvents.append($0) }, installationProbe: {}, listenerCommand: { _ in preconditionFailure("deadline-exhausted validate must not query the listener") })
    do { try await exhaustedRuntime.makeAssembly().validateProcess(lateProcess, fake.uptime);preconditionFailure("exhausted deadline accepted") } catch { checks += 1 }
    expect(exhaustedEvents.contains { $0["stage"] as? String == "zcode-validate-identity-refused" && $0["observed"] as? String == "deadline-exhausted" },
           "an exhausted operation deadline refuses immediately without starting the identity wait")
    let symbolicState = temporary.appendingPathComponent("symbolic-listener")
    try FileManager.default.createSymbolicLink(at: symbolicState, withDestinationURL: listenerState)
    let publicState = temporary.appendingPathComponent("too-wide-listener")
    try FileManager.default.createDirectory(at: publicState, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o755])
    try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: publicState.path)
    for invalidState in [symbolicState, publicState] {
        let rejected = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { "unused" }, stateRoot: invalidState,
            onEvent: { _ in }, installationProbe: {}, listenerCommand: { _ in preconditionFailure("invalid directory must refuse before process query") })
        do { _ = try await rejected.makeAssembly().attach(process, 110, .existingPage);preconditionFailure("invalid directory accepted") }
        catch let error as StartupFailure { expect(error.reason == "profile-isolation-unproven", "directory hint normalization preserves symlink and private-permission guards") }
    }
    var captured: NSWorkspace.OpenConfiguration?
    let system = SystemNativeAppRuntime(openApplication: { _, config, done in captured = config;done(nil, nil) })
    let environment = ["HOME": "/synthetic/owned/home", "ZCODE_DATA_BASE_DIR": "/synthetic/owned/business"]
    system.openApplication(at: key.bundleURL, debuggingPort: 12345, environment: environment) { _, _ in }
    expect(captured?.environment == environment && captured?.arguments == ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=12345"] && captured?.activates == true, "ZCode NSWorkspace requests activation with its exact explicit environment")
    system.openApplication(at: URL(fileURLWithPath: "/synthetic/Codex.app"), debuggingPort: 12345) { _, _ in }
    expect(captured?.environment == NSWorkspace.OpenConfiguration().environment && captured?.activates == false, "Codex original default environment and inactive launch unchanged")
    return checks
}

@MainActor
private final class ZCodeRuntimeFixture {
    let root: URL
    let state: URL
    let resources: URL
    let fake: FakeNativeAppRuntime
    let app: FakeNativeApplication
    let key: HostApplicationKey
    let inputs: BoundHostInputs
    let port: Int
    var payload = "((controllerMetadata) => { return {installed:true}; })"
    var payloadReadFailure = false
    var payloadReads = 0
    var probeFailure = false
    var events: [[String: Any]] = []
    var listenerPIDs: [Int32] = []
    var listenerOverride: ((Int32) throws -> ZCodeNativeRuntime.ListenerCommandResult)?
    let identityWaitBudget: TimeInterval?
    var held: [any ZCodeOperationLease] = []
    lazy var bridge = ZCodeNativeRuntime(inputs: inputs, runtime: fake, readPayload: { [weak self] in
        guard let self, !self.payloadReadFailure else { throw StartupFailure(reason: "asset-invalid", message: "synthetic payload failure") }
        self.payloadReads += 1;return self.payload
    }, stateRoot: state, onEvent: { [weak self] in self?.events.append($0) }, installationProbe: { [weak self] in
        guard let self, !self.probeFailure else { throw StartupFailure(reason: "target-identity", message: "synthetic installation failure") }
    }, listenerCommand: { [weak self] pid in
        guard let self else { throw StartupFailure(reason: "inspection-failed", message: "synthetic fixture gone") }
        self.listenerPIDs.append(pid)
        if let override = self.listenerOverride { return try override(pid) }
        return .init(status: 0, stdout: Data("p\(pid)\nn127.0.0.1:\(self.port)\n".utf8), stderr: Data())
    }, identityWaitBudget: identityWaitBudget ?? 8)
    init(port: Int, pid: Int32 = 654321, version: String = "3.17.2", build: String = "3.17.2.9661",
         executableSHA256: String = "a9279c2cb198fa58efe564b417ff6717cff388c5fa391c17fc2766a6b1b2121d",
         identityWaitBudget: TimeInterval? = nil) throws {
        self.port = port
        root = FileManager.default.temporaryDirectory.appendingPathComponent("zcode-runtime-unit-" + UUID().uuidString, isDirectory: true).resolvingSymlinksInPath()
        state = root.appendingPathComponent("state", isDirectory: true)
        resources = root.appendingPathComponent("resources", isDirectory: true)
        try FileManager.default.createDirectory(at: resources, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        key = HostApplicationKey(host: .zcode, bundleURL: URL(fileURLWithPath: "/Applications/ZCode.app"), executableURL: URL(fileURLWithPath: "/Applications/ZCode.app/Contents/MacOS/ZCode"), bundleIdentifier: "dev.zcode.app", version: version, build: build, executableSHA256: executableSHA256)
        inputs = BoundHostInputs(identity: HostIdentityEvidence(key: key, signingIdentity: "synthetic", evidenceID: "synthetic-only"), findings: [], contractVersion: SkinHostContract.version)
        fake = FakeNativeAppRuntime(arguments: ["SYNTHETIC-ONLY"], resourceURL: resources)
        fake.allocatedPort = port
        app = FakeNativeApplication(pid: pid, bundleIdentifier: key.bundleIdentifier, bundleURL: key.bundleURL, executableURL: key.executableURL, launchTime: 50)
        fake.openedApplication = app
        fake.beforeOpenCompletion = { [weak fake, weak app] in if let app { fake?.applications = [app] } }
        self.identityWaitBudget = identityWaitBudget
        try writeProof()
    }
    var hash: String { SHA256.hash(data: Data(payload.utf8)).map { String(format: "%02x", $0) }.joined() }
    var process: HostProcessGeneration { .init(pid: app.processIdentifier, launchTime: 50, executableURL: key.executableURL) }
    var assembly: ZCodeSkinAssembly { bridge.makeAssembly() }
    var request: SkinLaunchRequest { .init(expectedApplication: key, operationID: UUID(), startedAt: 100, deadline: 160) }
    func writeProof(_ overrides: [String: Any] = [:]) throws {
        var proof: [String: Any] = ["schema": "agent-skin-zcode-ui-evidence/v1", "contractVersion": SkinHostContract.version,
            "recordID": "SYNTHETIC-NOT-HOST", "recordSHA256": String(repeating: "b", count: 64), "observedAt": "2026-11-02T15:00:00.123Z",
            "infoSHA256": "aa29610c3c02fb37416d8a12322adf58bf1a27270718f07bbbc5ea3efe77c593", "version": "3.17.2.9661",
            "executableSHA256": key.executableSHA256, "appAsarSHA256": "12a2fc939df2fcb4188699772590f5151f1f2b90556bd34ecb6d44cf0d793cc6",
            "payloadSHA256": hash, "evidenceIDs": ["SYNTHETIC-ONLY-NOT-ACCEPTANCE"], "ownedAppearanceSurface": true, "persistentSettings": true]
        proof.merge(overrides) { _, replacement in replacement }
        try JSONSerialization.data(withJSONObject: proof).write(to: resources.appendingPathComponent("zcode-validation.json"))
    }
    func acquire() throws { held.append(try assembly.acquireOperation(process.pid)) }
    func close() { held.forEach { $0.release() };held.removeAll() }
    func cleanup() { close();try? FileManager.default.removeItem(at: root) }
}

@MainActor
private func zcodeRuntimeFixtureChecks(port: Int) async throws -> Int {
    var checks = 0
    var fixtures: [ZCodeRuntimeFixture] = []
    func expect(_ value: Bool, _ label: String) { precondition(value, label);checks += 1 }
    func make(identityWaitBudget: TimeInterval? = nil) throws -> ZCodeRuntimeFixture { let f = try ZCodeRuntimeFixture(port: port, identityWaitBudget: identityWaitBudget);fixtures.append(f);return f }
    defer { fixtures.forEach { $0.cleanup() } }
    func mode(_ value: String, reset: Bool = true) async throws {
        let configuration = URLSessionConfiguration.ephemeral;configuration.httpCookieStorage = nil;configuration.urlCredentialStorage = nil
        let session = URLSession(configuration: configuration);defer { session.invalidateAndCancel() }
        var request = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/fixture/mode")!);request.httpMethod = "POST";request.timeoutInterval = 2
        request.httpBody = try JSONSerialization.data(withJSONObject: ["mode": value, "reset": reset]);request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let (_, response) = try await session.data(for: request)
        expect((response as? HTTPURLResponse)?.statusCode == 200, "owned synthetic fixture accepts mode")
    }
    func open(_ f: ZCodeRuntimeFixture) async throws -> ZCodePageBinding {
        let observed = try await f.assembly.openApplication(160)
        expect(observed == f.process, "cold callback retains exact generation")
        try f.acquire()
        return try await f.assembly.attach(observed, 160, .existingPage)
    }
    let capabilityFixture = try make()
    let validFindings = ZCodeNativeRuntime.findings(for: capabilityFixture.key, resources: capabilityFixture.resources)
    expect(validFindings.count == SkinCapability.allCases.count, "every capability has its own typed finding")
    expect(validFindings.allSatisfy { $0.subject.application == capabilityFixture.key && $0.subject.contractVersion == SkinHostContract.version }, "finding subjects remain bound to the requested installation contract")
    for capability in [SkinCapability.ownedAppearanceSurface, .persistentSettings] {
        let finding = validFindings.first { $0.capability == capability }
        expect(finding?.state == .verified && finding?.evidenceIDs == ["SYNTHETIC-ONLY-NOT-ACCEPTANCE"], "only explicit fixture proof fills the matching UI capability")
    }
    let absentFindings = ZCodeNativeRuntime.findings(for: capabilityFixture.key, resources: nil)
    expect(absentFindings.filter { $0.capability == .ownedAppearanceSurface || $0.capability == .persistentSettings }.allSatisfy { $0.state == .unverified && $0.evidenceIDs.isEmpty }, "absent resource proof never invents UI evidence")
    try capabilityFixture.writeProof(["ownedAppearanceSurface": false])
    let splitFindings = ZCodeNativeRuntime.findings(for: capabilityFixture.key, resources: capabilityFixture.resources)
    expect(splitFindings.first { $0.capability == .ownedAppearanceSurface }?.state == .unverified
        && splitFindings.first { $0.capability == .persistentSettings }?.state == .verified, "appearance and storage evidence stay independent")
    try Data(repeating: 65, count: 16384).write(to: capabilityFixture.resources.appendingPathComponent("zcode-validation.json"))
    expect(ZCodeNativeRuntime.findings(for: capabilityFixture.key, resources: capabilityFixture.resources).filter { $0.capability == .ownedAppearanceSurface || $0.capability == .persistentSettings }.allSatisfy { $0.state == .unverified }, "oversized proof is never a capability receipt")

    // Exercise the unchanged default Process adapter against this test binary
    // only. It cannot own the Python fixture server's port; no host PID is read.
    let selfListener = try ZCodeRuntimeFixture(port: port, pid: getpid());fixtures.append(selfListener)
    selfListener.fake.applications = [selfListener.app]
    try FileManager.default.createDirectory(at: selfListener.state, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    let ownRecord: [String: Any] = ["pid": selfListener.process.pid, "launchTime": 50.0, "port": port, "executableSHA256": selfListener.key.executableSHA256]
    try JSONSerialization.data(withJSONObject: ownRecord).write(to: selfListener.state.appendingPathComponent("launch-receipt.json"))
    let realListener = ZCodeNativeRuntime(inputs: selfListener.inputs, runtime: selfListener.fake, readPayload: { "unused" },
        stateRoot: selfListener.state, onEvent: { _ in }, installationProbe: {})
    let expireOwnRead = Task { try? await Task.sleep(nanoseconds: 100_000_000);selfListener.fake.uptime = 111 }
    do { _ = try await realListener.makeAssembly().attach(selfListener.process, 110, .existingPage);fatalError("test binary cannot own the separate fixture server port") }
    catch ZCodeAttachFailure.deadline { expect(true, "unowned listener respects the bounded deadline") }
    catch let error as StartupFailure { expect(error.reason == "listener-mismatch", "default self-PID inspection refuses an unowned port, not an inspection error") }
    expireOwnRead.cancel()
    expect(selfListener.fake.openCount == 0, "self-listener unit probe opens no host application")

    // Real assembly, fake native boundary, and real owned loopback protocol.
    try await mode("ready")
    let ready = try make();let binding = try await open(ready)
    expect(ready.fake.openCount == 1 && ready.fake.allocationCount == 1, "cold path opens and allocates once")
    expect(ready.fake.openedEnvironments.count == 1 && ready.fake.openedEnvironments[0].isEmpty, "daily cold launch passes no profile overrides so the user's own profile stays in effect")
    for name in ["home", "tmp", "business", "electron-user", "electron-session"] {
        expect(!FileManager.default.fileExists(atPath: ready.state.appendingPathComponent(name).path), "daily launch creates no isolated profile directories")
    }
    let record = try JSONSerialization.jsonObject(with: Data(contentsOf: ready.state.appendingPathComponent("launch-receipt.json"))) as! [String: Any]
    expect(record["pid"] as? Int32 == ready.process.pid && record["launchTime"] as? Double == 50 && record["port"] as? Int == port, "owned launch record preserves exact generation and port")
    expect(try ready.assembly.runningProcesses() == [ready.process], "running inspection returns exact known generation")
    expect(try await ready.assembly.activateExisting(ready.process, 999), "hot activation uses validated existing generation")
    let observation = ZCodeInstallObservation();let request = ready.request
    let result = try await ready.assembly.install(binding, request, observation)
    guard case .ready(let receipt, let runID) = result else { fatalError("synthetic ready assembly did not acknowledge") }
    expect(observation.sent && runID == 1 && receipt.createdByOperationID == request.operationID && receipt.payloadSHA256 == ready.hash, "ready is backed by actual sent metadata and status")
    expect(!ready.listenerPIDs.isEmpty && ready.listenerPIDs.allSatisfy { $0 == ready.process.pid }, "all listener checks query only bound fake PID")
    if case .present(.instance(let inspected), .alreadyActive) = try await ready.assembly.inspectPage(binding, 160) {
        expect(inspected.location.application == receipt.location.application && inspected.location.process == receipt.location.process
            && inspected.location.documentToken == receipt.location.documentToken && inspected.owner == receipt.owner
            && inspected.protocolVersion == receipt.protocolVersion && inspected.payloadSHA256 == receipt.payloadSHA256
            && inspected.controllerInstanceID == receipt.controllerInstanceID && inspected.createdByOperationID == receipt.createdByOperationID,
            "inspect reads every exact current owned receipt field")
    } else { fatalError("synthetic inspect lost receipt") }
    do { _ = try await ready.assembly.inspectPage(binding, 160);fatalError("closed connection must not inspect") } catch { checks += 1 }
    let disposeBinding = try await ready.assembly.attach(ready.process, 160, .existingPage)
    expect(try await ready.assembly.dispose(disposeBinding, receipt, 160), "dispose acknowledges matching owner instance")
    let repeatBinding = try await ready.assembly.attach(ready.process, 160, .existingPage)
    expect(try await ready.assembly.dispose(repeatBinding, receipt, 160), "repeat dispose confirms already absent")
    let absentBinding = try await ready.assembly.attach(ready.process, 160, .existingPage)
    ready.payloadReadFailure = true
    if case .absent(let location) = try await ready.assembly.inspectPage(absentBinding, 160) { expect(location.process == ready.process, "absence is exact and does not read payload") }
    else { fatalError("disposed controller not absent") }
    do { _ = try await ready.assembly.dispose(absentBinding, receipt, 160);fatalError("closed connection must not dispose") } catch { checks += 1 }
    ready.close();ready.close()
    expect(ready.events.contains { $0["stage"] as? String == "zcode-open-selected-process" && $0["native_child_wait_claim"] as? Bool == false }, "NSWorkspace selected host never fabricates native child wait")

    for value in ["complete", "before-ready", "already-active", "readylost", "badreceipt", "absent", "dispose-failed", "late", "interrupted"] {
        try await mode(value);let f = try make();let b = try await open(f);let observed = ZCodeInstallObservation();let req = f.request
        var expiry: Task<Void, Never>?
        if value == "late" { expiry = Task { try? await Task.sleep(nanoseconds: 150_000_000);f.fake.uptime = 161 } }
        defer { expiry?.cancel();f.close() }
        do {
            let outcome = try await f.assembly.install(b, req, observed)
            switch value {
            case "complete", "before-ready":
                guard case .skipped(.present(.instance(let r), .created), _, let before) = outcome else { fatalError("completion acquisition lost") }
                expect(before == (value == "before-ready") && r.createdByOperationID == req.operationID, "completion preserves actual before-ready flag and created receipt")
            case "already-active":
                guard case .skipped(.present(.instance(let r), .alreadyActive), _, _) = outcome else { fatalError("existing acquisition upgraded") }
                expect(r.createdByOperationID != req.operationID, "already-active retains previous operation")
            case "readylost", "late":
                guard case .partial(_, .present(.instance(let r), .created), let cleanup) = outcome else { fatalError("confirmed receipt erased after interruption") }
                expect(r.createdByOperationID == req.operationID && cleanup.state == .unknown, "later interruption preserves confirmed effect and unknown cleanup")
            case "interrupted":
                guard case .partial(let failure, .present(.instance(let r), .created), _) = outcome else {
                    fatalError("ZCode polled past terminal failure and accepted a later ready")
                }
                expect(failure.detail == "startup-interrupted" && r.createdByOperationID == req.operationID,
                       "terminal controller failure promptly reports interruption with its acknowledged receipt")
            case "dispose-failed":
                guard case .ready(let r, _) = outcome else { fatalError("dispose fixture not ready") }
                expect(try await f.assembly.dispose(b, r, 160) == false, "unconfirmed dispose cannot claim clean")
            default: fatalError("invalid receipt/absent controller unexpectedly acknowledged")
            }
            expect(observed.sent, "result follows a real protocol send")
        } catch {
            expect(["badreceipt", "absent"].contains(value) && observed.sent, "unacknowledged sent install remains an error")
        }
    }

    // Proof validation must finish before any native open, port or state effects.
    let invalidProofs: [[String: Any]] = [["recordSHA256": "bad"], ["observedAt": "not-a-date"], ["evidenceIDs": []], ["ownedAppearanceSurface": false], ["persistentSettings": false], ["payloadSHA256": String(repeating: "f", count: 64)]]
    for overrides in invalidProofs {
        let f = try make();try f.writeProof(overrides)
        do { _ = try await f.assembly.openApplication(160);fatalError("invalid proof opened host") } catch { checks += 1 }
        expect(f.fake.openCount == 0 && f.fake.allocationCount == 0 && !FileManager.default.fileExists(atPath: f.state.path), "invalid proof has zero cold side effects")
    }
    let existing = try make();existing.fake.applications = [existing.app]
    do { _ = try await existing.assembly.openApplication(160);fatalError("cold path ignored running process") } catch { checks += 1 }
    expect(existing.payloadReads == 0 && existing.fake.openCount == 0, "existing process refuses cold before payload access")
    let invalidProcess = try make(identityWaitBudget: 0.2);invalidProcess.fake.applications = [FakeNativeApplication(pid: invalidProcess.process.pid, bundleIdentifier: invalidProcess.key.bundleIdentifier, bundleURL: invalidProcess.key.bundleURL, executableURL: invalidProcess.key.executableURL, launchTime: nil)]
    do { try await invalidProcess.assembly.validateProcess(invalidProcess.process, 999);fatalError("missing process birth accepted") } catch { checks += 1 }
    let probe = try make();probe.probeFailure = true
    do { _ = try probe.assembly.runningProcesses();fatalError("failed installation probe ignored") } catch { checks += 1 }
    expect(probe.fake.openCount == 0 && probe.listenerPIDs.isEmpty, "installation failure precedes all host and listener effects")

    let driftedHosts = try [
        ZCodeRuntimeFixture(port: port, version: "3.17.1", build: "3.17.1.9553"),
        ZCodeRuntimeFixture(port: port, executableSHA256: String(repeating: "f", count: 64)),
    ]
    fixtures.append(contentsOf: driftedHosts)
    for drifted in driftedHosts {
        do {
            _ = try await drifted.assembly.openApplication(160)
            fatalError("unpinned ZCode identity opened the host")
        } catch let error as StartupFailure {
            expect(error.reason == "target-identity", "ZCode version or executable drift reports an identity refusal")
        }
        expect(drifted.payloadReads == 0 && drifted.fake.openCount == 0 && drifted.fake.allocationCount == 0
            && drifted.listenerPIDs.isEmpty && !FileManager.default.fileExists(atPath: drifted.state.path),
            "ZCode identity drift refuses before payload, port, process or profile side effects")
    }

    func checkOpenFailure(_ f: ZCodeRuntimeFixture, points: [(String, String)], selected: Bool, _ label: String) {
        let failures = f.events.filter { $0["stage"] as? String == "zcode-runtime-failed" }
        expect(failures.count == points.count, "\(label) reports exactly its actual failed phases")
        for (event, expected) in zip(failures, points) {
            expect(Set(event.keys) == ["stage", "point", "reason"]
                && event["point"] as? String == expected.0 && event["reason"] as? String == expected.1,
                "\(label) exposes only fixed stage/point/reason tags")
        }
        expect(f.events.filter { $0["stage"] as? String == "zcode-open-request" }.count == 1
            && f.events.filter { $0["stage"] as? String == "zcode-open-selected-process" }.count == (selected ? 1 : 0),
            "\(label) preserves actual request/selection facts without converting them into success")
        expect(!f.events.contains { event in
            event["stage"] as? String == "zcode-controller-ready"
                || ["startup-ready", "startup-skipped", "target-activated", "launcher-exit"].contains(event["event"] as? String ?? "")
                || event["ready"] as? Bool == true || event["completed"] as? Bool == true
        }, "\(label) never claims controller readiness, startup success or final exit")
    }
    let openError = try make()
    openError.fake.openError = NSError(domain: "synthetic-private", code: 17,
        userInfo: [NSLocalizedDescriptionKey: "private-url?token=must-not-leak"])
    do { _ = try await openError.assembly.openApplication(160);fatalError("NSWorkspace error callback was accepted") }
    catch let error as StartupFailure { expect(error.reason == "attach-timeout", "open callback errors retain bounded failure mapping") }
    expect(openError.fake.openCount == 1 && !FileManager.default.fileExists(atPath: openError.state.appendingPathComponent("launch-receipt.json").path), "error callback cannot create a selected success receipt")
    checkOpenFailure(openError, points: [("open-callback-error", "unclassified"), ("open-callback", "attach-timeout")],
        selected: true, "native callback error")
    let callbackEventJSON = String(decoding: try JSONSerialization.data(withJSONObject: openError.events), as: UTF8.self)
    expect(!callbackEventJSON.contains("synthetic-private") && !callbackEventJSON.contains("must-not-leak"),
        "native callback diagnostics never emit private error domain or localized description")
    let inactive = try make();inactive.app.activationResult = false
    do { _ = try await inactive.assembly.openApplication(160);fatalError("failed activation was accepted") }
    catch let error as StartupFailure { expect(error.reason == "target-identity", "failed activation does not become cold ready") }
    expect(inactive.app.activationCount == 1 && !FileManager.default.fileExists(atPath: inactive.state.appendingPathComponent("launch-receipt.json").path), "failed activation does not persist a reusable generation")
    checkOpenFailure(inactive, points: [("open-activation", "target-identity")], selected: true, "activation refusal")

    let unobservedSelection = try make();unobservedSelection.fake.beforeOpenCompletion = {}
    do { _ = try await unobservedSelection.assembly.openApplication(160);fatalError("unobserved selected process was accepted") }
    catch let error as StartupFailure { expect(error.reason == "target-identity", "callback selection still requires live fake runtime validation") }
    expect(unobservedSelection.app.activationCount == 0
        && !FileManager.default.fileExists(atPath: unobservedSelection.state.appendingPathComponent("launch-receipt.json").path),
        "selected callback without live generation cannot activate or create a reusable receipt")
    checkOpenFailure(unobservedSelection, points: [("open-selected-validation", "target-identity")], selected: true,
        "unobserved selected generation")

    let nilCallback = try make();nilCallback.fake.openedApplication = nil
    do { _ = try await nilCallback.assembly.openApplication(160);fatalError("empty callback was accepted") }
    catch let error as StartupFailure { expect(error.reason == "attach-timeout", "empty callback retains bounded failure mapping") }
    expect(nilCallback.app.activationCount == 0
        && !FileManager.default.fileExists(atPath: nilCallback.state.appendingPathComponent("launch-receipt.json").path),
        "empty callback cannot activate or create a reusable receipt")
    checkOpenFailure(nilCallback, points: [("open-callback", "attach-timeout")], selected: false, "empty callback")

    let blockedReceipt = try make()
    try FileManager.default.createDirectory(at: blockedReceipt.state, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    let receiptDirectory = blockedReceipt.state.appendingPathComponent("launch-receipt.json", isDirectory: true)
    try FileManager.default.createDirectory(at: receiptDirectory, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
    do { _ = try await blockedReceipt.assembly.openApplication(160);fatalError("receipt write into existing directory was accepted") }
    catch { checks += 1 }
    let blockedAttributes = try FileManager.default.attributesOfItem(atPath: receiptDirectory.path)
    expect(blockedAttributes[.type] as? FileAttributeType == .typeDirectory
        && blockedReceipt.app.activationCount == 1,
        "failed receipt write retains the fixture directory and never produces a reusable file despite activation")
    checkOpenFailure(blockedReceipt, points: [("open-receipt-write", "unclassified")], selected: true, "receipt write refusal")
    let unreadable = try make();unreadable.payloadReadFailure = true
    do { _ = try await unreadable.assembly.openApplication(160);fatalError("unreadable payload opened host") } catch { checks += 1 }
    expect(unreadable.fake.openCount == 0 && unreadable.fake.allocationCount == 0 && !FileManager.default.fileExists(atPath: unreadable.state.path), "unreadable payload refuses before every cold effect")

    // Bounded cancellation and late callbacks must never create a success receipt.
    let timeout = try make();timeout.fake.deferOpenCompletion = true
    do { _ = try await timeout.assembly.openApplication(101.02);fatalError("deferred callback ignored deadline") } catch { checks += 1 }
    timeout.fake.completePendingOpen();try await Task.sleep(nanoseconds: 10_000_000)
    expect(!FileManager.default.fileExists(atPath: timeout.state.appendingPathComponent("launch-receipt.json").path), "late callback cannot write a ready launch receipt")
    let cancelled = try make();cancelled.fake.deferOpenCompletion = true
    let pending = Task { () -> Bool in do { _ = try await cancelled.assembly.openApplication(160);return false } catch { return true } }
    for _ in 0..<100 where cancelled.fake.openCount == 0 { await Task.yield() }
    expect(cancelled.fake.openCount == 1, "cancel test reached the actual fake open callback")
    pending.cancel();let canceled = await pending.value;expect(canceled, "open cancellation unblocks bounded waiter")
    cancelled.fake.completePendingOpen();await Task.yield()
    expect(!FileManager.default.fileExists(atPath: cancelled.state.appendingPathComponent("launch-receipt.json").path), "cancelled late callback cannot claim a receipt")
    return checks
}

// Insert at file scope in StartupNativeTests.swift. Call from main before old tests:
// checks += nativePureStatusContractChecks()
@MainActor
private func nativePureStatusContractChecks() -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        precondition(condition(), label)
        checks += 1
    }
    let old = LegacyOnlyNativeRuntime()
    let legacy: any NativeAppRuntime = old
    var completions = 0
    var refusal: NSError?
    legacy.openApplication(at: URL(fileURLWithPath: "/synthetic/Legacy.app"), debuggingPort: 1337, environment: ["HOME": "/synthetic/home"]) { app, error in
        expect(app == nil, "legacy runtime cannot pretend to open with an unimplemented environment")
        refusal = error as NSError?;completions += 1
    }
    expect(completions == 1 && refusal?.domain == "local.azhou.zcode-startup" && refusal?.code == 1 && old.base.openCount == 0,
           "nonempty environment refuses before the legacy open path, preserving isolation")
    legacy.openApplication(at: URL(fileURLWithPath: "/synthetic/Legacy.app"), debuggingPort: 1337, environment: [:]) { _, error in
        expect(error == nil, "empty environment retains the original legacy callback")
        completions += 1
    }
    expect(completions == 2 && old.base.openCount == 1 && old.base.openedPorts == [1337] && old.base.openedEnvironments.isEmpty,
           "empty environment forwards exactly once to the original open method")
    func status(phase: String = "loading", ready: Bool = false, completed: Bool = false,
                overlay: Bool = true, completion: Any = NSNull(), reason: String = "") -> [String: Any] {
        ["owner": "azhou-codex-startup", "version": 1, "runId": 7, "phase": phase,
         "ready": ready, "completed": completed, "overlay": overlay, "completion": completion,
         "reason": reason, "wallpaper": ["applied": false, "reason": "disabled", "imageDecoded": false]]
    }
    let accepted = [
        status(), status(phase: "playing", ready: true), status(phase: "settings", ready: true),
        status(phase: "complete", completed: true, overlay: false,
               completion: ["cause": "natural", "beforeReady": false]),
        status(phase: "failed", overlay: false, reason: "asset-invalid"),
        status(phase: "timeout", overlay: false, reason: "overlay-timeout"),
        status(phase: "disposed", overlay: false)
    ]
    for value in accepted {
        expect(NativeStartupStatus.parse(value)?.phase == value["phase"] as? String,
               "valid lifecycle state is retained: \(value["phase"]!)")
        var visible = value
        visible["overlay"] = !(value["overlay"] as! Bool)
        expect(NativeStartupStatus.parse(visible) == nil,
               "lifecycle state rejects contradictory overlay: \(value["phase"]!)")
    }
    for value in [status(ready: true), status(completed: true),
                  status(phase: "playing"), status(phase: "settings"),
                  status(phase: "complete", overlay: false),
                  status(phase: "failed", overlay: false), status(phase: "timeout", overlay: false)] {
        expect(NativeStartupStatus.parse(value) == nil, "contradictory lifecycle flags fail closed")
    }
    for completion: Any in ["skip", [:] as [String: Any], ["cause": "unknown", "beforeReady": true],
                            ["cause": "skip", "beforeReady": 1], ["cause": "skip"]] {
        expect(NativeStartupStatus.parse(status(phase: "complete", completed: true, overlay: false,
                                                completion: completion)) == nil,
               "completion proof must have a known cause and a JSON boolean")
    }
    for field in ["version", "runId"] {
        for value: Any in [true, -1, 1.5, Double.nan, Double.infinity, "1"] {
            var malformed = status(); malformed[field] = value
            expect(NativeStartupStatus.parse(malformed) == nil,
                   "protocol integer rejects boolean, fractional, nonfinite, negative or string: \(field)")
        }
    }
    for field in ["ready", "completed", "overlay"] {
        var malformed = status(); malformed[field] = 0
        expect(NativeStartupStatus.parse(malformed) == nil, "numeric flag cannot impersonate JSON boolean: \(field)")
    }

    // An observed installation owns one run; another run cannot overwrite readiness.
    let capture = NativeStartupCapture(targetPID: 700)
    expect(capture.observe(["status": accepted[1]], at: 1) == nil
           && capture.snapshot().status == nil, "status without our installation does not establish ownership")
    expect(capture.observe(["installed": true, "alreadyActive": false, "status": accepted[0]], at: 2)?.runID == 7,
           "installation establishes its first valid run")
    var stale = accepted[1]; stale["runId"] = 8
    expect(capture.observe(["status": stale], at: 3) == nil
           && capture.snapshot().status?.runID == 7 && capture.snapshot().statusAt == 2,
           "a foreign run cannot replace the owned loading observation")
    _ = capture.observe(["status": accepted[1]], at: 4)
    expect(capture.snapshot().status?.ready == true && capture.snapshot().statusAt == 4
           && capture.snapshot().installedAt == 2, "the same run advances readiness without moving installation time")

    let outcomes: [(NativeStartupFinalOutcome, String, String, Int32, String?)] = [
        (.activated, "target-activated", "activated", 0, nil),
        (.ready, "startup-ready", "startup-ready", 0, nil),
        (.skipped, "startup-skipped", "skipped", 0, nil),
        (.partial(reason: "startup-interrupted"), "startup-interrupted", "partial", 2, "startup-interrupted"),
        (.behaviorNotProven(reason: "protocol-error"), "startup-failed", "behavior-not-proven", 1, "protocol-error")
    ]
    for (outcome, event, exitName, code, reason) in outcomes {
        expect(outcome.event == event && outcome.exitName == exitName && outcome.exitCode == code
               && outcome.reason == reason, "public outcome envelope agrees on event, exit name, code and reason")
    }
    var records: [[String: Any]] = []
    let stream = NativeStartupEventStream(writer: NativeEventWriter(
        startedAt: 0, launcherPID: 1, launcherPath: "/synthetic/launcher", sink: { records.append($0) }))
    expect(stream.finish(at: 0) == nil && records.isEmpty, "teardown before begin emits no fictitious startup")
    stream.begin(at: 1)
    expect(stream.resolve(.activated(pid: 0), observation: nil, at: 2)
           == .behaviorNotProven(reason: "target-identity"), "activation without a positive process identity refuses success")
    let final = stream.finish(at: 3)
    expect(stream.finish(at: 4) == final && records.count == 3,
           "repeated teardown preserves the refusal and emits exactly one exit")
    stream.targetOpened(pid: 701, at: 5); stream.startupInstalled(pid: 701, runID: 7, at: 6)
    stream.portError(operation: "bind", errno: 48, at: 7)
    expect(records.count == 3, "late host callbacks cannot append milestones after the launcher exit")

    expect(NativeEntryIdentity.host(bundleIdentifier: "local.azhou.codex-startup", declaredHost: "codex") == .codex,
           "explicit Codex declaration binds to its launcher identity")
    for declaration: Any in ["zcode", "unknown", 1, true] {
        expect(NativeEntryIdentity.host(bundleIdentifier: "local.azhou.codex-startup", declaredHost: declaration) == nil,
               "Codex entry refuses another host or non-string declaration")
    }
    expect(NativeEntryIdentity.host(bundleIdentifier: "other.launcher", declaredHost: "codex") == nil,
           "declaring Codex cannot authorize a different bundle")
    return checks
}

// File-scope test helper. In StartupNativeTests.main, before old tests:
// checks += zcodeTypedEventContractChecks()
@MainActor
private func zcodeTypedEventContractChecks() -> Int {
    var checks = 0
    func expect(_ value: @autoclosure () -> Bool, _ label: String) {
        guard value() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    func key(host: SkinHostID = .zcode, path: String = "/synthetic/ZCode.app",
             executable: String = "/synthetic/ZCode.app/Contents/MacOS/ZCode",
             identifier: String = "dev.zcode.app", version: String = "synthetic",
             build: String = "synthetic", hash: String = String(repeating: "a", count: 64)) -> HostApplicationKey {
        HostApplicationKey(host: host, bundleURL: URL(fileURLWithPath: path),
            executableURL: URL(fileURLWithPath: executable), bundleIdentifier: identifier,
            version: version, build: build, executableSHA256: hash)
    }
    let expected = key()
    let process = HostProcessGeneration(pid: 700, launchTime: 50, executableURL: expected.executableURL)
    let instance = "12345678-1234-4234-8234-123456789abc"
    let operation = UUID(uuidString: "abcdefab-1234-4234-9234-123456789abc")!
    let payload = String(repeating: "b", count: 64)
    let token = "synthetic-owned-context"
    let tokenSHA = SHA256.hash(data: Data(token.utf8)).map { String(format: "%02x", $0) }.joined()
    func receipt(application: HostApplicationKey? = nil, generation: HostProcessGeneration? = nil,
                 owner: String = "azhou-zcode-startup", version: Int = 1,
                 hash: String? = nil, context: String? = nil, controller: String? = nil) -> ControllerReceipt {
        ControllerReceipt(location: PageLocation(application: application ?? expected, process: generation ?? process,
                documentToken: context ?? token), owner: owner, protocolVersion: version,
            payloadSHA256: hash ?? payload, controllerInstanceID: controller ?? instance, createdByOperationID: operation)
    }
    func makeStream() -> (NativeStartupEventStream, () -> [[String: Any]]) {
        var records: [[String: Any]] = []
        let stream = NativeStartupEventStream(writer: NativeEventWriter(
            startedAt: 0, launcherPID: 1, launcherPath: "/synthetic/launcher", sink: { records.append($0) }))
        return (stream, { records })
    }
    func events(_ records: [[String: Any]]) -> [String] { records.map { $0["event"] as? String ?? "" } }
    func checkReceiptEvent(_ event: [String: Any], _ label: String) {
        expect(event["host"] as? String == "zcode" && event["evidence"] as? String == "typed-controller-receipt",
               "\(label) identifies typed ZCode evidence")
        expect(event["targetPID"] as? Int == 700 && event["runId"] as? Int == 7,
               "\(label) binds its observed process and run")
        expect(event["owner"] as? String == "azhou-zcode-startup" && event["version"] as? Int == 1
               && event["controllerInstanceID"] as? String == instance
               && event["createdByOperationID"] as? String == operation.uuidString
               && event["payloadSHA256"] as? String == payload,
               "\(label) retains verified controller metadata")
        expect(event["documentTokenSHA256"] as? String == tokenSHA && event["documentToken"] == nil,
               "\(label) hashes its context identity")
        expect(["phase", "completed", "completion", "overlay", "cause"].allSatisfy { event[$0] == nil },
               "\(label) does not invent lifecycle fields absent from the typed result")
    }

    // The original bug: a valid typed ZCode receipt must not require Codex capture.
    do {
        let (stream, records) = makeStream(); stream.begin(at: 1)
        expect(stream.resolveZCode(.ready(receipt(), runID: 7), expectedApplication: expected, at: 2) == .ready,
               "typed ZCode readiness succeeds without Codex startup capture or milestone history")
        expect(stream.finish(at: 3) == .ready, "typed readiness retains its successful final outcome")
        expect(events(records()) == ["launcher-start", "startup-ready", "launcher-exit"],
               "typed receipt finalization never fabricates target-opened or startup-installed history")
        checkReceiptEvent(records()[1], "ready")
        expect(records()[1]["ready"] as? Bool == true && records()[1]["beforeReady"] == nil,
               "ready reports readiness without inventing skip status")
        expect(records()[2]["exitCode"] as? Int == 0 && records()[2]["outcome"] as? String == "startup-ready",
               "typed readiness emits a successful launcher exit")
    }
    for acquisition: PageAcquisition in [.created, .alreadyActive] {
        for beforeReady in [false, true] {
            let (stream, records) = makeStream(); stream.begin(at: 1)
            let result = SkinLaunchResult.skipped(.present(.instance(receipt()), acquisition: acquisition),
                                                  runID: 7, beforeReady: beforeReady)
            expect(stream.resolveZCode(result, expectedApplication: expected, at: 2) == .skipped,
                   "confirmed typed skip accepts a created or already-active receipt")
            _ = stream.finish(at: 3)
            expect(events(records()) == ["launcher-start", "startup-skipped", "launcher-exit"],
                   "typed skip preserves only evidenced event history")
            checkReceiptEvent(records()[1], "skip")
            let acquisitionName: String
            switch acquisition { case .created: acquisitionName = "created"; case .alreadyActive: acquisitionName = "alreadyActive" }
            expect(records()[1]["beforeReady"] as? Bool == beforeReady
                   && records()[1]["acquisition"] as? String == acquisitionName && records()[1]["ready"] == nil,
                   "skip emits its typed timing and acquisition without a readiness claim")
            expect(records()[2]["exitCode"] as? Int == 0 && records()[2]["outcome"] as? String == "skipped",
                   "typed skip finalizes as successful skip")
        }
    }

    // Each malformed receipt is exercised as both ready and confirmed-present skip.
    let badProcesses = [
        HostProcessGeneration(pid: 0, launchTime: 50, executableURL: expected.executableURL),
        HostProcessGeneration(pid: -1, launchTime: 50, executableURL: expected.executableURL),
        HostProcessGeneration(pid: 700, launchTime: nil, executableURL: expected.executableURL),
        HostProcessGeneration(pid: 700, launchTime: .nan, executableURL: expected.executableURL),
        HostProcessGeneration(pid: 700, launchTime: .infinity, executableURL: expected.executableURL),
        HostProcessGeneration(pid: 700, launchTime: 0, executableURL: expected.executableURL),
        HostProcessGeneration(pid: 700, launchTime: -1, executableURL: expected.executableURL),
        HostProcessGeneration(pid: 700, launchTime: 50, executableURL: URL(fileURLWithPath: "/synthetic/foreign-executable"))
    ]
    var malformed: [(String, ControllerReceipt)] = [
        ("foreign owner", receipt(owner: "azhou-codex-startup")), ("unsupported version", receipt(version: 2)),
        ("empty context", receipt(context: "")), ("short instance", receipt(controller: "1234")),
        ("invalid UUID", receipt(controller: String(repeating: "g", count: 36))),
        ("UUID trailing newline", receipt(controller: instance + "\n")),
        ("short SHA", receipt(hash: String(repeating: "a", count: 63))),
        ("uppercase SHA", receipt(hash: String(repeating: "A", count: 64))),
        ("nonhex SHA", receipt(hash: String(repeating: "g", count: 64))),
        ("SHA trailing newline", receipt(hash: payload + "\n")),
        ("foreign host", receipt(application: key(host: .codex))),
        ("foreign bundle path", receipt(application: key(path: "/synthetic/Other.app"))),
        ("foreign executable key", receipt(application: key(executable: "/synthetic/other"))),
        ("foreign bundle ID", receipt(application: key(identifier: "foreign.app"))),
        ("foreign version", receipt(application: key(version: "other"))),
        ("foreign build", receipt(application: key(build: "other"))),
        ("foreign executable SHA", receipt(application: key(hash: String(repeating: "c", count: 64))))
    ]
    malformed += badProcesses.enumerated().map { ("invalid process \($0.offset)", receipt(generation: $0.element)) }
    func expectRefusal(_ result: SkinLaunchResult, expectedApplication: HostApplicationKey = expected, label: String) {
        let (stream, records) = makeStream(); stream.begin(at: 1)
        let outcome = stream.resolveZCode(result, expectedApplication: expectedApplication, at: 2)
        if case .behaviorNotProven? = outcome { checks += 1 }
        else { fatalError("FAILED: \(label) must refuse claimed success") }
        _ = stream.finish(at: 3)
        expect(events(records()) == ["launcher-start", "startup-failed", "launcher-exit"]
               && records().last?["exitCode"] as? Int == 1, "\(label) emits no success milestone")
    }
    for (label, malformedReceipt) in malformed {
        expectRefusal(.ready(malformedReceipt, runID: 7), label: label + " ready")
        expectRefusal(.skipped(.present(.instance(malformedReceipt), acquisition: .created), runID: 7, beforeReady: true),
                      label: label + " skipped")
    }
    for runID in [0, -1] {
        expectRefusal(.ready(receipt(), runID: runID), label: "nonpositive ready run")
        expectRefusal(.skipped(.present(.instance(receipt()), acquisition: .created), runID: runID, beforeReady: false),
                      label: "nonpositive skipped run")
    }
    let legacy = LegacyV1Observation(location: receipt().location, owner: "azhou-zcode-startup", protocolVersion: 1)
    for page: PageEffect in [.notObserved(reason: "unobserved"), .absent(receipt().location),
                            .unknown(operationID: operation, detail: "unknown"),
                            .present(.legacyV1(legacy), acquisition: .alreadyActive)] {
        expectRefusal(.skipped(page, runID: 7, beforeReady: false), label: "skip without confirmed instance receipt")
    }
    expectRefusal(.ready(receipt(application: key(host: .codex)), runID: 7), expectedApplication: key(host: .codex),
                  label: "matching Codex identity cannot use ZCode resolver")
    expectRefusal(.activated(process), expectedApplication: key(host: .codex), label: "Codex activation cannot use ZCode resolver")
    for invalid in badProcesses { expectRefusal(.activated(invalid), label: "invalid activated process") }
    do {
        let (stream, records) = makeStream(); stream.begin(at: 1)
        expect(stream.resolveZCode(.activated(process), expectedApplication: expected, at: 2) == .activated,
               "valid typed process activation succeeds")
        _ = stream.finish(at: 3)
        expect(events(records()) == ["launcher-start", "target-activated", "launcher-exit"]
               && records()[1]["targetPID"] as? Int == 700, "activation identifies its process without a controller claim")
    }

    let cleanup = CleanupReport(state: .notNeeded, released: [], intentionallyRetained: [], unconfirmed: [])
    let page = PageEffect.notObserved(reason: "synthetic no page")
    let failureCases: [(SkinLaunchResult, NativeStartupFinalOutcome)] = [
        (.partial(SkinOperationFailure(reason: .targetStale, detail: "startup-interrupted"), page: page, cleanup: cleanup),
         .partial(reason: "startup-interrupted")),
        (.partial(SkinOperationFailure(reason: .ownerConflict, detail: "startup-active"), page: page, cleanup: cleanup),
         .behaviorNotProven(reason: "startup-active")),
        (.failed(SkinOperationFailure(reason: .targetIdentity, detail: "target-identity"), page: page, cleanup: cleanup),
         .behaviorNotProven(reason: "target-identity")),
        (.failed(SkinOperationFailure(reason: .protocolError, detail: "private arbitrary detail"), page: page, cleanup: cleanup),
         .behaviorNotProven(reason: "protocol-error"))
    ]
    for (result, expectedOutcome) in failureCases {
        let (stream, records) = makeStream(); stream.begin(at: 1)
        expect(stream.resolveZCode(result, expectedApplication: expected, at: 2) == expectedOutcome,
               "typed failure keeps established partial/failure reason semantics")
        _ = stream.finish(at: 3)
        expect(records().last?["exitCode"] as? Int == Int(expectedOutcome.exitCode), "failure exit code agrees with its outcome")
    }
    for reason: HostRefusalReason in [.identityUnavailable, .identityMismatch, .capabilityUnverified,
                                      .evidenceMismatch, .implementationUnavailable, .capabilityUnsupported] {
        let refusal = HostRefusal(host: .zcode, reason: reason, findings: [], detail: "synthetic refusal", nextProbe: nil)
        let (stream, _) = makeStream(); stream.begin(at: 1)
        let foldedReason = [.identityUnavailable, .identityMismatch, .capabilityUnverified].contains(reason)
            ? "target-identity" : "protocol-error"
        expect(stream.resolveZCode(.refused(refusal), expectedApplication: expected, at: 2)
               == .behaviorNotProven(reason: foldedReason), "typed refusal preserves existing fixed reason folding")
    }
    for latchFailure in [false, true] {
        let (stream, records) = makeStream(); stream.begin(at: 1)
        stream.latchInterruption()
        if latchFailure { stream.latchFailure("asset-invalid") }
        let expectedOutcome: NativeStartupFinalOutcome = latchFailure
            ? .behaviorNotProven(reason: "asset-invalid") : .partial(reason: "startup-interrupted")
        expect(stream.resolveZCode(.ready(receipt(), runID: 7), expectedApplication: expected, at: 2) == expectedOutcome,
               "latched failure/interruption dominates a later typed ready result")
        _ = stream.finish(at: 3)
        expect(!events(records()).contains("startup-ready") && records().count == 3,
               "latched failure/interruption emits exactly one final result and exit")
    }
    do {
        let (stream, records) = makeStream()
        expect(stream.resolveZCode(.ready(receipt(), runID: 7), expectedApplication: expected, at: 0) == nil
               && records().isEmpty, "typed resolution before begin emits nothing")
        stream.begin(at: 1)
        expect(stream.resolveZCode(.ready(receipt(), runID: 7), expectedApplication: expected, at: 2) == .ready,
               "a begun typed stream can finalize once")
        expect(stream.resolveZCode(.activated(process), expectedApplication: expected, at: 3) == nil,
               "a later typed success cannot replace an earlier final result")
        expect(stream.resolve(.failed(reason: "asset-invalid"), observation: nil, at: 4) == nil,
               "legacy resolution cannot overwrite the typed final result")
        _ = stream.finish(at: 5)
        expect(stream.resolveZCode(.ready(receipt(), runID: 7), expectedApplication: expected, at: 6) == nil
               && stream.finish(at: 7) == .ready && records().count == 3,
               "post-exit typed callbacks and repeated finish cannot duplicate a final event")
    }
    do {
        let (stream, records) = makeStream(); stream.begin(at: 1)
        _ = stream.resolve(.failed(reason: "asset-invalid"), observation: nil, at: 2)
        expect(stream.resolveZCode(.ready(receipt(), runID: 7), expectedApplication: expected, at: 3) == nil,
               "typed resolution cannot erase an existing legacy failure")
        _ = stream.finish(at: 4)
        expect(events(records()) == ["launcher-start", "startup-failed", "launcher-exit"],
               "mixed callbacks retain the initial failure event")
    }
    // Exercise the actual App-owned exit adapter, not only the event resolver.
    // The fake runtime records termination and exit without opening a real App.
    let lifecycleCases: [(SkinLaunchResult, String, String, Int)] = [
        (.ready(receipt(), runID: 7), "startup-ready", "startup-ready", 0),
        (.skipped(.present(.instance(receipt()), acquisition: .alreadyActive), runID: 7, beforeReady: false),
         "startup-skipped", "skipped", 0),
        (.activated(process), "target-activated", "activated", 0),
        (.partial(SkinOperationFailure(reason: .operationCancelled, detail: "startup-interrupted"),
                  page: page, cleanup: cleanup), "startup-interrupted", "partial", 2),
        (.ready(receipt(owner: "foreign"), runID: 7), "startup-failed", "behavior-not-proven", 1)
    ]
    for (result, event, outcome, exitCode) in lifecycleCases {
        let runtime = FakeNativeAppRuntime(arguments: ["synthetic-ZCode-entry"])
        let delegate = AppDelegate(runtime: runtime)
        delegate.finishZCodeStartup(result, expectedApplication: expected, promoted: false)
        expect(runtime.terminated == 1, "typed App lifecycle requests exactly one termination for \(outcome)")
        delegate.finishZCodeStartup(.ready(receipt(), runID: 7), expectedApplication: expected, promoted: false)
        expect(runtime.terminated == 1, "a duplicate typed callback does not terminate twice or replace \(outcome)")
        delegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
        let output = runtime.output.compactMap { line -> [String: Any]? in
            guard let data = line.data(using: .utf8) else { return nil }
            return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        }
        expect(events(output) == ["launcher-start", event, "player-terminated", "launcher-exit"],
               "typed App lifecycle keeps one real event sequence for \(outcome)")
        expect(output.last?["outcome"] as? String == outcome && output.last?["exitCode"] as? Int == exitCode
               && runtime.processExitCode == Int32(exitCode),
               "willTerminate propagates the exact typed outcome and native exit code for \(outcome)")
        expect(runtime.openCount == 0 && runtime.allocationCount == 0 && runtime.openedEnvironments.isEmpty,
               "terminal result handling itself cannot open a host or create launch side effects")
    }
    return checks
}

// File-scope helper; add checks += zcodeRuntimeEventEnvelopeChecks() in main.
@MainActor
private func zcodeRuntimeEventEnvelopeChecks() -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        precondition(condition(), label); checks += 1
    }
    let runtime = FakeNativeAppRuntime(arguments: ["SYNTHETIC-EVENTS-ONLY"])
    runtime.bundleURL = URL(fileURLWithPath: "/tmp/synthetic-zcode-event-envelope/Azhou.app")
    let presentation = FakeNativePlayerPresentation()
    let delegate = AppDelegate(runtime: runtime, presentation: presentation)
    let port = 45678
    let hostPID = 700
    let hostBirth = 50.125
    let environmentKeys = ["HOME", "LANG", "PATH", "TMPDIR", "ZCODE_DATA_BASE_DIR", "ZCODE_DESKTOP_HOME_DIR",
                           "ZCODE_DESKTOP_SESSION_DATA_DIR", "ZCODE_DESKTOP_USER_DATA_DIR"]
    let request: [String: Any] = ["stage": "zcode-open-request", "debuggingPort": port,
        "entryPID": runtime.processIdentifier, "environmentKeys": environmentKeys, "host_is_not_native_child": true]
    let selected: [String: Any] = ["stage": "zcode-open-selected-process", "debuggingPort": port,
        "entryPID": runtime.processIdentifier, "hostPID": hostPID, "hostStartedAt": hostBirth,
        "native_child_wait_claim": false]
    runtime.uptime = 101
    delegate.emitZCodeRuntimeEvent(request)
    runtime.uptime = 100.5 // A regressing source clock must not regress envelope time.
    delegate.emitZCodeRuntimeEvent(selected)
    var overridden = request
    overridden.merge(["schema": "foreign.schema", "event": "startup-ready", "seconds": -100.0,
                      "launcherPID": -1, "launcherPath": "/synthetic/foreign-entry"]) { _, new in new }
    runtime.uptime = 103
    delegate.emitZCodeRuntimeEvent(overridden)

    let records = runtime.output.compactMap { line -> [String: Any]? in
        guard let data = line.data(using: .utf8) else { return nil }
        return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    }
    expect(records.count == 3 && runtime.output.count == 3,
           "each runtime diagnostic is emitted as one valid JSON record")
    let expectedPath = runtime.bundleURL.resolvingSymlinksInPath().standardizedFileURL.path
    expect(records.allSatisfy {
        $0["schema"] as? String == NativeEventWriter.schema && $0["event"] as? String == "zcode-runtime"
            && $0["launcherPID"] as? Int == runtime.processIdentifier && $0["launcherPath"] as? String == expectedPath
    }, "runtime request and selected process share the strict owner envelope and exact entry identity")
    expect(records.compactMap { $0["seconds"] as? Double } == [1, 1, 3],
           "runtime event elapsed seconds remain monotonic when the source clock moves backward")
    let envelope: Set<String> = ["schema", "event", "seconds", "launcherPID", "launcherPath"]
    expect(Set(records[0].keys) == Set(request.keys).union(envelope)
           && Set(records[1].keys) == Set(selected.keys).union(envelope),
           "the writer preserves actual runtime fieldsets without adding unsupported evidence")
    expect(records[0]["debuggingPort"] as? Int == port && records[1]["debuggingPort"] as? Int == port
           && records[0]["entryPID"] as? Int == runtime.processIdentifier
           && records[1]["entryPID"] as? Int == runtime.processIdentifier,
           "request and selection retain the same port and entry PID")
    expect(records[1]["hostPID"] as? Int == hostPID && records[1]["hostStartedAt"] as? Double == hostBirth,
           "selected process diagnostic preserves the actual host generation rather than the entry PID")
    expect(records[0]["environmentKeys"] as? [String] == environmentKeys
           && records[0]["host_is_not_native_child"] as? Bool == true
           && records[1]["native_child_wait_claim"] as? Bool == false,
           "launch request records isolation key names and selection never claims a native child wait")
    expect(records[2]["stage"] as? String == "zcode-open-request" && records[2]["debuggingPort"] as? Int == port
           && records[2]["schema"] as? String == NativeEventWriter.schema
           && records[2]["event"] as? String == "zcode-runtime" && records[2]["seconds"] as? Double == 3
           && records[2]["launcherPID"] as? Int == runtime.processIdentifier
           && records[2]["launcherPath"] as? String == expectedPath,
           "producer fields cannot overwrite the writer's schema, event, monotonic time or entry identity")
    expect(records.allSatisfy { record in
        ["ready", "completed", "completion", "outcome", "exitCode", "runId"].allSatisfy { record[$0] == nil }
    }, "request and selection diagnostics do not fabricate startup success, completion or finalization")
    expect(runtime.openCount == 0 && runtime.allocationCount == 0 && runtime.terminated == 0
           && runtime.activated == 0 && presentation.createdPlayers.isEmpty && presentation.evaluations.isEmpty,
           "emitting runtime evidence performs no application launch, port allocation, UI or shutdown action")

    let secret = "fixture-private-url?query=must-not-be-emitted"
    let allowedStartup = ["target-identity", "attach-timeout", "listener-mismatch", "endpoint-unavailable",
        "profile-isolation-unproven", "asset-invalid", "inspection-failed", "inspection-timeout", "protocol-error"]
    for reason in allowedStartup {
        expect(ZCodeNativeRuntime.diagnosticReason(for: StartupFailure(reason: reason, message: secret)) == reason,
               "known startup diagnostic retains only its fixed reason tag")
    }
    for reason in ["busy", "inspection-failed", "inspection-timeout"] {
        expect(ZCodeNativeRuntime.diagnosticReason(for: WallpaperFailure(state: reason, chinese: secret, english: secret)) == reason,
               "known operation diagnostic retains only its fixed state tag")
    }
    let cdpErrors: [(ZCodeBoundCDP.Failure, String)] = [
        (.deadline, "cdp-deadline"), (.cancelled, "cdp-cancelled"), (.busy, "cdp-busy"),
        (.identity, "cdp-identity"), (.protocolError, "cdp-protocol-error"), (.unavailable, "cdp-unavailable")
    ]
    for (error, reason) in cdpErrors {
        expect(ZCodeNativeRuntime.diagnosticReason(for: error) == reason,
               "CDP diagnostic identifies its bounded failure class")
    }
    expect(ZCodeNativeRuntime.diagnosticReason(for: CancellationError()) == "cancelled",
           "task cancellation remains a fixed diagnostic tag")
    for error: Error in [StartupFailure(reason: secret, message: secret),
                         WallpaperFailure(state: secret, chinese: secret, english: secret),
                         NSError(domain: secret, code: 17, userInfo: [NSLocalizedDescriptionKey: secret])] {
        expect(ZCodeNativeRuntime.diagnosticReason(for: error) == "unclassified",
               "unknown reasons, error domains and localized text cannot enter diagnostic fields")
    }
    final class DescriptionReads { var count = 0 }
    struct PrivateDiagnosticError: LocalizedError {
        let reads: DescriptionReads
        var errorDescription: String? { reads.count += 1; return "fixture-private-localized-description" }
    }
    let reads = DescriptionReads()
    expect(ZCodeNativeRuntime.diagnosticReason(for: PrivateDiagnosticError(reads: reads)) == "unclassified"
           && reads.count == 0, "classifying unknown errors never evaluates localized description")
    runtime.uptime = 104
    delegate.emitZCodeRuntimeEvent(["stage": "zcode-runtime-failed", "point": "open-proof",
                                   "reason": ZCodeNativeRuntime.diagnosticReason(for: StartupFailure(reason: "asset-invalid", message: secret))])
    let diagnostic = try! JSONSerialization.jsonObject(with: Data(runtime.output.last!.utf8)) as! [String: Any]
    expect(Set(diagnostic.keys) == envelope.union(["stage", "point", "reason"])
           && diagnostic["stage"] as? String == "zcode-runtime-failed"
           && diagnostic["point"] as? String == "open-proof" && diagnostic["reason"] as? String == "asset-invalid",
           "runtime failure diagnostic has exactly a fixed point and reason inside the strict envelope")
    expect(!runtime.output.last!.contains(secret) && diagnostic["event"] as? String == "zcode-runtime"
           && diagnostic["schema"] as? String == NativeEventWriter.schema,
           "private exception text never accompanies a fixed runtime failure diagnostic")

    // A renderer/runtime failure remains failure after the legacy bridge. The
    // diagnostic repair must never make an unknown detail into a successful run.
    let failure = SkinOperationFailure(reason: .protocolError, detail: "fixture-private-url?query=must-not-be-emitted")
    let typed = SkinLaunchResult.failed(failure, page: .notObserved(reason: "fixture"),
        cleanup: CleanupReport(state: .notNeeded, released: [], intentionallyRetained: [], unconfirmed: []))
    var finalRecords: [[String: Any]] = []
    let stream = NativeStartupEventStream(writer: NativeEventWriter(startedAt: 0, launcherPID: 1,
        launcherPath: "/synthetic/entry", sink: { finalRecords.append($0) }))
    stream.begin(at: 1)
    let expectedApplication = HostApplicationKey(host: .zcode,
        bundleURL: URL(fileURLWithPath: "/synthetic/ZCode.app"),
        executableURL: URL(fileURLWithPath: "/synthetic/ZCode.app/Contents/MacOS/ZCode"),
        bundleIdentifier: "dev.zcode.app", version: "synthetic", build: "synthetic",
        executableSHA256: String(repeating: "a", count: 64))
    expect(stream.resolveZCode(typed, expectedApplication: expectedApplication, at: 2)
           == .behaviorNotProven(reason: "protocol-error"),
           "fixed diagnostic reporting leaves the actual typed ZCode finalizer non-successful")
    _ = stream.finish(at: 3)
    expect(finalRecords.map { $0["event"] as? String ?? "" } == ["launcher-start", "startup-failed", "launcher-exit"]
           && finalRecords.last?["exitCode"] as? Int == 1
           && finalRecords[1]["reason"] as? String == "protocol-error",
           "the final generic failure remains sanitized and emits a nonzero exit")
    return checks
}

@MainActor
private func zcodeDriverInterleave(port: Int) async throws {
    let fixture = try ZCodeRuntimeFixture(port: port, pid: 987654319)
    defer { fixture.cleanup() }
    let capabilities = SkinCapability.allCases.map {
        CapabilityFinding(subject: CapabilityEvidenceSubject(application: fixture.key, surface: SkinHostContract.surface(for: $0), contractVersion: SkinHostContract.version),
            capability: $0, state: .verified, evidenceIDs: ["synthetic-only"], reason: "fixture")
    }
    let inputs = BoundHostInputs(identity: HostIdentityEvidence(key: fixture.key, signingIdentity: "synthetic", evidenceID: "synthetic-only"),
        findings: capabilities, contractVersion: SkinHostContract.version)
    let driver = ZCodeSkinDriver(inputs: inputs, assembly: fixture.assembly)
    func control(_ path: String, post: Bool = false) async throws -> [String:Any] {
        let cfg = URLSessionConfiguration.ephemeral;cfg.httpCookieStorage = nil;cfg.urlCredentialStorage = nil
        let session = URLSession(configuration: cfg);defer { session.invalidateAndCancel() }
        var req = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/fixture/" + path)!)
        req.httpMethod = post ? "POST" : "GET";req.timeoutInterval = 2
        let (data, response) = try await session.data(for: req)
        guard (response as? HTTPURLResponse)?.statusCode == 200, let value = try JSONSerialization.jsonObject(with: data) as? [String:Any] else { fatalError("synthetic gate failed") }
        return value
    }
    let launch = Task { await driver.launch(fixture.request) }
    let end = ProcessInfo.processInfo.systemUptime + 5
    while true {
        if try await control("frame-entered")["entered"] as? Bool == true { break }
        precondition(ProcessInfo.processInfo.systemUptime < end, "first attach did not reach gate")
        try await Task.sleep(nanoseconds: 20_000_000)
    }
    let inspect = await driver.inspect(SkinInspectRequest(expectedApplication: fixture.key, operationID: UUID(), deadline: 160, includePage: true, previousObservation: nil))
    var inspectBusy = false
    if case .staleTarget(let e) = inspect { inspectBusy = e.reason == .operationBusy }
    _ = try await control("release-frame", post: true)
    let launchResult = await launch.value
    var launchReady = false
    if case .ready = launchResult { launchReady = true }
    let checkLock = try fixture.assembly.acquireOperation(fixture.process.pid);checkLock.release()
    let expected = "safe"
    precondition(expected == "safe" ? (inspectBusy && launchReady) : (!inspectBusy && !launchReady), "interleaving did not match expected driver behavior")
    let output: [String:Any] = ["variant":expected,"inspectBusy":inspectBusy,"launchReady":launchReady,"lockReacquired":true,"realHost":false]
    print(String(decoding: try JSONSerialization.data(withJSONObject: output,options:.sortedKeys),as:UTF8.self))
}

// An executable transport fixture: production URLSession discovery, CDP codec,
// connector, install recorder and event capture; only HTTP/socket/host boundaries
// are synthetic. All document generations deliberately start at runID 1.
private final class StartupReplacementWorld: @unchecked Sendable {
    let stage: String
    let mode: String
    let handshakeStatus: Int?
    let href = "app://-/index.html?initialRoute=%2F"
    private let lock = NSLock()
    private var generation = 0
    private var statusCount = 0
    private var clock: TimeInterval = 1
    private var lockHeld = false
    private(set) var installs: [String: Int] = [:]
    private(set) var disposedControllers: [String] = []
    private(set) var installReplyTimes: [String: TimeInterval] = [:]
    private(set) var requests: [String] = []
    private(set) var requestIDs: [Int] = []
    private(set) var sockets: [StartupReplacementSocket] = []
    private(set) var lockAcquires = 0
    private(set) var lockReleases = 0
    private(set) var requestsLocked = true
    var cancel: (() -> Void)?
    private var lagReadsLeft = 0
    private var waitReads = 0
    private var recheckReads = 0
    init(stage: String, mode: String = "replace", handshakeStatus: Int? = nil) {
        self.stage = stage; self.mode = mode
        self.handshakeStatus = handshakeStatus ?? ["handshake-404": 404, "handshake-401": 401][mode]
        lagReadsLeft = mode.hasPrefix("lag-") ? Int(String(mode.dropFirst(4))) ?? 0 : 0
    }
    func time() -> TimeInterval { lock.lock(); defer { lock.unlock() }; return clock }
    func advance(_ seconds: TimeInterval) { lock.lock(); clock += seconds; lock.unlock() }
    func hasReplaced() -> Bool { lock.lock(); defer { lock.unlock() }; return generation > 0 }
    func recheckCount() -> Int { lock.lock(); defer { lock.unlock() }; return recheckReads }
    func acquire() { lock.lock(); lockAcquires += 1; lockHeld = true; lock.unlock() }
    func release() { lock.lock(); lockReleases += 1; lockHeld = false; lock.unlock() }
    func pages() throws -> [[String: Any]] {
        lock.lock(); defer { lock.unlock() }
        clock += 0.01
        func entry(_ id: String, type: String = "page", url: String? = nil) -> [String: Any] {
            ["id": id, "type": type, "url": url ?? href,
             "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/\(id)"]
        }
        if generation == 0 { return [entry("page-a")] }
        if mode.hasPrefix("recheck-") {
            recheckReads += 1
            let responseFailures = ["recheck-http401", "recheck-http503", "recheck-redirect", "recheck-foreign-url",
                                    "recheck-array", "recheck-json", "recheck-oversized"]
            if !responseFailures.contains(mode), recheckReads == 1 || mode == "recheck-permanent" {
                if mode == "recheck-cancel" { cancel?(); throw URLError(.cancelled) }
                let code: URLError.Code = mode == "recheck-lost" ? .networkConnectionLost
                    : mode == "recheck-connect" ? .cannotConnectToHost
                    : mode == "recheck-unknown" ? .badServerResponse : .timedOut
                throw URLError(code)
            }
            if mode == "recheck-page" { return [entry("page-b")] }
            if mode == "recheck-ambiguous" { return [entry("page-a"), entry("page-b")] }
            return [entry("page-a")]
        }
        if ["raw-unavailable", "complete-blip", "ready-blip"].contains(mode) { throw URLError(.badServerResponse) }
        if ["cancel-list", "cancel-ready-list"].contains(mode) { cancel?(); throw URLError(.cancelled) }
        if mode.hasPrefix("lag-"), generation > 0 {
            if lagReadsLeft > 0 { lagReadsLeft -= 1; return [entry("page-a"), entry("page-b")] }
            return [entry("page-b")]
        }
        if mode == "persist", generation > 0 { return [entry("page-a"), entry("page-b")] }
        if mode == "cancel-wait", generation > 0 {
            waitReads += 1
            if waitReads > 1 { cancel?(); throw URLError(.cancelled) }
            return [entry("page-a"), entry("page-b")]
        }
        switch mode {
        case "same-target": return [entry("page-a")]
        case "old-main": return [entry("page-a"), entry("page-b")]
        case "old-avatar": return [entry("page-a", url: "app://-/index.html?initialRoute=avatar"), entry("page-b")]
        case "old-worker": return [entry("page-a", type: "worker"), entry("page-b")]
        case "ambiguous": return [entry("page-b"), entry("page-c")]
        case "no-main": return [entry("worker", type: "worker")]
        case "missing-id": return [entry("page-b"), ["type": "worker", "url": href]]
        case "duplicate-id": return [entry("page-b"), entry("page-b", type: "worker")]
        case "invalid-id": return [entry("page-b"), entry("bad id", type: "worker")]
        case "socket-mismatch":
            var value = entry("page-b"); value["webSocketDebuggerUrl"] = "ws://127.0.0.1:49221/devtools/page/other"; return [value]
        case "foreign-socket":
            var value = entry("page-b"); value["webSocketDebuggerUrl"] = "ws://127.0.0.1:49222/devtools/page/page-b"; return [value]
        case "reuse": return [entry(generation > 1 ? "page-a" : "page-b")]
        default: return [entry(generation > 1 ? "page-c" : "page-b")]
        }
    }
    func socket(_ request: URLRequest) -> any WallpaperSocketTask {
        let socket = StartupReplacementSocket(id: request.url!.lastPathComponent, world: self)
        lock.lock(); sockets.append(socket); lock.unlock()
        return socket
    }
    func reply(id: String, request: [String: Any]) throws -> Data {
        lock.lock(); defer { lock.unlock() }
        clock += 0.01
        let params = request["params"] as? [String: Any] ?? [:]
        let expression = params["expression"] as? String ?? ""
        let boundDisposal = ((params["arguments"] as? [[String: Any]])?.first?["value"] as? Bool) == true
        let operation = request["method"] as? String == "Runtime.callFunctionOn" ? (boundDisposal ? "dispose" : "status")
            : expression == WallpaperTransport.controllerReferenceExpression ? "reference"
            : expression.contains("Promise.resolve((") ? "install"
            : expression == StartupConnector.inspectExpression ? "inspect"
            : expression == StartupConnector.statusExpression ? "status" : "dispose"
        requests.append("\(id):\(operation)"); requestIDs.append(request["id"] as? Int ?? -1)
        requestsLocked = requestsLocked && lockHeld
        // CDP Runtime.callFunctionOn has no execution timeout parameter. Its
        // independent client timer bounds the request, unlike Runtime.evaluate.
        if request["method"] as? String == "Runtime.callFunctionOn" {
            let allowed: Set<String> = ["functionDeclaration", "objectId", "arguments", "silent", "returnByValue", "generatePreview",
                "userGesture", "awaitPromise", "executionContextId", "objectGroup", "throwOnSideEffect", "uniqueContextId", "serializationOptions"]
            if !Set(params.keys).isSubset(of: allowed) {
                return try JSONSerialization.data(withJSONObject: ["id": request["id"]!, "error": ["code": -32602, "message": "Invalid parameters"]])
            }
        }
        if operation == "reference" {
            var remote: [String: Any] = ["type": "object", "objectId": "controller-" + id]
            if mode == "reference-null" { remote = ["type": "object", "subtype": "null"] }
            if mode == "reference-missing-id" { remote = ["type": "object"] }
            if mode == "reference-wrong-type" { remote = ["type": "string", "objectId": "controller-" + id] }
            if mode == "reference-large-id" { remote["objectId"] = String(repeating: "x", count: 1025) }
            return try JSONSerialization.data(withJSONObject: ["id": request["id"]!, "result": ["result": remote]])
        }
        if request["method"] as? String == "Runtime.callFunctionOn", params["objectId"] as? String != "controller-" + id {
            return try JSONSerialization.data(withJSONObject: ["id": request["id"]!, "error": ["code": -32000, "message": "foreign controller object"]])
        }
        if operation == "dispose" {
            let replaced = mode == "recheck-controller-http" && recheckReads > 1
            if !replaced { disposedControllers.append(id) }
            return try JSONSerialization.data(withJSONObject: ["id": request["id"]!, "result": ["result": ["value": ["disposed": !replaced]]]])
        }
        if operation == "install" { installs[id, default: 0] += 1 }
        if id == "page-a", operation == "status" { statusCount += 1 }
        let replaceNow = id == "page-a" && operation == stage && (stage != "status" || statusCount == 2)
            || id == "page-b" && operation == "install" && ["chain", "reuse"].contains(mode)
        func envelope(_ value: [String: Any]) -> [String: Any] {
            ["id": request["id"]!, "result": ["result": ["value": value]]]
        }
        func data(_ value: [String: Any]) throws -> Data { try JSONSerialization.data(withJSONObject: value) }
        var terminal: String?
        if replaceNow {
            generation += 1
            if handshakeStatus != nil { throw URLError(.badServerResponse) }
            if mode.hasPrefix("recheck-") { terminal = "ready-replaced" }
            else { switch mode {
            case "context-lost": return try data(["id": request["id"]!, "error": ["code": -32000, "message": "Execution context was destroyed."]])
            case "mixed-error": return try data(["id": request["id"]!, "error": ["code": -32000, "message": "Execution context was destroyed."], "result": ["exceptionDetails": [:]]])
            case "ordinary-cdp": return try data(["id": request["id"]!, "error": ["code": -32000, "message": "Unrelated protocol failure"]])
            case "js-exception": return try data(["id": request["id"]!, "result": ["exceptionDetails": [:]]])
            case "wrong-id": return try data(["id": 9999, "result": ["result": ["value": [:]]]])
            case "malformed-json": return Data("{".utf8)
            case "bad-install": return try data(envelope(["installed": true, "alreadyActive": "invalid"]))
            case "bad-status": return try data(envelope(["href": href, "missing": false, "status": ["owner": "foreign"]]))
            case "missing-controller": return try data(envelope(["href": href, "missing": true]))
            case "href-drift": return try data(envelope(["href": "app://-/index.html?initialRoute=settings", "missing": false]))
            case "cancel-task": withUnsafeCurrentTask { $0?.cancel() }; throw URLError(.networkConnectionLost)
            case "cancel-error": throw URLError(.cancelled)
            case "timeout-error": throw URLError(.timedOut)
            case "handshake-unknown": throw URLError(.badServerResponse)
            case "posix-loss": throw NSError(domain: NSPOSIXErrorDomain, code: Int(ECONNRESET))
            case "deadline": clock = 5; throw URLError(.networkConnectionLost)
            case "before-install": break
            case "cancel-ready-list": terminal = "ready-replaced"
            case "ready-replaced", "complete-replaced", "skip-replaced", "failed-replaced", "disposed-replaced", "run-drift": terminal = mode
            case "ready-blip", "recheck-once": terminal = "ready-replaced"
            case "complete-blip": terminal = "complete-replaced"
            default: throw URLError(.networkConnectionLost)
            } }
        }
        if mode.hasPrefix("recheck-"), generation > 0 { terminal = "ready-replaced" }
        let value: [String: Any]
        switch operation {
        case "inspect": value = ["href": href, "controllerPresent": id == "page-b" && mode == "already-present"]
        case "install":
            installReplyTimes[id] = clock
            value = mode == "missing-new-receipt" && id == "page-b" ? ["installed": "invalid"]
                : ["installed": true, "alreadyActive": id == "page-b" && mode == "already-active"]
        case "status":
            if mode.hasPrefix("recheck-"), recheckReads > 1 {
                if ["recheck-controller", "recheck-missing"].contains(mode) { return try data(envelope(["href": href, "missing": true])) }
                if mode == "recheck-href" { return try data(envelope(["href": "app://-/index.html?initialRoute=settings", "missing": false])) }
                if mode == "recheck-schema" { return try data(envelope(["href": href, "missing": false, "status": ["owner": "foreign"]])) }
                if mode == "recheck-complete" { terminal = "complete-replaced" }
                if mode == "recheck-skip" { terminal = "skip-replaced" }
                if mode == "recheck-failed" { terminal = "failed-replaced" }
                if mode == "recheck-disposed" { terminal = "disposed-replaced" }
                if mode == "recheck-run" { terminal = "run-drift" }
            }
            let timedOut = mode == "recheck-timeout" && recheckReads > 1
            let completed = ["complete-replaced", "skip-replaced"].contains(terminal ?? "")
            let failed = terminal == "failed-replaced"
            let disposed = terminal == "disposed-replaced"
            let ready = id != "page-a" || ["ready-replaced", "complete-replaced", "run-drift"].contains(terminal ?? "")
            let phase = timedOut ? "timeout" : failed ? "failed" : disposed ? "disposed" : completed ? "complete" : ready ? "playing" : "loading"
            let completion: Any = completed ? ["cause": terminal == "skip-replaced" ? "skip" : "natural",
                                                "beforeReady": terminal == "skip-replaced" && mode != "recheck-skip"] : NSNull()
            value = ["href": href, "missing": false, "status": [
                "owner": "azhou-codex-startup", "version": 1, "phase": phase, "runId": terminal == "run-drift" ? 2 : 1,
                "ready": ready, "completed": completed, "overlay": !completed && !failed && !disposed && !timedOut,
                "reason": timedOut ? "overlay-timeout" : failed ? "protocol-error" : "",
                "wallpaper": ["applied": false, "reason": "", "imageDecoded": false], "completion": completion
            ]]
        default: value = ["disposed": true]
        }
        return try data(envelope(value))
    }
}

private final class StartupReplacementSystem: StartupTargetSystem, StartupOperationLock {
    let world: StartupReplacementWorld
    init(_ world: StartupReplacementWorld) { self.world = world }
    func preflightBundle(_ bundle: URL, deadline: TimeInterval) throws {}
    func validate(_ target: StartupTargetFacts, deadline: TimeInterval) throws {
        if world.mode == "identity-drift" && world.hasReplaced()
            || world.mode == "recheck-identity" && world.recheckCount() > 0 {
            throw StartupFailure(reason: "target-identity", message: "synthetic process generation changed")
        }
    }
    func listeningPorts(_ target: StartupTargetFacts, deadline: TimeInterval) throws -> [Int] {
        (world.mode == "port-drift" && world.hasReplaced()
            || world.mode == "recheck-port" && world.recheckCount() > 0) ? [] : [49221]
    }
    func acquireOperationLock(pid: Int32) throws -> any StartupOperationLock { world.acquire(); return self }
    func release() { world.release() }
}

private final class StartupReplacementSocket: WallpaperSocketTask, @unchecked Sendable {
    let id: String
    let world: StartupReplacementWorld
    var maximumMessageSize = 0
    var response: URLResponse? {
        guard id == "page-a", let status = world.handshakeStatus else { return nil }
        return HTTPURLResponse(url: URL(string: "http://127.0.0.1:49221/devtools/page/\(id)")!,
            statusCode: status, httpVersion: nil, headerFields: nil)
    }
    private(set) var canceled = 0
    private var pending: [String: Any] = [:]
    var holdReference = false
    private let referenceLock = NSLock()
    private var heldReference: (CheckedContinuation<URLSessionWebSocketTask.Message, Never>, URLSessionWebSocketTask.Message)?
    var isHoldingReference: Bool { referenceLock.lock(); defer { referenceLock.unlock() }; return heldReference != nil }
    func releaseReference() {
        referenceLock.lock(); let held = heldReference; heldReference = nil; referenceLock.unlock()
        if let held { held.0.resume(returning: held.1) }
    }
    init(id: String, world: StartupReplacementWorld) { self.id = id; self.world = world }
    func resume() {}
    func send(_ message: URLSessionWebSocketTask.Message) async throws {
        guard case .string(let source) = message,
              let request = try JSONSerialization.jsonObject(with: Data(source.utf8)) as? [String: Any] else {
            throw URLError(.cannotParseResponse)
        }
        pending = request
    }
    func receive() async throws -> URLSessionWebSocketTask.Message {
        let reply = URLSessionWebSocketTask.Message.data(try world.reply(id: id, request: pending))
        if holdReference, (pending["params"] as? [String: Any])?["expression"] as? String == WallpaperTransport.controllerReferenceExpression {
            return await withCheckedContinuation { continuation in
                referenceLock.lock(); heldReference = (continuation, reply); referenceLock.unlock()
            }
        }
        return reply
    }
    func cancel(with closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) { canceled += 1 }
}

private final class StartupReplacementURLProtocol: URLProtocol {
    static var world: StartupReplacementWorld?
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        guard let world = Self.world, let url = request.url,
              url.absoluteString == "http://127.0.0.1:49221/json/list" else {
            client?.urlProtocol(self, didFailWithError: URLError(.badURL)); return
        }
        do {
            var body = try JSONSerialization.data(withJSONObject: world.pages())
            var status = 200
            var responseURL = url
            if world.hasReplaced() {
                if world.mode == "recheck-http401" { status = 401 }
                if world.mode == "recheck-http503" || world.mode == "recheck-controller-http" && world.recheckCount() > 1 { status = 503 }
                if world.mode == "recheck-redirect" { status = 302 }
                if world.mode == "recheck-foreign-url" { responseURL = URL(string: "http://127.0.0.1:49222/json/list")! }
                if world.mode == "recheck-array" { body = Data("{}".utf8) }
                if world.mode == "recheck-json" { body = Data("{".utf8) }
                if world.mode == "recheck-oversized" { body = Data(repeating: 32, count: 2 * 1024 * 1024) }
            }
            let response = HTTPURLResponse(url: responseURL, statusCode: status, httpVersion: nil,
                                           headerFields: ["Content-Type": "application/json"])!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: body)
            client?.urlProtocolDidFinishLoading(self)
        } catch { client?.urlProtocol(self, didFailWithError: error) }
    }
    override func stopLoading() {}
}

@MainActor
private func startupReplacementScenario(stage: String, mode: String = "replace",
                                        diagnostics enabled: Bool = false, handshakeStatus: Int? = nil) async throws -> [String: Any] {
    let world = StartupReplacementWorld(stage: stage, mode: mode, handshakeStatus: handshakeStatus)
    StartupReplacementURLProtocol.world = world
    defer { StartupReplacementURLProtocol.world = nil }
    var diagnosticRecords: [[String: Any]] = []
    if enabled { diagnosticRecords.reserveCapacity(16) }
    let task = Task { @MainActor () throws -> [String: Any] in
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StartupReplacementURLProtocol.self]
        let base = WallpaperTransport(session: URLSession(configuration: configuration), socketFactory: world.socket)
        let capture = NativeStartupCapture(targetPID: 4123)
        var records: [[String: Any]] = []
        let events = NativeStartupEventStream(writer: NativeEventWriter(startedAt: 0, launcherPID: 42,
            launcherPath: "/synthetic/Agent-Skin.app", now: world.time, sink: { records.append($0) }))
        events.begin(at: 0); events.targetOpened(pid: 4123, at: 0)
        let recorder = CodexInstallObservation()
        let transport = InstallObservingStartupTransport(
            base: NativeStartupEventTransport(base: base, capture: capture, events: events, now: world.time), recorder: recorder)
        let target = StartupTargetFacts(pid: 4123, bundle: URL(fileURLWithPath: "/synthetic/Codex.app"),
            executable: URL(fileURLWithPath: "/synthetic/Codex.app/Contents/MacOS/Codex"),
            bundleID: "com.openai.codex", launchTime: mode == "missing-launch" ? nil : 100)
        let outcome = await StartupConnector(target: target, expectedPort: 49221, system: StartupReplacementSystem(world),
            transport: transport, diagnostics: enabled ? { _, fields in diagnosticRecords.append(fields) } : nil,
            now: world.time, sleep: {
                world.advance($0)
                if mode == "recheck-cancel-wait", world.recheckCount() > 0 { withUnsafeCurrentTask { $0?.cancel() } }
            })
            .run(payload: "test-only-probe", deadline: 5)
        let observation = capture.snapshot()
        let final = events.resolve(outcome, observation: observation, at: world.time())
        return ["stage": stage, "mode": mode, "recovered": outcome == .ready(runID: 1) && final == .ready,
            "outcome": String(describing: outcome), "final": String(describing: final),
            "installs": world.installs, "installSentCount": recorder.installSentCount, "disposedControllers": world.disposedControllers,
            "requests": world.requests, "requestIDs": world.requestIDs,
            "connections": world.sockets.map(\.id), "socketCloses": world.sockets.map(\.canceled),
            "lockAcquires": world.lockAcquires, "lockReleases": world.lockReleases, "requestsLocked": world.requestsLocked,
            "currentPageID": observation.pageID ?? "", "installedAt": observation.installedAt ?? -1,
            "installReplyTimes": world.installReplyTimes,
            "installationPageIDs": records.filter { $0["event"] as? String == "startup-installed" }.compactMap { $0["pageTargetID"] as? String },
            "readyPageIDs": records.filter { $0["event"] as? String == "startup-ready" }.compactMap { $0["pageTargetID"] as? String },
            "events": records.map { $0["event"] as? String ?? "" }, "elapsed": world.time(),
            "diagnostics": diagnosticRecords, "recheckReads": world.recheckCount(),
            "host": false, "productionConnectorAndCodec": true]
    }
    world.cancel = { task.cancel() }
    return try await task.value
}

@MainActor
private func startupPageReplacementProbe() async throws -> [[String: Any]] {
    var results: [[String: Any]] = []
    for stage in ["inspect", "install", "status"] { results.append(try await startupReplacementScenario(stage: stage)) }
    return results
}

@MainActor
private func startupControllerBindingChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: controller generation: \(label)") }; checks += 1
    }
    let world = StartupReplacementWorld(stage: "never")
    var held: StartupReplacementSocket?
    let transport = WallpaperTransport(session: nil, socketFactory: { request in
        let socket = world.socket(request) as! StartupReplacementSocket
        if request.url?.lastPathComponent == "page-a" { socket.holdReference = true; held = socket }
        return socket
    })
    defer { transport.close() }
    try transport.connect(to: URL(string: "ws://127.0.0.1:49221/devtools/page/page-a")!, timeout: 5)
    let old = Task { () -> String in
        do { _ = try await transport.evaluate(StartupConnector.statusExpression, timeout: 5); return "accepted" }
        catch is CancellationError { return "cancelled" }
        catch { return "other-error" }
    }
    let until = ProcessInfo.processInfo.systemUptime + 1
    while held?.isHoldingReference != true, ProcessInfo.processInfo.systemUptime < until {
        try await Task.sleep(nanoseconds: 1_000_000)
    }
    expect(held?.isHoldingReference == true, "the original controller capture is genuinely suspended")
    transport.disconnectPage()
    try transport.connect(to: URL(string: "ws://127.0.0.1:49221/devtools/page/page-b")!, timeout: 5)
    held?.releaseReference()
    let outcome = await old.value
    expect(outcome == "cancelled" && world.requests == ["page-a:reference"],
           "a late A capture cannot commit its object ID or issue a request on B")
    let result = try await transport.evaluate(StartupConnector.statusExpression, timeout: 5)
    expect((result["status"] as? [String: Any])?["ready"] as? Bool == true
        && world.requests == ["page-a:reference", "page-b:reference", "page-b:status"],
        "B performs its own fresh capture and uses only B's object ID")
    let disposed = try await transport.disposeController(href: world.href, timeout: 5)
    expect(disposed["disposed"] as? Bool == true && world.disposedControllers == ["page-b"],
        "cleanup after rebinding reaches only the newly bound controller")
    transport.close()
    let afterClose = try await transport.disposeController(href: world.href, timeout: 5)
    expect(afterClose["disposed"] as? Bool == false && world.disposedControllers == ["page-b"],
        "closed transports retain no cleanup authority")

    let openingWorld = StartupReplacementWorld(stage: "never")
    var openingTransport: WallpaperTransport?
    var interruptOpening = true
    let opening = WallpaperTransport(session: nil, socketFactory: { request in
        let socket = openingWorld.socket(request)
        if interruptOpening { interruptOpening = false; openingTransport?.disconnectPage() }
        return socket
    })
    openingTransport = opening
    defer { opening.close() }
    var openingCancelled = false
    do { try opening.connect(to: URL(string: "ws://127.0.0.1:49221/devtools/page/page-a")!, timeout: 5) }
    catch is CancellationError { openingCancelled = true }
    expect(openingCancelled && openingWorld.sockets.first?.canceled == 1,
        "invalidation while a socket is opening cancels the unpublished candidate")
    try opening.connect(to: URL(string: "ws://127.0.0.1:49221/devtools/page/page-b")!, timeout: 5)
    let fresh = try await opening.evaluate(StartupConnector.statusExpression, timeout: 5)
    expect((fresh["status"] as? [String: Any])?["ready"] as? Bool == true
        && openingWorld.requests == ["page-b:reference", "page-b:status"],
        "the next connection remains usable after interrupted socket creation")
    return checks
}

@MainActor
private func startupPageReplacementChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: page replacement: \(label)") }; checks += 1
    }
    func common(_ r: [String: Any]) {
        expect(r["lockAcquires"] as? Int == 1 && r["lockReleases"] as? Int == 1 && r["requestsLocked"] as? Bool == true,
               "one operation lock covers every generation")
        expect((r["socketCloses"] as? [Int] ?? []).allSatisfy { $0 == 1 }, "every socket closes once")
        let ids = r["requestIDs"] as? [Int] ?? []
        expect(ids == Array(1...max(1, ids.count)), "request IDs remain monotonic across sockets")
        let installs = r["installs"] as? [String: Int] ?? [:]
        expect(installs.values.allSatisfy { $0 == 1 }, "each target receives at most one installation")
        expect(r["installSentCount"] as? Int == installs.values.reduce(0, +), "cumulative sent evidence is never reset")
    }
    for stage in ["inspect", "install", "status"] {
        let r = try await startupReplacementScenario(stage: stage); common(r)
        let installs = r["installs"] as? [String: Int] ?? [:]
        expect(r["recovered"] as? Bool == true && installs["page-b"] == 1 && installs["page-a", default: 0] == (stage == "inspect" ? 0 : 1),
               "\(stage) resumes on a proven new target")
        expect(r["readyPageIDs"] as? [String] == ["page-b"] && r["currentPageID"] as? String == "page-b",
               "ready belongs only to B")
        expect(r["installedAt"] as? Double == (r["installReplyTimes"] as? [String: Double])?["page-b"],
               "B must supply its own installation timestamp")
        expect(r["installationPageIDs"] as? [String] == (stage == "status" ? ["page-a", "page-b"] : ["page-b"]),
               "identical run IDs never merge document evidence")
        expect(!(r["requests"] as? [String] ?? []).contains("page-a:dispose"), "dead page cleanup never reaches the replacement")
    }
    let refusals = ["same-target", "old-main", "old-avatar", "old-worker", "ambiguous", "no-main", "missing-id", "duplicate-id",
        "invalid-id", "socket-mismatch", "foreign-socket", "raw-unavailable", "missing-launch", "identity-drift", "port-drift",
        "ordinary-cdp", "mixed-error", "handshake-401", "handshake-unknown", "js-exception", "wrong-id", "malformed-json", "timeout-error", "cancel-error", "deadline"]
    for mode in refusals {
        let r = try await startupReplacementScenario(stage: mode == "handshake-401" ? "inspect" : "install", mode: mode); common(r)
        expect(r["recovered"] as? Bool == false && r["connections"] as? [String] == ["page-a"], "\(mode) cannot authorize replacement")
    }
    for stage in ["inspect", "install", "status"] {
        let r = try await startupReplacementScenario(stage: stage, mode: "cancel-task"); common(r)
        expect(r["outcome"] as? String == "partial(reason: \"startup-interrupted\")" && r["connections"] as? [String] == ["page-a"],
               "cancellation during \(stage) never reconnects")
    }
    for mode in ["cancel-list", "cancel-ready-list", "bad-install", "bad-status", "missing-controller", "href-drift", "run-drift", "complete-replaced", "skip-replaced", "failed-replaced", "disposed-replaced"] {
        let r = try await startupReplacementScenario(stage: mode == "bad-install" ? "install" : "status", mode: mode); common(r)
        expect(r["recovered"] as? Bool == false && r["connections"] as? [String] == ["page-a"], "\(mode) remains terminal")
    }
    // A temporary discovery transport error does not invalidate an already-owned
    // ready controller. Recovery still needs a fresh same-page list and status.
    for mode in ["recheck-once", "recheck-lost", "recheck-connect", "recheck-complete"] {
        let r = try await startupReplacementScenario(stage: "status", mode: mode, diagnostics: true); common(r)
        let requests = r["requests"] as? [String] ?? []
        expect(r["recovered"] as? Bool == true && r["connections"] as? [String] == ["page-a"]
            && !requests.contains("page-a:dispose") && r["installs"] as? [String: Int] == ["page-a": 1],
            "one timed-out ready proof must recover on the same page without disposal or installation replay")
        expect(requests.filter { $0 == "page-a:reference" }.count == 1
            && requests.filter { $0 == "page-a:status" }.count == 3 && r["recheckReads"] as? Int == 3,
            "successful proof waits re-read exactly the retained controller before declaring readiness")
        let diagnostic = (r["diagnostics"] as? [[String: Any]])?.first
        let code = mode == "recheck-lost" ? -1005 : mode == "recheck-connect" ? -1004 : -1001
        expect(diagnostic?["stage"] as? String == "recheck-wait" && diagnostic?["errorDomain"] as? String == NSURLErrorDomain
            && diagnostic?["errorCode"] as? Int == code && diagnostic?["httpStatus"] == nil,
            "list diagnostics preserve only the actual transport domain and code")
    }
    let permanent = try await startupReplacementScenario(stage: "status", mode: "recheck-permanent"); common(permanent)
    expect(permanent["outcome"] as? String == "failed(reason: \"attach-timeout\")"
        && (permanent["elapsed"] as? Double ?? 6) <= 5 && (permanent["recheckReads"] as? Int ?? 0) > 1
        && permanent["connections"] as? [String] == ["page-a"], "permanent failure consumes only the original deadline")
    for mode in ["recheck-http401", "recheck-http503", "recheck-redirect", "recheck-foreign-url",
                 "recheck-array", "recheck-json", "recheck-oversized", "recheck-unknown"] {
        let r = try await startupReplacementScenario(stage: "status", mode: mode, diagnostics: true); common(r)
        expect(r["outcome"] as? String == "failed(reason: \"protocol-error\")" && r["recheckReads"] as? Int == 1
            && r["connections"] as? [String] == ["page-a"], "\(mode) cannot become a transient retry")
        if mode == "recheck-http503" {
            expect((r["diagnostics"] as? [[String: Any]])?.first?["httpStatus"] as? Int == 503,
                "a rejected HTTP response retains its actual status without a response body")
        }
    }
    for mode in ["recheck-controller", "recheck-missing", "recheck-href", "recheck-run", "recheck-disposed", "recheck-page",
                 "recheck-cancel", "recheck-cancel-wait"] {
        let r = try await startupReplacementScenario(stage: "status", mode: mode); common(r)
        expect(r["outcome"] as? String == "partial(reason: \"startup-interrupted\")"
            && r["connections"] as? [String] == ["page-a"] && r["installs"] as? [String: Int] == ["page-a": 1]
            && !(r["requests"] as? [String] ?? []).contains("page-a:dispose"),
            "\(mode) never replays or disposes a changed controller while waiting for same-page proof")
    }
    for (mode, reason) in [("recheck-identity", "target-identity"), ("recheck-port", "listener-mismatch"),
                           ("recheck-ambiguous", "ambiguous-main-page"), ("recheck-timeout", "overlay-timeout"),
                           ("recheck-failed", "protocol-error"), ("recheck-schema", "protocol-error")] {
        let r = try await startupReplacementScenario(stage: "status", mode: mode); common(r)
        expect(r["outcome"] as? String == "failed(reason: \"\(reason)\")"
            && r["connections"] as? [String] == ["page-a"] && r["installs"] as? [String: Int] == ["page-a": 1],
            "\(mode) cannot reuse the earlier ready snapshot")
    }
    let waitedSkip = try await startupReplacementScenario(stage: "status", mode: "recheck-skip"); common(waitedSkip)
    expect(waitedSkip["outcome"] as? String == "skipped(runID: 1, beforeReady: false)"
        && !(waitedSkip["requests"] as? [String] ?? []).contains("page-a:dispose"), "a fresh skip after waiting remains terminal")
    let unboundFailure = try await startupReplacementScenario(stage: "install", mode: "bad-install"); common(unboundFailure)
    expect(unboundFailure["outcome"] as? String == "failed(reason: \"protocol-error\")"
        && unboundFailure["disposedControllers"] as? [String] == []
        && !(unboundFailure["requests"] as? [String] ?? []).contains("page-a:dispose"),
        "failure before object binding cannot capture the current global merely for cleanup")
    let swappedFailure = try await startupReplacementScenario(stage: "status", mode: "recheck-controller-http"); common(swappedFailure)
    expect(swappedFailure["outcome"] as? String == "failed(reason: \"protocol-error\")"
        && swappedFailure["disposedControllers"] as? [String] == []
        && (swappedFailure["requests"] as? [String] ?? []).filter { $0 == "page-a:reference" }.count == 1,
        "a failed list after a controller swap cannot acquire or dispose the new object")
    for mode in ["reference-null", "reference-missing-id", "reference-wrong-type", "reference-large-id"] {
        let r = try await startupReplacementScenario(stage: "status", mode: mode); common(r)
        expect(r["outcome"] as? String == "failed(reason: \"protocol-error\")"
            && r["connections"] as? [String] == ["page-a"] && r["disposedControllers"] as? [String] == []
            && !(r["requests"] as? [String] ?? []).contains("page-a:dispose"),
            "\(mode) cannot bind a controller or fall back to disposing the current global")
    }
    for mode in ["complete-blip", "ready-blip"] {
        let r = try await startupReplacementScenario(stage: "status", mode: mode); common(r)
        let requests = r["requests"] as? [String] ?? []
        if mode == "complete-blip" {
            expect(r["outcome"] as? String == "partial(reason: \"startup-interrupted\")"
                && !requests.contains("page-a:dispose") && r["connections"] as? [String] == ["page-a"],
                "a transient completed-checkpoint recheck failure stays terminal without disposal or reconnection")
        } else {
            expect(r["outcome"] as? String == "failed(reason: \"protocol-error\")"
                && requests.contains("page-a:dispose") && r["connections"] as? [String] == ["page-a"],
                "a transient pre-completion recheck failure stays a strict disposal failure")
        }
    }
    for stage in ["inspect", "install", "status"] {
        let r = try await startupReplacementScenario(stage: stage, mode: "lag-1"); common(r)
        expect(r["recovered"] as? Bool == true && r["connections"] as? [String] == ["page-a", "page-b"]
            && (r["installs"] as? [String: Int])?["page-b"] == 1,
            "\(stage) recovers once delayed inventory removal proves the old target absent")
        expect((r["diagnostics"] as? [[String: Any]])?.isEmpty == true,
            "\(stage) stays diagnostic-silent unless the invocation opts in")
    }
    let lagging = try await startupReplacementScenario(stage: "install", mode: "lag-3"); common(lagging)
    expect(lagging["recovered"] as? Bool == true && (lagging["installs"] as? [String: Int])?["page-b"] == 1,
        "repeated delayed inventory reads keep waiting within the shared budget")
    let persistent = try await startupReplacementScenario(stage: "install", mode: "persist"); common(persistent)
    expect(persistent["outcome"] as? String == "failed(reason: \"attach-timeout\")"
        && persistent["connections"] as? [String] == ["page-a"]
        && (persistent["installs"] as? [String: Int])?["page-b"] == nil,
        "a never-absent old target refuses at the exhausted budget without reaching the candidate")
    let cancelWait = try await startupReplacementScenario(stage: "install", mode: "cancel-wait"); common(cancelWait)
    expect(cancelWait["outcome"] as? String == "partial(reason: \"startup-interrupted\")"
        && cancelWait["connections"] as? [String] == ["page-a"],
        "cancellation inside the proof wait never reconnects")
    let malformedInventory = try await startupReplacementScenario(stage: "install", mode: "duplicate-id"); common(malformedInventory)
    expect(malformedInventory["outcome"] as? String == "failed(reason: \"protocol-error\")",
        "malformed inventory still refuses immediately")
    let exhausted = try await startupReplacementScenario(stage: "install", mode: "deadline"); common(exhausted)
    expect(exhausted["outcome"] as? String == "failed(reason: \"attach-timeout\")",
        "an exhausted budget still refuses without a proof read")
    let observed = try await startupReplacementScenario(stage: "install", mode: "lag-1", diagnostics: true); common(observed)
    let diagnosticRecords = (observed["diagnostics"] as? [[String: Any]]) ?? []
    let allowedKeys: Set<String> = ["stage", "at", "page", "errorDomain", "errorCode", "httpStatus", "pageConnectionLost", "state",
                                    "oldIDPresent", "eligibleMains", "uniqueIDs"]
    var serializedDiagnostics = ""
    for record in diagnosticRecords {
        serializedDiagnostics += String(decoding: try JSONSerialization.data(withJSONObject: record), as: UTF8.self)
    }
    expect(observed["recovered"] as? Bool == true
        && !diagnosticRecords.isEmpty
        && diagnosticRecords.allSatisfy { Set($0.keys).isSubset(of: allowedKeys) }
        && !serializedDiagnostics.contains("test-only-probe"),
        "opt-in diagnostics stay bounded and content-free")
    let proofs = diagnosticRecords.filter { ($0["stage"] as? String) == "proof" }
    expect(proofs.count == 2 && (proofs[0]["oldIDPresent"] as? Bool) == true
        && (proofs[0]["eligibleMains"] as? Int) == 2 && (proofs[0]["uniqueIDs"] as? Bool) == true
        && (proofs[1]["oldIDPresent"] as? Bool) == false && (proofs[1]["eligibleMains"] as? Int) == 1,
        "proof diagnostics record the lagging read and the proven replacement inventory")
    let recover = diagnosticRecords.first { ($0["stage"] as? String) == "install" }
    expect(recover?["page"] as? String == "page-a" && (recover?["pageConnectionLost"] as? Bool) == true
        && recover?["errorDomain"] as? String == NSURLErrorDomain
        && recover?["errorCode"] as? Int == URLError.networkConnectionLost.rawValue
        && recover?["httpStatus"] == nil,
        "the qualifying failure preserves its original stage and network identity")
    expect(!StartupDiagnosticsPolicy.isEnabled(environment: [:])
        && !StartupDiagnosticsPolicy.isEnabled(environment: [StartupDiagnosticsPolicy.environmentKey: "0"])
        && !StartupDiagnosticsPolicy.isEnabled(environment: ["UNRELATED": "1"])
        && StartupDiagnosticsPolicy.isEnabled(environment: [StartupDiagnosticsPolicy.environmentKey: "1"]),
        "startup diagnostics stay disabled unless the invocation opts in exactly")
    for (status, accepted) in [(404, true), (500, true), (401, false), (503, false)] {
        let r = try await startupReplacementScenario(stage: "inspect", diagnostics: true, handshakeStatus: status); common(r)
        expect(r["recovered"] as? Bool == accepted
            && r["connections"] as? [String] == (accepted ? ["page-a", "page-b"] : ["page-a"]),
            "handshake \(status) changes only candidate qualification, not independent replacement proof")
        let diagnostic = (r["diagnostics"] as? [[String: Any]])?.first { $0["stage"] as? String == "inspect" }
        expect(diagnostic?["errorDomain"] as? String == NSURLErrorDomain
            && diagnostic?["errorCode"] as? Int == -1011 && diagnostic?["httpStatus"] as? Int == status
            && diagnostic?["pageConnectionLost"] as? Bool == accepted,
            "handshake diagnostics preserve original NSError identity, status and inspect stage")
    }
    for mode in ["persist", "ambiguous", "duplicate-id", "identity-drift", "port-drift", "cancel-wait"] {
        let r = try await startupReplacementScenario(stage: "inspect", mode: mode, handshakeStatus: 500); common(r)
        expect(r["recovered"] as? Bool == false && r["connections"] as? [String] == ["page-a"]
            && (r["installs"] as? [String: Int])?["page-b"] == nil,
            "HTTP 500 never bypasses \(mode) proof refusal or cancellation")
        if mode == "persist" {
            expect(r["outcome"] as? String == "failed(reason: \"attach-timeout\")"
                && (r["elapsed"] as? Double ?? 0) >= 5 && (r["elapsed"] as? Double ?? 99) <= 5.1,
                "HTTP 500 with a still-live old ID only consumes the original bounded proof budget")
        }
    }
    for stage in ["inspect", "install", "status"] {
        let r = try await startupReplacementScenario(stage: stage, diagnostics: true); common(r)
        let diagnostic = (r["diagnostics"] as? [[String: Any]])?.first { $0["pageConnectionLost"] as? Bool == true }
        expect(diagnostic?["stage"] as? String == stage && diagnostic?["errorDomain"] as? String == NSURLErrorDomain
            && diagnostic?["errorCode"] as? Int == -1005 && diagnostic?["httpStatus"] == nil,
            "each transport failure keeps its originating \(stage) instead of relabeling it recover")
    }
    let posix = try await startupReplacementScenario(stage: "install", mode: "posix-loss", diagnostics: true); common(posix)
    let posixRecord = (posix["diagnostics"] as? [[String: Any]])?.first { $0["pageConnectionLost"] as? Bool == true }
    expect(posixRecord?["errorDomain"] as? String == NSPOSIXErrorDomain
        && posixRecord?["errorCode"] as? Int == Int(ECONNRESET) && posixRecord?["httpStatus"] == nil,
        "non-HTTP transport failures preserve numeric provenance without inventing status")
    for mode in ["context-lost", "posix-loss", "handshake-404", "before-install", "ready-replaced", "chain"] {
        let stage = ["before-install", "handshake-404"].contains(mode) ? "inspect" : mode == "ready-replaced" ? "status" : "install"
        let r = try await startupReplacementScenario(stage: stage, mode: mode); common(r)
        expect(r["recovered"] as? Bool == true, "\(mode) requires the same replacement proof")
    }
    for mode in ["already-present", "already-active", "missing-new-receipt", "reuse"] {
        let r = try await startupReplacementScenario(stage: mode == "missing-new-receipt" ? "status" : "install", mode: mode); common(r)
        expect(r["recovered"] as? Bool == false && r["connections"] as? [String] == ["page-a", "page-b"],
               "\(mode) cannot invent ownership or reinstall a retired ID")
        if mode == "already-present" {
            expect((r["installs"] as? [String: Int])?["page-b"] == nil, "pre-existing B controller is preserved")
        }
        if mode == "missing-new-receipt" {
            expect(r["installedAt"] as? Double == -1 && (r["readyPageIDs"] as? [String])?.isEmpty == true,
                   "missing B receipt cannot inherit A's evidence")
        }
    }
    let valid: [String: Any] = ["owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": 1,
        "ready": true, "completed": false, "overlay": true, "reason": "",
        "wallpaper": ["applied": false, "reason": "", "imageDecoded": false], "completion": NSNull()]
    let capture = NativeStartupCapture(targetPID: 4123)
    capture.bindPage("page-a")
    _ = capture.observe(["installed": true, "alreadyActive": false], at: 1, pageID: "page-a")
    _ = capture.observe(["status": valid], at: 2, pageID: "page-a")
    let oldObservation = capture.snapshot()
    capture.bindPage("page-b")
    _ = capture.observe(["installed": true, "alreadyActive": false], at: 3, pageID: "page-a")
    _ = capture.observe(["status": valid], at: 4, pageID: "page-a")
    _ = capture.observe(["status": valid], at: 5, pageID: "page-b")
    expect(capture.snapshot().installedAt == nil && capture.snapshot().status == nil,
           "late A responses and B status without B installation are discarded")
    _ = capture.observe(["installed": true, "alreadyActive": false], at: 6, pageID: "page-b")
    _ = capture.observe(["status": valid], at: 7, pageID: "page-b")
    expect(capture.snapshot().installedAt == 6 && capture.snapshot().pageID == "page-b", "B establishes fresh capture evidence")
    let stream = NativeStartupEventStream(writer: NativeEventWriter(startedAt: 0, launcherPID: 42,
        launcherPath: "/synthetic/Agent-Skin.app", sink: { _ in }))
    expect(!stream.bindPage(pid: 4123, pageID: "page-a"), "dormant event stream cannot authorize page binding")
    stream.begin(at: 0); stream.targetOpened(pid: 4123, at: 0)
    expect(stream.bindPage(pid: 4123, pageID: "page-a"), "first page binding is accepted")
    stream.startupInstalled(pid: 4123, runID: 1, at: 1, pageID: "page-a")
    expect(stream.bindPage(pid: 4123, pageID: "page-b"), "replacement invalidates the old installation")
    stream.startupInstalled(pid: 4123, runID: 1, at: 2, pageID: "page-a")
    stream.startupInstalled(pid: 4123, runID: 1, at: 6, pageID: "page-b")
    expect(stream.resolve(.ready(runID: 1), observation: oldObservation, at: 8) == .behaviorNotProven(reason: "protocol-error"),
           "same PID and run ID cannot make an old-page observation satisfy new-page readiness")
    return checks
}


#if AGENT_SKIN_NATIVE_EVENT_TESTS
@MainActor
private final class IdentityDiagnosticApplication: NativeApplication {
    let mode: String
    let expectedBundle: URL
    let expectedExecutable: URL
    var postOpenMode = ""
    private(set) var reads: [String] = []
    init(mode: String, bundle: URL, executable: URL) {
        self.mode = mode; expectedBundle = bundle; expectedExecutable = executable
    }
    var processIdentifier: Int32 { reads.append("pid"); return mode == "invalid-pid" ? -1 : 4123 }
    var bundleIdentifier: String? {
        reads.append("bundleID")
        if mode == "callback-id-missing" || postOpenMode == "id-missing" { return nil }
        return mode == "callback-id-mismatch" ? "fixture.other" : "com.openai.codex"
    }
    var bundleURL: URL? {
        reads.append("bundle")
        if mode == "callback-bundle-missing" || postOpenMode == "bundle-missing"
            || (mode == "callback-bundle-vanishes" && reads.filter { $0 == "bundle" }.count > 1) { return nil }
        return mode == "callback-bundle-mismatch" ? URL(fileURLWithPath: "/private/identity-private-other.app") : expectedBundle
    }
    var executableURL: URL? {
        reads.append("executable")
        if mode == "callback-executable-missing" || postOpenMode == "executable-missing" { return nil }
        return mode == "facts-executable-mismatch" ? URL(fileURLWithPath: "/private/identity-private-binary") : expectedExecutable
    }
    var launchTime: TimeInterval? {
        reads.append("launchTime")
        return ["no-launch-time", "no-launch-time-or-date"].contains(mode) ? nil : 123.456
    }
    var isTerminated: Bool { reads.append("terminated"); return mode == "callback-terminated" || postOpenMode == "terminated" }
    var isActive: Bool { false }
    var isHidden: Bool { false }
    func activate() -> Bool { fatalError("identity diagnostics must never activate the host") }
}

private final class IdentityDiagnosticEnvironment: @unchecked Sendable {
    let mode: String
    let bundle: URL
    let executable: URL
    private(set) var probes: [String] = []
    private var bundleReads = 0
    private var processReads = 0
    private var psReads = 0
    private var time: TimeInterval = 101
    init(_ mode: String) {
        self.mode = mode
        let path = mode == "invalid-extension" ? "/private/identity-private"
            : mode == "nested-app" ? "/private/identity-private.app/Inner.app"
            : "/private/identity-private.app"
        bundle = URL(fileURLWithPath: path)
        executable = bundle.appendingPathComponent("Contents/MacOS/Fixture")
    }
    func environment() -> CodexTargetEnvironment {
        CodexTargetEnvironment(
            mainBundleURL: mode == "launcher-bundle" ? bundle : URL(fileURLWithPath: "/private/launcher.app"),
            bundleFacts: { [self] _ in
                bundleReads += 1; probes.append("bundle:\(bundleReads)")
                if (mode == "bundle-facts-missing" && bundleReads == 1)
                    || (mode == "signature-bundle-missing" && bundleReads == 2) { return nil }
                let identifier: String? = mode == "package-id-missing" ? nil
                    : mode == "package-id-mismatch" || (mode == "signature-id-mismatch" && bundleReads == 2)
                        ? "fixture.other" : "com.openai.codex"
                let binary: URL? = mode == "package-executable-missing" ? nil
                    : mode == "package-executable-outside" ? URL(fileURLWithPath: "/private/identity-private-binary") : executable
                return CodexBundleFacts(identifier: identifier, executableURL: binary)
            },
            processFacts: { [self] pid in
                processReads += 1; probes.append("process:\(processReads)")
                if (mode == "fresh-process-missing" && processReads == 1)
                    || (mode == "revalidate-process-missing" && processReads == 2) { return nil }
                if mode == "ps-budget-timeout" && processReads == 2 { time = 200 }
                let identifier: String? = mode == "fresh-id-missing" ? nil
                    : mode == "fresh-id-mismatch" ? "fixture.other" : "com.openai.codex"
                let processBundle: URL? = mode == "fresh-bundle-missing" ? nil
                    : mode == "fresh-bundle-mismatch" ? URL(fileURLWithPath: "/private/identity-private-other.app") : bundle
                let binary: URL? = mode == "fresh-executable-missing" ? nil
                    : mode == "fresh-executable-mismatch" ? URL(fileURLWithPath: "/private/identity-private-binary") : executable
                let date: Date? = ["fresh-launch-missing", "no-launch-time-or-date"].contains(mode) ? nil
                    : Date(timeIntervalSince1970: mode == "fresh-launch-mismatch"
                           || (mode == "revalidate-launch-mismatch" && processReads == 2)
                           || (mode == "post-signature-launch-mismatch" && processReads == 3) ? 124.456 : 123.456)
                return CodexProcessFacts(processIdentifier: pid, isTerminated: mode == "fresh-terminated",
                                         bundleIdentifier: identifier, bundleURL: processBundle,
                                         executableURL: binary, launchDate: date)
            },
            runningProcesses: { _ in fatalError("identity validation must not enumerate or open the host") },
            isExecutableFile: { [self] _ in probes.append("executable"); return mode != "not-executable" },
            runCommand: { [self] file, _, timeout, _ in
                probes.append("command:\(file):\(timeout)")
                if file == "/bin/ps" {
                    psReads += 1
                    if mode == "ps-nserror" { throw NSError(domain: "IdentityFixture", code: 71, userInfo: [NSLocalizedDescriptionKey: "identity-private-message"]) }
                    if mode == "ps-inspection-failed" { throw WallpaperFailure(state: "inspection-failed", chinese: "identity-private-message", english: "identity-private-message") }
                    if mode == "signature-budget-timeout" { time = 200 }
                    if mode == "ps-field-count" { return "identity-private-output" }
                    if mode == "ps-uid-missing" { return "invalid \(executable.path)" }
                    if mode == "ps-uid-mismatch" { return "502 \(executable.path)" }
                    if mode == "ps-executable-mismatch" { return "501 /private/identity-private-other" }
                    return "501 \(executable.path)"
                }
                precondition(file == "/usr/bin/codesign", "identity fixture must not probe listeners")
                if mode == "signature-nserror" { throw NSError(domain: "IdentityFixture", code: 72, userInfo: [NSLocalizedDescriptionKey: "identity-private-signature", NSFilePathErrorKey: "/private/identity-private-file"]) }
                if mode == "signature-inspection-timeout" || mode == "signature-inspection-failed" {
                    throw WallpaperFailure(state: mode == "signature-inspection-timeout" ? "inspection-timeout" : "inspection-failed",
                                           chinese: "identity-private-message", english: "identity-private-message")
                }
                return ""
            },
            currentUID: { [self] in probes.append("uid"); return 501 },
            now: { [self] in time })
    }
}

@MainActor
private func startupIdentityDiagnosticChecks() async throws -> Int {
    var checks = 0
    func expect(_ value: @autoclosure () -> Bool, _ label: String) {
        guard value() else { fatalError("FAILED: identity diagnostics: \(label)") }
        checks += 1
    }
    let allowed: Set<String> = ["stage", "checkpoint", "at", "pid", "pidObserved", "outcome", "errorDomain", "errorCode", "state", "reason",
                               "beforeDeadline", "callbackErrorPresent", "applicationPresent", "notTerminated", "bundlePresent", "executablePresent",
                               "bundleIDPresent", "bundleMatches", "bundleIDMatches", "executableMatches", "launchTimePresent", "pidValid", "appExtensionMatches",
                               "differentFromLauncher", "notNestedApp", "bundleFactsPresent", "executableInsideBundle", "executableFile", "processPresent",
                               "expectedLaunchTimePresent", "observedLaunchTimePresent", "launchTimeMatches", "launchTimeAccepted", "fieldCountMatches", "uidPresent", "uidMatches"]
    func contentFree(_ records: [[String: Any]]) throws {
        for record in records {
            expect(Set(record.keys).isSubset(of: allowed), "diagnostics expose only the fixed identity schema")
            expect(record["stage"] as? String == "target-identity" && record["at"] is TimeInterval,
                   "every identity record has a fixed stage and its sampled monotonic time")
            let text = String(decoding: try JSONSerialization.data(withJSONObject: record), as: UTF8.self)
            expect(!text.contains("identity-private") && !text.contains("file://") && !text.contains("/bin/") && !text.contains("/Applications/"),
                   "paths, ps output, command text and arbitrary error descriptions never enter the sink")
        }
    }
    func expanded(_ record: [String: Any]) -> [[String: Any]] {
        guard let records = record["checks"] as? [[String: Any]] else { return [record] }
        expect(Set(record.keys) == ["stage", "checkpoint", "at", "checks"]
               && record["stage"] as? String == "target-identity"
               && record["checkpoint"] as? String == "bounded-open" && record["at"] is TimeInterval,
               "one bounded-open envelope carries only the fixed metadata and actual observations")
        expect(!records.isEmpty && records.count <= 11, "the finite validation path keeps its diagnostic batch bounded")
        return records
    }
    struct Observation {
        let reason: String
        let reads: [String]
        let probes: [String]
        let records: [[String: Any]]
    }
    func observe(_ mode: String, enabled: Bool) async throws -> Observation {
        let fixture = IdentityDiagnosticEnvironment(mode)
        let application = IdentityDiagnosticApplication(mode: mode, bundle: fixture.bundle, executable: fixture.executable)
        let runtime = FakeNativeAppRuntime(arguments: ["identity fixture"])
        runtime.openedApplication = mode == "callback-missing" ? nil : application
        if mode == "callback-error" { runtime.openError = NSError(domain: "IdentityFixture", code: 70, userInfo: [NSLocalizedDescriptionKey: "identity-private-open"]) }
        if mode == "callback-deadline" { runtime.beforeOpenCompletion = { runtime.uptime = 200 } }
        var records: [[String: Any]] = []
        var emittedProbeCounts: [Int] = []
        var emittedGetterCounts: [Int] = []
        let sink: ((String, [String: Any]) -> Void)? = enabled ? { event, fields in
            precondition(event == "startup-diagnostic")
            emittedProbeCounts.append(fixture.probes.count)
            emittedGetterCounts.append(application.reads.count)
            records.append(contentsOf: expanded(fields))
        } : nil
        let system: any StartupTargetSystem = CodexStartupTargetSystem(environment: fixture.environment())
        let reason: String
        do {
            let result = try await AppDelegate.openTargetApplication(
                runtime: runtime, targetBundleID: "com.openai.codex", url: fixture.bundle,
                port: 9333, deadline: 200, system: system, log: { _, _ in }, diagnostics: sink)
            expect(result === application, "the unchanged bounded open returns exactly its callback object")
            reason = "ready"
        } catch let failure as StartupFailure { reason = failure.reason }
        expect(runtime.openCount == 1 && runtime.terminated == 0 && runtime.activated == 0,
               "observations do not add opens, activation, termination or retries")
        if enabled {
            expect(emittedProbeCounts == [fixture.probes.count] && emittedGetterCounts == [application.reads.count],
                   "diagnostic I/O occurs exactly once, after all callback identity decisions and host probes finish")
        } else { expect(records.isEmpty, "off means no identity records") }
        try contentFree(records)
        return Observation(reason: reason, reads: application.reads, probes: fixture.probes, records: records)
    }
    let cases: [(String, String, String, String, Bool)] = [
        ("valid", "ready", "callback-identity", "bundleMatches", true),
        ("callback-bundle-vanishes", "ready", "callback-identity", "bundlePresent", true),
        ("no-launch-time", "ready", "launch-time", "expectedLaunchTimePresent", false),
        ("no-launch-time-or-date", "ready", "process-facts", "expectedLaunchTimePresent", false),
        ("callback-missing", "target-identity", "callback-identity", "applicationPresent", false),
        ("callback-terminated", "target-identity", "callback-identity", "notTerminated", false),
        ("callback-bundle-missing", "target-identity", "callback-identity", "bundlePresent", false),
        ("callback-executable-missing", "target-identity", "callback-identity", "executablePresent", false),
        ("callback-id-missing", "target-identity", "callback-identity", "bundleIDPresent", false),
        ("callback-bundle-mismatch", "target-identity", "callback-identity", "bundleMatches", false),
        ("callback-id-mismatch", "target-identity", "callback-identity", "bundleIDMatches", false),
        ("callback-error", "target-missing", "callback-identity", "callbackErrorPresent", true),
        ("callback-deadline", "attach-timeout", "callback-identity", "beforeDeadline", false),
        ("invalid-pid", "target-identity", "target-input", "pidValid", false),
        ("invalid-extension", "target-identity", "target-input", "appExtensionMatches", false),
        ("launcher-bundle", "target-identity", "target-input", "differentFromLauncher", false),
        ("nested-app", "target-identity", "target-input", "notNestedApp", false),
        ("bundle-facts-missing", "target-identity", "target-input", "bundleFactsPresent", false),
        ("package-id-missing", "target-identity", "target-input", "bundleIDPresent", false),
        ("package-id-mismatch", "target-identity", "target-input", "bundleIDMatches", false),
        ("package-executable-missing", "target-identity", "target-input", "executablePresent", false),
        ("package-executable-outside", "target-identity", "target-input", "executableInsideBundle", false),
        ("not-executable", "target-identity", "target-input", "executableFile", false),
        ("fresh-process-missing", "target-identity", "process-facts-initial", "processPresent", false),
        ("fresh-terminated", "target-identity", "process-facts-initial", "notTerminated", false),
        ("fresh-id-missing", "target-identity", "process-facts-initial", "bundleIDPresent", false),
        ("fresh-id-mismatch", "target-identity", "process-facts-initial", "bundleIDMatches", false),
        ("fresh-bundle-missing", "target-identity", "process-facts-initial", "bundlePresent", false),
        ("fresh-bundle-mismatch", "target-identity", "process-facts-initial", "bundleMatches", false),
        ("fresh-executable-missing", "target-identity", "process-facts-initial", "executablePresent", false),
        ("fresh-executable-mismatch", "target-identity", "process-facts-initial", "executableMatches", false),
        ("fresh-launch-missing", "target-identity", "launch-time", "observedLaunchTimePresent", false),
        ("fresh-launch-mismatch", "target-identity", "launch-time", "launchTimeMatches", false),
        ("revalidate-process-missing", "target-identity", "process-facts", "processPresent", false),
        ("revalidate-launch-mismatch", "target-identity", "process-facts", "launchTimeAccepted", false),
        ("post-signature-launch-mismatch", "target-identity", "process-facts", "launchTimeAccepted", false),
        ("ps-field-count", "target-identity", "ps-identity", "fieldCountMatches", false),
        ("ps-uid-missing", "target-identity", "ps-identity", "uidPresent", false),
        ("ps-uid-mismatch", "target-identity", "ps-identity", "uidMatches", false),
        ("ps-executable-mismatch", "target-identity", "ps-identity", "executableMatches", false),
        ("facts-executable-mismatch", "target-identity", "system-target-input", "executableMatches", false),
        ("signature-bundle-missing", "target-identity", "signature", "bundleFactsPresent", false),
        ("signature-id-mismatch", "target-identity", "signature", "bundleIDMatches", false),
    ]
    for (mode, expectedReason, checkpoint, field, value) in cases {
        let off = try await observe(mode, enabled: false)
        let on = try await observe(mode, enabled: true)
        expect(off.reason == expectedReason && on.reason == off.reason, "opt-in leaves success/refusal unchanged for \(mode)")
        expect(on.reads == off.reads && on.probes == off.probes, "identity getters and actual host-boundary probe order/count stay unchanged for \(mode)")
        expect(on.records.contains { $0["checkpoint"] as? String == checkpoint && $0[field] as? Bool == value },
               "the actual rejecting/accepting predicate is distinguishable for \(mode)")
        let callback = on.records.first { $0["checkpoint"] as? String == "callback-identity" }!
        if on.reads.contains("pid") {
            expect(callback["pid"] as? Int32 == (mode == "invalid-pid" ? -1 : 4123) && callback["pidObserved"] as? Bool == true,
                   "PID comes only from the facts constructed after callback guards")
        } else {
            expect(callback["pid"] == nil && callback["pidObserved"] as? Bool == false,
                   "an early refusal never samples an unvisited PID just for logging")
        }
        if mode == "callback-bundle-missing" {
            expect(on.reads == ["terminated", "bundle"] && callback["executablePresent"] == nil && callback["bundleMatches"] == nil,
                   "unvisited short-circuit predicates stay absent rather than looking missing or mismatched")
        }
        if mode == "fresh-process-missing" {
            expect(on.probes == ["bundle:1", "executable", "process:1"],
                   "a missing initial process snapshot is never re-probed for diagnosis")
        }
        if mode == "valid" {
            expect(on.reads == ["terminated", "bundle", "executable", "bundleID", "pid", "launchTime"],
                   "callback diagnostic taps consume the original getter order exactly once")
            expect(on.probes == ["bundle:1", "executable", "process:1", "process:2", "command:/bin/ps:2.0", "uid", "bundle:2", "command:/usr/bin/codesign:12.0", "process:3", "command:/bin/ps:2.0", "uid"],
                   "production validation through the existential still performs its original three snapshots/two ps/one signature checks")
        }
    }
    let failures: [(String, String, String, String?, Int?)] = [
        ("ps-nserror", "target-identity", "ps-identity", nil, 71),
        ("ps-inspection-failed", "target-identity", "ps-identity", "inspection-failed", nil),
        ("ps-budget-timeout", "attach-timeout", "ps-identity", nil, nil),
        ("signature-budget-timeout", "attach-timeout", "signature", nil, nil),
        ("signature-nserror", "target-identity", "signature", nil, 72),
        ("signature-inspection-timeout", "attach-timeout", "signature", "inspection-timeout", nil),
        ("signature-inspection-failed", "target-identity", "signature", "inspection-failed", nil),
    ]
    for (mode, expectedReason, checkpoint, state, code) in failures {
        let off = try await observe(mode, enabled: false)
        let on = try await observe(mode, enabled: true)
        expect(off.reason == expectedReason && on.reason == off.reason && on.reads == off.reads && on.probes == off.probes,
               "throwing checkpoint leaves error mapping and all probe counts unchanged for \(mode)")
        let record = on.records.first { $0["checkpoint"] as? String == checkpoint && $0["outcome"] as? String == "error" }!
        if let state { expect(record["state"] as? String == state, "original fixed WallpaperFailure state survives at \(checkpoint)") }
        if let code { expect(record["errorDomain"] as? String == "IdentityFixture" && record["errorCode"] as? Int == code,
                             "raw NSError identity survives before outer failure mapping") }
        if mode == "signature-nserror" || mode == "signature-inspection-failed" {
            expect(on.records.last?["state"] as? String == "signature-refused", "signature diagnostics distinguish the raw command failure from its existing public mapping")
        }
    }
    // Default protocol forwarding keeps fake/custom target systems on their exact
    // existing validate path; it must not swallow production dynamic dispatch.
    let typedErrors: [Error] = [StartupFailure(reason: "attach-timeout", message: "identity-private-timeout"),
                               WallpaperFailure(state: "inspection-timeout", chinese: "identity-private", english: "identity-private"),
                               WallpaperFailure(state: "target-changed", chinese: "identity-private", english: "identity-private"),
                               NSError(domain: "IdentityFixture", code: 73, userInfo: [NSLocalizedDescriptionKey: "identity-private"])]
    for (index, error) in typedErrors.enumerated() {
        let runtime = FakeNativeAppRuntime(arguments: ["identity fixture"])
        let fixture = IdentityDiagnosticEnvironment("valid")
        runtime.openedApplication = IdentityDiagnosticApplication(mode: "valid", bundle: fixture.bundle, executable: fixture.executable)
        let system = FakeStartupSystem(expectedPID: 4123, ports: [])
        system.validationError = error
        var records: [[String: Any]] = []
        do {
            _ = try await AppDelegate.openTargetApplication(runtime: runtime, targetBundleID: "com.openai.codex", url: fixture.bundle,
                                                           port: 9333, deadline: 200, system: system, log: { _, _ in },
                                                           diagnostics: { _, record in records.append(contentsOf: expanded(record)) })
            fatalError("typed validation failure must still reject")
        } catch let failure as StartupFailure {
            expect(failure.reason == (index < 2 ? "attach-timeout" : "target-identity"), "all existing bounded-open typed error mappings stay fixed")
        }
        expect(system.validatedPIDs == [4123] && records.last?["checkpoint"] as? String == "system-validation",
               "default overload forwards once and the catch identifies its own checkpoint")
        try contentFree(records)
    }
    // The callback may have complete facts while the next, independently used
    // post-open snapshot does not. Never overwrite the earlier observation.
    for mode in ["", "bundle-missing", "executable-missing", "id-missing", "terminated"] {
        for enabled in [false, true] {
            let fixture = IdentityDiagnosticEnvironment("valid")
            let application = IdentityDiagnosticApplication(mode: "callback-bundle-vanishes", bundle: fixture.bundle, executable: fixture.executable)
            let runtime = FakeNativeAppRuntime(arguments: ["identity fixture"]); runtime.openedApplication = application
            let system = FakeStartupSystem(expectedPID: 4123, ports: [])
            var records: [[String: Any]] = []
            let sink: ((String, [String: Any]) -> Void)? = enabled ? { _, record in records.append(contentsOf: expanded(record)) } : nil
            _ = try await AppDelegate.openTargetApplication(runtime: runtime, targetBundleID: "com.openai.codex", url: fixture.bundle,
                                                           port: 9333, deadline: 200, system: system, log: { _, _ in }, diagnostics: sink)
            // Use a separate application for the non-bundle predicates so the
            // original short-circuit order is tested at every post-open field.
            let postApplication = mode.isEmpty || mode == "bundle-missing" ? application
                : IdentityDiagnosticApplication(mode: "valid", bundle: fixture.bundle, executable: fixture.executable)
            postApplication.postOpenMode = mode
            let delegate = AppDelegate(runtime: runtime, presentation: FakeNativePlayerPresentation())
            do {
                _ = try delegate.startupFacts(postApplication, diagnostics: sink, at: 102)
                fatalError("post-open missing identity must still reject")
            } catch let failure as StartupFailure { expect(failure.reason == "target-identity", "post-open disappearance keeps its existing refusal") }
            if enabled {
                let callback = records.first { $0["checkpoint"] as? String == "callback-identity" }!
                let post = records.last!
                expect(callback["outcome"] as? String == "accepted" && callback["bundlePresent"] as? Bool == true
                       && post["checkpoint"] as? String == "post-open-facts" && post["outcome"] as? String == "rejected",
                       "later field loss is distinguished from the successful callback snapshot")
                expect(post["pid"] == nil && post["pidObserved"] as? Bool == false && post["at"] as? TimeInterval == 102,
                       "post-open refusal records only observed predicates at its own time")
                try contentFree(records)
            } else { expect(records.isEmpty, "post-open diagnostics also remain opt-in") }
        }
    }
    let fixture = IdentityDiagnosticEnvironment("no-launch-time")
    let application = IdentityDiagnosticApplication(mode: "no-launch-time", bundle: fixture.bundle, executable: fixture.executable)
    var postRecords: [[String: Any]] = []
    var clockReads = 0
    func clock() -> TimeInterval { clockReads += 1; return 102 }
    let delegate = AppDelegate(runtime: FakeNativeAppRuntime(arguments: ["identity fixture"]),
                               presentation: FakeNativePlayerPresentation())
    let offFacts = try delegate.startupFacts(application, at: clock())
    expect(clockReads == 0 && offFacts.launchTime == nil, "disabled diagnostic does not evaluate even its clock autoclosure")
    let onFacts = try delegate.startupFacts(application, diagnostics: { _, record in postRecords.append(record) }, at: clock())
    expect(clockReads == 1 && onFacts.pid == offFacts.pid && onFacts.bundle == offFacts.bundle && onFacts.executable == offFacts.executable
           && onFacts.bundleID == offFacts.bundleID && onFacts.launchTime == nil,
           "accepted post-open facts stay identical and absent launch time remains allowed")
    expect(postRecords.count == 1 && postRecords[0]["pid"] as? Int32 == 4123 && postRecords[0]["launchTimePresent"] as? Bool == false,
           "accepted post-open diagnostic uses its constructed facts")
    try contentFree(postRecords)
    let scopeFixture = IdentityDiagnosticEnvironment("valid")
    let scopedSystem: any StartupTargetSystem = CodexStartupTargetSystem(environment: scopeFixture.environment())
    let facts = StartupTargetFacts(pid: 4123, bundle: scopeFixture.bundle, executable: scopeFixture.executable,
                                   bundleID: "com.openai.codex", launchTime: 123.456)
    var scopedRecords: [[String: Any]] = []
    try scopedSystem.validate(facts, deadline: 200, diagnostics: { _, record in scopedRecords.append(record) })
    let count = scopedRecords.count
    try scopedSystem.validate(facts, deadline: 200)
    try scopedSystem.validate(facts, deadline: 200, diagnostics: nil)
    expect(count > 0 && scopedRecords.count == count, "the diagnostic environment copy never leaks its sink into later validations")
    let wrongFacts = StartupTargetFacts(pid: 4123, bundle: scopeFixture.bundle, executable: scopeFixture.executable,
                                        bundleID: "fixture.other", launchTime: nil)
    do {
        try scopedSystem.validate(wrongFacts, deadline: 200, diagnostics: { _, record in scopedRecords.append(record) })
        fatalError("a wrong target ID must still reject before any process probe")
    } catch let failure as StartupFailure { expect(failure.reason == "target-identity", "system target-input guard is unchanged") }
    expect(scopedRecords.last?["checkpoint"] as? String == "system-target-input"
           && scopedRecords.last?["bundleIDMatches"] as? Bool == false,
           "direct system input refusal gets its own content-free predicate")
    try contentFree(scopedRecords)
    return checks
}
#endif
