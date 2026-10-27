// Compile separately from the application; fake host operations never launch or kill Codex.
// python3 -B tools/test-startup-native.py
import Foundation

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
            validate: { validatedPID = $0.pid },
            activate: { activatedPID = $0.pid; return true },
            coldStart: { coldStartCount += 1; return .failed(reason: "unexpected-cold-start") }
        )
        expect(validatedPID == 4123, "hot start validates the existing process")
        expect(activatedPID == 4123, "hot start activates the same process")
        expect(coldStartCount == 0, "hot start does not launch or replay a session")
        expect(outcome == .activated(pid: 4123), "hot start is reported as activated")

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
    func validate(_ target: StartupTargetFacts) throws {
        guard target.pid == expectedPID else {
            throw StartupFailure(reason: "target-identity", message: "fake target mismatch")
        }
    }
    func listeningPorts(_ target: StartupTargetFacts) throws -> [Int] { ports }
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
    private var pageResponses: [[String: Any]]
    private var evaluationResponses: [[String: Any]]
    private var pageFailures: Int
    private var repeatLastEvaluation: Bool
    private var lastEvaluation: [String: Any]?

    init(pages: [[String: Any]] = [], evaluations: [[String: Any]] = [], pageFailures: Int = 0,
         repeatLastEvaluation: Bool = false) {
        pageResponses = pages
        evaluationResponses = evaluations
        self.pageFailures = pageFailures
        self.repeatLastEvaluation = repeatLastEvaluation
    }

    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        pagesCount += 1
        if pageFailures > 0 {
            pageFailures -= 1
            throw WallpaperFailure(state: "endpoint-unavailable", message: "temporary")
        }
        return pageResponses
    }
    func connect(to url: URL, timeout: TimeInterval) throws { connectCount += 1 }
    func evaluate(_ expression: String, timeout: TimeInterval) async throws -> [String: Any] {
        evaluateCount += 1
        if expression.contains("test-only-probe") { payloadCount += 1 }
        if !evaluationResponses.isEmpty {
            lastEvaluation = evaluationResponses.removeFirst()
            return lastEvaluation!
        }
        return repeatLastEvaluation ? lastEvaluation ?? [:] : [:]
    }
    func close() { closeCount += 1 }
}
