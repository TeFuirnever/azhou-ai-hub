// Compile separately from the application; fake host operations never launch or kill Codex.
// python3 -B tools/test-startup-native.py
import Foundation
import Darwin

@main
struct StartupNativeTests {
    @MainActor
    static func main() async throws {
        var checks = 0
        func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
            guard condition() else { fatalError("FAILED: \(label)") }
            checks += 1
        }
        func refuses(_ label: String, _ operation: () throws -> Void) {
            do { try operation(); fatalError("FAILED: \(label)") }
            catch { checks += 1 }
        }

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
               && WallpaperCLI.statusSource.contains("azhou.codex-startup-animation"),
               "wallpaper status reads only supported owner tuples and includes startup status")
        expect(WallpaperCLI.applyGuardSource.contains("startup-active")
               && WallpaperCLI.applyGuardSource.contains("owner-conflict"),
               "explicit helper apply refuses an active or unknown page owner before injection")
        expect(WallpaperCLI.restoreSource.contains("azhou-codex-startup")
               && WallpaperCLI.restoreSource.contains("azhou.codex-startup-animation")
               && WallpaperCLI.restoreSource.contains("0.7.1"),
               "explicit restore supports the controller and exact known legacy wallpaper version")

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
