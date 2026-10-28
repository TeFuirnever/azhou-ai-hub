// Compile separately from the application; fake host operations never launch or kill Codex.
// python3 -B tools/test-startup-native.py
import Foundation
import Darwin

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
                "restoreSource": WallpaperCLI.restoreSource,
            ]
            let bytes = try JSONSerialization.data(withJSONObject: expressions, options: [.sortedKeys])
            guard let text = String(data: bytes, encoding: .utf8) else { fatalError("helper expressions are not UTF-8") }
            print(text)
            return
        }

        var checks = 0
        func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
            guard condition() else { fatalError("FAILED: \(label)") }
            checks += 1
        }

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
            "renderer-complete-timeout", "javascript-error", "asset-error", "target-exited",
            "activation-rejected", "renderer-terminated", "target-missing", "target-identity",
            "listener-mismatch", "page-pending", "page-unsupported", "ambiguous-main-page",
            "owner-conflict", "startup-active", "startup-interrupted", "attach-timeout", "asset-invalid",
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
        expect(WallpaperCLI.restoreMessage == "已移除本页启动美化及设置入口；已保存值保留；Codex 与调试端口保持原状态。",
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
        #endif

        print("Startup native checks passed: \(checks). Scope: injected host facts and transport only; no real open/kill.")
    }
}

private struct FakeStartupSystem: StartupTargetSystem {
    let expectedPID: Int32
    let ports: [Int]
    func preflightBundle(_ bundle: URL, deadline: TimeInterval) throws {}
    func validate(_ target: StartupTargetFacts, deadline: TimeInterval) throws {
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
            throw WallpaperFailure(state: "endpoint-unavailable", message: "temporary")
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

    return checks
}
#endif
