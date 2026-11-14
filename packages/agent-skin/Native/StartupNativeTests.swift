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

private final class ConcurrentTimeoutFixture: @unchecked Sendable {
    let item = DispatchWorkItem {}
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
    private(set) var nativeStartupInputs: [NativeStartupBridgeInput?] = []
    private(set) var loadedPlayers: [(URL, URL)] = []
    var evaluationResult: (Any?, Error?) = ("{}", nil)
    var snapshotResult: (NSImage?, Error?) = (nil, nil)
    var nativeCoverCount = 0
    var coldRevealCount = 0
    var coverValid = true
    var coverHook: ((String) -> Void)?
    weak var nativeHandler: NativeColdPlayer?
    var evaluationHook: ((String) -> (Any?, Error?))?
    func showColdCover(locale: NativeDisplayLocale, runNonce: String, delegate: NSWindowDelegate) throws -> NativeCoverReceipt {
        nativeCoverCount += 1
        nativeHandler = delegate as? NativeColdPlayer
        coverHook?(runNonce)
        return NativeCoverReceipt(runNonce: runNonce, drawObserved: coverValid, transactionCommitted: coverValid)
    }
    func revealColdPlayer() { coldRevealCount += 1 }

    func createPlayer(locale: NativeDisplayLocale, mode: String, theme: String, inspect: Bool,
                      nativeStartup: NativeStartupBridgeInput?,
                      messageHandler: WKScriptMessageHandler, navigationDelegate: WKNavigationDelegate) {
        createdPlayers.append((locale, mode, theme, inspect))
        nativeStartupInputs.append(nativeStartup)
    }
    func loadPlayer(page: URL, allowingReadAccessTo root: URL) { loadedPlayers.append((page, root)) }
    func updateLabels(_ locale: NativeDisplayLocale) { updatedLocales.append(locale) }
    func showReady() { readyCount += 1 }
    func setNormalLevel() { normalLevelCount += 1 }
    func makeVisible() { visibleCount += 1 }
    func orderOut() { orderedOutCount += 1 }
    func evaluateJavaScript(_ source: String, completion: ((Any?, Error?) -> Void)?) {
        evaluations.append(source)
        let result = evaluationHook?(source) ?? evaluationResult
        completion?(result.0, result.1)
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

        for end in [SkinNativePresentationEnd.completed, .skipped, .interrupted, .failed] {
            let (writer, records) = makeWriter(startedAt: 70, launcherPID: 170)
            let stream = NativeStartupEventStream(writer: writer)
            stream.begin(at: 70)
            stream.targetOpened(pid: 2170, at: 71)
            _ = stream.bindPage(pid: 2170, pageID: "native-page")
            let workspace = end == .completed ? SkinNativeWorkspaceObservation(pageGeneration: "native-page",
                runID: 7, wallpaperDisposition: "disabled", wallpaperReason: "disabled") : nil
            _ = stream.resolveNative(SkinNativeLaunchReceipt(operationID: UUID(),
                runNonce: "11111111-2222-4333-8444-555555555555", presentation: end,
                reason: end == .failed ? "attach-timeout" : nil, workspace: workspace,
                coverDrawCommitted: true), at: 73)
            _ = stream.finish(at: 74)
            try write("native-\(end.rawValue)", records())
        }
    }

    @MainActor
    static func main() async throws {
        if CommandLine.arguments.contains("--probe-cold-window-ordering") {
            _ = NSApplication.shared
            NSApp.setActivationPolicy(.accessory)
            print("Cold-window ordering checks: \(try nativeColdWindowOrderingChecks())")
            return
        }
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
        if CommandLine.arguments.contains("--probe-ready-replacement") {
            let result = try await startupReplacementScenario(stage: "status", mode: "after-ready",
                                                              readyOverlap: CommandLine.arguments.contains("--ready-overlap"))
            print(String(decoding: try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]), as: UTF8.self))
            exit(result["currentPageID"] as? String == "page-b" && result["completed"] as? Bool == true ? 0 : 1)
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
        checks += startupIdentityDiagnosticChecks()
        checks += launcherCommandLineChecks()
        checks += try await hostApplicationKeyChecks()
        func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
            guard condition() else { fatalError("FAILED: \(label)") }
            checks += 1
        }
        let startupBridgeInput = NativeStartupBridgeInput(runNonce: "native-run-01", locale: "zh-CN", theme: "light")
        let startupBridgeSource = startupBridgeInput.documentStartSource() ?? ""
        expect(startupBridgeSource.contains("Object.defineProperty(window, '__agentSkinNativeStartup'")
               && startupBridgeSource.contains("writable: false")
               && startupBridgeSource.contains("configurable: false")
               && startupBridgeSource.contains("azhou-agent-skin-native"),
               "formal local bootstrap binds one immutable native identity at document start")
        expect(!startupBridgeSource.contains("data:image")
               && NativeStartupBridgeInput(runNonce: "bad nonce", locale: "zh-CN", theme: "light")
                    .documentStartSource() == nil,
               "document-start identity carries no settings payload and rejects malformed nonces")
        expect(NativeStartupSnapshotTransfer.maximumBytes == StartupSettingsSnapshotReceiver.maximumBytes
               && NativeStartupSnapshotTransfer.chunkSize == 192 * 1024
               && NativeStartupSnapshotTransfer.maximumExpressionBytes == 512 * 1024,
               "native WK transfer shares the receiver byte ceiling and keeps each message bounded")
        let transferValues = StartupSettingsSnapshotValues(
            avatar: "data:image/png;base64,AA==", artwork: "data:image/png;base64,AA==",
            contours: [[StartupSettingsSnapshotPoint(x: 10, y: 10),
                        StartupSettingsSnapshotPoint(x: 20, y: 30)]],
            introTitle: "阿舟", introCaption: "冷启动", artworkSubtitle: "工作区准备",
            wallpaperStrength: 42,
            explicitText: ["introTitle": true, "introCaption": true, "artworkSubtitle": true])
        let transferSnapshot = StartupSettingsSnapshot(
            owner: "azhou-codex-startup", runID: 7, runNonce: "native-run-01",
            snapshotID: "7:native-run-01", status: "valid", sha256: String(repeating: "a", count: 64),
            appearance: StartupSettingsSnapshotAppearance(locale: "zh-CN", theme: "light"),
            values: transferValues)
        var transferExpressions: [String] = []
        var transferTimeouts: [TimeInterval] = []
        try await NativeStartupSnapshotTransfer.send(
            snapshot: transferSnapshot, runNonce: "native-run-01", deadline: 110, now: { 100 },
            evaluate: { expression, timeout in
                transferExpressions.append(expression); transferTimeouts.append(timeout); return true
            })
        expect(transferExpressions.count == 3
               && transferExpressions[0].contains("acceptNativeSnapshotDescriptor")
               && transferExpressions[1].contains("acceptNativeSnapshotChunk")
               && transferExpressions[2].contains("finishNativeSnapshot"),
               "WK handoff sends descriptor, ordered payload chunks, and finish through the local adapter")
        expect(transferExpressions.allSatisfy { $0.utf8.count < NativeStartupSnapshotTransfer.maximumExpressionBytes }
               && transferTimeouts.allSatisfy { $0 > 0 && $0 <= 2 },
               "every native message stays under its expression cap and consumes the absolute deadline")
        var mismatchCalls = 0
        do {
            try await NativeStartupSnapshotTransfer.send(
                snapshot: transferSnapshot, runNonce: "another-run", deadline: 110, now: { 100 },
                evaluate: { _, _ in mismatchCalls += 1; return true })
            fatalError("a mismatched startup nonce unexpectedly transferred a snapshot")
        } catch { }
        expect(mismatchCalls == 0, "a snapshot for another run is refused before its first WK side effect")
        var failedTransferExpressions: [String] = []
        do {
            try await NativeStartupSnapshotTransfer.send(
                snapshot: transferSnapshot, runNonce: "native-run-01", deadline: 110, now: { 100 },
                evaluate: { expression, _ in
                    failedTransferExpressions.append(expression)
                    return !expression.contains("acceptNativeSnapshotChunk")
                })
            fatalError("a rejected snapshot chunk unexpectedly completed")
        } catch { }
        expect(failedTransferExpressions.count == 3
               && failedTransferExpressions.last?.contains("cancelNativeSnapshot") == true,
               "a failed WK chunk triggers one nonce-bound cleanup call")
        var delayedFinishStarted: CheckedContinuation<Void, Never>?
        var delayedFinishResult: CheckedContinuation<Any?, Error>?
        var delayedTransferExpressions: [String] = []
        let delayedTransfer = Task { @MainActor in
            try await NativeStartupSnapshotTransfer.send(
                snapshot: transferSnapshot, runNonce: "native-run-01", deadline: 110, now: { 100 },
                evaluate: { expression, _ in
                    delayedTransferExpressions.append(expression)
                    if expression.contains("finishNativeSnapshot") {
                        delayedFinishStarted?.resume()
                        delayedFinishStarted = nil
                        return try await withCheckedThrowingContinuation {
                            (continuation: CheckedContinuation<Any?, Error>) in
                            delayedFinishResult = continuation
                        }
                    }
                    return true
                })
        }
        await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
            delayedFinishStarted = continuation
        }
        delayedTransfer.cancel()
        delayedFinishResult?.resume(returning: true)
        delayedFinishResult = nil
        var delayedCancellationCaught = false
        do { try await delayedTransfer.value }
        catch is CancellationError { delayedCancellationCaught = true }
        catch { }
        let nonceBoundCleanup = delayedTransferExpressions.last
        expect(delayedCancellationCaught
               && delayedTransferExpressions.count == 4
               && nonceBoundCleanup?.contains("cancelNativeSnapshot") == true
               && nonceBoundCleanup?.contains("native-run-01") == true
               && nonceBoundCleanup?.contains("[\"native-run-01\"]") == true,
               "cancellation during a delayed finish rejects success and cleans up only the bound run")
        var expiredCalls = 0
        do {
            try await NativeStartupSnapshotTransfer.send(
                snapshot: transferSnapshot, runNonce: "native-run-01", deadline: 99, now: { 100 },
                evaluate: { _, _ in expiredCalls += 1; return true })
            fatalError("an expired WK transfer unexpectedly completed")
        } catch { }
        expect(expiredCalls == 0, "an expired startup budget refuses WK transfer before sending")
        let registeredTimeout = DispatchWorkItem {}
        do {
            let _: any NativeApplication = try await withCheckedThrowingContinuation { continuation in
                let waiter = StartupApplicationWaiter(continuation)
                waiter.setTimeout(registeredTimeout)
                waiter.finish(.failure(NSError(domain: "waiter-fixture", code: 1)))
                waiter.finish(.failure(NSError(domain: "waiter-fixture", code: 2)))
            }
            fatalError("waiter fixture unexpectedly succeeded")
        } catch let error as NSError {
            expect(error.domain == "waiter-fixture" && error.code == 1 && registeredTimeout.isCancelled,
                   "first waiter result wins and cancels an existing timeout")
        }
        let lateTimeout = DispatchWorkItem {}
        do {
            let _: any NativeApplication = try await withCheckedThrowingContinuation { continuation in
                let waiter = StartupApplicationWaiter(continuation)
                waiter.finish(.failure(NSError(domain: "waiter-fixture", code: 3)))
                waiter.setTimeout(lateTimeout)
            }
            fatalError("waiter fixture unexpectedly succeeded")
        } catch let error as NSError {
            expect(error.domain == "waiter-fixture" && error.code == 3 && lateTimeout.isCancelled,
                   "a timeout registered after completion is immediately canceled")
        }
        let firstTimeout = DispatchWorkItem {}
        let replacementTimeout = DispatchWorkItem {}
        do {
            let _: any NativeApplication = try await withCheckedThrowingContinuation { continuation in
                let waiter = StartupApplicationWaiter(continuation)
                waiter.setTimeout(firstTimeout)
                waiter.setTimeout(replacementTimeout)
                waiter.finish(.failure(NSError(domain: "waiter-fixture", code: 4)))
            }
            fatalError("waiter fixture unexpectedly succeeded")
        } catch let error as NSError {
            expect(error.code == 4 && !firstTimeout.isCancelled && replacementTimeout.isCancelled,
                   "the latest registered timeout retains the existing replacement semantics")
        }
        var canceledDuringRace = 0
        for _ in 0..<40 {
            let timeout = ConcurrentTimeoutFixture()
            do {
                let _: any NativeApplication = try await withCheckedThrowingContinuation { continuation in
                    let waiter = StartupApplicationWaiter(continuation)
                    DispatchQueue.concurrentPerform(iterations: 2) { index in
                        if index == 0 { waiter.setTimeout(timeout.item) }
                        else { waiter.finish(.failure(NSError(domain: "waiter-race", code: 1))) }
                    }
                }
                fatalError("waiter fixture unexpectedly succeeded")
            } catch {
                if timeout.item.isCancelled { canceledDuringRace += 1 }
            }
        }
        expect(canceledDuringRace == 40, "registration racing completion always cancels the registered timeout")
        var concurrentFailures = 0
        for _ in 0..<40 {
            do {
                let _: any NativeApplication = try await withCheckedThrowingContinuation { continuation in
                    let waiter = StartupApplicationWaiter(continuation)
                    DispatchQueue.concurrentPerform(iterations: 16) { index in
                        waiter.finish(.failure(NSError(domain: "concurrent-waiter-fixture", code: index)))
                    }
                }
                fatalError("waiter fixture unexpectedly succeeded")
            } catch let error as NSError {
                if error.domain == "concurrent-waiter-fixture" && (0..<16).contains(error.code) {
                    concurrentFailures += 1
                }
            }
        }
        expect(concurrentFailures == 40, "concurrent waiter completions resume exactly once per operation")
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

        checks += await startupShellAdmissionChecks(target: existing)

        var fakeNow: TimeInterval = 0
        let startupURL = "app://-/index.html?initialRoute=%2F"
        let successfulTransport = FakeStartupTransport(
            pages: [[
                "type": "page", "id": "selected-page", "url": startupURL,
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"
            ]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": [
                    "owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": 7,
                    "ready": true, "completed": false, "overlay": true, "reason": "",
                    "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
                    "completion": NSNull()
                ]],
                ["href": startupURL, "missing": false, "status": [
                    "owner": "azhou-codex-startup", "version": 1, "phase": "complete", "runId": 7,
                    "ready": true, "completed": true, "overlay": false, "reason": "",
                    "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
                    "completion": ["cause": "natural", "beforeReady": false]
                ]]
            ],
            pageFailures: 1
        )
        var readyNotifications = 0
        let successful = await StartupConnector(
            target: existing,
            expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: successfulTransport,
            onReady: { readyNotifications += 1 },
            now: { fakeNow },
            sleep: { fakeNow += $0 }
        ).run(payload: "test-only-probe", deadline: 45)
        expect(successful == .ready(runID: 7), "a controlled main page reaches startup-ready")
        expect(successfulTransport.pagesCount == 5, "page discovery retries and rechecks identity before install and ready within the shared budget")
        expect(successfulTransport.connectCount == 1, "startup uses one selected page socket")
        expect(successfulTransport.payloadCount == 1, "startup installs its payload once")
        expect(successfulTransport.closeCount == 1, "startup closes its socket after playback completes")
        expect(successfulTransport.disposeCount == 0, "successful startup is not disposed")
        expect(readyNotifications == 1 && successfulTransport.evaluateCount == 4,
               "readiness notifies presentation once but does not finish playback observation")

        for phase in ["playing", "settings"] {
            var time: TimeInterval = 0
            var notifications = 0
            let transport = FakeStartupTransport(
                pages: [["type": "page", "id": "selected-page", "url": startupURL,
                         "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
                evaluations: [
                    ["href": startupURL, "controllerPresent": false, "shellReady": true],
                    ["installed": true, "alreadyActive": false],
                    ["href": startupURL, "missing": false, "status": [
                        "owner": "azhou-codex-startup", "version": 1, "phase": phase, "runId": 7,
                        "ready": true, "completed": false, "overlay": true, "reason": "",
                        "wallpaper": ["applied": false, "reason": "disabled", "imageDecoded": false],
                        "completion": NSNull()
                    ]]
                ], repeatLastEvaluation: true)
            let result = await StartupConnector(target: existing, expectedPort: 9222,
                system: FakeStartupSystem(expectedPID: 4123, ports: [9222]), transport: transport,
                onReady: { notifications += 1 }, now: { time }, sleep: { time += $0 })
                .run(payload: "test-only-probe", deadline: 45)
            expect(result == (phase == "playing" ? .failed(reason: "attach-timeout") : .ready(runID: 7)),
                   "playing remains bounded while settings hands control to the user without waiting")
            expect(notifications == 1 && transport.payloadCount == 1 && transport.closeCount == 1,
                   "repeated ready polls neither reactivate nor reinstall, and always close")
        }

        var skippedNow: TimeInterval = 0
        let skippedTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
        ).run(payload: "test-only-probe", deadline: 45)
        expect(skipped == .skipped(runID: 8, beforeReady: true), "a pre-ready skip stays distinct from readiness")
        expect(skippedTransport.payloadCount == 1 && skippedTransport.closeCount == 1,
               "skip does not replay and closes its page socket")

        var savedNow: TimeInterval = 0
        let savedTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
        ).run(payload: "test-only-probe", deadline: 45)
        expect(saved == .ready(runID: 9), "a completed settings save remains a valid ready attachment")
        expect(savedTransport.payloadCount == 1 && savedTransport.disposeCount == 0,
               "settings save does not cause the connector to dispose the installed controller")

        var navigationNow: TimeInterval = 0
        let navigationTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
        ).run(payload: "test-only-probe", deadline: 45)
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
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
        ).run(payload: "test-only-probe", deadline: 45)
        expect(drift == .partial(reason: "startup-interrupted"), "a status run ID change interrupts the owned startup run")
        expect(driftTransport.disposeCount == 0, "a changed status run ID does not dispose another run")

        var stalledNow: TimeInterval = 0
        let stalledTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
        ).run(payload: "test-only-probe", deadline: 45)
        expect(stalled == .failed(reason: "attach-timeout"), "never-ready polling ends at the shared deadline")
        expect(stalledTransport.payloadCount == 1 && stalledTransport.closeCount == 1,
               "never-ready polling does not reinstall and closes the session")
        expect(stalledTransport.requestTimeouts.allSatisfy { $0 > 0 && $0 <= 10 } && stalledNow <= 45.001,
               "page lookup, WebSocket connect, and evaluation requests stay inside the absolute budget")
        expect(stalledTransport.requestTimeouts.contains { $0 < 0.1 },
               "the final status request is truncated to the remaining stage time")

        var malformedNow: TimeInterval = 0
        let malformedStatusTransport = FakeStartupTransport(
            pages: [["type": "page", "id": "selected-page", "url": startupURL,
                     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]],
            evaluations: [
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
        ).run(payload: "test-only-probe", deadline: 45)
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
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": ["owner": "unknown"]]
            ],
            afterEvaluation: { _, index in if index == 2 { expiredNow = 45 } }
        )
        let expiredMalformedStatus = await StartupConnector(
            target: existing, expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: 4123, ports: [9222]),
            transport: expiredMalformedStatusTransport,
            now: { expiredNow }, sleep: { expiredNow += $0 }
        ).run(payload: "test-only-probe", deadline: 45)
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
        checks += try await startupPageReplacementChecks()
        checks += try await startupControllerBindingChecks()
        checks += try await startupSettingsSnapshotChecks()
        checks += try await startupPreparedConnectorChecks()
        checks += try await nativeColdLaunchChecks()
        checks += try await nativeEventContractChecks()
        checks += try await skinHostContractChecks()
        checks += codexLaunchConfigurationChecks()
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

@MainActor
private func startupSettingsSnapshotChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: native settings snapshot: \(label)") }
        checks += 1
    }

    func opened(_ world: StartupSnapshotWorld, pageID: String = "page-a") throws -> WallpaperTransport {
        let transport = WallpaperTransport(session: nil, socketFactory: { world.socket($0) })
        world.transport = transport
        try transport.connect(to: URL(string: "ws://127.0.0.1:49221/devtools/page/\(pageID)")!, timeout: 5)
        return transport
    }
    let page = StartupSnapshotPage(id: "page-a", href: "app://-/index.html?initialRoute=%2F")
    let request = StartupSettingsSnapshotRequest(owner: "azhou-codex-startup", runID: 1, runNonce: "test-run-1")

    var receiverOwnedBytes = Data("receiver-owned-buffer".utf8)
    StartupSettingsSnapshotReceiver.clearNativeOwnedBuffer(&receiverOwnedBytes)
    expect(!receiverOwnedBytes.isEmpty && receiverOwnedBytes.allSatisfy { $0 == 0 },
           "receiver-owned snapshot bytes are zeroed within their bounded Data buffer")
    var aggregateBytes = Data("prefix:".utf8)
    var sourceChunk = Data("chunk-secret".utf8)
    let sourceAlias = sourceChunk
    StartupSettingsSnapshotReceiver.appendNativeChunk(sourceChunk, to: &aggregateBytes)
    StartupSettingsSnapshotReceiver.clearNativeOwnedBuffer(&sourceChunk)
    expect(sourceChunk.allSatisfy { $0 == 0 }
           && aggregateBytes == Data("prefix:chunk-secret".utf8)
           && sourceAlias == Data("chunk-secret".utf8),
           "chunk append copies bytes into the aggregate before zeroing while Data aliases retain value semantics")

    let healthy = StartupSnapshotWorld()
    let healthyTransport = try opened(healthy)
    defer { healthyTransport.close() }
    let received = try await StartupSettingsSnapshotReceiver.receive(
        transport: healthyTransport, page: page, request: request, deadline: 50, now: { healthy.time() })
    expect(received.snapshotID == "1:test-run-1" && received.status == "valid" && received.values.wallpaperStrength == 42,
           "a snapshot is received through the real WallpaperTransport session")
    expect(received.appearance == StartupSettingsSnapshotAppearance(locale: "zh-CN", theme: "light"),
           "host locale and theme are read from the same digest-bound snapshot")
    expect(healthy.operationLog.filter { $0 == "page-a:read" }.count == healthy.descriptor["chunkCount"] as? Int,
           "the receiver reads every declared chunk")
    expect(healthy.chunkBase64.first?.hasSuffix("==") == true,
           "each 64 KiB chunk is independently Base64 encoded and padded")
    expect(healthy.descriptor["encodedByteLength"] as? Int == healthy.chunkBase64.reduce(0) { $0 + $1.utf8.count },
           "descriptor encoded length sums independently padded chunk strings")
    expect(healthy.objectIDs.allSatisfy { $0 == "controller-page-a" },
           "begin and chunks use the retained controller object ID")
    expect(healthy.maxSocketMessageSize == 2 * 1024 * 1024,
           "the snapshot path keeps the existing 2 MiB WebSocket limit")

    let wrapped = StartupSnapshotWorld()
    let wrappedBase = WallpaperTransport(session: nil, socketFactory: { wrapped.socket($0) })
    wrapped.transport = wrappedBase
    let capture = NativeStartupCapture(targetPID: 4123)
    let writer = NativeEventWriter(startedAt: 0, launcherPID: 42, launcherPath: "/synthetic/launcher",
                                   now: { wrapped.time() }, sink: { _ in })
    let events = NativeStartupEventStream(writer: writer)
    events.begin(at: 1); events.targetOpened(pid: 4123, at: 1)
    let eventTransport = NativeStartupEventTransport(base: wrappedBase, capture: capture, events: events, now: { wrapped.time() })
    let observingTransport = InstallObservingStartupTransport(base: eventTransport, recorder: CodexInstallObservation())
    try observingTransport.connect(to: URL(string: "ws://127.0.0.1:49221/devtools/page/page-a")!, timeout: 5)
    defer { observingTransport.close() }
    let wrappedSnapshot = try await StartupSettingsSnapshotReceiver.receive(
        transport: observingTransport, page: page, request: request, deadline: 50, now: { wrapped.time() })
    expect(wrappedSnapshot.snapshotID == received.snapshotID && wrapped.operationLog.contains("page-a:begin"),
           "both production startup transport wrappers forward the captured snapshot session")
    let operationsBeforeWrongPage = wrapped.operationLog
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: observingTransport,
            page: StartupSnapshotPage(id: "page-b", href: page.href), request: request,
            deadline: 50, now: { wrapped.time() })
        fatalError("FAILED: event wrapper must reject a page different from the captured page")
    } catch is CancellationError {
        expect(wrapped.operationLog == operationsBeforeWrongPage,
               "wrapper page mismatch fails before beginning or disposing another page's snapshot")
    }

    let unsupported = StartupSnapshotWorld(controllerSupportsSnapshot: false)
    let unsupportedTransport = try opened(unsupported)
    defer { unsupportedTransport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: unsupportedTransport, page: page, request: request, deadline: 50, now: { unsupported.time() })
        fatalError("FAILED: an old controller without snapshot methods must fail closed")
    } catch let failure as StartupFailure {
        expect(failure.reason == "snapshot-invalid", "old controller snapshot API is rejected")
    }
    expect(unsupported.operationLog.contains("page-a:dispose"),
           "unsupported snapshot begin still attempts disposal on its bound controller")
    expect(unsupported.objectIDs.allSatisfy { $0 == "controller-page-a" },
           "unsupported API cleanup never uses an unbound global controller")

    for (name, mutate) in [
        ("owner", { (descriptor: inout [String: Any]) in descriptor["owner"] = "foreign" }),
        ("run ID", { (descriptor: inout [String: Any]) in descriptor["runId"] = 2 }),
        ("nonce", { (descriptor: inout [String: Any]) in descriptor["runNonce"] = "other-run" }),
        ("status", { (descriptor: inout [String: Any]) in descriptor["status"] = "failure" }),
        ("length", { (descriptor: inout [String: Any]) in descriptor["encodedByteLength"] = 1 }),
        ("digest", { (descriptor: inout [String: Any]) in descriptor["sha256"] = String(repeating: "0", count: 64) }),
    ] {
        let malformed = StartupSnapshotWorld()
        malformed.mutateDescriptor = mutate
        let transport = try opened(malformed)
        defer { transport.close() }
        do {
            _ = try await StartupSettingsSnapshotReceiver.receive(
                transport: transport, page: page, request: request, deadline: 50, now: { malformed.time() })
            fatalError("FAILED: malformed \(name) descriptor must be rejected")
        } catch is StartupFailure {
            expect(malformed.operationLog.contains("page-a:dispose"), "\(name) descriptor failure attempts bound cleanup")
            if name != "digest" {
                expect(!malformed.operationLog.contains("page-a:read"), "\(name) descriptor failure downloads no chunks")
            }
        }
    }

    for invalidAppearance: Any in [NSNull(), ["locale": "fr", "theme": "light"],
                                  ["locale": "en", "theme": "auto"],
                                  ["locale": "en", "theme": "dark", "extra": "untrusted"]] {
        var object = try JSONSerialization.jsonObject(with: StartupSnapshotWorld.makePayload()) as! [String: Any]
        object["appearance"] = invalidAppearance
        let malformed = StartupSnapshotWorld(payload: try JSONSerialization.data(withJSONObject: object))
        let transport = try opened(malformed)
        defer { transport.close() }
        do {
            _ = try await StartupSettingsSnapshotReceiver.receive(
                transport: transport, page: page, request: request, deadline: 50, now: { malformed.time() })
            fatalError("FAILED: an invalid snapshot appearance must not be replaced with system preferences")
        } catch let failure as StartupFailure {
            expect(failure.reason == "snapshot-invalid", "invalid snapshot appearance fails closed")
            expect(malformed.operationLog.contains("page-a:dispose"), "appearance failure attempts bound cleanup")
        }
    }

    let digestMismatch = StartupSnapshotWorld()
    digestMismatch.mutateDescriptor = { $0["sha256"] = String(repeating: "0", count: 64) }
    digestMismatch.mutateChunk = { chunk, _ in chunk["sha256"] = String(repeating: "0", count: 64) }
    let digestTransport = try opened(digestMismatch)
    defer { digestTransport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: digestTransport, page: page, request: request, deadline: 50,
            now: { digestMismatch.time() })
        fatalError("FAILED: a mismatched whole-snapshot digest must be rejected")
    } catch is StartupFailure {
        expect(digestMismatch.chunkBase64.count == digestMismatch.descriptor["chunkCount"] as? Int,
               "all chunks are received before the final whole-snapshot digest check")
        expect(digestMismatch.operationLog.contains("page-a:dispose"), "whole digest failure attempts bound cleanup")
    }

    let wrongSequence = StartupSnapshotWorld()
    wrongSequence.mutateChunk = { chunk, index in if index == 0 { chunk["offset"] = 1 } }
    let sequenceTransport = try opened(wrongSequence)
    defer { sequenceTransport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: sequenceTransport, page: page, request: request, deadline: 50, now: { wrongSequence.time() })
        fatalError("FAILED: an out-of-order chunk must be rejected")
    } catch is StartupFailure {
        expect(wrongSequence.operationLog.contains("page-a:dispose"), "chunk sequence failure attempts bound cleanup")
    }

    let wrongIndex = StartupSnapshotWorld()
    wrongIndex.mutateChunk = { chunk, index in if index == 0 { chunk["index"] = index + 1 } }
    let wrongIndexTransport = try opened(wrongIndex)
    defer { wrongIndexTransport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: wrongIndexTransport, page: page, request: request, deadline: 50, now: { wrongIndex.time() })
        fatalError("FAILED: a chunk with an unexpected sequence number must be rejected")
    } catch is StartupFailure {
        expect(wrongIndex.operationLog.contains("page-a:dispose"), "chunk index failure attempts bound cleanup")
    }

    let wrongTotal = StartupSnapshotWorld()
    wrongTotal.mutateChunk = { chunk, index in if index == 0 { chunk["totalBytes"] = wrongTotal.payload.count + 1 } }
    let wrongTotalTransport = try opened(wrongTotal)
    defer { wrongTotalTransport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: wrongTotalTransport, page: page, request: request, deadline: 50, now: { wrongTotal.time() })
        fatalError("FAILED: a chunk with an inconsistent total length must be rejected")
    } catch is StartupFailure {
        expect(wrongTotal.operationLog.contains("page-a:dispose"), "chunk total length failure attempts bound cleanup")
    }

    let invalidUTF8 = StartupSnapshotWorld(payload: StartupSnapshotWorld.makePayload(invalidUTF8: true))
    let utf8Transport = try opened(invalidUTF8)
    defer { utf8Transport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: utf8Transport, page: page, request: request, deadline: 50, now: { invalidUTF8.time() })
        fatalError("FAILED: invalid UTF-8 snapshot must be rejected")
    } catch is StartupFailure {
        expect(invalidUTF8.operationLog.contains("page-a:dispose"), "invalid UTF-8 failure attempts bound cleanup")
    }

    let invalidSchema = StartupSnapshotWorld(payload: StartupSnapshotWorld.makePayload(schemaVersion: 2))
    let schemaTransport = try opened(invalidSchema)
    defer { schemaTransport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: schemaTransport, page: page, request: request, deadline: 50, now: { invalidSchema.time() })
        fatalError("FAILED: unsupported settings schema must be rejected")
    } catch is StartupFailure {
        expect(invalidSchema.operationLog.contains("page-a:dispose"), "schema failure attempts bound cleanup")
    }

    let tooLarge = StartupSnapshotWorld()
    tooLarge.mutateDescriptor = { descriptor in
        let count = (StartupSettingsSnapshotReceiver.maximumBytes + 1 + StartupSettingsSnapshotReceiver.chunkSize - 1)
            / StartupSettingsSnapshotReceiver.chunkSize
        descriptor["byteLength"] = StartupSettingsSnapshotReceiver.maximumBytes + 1
        descriptor["chunkCount"] = count
        descriptor["encodedByteLength"] = 4 * (((count - 1) * StartupSettingsSnapshotReceiver.chunkSize + 2) / 3)
            + 4 * ((StartupSettingsSnapshotReceiver.maximumBytes + 1 - (count - 1) * StartupSettingsSnapshotReceiver.chunkSize + 2) / 3)
    }
    let largeTransport = try opened(tooLarge)
    defer { largeTransport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: largeTransport, page: page, request: request, deadline: 50, now: { tooLarge.time() })
        fatalError("FAILED: a descriptor above the maximum byte length must be rejected")
    } catch is StartupFailure {
        expect(!tooLarge.operationLog.contains("page-a:read"), "oversized descriptor is rejected before any chunk request")
        expect(tooLarge.operationLog.contains("page-a:dispose"), "oversized descriptor attempts bound cleanup")
    }

    let cancelled = StartupSnapshotWorld(cancelAfterChunk: 0)
    let cancelledTransport = try opened(cancelled)
    defer { cancelledTransport.close() }
    let cancellationTask = Task {
        try await StartupSettingsSnapshotReceiver.receive(
            transport: cancelledTransport, page: page, request: request, deadline: 50, now: { cancelled.time() })
    }
    do {
        _ = try await cancellationTask.value
        fatalError("FAILED: cancellation during chunk receive must propagate")
    } catch is CancellationError {
        expect(cancelled.operationLog.contains("page-a:dispose"), "cancelled transfer attempts cleanup despite task cancellation")
    }

    let replaced = StartupSnapshotWorld(replaceAfterChunk: 0)
    let replacedTransport = try opened(replaced)
    defer { replacedTransport.close() }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: replacedTransport, page: page, request: request, deadline: 50, now: { replaced.time() })
        fatalError("FAILED: page replacement during a snapshot must cancel the transfer")
    } catch is CancellationError {
        expect(replaced.operationLog.contains("page-a:dispose"), "page replacement attempts cleanup on the old controller: \(replaced.operationLog)")
        expect(!replaced.operationLog.contains("page-b:dispose") && replaced.objectIDs.allSatisfy { $0 == "controller-page-a" },
               "page replacement cannot retarget cleanup to the successor page")
    }

    let expired = StartupSnapshotWorld()
    let expiredTransport = try opened(expired)
    defer { expiredTransport.close() }
    var expiredNow: TimeInterval = 1
    expired.afterChunk = { index in if index == 0 { expiredNow = 50 } }
    do {
        _ = try await StartupSettingsSnapshotReceiver.receive(
            transport: expiredTransport, page: page, request: request, deadline: 50, now: { expiredNow })
        fatalError("FAILED: the original absolute deadline must bound later chunks")
    } catch is StartupFailure {
        expect(expired.operationLog.filter { $0 == "page-a:read" }.count == 1,
               "the original deadline prevents a second chunk request")
        expect(!expired.operationLog.contains("page-a:dispose"), "expired deadline sends no cleanup request past its bound")
    }
    return checks
}

private final class StartupSnapshotWorld: @unchecked Sendable {
    let href = "app://-/index.html?initialRoute=%2F"
    var runNonce = "test-run-1"
    var preparedMode = false
    var preparedDisposition = "disabled"
    var preparedShell = true
    var malformedPrepared = false
    var preparedPages: Set<String> = []
    var preparedExpiries: [Double] = []
    var cleanupCancellationStates: [Bool] = []
    var afterWorkspaceClock: (() -> Void)?
    var submittedInstall: String?
    let payload: Data
    let controllerSupportsSnapshot: Bool
    let cancelAfterChunk: Int?
    let replaceAfterChunk: Int?
    weak var transport: WallpaperTransport?
    var mutateDescriptor: ((inout [String: Any]) -> Void)?
    var mutateChunk: ((inout [String: Any], Int) -> Void)?
    var afterChunk: ((Int) -> Void)?
    private(set) var operationLog: [String] = []
    private(set) var objectIDs: [String] = []
    private(set) var chunkBase64: [String] = []
    var maxSocketMessageSize = 0
    private var clock: TimeInterval = 1

    var descriptor: [String: Any] {
        let count = (payload.count + StartupSettingsSnapshotReceiver.chunkSize - 1) / StartupSettingsSnapshotReceiver.chunkSize
        let encoded = (0..<count).reduce(0) { total, index in
            let length = min(StartupSettingsSnapshotReceiver.chunkSize, payload.count - index * StartupSettingsSnapshotReceiver.chunkSize)
            return total + 4 * ((length + 2) / 3)
        }
        return ["ok": true, "owner": "azhou-codex-startup", "runId": 1, "runNonce": runNonce,
                "snapshotID": "1:\(runNonce)", "status": "valid", "byteLength": payload.count,
                "encodedByteLength": encoded, "chunkSize": StartupSettingsSnapshotReceiver.chunkSize,
                "chunkCount": count, "digestAlgorithm": "sha-256",
                "sha256": SHA256.hash(data: payload).map { String(format: "%02x", $0) }.joined()]
    }

    init(controllerSupportsSnapshot: Bool = true, cancelAfterChunk: Int? = nil, replaceAfterChunk: Int? = nil,
         payload: Data? = nil) {
        self.controllerSupportsSnapshot = controllerSupportsSnapshot
        self.cancelAfterChunk = cancelAfterChunk
        self.replaceAfterChunk = replaceAfterChunk
        self.payload = payload ?? Self.makePayload()
    }

    func time() -> TimeInterval { clock }

    static func makePayload(schemaVersion: Int = 1, invalidUTF8: Bool = false) -> Data {
        let pngSignature = Data([137, 80, 78, 71, 13, 10, 26, 10])
        let artworkBytes = pngSignature + Data(repeating: 0x42, count: 80_000)
        let settings: [String: Any] = [
            "schemaVersion": schemaVersion,
            "avatar": "data:image/png;base64,\(pngSignature.base64EncodedString())",
            "artwork": "data:image/png;base64,\(artworkBytes.base64EncodedString())",
            "contours": [[[0, 0], [1536, 1024]]],
            "introTitle": "阿舟 AI 实验室", "introCaption": "AZHOU / AI LAB",
            "artworkSubtitle": "和阿舟一起，把想法做出来。", "wallpaperStrength": 42,
        ]
        let object: [String: Any] = ["status": "valid", "settings": settings,
            "appearance": ["locale": "zh-CN", "theme": "light"],
            "explicitText": ["introTitle": true, "introCaption": true, "artworkSubtitle": true]]
        var data = try! JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        if invalidUTF8 { data.append(0xff) }
        return data
    }

    func socket(_ request: URLRequest) -> any WallpaperSocketTask {
        StartupSnapshotSocket(pageID: request.url?.lastPathComponent ?? "unknown", world: self)
    }

    func reply(pageID: String, request: [String: Any]) throws -> Data {
        let requestID = request["id"] as? Int ?? -1
        let params = request["params"] as? [String: Any] ?? [:]
        let objectID = params["objectId"] as? String
        let envelope: ([String: Any]) throws -> Data = { value in
            try JSONSerialization.data(withJSONObject: ["id": requestID, "result": ["result": ["value": value]]])
        }
        if preparedMode, request["method"] as? String == "Runtime.evaluate",
           let expression = params["expression"] as? String {
            if expression == StartupConnector.inspectExpression {
                return try envelope(["href": href, "controllerPresent": false, "shellReady": true])
            }
            if expression.contains("Promise.resolve((") {
                submittedInstall = expression
                operationLog.append("\(pageID):install")
                return try envelope(["installed": true, "alreadyActive": false])
            }
        }
        if request["method"] as? String == "Runtime.evaluate",
           params["expression"] as? String == WallpaperTransport.controllerReferenceExpression {
            return try JSONSerialization.data(withJSONObject: ["id": requestID,
                "result": ["result": ["type": "object", "objectId": "controller-\(pageID)"]]])
        }
        guard request["method"] as? String == "Runtime.callFunctionOn",
              objectID == "controller-\(pageID)" else {
            return try JSONSerialization.data(withJSONObject: ["id": requestID, "error": ["code": -32000, "message": "wrong bound object"]])
        }
        objectIDs.append(objectID ?? "")
        if params["functionDeclaration"] as? String == WallpaperTransport.boundStatusExpression {
            if preparedMode {
                let disposition = preparedPages.contains(pageID) ? preparedDisposition : "pending"
                let reason = disposition == "disabled" ? "disabled"
                    : disposition == "degraded" ? "wallpaper-unsupported" : ""
                return try envelope(["href": href, "missing": false, "shellReady": preparedShell, "status": [
                    "owner": "azhou-codex-startup", "version": 1, "runId": 1,
                    "playbackOwner": "native", "phase": "prepared", "prepared": true,
                    "ready": malformedPrepared, "completed": false, "overlay": false, "reason": "",
                    "completion": NSNull(), "wallpaperDisposition": disposition,
                    "workspace": preparedPages.contains(pageID)
                        ? ["runId": 1, "runNonce": runNonce, "phase": disposition == "pending" ? "pending" : "complete"] : NSNull(),
                    "wallpaper": ["applied": disposition == "applied", "reason": reason,
                                  "imageDecoded": disposition == "applied"],
                ]])
            }
            return try envelope(["href": href, "missing": false, "status": [
                "owner": "azhou-codex-startup", "version": 1, "runId": 1,
            ]])
        }
        guard params["functionDeclaration"] as? String == WallpaperTransport.settingsSnapshotFunction,
              let args = params["arguments"] as? [[String: Any]], args.count == 2,
              let operation = args[0]["value"] as? String,
              let input = args[1]["value"] as? [String: Any] else {
            return try JSONSerialization.data(withJSONObject: ["id": requestID, "error": ["code": -32602, "message": "bad snapshot request"]])
        }
        operationLog.append("\(pageID):\(operation)")
        switch operation {
        case "clock":
            afterWorkspaceClock?()
            return try envelope(["ok": true, "now": 1000])
        case "prepare":
            preparedPages.insert(pageID)
            preparedExpiries.append((input["expiresAt"] as? NSNumber)?.doubleValue ?? -1)
            return try envelope(["ok": true, "accepted": true])
        case "cancelWorkspace":
            cleanupCancellationStates.append(Task.isCancelled)
            return try envelope(["ok": true, "cancelled": true])
        case "begin":
            guard controllerSupportsSnapshot else { return try envelope(["ok": false, "reason": "snapshot-unsupported"]) }
            var result = descriptor
            mutateDescriptor?(&result)
            return try envelope(result)
        case "read":
            guard let index = input["index"] as? Int, let offset = input["offset"] as? Int,
                  index >= 0, offset >= 0, offset < payload.count else { return try envelope(["ok": false, "reason": "snapshot-order-invalid"]) }
            let length = min(StartupSettingsSnapshotReceiver.chunkSize, payload.count - offset)
            let bytes = payload.subdata(in: offset..<(offset + length))
            let text = bytes.base64EncodedString()
            chunkBase64.append(text)
            let original = descriptor
            var result: [String: Any] = ["ok": true, "owner": "azhou-codex-startup", "runId": 1,
                "runNonce": runNonce, "snapshotID": "1:\(runNonce)", "index": index, "offset": offset,
                "byteLength": length, "totalBytes": payload.count, "chunkCount": original["chunkCount"]!,
                "status": "valid", "digestAlgorithm": "sha-256", "sha256": original["sha256"]!, "dataBase64": text]
            mutateChunk?(&result, index)
            afterChunk?(index)
            if cancelAfterChunk == index { withUnsafeCurrentTask { $0?.cancel() } }
            if replaceAfterChunk == index {
                transport?.disconnectPage()
                try? transport?.connect(to: URL(string: "ws://127.0.0.1:49221/devtools/page/page-b")!, timeout: 5)
            }
            return try envelope(result)
        case "dispose":
            return try envelope(controllerSupportsSnapshot ? ["ok": true, "disposed": true]
                : ["ok": false, "reason": "snapshot-unsupported"])
        default:
            return try envelope(["ok": false, "reason": "snapshot-request-invalid"])
        }
    }
}

private final class StartupSnapshotSocket: WallpaperSocketTask, @unchecked Sendable {
    let pageID: String
    let world: StartupSnapshotWorld
    var maximumMessageSize = 0 {
        didSet { world.maxSocketMessageSize = max(world.maxSocketMessageSize, maximumMessageSize) }
    }
    var response: URLResponse? { nil }
    private var pending: [String: Any] = [:]
    private(set) var cancelled = 0

    init(pageID: String, world: StartupSnapshotWorld) { self.pageID = pageID; self.world = world }
    func resume() {}
    func send(_ message: URLSessionWebSocketTask.Message) async throws {
        guard case .string(let text) = message,
              let request = try JSONSerialization.jsonObject(with: Data(text.utf8)) as? [String: Any] else {
            throw URLError(.cannotParseResponse)
        }
        pending = request
    }
    func receive() async throws -> URLSessionWebSocketTask.Message {
        .data(try world.reply(pageID: pageID, request: pending))
    }
    func cancel(with closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) { cancelled += 1 }
}

@MainActor
private func startupShellAdmissionChecks(target: StartupTargetFacts) async -> Int {
    var checks = 0
    var failures: [String] = []
    func expect(_ value: Bool, _ label: String) {
        if !value { failures.append(label) }
        checks += 1
    }
    let href = "app://-/index.html?initialRoute=%2F"
    let pages: [[String: Any]] = [["type": "page", "id": "selected-page", "url": href,
                                 "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/selected-page"]]
    let pending: [String: Any] = ["href": href, "controllerPresent": false, "shellReady": false]
    let ready: [String: Any] = ["href": href, "controllerPresent": false, "shellReady": true]
    let installed: [String: Any] = ["installed": true, "alreadyActive": false]
    let complete: [String: Any] = ["href": href, "missing": false, "status": [
        "owner": "azhou-codex-startup", "version": 1, "phase": "complete", "runId": 1,
        "ready": true, "completed": true, "overlay": false, "reason": "",
        "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
        "completion": ["cause": "natural", "beforeReady": false]
    ]]
    let cases: [(String, [[String: Any]], StartupOutcome, Int, Int?)] = [
        ("a bound page waits for its shell then plays once", [pending, ready, installed, complete], .ready(runID: 1), 1, 4),
        ("a temporary page without a shell receives no payload", [pending], .failed(reason: "attach-timeout"), 0, nil),
        ("a missing readiness field rejects the page", [["href": href, "controllerPresent": false]], .failed(reason: "page-unsupported"), 0, 1),
        ("a numeric readiness field cannot admit the page", [["href": href, "controllerPresent": false, "shellReady": 1]], .failed(reason: "page-unsupported"), 0, 1),
        ("an incumbent appearing during the wait is preserved", [pending, ["href": href, "controllerPresent": true, "shellReady": false]], .partial(reason: "startup-active"), 0, 2)
    ]
    for (label, responses, expected, payloads, evaluations) in cases {
        var clock: TimeInterval = 0
        let transport = FakeStartupTransport(pages: pages, evaluations: responses, repeatLastEvaluation: true)
        let result = await StartupConnector(target: target, expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: target.pid, ports: [9222]), transport: transport,
            now: { clock }, sleep: { clock += $0 }).run(payload: "test-only-probe", deadline: 60)
        expect(result == expected && transport.payloadCount == payloads, label)
        expect(transport.closeCount == 1 && transport.disposeCount == 0, "\(label) closes without taking a controller")
        if let evaluations { expect(transport.evaluateCount == evaluations, "\(label) uses only the admitted playback") }
        expect(clock <= 60 && transport.requestTimeouts.allSatisfy { $0 > 0 && $0 <= 10 }, "\(label) stays bounded")
    }
    for lateSignature in [false, true] {
        var clock: TimeInterval = 0
        var inspected = false
        var validations = 0
        let system = FakeStartupSystem(expectedPID: target.pid, ports: [9222])
        system.afterValidation = {
            if inspected { validations += 1 }
            if lateSignature && validations == 3 { clock = 34 }
        }
        let transport = FakeStartupTransport(pages: pages, evaluations: [ready, installed, complete],
            afterEvaluation: { _, _ in inspected = true })
        let result = await StartupConnector(target: target, expectedPort: 9222, system: system, transport: transport,
            now: { clock }, sleep: { clock += $0 })
            .run(payload: "test-only-probe", deadline: lateSignature ? 60 : 26.5)
        expect(result == .failed(reason: "attach-timeout") && transport.payloadCount == 0,
               lateSignature ? "the final signature check cannot consume the playback reserve" : "a late shell cannot start beyond the full controller window")
    }
    var cancelledClock: TimeInterval = 0
    let cancelledTransport = FakeStartupTransport(pages: pages, evaluations: [pending], repeatLastEvaluation: true)
    let cancelled = await Task { @MainActor in
        await StartupConnector(target: target, expectedPort: 9222,
            system: FakeStartupSystem(expectedPID: target.pid, ports: [9222]), transport: cancelledTransport,
            now: { cancelledClock }, sleep: { cancelledClock += $0; withUnsafeCurrentTask { $0?.cancel() } })
            .run(payload: "test-only-probe", deadline: 60)
    }.value
    expect(cancelled == .partial(reason: "startup-interrupted") && cancelledTransport.payloadCount == 0,
           "cancelling the shell wait never installs a controller")
    let changedSystem = FakeStartupSystem(expectedPID: target.pid, ports: [9222])
    let changedTransport = FakeStartupTransport(pages: pages, evaluations: [pending, ready, installed, complete],
        afterEvaluation: { _, _ in changedSystem.validationError = StartupFailure(reason: "target-identity", message: "changed process") })
    var changedClock: TimeInterval = 0
    let changed = await StartupConnector(target: target, expectedPort: 9222, system: changedSystem, transport: changedTransport,
        now: { changedClock }, sleep: { changedClock += $0 }).run(payload: "test-only-probe", deadline: 60)
    expect(changed == .failed(reason: "target-identity") && changedTransport.payloadCount == 0,
           "ownership changes while waiting refuse without a payload")
    precondition(failures.isEmpty, "FAILED: shell admission: " + failures.joined(separator: "; "))
    return checks
}

#if AGENT_SKIN_NATIVE_EVENT_TESTS
@MainActor
private func nativeEventContractChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }

    let navigationBase = FileManager.default.temporaryDirectory.appendingPathComponent("agent-skin-navigation-" + UUID().uuidString)
    let navigationRoot = navigationBase.appendingPathComponent("web")
    let navigationSibling = navigationBase.appendingPathComponent("web-other")
    try FileManager.default.createDirectory(at: navigationRoot, withIntermediateDirectories: true)
    try FileManager.default.createDirectory(at: navigationSibling, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: navigationBase) }
    let page = navigationRoot.appendingPathComponent("index.html")
    try "synthetic".write(to: page, atomically: true, encoding: .utf8)
    let outside = navigationSibling.appendingPathComponent("outside.html")
    try "synthetic".write(to: outside, atomically: true, encoding: .utf8)
    let innerLink = navigationRoot.appendingPathComponent("inner-link")
    let outerLink = navigationRoot.appendingPathComponent("outer-link")
    try FileManager.default.createSymbolicLink(at: innerLink, withDestinationURL: page)
    try FileManager.default.createSymbolicLink(at: outerLink, withDestinationURL: outside)
    var remote = URLComponents(url: page, resolvingAgainstBaseURL: false)!
    remote.host = "remote"
    var localhost = URLComponents(url: page, resolvingAgainstBaseURL: false)!
    localhost.host = "localhost"
    var withUser = URLComponents(url: page, resolvingAgainstBaseURL: false)!
    withUser.host = "localhost"; withUser.user = "user"
    var withPort = URLComponents(url: page, resolvingAgainstBaseURL: false)!
    withPort.host = "localhost"; withPort.port = 8080
    expect(remote.url?.host == "remote", "remote navigation fixture retains authority")
    expect(withUser.url?.user == "user", "navigation fixture retains user info")
    expect(withPort.url?.port == 8080, "navigation fixture retains port")
    var query = URLComponents(url: page, resolvingAgainstBaseURL: false)!
    query.query = "preview=1"; query.fragment = "fixture"
    let navigationCases: [(URL?, URL?, WKNavigationActionPolicy, String)] = [
        (page, navigationRoot, .allow, "local page"),
        (innerLink, navigationRoot, .allow, "internal symlink"),
        (localhost.url, navigationRoot, .allow, "localhost authority"),
        (query.url, navigationRoot, .allow, "local query and fragment"),
        (navigationRoot, navigationRoot, .cancel, "root is not a file descendant"),
        (outside, navigationRoot, .cancel, "sibling sharing a prefix"),
        (outerLink, navigationRoot, .cancel, "symlink to outside"),
        (navigationRoot.appendingPathComponent("../web-other/outside.html"), navigationRoot, .cancel, "parent traversal"),
        (remote.url, navigationRoot, .cancel, "remote authority"),
        (withUser.url, navigationRoot, .cancel, "authority with user"),
        (withPort.url, navigationRoot, .cancel, "authority with port"),
        (URL(string: "https://example.invalid/index.html"), navigationRoot, .cancel, "remote scheme"),
        (nil, navigationRoot, .cancel, "missing URL"),
        (page, nil, .cancel, "missing root"),
        (page, URL(fileURLWithPath: "/"), .cancel, "filesystem root"),
        (page, remote.url, .cancel, "remote root authority"),
    ]
    for (url, root, expected, label) in navigationCases {
        var calls = 0
        var actual: WKNavigationActionPolicy?
        LocalWebNavigation.decide(url: url, root: root) { value in calls += 1; actual = value }
        expect(calls == 1 && actual == expected, "local navigation: " + label)
    }

    func validStatus(_ runID: Int, phase: String, ready: Bool, completed: Bool,
                     overlay: Bool, completion: Any) -> [String: Any] {
        ["owner": "azhou-codex-startup", "version": 1, "phase": phase, "runId": runID,
         "ready": ready, "completed": completed, "overlay": overlay, "reason": "",
         "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
         "completion": completion]
    }

    var lifecycleRecords: [[String: Any]] = []
    let lifecycle = NativeStartupEventStream(writer: NativeEventWriter(
        startedAt: 0, launcherPID: 1, launcherPath: "/synthetic/launcher",
        sink: { lifecycleRecords.append($0) }
    ))
    lifecycle.targetOpened(pid: 4040, at: 0)
    expect(lifecycle.finish(at: 0) == nil && lifecycleRecords.isEmpty,
           "pre-begin activity cannot emit events or prevent a later begin")
    lifecycle.begin(at: 1)
    lifecycle.begin(at: 2)
    lifecycle.latchInterruption()
    lifecycle.latchFailure("asset-invalid")
    lifecycle.portError(operation: "bind-loopback", errno: 48, at: 3)
    expect(lifecycle.resolve(.activated(pid: 4040), observation: nil, at: 4)
           == .behaviorNotProven(reason: "listener-mismatch"),
           "a later port error keeps its existing precedence over pending interruption and failure")
    let lifecycleFinal = lifecycle.finish(at: 5)
    lifecycle.begin(at: 6)
    lifecycle.portError(operation: "late", errno: 49, at: 7)
    expect(lifecycle.finish(at: 8) == lifecycleFinal
           && lifecycleRecords.map { $0["event"] as? String ?? "" } == [
               "launcher-start", "startup-port-error", "startup-failed", "launcher-exit"
           ], "repeated begin, finish and late observations do not duplicate events")

    let observations = NativeStartupCapture(targetPID: 4040)
    let loading = validStatus(42, phase: "loading", ready: false, completed: false,
                              overlay: true, completion: NSNull())
    let playing = validStatus(42, phase: "playing", ready: true, completed: false,
                              overlay: true, completion: NSNull())
    expect(observations.snapshot().installedAt == nil && observations.snapshot().status == nil,
           "capture starts without installation or status evidence")
    expect(observations.observe(["status": loading], at: 1) == nil
           && observations.snapshot().status == nil,
           "status alone cannot establish an installation")
    expect(observations.observe(["installed": true, "alreadyActive": true, "status": loading], at: 2) == nil
           && observations.snapshot().installedAt == nil,
           "an already-active controller cannot establish a new installation")
    expect(observations.observe(["installed": true, "alreadyActive": false, "status": ["invalid": true]], at: 3) == nil
           && observations.snapshot().installedAt == 3 && observations.snapshot().status == nil,
           "a confirmed installation waits for a valid run")
    _ = observations.observe(["installed": true, "alreadyActive": false], at: 4)
    expect(observations.snapshot().installedAt == 3, "duplicate install receipts retain the first time")
    let captured = observations.observe(["status": loading], at: 5)
    expect(captured?.runID == 42 && captured?.installedAt == 3
           && observations.snapshot().statusAt == 5,
           "the first valid status binds the run and reports installation once")
    let other = validStatus(43, phase: "playing", ready: true, completed: false,
                            overlay: true, completion: NSNull())
    expect(observations.observe(["status": other], at: 6) == nil
           && observations.snapshot().status?.runID == 42 && observations.snapshot().statusAt == 5,
           "another run cannot replace the bound status")
    expect(observations.observe(["status": ["runId": 42]], at: 7) == nil
           && observations.snapshot().statusAt == 5,
           "invalid status preserves the last valid observation")
    expect(observations.observe(["status": playing], at: 8) == nil
           && observations.snapshot().status?.phase == "playing" && observations.snapshot().statusAt == 8,
           "the bound run can update without another installation notification")
    let combined = NativeStartupCapture(targetPID: 4041)
    let combinedResult = combined.observe(["installed": true, "alreadyActive": false, "status": playing], at: 9)
    expect(combinedResult?.runID == 42 && combinedResult?.installedAt == 9
           && combined.snapshot().targetPID == 4041 && combined.snapshot().statusAt == 9,
           "one response can confirm the install and bind its status")

    var failedProtocolStatus = validStatus(2, phase: "failed", ready: false, completed: false,
                                           overlay: false, completion: NSNull())
    failedProtocolStatus["reason"] = "asset-invalid"
    expect(NativeStartupStatus.parse(failedProtocolStatus)?.reason == "asset-invalid",
           "the shared startup protocol preserves the bounded failure reason")
    failedProtocolStatus["reason"] = "unknown-reason"
    expect(NativeStartupStatus.parse(failedProtocolStatus) == nil,
           "the shared startup protocol rejects an unknown failure reason")

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
    for (duration, expectedDelay) in [
        (NSNumber(value: Double.nan), 25.0),
        (NSNumber(value: Double.infinity), 25.0),
        (NSNumber(value: -1), 25.0),
        (NSNumber(value: 50_000), 62.0),
    ] {
        let runtime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
        let presentation = FakeNativePlayerPresentation()
        let delegate = AppDelegate(runtime: runtime, presentation: presentation)
        delegate.receivePlayerMessage(body: ["action": "ready", "duration": duration], isMainFrame: true)
        expect(presentation.schedules.map(\.delay) == [expectedDelay],
               "ready normalizes duration before scheduling its watchdog")
    }
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

    let outOfOrderRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    let outOfOrderPresentation = FakeNativePlayerPresentation()
    let outOfOrderPlayer = AppDelegate(runtime: outOfOrderRuntime, presentation: outOfOrderPresentation)
    outOfOrderPlayer.receivePlayerMessage(body: "complete", isMainFrame: true)
    expect(outOfOrderRuntime.terminated == 0 && outOfOrderPresentation.evaluations.isEmpty,
           "completion before readiness is ignored without ending preview")
    outOfOrderPlayer.receivePlayerMessage(body: "ready", isMainFrame: true)
    outOfOrderPlayer.receivePlayerMessage(body: "complete", isMainFrame: true)
    let outOfOrderCount = outOfOrderPresentation.evaluations.count
    outOfOrderPlayer.receivePlayerMessage(body: "complete", isMainFrame: true)
    expect(outOfOrderPresentation.readyCount == 1 && outOfOrderRuntime.terminated == 1
           && outOfOrderPresentation.evaluations.count == outOfOrderCount,
           "a later ready and completion succeed once despite an earlier completion")

    var closedBeforeReady = NativePlayerProgress()
    closedBeforeReady.markClosed()
    expect(!closedBeforeReady.isReady && closedBeforeReady.isDone,
           "closing before readiness records completion without fabricating readiness")
    closedBeforeReady.markReady()
    expect(closedBeforeReady.isReady && closedBeforeReady.isDone && !closedBeforeReady.acceptCompletion(),
           "late readiness cannot complete a previously closed player twice")
    var progress = NativePlayerProgress()
    expect(!progress.acceptCompletion() && !progress.isReady && !progress.isDone,
           "completion before readiness does not advance player progress")
    progress.markReady()
    expect(progress.acceptCompletion() && !progress.acceptCompletion() && progress.isDone,
           "ready player accepts exactly one completion")

    let failedAfterReadyRuntime = FakeNativeAppRuntime(arguments: ["agent-skin", "--preview"])
    let failedAfterReadyPresentation = FakeNativePlayerPresentation()
    let failedAfterReadyPlayer = AppDelegate(runtime: failedAfterReadyRuntime, presentation: failedAfterReadyPresentation)
    failedAfterReadyPlayer.receivePlayerMessage(body: "ready", isMainFrame: true)
    failedAfterReadyPlayer.receivePlayerMessage(body: "jsError", isMainFrame: true)
    let failedAfterReadyCount = failedAfterReadyPresentation.evaluations.count
    failedAfterReadyPlayer.receivePlayerMessage(body: "complete", isMainFrame: true)
    expect(failedAfterReadyRuntime.terminated == 0
           && failedAfterReadyPresentation.evaluations.count == failedAfterReadyCount
           && failedAfterReadyRuntime.output.contains { $0.contains("javascript-error") },
           "completion after a displayed player failure is ignored")

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
        let deadline = ProcessInfo.processInfo.systemUptime + 5
        while runtime.terminated == 0 && ProcessInfo.processInfo.systemUptime < deadline {
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        expect(runtime.terminated > 0, "the synthetic launcher reaches its terminal callback within the test deadline")
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
            ["href": coldStartupURL, "controllerPresent": false, "shellReady": true],
            ["installed": true, "alreadyActive": false],
            ["href": coldStartupURL, "missing": false, "status": [
                "owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": 31,
                "ready": true, "completed": false, "overlay": true, "reason": "",
                "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
                "completion": NSNull()
            ]],
            ["href": coldStartupURL, "missing": false, "status": [
                "owner": "azhou-codex-startup", "version": 1, "phase": "complete", "runId": 31,
                "ready": true, "completed": true, "overlay": false, "reason": "",
                "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
                "completion": ["cause": "natural", "beforeReady": false]
            ]]
        ], afterEvaluation: { _, index in
            if index == 3 {
                expect(coldTarget.activationCount == 1 && coldRuntime.terminated == 0,
                       "the actual AppDelegate activates at playing readiness and remains alive until completion")
            }
        }
    )
    coldRuntime.startupTransportFactory = { capture, events in
        NativeStartupEventTransport(base: coldTransport, capture: capture, events: events,
                                    now: { coldRuntime.uptime })
    }
    let coldDelegate = AppDelegate(runtime: coldRuntime, presentation: FakeNativePlayerPresentation(), nativeColdLaunch: false)
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
           "cold startup terminates after completion and releases its instance lock")
    expect(eventNames(coldRuntime).contains("startup-installed") && eventNames(coldRuntime).contains("startup-ready")
           && eventNames(coldRuntime).contains("launcher-exit") && coldRuntime.processExitCode == 0,
           "cold startup emits installed, ready, and successful teardown events")

    try Data("native-prepare-entry-fixture".utf8).write(to: coldResources.appendingPathComponent("startup/prepare.js"))
    try FileManager.default.createDirectory(at: coldResources.appendingPathComponent("web"), withIntermediateDirectories: true)
    try Data("<html></html>".utf8).write(to: coldResources.appendingPathComponent("web/index.html"))
    let nativeRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"], resourceURL: coldResources)
    nativeRuntime.uptime = ProcessInfo.processInfo.systemUptime
    nativeRuntime.allocatedPort = 49221
    nativeRuntime.installedTargetURL = syntheticCodex
    nativeRuntime.applications = [retiredTarget]
    nativeRuntime.openedApplication = coldTarget
    nativeRuntime.startupTargetSystem = FakeStartupSystem(expectedPID: 45, ports: [49221])
    let nativeWorld = StartupSnapshotWorld(); nativeWorld.preparedMode = true
    let nativeTransport = PreparedConnectorTransport(nativeWorld)
    let nativeCandidatePresentation = FakeNativePlayerPresentation()
    nativeCandidatePresentation.coverHook = { nativeWorld.runNonce = $0 }
    nativeRuntime.beforeOpenCompletion = {
        expect(nativeCandidatePresentation.nativeCoverCount == 1, "actual AppDelegate opens host only after cover receipt")
        nativeRuntime.applications = [coldTarget]
    }
    nativeRuntime.startupTransportFactory = { capture, events in
        NativeStartupEventTransport(base: nativeTransport, capture: capture, events: events, now: { nativeRuntime.uptime })
    }
    nativeCandidatePresentation.evaluationHook = { source in
        if source.contains("finishNativeSnapshot") {
            nativeCandidatePresentation.nativeHandler?.receive(body: ["action": "ready", "runId": nativeWorld.runNonce,
                "duration": 12000], isMainFrame: true)
        } else if source == "window.launcherUI.beginLaunch()" {
            nativeCandidatePresentation.nativeHandler?.receive(body: ["action": "complete", "runId": nativeWorld.runNonce,
                "skipped": false], isMainFrame: true)
        }
        return (true, nil)
    }
    let nativeDelegate = AppDelegate(runtime: nativeRuntime, presentation: nativeCandidatePresentation)
    nativeDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(nativeRuntime)
    nativeDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(nativeTransport.world.submittedInstall?.contains("native-prepare-entry-fixture") == true
        && nativeTransport.world.submittedInstall?.contains("test-only-probe") == false,
        "actual AppDelegate selects fixed prepare.js rather than legacy page-player payload: \(nativeRuntime.output.joined(separator: " | "))")
    expect(nativeRuntime.openCount == 1 && nativeRuntime.processExitCode == 0
        && nativeCandidatePresentation.nativeCoverCount == 1 && nativeCandidatePresentation.createdPlayers.count == 1
        && nativeCandidatePresentation.orderedOutCount == 1 && nativeRuntime.acquiredLock?.releaseCount == 1,
        "native AppDelegate consumer finishes and releases its cover and single-instance lease")
    expect(eventNames(nativeRuntime).contains("startup-native-result")
        && !eventNames(nativeRuntime).contains("startup-ready"), "actual native consumer uses dedicated native evidence")
    let nativeEvents = nativeRuntime.output.compactMap { line -> [String: Any]? in
        guard let data = line.data(using: .utf8) else { return nil }
        return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
    }
    let nativeResult = nativeEvents.first { $0["event"] as? String == "startup-native-result" }
    let nativeExit = nativeEvents.first { $0["event"] as? String == "launcher-exit" }
    let nativeWorkspace = nativeResult?["workspace"] as? [String: Any]
    let nativeCover = nativeResult?["cover"] as? [String: Any]
    expect(nativeResult?["runNonce"] as? String == nativeWorld.runNonce
        && nativeExit?["runNonce"] as? String == nativeWorld.runNonce
        && nativeResult?["targetPID"] as? Int == 45 && nativeExit?["targetPID"] as? Int == 45
        && nativeCover?["runNonce"] as? String == nativeWorld.runNonce
        && nativeCover?["drawCommitted"] as? Bool == true
        && nativeWorkspace?["runNonce"] as? String == nativeWorld.runNonce
        && nativeWorkspace?["runId"] as? Int == 1
        && nativeResult?["visualContinuity"] as? String == "not-measured",
        "native event and exit preserve actual run, target, cover and workspace receipts without visual claims")

    let missingPayloadRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"])
    missingPayloadRuntime.installedTargetURL = syntheticCodex
    missingPayloadRuntime.startupTargetSystem = FakeStartupSystem(expectedPID: 45, ports: [45678])
    let missingPayloadDelegate = AppDelegate(runtime: missingPayloadRuntime, presentation: FakeNativePlayerPresentation(), nativeColdLaunch: false)
    missingPayloadDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(missingPayloadRuntime)
    missingPayloadDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(missingPayloadRuntime.openCount == 0 && missingPayloadRuntime.terminated == 1
           && missingPayloadRuntime.processExitCode == 1
           && eventNames(missingPayloadRuntime).contains("startup-failed"),
           "cold startup refuses a missing packaged payload before opening the target")

    let missingTargetRuntime = FakeNativeAppRuntime(arguments: ["agent-skin"])
    missingTargetRuntime.bundleURL = URL(fileURLWithPath: "/Applications/ChatGPT.app")
    AppDelegate(runtime: missingTargetRuntime, presentation: FakeNativePlayerPresentation(), nativeColdLaunch: false)
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

    let linkedResourceRoot = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-linked-resource-" + UUID().uuidString, isDirectory: true)
    let outsideStartup = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-outside-payload-" + UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: linkedResourceRoot); try? FileManager.default.removeItem(at: outsideStartup) }
    try FileManager.default.createDirectory(at: linkedResourceRoot, withIntermediateDirectories: true)
    try FileManager.default.createDirectory(at: outsideStartup, withIntermediateDirectories: true)
    try Data("synthetic-external-payload".utf8).write(to: outsideStartup.appendingPathComponent("install.js"))
    try FileManager.default.createSymbolicLink(at: linkedResourceRoot.appendingPathComponent("startup"),
                                               withDestinationURL: outsideStartup)
    let (linkedPayloadRuntime, _, _) = makeColdRuntime(pid: 491, resourceURL: linkedResourceRoot)
    linkedPayloadRuntime.startupTransportFactory = { _, _ in FakeStartupTransport(pages: [], evaluations: []) }
    let linkedPayloadDelegate = AppDelegate(runtime: linkedPayloadRuntime, presentation: FakeNativePlayerPresentation(), nativeColdLaunch: false)
    linkedPayloadDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(linkedPayloadRuntime)
    let linkedFailure = linkedPayloadRuntime.output.compactMap { line -> [String: Any]? in
        guard let data = line.data(using: .utf8) else { return nil }
        return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    }.first { $0["event"] as? String == "startup-failed" }
    expect(linkedPayloadRuntime.openCount == 0 && linkedFailure?["reason"] as? String == "asset-invalid",
           "a startup directory symlink is rejected as an invalid asset before opening the target")

    let boundedRoot = FileManager.default.temporaryDirectory
        .appendingPathComponent("agent-skin-payload-bounds-" + UUID().uuidString, isDirectory: true)
        .resolvingSymlinksInPath().standardizedFileURL
    defer { try? FileManager.default.removeItem(at: boundedRoot) }
    let boundedDirectory = boundedRoot.appendingPathComponent("startup", isDirectory: true)
    let boundedFile = boundedDirectory.appendingPathComponent("install.js")
    let prepareFile = boundedDirectory.appendingPathComponent("prepare.js")
    try FileManager.default.createDirectory(at: boundedDirectory, withIntermediateDirectories: true)
    try Data("fixture-payload".utf8).write(to: boundedFile)
    expect(StartupPayloadReader.read(from: boundedRoot) == "fixture-payload", "bounded payload reader accepts normal UTF-8 bytes")
    expect(StartupPayloadReader.read(from: boundedRoot, kind: .nativePrepare) == nil,
           "an older package without prepare.js is rejected instead of falling back to install.js")
    try Data("fixture-native-prepare".utf8).write(to: prepareFile)
    expect(StartupPayloadReader.read(from: boundedRoot, kind: .nativePrepare) == "fixture-native-prepare",
           "bounded payload reader accepts the explicitly selected prepare.js resource")
    var interruptedReads = 0
    let retriedPayload = StartupPayloadReader.read(from: boundedRoot) { descriptor, buffer, count in
        if interruptedReads == 0 { interruptedReads += 1; errno = EINTR; return -1 }
        return Darwin.read(descriptor, buffer, min(count, 2))
    }
    expect(retriedPayload == "fixture-payload" && interruptedReads == 1,
           "bounded payload reader retries EINTR and assembles short reads")
    let failedPayload = StartupPayloadReader.read(from: boundedRoot) { _, _, _ in errno = EIO; return -1 }
    expect(failedPayload == nil && (try? Data(contentsOf: boundedFile)) == Data("fixture-payload".utf8),
           "bounded payload reader refuses an I/O error without changing the source")
    let savedPayload = boundedDirectory.appendingPathComponent("saved-original.js")
    var replacementError: Error?, replaced = false
    let changedPayload = StartupPayloadReader.read(from: boundedRoot) { descriptor, buffer, count in
        let received = Darwin.read(descriptor, buffer, count)
        if received > 0 && !replaced {
            do {
                try FileManager.default.moveItem(at: boundedFile, to: savedPayload)
                try Data("foreign-payload".utf8).write(to: boundedFile)
                replaced = true
            } catch { replacementError = error }
        }
        return received
    }
    expect(replacementError == nil && replaced && changedPayload == nil,
           "bounded payload reader rejects a file replaced while reading")
    expect((try? Data(contentsOf: savedPayload)) == Data("fixture-payload".utf8)
           && (try? Data(contentsOf: boundedFile)) == Data("foreign-payload".utf8),
           "the replaced and replacement payloads remain available for review")
    try FileManager.default.removeItem(at: savedPayload)
    try Data("fixture-payload".utf8).write(to: boundedFile)
    let savedPrepare = boundedDirectory.appendingPathComponent("saved-prepare-original.js")
    var prepareReplacementError: Error?, prepareReplaced = false
    let changedPrepare = StartupPayloadReader.read(from: boundedRoot, kind: .nativePrepare) { descriptor, buffer, count in
        let received = Darwin.read(descriptor, buffer, count)
        if received > 0 && !prepareReplaced {
            do {
                try FileManager.default.moveItem(at: prepareFile, to: savedPrepare)
                try Data("foreign-native-prepare".utf8).write(to: prepareFile)
                prepareReplaced = true
            } catch { prepareReplacementError = error }
        }
        return received
    }
    expect(prepareReplacementError == nil && prepareReplaced && changedPrepare == nil,
           "the selected prepare.js path is rechecked after reading and replacement is rejected")
    expect((try? Data(contentsOf: savedPrepare)) == Data("fixture-native-prepare".utf8)
           && (try? Data(contentsOf: prepareFile)) == Data("foreign-native-prepare".utf8),
           "prepare.js replacement leaves both original and replacement available for review")
    try FileManager.default.removeItem(at: savedPrepare)
    try Data("fixture-native-prepare".utf8).write(to: prepareFile)
    var growthError: Error?, grew = false, readBytes = 0
    let grownPayload = StartupPayloadReader.read(from: boundedRoot) { descriptor, buffer, count in
        let received = Darwin.read(descriptor, buffer, count)
        if received > 0 {
            readBytes += received
            if !grew {
                do {
                    let writer = try FileHandle(forWritingTo: boundedFile)
                    try writer.seekToEnd()
                    try writer.write(contentsOf: Data(repeating: 0x42, count: 24 * 1024 * 1024))
                    try writer.close()
                    grew = true
                } catch { growthError = error }
            }
        }
        return received
    }
    expect(growthError == nil && grew && grownPayload == nil && readBytes <= 24 * 1024 * 1024,
           "bounded payload reader rejects a file that grows past its limit without reading beyond the bound")
    try Data().write(to: boundedFile)
    expect(StartupPayloadReader.read(from: boundedRoot) == nil, "bounded payload reader rejects an empty file")
    try Data([0xff, 0xfe]).write(to: boundedFile)
    expect(StartupPayloadReader.read(from: boundedRoot) == nil, "bounded payload reader rejects invalid UTF-8")
    try FileManager.default.removeItem(at: boundedFile)
    try FileManager.default.createSymbolicLink(at: boundedFile, withDestinationURL: startupPayloadURL)
    expect(StartupPayloadReader.read(from: boundedRoot) == nil, "bounded payload reader rejects a file symlink")
    try FileManager.default.removeItem(at: boundedFile)
    expect(mkfifo(boundedFile.path, 0o600) == 0, "synthetic payload FIFO was created")
    expect(StartupPayloadReader.read(from: boundedRoot) == nil, "bounded payload reader rejects a FIFO without waiting for a writer")
    try FileManager.default.removeItem(at: boundedFile)

    try FileManager.default.removeItem(at: prepareFile)
    try FileManager.default.createSymbolicLink(at: prepareFile, withDestinationURL: startupPayloadURL)
    expect(StartupPayloadReader.read(from: boundedRoot, kind: .nativePrepare) == nil,
           "the selected prepare.js path rejects a symlink without falling back to install.js")
    try FileManager.default.removeItem(at: prepareFile)
    expect(mkfifo(prepareFile.path, 0o600) == 0, "synthetic prepare FIFO was created")
    expect(StartupPayloadReader.read(from: boundedRoot, kind: .nativePrepare) == nil,
           "the selected prepare.js path rejects a FIFO without waiting for a writer")
    try FileManager.default.removeItem(at: prepareFile)

    try FileManager.default.createDirectory(at: boundedFile, withIntermediateDirectories: false)
    expect(StartupPayloadReader.read(from: boundedRoot) == nil, "bounded payload reader rejects a directory")
    try FileManager.default.removeItem(at: boundedFile)
    let allowedSize = 24 * 1024 * 1024 - 1
    try Data(repeating: 0x41, count: allowedSize).write(to: boundedFile)
    expect(StartupPayloadReader.read(from: boundedRoot)?.utf8.count == allowedSize,
           "bounded payload reader accepts one byte below its exclusive limit")
    let oversizedHandle = try FileHandle(forWritingTo: boundedFile)
    try oversizedHandle.truncate(atOffset: UInt64(allowedSize + 1))
    try oversizedHandle.close()
    expect(StartupPayloadReader.read(from: boundedRoot) == nil,
           "bounded payload reader rejects the exclusive size limit")

    try Data().write(to: prepareFile)
    let oversizedPrepareHandle = try FileHandle(forWritingTo: prepareFile)
    try oversizedPrepareHandle.truncate(atOffset: UInt64(24 * 1024 * 1024))
    try oversizedPrepareHandle.close()
    expect(StartupPayloadReader.read(from: boundedRoot, kind: .nativePrepare) == nil,
           "the selected prepare.js path rejects the exclusive size limit")

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
    let emptyPayloadDelegate = AppDelegate(runtime: emptyPayloadRuntime, presentation: FakeNativePlayerPresentation(), nativeColdLaunch: false)
    emptyPayloadDelegate.applicationDidFinishLaunching(Notification(name: NSApplication.didFinishLaunchingNotification))
    try await settleLaunch(emptyPayloadRuntime)
    emptyPayloadDelegate.applicationWillTerminate(Notification(name: NSApplication.willTerminateNotification))
    expect(emptyPayloadRuntime.openCount == 0 && emptyPayloadRuntime.terminated == 1
           && eventNames(emptyPayloadRuntime).contains("startup-failed"),
           "cold startup rejects an empty packaged payload before opening the target")

    func runConfiguredStartup(_ runtime: FakeNativeAppRuntime) async throws {
        let delegate = AppDelegate(runtime: runtime, presentation: FakeNativePlayerPresentation(), nativeColdLaunch: false)
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
                                    nativeStartup: nil,
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
// The contract string is frozen under its historical ZCode-era name; see
// SkinHostContract.version for the provenance note.

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

    func applicationKey(bundle: String = "/Applications/Codex.app",
                        executable: String = "/Applications/Codex.app/Contents/MacOS/Codex",
                        identifier: String = "com.openai.codex",
                        sha: String = "codex-executable-sha") -> HostApplicationKey {
        HostApplicationKey(host: .codex, bundleURL: URL(fileURLWithPath: bundle).resolvingSymlinksInPath().standardizedFileURL,
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
    func dependencies(codex: ((BoundHostInputs) -> any SkinHostDriver)? = nil) -> SkinAssemblyDependencies {
        SkinAssemblyDependencies(
            inspectIdentity: { _, _ in .observed(identity()) },
            capabilityEvidence: { verifiedCodexFindings($0.key) },
            makeCodexDriver: codex ?? { _ in
                codexDrivers += 1
                return PlaceholderSkinHostDriver(inputs: nil)
            })
    }
    if case .unavailable(let refusal) = SkinHostFactory.make(
        host: .codex, expectedApplication: otherApplication, observed: identity(codexKey),
        findings: [], contractVersion: contractVersion, dependencies: dependencies()) {
        expect(refusal.reason == .identityMismatch && refusal.host == .codex,
               "a factory refuses an expected application that differs from the observed identity")
    } else { fatalError("FAILED: mismatched application must not assemble a driver") }

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

    // Factory step 5: a Codex assembly binds the driver to immutable bound inputs.
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
         "ready": ready, "completed": phase == "complete", "overlay": phase != "complete", "reason": "",
         "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
         "completion": phase == "complete" ? ["cause": "natural", "beforeReady": false] : NSNull()]
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
            ["href": installURL, "controllerPresent": false, "shellReady": true],
            ["installed": true, "alreadyActive": false],
            ["href": installURL, "missing": false, "status": statusBody(runID: 7, phase: "complete", ready: true)],
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
            ["href": installURL, "controllerPresent": false, "shellReady": true],
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
            ["href": installURL, "controllerPresent": false, "shellReady": true],
            ["installed": true, "alreadyActive": false],
            ["href": installURL, "missing": false, "status": statusBody(runID: 11, phase: "complete", ready: true)],
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
            ["href": installURL, "controllerPresent": false, "shellReady": true],
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
        expect(startupLegacyOutcome(from: .refused(HostRefusal(host: .codex, reason: reason,
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
            ["href": installURL, "controllerPresent": false, "shellReady": true],
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
                                               ["href": installURL, "controllerPresent": false, "shellReady": true],
                                               ["installed": true, "alreadyActive": false],
                                               ["href": installURL, "missing": false,
                                                "status": statusBody(runID: 12, phase: "complete", ready: true)],
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
        if source.contains("controllerPresent") { return ["href": "app://-/index.html?initialRoute=%2F", "controllerPresent": false, "shellReady": true] }
        return [:]
    }
    func close() {}
}
#endif

// Pins the production NSWorkspace launch configuration: the Codex daily launch
// keeps its inherited environment, never activates and always carries the
// loopback debugging arguments.
@MainActor
private func codexLaunchConfigurationChecks() -> Int {
    var checks = 0
    func expect(_ value: Bool, _ message: String) { precondition(value, message); checks += 1 }
    var captured: NSWorkspace.OpenConfiguration?
    let system = SystemNativeAppRuntime(openApplication: { _, config, done in captured = config; done(nil, nil) })
    system.openApplication(at: URL(fileURLWithPath: "/synthetic/Codex.app"), debuggingPort: 12345) { _, _ in }
    expect(captured?.environment == NSWorkspace.OpenConfiguration().environment && captured?.activates == false
           && captured?.arguments == ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=12345"],
           "Codex launches keep their default environment, inactive activation and debugging arguments")
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
                  status(phase: "playing", ready: true, completed: true, completion: ["cause": "natural", "beforeReady": false]),
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
    for declaration: Any in ["dsh", "unknown", 1, true] {
        expect(NativeEntryIdentity.host(bundleIdentifier: "local.azhou.codex-startup", declaredHost: declaration) == nil,
               "Codex entry refuses another host or non-string declaration")
    }
    expect(NativeEntryIdentity.host(bundleIdentifier: "other.launcher", declaredHost: "codex") == nil,
           "declaring Codex cannot authorize a different bundle")
    return checks
}

// An executable transport fixture: production URLSession discovery, CDP codec,
// connector, install recorder and event capture; only HTTP/socket/host boundaries
// are synthetic. All document generations deliberately start at runID 1.
private final class StartupReplacementWorld: @unchecked Sendable {
    static let deadline: TimeInterval = 45
    let stage: String
    let mode: String
    let readyOverlap: Bool
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
    private(set) var candidateActionsWhileOldListed: [String] = []
    private(set) var requestIDs: [Int] = []
    private(set) var sockets: [StartupReplacementSocket] = []
    private(set) var lockAcquires = 0
    private(set) var lockReleases = 0
    private(set) var requestsLocked = true
    var cancel: (() -> Void)?
    private var lagReadsLeft = 0
    private var waitReads = 0
    private var recheckReads = 0
    private var inspectReads: [String: Int] = [:]
    private var oldListed = true
    init(stage: String, mode: String = "replace", handshakeStatus: Int? = nil, readyOverlap: Bool = false) {
        self.stage = stage; self.mode = mode
        self.readyOverlap = readyOverlap
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
        let entries = try pageEntries()
        oldListed = entries.contains { $0["id"] as? String == "page-a" }
        return entries
    }
    private func pageEntries() throws -> [[String: Any]] {
        func entry(_ id: String, type: String = "page", url: String? = nil) -> [String: Any] {
            ["id": id, "type": type, "url": url ?? href,
             "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/\(id)"]
        }
        if generation == 0 { return [entry("page-a")] }
        if readyOverlap {
            waitReads += 1
            if waitReads <= 3 {
                var old = entry("page-a")
                if mode == "old-socket-drift" { old["webSocketDebuggerUrl"] = "ws://127.0.0.1:49221/devtools/page/other" }
                return [old, entry("page-b")]
            }
        }
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
        lock.lock()
        if socket.id != "page-a", oldListed { candidateActionsWhileOldListed.append(socket.id + ":connect") }
        sockets.append(socket); lock.unlock()
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
        if id != "page-a", oldListed { candidateActionsWhileOldListed.append("\(id):\(operation)") }
        requestsLocked = requestsLocked && lockHeld
        if operation == "inspect" { inspectReads[id, default: 0] += 1 }
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
        if mode == "shell-replace", id == "page-a", operation == "inspect" {
            if inspectReads[id] == 2 { generation += 1 }
            if inspectReads[id] == 3 { throw URLError(.networkConnectionLost) }
        }
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
            case "deadline": clock = Self.deadline; throw URLError(.networkConnectionLost)
            case "before-install": break
            case "cancel-ready-list": terminal = "ready-replaced"
            case "ready-replaced", "complete-replaced", "skip-replaced", "failed-replaced", "disposed-replaced", "run-drift": terminal = mode
            case "ready-blip", "recheck-once": terminal = "ready-replaced"
            case "complete-blip": terminal = "complete-replaced"
            default:
                if readyOverlap { terminal = "ready-replaced" }
                else { throw URLError(.networkConnectionLost) }
            } }
        }
        if mode.hasPrefix("recheck-"), generation > 0 { terminal = "ready-replaced" }
        let value: [String: Any]
        switch operation {
        case "inspect": value = ["href": href, "controllerPresent": id == "page-b" && mode == "already-present",
                                  "shellReady": mode != "shell-replace" || id != "page-a" && inspectReads[id, default: 0] > 1]
        case "install":
            installReplyTimes[id] = clock
            value = mode == "missing-new-receipt" && id == "page-b" ? ["installed": "invalid"]
                : ["installed": true, "alreadyActive": id == "page-b" && mode == "already-active"]
        case "status":
            if mode.hasPrefix("recheck-"), recheckReads > 1 {
                if ["recheck-controller", "recheck-missing"].contains(mode) { return try data(envelope(["href": href, "missing": true])) }
                if mode == "recheck-href" { return try data(envelope(["href": "app://-/index.html?initialRoute=settings", "missing": false])) }
                if mode == "recheck-schema" { return try data(envelope(["href": href, "missing": false, "status": ["owner": "foreign"]])) }
                if ["recheck-once", "recheck-lost", "recheck-connect", "recheck-complete"].contains(mode) { terminal = "complete-replaced" }
                if mode == "recheck-skip" { terminal = "skip-replaced" }
                if mode == "recheck-failed" { terminal = "failed-replaced" }
                if mode == "recheck-disposed" { terminal = "disposed-replaced" }
                if mode == "recheck-run" { terminal = "run-drift" }
            }
            let timedOut = mode == "recheck-timeout" && recheckReads > 1
            let completed = ["complete-replaced", "skip-replaced"].contains(terminal ?? "")
                || id != "page-a"
            let failed = terminal == "failed-replaced"
            let disposed = terminal == "disposed-replaced"
            let ready = id != "page-a" || mode == "after-ready"
                || ["ready-replaced", "complete-replaced", "run-drift"].contains(terminal ?? "")
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
    private var heldWaiters: [CheckedContinuation<Void, Never>] = []
    var isHoldingReference: Bool { referenceLock.lock(); defer { referenceLock.unlock() }; return heldReference != nil }
    func waitUntilHeldReference() async {
        await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
            referenceLock.lock()
            if heldReference != nil {
                referenceLock.unlock()
                continuation.resume()
            } else {
                heldWaiters.append(continuation)
                referenceLock.unlock()
            }
        }
    }
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
                referenceLock.lock()
                heldReference = (continuation, reply)
                let waiters = heldWaiters
                heldWaiters = []
                referenceLock.unlock()
                waiters.forEach { $0.resume() }
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
                                        diagnostics enabled: Bool = false, handshakeStatus: Int? = nil,
                                        readyOverlap: Bool = false) async throws -> [String: Any] {
    let world = StartupReplacementWorld(stage: stage, mode: mode, handshakeStatus: handshakeStatus, readyOverlap: readyOverlap)
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
        var presentationPages: [String] = []
        let transport = InstallObservingStartupTransport(
            base: NativeStartupEventTransport(base: base, capture: capture, events: events, now: world.time), recorder: recorder)
        let target = StartupTargetFacts(pid: 4123, bundle: URL(fileURLWithPath: "/synthetic/Codex.app"),
            executable: URL(fileURLWithPath: "/synthetic/Codex.app/Contents/MacOS/Codex"),
            bundleID: "com.openai.codex", launchTime: mode == "missing-launch" ? nil : 100)
        let outcome = await StartupConnector(target: target, expectedPort: 49221, system: StartupReplacementSystem(world),
            transport: transport, diagnostics: enabled ? { _, fields in diagnosticRecords.append(fields) } : nil,
            onReady: { presentationPages.append(capture.snapshot().pageID ?? "") },
            now: world.time, sleep: {
                world.advance($0)
                if mode == "recheck-cancel-wait", world.recheckCount() > 0 { withUnsafeCurrentTask { $0?.cancel() } }
            })
            .run(payload: "test-only-probe", deadline: StartupReplacementWorld.deadline)
        let observation = capture.snapshot()
        let final = events.resolve(outcome, observation: observation, at: world.time())
        return ["stage": stage, "mode": mode, "recovered": outcome == .ready(runID: 1) && final == .ready,
            "outcome": String(describing: outcome), "final": String(describing: final),
            "installs": world.installs, "installSentCount": recorder.installSentCount, "disposedControllers": world.disposedControllers,
            "requests": world.requests, "requestIDs": world.requestIDs,
            "connections": world.sockets.map(\.id), "socketCloses": world.sockets.map(\.canceled),
            "candidateActionsWhileOldListed": world.candidateActionsWhileOldListed,
            "lockAcquires": world.lockAcquires, "lockReleases": world.lockReleases, "requestsLocked": world.requestsLocked,
            "currentPageID": observation.pageID ?? "", "installedAt": observation.installedAt ?? -1,
            "completed": observation.status?.completed ?? false,
            "presentationPages": presentationPages,
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
    await held?.waitUntilHeldReference()
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
    let afterReady = try await startupReplacementScenario(stage: "status", mode: "after-ready")
    expect(afterReady["recovered"] as? Bool == true && afterReady["currentPageID"] as? String == "page-b"
        && afterReady["completed"] as? Bool == true,
        "a playing page replaced after readiness must complete on the proven successor before handoff")
    expect(afterReady["presentationPages"] as? [String] == ["page-a", "page-b"],
        "presentation gets readiness before page replacement and the successor completes independently")
    let overlap = try await startupReplacementScenario(stage: "status", mode: "after-ready", diagnostics: true, readyOverlap: true)
    expect(overlap["recovered"] as? Bool == true && overlap["currentPageID"] as? String == "page-b"
        && overlap["completed"] as? Bool == true && overlap["installs"] as? [String: Int] == ["page-a": 1, "page-b": 1],
        "a playing old page overlapping its successor must wait for retirement and complete on the successor")
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
    common(overlap)
    let gatedReplacement = try await startupReplacementScenario(stage: "never", mode: "shell-replace", diagnostics: true, readyOverlap: true)
    common(gatedReplacement)
    expect(gatedReplacement["recovered"] as? Bool == true && gatedReplacement["installs"] as? [String: Int] == ["page-b": 1]
        && (gatedReplacement["requests"] as? [String] ?? []).filter { $0 == "page-b:inspect" }.count == 2
        && gatedReplacement["candidateActionsWhileOldListed"] as? [String] == [],
        "a temporary page loses its connection before installation and the uniquely proven successor waits for its own shell before one playback")
    let overlapProofs = (overlap["diagnostics"] as? [[String: Any]] ?? []).filter { $0["stage"] as? String == "proof" }
    expect(overlapProofs.compactMap { $0["oldIDPresent"] as? Bool } == [true, true, false]
        && overlap["candidateActionsWhileOldListed"] as? [String] == []
        && overlap["disposedControllers"] as? [String] == []
        && overlap["presentationPages"] as? [String] == ["page-a", "page-b"],
        "overlap performs only retirement proof until the old ID disappears and each page supplies its own readiness")
    for (mode, reason) in [("persist", "attach-timeout"), ("old-socket-drift", "ambiguous-main-page")] {
        let r = try await startupReplacementScenario(stage: "status", mode: mode, diagnostics: true, readyOverlap: true); common(r)
        expect(r["outcome"] as? String == "failed(reason: \"\(reason)\")"
            && r["connections"] as? [String] == ["page-a"] && r["installs"] as? [String: Int] == ["page-a": 1]
            && r["candidateActionsWhileOldListed"] as? [String] == [] && (r["elapsed"] as? Double ?? 99) <= StartupReplacementWorld.deadline + 0.1,
            "\(mode) cannot use a playing overlap to bypass the selected socket, retirement or deadline boundaries")
    }
    let terminalOverlap = try await startupReplacementScenario(stage: "status", mode: "complete-replaced", diagnostics: true, readyOverlap: true)
    common(terminalOverlap)
    expect(terminalOverlap["outcome"] as? String == "partial(reason: \"startup-interrupted\")"
        && terminalOverlap["connections"] as? [String] == ["page-a"]
        && terminalOverlap["installs"] as? [String: Int] == ["page-a": 1]
        && !(terminalOverlap["diagnostics"] as? [[String: Any]] ?? []).contains { $0["stage"] as? String == "proof" },
        "a completed run cannot enter retirement proof or replay even while the old and new pages overlap")
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
        && (permanent["elapsed"] as? Double ?? 99) <= StartupReplacementWorld.deadline && (permanent["recheckReads"] as? Int ?? 0) > 1
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
                && (r["elapsed"] as? Double ?? 0) >= StartupReplacementWorld.deadline
                && (r["elapsed"] as? Double ?? 99) <= StartupReplacementWorld.deadline + 0.1,
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

private func startupIdentityDiagnosticChecks() -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        precondition(condition(), label); checks += 1
    }

    // The diagnostics policy is opt-in through exactly one environment value.
    expect(StartupDiagnosticsPolicy.isEnabled(environment: ["AZHOU_STARTUP_DIAGNOSTICS": "1"]),
           "startup diagnostics opt in through AZHOU_STARTUP_DIAGNOSTICS=1")
    expect(!StartupDiagnosticsPolicy.isEnabled(environment: ["AZHOU_STARTUP_DIAGNOSTICS": "0"]),
           "startup diagnostics stay off for other values")
    expect(!StartupDiagnosticsPolicy.isEnabled(environment: [:]),
           "startup diagnostics default to off")

    // Without a sink the diagnostic stays inert and still passes values through.
    var inert = StartupIdentityDiagnostic("probe", pid: 42, at: 10, diagnostics: nil)
    expect(inert.check("identity", true), "checks report their value without a sink")
    expect(inert.present("bundle", URL(fileURLWithPath: "/tmp/synthetic") as URL?) != nil,
           "present yields the observed value without a sink")
    expect(inert.present("absent", nil as String?) == nil, "present passes nil through")
    expect(inert.processIdentifier(77) == 77, "process identifier passes through without a sink")
    inert.finish("refused", error: nil) // Must not crash without a sink.

    // With a sink every tap lands in one bounded record and finish decorates it.
    var records: [[String: Any]] = []
    var diagnosed = StartupIdentityDiagnostic("open", pid: 700, at: 5,
                                              diagnostics: { records.append($1) })
    expect(diagnosed.check("bundle-identity", true), "identity check reports true")
    expect(!diagnosed.check("page-supported", false), "a failing check reports false")
    expect(diagnosed.present("main-page", "https://synthetic.invalid" as String?) == "https://synthetic.invalid",
           "present yields the observed page")
    expect(diagnosed.processIdentifier(701) == 701, "the latest process identifier tap wins")
    diagnosed.finish("verified", error: nil)
    expect(records.count == 1, "finish emits exactly one diagnostic record")
    var record = records.last ?? [:]
    expect((record["stage"] as? String) == "target-identity", "records carry the target-identity stage")
    expect((record["checkpoint"] as? String) == "open", "records carry the checkpoint")
    expect((record["pid"] as? Int32) == 701, "records carry the latest process identifier")
    expect((record["pidObserved"] as? Bool) == true, "finish reports whether a pid was observed")
    expect((record["outcome"] as? String) == "verified", "records carry the outcome")

    // Errors are reduced to domain/code plus the failure taxonomy, never payloads.
    records.removeAll()
    var failing = StartupIdentityDiagnostic("swap", at: 6, diagnostics: { records.append($1) })
    failing.check("signature", false)
    let transport = StartupTransportError(domain: "transport-fixture", code: 7, httpStatus: 503)
    failing.finish("aborted", error: StartupFailure(reason: "listener-mismatch", message: "synthetic",
                                                    transportError: transport))
    record = records.last ?? [:]
    expect(records.count == 1 && (record["outcome"] as? String) == "aborted",
           "the failing path also emits exactly one bounded record")
    expect((record["errorDomain"] as? String)?.isEmpty == false,
           "startup failures reduce to a non-empty error domain")
    expect(record["errorCode"] != nil, "startup failures reduce to an error code")
    expect((record["reason"] as? String) == "listener-mismatch", "startup failures record their reason")
    expect(record["state"] == nil, "a startup failure carries no wallpaper state")
    expect((record["pidObserved"] as? Bool) == false, "no pid tap keeps pidObserved false")

    records.removeAll()
    let wallpaperFailure = WallpaperFailure(state: "page-missing", chinese: "合成失败。", english: "Synthetic failure.",
                                            transportError: nil, retryableListFailure: false, httpStatus: nil)
    var stateDiagnosed = StartupIdentityDiagnostic("swap", at: 7, diagnostics: { records.append($1) })
    stateDiagnosed.check("signature", false)
    stateDiagnosed.finish("aborted", error: wallpaperFailure)
    record = records.last ?? [:]
    expect((record["state"] as? String) == "page-missing", "wallpaper failures record their state")
    expect(record["errorDomain"] as? String != nil, "wallpaper failures still reduce to domain and code")

    return checks
}

private func launcherCommandLineChecks() -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        precondition(condition(), label); checks += 1
    }
    let full = LauncherCommandLine(arguments: ["launcher", "--preview", "--snapshot", "/tmp/synth", "--probe"])
    expect(full.value(after: "--snapshot") == "/tmp/synth",
           "value(after:) returns the argument following the flag")
    expect(full.value(after: "--missing") == nil,
           "value(after:) returns nil for an absent flag")
    let trailing = LauncherCommandLine(arguments: ["launcher", "--snapshot"])
    expect(trailing.value(after: "--snapshot") == nil,
           "value(after:) returns nil when the flag has no follower")
    expect(full.snapshotDirectory == "/tmp/synth", "snapshot directory parses from its flag")
    expect(full.snapshotTimes == "0.4,1.4,2.3,3.5,5.5,7.3", "snapshot times keep their default cadence")
    let bare = LauncherCommandLine(arguments: ["launcher"])
    expect(bare.snapshotDirectory == nil,
           "snapshot directories stay absent without their flags")
    return checks
}

@MainActor private func hostApplicationKeyChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        precondition(condition(), label); checks += 1
    }

    func makeSyntheticKeyBundle(bundleIdentifier: String, declaredHost: String?, executableName: String)
        throws -> (bundle: URL, executable: URL, payload: Data) {
        let bundle = FileManager.default.temporaryDirectory
            .appendingPathComponent("Synthetic Key Host-" + UUID().uuidString + ".app", isDirectory: true)
        let executable = bundle.appendingPathComponent("Contents/MacOS/" + executableName)
        try FileManager.default.createDirectory(at: executable.deletingLastPathComponent(), withIntermediateDirectories: true)
        let payload = Data("#!/bin/sh\nexit 0\n".utf8)
        try payload.write(to: executable)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: executable.path)
        var info: [String: Any] = ["CFBundleIdentifier": bundleIdentifier, "CFBundlePackageType": "APPL",
                                   "CFBundleExecutable": executableName]
        if let declaredHost { info["AzhouTargetHost"] = declaredHost }
        try PropertyListSerialization.data(fromPropertyList: info, format: .xml, options: 0)
            .write(to: bundle.appendingPathComponent("Contents/Info.plist"))
        return (bundle, executable, payload)
    }

    let system = TrustedLaunchSession()

    let (codexLauncher, _, _) = try makeSyntheticKeyBundle(
        bundleIdentifier: "local.azhou.codex-startup", declaredHost: "codex", executableName: "Launcher")
    defer { try? FileManager.default.removeItem(at: codexLauncher) }
    let codexIdentity = LauncherIdentity(bundleURL: codexLauncher)
    expect(codexIdentity.host == .codex && codexIdentity.targetBundleID == "com.openai.codex",
           "the codex launcher bundle resolves its host and target identity")

    let (targetBundle, targetExecutable, _) = try makeSyntheticKeyBundle(
        bundleIdentifier: "com.openai.codex", declaredHost: nil, executableName: "Codex")
    defer { try? FileManager.default.removeItem(at: targetBundle) }
    guard let codexKey = system.hostApplicationKey(for: targetBundle, identity: codexIdentity) else {
        preconditionFailure("FAILED: the verified codex target yields its application key")
    }
    expect(codexKey.bundleIdentifier == "com.openai.codex", "the key carries the target bundle identifier")
    expect(codexKey.executableURL == PathCanonicalization.resolved(targetExecutable),
           "the key pins the canonical executable URL")
    expect(codexKey.executableSHA256.isEmpty,
           "the codex branch leaves the executable digest to its codesign path")

    let (foreignLauncher, _, _) = try makeSyntheticKeyBundle(
        bundleIdentifier: "local.azhou.foreign-startup", declaredHost: "dsh", executableName: "Launcher")
    defer { try? FileManager.default.removeItem(at: foreignLauncher) }
    expect(LauncherIdentity(bundleURL: foreignLauncher).host == nil,
          "a launcher declaring a foreign host resolves no host identity")

    // A stream failure latch is idempotent and never touches verified key state.
    system.latchStreamFailure("synthetic")
    expect(system.eventStream == nil, "latching a failure without an open stream stays inert")
    return checks
}


private final class PreparedConnectorTransport: StartupTransport {
    let world: StartupSnapshotWorld
    let base: WallpaperTransport
    var selected = "page-a"
    var closed = false
    init(_ world: StartupSnapshotWorld) {
        self.world = world
        base = WallpaperTransport(session: nil, socketFactory: { world.socket($0) })
    }
    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        [["id": selected, "type": "page", "url": world.href,
          "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/\(selected)"]]
    }
    func targets(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        try await pages(port: port, timeout: timeout)
    }
    func connect(to url: URL, timeout: TimeInterval) throws { try base.connect(to: url, timeout: timeout) }
    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        try await base.evaluate(source, timeout: timeout)
    }
    func makeSettingsSnapshotSession(page: StartupSnapshotPage, request: StartupSettingsSnapshotRequest,
                                     timeout: TimeInterval) async throws -> any StartupSettingsSnapshotSession {
        try await base.makeSettingsSnapshotSession(page: page, request: request, timeout: timeout)
    }
    func disconnectPage() { base.disconnectPage() }
    func close() { closed = true; base.close() }
}

@MainActor
private func startupPreparedConnectorChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: Bool, _ label: String) {
        precondition(condition, "FAILED: " + label); checks += 1
    }
    let bundle = URL(fileURLWithPath: "/Applications/Codex.app")
    let target = StartupTargetFacts(pid: 4123, bundle: bundle,
        executable: bundle.appendingPathComponent("Contents/MacOS/Codex"), bundleID: "com.openai.codex", launchTime: 100)
    for disposition in ["disabled", "degraded", "applied"] {
        let world = StartupSnapshotWorld(); world.preparedMode = true; world.preparedDisposition = disposition
        let transport = PreparedConnectorTransport(world)
        var snapshots = 0
        var finished = false
        let connector = StartupConnector(target: target, expectedPort: 49221,
            system: FakeStartupSystem(expectedPID: 4123, ports: [49221]), transport: transport,
            now: { 1 }, sleep: { _ in finished = true })
        let outcome = try await connector.runPrepared(payload: "native-prepare-fixture", runNonce: "test-run-1",
            deadline: 60, playbackReserve: 12, acceptSnapshot: { _ in snapshots += 1 },
            presentationFinished: { finished }, releaseRequested: { false })
        expect(outcome == .observed(.init(pageID: "page-a", runID: 1,
            wallpaperDisposition: disposition, wallpaperReason: disposition == "disabled" ? "disabled"
                : disposition == "degraded" ? "wallpaper-unsupported" : "")), "independent workspace disposition survives native reconciliation")
        expect(snapshots == 1 && transport.closed, "exactly one snapshot accepted and transport always closed")
        expect(world.operationLog.contains("page-a:prepare"), "connector uses the bound production prepare method")
    }
    do {
        let world = StartupSnapshotWorld(); world.preparedMode = true
        let transport = PreparedConnectorTransport(world)
        var snapshots = 0
        let connector = StartupConnector(target: target, expectedPort: 49221,
            system: FakeStartupSystem(expectedPID: 4123, ports: [49221]), transport: transport, now: { 1 })
        let outcome = try await connector.runPrepared(payload: "native-prepare-fixture", runNonce: "test-run-1",
            deadline: 60, playbackReserve: 12, acceptSnapshot: { _ in
                snapshots += 1; transport.selected = "page-b"
            }, presentationFinished: { true }, releaseRequested: { false })
        expect(outcome == .observed(.init(pageID: "page-b", runID: 1, wallpaperDisposition: "disabled", wallpaperReason: "disabled")),
               "retired page is replaced before workspace acceptance")
        expect(snapshots == 1 && world.operationLog.filter { $0.hasSuffix(":begin") }.count == 1,
               "successor prepares workspace without replaying or re-reading accepted animation snapshot")
        expect(world.operationLog.contains("page-a:prepare") && world.operationLog.contains("page-b:prepare"),
               "each generation proves its own workspace")
    }
    for mode in ["skip", "deadline", "malformed", "no-shell"] {
        let world = StartupSnapshotWorld(); world.preparedMode = true
        world.malformedPrepared = mode == "malformed"
        world.preparedShell = mode != "no-shell"
        let transport = PreparedConnectorTransport(world)
        var time = 1.0
        var snapshots = 0
        let connector = StartupConnector(target: target, expectedPort: 49221,
            system: FakeStartupSystem(expectedPID: 4123, ports: [49221]), transport: transport,
            now: { time }, sleep: { _ in time = 60 })
        do {
            let outcome = try await connector.runPrepared(payload: "native-prepare-fixture", runNonce: "test-run-1",
                deadline: mode == "deadline" ? 10 : 60, playbackReserve: 12,
                acceptSnapshot: { _ in snapshots += 1 }, presentationFinished: { true },
                releaseRequested: { mode == "skip" })
            expect(mode == "skip" && outcome == .released, "skip is released, never ready")
        } catch is StartupFailure {
            expect(mode != "skip", "invalid or exhausted preparation fails explicitly")
        }
        expect(transport.closed, "failure and skip release the bound transport")
        if mode != "no-shell" { expect(snapshots == 0, "invalid admission never starts playback") }
    }
    do {
        let world = StartupSnapshotWorld(); world.preparedMode = true
        let transport = PreparedConnectorTransport(world)
        let connector = StartupConnector(target: target, expectedPort: 49221,
            system: FakeStartupSystem(expectedPID: 4123, ports: [49221]), transport: transport, now: { 1 })
        let task = Task {
            try await connector.runPrepared(payload: "native-prepare-fixture", runNonce: "test-run-1",
                deadline: 60, playbackReserve: 12, acceptSnapshot: { _ in
                    withUnsafeCurrentTask { $0?.cancel() }
                }, presentationFinished: { false }, releaseRequested: { false })
        }
        do { _ = try await task.value; preconditionFailure("cancelled preparation unexpectedly completed") }
        catch is CancellationError { }
        expect(world.operationLog.contains("page-a:cancelWorkspace"), "task cancellation sends cleanup to the original controller")
        expect(world.cleanupCancellationStates == [false], "cleanup executes without inherited task cancellation")
        expect(world.preparedExpiries == [60000], "remote monotonic sample plus remaining native budget bounds the page lease")
        expect(transport.closed, "cancelled native preparation closes only its transport")
    }
    do {
        let world = StartupSnapshotWorld(); world.preparedMode = true
        let transport = PreparedConnectorTransport(world)
        var skip = false
        let connector = StartupConnector(target: target, expectedPort: 49221,
            system: FakeStartupSystem(expectedPID: 4123, ports: [49221]), transport: transport, now: { 1 })
        let outcome = try await connector.runPrepared(payload: "native-prepare-fixture", runNonce: "test-run-1",
            deadline: 60, playbackReserve: 12, acceptSnapshot: { _ in skip = true },
            presentationFinished: { false }, releaseRequested: { skip })
        expect(outcome == .released && world.preparedPages.contains("page-a"), "skip releases while workspace preparation may continue")
        expect(!world.operationLog.contains("page-a:cancelWorkspace"), "user skip does not cancel background wallpaper preparation")
    }
    do {
        let world = StartupSnapshotWorld(); world.preparedMode = true
        let transport = PreparedConnectorTransport(world)
        var time = 1.0
        world.afterWorkspaceClock = { time = 10 }
        let connector = StartupConnector(target: target, expectedPort: 49221,
            system: FakeStartupSystem(expectedPID: 4123, ports: [49221]), transport: transport, now: { time })
        do {
            _ = try await connector.runPrepared(payload: "native-prepare-fixture", runNonce: "test-run-1",
                deadline: 60, playbackReserve: 12, acceptSnapshot: { _ in time = 60 },
                presentationFinished: { false }, releaseRequested: { false })
            preconditionFailure("expired preparation unexpectedly completed")
        } catch let failure as StartupFailure { expect(failure.reason == "attach-timeout", "native deadline remains absolute") }
        expect(world.preparedExpiries == [51000], "clock reply latency reduces the page lease instead of extending it")
        expect(!world.operationLog.contains("page-a:cancelWorkspace"), "expired budget sends no cleanup business request past its deadline")
        expect(transport.closed, "expired native run releases transport while independent page deadline prevents late writes")
    }
    return checks
}


@MainActor
private func nativeColdLaunchChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: Bool, _ label: String) { precondition(condition, "FAILED: " + label); checks += 1 }
    let root = FileManager.default.temporaryDirectory.appendingPathComponent("skin-native-cover-" + UUID().uuidString)
    try FileManager.default.createDirectory(at: root.appendingPathComponent("web"), withIntermediateDirectories: true)
    try Data("<html></html>".utf8).write(to: root.appendingPathComponent("web/index.html"))
    defer { try? FileManager.default.removeItem(at: root) }
    let bundle = URL(fileURLWithPath: "/Applications/Codex.app")
    let key = HostApplicationKey(host: .codex, bundleURL: bundle,
        executableURL: bundle.appendingPathComponent("Contents/MacOS/Codex"), bundleIdentifier: "com.openai.codex",
        version: "fixture", build: "fixture", executableSHA256: "")
    let findings = SkinCapability.allCases.map { capability in
        CapabilityFinding(subject: .init(application: key, surface: SkinHostContract.surface(for: capability),
            contractVersion: SkinHostContract.version), capability: capability, state: .verified, evidenceIDs: ["fixture"], reason: "fixture")
    }
    let inputs = BoundHostInputs(identity: .init(key: key, signingIdentity: "fixture", evidenceID: "fixture"),
        findings: findings, contractVersion: SkinHostContract.version)
    _ = NSApplication.shared
    let originalMenu = NSApp.mainMenu
    defer { NSApp.mainMenu = originalMenu }
    for mode in ["complete", "skip", "failure", "bad-cover", "deadline", "preflight", "hot",
                 "cancel-open", "cancel-task", "short-preflight", "short-cover", "short-attach", "window-close",
                 "host-activation", "interrupt-open", "interrupt-prepare", "interrupt-wait", "space-wait"] {
        let runtime = FakeNativeAppRuntime(arguments: ["skin"], resourceURL: root)
        let app = FakeNativeApplication(pid: 4123, bundleIdentifier: key.bundleIdentifier, bundleURL: bundle,
            executableURL: key.executableURL, launchTime: 100)
        if mode == "hot" { runtime.applications = [app] }
        let facts = StartupTargetFacts(pid: 4123, bundle: bundle, executable: key.executableURL,
            bundleID: key.bundleIdentifier, launchTime: 100)
        let operationID = UUID()
        let world = StartupSnapshotWorld(); world.preparedMode = true; world.runNonce = operationID.uuidString
        let transport = PreparedConnectorTransport(world)
        let system = FakeStartupSystem(expectedPID: 4123, ports: [49221])
        let presentation = FakeNativePlayerPresentation()
        let workspaceNotifications = NotificationCenter()
        let unrelated = FakeNativeApplication(pid: 800, bundleIdentifier: "fixture.other", bundleURL: URL(fileURLWithPath: "/Applications/Other.app"))
        presentation.coverValid = mode != "bad-cover"
        presentation.coverHook = {
            world.runNonce = $0
            if mode == "short-cover" { runtime.uptime = 108 }
        }
        if mode == "short-attach" { world.afterWorkspaceClock = { runtime.uptime = 130 } }
        if mode == "interrupt-prepare" { world.afterWorkspaceClock = { presentation.nativeHandler?.applicationActivated(unrelated) } }
        let callerDeadline: TimeInterval = ["short-preflight", "short-cover"].contains(mode) ? 108 : mode == "short-attach" ? 130 : 160
        var closeWindow: NSWindow?
        var windowCloseCount = 0
        var closeObserver: NSObjectProtocol?
        let realPresentation: AppKitNativePlayerPresentation? = mode == "window-close"
            ? AppKitNativePlayerPresentation(activateApp: {}, makeVisible: { _ in }, runAlert: { _ in }, orderCover: { window in
                closeWindow = window
                closeObserver = NotificationCenter.default.addObserver(forName: NSWindow.willCloseNotification, object: window, queue: nil) { _ in windowCloseCount += 1 }
            }) : nil
        defer { if let closeObserver { NotificationCenter.default.removeObserver(closeObserver) } }
        var portAllocations = 0
        var sequence: [String] = []
        var records: [[String: Any]] = []
        let events = NativeStartupEventStream(writer: NativeEventWriter(startedAt: 100, launcherPID: 42,
            launcherPath: "/synthetic", now: { runtime.uptime }, sink: { records.append($0) }))
        events.begin(at: 100)
        var assembly = CodexSkinAssembly(preflightBundle: { _, budget in
            sequence.append("preflight")
            expect(budget.totalDeadline == min(160, callerDeadline)
                && budget.preflightDeadline == min(115, callerDeadline), "caller deadline bounds preflight and total budget")
            if mode == "preflight" { throw StartupFailure(reason: "target-identity", message: "fixture") }
            if mode == "short-preflight" { runtime.uptime = 108 }
        }, activateExisting: { _ in app.activate() }, preparePort: { portAllocations += 1; return 49221 }, openApplication: { _, _, deadline, _ in
            sequence.append("open")
            expect(presentation.nativeCoverCount == 1 || closeWindow != nil, "cold host opens after native cover draw receipt")
            expect(deadline == min(146, callerDeadline), "opening respects the earlier caller and 45-second attach deadline")
            if mode == "deadline" { presentation.schedules.last?.fire() }
            if mode == "cancel-open" { throw CancellationError() }
            if mode == "host-activation" { presentation.nativeHandler?.applicationActivated(app) }
            if mode == "interrupt-open" { presentation.nativeHandler?.applicationActivated(unrelated) }
            if mode == "window-close" {
                guard let window = closeWindow, let delegate = window.delegate as? NativeColdPlayer else {
                    preconditionFailure("actual cover window must bind NativeColdPlayer as its X delegate")
                }
                window.performClose(nil)
                expect(windowCloseCount == 1 && realPresentation?.geometry.isEmpty == true,
                    "real AppKit performClose reaches windowShouldClose and immediately releases the owned cover once")
                expect(delegate.windowShouldClose(window) == false && windowCloseCount == 1,
                    "a duplicate X delegate event cannot release the window twice")
            }
            return app
        }, onTargetOpened: { _ in }, onCaptureReady: { _ in }, eventStream: { events },
        onOpeningChanged: { _ in }, startupFacts: { _ in facts }, performDisable: nil)
        assembly.nativePresentation = { nonce, event in
            sequence.append("cover")
            return NativeColdPlayer(nonce: nonce, expectedApplication: key, runtime: runtime,
                presentation: realPresentation ?? presentation, workspaceNotifications: workspaceNotifications, event: event)
        }
        presentation.evaluationHook = { source in
            if source.contains("finishNativeSnapshot") {
                if mode == "skip" { presentation.nativeHandler?.requestSkip() }
                else if mode == "cancel-task" { withUnsafeCurrentTask { $0?.cancel() } }
                else if mode == "failure" {
                    presentation.nativeHandler?.receive(body: ["action": "assetError", "runId": world.runNonce], isMainFrame: true)
                } else {
                    presentation.nativeHandler?.receive(body: ["action": "ready", "runId": world.runNonce, "duration": 12000], isMainFrame: true)
                }
            }
            if source == "window.launcherUI.beginLaunch()" {
                sequence.append("play")
                if mode == "interrupt-wait" { presentation.nativeHandler?.applicationActivated(unrelated) }
                else if mode == "space-wait" { workspaceNotifications.post(name: NSWorkspace.activeSpaceDidChangeNotification, object: nil) }
                else { presentation.nativeHandler?.receive(body: ["action": "complete", "runId": world.runNonce, "skipped": false], isMainFrame: true) }
            }
            return (true, nil)
        }
        let driver = CodexSkinDriver(inputs: inputs, runtime: runtime, readPayload: { sequence.append("payload"); return "trusted-native-prepare" },
            makeTargetSystem: { system }, makeConnector: { target, port, system, capture, events in
                let observing = NativeStartupEventTransport(base: transport, capture: capture, events: events, now: { runtime.uptime })
                return StartupConnector(target: target, expectedPort: port, system: system, transport: observing,
                    now: { runtime.uptime }, sleep: { _ in try await Task.sleep(nanoseconds: 1_000_000) })
            }, installObservation: CodexInstallObservation(), assembly: assembly)
        let result = await Task { @MainActor in
            await driver.launch(.init(expectedApplication: key, operationID: operationID, startedAt: 100, deadline: callerDeadline))
        }.value
        if mode == "hot" {
            if case .activated = result {} else { preconditionFailure("native assembly changed hot activation") }
            expect(sequence.isEmpty && presentation.nativeCoverCount == 0, "hot path reads no payload and constructs no cover")
            continue
        }
        guard case .nativePresentation(let receipt) = result else { preconditionFailure("cold native result lost its presentation identity") }
        if mode == "complete" || mode == "host-activation" {
            expect(receipt.presentation == .completed && receipt.workspace?.wallpaperDisposition == "disabled", "native completion reconciles independently observed workspace")
            expect(sequence == ["preflight", "payload", "cover", "open", "play"], "production driver invokes real NativeColdPlayer in the intended order")
            expect(presentation.evaluations.contains { $0.contains("acceptNativeSnapshotDescriptor") }
                && presentation.evaluations.contains { $0.contains("acceptNativeSnapshotChunk") }
                && presentation.evaluations.contains { $0.contains("finishNativeSnapshot") }, "actual NativeColdPlayer consumes the bounded snapshot bridge")
            expect(presentation.createdPlayers.count == 1 && presentation.coldRevealCount == 1, "native player mounts and reveals exactly once")
            expect(events.resolveNative(receipt, at: 110) == .ready, "native journal accepts independent evidence without page-player ready")
            expect(records.contains { $0["event"] as? String == "startup-native-result" }
                && !records.contains { $0["event"] as? String == "startup-ready" }, "native evidence is not relabelled as page playback")
        } else if mode == "cancel-open" || mode == "cancel-task" || mode.hasPrefix("interrupt-") || mode == "space-wait" {
            expect(receipt.presentation == .interrupted && receipt.reason == "startup-interrupted" && receipt.workspace == nil,
                "actual driver distinguishes Task cancellation from protocol failure and user skip")
            expect(events.resolveNative(receipt, at: 110) == .partial(reason: "startup-interrupted"),
                "cancelled native receipt resolves to the established partial/startup-interrupted outcome")
            if mode == "cancel-task" {
                expect(world.operationLog.contains("page-a:cancelWorkspace"), "cancelled driver cleans up its bound workspace operation")
            }
            expect(transport.closed || mode == "cancel-open" || mode == "interrupt-open", "interruption exits connector preparation or completion wait and releases transport")
        } else if mode == "skip" || mode == "window-close" {
            expect(receipt.presentation == .skipped && receipt.workspace == nil, "skip releases without inventing workspace readiness")
            expect(events.resolveNative(receipt, at: 110) == .skipped, "native user skip has its own terminal receipt")
            expect(!world.operationLog.contains("page-a:cancelWorkspace"), "skip during WK transfer retains background host preparation")
        } else {
            expect(receipt.presentation == .failed, "failed native branch returns its own failure receipt")
            expect(events.resolveNative(receipt, at: 110) == .behaviorNotProven(reason: receipt.reason ?? "protocol-error"),
                "native failure keeps its production reason and failure exit")
            if ["bad-cover", "preflight", "short-preflight", "short-cover"].contains(mode) {
                expect(!sequence.contains("open"), "failed admission never opens the host")
            }
            if mode.hasPrefix("short-") {
                expect(receipt.reason == "attach-timeout", "short caller deadline is a timeout rather than protocol error")
                expect(world.submittedInstall == nil || mode == "short-attach", "preflight and cover deadlines cannot reach page install")
                if mode == "short-preflight" { expect(!sequence.contains("payload") && !sequence.contains("cover"), "expired preflight performs no later payload or cover work") }
                if mode == "short-cover" { expect(portAllocations == 0, "expired cover does not allocate a host port") }
                if mode == "short-attach" { expect(world.preparedExpiries.isEmpty && presentation.createdPlayers.isEmpty,
                    "attach cannot reset an expired caller deadline for workspace or WK preparation") }
            }
        }
        _ = events.finish(at: 111)
        if !["preflight", "short-preflight", "window-close"].contains(mode) { expect(presentation.orderedOutCount == 1, "every created cover is released once") }
        expect(!app.isTerminated && runtime.terminated == 0, "skip, cancellation and window X never terminate the user's host")
        expect(app.activationCount == 0, "driver does not steal focus during native presentation or skip")
        let revealCount = presentation.coldRevealCount
        presentation.nativeHandler?.receive(body: ["action": "ready", "runId": world.runNonce, "duration": 12000], isMainFrame: true)
        expect(presentation.coldRevealCount == revealCount, "late renderer events cannot revive a released run")
    }
    for mode in ["retired-page", "missing-target", "missing-cover", "pending-failure", "pending-interruption"] {
        var records: [[String: Any]] = []
        let stream = NativeStartupEventStream(writer: NativeEventWriter(startedAt: 100, launcherPID: 42,
            launcherPath: "/synthetic", now: { 110 }, sink: { records.append($0) }))
        stream.begin(at: 100)
        if mode != "missing-target" {
            stream.targetOpened(pid: 4123, at: 101)
            _ = stream.bindPage(pid: 4123, pageID: "current-page")
        }
        if mode == "pending-failure" { stream.latchFailure("owner-conflict") }
        if mode == "pending-interruption" { stream.latchInterruption() }
        let receipt = SkinNativeLaunchReceipt(operationID: UUID(), runNonce: UUID().uuidString,
            presentation: .completed, reason: nil, workspace: SkinNativeWorkspaceObservation(
                pageGeneration: mode == "retired-page" ? "retired-page" : "current-page", runID: 1,
                wallpaperDisposition: "disabled", wallpaperReason: "disabled"), coverDrawCommitted: mode != "missing-cover")
        let result = stream.resolveNative(receipt, at: 110)
        expect(result == (mode == "pending-interruption" ? .partial(reason: "startup-interrupted")
            : .behaviorNotProven(reason: mode == "pending-failure" ? "owner-conflict" : "protocol-error")),
            "native producer refuses missing, stale or contradicted evidence: \(mode)")
        expect(stream.resolveNative(receipt, at: 111) == nil, "native terminal cannot be replaced by a late result")
        _ = stream.finish(at: 112)
        _ = stream.finish(at: 113)
        expect(records.filter { $0["event"] as? String == "launcher-exit" }.count == 1,
            "native exit binding is emitted once")
    }
    _ = NSApplication.shared
    let oldMenu = NSApp.mainMenu
    defer { NSApp.mainMenu = oldMenu }
    var firstWindow: NSWindow?
    var reusedWindow: NSWindow?
    var activationCount = 0
    let panel = AppKitNativePlayerPresentation(activateApp: { activationCount += 1 },
        makeVisible: { reusedWindow = $0 }, runAlert: { _ in }, orderCover: { firstWindow = $0 })
    let previewDelegate = AppDelegate(runtime: FakeNativeAppRuntime(arguments: ["skin", "--preview"]))
    let cover = try panel.showColdCover(locale: .chinese, runNonce: "appkit-unit", delegate: previewDelegate)
    expect(firstWindow?.level == .floating, "cold cover stays above a subsequently opened normal host window")
    panel.createPlayer(locale: .chinese, mode: "launch", theme: "light", inspect: false,
        nativeStartup: .init(runNonce: "appkit-unit", locale: "zh-CN", theme: "light"),
        messageHandler: previewDelegate, navigationDelegate: previewDelegate)
    panel.revealColdPlayer(); panel.makeVisible(); panel.orderOut(); panel.stopLoading(); panel.removeMessageHandler(named: "launcher")
    expect(firstWindow != nil && firstWindow === reusedWindow, "real AppKit cover and WK attach reuse the identical NSWindow")
    expect(cover.drawObserved && cover.transactionCommitted && activationCount == 0, "AppKit receipt reports draw/commit without activation or a visual no-flash claim")
    panel.discardColdPlayer()
    expect(panel.geometry.isEmpty, "cold teardown drops the owned window and WebKit view")
    checks += try nativeColdWorkspaceChecks(key: key)
    return checks
}

private final class TrackingWorkspaceNotifications: NotificationCenter, @unchecked Sendable {
    private(set) var removalCount = 0
    override func removeObserver(_ observer: Any) {
        removalCount += 1
        super.removeObserver(observer)
    }
}

@MainActor
private func nativeColdWorkspaceChecks(key: HostApplicationKey) throws -> Int {
    var checks = 0
    func expect(_ condition: Bool, _ label: String) { precondition(condition, "FAILED: " + label); checks += 1 }
    for mode in ["activation", "foreign-path", "space", "release"] {
        let runtime = FakeNativeAppRuntime(arguments: ["skin"])
        let presentation = FakeNativePlayerPresentation()
        let notifications = TrackingWorkspaceNotifications()
        var interruptions = 0
        var player: NativeColdPlayer? = NativeColdPlayer(nonce: "workspace-test", expectedApplication: key,
            runtime: runtime, presentation: presentation, workspaceNotifications: notifications) { event in
                if case .interrupted = event { interruptions += 1 }
            }
        weak var releasedPlayer = player
        let original = FakeNativeApplication(pid: 700, bundleIdentifier: "fixture.original", bundleURL: URL(fileURLWithPath: "/Applications/Original.app"))
        runtime.frontmostApplication = original
        _ = try player?.showCover()
        expect(interruptions == 0, "an initially unrelated foreground application is not an activation switch")
        let host = FakeNativeApplication(pid: 701, bundleIdentifier: key.bundleIdentifier, bundleURL: key.bundleURL)
        let launcher = FakeNativeApplication(pid: Int32(runtime.processIdentifier), bundleIdentifier: "fixture.launcher", bundleURL: runtime.bundleURL)
        var activated: (any NativeApplication)? = host
        runtime.applicationOverride = { _ in activated }
        func activate(_ application: any NativeApplication) {
            activated = application
            notifications.post(name: NSWorkspace.didActivateApplicationNotification, object: nil,
                userInfo: [NSWorkspace.applicationUserInfoKey: NSRunningApplication.current])
        }
        activate(launcher); activate(host)
        expect(interruptions == 0, "launcher and verified host activation are admitted before open completion")
        if mode == "activation" { activate(original) }
        else if mode == "foreign-path" {
            activate(FakeNativeApplication(pid: 702, bundleIdentifier: key.bundleIdentifier,
                bundleURL: URL(fileURLWithPath: "/Applications/Foreign/Codex.app")))
        }
        else if mode == "space" { notifications.post(name: NSWorkspace.activeSpaceDidChangeNotification, object: nil) }
        else { player?.releaseCover() }
        expect(interruptions == (mode == "release" ? 0 : 1) && presentation.orderedOutCount == 1,
            "application or Space departure interrupts and releases exactly once")
        expect(notifications.removalCount == 2, "release removes both run-scoped workspace observations")
        activate(original)
        notifications.post(name: NSWorkspace.activeSpaceDidChangeNotification, object: nil)
        player?.beginPlayback(deadline: 160)
        player?.receive(body: ["action": "ready", "runId": "workspace-test", "duration": 12000], isMainFrame: true)
        player?.releaseCover()
        expect(interruptions == (mode == "release" ? 0 : 1) && presentation.orderedOutCount == 1
            && presentation.coldRevealCount == 0, "late workspace and renderer events cannot revive or release a finished cover")
        expect(notifications.removalCount == 2, "duplicate release never removes workspace observers twice")
        player = nil
        expect(releasedPlayer == nil, "released workspace observations do not retain the player")
    }
    return checks
}

@MainActor
private func nativeColdWindowOrderingChecks() throws -> Int {
    var checks = 0
    func expect(_ condition: Bool, _ label: String) { precondition(condition, "FAILED: " + label); checks += 1 }
    let beforePID = NSWorkspace.shared.frontmostApplication?.processIdentifier
    let delegate = AppDelegate(runtime: FakeNativeAppRuntime(arguments: ["skin", "--preview"]))
    for normalControl in [true, false] {
        var cover: NSWindow?
        let frame = NSRect(x: 24, y: 40, width: 260, height: 160)
        let presentation = AppKitNativePlayerPresentation(
            activateApp: { preconditionFailure("cold ordering must not activate") },
            makeVisible: { _ in preconditionFailure("cold ordering must not select a key window") },
            runAlert: { _ in }, orderCover: { window in
                cover = window
                if normalControl { window.level = .normal }
                window.setFrame(frame, display: false); window.orderFront(nil)
            })
        _ = try presentation.showColdCover(locale: .chinese, runNonce: "ordering-test", delegate: delegate)
        guard let cover else { preconditionFailure("production cold presentation must own a window") }
        let host = NSWindow(contentRect: frame, styleMask: [.titled], backing: .buffered, defer: false)
        host.isReleasedWhenClosed = false
        defer { presentation.discardColdPlayer(); host.orderOut(nil); host.close() }
        host.orderFront(nil)
        let windowNumber = cover.windowNumber
        presentation.createPlayer(locale: .chinese, mode: "launch", theme: "light", inspect: false,
            nativeStartup: .init(runNonce: "ordering-test", locale: "zh-CN", theme: "light"),
            messageHandler: delegate, navigationDelegate: delegate)
        for revealed in [false, true] {
            if revealed { presentation.revealColdPlayer() }
            RunLoop.main.run(until: Date().addingTimeInterval(0.1))
            let rows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
            let ids = rows.compactMap { $0[kCGWindowNumber as String] as? Int }
            guard let coverIndex = ids.firstIndex(of: windowNumber), let hostIndex = ids.firstIndex(of: host.windowNumber) else {
                preconditionFailure("ordering regression needs both real onscreen window identities")
            }
            print("cold-ordering control=\(normalControl) revealed=\(revealed) cover=\(windowNumber) host=\(host.windowNumber) coverIndex=\(coverIndex) hostIndex=\(hostIndex) frontmost=\(beforePID ?? 0)")
            fflush(stdout)
            expect(normalControl ? hostIndex < coverIndex : coverIndex < hostIndex,
                "real AppKit ordering distinguishes the normal-level negative control from the cold fix before and after reveal")
            expect(cover.windowNumber == windowNumber && NSWorkspace.shared.frontmostApplication?.processIdentifier == beforePID,
                "cold cover and reveal reuse their window without changing the foreground application")
        }
        expect(!cover.collectionBehavior.contains(.canJoinAllSpaces) && !cover.collectionBehavior.contains(.moveToActiveSpace),
            "cold window never follows the user to another Space")
    }
    return checks
}
