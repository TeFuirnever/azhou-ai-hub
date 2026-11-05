// ZCode-specific strategy. Transport and native UI ports are supplied by C0.
// No Codex target/controller assumptions or host-side mutations at construction.
import Foundation

@MainActor protocol ZCodeOperationLease: AnyObject { func release() }
@MainActor final class ZCodeInstallObservation {
    private(set) var sent = false
    func markSent() { sent = true }
}
struct ZCodePageBinding: Sendable {
    let process: HostProcessGeneration
    let endpoint: URL
    let pageURL: URL
    let targetID: String
    let documentToken: String
}
@MainActor struct ZCodeSkinAssembly {
    let now: () -> TimeInterval
    let runningProcesses: () throws -> [HostProcessGeneration]
    let validateProcess: (HostProcessGeneration) throws -> Void
    let activateExisting: (HostProcessGeneration) throws -> Bool
    let openApplication: (TimeInterval) async throws -> HostProcessGeneration
    let attach: (HostProcessGeneration, TimeInterval) async throws -> ZCodePageBinding
    // markSent() immediately before the first page-changing install send.
    let install: (ZCodePageBinding, SkinLaunchRequest, ZCodeInstallObservation) async throws -> SkinLaunchResult
    let inspectPage: (ZCodePageBinding, TimeInterval) async throws -> PageEffect
    let dispose: (ZCodePageBinding, ControllerReceipt, TimeInterval) async throws -> Bool
    let acquireOperation: (Int32) throws -> any ZCodeOperationLease
}
@MainActor final class ZCodeSkinDriver: SkinHostDriver {
    static let owner = "azhou-zcode-startup"
    private let inputs: BoundHostInputs
    private let assembly: ZCodeSkinAssembly
    private var busy = false
    init(inputs: BoundHostInputs, assembly: ZCodeSkinAssembly) {
        self.inputs = inputs; self.assembly = assembly
    }
    private struct Stop: Error { let reason: SkinFailureReason; let detail: String }
    private func checkTime(_ deadline: TimeInterval) throws {
        if Task.isCancelled { throw Stop(reason: .operationCancelled, detail: "operation-cancelled") }
        guard deadline.isFinite, assembly.now() < deadline else {
            throw Stop(reason: .operationTimeout, detail: "operation-deadline")
        }
    }
    private func refusal(_ key: HostApplicationKey) -> HostRefusal? {
        guard inputs.identity.key.host == .zcode, inputs.contractVersion == SkinHostContract.version,
              key == inputs.identity.key else {
            return HostRefusal(host: .zcode, reason: .identityMismatch, findings: [],
                detail: "ZCode bound installation identity required", nextProbe: nil)
        }
        // Do not accept forged/mismatched capability subjects when constructed directly.
        var seen = Set<SkinCapability>()
        for f in inputs.findings {
            guard seen.insert(f.capability).inserted,
                  f.subject.application == key, f.subject.contractVersion == inputs.contractVersion,
                  f.subject.surface == SkinHostContract.surface(for: f.capability),
                  f.state != .verified || !f.evidenceIDs.isEmpty else {
                return HostRefusal(host: .zcode, reason: .evidenceMismatch, findings: inputs.findings,
                    detail: "ZCode capability evidence subject mismatch", nextProbe: nil)
            }
        }
        return nil
    }
    private func validate(_ process: HostProcessGeneration) throws {
        guard process.pid > 0, let birth = process.launchTime, birth.isFinite, birth > 0,
              process.executableURL == inputs.identity.key.executableURL else {
            throw Stop(reason: .targetIdentity, detail: "process-generation-incomplete")
        }
        try assembly.validateProcess(process)
    }
    private func validate(_ binding: ZCodePageBinding, process: HostProcessGeneration) throws {
        try validate(process)
        guard binding.process == process, !binding.targetID.isEmpty, !binding.documentToken.isEmpty,
              let endpoint = URLComponents(url: binding.endpoint, resolvingAgainstBaseURL: false),
              endpoint.scheme == "http", ["127.0.0.1", "::1", "[::1]"].contains(endpoint.host ?? ""),
              let port = endpoint.port, (1...65535).contains(port),
              endpoint.user == nil, endpoint.password == nil, endpoint.query == nil, endpoint.fragment == nil,
              endpoint.path.isEmpty || endpoint.path == "/" else {
            throw Stop(reason: .targetIdentity, detail: "owned-loopback-binding-required")
        }
        guard let page = URLComponents(url: binding.pageURL, resolvingAgainstBaseURL: false),
              page.scheme == "file", (page.host ?? "").isEmpty, page.user == nil, page.password == nil,
              page.fragment == nil,
              page.path == inputs.identity.key.bundleURL.appendingPathComponent("Contents/Resources/app.asar/out/renderer/index.html").path else {
            throw Stop(reason: .targetIdentity, detail: "installed-main-page-required")
        }
        let allowed: Set<String> = ["restoreSession", "supportsSettings", "initialWorkspacePath", "initialWorkspacePurpose", "unavailableWorkspacePath", "windowKind", "locale", "zcodeLaunchMarks"]
        var seen = Set<String>()
        for item in page.queryItems ?? [] {
            guard allowed.contains(item.name), seen.insert(item.name).inserted,
                  item.name != "windowKind" || item.value == "main" else {
                throw Stop(reason: .targetIdentity, detail: "bootstrap-query-key-rejected")
            }
        }
    }
    private func location(_ observation: PageObservation) -> PageLocation {
        switch observation { case .instance(let r): return r.location; case .legacyV1(let r): return r.location }
    }
    private func sameLocation(_ a: PageLocation, _ b: PageLocation) -> Bool {
        a.application == b.application && a.process == b.process && a.documentToken == b.documentToken
    }
    private func validReceipt(_ r: ControllerReceipt, _ b: ZCodePageBinding) -> Bool {
        r.location.application == inputs.identity.key && r.location.process == b.process &&
        r.location.documentToken == b.documentToken && r.owner == Self.owner && r.protocolVersion == 1 &&
        r.payloadSHA256.utf8.count == 64 && r.payloadSHA256.range(of: "^[a-f0-9]{64}$", options: .regularExpression) != nil &&
        !r.controllerInstanceID.isEmpty && r.controllerInstanceID != SkinHostContract.legacyUnreportedInstanceID
    }
    private func errorReason(_ error: Error) -> SkinOperationFailure {
        if let e = error as? Stop { return SkinOperationFailure(reason: e.reason, detail: e.detail) }
        return SkinOperationFailure(reason: Task.isCancelled ? .operationCancelled : .protocolError,
                                    detail: "ZCode-operation-unconfirmed")
    }
    private func failed(_ error: Error, _ request: SkinLaunchRequest, sent: Bool) -> SkinLaunchResult {
        .failed(errorReason(error),
            page: sent ? .unknown(operationID: request.operationID, detail: "install-sent-result-unconfirmed") : .notObserved(reason: "install-not-sent"),
            cleanup: CleanupReport(state: sent ? .unknown : .notNeeded, released: [], intentionallyRetained: [], unconfirmed: sent ? ["page-controller"] : []))
    }
    func launch(_ request: SkinLaunchRequest) async -> SkinLaunchResult {
        if let r = refusal(request.expectedApplication) { return .refused(r) }
        if busy { return failed(Stop(reason: .operationBusy, detail: "page-operation-in-flight"), request, sent: false) }
        let observation = ZCodeInstallObservation()
        var committed: (receipt: ControllerReceipt, acquisition: PageAcquisition, cleanup: CleanupReport?)?
        do {
            guard request.startedAt.isFinite, request.startedAt <= assembly.now() else { throw Stop(reason: .protocolError, detail: "invalid-start-time") }
            let deadline = min(request.deadline, request.startedAt + 60)
            try checkTime(deadline)
            let running = try assembly.runningProcesses()
            guard running.count <= 1 else { throw Stop(reason: .targetIdentity, detail: "ambiguous-running-instance") }
            let stage: SkinOperationStage = running.isEmpty ? .coldLaunchSkin : .activateExisting
            if let r = capabilityRefusal(for: stage, inputs: inputs) { return .refused(r) }
            busy = true; defer { busy = false }
            if let process = running.first {
                try validate(process); try checkTime(deadline)
                guard try assembly.activateExisting(process) else { throw Stop(reason: .targetStale, detail: "activation-unconfirmed") }
                try validate(process)
                return .activated(process) // No port, attach, payload, replay or restart.
            }
            let process = try await assembly.openApplication(deadline)
            try validate(process); try checkTime(deadline)
            let lease = try assembly.acquireOperation(process.pid); defer { lease.release() }
            let binding = try await assembly.attach(process, deadline)
            try validate(binding, process: process); try checkTime(deadline)
            let bounded = SkinLaunchRequest(expectedApplication: request.expectedApplication, operationID: request.operationID, startedAt: request.startedAt, deadline: deadline)
            let result = try await assembly.install(binding, bounded, observation)
            // Every result can carry a confirmed page, including partial failure
            // and alreadyActive skips. Preserve the exact acquisition, never gain
            // rollback rights over an instance created by an earlier operation.
            let confirmedPage: PageEffect?
            let confirmedCleanup: CleanupReport?
            switch result {
            case .ready(let receipt, _):
                confirmedPage = .present(.instance(receipt), acquisition: .created)
                confirmedCleanup = nil
            case .skipped(let page, _, _):
                confirmedPage = page; confirmedCleanup = nil
            case .partial(_, let page, let cleanup), .failed(_, let page, let cleanup):
                confirmedPage = page; confirmedCleanup = cleanup
            default: confirmedPage = nil; confirmedCleanup = nil
            }
            if case .present(let instance, let acquisition) = confirmedPage {
                guard case .instance(let receipt) = instance, validReceipt(receipt, binding) else {
                    throw Stop(reason: .ownerConflict, detail: "controller-receipt-mismatch")
                }
                if case .created = acquisition {
                    guard receipt.createdByOperationID == request.operationID else {
                        throw Stop(reason: .ownerConflict, detail: "controller-operation-mismatch")
                    }
                }
                committed = (receipt, acquisition, confirmedCleanup)
            }
            try validate(binding, process: process); try checkTime(deadline)
            switch result {
            case .ready(let r, let runID):
                guard validReceipt(r, binding), r.createdByOperationID == request.operationID else { throw Stop(reason: .protocolError, detail: "controller-receipt-mismatch") }
                return .ready(r, runID: runID)
            case .skipped(let page, let runID, let beforeReady):
                if case .present(.instance(let r), _) = page {
                    guard validReceipt(r, binding) else { throw Stop(reason: .ownerConflict, detail: "existing-controller-mismatch") }
                } else if !page.isNotObserved || observation.sent {
                    throw Stop(reason: .protocolError, detail: "skip-observation-unverified")
                }
                return .skipped(page, runID: runID, beforeReady: beforeReady)
            case .partial, .failed:
                // A transport result cannot erase an uncertain install send.
                if committed == nil && observation.sent { return failed(Stop(reason: .protocolError, detail: "install-result-partial"), request, sent: true) }
                return result
            case .refused: return observation.sent ? failed(Stop(reason: .protocolError, detail: "refusal-after-send"), request, sent: true) : result
            case .activated: throw Stop(reason: .protocolError, detail: "cold-install-cannot-activate")
            }
        } catch {
            if let confirmed = committed {
                // The old bound document acknowledged a commit. Never relabel it
                // unknown or roll it back just because a later check was cancelled.
                let failure = errorReason(error)
                let retained = failure.reason == .operationCancelled || failure.reason == .operationTimeout
                return .partial(failure, page: .present(.instance(confirmed.receipt), acquisition: confirmed.acquisition),
                    cleanup: confirmed.cleanup ?? CleanupReport(state: retained ? .notNeeded : .unknown, released: [],
                        intentionallyRetained: ["confirmed-ZCode-page-controller"],
                        unconfirmed: retained ? [] : ["current-page-controller"]))
            }
            return failed(error, request, sent: observation.sent)
        }
    }
    func inspect(_ request: SkinInspectRequest) async -> SkinInspectResult {
        if let r = refusal(request.expectedApplication) { return .unavailable(r) }
        if let r = capabilityRefusal(for: request.includePage ? .inspectPage : .inspectApplication, inputs: inputs) { return .unavailable(r) }
        do {
            try checkTime(request.deadline)
            let running = try assembly.runningProcesses()
            guard running.count <= 1 else { throw Stop(reason: .targetIdentity, detail: "ambiguous-running-instance") }
            guard let process = running.first else { return .observed(process: nil, page: .notObserved(reason: "application-not-running")) }
            try validate(process)
            if !request.includePage { return .observed(process: process, page: .notObserved(reason: "application-only")) }
            let b = try await assembly.attach(process, request.deadline); try validate(b, process: process)
            if let previous = request.previousObservation, !sameLocation(location(previous), PageLocation(application: inputs.identity.key, process: process, documentToken: b.documentToken)) { throw Stop(reason: .targetStale, detail: "document-generation-changed") }
            let page = try await assembly.inspectPage(b, request.deadline)
            try validate(b, process: process); try checkTime(request.deadline)
            switch page {
            case .present(.instance(let r), _): guard validReceipt(r, b) else { throw Stop(reason: .ownerConflict, detail: "controller-receipt-mismatch") }
            case .absent(let l): guard sameLocation(l, PageLocation(application: inputs.identity.key, process: process, documentToken: b.documentToken)) else { throw Stop(reason: .targetStale, detail: "absence-location-mismatch") }
            case .present(.legacyV1, _): throw Stop(reason: .ownerConflict, detail: "legacy-controller-not-ZCode")
            case .notObserved, .unknown: break
            }
            return .observed(process: process, page: page)
        } catch { return .staleTarget(errorReason(error)) }
    }
    func disable(_ request: SkinDisableRequest) async -> SkinDisableResult {
        if let r = refusal(request.expectedApplication) { return .unavailable(r) }
        if let r = capabilityRefusal(for: .disableSkin, inputs: inputs) { return .unavailable(r) }
        let effect = PageEffect.present(request.expectedPage, acquisition: .alreadyActive)
        guard !busy else { return .refused(SkinOperationFailure(reason: .operationBusy, detail: "page-operation-in-flight"), page: effect) }
        guard case .instance(let receipt) = request.expectedPage,
              receipt.location.application == inputs.identity.key, receipt.owner == Self.owner, receipt.protocolVersion == 1 else {
            return .refused(SkinOperationFailure(reason: .ownerConflict, detail: "only-owned-ZCode-instance-may-dispose"), page: effect)
        }
        busy = true; defer { busy = false }
        var sent = false
        do {
            try checkTime(request.deadline)
            let running = try assembly.runningProcesses()
            guard running.count <= 1 else { throw Stop(reason: .targetIdentity, detail: "ambiguous-running-instance") }
            guard let process = running.first else { return .alreadyAbsent(receipt.location) }
            guard process == receipt.location.process else { throw Stop(reason: .targetStale, detail: "process-generation-changed") }
            try validate(process)
            let lease = try assembly.acquireOperation(process.pid); defer { lease.release() }
            let b = try await assembly.attach(process, request.deadline); try validate(b, process: process)
            guard validReceipt(receipt, b) else { throw Stop(reason: .targetStale, detail: "controller-generation-changed") }
            try checkTime(request.deadline); sent = true
            guard try await assembly.dispose(b, receipt, request.deadline) else { throw Stop(reason: .protocolError, detail: "dispose-unconfirmed") }
            try validate(b, process: process); try checkTime(request.deadline)
            return .removed(CleanupReport(state: .complete, released: ["ZCode-page-controller"], intentionallyRetained: [], unconfirmed: []))
        } catch {
            if !sent { return .refused(errorReason(error), page: effect) }
            return .partial(errorReason(error), page: .unknown(operationID: request.operationID, detail: "dispose-sent-result-unconfirmed"), cleanup: CleanupReport(state: .unknown, released: [], intentionallyRetained: [], unconfirmed: ["page-controller"]))
        }
    }
}
