// ZCode-specific fixed-target CDP transport. Native assembly supplies trusted OS identity ports.
// Main-actor, one ticket/target/context only; no generic cross-host transport.
import Foundation

private final class ZCodeRejectRedirect: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}
@MainActor final class ZCodeBoundCDP {
    enum Failure: Error { case deadline, cancelled, busy, identity, protocolError, unavailable }
    enum AttachmentStage: String {
        case targetList = "target-list", mainPageMissing = "main-page-missing"
        case mainPageAmbiguous = "main-page-ambiguous", targetEndpoint = "target-endpoint"
        case frame, context, bound
    }
    private(set) var attachmentStage = AttachmentStage.targetList
    private(set) var discoveryAttempts = 0
    private(set) var initialDiscoveryCounts: [String: Int]?
    private(set) var latestDiscoveryCounts: [String: Int]?
    private let session: URLSession
    private var socket: URLSessionWebSocketTask?
    private var serial = 0
    private var pending = false
    private var sentMetadata: [String: String]?
    private var contexts: [String: [String: Any]] = [:]
    private var frameID = ""
    private var pinnedURL = "" // memory only; never log query values.
    private let guardLive: () throws -> Void
    private let now: () -> TimeInterval
    private let process: HostProcessGeneration
    private let endpoint: URL
    private let installedPage: String
    private(set) var binding: ZCodePageBinding?

    // guardLive MUST independently verify installation/PID/birth/executable AND
    // kernel listener ownership and loopback-only addresses, including all sockets.
    init(process: HostProcessGeneration, endpoint: URL, installedPage: String,
         now: @escaping () -> TimeInterval, guardLive: @escaping () throws -> Void) throws {
        guard endpoint.scheme == "http", endpoint.host == "127.0.0.1", endpoint.port != nil,
              endpoint.user == nil, endpoint.password == nil, endpoint.query == nil,
              endpoint.fragment == nil, endpoint.path.isEmpty || endpoint.path == "/" else { throw Failure.identity }
        self.process = process; self.endpoint = endpoint; self.installedPage = installedPage
        self.now = now; self.guardLive = guardLive
        let configuration = URLSessionConfiguration.ephemeral
        configuration.httpCookieStorage = nil; configuration.urlCredentialStorage = nil
        configuration.urlCache = nil; configuration.connectionProxyDictionary = [:]
        session = URLSession(configuration: configuration, delegate: ZCodeRejectRedirect(), delegateQueue: nil)
    }
    func close() { socket?.cancel(with: .normalClosure, reason: nil); socket = nil; session.invalidateAndCancel() }
    static func normalizedBoundaryFailure(_ error: Error, deadline: TimeInterval, now: TimeInterval, cancelled: Bool) -> Error {
        if cancelled { return Failure.cancelled }
        if !deadline.isFinite || now >= deadline { return Failure.deadline }
        return error
    }
    private func basicCheck(_ deadline: TimeInterval) throws {
        if Task.isCancelled { throw Failure.cancelled }
        guard deadline.isFinite, now() < deadline else { throw Failure.deadline }
    }
    private func check(_ deadline: TimeInterval) throws {
        try basicCheck(deadline)
        do { try guardLive() }
        catch { throw Self.normalizedBoundaryFailure(error, deadline: deadline, now: now(), cancelled: Task.isCancelled) }
        try basicCheck(deadline)
    }
    private func validPage(_ raw: String) -> Bool {
        guard let u = URLComponents(string: raw), u.scheme == "file", (u.host ?? "").isEmpty,
              u.user == nil, u.password == nil, u.fragment == nil, u.path == installedPage else { return false }
        let keys: Set<String> = ["restoreSession", "supportsSettings", "initialWorkspacePath", "initialWorkspacePurpose", "unavailableWorkspacePath", "windowKind", "locale", "zcodeLaunchMarks"]
        var seen = Set<String>()
        return (u.queryItems ?? []).allSatisfy { keys.contains($0.name) && seen.insert($0.name).inserted && ($0.name != "windowKind" || $0.value == "main") }
    }
    private func receive(_ deadline: TimeInterval) async throws -> [String: Any] {
        try check(deadline)
        guard let ws = socket else { throw Failure.unavailable }
        let seconds = min(4, deadline - now())
        let message: URLSessionWebSocketTask.Message
        do { message = try await withTaskCancellationHandler {
            try await withThrowingTaskGroup(of: URLSessionWebSocketTask.Message.self) { group in
                group.addTask { try await ws.receive() }
                group.addTask {
                    try await Task.sleep(nanoseconds: UInt64(max(0, seconds) * 1_000_000_000))
                    ws.cancel(with: .goingAway, reason: nil)
                    throw Failure.deadline
                }
                defer { group.cancelAll() }
                guard let first = try await group.next() else { throw Failure.protocolError }
                return first
            }
        } onCancel: { ws.cancel(with: .goingAway, reason: nil) }
        } catch { throw Self.normalizedBoundaryFailure(error, deadline: deadline, now: now(), cancelled: Task.isCancelled) }
        try basicCheck(deadline)
        let bytes: Data
        switch message { case .data(let data): bytes = data; case .string(let text): bytes = Data(text.utf8); @unknown default: throw Failure.protocolError }
        guard bytes.count <= 1_048_576,
              let object = try JSONSerialization.jsonObject(with: bytes) as? [String: Any] else { throw Failure.protocolError }
        return object
    }
    private func send(_ message: URLSessionWebSocketTask.Message, deadline: TimeInterval, willSend: (() -> Void)?) async throws {
        try check(deadline)
        guard let ws = socket else { throw Failure.unavailable }
        let seconds = max(0, deadline - now())
        try basicCheck(deadline)
        willSend?()
        do { try await withTaskCancellationHandler {
            try await withThrowingTaskGroup(of: Void.self) { group in
                group.addTask { @MainActor in
                    try self.basicCheck(deadline)
                    try await ws.send(message)
                }
                group.addTask {
                    try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
                    ws.cancel(with: .goingAway, reason: nil)
                    throw Failure.deadline
                }
                defer { group.cancelAll() }
                _ = try await group.next()
            }
        } onCancel: { ws.cancel(with: .goingAway, reason: nil) }
        } catch { throw Self.normalizedBoundaryFailure(error, deadline: deadline, now: now(), cancelled: Task.isCancelled) }
        try basicCheck(deadline)
    }
    private func call(_ method: String, _ params: [String: Any] = [:], deadline: TimeInterval, willSend: (() -> Void)? = nil) async throws -> [String: Any] {
        try check(deadline)
        guard !pending, socket != nil else { throw Failure.busy }
        pending = true; defer { pending = false }
        serial += 1; let id = serial
        let data = try JSONSerialization.data(withJSONObject: ["id": id, "method": method, "params": params])
        let rpcDeadline = min(deadline, now() + 4)
        try await send(.string(String(decoding: data, as: UTF8.self)), deadline: rpcDeadline, willSend: willSend)
        while true {
            let response = try await receive(rpcDeadline)
            if let event = response["method"] as? String, let p = response["params"] as? [String: Any] {
                if event == "Runtime.executionContextsCleared" { contexts.removeAll() }
                if event == "Runtime.executionContextCreated", let c = p["context"] as? [String: Any], let token = c["uniqueId"] as? String { contexts[token] = c }
                if event == "Runtime.executionContextDestroyed", let destroyed = p["executionContextId"] as? Int { contexts = contexts.filter { ($0.value["id"] as? Int) != destroyed } }
            }
            if response["id"] as? Int != id { continue }
            guard response["error"] == nil, let value = response["result"] as? [String: Any] else { throw Failure.protocolError }
            try check(deadline); return value
        }
    }
    // Single snapshot remains the default for inspection/disposal. Only the
    // first attachment after this runtime's successful cold open opts into wait.
    private func discoverMain(deadline: TimeInterval, waitForInitialMain: Bool) async throws -> [[String: Any]] {
        while true {
            attachmentStage = .targetList
            try check(deadline)
            // guardLive can itself spend time. Never send after its deadline or
            // cancellation check has become stale.
            if Task.isCancelled { throw Failure.cancelled }
            guard now() < deadline else { throw Failure.deadline }
            var request = URLRequest(url: endpoint.appendingPathComponent("json/list"))
            request.timeoutInterval = max(0.001, min(3, deadline - now()));request.cachePolicy = .reloadIgnoringLocalCacheData
            let (bytes, response) = try await session.data(for: request)
            try check(deadline)
            if Task.isCancelled { throw Failure.cancelled }
            guard now() < deadline else { throw Failure.deadline }
            guard (response as? HTTPURLResponse)?.statusCode == 200, bytes.count <= 1_048_576,
                  let pages = try JSONSerialization.jsonObject(with: bytes) as? [[String: Any]] else { throw Failure.protocolError }
            let pageRows = pages.filter { $0["type"] as? String == "page" }
            let candidates = pageRows.filter { validPage($0["url"] as? String ?? "") }
            var counts = ["empty": pageRows.isEmpty ? 1 : 0, "knownIndex": 0, "knownLogin": 0,
                          "aboutBlank": 0, "other": 0, "accepted": candidates.count]
            let loginPath = URL(fileURLWithPath: installedPage).deletingLastPathComponent().appendingPathComponent("login.html").path
            for row in pageRows {
                let raw = row["url"] as? String ?? ""
                if raw == "about:blank" { counts["aboutBlank", default: 0] += 1 }
                else if let u = URLComponents(string: raw), u.scheme == "file", (u.host ?? "").isEmpty, u.path == installedPage {
                    counts["knownIndex", default: 0] += 1
                } else if let u = URLComponents(string: raw), u.scheme == "file", (u.host ?? "").isEmpty, u.path == loginPath {
                    counts["knownLogin", default: 0] += 1
                } else { counts["other", default: 0] += 1 }
            }
            discoveryAttempts += 1
            if initialDiscoveryCounts == nil { initialDiscoveryCounts = counts }
            latestDiscoveryCounts = counts
            if candidates.count == 1 { return candidates }
            attachmentStage = candidates.isEmpty ? .mainPageMissing : .mainPageAmbiguous
            guard candidates.isEmpty, waitForInitialMain, binding == nil,
                  pageRows.allSatisfy({ $0["url"] as? String == "about:blank" }) else { throw Failure.identity }
            // No page or only initial blank pages may become the verified main.
            // Login, foreign paths and rejected queries are terminal, not retry.
            try check(deadline)
            if Task.isCancelled { throw Failure.cancelled }
            let remaining = deadline - now()
            guard remaining > 0 else { throw Failure.deadline }
            try await Task.sleep(nanoseconds: UInt64(min(0.1, remaining) * 1_000_000_000))
        }
    }
    func attach(deadline: TimeInterval, waitForInitialMain: Bool = false) async throws -> ZCodePageBinding {
        discoveryAttempts = 0;initialDiscoveryCounts = nil;latestDiscoveryCounts = nil
        let candidates = try await discoverMain(deadline: deadline, waitForInitialMain: waitForInitialMain)
        attachmentStage = .targetEndpoint
        guard candidates.count == 1, let page = candidates.first,
              let id = page["id"] as? String, id.range(of: "^[A-Za-z0-9_-]+$", options: .regularExpression) != nil,
              let address = page["webSocketDebuggerUrl"] as? String, let wsURL = URL(string: address),
              wsURL.scheme == "ws", wsURL.host == "127.0.0.1", wsURL.port == endpoint.port,
              wsURL.user == nil, wsURL.password == nil, wsURL.query == nil, wsURL.fragment == nil,
              wsURL.path == "/devtools/page/" + id else { throw Failure.identity }
        let ws = session.webSocketTask(with: wsURL); ws.maximumMessageSize = 1_048_576; socket = ws
        try check(deadline)
        ws.resume()
        attachmentStage = .frame
        let tree = try await call("Page.getFrameTree", deadline: deadline)
        guard let t = tree["frameTree"] as? [String: Any], let frame = t["frame"] as? [String: Any],
              let fid = frame["id"] as? String, let url = frame["url"] as? String, validPage(url) else { throw Failure.identity }
        frameID = fid; pinnedURL = url
        attachmentStage = .context
        _ = try await call("Runtime.enable", deadline: deadline)
        _ = try await call("Page.enable", deadline: deadline)
        let matches = contexts.filter { _, c in
            guard let aux = c["auxData"] as? [String: Any] else { return false }
            return aux["isDefault"] as? Bool == true && aux["frameId"] as? String == fid
        }
        guard matches.count == 1, let context = matches.first?.key, let pageURL = URL(string: url) else { throw Failure.identity }
        let result = ZCodePageBinding(process: process, endpoint: endpoint, pageURL: pageURL, targetID: id, documentToken: context)
        binding = result; attachmentStage = .bound; return result
    }
    private func recheckFrame(deadline: TimeInterval) async throws {
        let tree = try await call("Page.getFrameTree", deadline: deadline)
        guard let t = tree["frameTree"] as? [String: Any], let frame = t["frame"] as? [String: Any],
              frame["id"] as? String == frameID, frame["url"] as? String == pinnedURL,
              let token = binding?.documentToken, contexts[token] != nil else { throw Failure.identity }
    }
    // factoryBytes are the exact SHA-bound factory file, not a self-referential
    // payload hash. Metadata values are non-sensitive and operation-scoped.
    func install(factoryBytes: String, payloadSHA256: String, operationID: UUID,
                 observation: ZCodeInstallObservation, deadline: TimeInterval) async throws -> [String: Any] {
        try await recheckFrame(deadline: deadline)
        guard let binding else { throw Failure.unavailable }
        let metadata: [String: String] = ["controllerInstanceID": UUID().uuidString,
            "createdByOperationID": operationID.uuidString, "payloadSHA256": payloadSHA256,
            "documentToken": binding.documentToken]
        let reply = try await call("Runtime.callFunctionOn", ["functionDeclaration": "function(metadata) { return (" + factoryBytes + ")(metadata); }",
            "uniqueContextId": binding.documentToken, "arguments": [["value": metadata]],
            "awaitPromise": true, "returnByValue": true, "timeout": max(1, min(2000, (deadline-now())*1000))], deadline: deadline, willSend: { self.sentMetadata = metadata; observation.markSent() })
        guard reply["exceptionDetails"] == nil, let object = reply["result"] as? [String: Any],
              let value = object["value"] as? [String: Any] else { throw Failure.protocolError }
        try await recheckFrame(deadline: deadline)
        return value // NOT a fabricated ready receipt; status must acknowledge safe fields.
    }
    func evaluateSafe(_ expression: String, deadline: TimeInterval) async throws -> [String: Any] {
        try await recheckFrame(deadline: deadline)
        guard let token = binding?.documentToken else { throw Failure.unavailable }
        let reply = try await call("Runtime.evaluate", ["expression": expression, "uniqueContextId": token,
            "returnByValue": true, "awaitPromise": true, "timeout": max(1, min(2000, (deadline-now())*1000))], deadline: deadline)
        guard reply["exceptionDetails"] == nil, let result = reply["result"] as? [String: Any], let value = result["value"] as? [String: Any] else { throw Failure.protocolError }
        try await recheckFrame(deadline: deadline)
        return value
    }
}

extension ZCodeBoundCDP {
    // Fixed controller API only. Does not inspect DOM, forms, text, storage, URLs
    // or user content. status() refreshes this owned controller's lifecycle only.
    func safeStatus(deadline: TimeInterval) async throws -> [String: Any] {
        guard let token = binding?.documentToken else { throw Failure.unavailable }
        let encodedToken = String(decoding: try JSONSerialization.data(withJSONObject: token, options: .fragmentsAllowed), as: UTF8.self)
        return try await evaluateSafe("""
        (() => {
          const value = (o,k) => { const d=o && Object.getOwnPropertyDescriptor(o,k); return d && Object.hasOwn(d,'value') ? d.value : undefined; };
          const descriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouStartup');
          if(descriptor && !Object.hasOwn(descriptor,'value')) return {present:true,unconfirmed:true};
          const c=descriptor?.value;
          if (!c) return {present:false};
          if (value(c,'owner')!=='azhou-zcode-startup' || value(c,'version')!==1) return {present:true,conflict:true};
          const snapshot={};
          for(const k of ['controllerInstanceID','createdByOperationID','payloadSHA256','documentToken']) snapshot[k]=value(c,k);
          const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
          if(typeof snapshot.controllerInstanceID!=='string'||snapshot.controllerInstanceID.length!==36||!uuid.test(snapshot.controllerInstanceID)
            ||typeof snapshot.createdByOperationID!=='string'||snapshot.createdByOperationID.length!==36||!uuid.test(snapshot.createdByOperationID)
            ||typeof snapshot.payloadSHA256!=='string'||snapshot.payloadSHA256.length!==64||!/^[a-f0-9]{64}$/.test(snapshot.payloadSHA256)
            ||typeof snapshot.documentToken!=='string'||snapshot.documentToken!==\(encodedToken)) return {present:true,unconfirmed:true};
          const status=value(c,'status');
          if(typeof status!=='function') return {present:true,unconfirmed:true};
          const s=status.call(c);
          return {present:true,owner:value(c,'owner'),version:value(c,'version'),...snapshot,
            ready:value(s,'ready')===true,completed:value(s,'completed')===true,
            runId:Number.isSafeInteger(value(s,'runId')) ? value(s,'runId') : null,
            completion:{skipped:value(value(s,'completion'),'skipped')===true,beforeReady:value(value(s,'completion'),'beforeReady')===true},
            phase:['loading','playing','complete','settings','disposed','failed'].includes(value(s,'phase')) ? value(s,'phase') : 'unconfirmed'};
        })()
        """, deadline: deadline)
    }
    func acknowledgedReceipt(_ status: [String: Any], key: HostApplicationKey,
                             payloadSHA256: String, acquisition: PageAcquisition = .created) throws -> ControllerReceipt {
        guard let b = binding, status["present"] as? Bool == true,
              status["owner"] as? String == "azhou-zcode-startup", status["version"] as? Int == 1,
              let instance = status["controllerInstanceID"] as? String, UUID(uuidString: instance) != nil,
              let operation = status["createdByOperationID"] as? String, let op = UUID(uuidString: operation),
              status["payloadSHA256"] as? String == payloadSHA256,
              status["documentToken"] as? String == b.documentToken else { throw Failure.identity }
        if case .created = acquisition {
            guard let sent = sentMetadata,
                  sent["controllerInstanceID"] == instance,
                  sent["createdByOperationID"].flatMap(UUID.init(uuidString:)) == op,
                  sent["payloadSHA256"] == payloadSHA256,
                  sent["documentToken"] == b.documentToken else { throw Failure.identity }
        }
        return ControllerReceipt(location: PageLocation(application: key, process: b.process, documentToken: b.documentToken),
            owner: "azhou-zcode-startup", protocolVersion: 1, payloadSHA256: payloadSHA256,
            controllerInstanceID: instance, createdByOperationID: op)
    }
    func disposeConfirmed(_ receipt: ControllerReceipt, deadline: TimeInterval) async throws -> Bool {
        guard let b = binding, receipt.owner == "azhou-zcode-startup", receipt.protocolVersion == 1,
              receipt.location.process == b.process, receipt.location.documentToken == b.documentToken else { throw Failure.identity }
        let expected: [String: String] = ["controllerInstanceID": receipt.controllerInstanceID,
            "createdByOperationID": receipt.createdByOperationID.uuidString,
            "payloadSHA256": receipt.payloadSHA256, "documentToken": receipt.location.documentToken]
        let encoded = String(decoding: try JSONSerialization.data(withJSONObject: expected), as: UTF8.self)
        let result = try await evaluateSafe("""
        (() => {
          const expected=\(encoded);
          const value=(o,k)=>{const d=o&&Object.getOwnPropertyDescriptor(o,k);return d&&Object.hasOwn(d,'value')?d.value:undefined;};
          const descriptor=Object.getOwnPropertyDescriptor(globalThis,'__azhouStartup');
          if(descriptor && !Object.hasOwn(descriptor,'value')) return {disposed:false};
          const c=descriptor?.value;
          if(!c) return {disposed:true,alreadyAbsent:true};
          if(value(c,'owner')!=='azhou-zcode-startup'||value(c,'version')!==1) return {disposed:false};
          for(const k of Object.keys(expected)) {
            const a=value(c,k),b=expected[k];
            if(k==='createdByOperationID' ? typeof a!=='string'||a.toLowerCase()!==b.toLowerCase() : a!==b) return {disposed:false};
          }
          const dispose=value(c,'dispose');
          if(typeof dispose!=='function')return {disposed:false};
          const result=dispose.call(c);
          return {disposed:value(result,'disposed')===true};
        })()
        """, deadline: deadline)
        return result["disposed"] as? Bool == true
    }
}

// Concrete native ports for the fixed, evidenced ZCode installation.
import AppKit
import CryptoKit
import Darwin

@MainActor private final class ZCodeRuntimeLease: ZCodeOperationLease {
    private var releaseBody: (() -> Void)?
    init(_ release: @escaping () -> Void) { releaseBody = release }
    func release() { let action = releaseBody;releaseBody = nil;action?() }
}

@MainActor final class ZCodeNativeRuntime {
    private let inputs: BoundHostInputs
    private let runtime: any NativeAppRuntime
    private let readPayload: () throws -> String
    private let stateRoot: URL
    private let onEvent: ([String: Any]) -> Void
    private let installationProbe: (() throws -> Void)?
    struct ListenerCommandResult {
        let status: Int32
        let stdout: Data
        let stderr: Data
    }
    typealias ListenerCommandRunner = (Int32) throws -> ListenerCommandResult
    private let listenerCommand: ListenerCommandRunner
    private let identityWaitBudget: TimeInterval
    private var port: Int?
    private var connection: ZCodeBoundCDP?
    private var opening: StartupApplicationWaiter?
    private var openingToken: UUID?
    private var installation: [String: [FileAttributeKey: Any]] = [:]
    private let expectedFiles = [
        "Contents/MacOS/ZCode": "a9279c2cb198fa58efe564b417ff6717cff388c5fa391c17fc2766a6b1b2121d",
        "Contents/Info.plist": "aa29610c3c02fb37416d8a12322adf58bf1a27270718f07bbbc5ea3efe77c593",
        "Contents/Resources/app.asar": "12a2fc939df2fcb4188699772590f5151f1f2b90556bd34ecb6d44cf0d793cc6",
    ]
    init(inputs: BoundHostInputs, runtime: any NativeAppRuntime, readPayload: @escaping () throws -> String,
         stateRoot: URL, onEvent: @escaping ([String: Any]) -> Void, installationProbe: (() throws -> Void)? = nil,
         listenerCommand: ListenerCommandRunner? = nil, identityWaitBudget: TimeInterval? = nil) {
        self.inputs = inputs;self.runtime = runtime;self.readPayload = readPayload
        self.stateRoot = stateRoot;self.onEvent = onEvent;self.installationProbe = installationProbe
        self.listenerCommand = listenerCommand ?? { try Self.runListenerCommand($0) }
        self.identityWaitBudget = identityWaitBudget ?? 8
    }
    private func failure(_ reason: String) -> StartupFailure { StartupFailure(reason: reason, message: "ZCode 接入未通过本次核验。") }
    private enum DiagnosticPoint: String {
        case openPreflight = "open-preflight", openProof = "open-proof", openEnvironment = "open-environment"
        case openCallback = "open-callback", openCallbackError = "open-callback-error"
        case openSelectedGeneration = "open-selected-generation", openSelectedValidation = "open-selected-validation"
        case openActivation = "open-activation", openReceiptWrite = "open-receipt-write", openReceiptMode = "open-receipt-mode"
        case validateProcess = "validate-process", operationLock = "operation-lock"
        case recordedPort = "recorded-port", listener, transportInit = "transport-init", pageAttach = "page-attach"
    }
    // Only finite tags leave the native boundary: never error descriptions,
    // URLs, query values, path-bearing userInfo, or arbitrary exception text.
    static func diagnosticReason(for error: Error) -> String {
        let allowed: Set<String> = ["target-identity", "attach-timeout", "listener-mismatch", "endpoint-unavailable",
            "profile-isolation-unproven", "asset-invalid", "inspection-failed", "inspection-timeout", "protocol-error"]
        if let error = error as? StartupFailure { return allowed.contains(error.reason) ? error.reason : "unclassified" }
        if let error = error as? WallpaperFailure {
            return ["busy", "inspection-failed", "inspection-timeout"].contains(error.state) ? error.state : "unclassified"
        }
        if let error = error as? ZCodeBoundCDP.Failure {
            switch error {
            case .deadline: return "cdp-deadline"
            case .cancelled: return "cdp-cancelled"
            case .busy: return "cdp-busy"
            case .identity: return "cdp-identity"
            case .protocolError: return "cdp-protocol-error"
            case .unavailable: return "cdp-unavailable"
            }
        }
        return error is CancellationError ? "cancelled" : "unclassified"
    }
    private func reportFailure(_ error: Error, point: DiagnosticPoint,
                               attachment: ZCodeBoundCDP.AttachmentStage? = nil) {
        onEvent(["stage": "zcode-runtime-failed", "point": attachment.map { "cdp-" + $0.rawValue } ?? point.rawValue,
                 "reason": Self.diagnosticReason(for: error)])
    }
    private func digest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
    private func checkTime(_ deadline: TimeInterval) throws {
        if Task.isCancelled { throw CancellationError() }
        guard deadline.isFinite, runtime.uptime < deadline else { throw failure("attach-timeout") }
    }
    private func validateInstallation() throws {
        let key = inputs.identity.key
        guard key.host == .zcode, key.bundleIdentifier == "dev.zcode.app", key.version == "3.17.2", key.build == "3.17.2.9661",
              key.bundleURL.path == "/Applications/ZCode.app", key.executableURL.path == "/Applications/ZCode.app/Contents/MacOS/ZCode",
              key.executableSHA256 == expectedFiles["Contents/MacOS/ZCode"] else { throw failure("target-identity") }
        if let installationProbe { try installationProbe();return }
        if installation.isEmpty {
            var observed: [String: [FileAttributeKey: Any]] = [:]
            for (name, hash) in expectedFiles {
                let url = key.bundleURL.appendingPathComponent(name)
                guard url.resolvingSymlinksInPath() == url,
                      digest(try Data(contentsOf: url)) == hash else { throw failure("target-identity") }
                observed[name] = try FileManager.default.attributesOfItem(atPath: url.path)
            }
            _ = try WallpaperCommand.run("/usr/bin/codesign", ["--verify", "--deep", "--strict", key.bundleURL.path], timeout: 3)
            let detail = try WallpaperCommand.run("/usr/bin/codesign", ["-dv", "--verbose=4", key.bundleURL.path], timeout: 3)
            guard detail.split(separator: "\n").contains("TeamIdentifier=8A5X4JJ39T") else { throw failure("target-identity") }
            installation = observed
        } else {
            for (name, original) in installation {
                let current = try FileManager.default.attributesOfItem(atPath: key.bundleURL.appendingPathComponent(name).path)
                guard current[.systemFileNumber] as? NSNumber == original[.systemFileNumber] as? NSNumber,
                      current[.size] as? NSNumber == original[.size] as? NSNumber,
                      current[.modificationDate] as? Date == original[.modificationDate] as? Date else { throw failure("target-identity") }
            }
        }
    }
    private func generation(_ app: any NativeApplication) throws -> HostProcessGeneration {
        let key = inputs.identity.key
        guard !app.isTerminated, app.bundleIdentifier == key.bundleIdentifier,
              app.bundleURL?.resolvingSymlinksInPath() == key.bundleURL,
              app.executableURL?.resolvingSymlinksInPath() == key.executableURL,
              let birth = app.launchTime, birth.isFinite, birth > 0 else { throw failure("target-identity") }
        return HostProcessGeneration(pid: app.processIdentifier, launchTime: birth, executableURL: key.executableURL)
    }
    private func running() throws -> [HostProcessGeneration] {
        try validateInstallation()
        return try runtime.runningApplications(bundleIdentifier: inputs.identity.key.bundleIdentifier)
            .filter { !$0.isTerminated }.map { try generation($0) }
    }
    private func validate(_ process: HostProcessGeneration) throws {
        try validateInstallation()
        guard let app = runtime.application(processIdentifier: process.pid), try generation(app) == process else { throw failure("target-identity") }
    }
    // The assembly re-validates with a fresh NSRunningApplication query, and a
    // freshly opened host may not have completed its LaunchServices registration
    // yet (2026-11-08 16:44: the same binary passed on the next attempt). Wait
    // out that unregistered window instead of failing on a point-in-time
    // snapshot; a confirmed different identity still fails fast.
    private func settledValidate(_ process: HostProcessGeneration, deadline: TimeInterval) async throws {
        try validateInstallation()
        // The wait never outlives the caller's operation deadline: the identity
        // budget only narrows whatever time the operation still has left.
        let remaining = deadline - runtime.uptime
        var observed = "missing"
        guard remaining > 0 else {
            onEvent(["stage": "zcode-validate-identity-refused", "observed": "deadline-exhausted",
                     "expectedPID": Int(process.pid), "expectedLaunchTime": process.launchTime ?? -1])
            throw failure("attach-timeout")
        }
        let waitDeadline = runtime.uptime + min(identityWaitBudget, remaining)
        var attempts = 0
        while true {
            attempts += 1
            let app = runtime.application(processIdentifier: process.pid)
            if let app, !app.isTerminated {
                if let bundleID = app.bundleIdentifier, bundleID != inputs.identity.key.bundleIdentifier {
                    throw failure("target-identity")
                }
                if let candidate = try? generation(app), candidate == process { return }
                observed = app.bundleIdentifier == nil ? "unregistered" : "generation-mismatch"
            } else if let app, app.isTerminated {
                observed = "terminated";break
            }
            // The attempt cap bounds a static clock (unit fakes); the budget
            // bounds real time. Either one alone must end the wait.
            guard runtime.uptime < waitDeadline, attempts < 80 else { break }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        onEvent(["stage": "zcode-validate-identity-refused", "observed": observed,
                 "expectedPID": Int(process.pid), "expectedLaunchTime": process.launchTime ?? -1])
        throw failure("target-identity")
    }
    private func directory(_ url: URL, create: Bool) throws {
        // Foundation discovers the directory hint after creation. Compare the
        // same explicit hint on both sides; path/symlink checks stay exact.
        guard var components = URLComponents(url: url, resolvingAgainstBaseURL: false) else { throw failure("profile-isolation-unproven") }
        if !components.percentEncodedPath.hasSuffix("/") { components.percentEncodedPath += "/" }
        guard let directoryURL = components.url, url.isFileURL, url.path.hasPrefix("/"), directoryURL.standardizedFileURL == directoryURL,
              directoryURL.resolvingSymlinksInPath() == directoryURL else { throw failure("profile-isolation-unproven") }
        if create { try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700]) }
        let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
        guard attributes[.type] as? FileAttributeType == .typeDirectory,
              (attributes[.ownerAccountID] as? NSNumber)?.uint32Value == getuid(),
              ((attributes[.posixPermissions] as? NSNumber)?.intValue ?? 0o777) & 0o077 == 0 else { throw failure("profile-isolation-unproven") }
    }
    private func environment() throws -> [String: String] {
        // Daily-profile cold launch (build 36): the entry adds only the loopback
        // debugging arguments; every profile variable stays the user's own, so
        // the cold-launched ZCode opens with the user's real conversations and
        // account. An empty dictionary routes through the no-override open path
        // and leaves the inherited environment untouched. The state root stays
        // driver-owned and private for launch receipts only.
        try directory(stateRoot, create: true)
        return [:]
    }
    private func open(_ deadline: TimeInterval) async throws -> HostProcessGeneration {
        var point = DiagnosticPoint.openPreflight
        do {
            try checkTime(deadline);guard try running().isEmpty else { throw failure("target-identity") }
            point = .openProof
            let coldPayload = try readPayload()
            try validateUIProof(payloadSHA256: digest(Data(coldPayload.utf8)))
            try checkTime(deadline)
            point = .openEnvironment
            let env = try environment();let chosen = try runtime.allocateLoopbackPort();port = chosen
            onEvent(["stage": "zcode-open-request", "debuggingPort": chosen, "entryPID": runtime.processIdentifier,
                     "environmentKeys": env.keys.sorted(), "host_is_not_native_child": true])
            let token = UUID();openingToken = token
            defer { opening = nil;openingToken = nil }
            point = .openCallback
            let app: any NativeApplication = try await withTaskCancellationHandler {
                try await withCheckedThrowingContinuation { continuation in
                    let waiter = StartupApplicationWaiter(continuation);opening = waiter
                    let timeout = DispatchWorkItem { waiter.finish(.failure(StartupFailure(reason: "attach-timeout", message: "ZCode 系统启动结果未在预算内确认。"))) }
                    waiter.setTimeout(timeout);DispatchQueue.main.asyncAfter(deadline: .now() + max(0.01, min(45, deadline-runtime.uptime)), execute: timeout)
                    runtime.openApplication(at: inputs.identity.key.bundleURL, debuggingPort: chosen, environment: env) { [weak self] app, error in
                        Task { @MainActor in
                            guard let self else { waiter.finish(.failure(CancellationError()));return }
                            if let app, let process = try? self.generation(app) {
                                self.onEvent(["stage": "zcode-open-selected-process", "hostPID": process.pid,
                                    "hostStartedAt": process.launchTime!, "debuggingPort": chosen, "entryPID": self.runtime.processIdentifier,
                                    "native_child_wait_claim": false])
                            }
                            if let error { self.reportFailure(error, point: .openCallbackError) }
                            guard error == nil, let app, self.runtime.uptime < deadline else {
                                waiter.finish(.failure(self.failure("attach-timeout")));return
                            }
                            waiter.finish(.success(app))
                        }
                    }
                }
            } onCancel: { [weak self] in Task { @MainActor in
                guard self?.openingToken == token else { return };self?.opening?.finish(.failure(CancellationError()))
            } }
            point = .openSelectedGeneration
            let process = try generation(app)
            point = .openSelectedValidation
            try validate(process);try checkTime(deadline)
            point = .openActivation
            guard app.activate() else { throw failure("target-identity") }
            let record: [String: Any] = ["pid": process.pid, "launchTime": process.launchTime!, "port": chosen,
                "executableSHA256": inputs.identity.key.executableSHA256]
            let path = stateRoot.appendingPathComponent("launch-receipt.json")
            point = .openReceiptWrite
            try JSONSerialization.data(withJSONObject: record).write(to: path, options: .atomic)
            point = .openReceiptMode
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path.path)
            return process
        } catch { reportFailure(error, point: point);throw error }
    }
    // Only the exact pid's listener metadata is queried; exit1 with empty output
    // is a clean not-ready result, while any diagnostic/nonzero result refuses.
    private func listenerRows(_ process: HostProcessGeneration) throws -> String {
        let result = try listenerCommand(process.pid)
        return try Self.validatedListenerOutput(status: result.status, stdout: result.stdout, stderr: result.stderr)
    }
    // Internal test injection cannot be selected through App configuration or CLI.
    // Production always uses this same bounded Process adapter by default.
    private static func runListenerCommand(_ pid: Int32) throws -> ListenerCommandResult {
        let command = Process(), output = Pipe(), errors = Pipe(), done = DispatchSemaphore(value: 0)
        command.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        command.arguments = ["-nP", "-a", "-p", String(pid), "-iTCP", "-sTCP:LISTEN", "-FpfnT"]
        command.standardOutput = output;command.standardError = errors;command.terminationHandler = { _ in done.signal() }
        try command.run()
        if done.wait(timeout: .now()+2) == .timedOut {
            command.terminate();if done.wait(timeout: .now()+0.2) == .timedOut { kill(command.processIdentifier, SIGKILL) }
            throw StartupFailure(reason: "inspection-timeout", message: "ZCode 接入未通过本次核验。")
        }
        return ListenerCommandResult(status: command.terminationStatus,
            stdout: output.fileHandleForReading.readDataToEndOfFile(), stderr: errors.fileHandleForReading.readDataToEndOfFile())
    }
    static func validatedListenerOutput(status: Int32, stdout: Data, stderr: Data) throws -> String {
        if status == 1 && stdout.isEmpty && stderr.isEmpty { return "" }
        guard status == 0, stderr.isEmpty, stdout.count < 65536, let text = String(data: stdout, encoding: .utf8) else {
            throw StartupFailure(reason: "inspection-failed", message: "ZCode listener inspection returned diagnostics or incomplete data.")
        }
        return text
    }
    private func kernelReady(_ process: HostProcessGeneration, port: Int) throws -> Bool {
        try validate(process);let text = try listenerRows(process)
        if text.isEmpty { return false }
        var owner = false, found = false
        for line in text.split(separator: "\n") {
            if line.hasPrefix("p") { guard String(line.dropFirst()) == String(process.pid) else { throw failure("listener-mismatch") };owner = true }
            if line.hasPrefix("n") {
                let address = String(line.dropFirst());guard owner,
                    address.hasPrefix("127.0.0.1:") || address.hasPrefix("[::1]:") else { throw failure("listener-mismatch") }
                if address.hasSuffix(":" + String(port)) { found = true }
            }
        }
        return found
    }
    private func recordedPort(_ process: HostProcessGeneration) throws -> Int {
        if let port { return port }
        try directory(stateRoot, create: false)
        let url = stateRoot.appendingPathComponent("launch-receipt.json")
        guard url.resolvingSymlinksInPath() == url, let data = try? Data(contentsOf: url), data.count < 4096,
              let record = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              record["pid"] as? Int32 == process.pid, record["launchTime"] as? Double == process.launchTime,
              record["executableSHA256"] as? String == inputs.identity.key.executableSHA256,
              let port = record["port"] as? Int, (1...65535).contains(port) else { throw failure("endpoint-unavailable") }
        self.port = port;return port
    }
    private func reportDiscovery(_ client: ZCodeBoundCDP) {
        guard let initial = client.initialDiscoveryCounts, let latest = client.latestDiscoveryCounts else { return }
        onEvent(["stage": "zcode-target-summary", "attempts": client.discoveryAttempts, "initial": initial, "latest": latest])
    }
    static func normalizedAttachFailure(_ error: Error, deadline: TimeInterval, now: TimeInterval, cancelled: Bool) -> Error {
        if cancelled || error is CancellationError { return ZCodeAttachFailure.cancelled }
        if !deadline.isFinite || now >= deadline { return ZCodeAttachFailure.deadline }
        if let failure = error as? ZCodeBoundCDP.Failure {
            switch failure {
            case .deadline: return ZCodeAttachFailure.deadline
            case .cancelled: return ZCodeAttachFailure.cancelled
            default: break
            }
        }
        if let failure = error as? StartupFailure, failure.reason == "attach-timeout" {
            return ZCodeAttachFailure.deadline
        }
        return error
    }
    private func attach(_ process: HostProcessGeneration, deadline: TimeInterval, purpose: ZCodeAttachPurpose) async throws -> ZCodePageBinding {
        let waitForInitialMain: Bool
        switch purpose { case .coldLaunch: waitForInitialMain = true; case .existingPage: waitForInitialMain = false }
        let attachDeadline = purpose.stageDeadline(caller: deadline, now: runtime.uptime)
        let chosen: Int
        do { chosen = try recordedPort(process) }
        catch { reportFailure(error, point: .recordedPort);throw Self.normalizedAttachFailure(error, deadline: attachDeadline, now: runtime.uptime, cancelled: Task.isCancelled) }
        do {
            while true {
                try checkTime(attachDeadline)
                let ready: Bool
                do { ready = try kernelReady(process, port: chosen) }
                catch { try checkTime(attachDeadline); throw error }
                try checkTime(attachDeadline)
                if ready { break }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
        } catch { reportFailure(error, point: .listener);throw Self.normalizedAttachFailure(error, deadline: attachDeadline, now: runtime.uptime, cancelled: Task.isCancelled) }
        let client: ZCodeBoundCDP
        do { client = try ZCodeBoundCDP(process: process, endpoint: URL(string: "http://127.0.0.1:\(chosen)")!,
            installedPage: inputs.identity.key.bundleURL.appendingPathComponent("Contents/Resources/app.asar/out/renderer/index.html").path,
            now: { [runtime] in runtime.uptime }, guardLive: { [weak self] in
                guard let self, try self.kernelReady(process, port: chosen) else { throw StartupFailure(reason: "listener-mismatch", message: "ZCode endpoint identity changed.") }
            }) } catch { reportFailure(error, point: .transportInit);throw error }
        connection?.close();connection = client
        do {
            let binding = try await client.attach(deadline: attachDeadline, waitForInitialMain: waitForInitialMain)
            reportDiscovery(client)
            onEvent(["stage": "zcode-page-bound", "hostPID": process.pid, "hostStartedAt": process.launchTime!,
                "debuggingPort": chosen, "targetID": binding.targetID,
                "documentTokenSHA256": digest(Data(binding.documentToken.utf8))])
            return binding
        } catch { reportDiscovery(client);reportFailure(error, point: .pageAttach, attachment: client.attachmentStage);client.close();connection = nil;throw Self.normalizedAttachFailure(error, deadline: attachDeadline, now: runtime.uptime, cancelled: Task.isCancelled) }
    }
    private func install(_ binding: ZCodePageBinding, request: SkinLaunchRequest, observation: ZCodeInstallObservation) async throws -> SkinLaunchResult {
        guard let client = connection else { throw failure("endpoint-unavailable") }
        let payload = try readPayload(), hash = digest(Data(payload.utf8))
        try validateUIProof(payloadSHA256: hash)
        guard payload.hasPrefix("((controllerMetadata) => {"), payload.trimmingCharacters(in: .whitespacesAndNewlines).hasSuffix("})") else { throw failure("asset-invalid") }
        let result = try await client.install(factoryBytes: payload, payloadSHA256: hash, operationID: request.operationID,
            observation: observation, deadline: request.deadline)
        guard result["installed"] as? Bool == true, let already = result["alreadyActive"] as? Bool else { throw failure("protocol-error") }
        let acquisition: PageAcquisition = already ? .alreadyActive : .created
        var receipt: ControllerReceipt?
        do {
            while true {
                try checkTime(request.deadline)
                let status = try await client.safeStatus(deadline: request.deadline)
                receipt = try client.acknowledgedReceipt(status, key: inputs.identity.key, payloadSHA256: hash, acquisition: acquisition)
                if already { return .skipped(.present(.instance(receipt!), acquisition: .alreadyActive), runID: status["runId"] as? Int ?? 0, beforeReady: false) }
                if status["ready"] as? Bool == true {
                    onEvent(["stage": "zcode-controller-ready", "operationID": request.operationID.uuidString,
                        "hostPID": binding.process.pid, "payloadSHA256": hash,
                        "controllerInstanceID": receipt!.controllerInstanceID, "runId": status["runId"] as? Int ?? 0,
                        "completion_observed": status["completed"] as? Bool == true])
                    return .ready(receipt!, runID: status["runId"] as? Int ?? 0)
                }
                if status["completed"] as? Bool == true {
                    let completion = status["completion"] as? [String: Any]
                    return .skipped(.present(.instance(receipt!), acquisition: .created), runID: status["runId"] as? Int ?? 0,
                        beforeReady: completion?["beforeReady"] as? Bool ?? true)
                }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
        } catch {
            guard let receipt else { throw error }
            return .partial(SkinOperationFailure(reason: Task.isCancelled ? .operationCancelled : .protocolError,
                detail: "ZCode controller confirmed before later interruption"),
                page: .present(.instance(receipt), acquisition: acquisition),
                cleanup: CleanupReport(state: .unknown, released: [], intentionallyRetained: ["confirmed-ZCode-page-controller"], unconfirmed: ["current-page-controller"]))
        }
    }
    func makeAssembly() -> ZCodeSkinAssembly {
        ZCodeSkinAssembly(now: { [runtime] in runtime.uptime }, runningProcesses: { try self.running() },
            validateProcess: { process, deadline in
                do { try await self.settledValidate(process, deadline: deadline) }
                catch { self.reportFailure(error, point: .validateProcess);throw error }
            }, activateExisting: { process, deadline in
                try await self.settledValidate(process, deadline: deadline);return self.runtime.application(processIdentifier: process.pid)?.activate() == true
            }, openApplication: { try await self.open($0) }, attach: { try await self.attach($0, deadline: $1, purpose: $2) },
            install: { try await self.install($0, request: $1, observation: $2) }, inspectPage: { binding, deadline in
                defer { self.connection?.close();self.connection = nil }
                guard let client = self.connection else { throw self.failure("endpoint-unavailable") }
                let status = try await client.safeStatus(deadline: deadline)
                if status["present"] as? Bool == false { return .absent(PageLocation(application: self.inputs.identity.key, process: binding.process, documentToken: binding.documentToken)) }
                let hash = self.digest(Data(try self.readPayload().utf8))
                return .present(.instance(try client.acknowledgedReceipt(status, key: self.inputs.identity.key, payloadSHA256: hash, acquisition: .alreadyActive)), acquisition: .alreadyActive)
            }, dispose: { _, receipt, deadline in
                defer { self.connection?.close();self.connection = nil }
                guard let client = self.connection else { throw self.failure("endpoint-unavailable") }
                return try await client.disposeConfirmed(receipt, deadline: deadline)
            }, acquireOperation: { pid in
                do {
                    let lock = try WallpaperOperationLock.acquire(pid: pid)
                    return ZCodeRuntimeLease { self.connection?.close();self.connection = nil;lock.release() }
                } catch {
                    self.reportFailure(error, point: .operationLock)
                    if let failure = error as? WallpaperFailure, failure.state == "busy" {
                        throw ZCodeOperationLockFailure.busy
                    }
                    throw error
                }
            })
    }
}

extension ZCodeNativeRuntime {
    // A build-owned, hash-bound receipt from the actual UI acceptance window.
    // It is not an auth/profile file and is never synthesized from fixture passes.
    private static func evidenceTimeValid(_ value: String) -> Bool {
        if ISO8601DateFormatter().date(from: value) != nil { return true }
        let fractional = ISO8601DateFormatter();fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return fractional.date(from: value) != nil
    }
    private static func proof(_ resources: URL?) -> [String: Any]? {
        guard let resources else { return nil }
        // Bundle.resourceURL can retain a base URL. Flatten that representation
        // before the unchanged symlink/physical-path comparison.
        let path = resources.appendingPathComponent("zcode-validation.json").absoluteURL
        guard path.resolvingSymlinksInPath() == path, let data = try? Data(contentsOf: path), data.count < 16384,
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              value["schema"] as? String == "agent-skin-zcode-ui-evidence/v1",
              value["contractVersion"] as? String == SkinHostContract.version,
              let recordID = value["recordID"] as? String, !recordID.isEmpty, recordID.utf8.count <= 256,
              !recordID.contains("\n"),
              let recordSHA = value["recordSHA256"] as? String, recordSHA.utf8.count == 64,
              recordSHA.allSatisfy({ "0123456789abcdef".contains($0) }),
              let observedAt = value["observedAt"] as? String, evidenceTimeValid(observedAt),
              value["infoSHA256"] as? String == "aa29610c3c02fb37416d8a12322adf58bf1a27270718f07bbbc5ea3efe77c593",
              value["version"] as? String == "3.17.2.9661",
              value["executableSHA256"] as? String == "a9279c2cb198fa58efe564b417ff6717cff388c5fa391c17fc2766a6b1b2121d",
              value["appAsarSHA256"] as? String == "12a2fc939df2fcb4188699772590f5151f1f2b90556bd34ecb6d44cf0d793cc6",
              let hash = value["payloadSHA256"] as? String, hash.utf8.count == 64,
              hash.allSatisfy({ "0123456789abcdef".contains($0) }),
              let ids = value["evidenceIDs"] as? [String], !ids.isEmpty,
              ids.allSatisfy({ !$0.isEmpty && $0.utf8.count <= 256 && !$0.contains("\n") }) else { return nil }
        return value
    }
    static func findings(for key: HostApplicationKey, resources: URL?) -> [CapabilityFinding] {
        let proof = proof(resources), ids = proof?["evidenceIDs"] as? [String] ?? []
        return SkinCapability.allCases.map { capability in
            let isUI = capability == .ownedAppearanceSurface || capability == .persistentSettings
            let field = capability == .ownedAppearanceSurface ? "ownedAppearanceSurface" : "persistentSettings"
            let state: EvidenceState = isUI ? (proof?[field] as? Bool == true ? .verified : .unverified) : .verified
            return CapabilityFinding(subject: CapabilityEvidenceSubject(application: key,
                surface: SkinHostContract.surface(for: capability), contractVersion: SkinHostContract.version),
                capability: capability, state: state,
                evidenceIDs: isUI ? ids : ["fixed-3.17.2.9661-host-entry08-H1", "ZCode-native-contract-tests"],
                reason: isUI ? "requires actual hash-bound ZCode UI evidence; fixtures do not fill this receipt"
                    : "host capability established by fixed-install H1 and contract tests; live identity/context rechecked per operation; Native entry acceptance remains separate")
        }
    }
    func validateUIProof(payloadSHA256: String) throws {
        guard let value = Self.proof(runtime.resourceURL), value["payloadSHA256"] as? String == payloadSHA256,
              value["ownedAppearanceSurface"] as? Bool == true, value["persistentSettings"] as? Bool == true else {
            throw StartupFailure(reason: "asset-invalid", message: "ZCode 尚缺本候选真实外观与保存证据。")
        }
    }
}
