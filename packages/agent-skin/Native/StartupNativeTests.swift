// Compile separately from the application; fake host operations never launch or kill Codex.
// python3 -B tools/test-startup-native.py
import Foundation
import Darwin
import AppKit
import WebKit

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
    var startupTargetSystem: (any StartupTargetSystem)?
    var startupTransportFactory: ((NativeStartupCapture, NativeStartupEventStream) -> any StartupTransport)?
    var lockBusy = false
    var lockError: Int32?
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
    func application(processIdentifier: Int32) -> (any NativeApplication)? {
        applications.first { $0.processIdentifier == processIdentifier }
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
                "disposeExpression": try StartupConnector.disposeExpression(href),
                "installExpression": try StartupConnector.installExpression("({installed:true})", expectedHref: href),
            ]
            let bytes = try JSONSerialization.data(withJSONObject: expressions, options: [.sortedKeys])
            guard let text = String(data: bytes, encoding: .utf8) else { fatalError("unit expressions are not UTF-8") }
            print(text)
            return
        }

        var checks = 0
        func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
            guard condition() else { fatalError("FAILED: \(label)") }
            checks += 1
        }
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
        expect(successfulTransport.pagesCount == 2, "a temporarily unavailable page list is retried within the shared budget")
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
        let disposalExpression = malformedStatusTransport.disposeExpressions.first ?? ""
        expect(disposalExpression.contains("location.href !==")
               && disposalExpression.contains("owner?.value !== 'azhou-codex-startup'")
               && disposalExpression.contains("version?.value !== 1"),
               "cleanup is guarded by the inspected document URL and exact controller owner/version")

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
        checks += try await nativeEventContractChecks()
        checks += try await skinHostContractChecks()
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
    private(set) var disposeExpressions: [String] = []
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
            disposeExpressions.append(expression)
        }
        afterEvaluation?(expression, index)
        if !evaluationResponses.isEmpty {
            lastEvaluation = evaluationResponses.removeFirst()
            return lastEvaluation!
        }
        return repeatLastEvaluation ? lastEvaluation ?? [:] : [:]
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
