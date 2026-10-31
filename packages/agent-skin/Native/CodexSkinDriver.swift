// Codex adapter over the shared skin host contract (agent-skin-zcode-contract/v0.1).
// Thin wrapper: the strategy order previously owned by AppDelegate.startTrustedSession
// moved here unchanged (validate → activate for an existing instance; preflight →
// coldStart otherwise). Codex-only types (StartupTargetSystem, StartupConnector,
// CDP transports) stay inside this adapter; the neutral SkinHostDriver protocol in
// SkinHostContract.swift never mentions them.
//
// The driver takes no operation lock itself: the per-process WallpaperOperationLock
// keeps exactly one owning layer — StartupConnector.attach for launch and
// WallpaperCLI.perform for explicit disable (spec §7.4).
import Foundation

// Only inside the Codex adapter; these types never appear in the neutral contract.
typealias CodexConnectorFactory = @MainActor (
    StartupTargetFacts,
    Int,
    any StartupTargetSystem,
    NativeStartupCapture,
    NativeStartupEventStream
) -> StartupConnector

/// Per-attempt record of whether the install expression was actually sent to the
/// page. Native cannot observe the commit point directly (spec §7.3), so the
/// transport wrapper below records the send; a lost reply after a send is an
/// installation-unknown outcome and never a fully-clean cleanup.
@MainActor
final class CodexInstallObservation {
    private(set) var installSentCount = 0

    func reset() { installSentCount = 0 }
    func markInstallSent() { installSentCount += 1 }
}

/// Transport wrapper that records the install send and delegates everything else.
@MainActor
final class InstallObservingStartupTransport: StartupTransport {
    /// StartupConnector.installExpression is the only expression that resolves the
    /// embedded payload through Promise.resolve; seeing it means the install was sent.
    private static let installMarker = "Promise.resolve(("
    private let base: any StartupTransport
    private let recorder: CodexInstallObservation

    init(base: any StartupTransport, recorder: CodexInstallObservation) {
        self.base = base
        self.recorder = recorder
    }

    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        try await base.pages(port: port, timeout: timeout)
    }

    func connect(to url: URL, timeout: TimeInterval) throws {
        try base.connect(to: url, timeout: timeout)
    }

    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        if source.contains(Self.installMarker) { recorder.markInstallSent() }
        return try await base.evaluate(source, timeout: timeout)
    }

    func close() { base.close() }
}

/// App-owned assembly points (UI state, event stream, opening Codex). The driver
/// owns order, gates, budgets and result mapping; the AppDelegate owns presentation
/// state and the native event stream. All closures are side-effect ports the
/// driver calls in the exact order startTrustedSession used before.
@MainActor
struct CodexSkinAssembly {
    let preflightBundle: (URL, StartupBudget) throws -> Void
    let activateExisting: (StartupTargetFacts) throws -> Bool
    let preparePort: () throws -> Int
    let openApplication: (URL, Int, TimeInterval, any StartupTargetSystem) async throws -> any NativeApplication
    let onTargetOpened: (any NativeApplication) -> Void
    let onCaptureReady: (NativeStartupCapture) -> Void
    let eventStream: () -> NativeStartupEventStream?
    let onOpeningChanged: (Bool) -> Void
    let startupFacts: (any NativeApplication) throws -> StartupTargetFacts
    /// Explicit page-controller disposal delegation. Production disable remains
    /// WallpaperCLI's owned path in C0; when nil the driver refuses explicitly
    /// instead of silently degrading.
    let performDisable: ((StartupTargetFacts, String, TimeInterval) async throws -> [String: Any])?
}

@MainActor
final class CodexSkinDriver: SkinHostDriver {
    private let inputs: BoundHostInputs
    private let runtime: any NativeAppRuntime
    private let readPayload: () throws -> String
    private let makeTargetSystem: () -> any StartupTargetSystem
    private let makeConnector: CodexConnectorFactory
    private let installObservation: CodexInstallObservation
    private let assembly: CodexSkinAssembly
    private var pageOperationInFlight = false

    /// Stores dependencies only. Never reads the payload, allocates ports, builds
    /// a transport, launches the host or touches a page here (spec §6.3).
    init(
        inputs: BoundHostInputs,
        runtime: any NativeAppRuntime,
        readPayload: @escaping () throws -> String,
        makeTargetSystem: @escaping () -> any StartupTargetSystem,
        makeConnector: @escaping CodexConnectorFactory,
        installObservation: CodexInstallObservation,
        assembly: CodexSkinAssembly
    ) {
        self.inputs = inputs
        self.runtime = runtime
        self.readPayload = readPayload
        self.makeTargetSystem = makeTargetSystem
        self.makeConnector = makeConnector
        self.installObservation = installObservation
        self.assembly = assembly
    }

    // MARK: - launch

    func launch(_ request: SkinLaunchRequest) async -> SkinLaunchResult {
        guard request.expectedApplication == inputs.identity.key else {
            return .refused(HostRefusal(host: inputs.identity.key.host, reason: .identityMismatch,
                                        findings: inputs.findings,
                                        detail: "request targets another application identity",
                                        nextProbe: nil))
        }
        guard !pageOperationInFlight else {
            return busyResult(detail: "a page-changing launch is already in flight on this driver")
        }
        let running = runtime.runningApplications(bundleIdentifier: inputs.identity.key.bundleIdentifier)
            .filter { !$0.isTerminated }
        let matching = running.filter {
            $0.bundleURL.map { $0.resolvingSymlinksInPath().standardizedFileURL } == inputs.identity.key.bundleURL
        }
        guard running.isEmpty || (running.count == 1 && matching.count == 1) else {
            return .refused(HostRefusal(host: inputs.identity.key.host, reason: .identityMismatch,
                                        findings: inputs.findings,
                                        detail: "running Codex processes do not resolve to one verified target",
                                        nextProbe: nil))
        }
        let existing: StartupTargetFacts?
        if let app = matching.first {
            guard let facts = try? assembly.startupFacts(app) else {
                return .refused(HostRefusal(host: inputs.identity.key.host, reason: .identityMismatch,
                                            findings: inputs.findings,
                                            detail: "running Codex process lacks a complete identity",
                                            nextProbe: nil))
            }
            existing = facts
        } else {
            existing = nil
        }
        // Per-branch capability gate before the branch's first side effect.
        let stage: SkinOperationStage = existing == nil ? .coldLaunchSkin : .activateExisting
        if let refusal = capabilityRefusal(for: stage, inputs: inputs) {
            return .refused(refusal)
        }
        pageOperationInFlight = true
        defer { pageOperationInFlight = false }
        let system = makeTargetSystem()
        let budget = StartupBudget(startedAt: request.startedAt)
        let outcome: StartupOutcome
        do {
            outcome = try await StartupLaunchFlow.run(
                existing: existing,
                preflightBundle: { try self.assembly.preflightBundle(self.inputs.identity.key.bundleURL, budget) },
                validate: { try system.validate($0, deadline: budget.preflightDeadline) },
                activate: { try self.assembly.activateExisting($0) },
                coldStart: {
                    let payload = try self.readPayload()
                    guard self.runtime.uptime < budget.totalDeadline else {
                        throw StartupFailure(reason: "attach-timeout", message: "Codex 启动已超过 60 秒总预算。")
                    }
                    let port = try self.assembly.preparePort()
                    let attachDeadline = budget.attachDeadline(startedAt: self.runtime.uptime)
                    self.assembly.onOpeningChanged(true)
                    let app = try await self.assembly.openApplication(self.inputs.identity.key.bundleURL,
                                                                      port, attachDeadline, system)
                    self.assembly.onOpeningChanged(false)
                    self.assembly.onTargetOpened(app)
                    let facts = try self.assembly.startupFacts(app)
                    let capture = NativeStartupCapture(targetPID: facts.pid)
                    self.assembly.onCaptureReady(capture)
                    let stream = self.assembly.eventStream()
                    stream?.targetOpened(pid: facts.pid, at: self.runtime.uptime)
                    guard let eventStream = stream else {
                        throw StartupFailure(reason: "protocol-error", message: "原生启动事件流不可用。")
                    }
                    self.installObservation.reset()
                    return await self.makeConnector(facts, port, system, capture, eventStream)
                        .run(payload: payload, deadline: attachDeadline)
                }
            )
        } catch let error as StartupFailure {
            outcome = .failed(reason: error.reason)
        } catch {
            outcome = .failed(reason: "protocol-error")
        }
        assembly.onOpeningChanged(false)
        return Self.bridge(outcome, request: request, key: inputs.identity.key,
                           observation: installObservation)
    }

    // MARK: - inspect (read-only; never cold-starts the host or installs controllers)

    func inspect(_ request: SkinInspectRequest) async -> SkinInspectResult {
        guard request.expectedApplication == inputs.identity.key else {
            return .unavailable(HostRefusal(host: inputs.identity.key.host, reason: .identityMismatch,
                                            findings: inputs.findings,
                                            detail: "request targets another application identity",
                                            nextProbe: nil))
        }
        let stage: SkinOperationStage = request.includePage ? .inspectPage : .inspectApplication
        if let refusal = capabilityRefusal(for: stage, inputs: inputs) {
            return .unavailable(refusal)
        }
        let running = runtime.runningApplications(bundleIdentifier: inputs.identity.key.bundleIdentifier)
            .filter { !$0.isTerminated }
        let matching = running.filter {
            $0.bundleURL.map { $0.resolvingSymlinksInPath().standardizedFileURL } == inputs.identity.key.bundleURL
        }
        let process: HostProcessGeneration?
        if let app = matching.first, let facts = try? assembly.startupFacts(app) {
            process = HostProcessGeneration(pid: facts.pid, launchTime: facts.launchTime,
                                            executableURL: facts.executable)
        } else {
            process = nil
        }
        // Page state stays explicitly unobserved: this build performs no implicit
        // cold start and never installs a controller to probe a page.
        return .observed(process: process,
                         page: .notObserved(reason: "page observation requires an attachment attempt"))
    }

    // MARK: - disable (lock domain shared with launch; no rollback of foreign owners)

    func disable(_ request: SkinDisableRequest) async -> SkinDisableResult {
        guard request.expectedApplication == inputs.identity.key else {
            return .unavailable(HostRefusal(host: inputs.identity.key.host, reason: .identityMismatch,
                                            findings: inputs.findings,
                                            detail: "request targets another application identity",
                                            nextProbe: nil))
        }
        guard !pageOperationInFlight else {
            return .refused(SkinOperationFailure(reason: .operationBusy,
                                                 detail: "a page-changing operation is already in flight on this driver"),
                            page: .notObserved(reason: "operation-busy"))
        }
        if let refusal = capabilityRefusal(for: .disableSkin, inputs: inputs) {
            return .unavailable(refusal)
        }
        // Legacy v1 disable requires the strict owner/version binding (spec §7.2);
        // instance receipts are not fabricated for legacy observations.
        guard case .legacyV1(let legacy) = request.expectedPage,
              legacy.owner == "azhou-codex-startup", legacy.protocolVersion == 1 else {
            return .refused(SkinOperationFailure(reason: .ownerConflict,
                                                 detail: "only the legacy azhou-codex-startup v1 controller may be disabled"),
                            page: request.expectedPage.effect)
        }
        let pid = legacy.location.process.pid
        guard let app = runtime.application(processIdentifier: pid), !app.isTerminated,
              app.bundleIdentifier == inputs.identity.key.bundleIdentifier else {
            return .alreadyAbsent(legacy.location)
        }
        guard let facts = try? assembly.startupFacts(app) else {
            return .refused(SkinOperationFailure(reason: .targetIdentity,
                                                 detail: "target process lacks a complete identity"),
                            page: request.expectedPage.effect)
        }
        guard let performDisable = assembly.performDisable else {
            return .refused(SkinOperationFailure(
                reason: .protocolError,
                detail: "codex driver disable needs an explicit page disposal assembly; WallpaperCLI keeps the production disable path in C0"),
                page: request.expectedPage.effect)
        }
        pageOperationInFlight = true
        defer { pageOperationInFlight = false }
        // The single per-process lock owner for disable is this bounded section,
        // mirroring WallpaperCLI.perform; StartupConnector.attach owns it for launch.
        guard let lock = try? makeTargetSystem().acquireOperationLock(pid: facts.pid) else {
            return .refused(SkinOperationFailure(reason: .operationBusy,
                                                 detail: "another startup, wallpaper or helper operation owns this process"),
                            page: request.expectedPage.effect)
        }
        defer { lock.release() }
        do {
            let response = try await performDisable(facts, legacy.location.documentToken, request.deadline)
            if response["disposed"] as? Bool == true {
                return .removed(CleanupReport(state: .complete, released: ["legacy-page-controller"],
                                              intentionallyRetained: [], unconfirmed: []))
            }
            return .partial(SkinOperationFailure(reason: .protocolError,
                                                 detail: (response["reason"] as? String) ?? "dispose-unconfirmed"),
                            page: request.expectedPage.effect,
                            cleanup: CleanupReport(state: .unknown, released: [],
                                                   intentionallyRetained: [], unconfirmed: ["page-controller"]))
        } catch {
            return .partial(SkinOperationFailure(reason: .protocolError, detail: "dispose-evaluation-failed"),
                            page: request.expectedPage.effect,
                            cleanup: CleanupReport(state: .unknown, released: [],
                                                   intentionallyRetained: [], unconfirmed: ["page-controller"]))
        }
    }

    // MARK: - bridging back to the legacy outcome contract

    private func busyResult(detail: String) -> SkinLaunchResult {
        .partial(SkinOperationFailure(reason: .operationBusy, detail: detail),
                 page: .notObserved(reason: "operation-busy"),
                 cleanup: CleanupReport(state: .notNeeded, released: [],
                                        intentionallyRetained: [], unconfirmed: []))
    }

    private static func legacyLocation(_ request: SkinLaunchRequest, _ key: HostApplicationKey,
                                       pid: Int32, launchTime: TimeInterval?) -> PageLocation {
        PageLocation(application: key,
                     process: HostProcessGeneration(pid: pid, launchTime: launchTime,
                                                    executableURL: key.executableURL),
                     documentToken: SkinHostContract.legacyUnreportedDocumentToken)
    }

    /// Maps the existing StartupOutcome onto the shared result contract. Legacy v1
    /// observations keep explicit unreported markers instead of fabricated instance
    /// IDs or payload digests (spec §7.2), and detail fields preserve the exact
    /// legacy reason strings so old consumers never see new reasons.
    static func bridge(_ outcome: StartupOutcome, request: SkinLaunchRequest, key: HostApplicationKey,
                       observation: CodexInstallObservation) -> SkinLaunchResult {
        switch outcome {
        case .activated(let pid):
            return .activated(HostProcessGeneration(pid: pid, launchTime: nil,
                                                    executableURL: key.executableURL))
        case .ready(let runID):
            let receipt = ControllerReceipt(
                location: legacyLocation(request, key, pid: 0, launchTime: nil),
                owner: "azhou-codex-startup", protocolVersion: 1,
                payloadSHA256: SkinHostContract.legacyUnreportedPayloadSHA256,
                controllerInstanceID: SkinHostContract.legacyUnreportedInstanceID,
                createdByOperationID: request.operationID)
            return .ready(receipt, runID: runID)
        case .skipped(let runID, let beforeReady):
            return .skipped(.notObserved(reason: "legacy-v1-status-polling"),
                            runID: runID, beforeReady: beforeReady)
        case .partial(let reason):
            if reason == "startup-active" {
                // alreadyActive keeps the existing controller: partial(startup-active),
                // no rollback authority over the pre-existing instance (spec §7.2).
                let observation = LegacyV1Observation(
                    location: legacyLocation(request, key, pid: 0, launchTime: nil),
                    owner: "azhou-codex-startup", protocolVersion: 1)
                return .partial(SkinOperationFailure(reason: .ownerConflict, detail: reason),
                                page: .present(.legacyV1(observation), acquisition: .alreadyActive),
                                cleanup: CleanupReport(state: .notNeeded, released: [],
                                                       intentionallyRetained: ["existing-startup-controller"],
                                                       unconfirmed: []))
            }
            return .partial(SkinOperationFailure(reason: .operationCancelled, detail: reason),
                            page: .notObserved(reason: reason),
                            cleanup: CleanupReport(state: .notNeeded, released: [],
                                                   intentionallyRetained: [], unconfirmed: []))
        case .failed(let reason):
            if observation.installSentCount > 0 {
                // Install expression sent but the reply was lost: the page may have
                // committed; report installation-unknown and never claim fully-clean.
                return .failed(SkinOperationFailure(reason: reason == "attach-timeout" ? .operationTimeout : .protocolError,
                                                    detail: reason),
                               page: .unknown(operationID: request.operationID,
                                              detail: "install expression was sent; the page reply was never confirmed"),
                               cleanup: CleanupReport(state: .unknown, released: [],
                                                      intentionallyRetained: [], unconfirmed: ["page-controller"]))
            }
            return .failed(SkinOperationFailure(reason: reason == "attach-timeout" ? .operationTimeout : .protocolError,
                                                detail: reason),
                           page: .notObserved(reason: reason),
                           cleanup: CleanupReport(state: .notNeeded, released: [],
                                                  intentionallyRetained: [], unconfirmed: []))
        }
    }
}

extension PageObservation {
    /// The page effect view of this observation for refusal/partial results.
    var effect: PageEffect {
        switch self {
        case .instance(let receipt): return .present(.instance(receipt), acquisition: .created)
        case .legacyV1(let legacy): return .present(.legacyV1(legacy), acquisition: .alreadyActive)
        }
    }
}
