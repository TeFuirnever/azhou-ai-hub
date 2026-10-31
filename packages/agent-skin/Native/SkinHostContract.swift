// Shared skin host contract (agent-skin-zcode-contract/v0.1).
// Neutral value types and the host factory gate table shared by every host
// adapter. This file stays free of every Codex adapter type (target systems,
// CDP transports, debugger sockets); those live only inside CodexSkinDriver.
//
// DESIGN source: .planning/agent-skin-zcode/spec.md §6.2, §7.2 and §7.3.
import Foundation

enum SkinHostID: String, Sendable { case codex, zcode }

enum SkinSurface: String, Sendable { case application, mainWindow }

struct HostApplicationKey: Hashable, Sendable {
    let host: SkinHostID
    let bundleURL: URL       // already symlink-resolved real path; keeps existing path matching.
    let executableURL: URL
    let bundleIdentifier: String
    let version: String
    let build: String
    let executableSHA256: String
}

struct HostIdentityEvidence: Sendable {
    let key: HostApplicationKey
    let signingIdentity: String
    let evidenceID: String
}

enum SkinCapability: String, Hashable, Sendable, CaseIterable {
    case applicationIdentity
    case activateExistingApplication
    case mainWindowAttachment
    case mainPageIdentification
    case ownedAppearanceSurface
    case persistentSettings
    case lifecycleInvalidation
    case ownedResourceRemoval
}

enum EvidenceState: String, Sendable {
    case verified, unverified, unsupported
}

struct CapabilityEvidenceSubject: Equatable, Sendable {
    let application: HostApplicationKey
    let surface: SkinSurface
    let contractVersion: String
}

struct CapabilityFinding: Sendable {
    let subject: CapabilityEvidenceSubject
    let capability: SkinCapability
    let state: EvidenceState
    let evidenceIDs: [String]
    let reason: String
}

enum SkinOperationStage: Sendable {
    case activateExisting
    case coldLaunchSkin
    case inspectApplication
    case inspectPage
    case disableSkin
}

enum HostRefusalReason: String, Sendable {
    case identityUnavailable
    case identityMismatch
    case evidenceMismatch
    case implementationUnavailable
    case capabilityUnverified
    case capabilityUnsupported
}

struct HostRefusal: Sendable {
    let host: SkinHostID
    let reason: HostRefusalReason
    let findings: [CapabilityFinding]
    let detail: String
    let nextProbe: String?
}

struct BoundHostInputs: Sendable {
    let identity: HostIdentityEvidence
    let findings: [CapabilityFinding]
    let contractVersion: String
}

enum IdentityProbeResult: Sendable {
    case observed(HostIdentityEvidence)
    case unavailable(HostRefusal)
}

@MainActor
protocol SkinHostDriver: AnyObject {
    func launch(_ request: SkinLaunchRequest) async -> SkinLaunchResult
    func inspect(_ request: SkinInspectRequest) async -> SkinInspectResult
    func disable(_ request: SkinDisableRequest) async -> SkinDisableResult
}

@MainActor
struct SkinAssemblyDependencies {
    // Both are read-only; never boot an app or mutate configuration to fill evidence gaps.
    let inspectIdentity: (SkinHostID, TimeInterval) async -> IdentityProbeResult
    let capabilityEvidence: (HostIdentityEvidence) -> [CapabilityFinding]

    // Constructors only capture dependencies; actual resources are taken per operation.
    let makeCodexDriver: (BoundHostInputs) -> any SkinHostDriver
    let makeZCodeDriver: ((BoundHostInputs) -> any SkinHostDriver)?
}

@MainActor
enum HostAssembly {
    case ready(any SkinHostDriver)
    case unavailable(HostRefusal)
}

enum SkinHostContract {
    /// Contract identity recorded by the shared checkpoint (agent-skin-zcode C0).
    static let version = "agent-skin-zcode-contract/v0.1"

    /// Legacy v1 controller protocol has no instance identity; receipts that must
    /// exist structurally carry this explicit marker instead of a fabricated value.
    static let legacyUnreportedInstanceID = "legacy-v1-unreported"
    static let legacyUnreportedDocumentToken = "legacy-v1-unresolved-document"
    static let legacyUnreportedPayloadSHA256 = "legacy-v1-unreported-payload"

    /// Fixed capability → surface mapping: identity and activation belong to the
    /// application surface; every skin behaviour capability belongs to the main window.
    static func surface(for capability: SkinCapability) -> SkinSurface {
        switch capability {
        case .applicationIdentity, .activateExistingApplication:
            return .application
        case .mainWindowAttachment, .mainPageIdentification, .ownedAppearanceSurface,
             .persistentSettings, .lifecycleInvalidation, .ownedResourceRemoval:
            return .mainWindow
        }
    }

    /// Per-operation capability gate table (spec §6.1). Each stage checks only the
    /// capabilities it actually uses, right before its first related side effect.
    static func requiredCapabilities(for stage: SkinOperationStage) -> [SkinCapability] {
        switch stage {
        case .activateExisting:
            return [.applicationIdentity, .activateExistingApplication]
        case .coldLaunchSkin:
            return [.applicationIdentity, .mainWindowAttachment, .mainPageIdentification,
                    .ownedAppearanceSurface, .persistentSettings, .lifecycleInvalidation]
        case .inspectApplication:
            return [.applicationIdentity]
        case .inspectPage:
            return [.applicationIdentity, .mainPageIdentification]
        case .disableSkin:
            return [.applicationIdentity, .mainPageIdentification, .ownedResourceRemoval]
        }
    }

}

@MainActor
enum SkinHostFactory {
    /// Spec §6.2 make() algorithm. Static host selection, identity/evidence binding
    /// and constructor injection only: no connections, locks, app launches, page
    /// injection, database opens or full-skin requirements for read-only checks.
    static func make(
        host: SkinHostID,
        expectedApplication: HostApplicationKey,
        observed: HostIdentityEvidence,
        findings: [CapabilityFinding],
        contractVersion: String,
        dependencies: SkinAssemblyDependencies
    ) -> HostAssembly {
        func refusal(_ reason: HostRefusalReason, _ detail: String,
                     evidence: [CapabilityFinding] = []) -> HostAssembly {
            .unavailable(HostRefusal(host: host, reason: reason, findings: evidence,
                                     detail: detail, nextProbe: nil))
        }
        // 1. host == expected.host == observed.host and expected == observed.key.
        guard host == expectedApplication.host, host == observed.key.host,
              expectedApplication == observed.key else {
            return refusal(.identityMismatch,
                           "expected application, observed identity and requested host disagree")
        }
        // 2. Every finding binds this application, this contract and the fixed surface.
        //    Plugin-page (application surface) evidence cannot pose as main-window evidence.
        for finding in findings {
            guard finding.subject.application == observed.key else {
                return refusal(.evidenceMismatch,
                               "finding for \(finding.capability.rawValue) is bound to another application",
                               evidence: findings)
            }
            guard finding.subject.contractVersion == contractVersion else {
                return refusal(.evidenceMismatch,
                               "finding for \(finding.capability.rawValue) uses another contract version",
                               evidence: findings)
            }
            guard finding.subject.surface == SkinHostContract.surface(for: finding.capability) else {
                return refusal(.evidenceMismatch,
                               "finding for \(finding.capability.rawValue) claims the wrong surface",
                               evidence: findings)
            }
        }
        // 3. Duplicate or conflicting records per capability are refused; verified
        //    records need source evidence references. Missing records stay unverified
        //    for the operation and never default to supported.
        var byCapability: [SkinCapability: CapabilityFinding] = [:]
        for finding in findings {
            if byCapability[finding.capability] != nil {
                return refusal(.evidenceMismatch,
                               "duplicate or conflicting records for \(finding.capability.rawValue)",
                               evidence: findings)
            }
            if finding.state == .verified && finding.evidenceIDs.isEmpty {
                return refusal(.evidenceMismatch,
                               "verified record for \(finding.capability.rawValue) has no source evidence",
                               evidence: findings)
            }
            byCapability[finding.capability] = finding
        }
        // 4. unverified/unsupported findings pass through; the factory never blocks
        //    operations that do not use those capabilities.
        // 5. Only .codex and .zcode constructors; a missing constructor refuses and
        //    never silently falls back to Codex.
        let boundInputs = BoundHostInputs(identity: observed, findings: findings,
                                          contractVersion: contractVersion)
        switch host {
        case .codex:
            return .ready(dependencies.makeCodexDriver(boundInputs))
        case .zcode:
            guard let makeZCodeDriver = dependencies.makeZCodeDriver else {
                return refusal(.implementationUnavailable,
                               "no verified ZCode driver constructor is available")
            }
            return .ready(makeZCodeDriver(boundInputs))
        }
        // 6. The returned driver owns immutable bound inputs; every operation
        //    re-checks the request identity and live process/document generation.
    }
}

/// Pure value check called by a concrete driver once it knows its actual branch.
func capabilityRefusal(
    for stage: SkinOperationStage,
    inputs: BoundHostInputs
) -> HostRefusal? {
    func refusal(_ reason: HostRefusalReason, _ gaps: [CapabilityFinding]) -> HostRefusal {
        HostRefusal(host: inputs.identity.key.host, reason: reason, findings: gaps,
                    detail: gaps.map { "\($0.capability.rawValue):\($0.state.rawValue)" }.joined(separator: ","),
                    nextProbe: nil)
    }
    var unverified: [CapabilityFinding] = []
    var unsupported: [CapabilityFinding] = []
    var findings: [SkinCapability: CapabilityFinding] = [:]
    for finding in inputs.findings { findings[finding.capability] = finding }
    for capability in SkinHostContract.requiredCapabilities(for: stage) {
        let finding = findings[capability]
        switch finding?.state {
        case .verified:
            continue
        case .unsupported:
            unsupported.append(finding ?? CapabilityFinding(
                subject: CapabilityEvidenceSubject(application: inputs.identity.key,
                                                   surface: SkinHostContract.surface(for: capability),
                                                   contractVersion: inputs.contractVersion),
                capability: capability, state: .unsupported, evidenceIDs: [], reason: "missing"))
        case .unverified, nil:
            unverified.append(finding ?? CapabilityFinding(
                subject: CapabilityEvidenceSubject(application: inputs.identity.key,
                                                   surface: SkinHostContract.surface(for: capability),
                                                   contractVersion: inputs.contractVersion),
                capability: capability, state: .unverified, evidenceIDs: [], reason: "missing"))
        }
    }
    if !unsupported.isEmpty { return refusal(.capabilityUnsupported, unsupported) }
    if !unverified.isEmpty { return refusal(.capabilityUnverified, unverified) }
    return nil
}

// MARK: - Requests, results and cancellation (spec §6.2)
// Requests reuse one installation identity so a driver assembled for application A
// cannot act on application B. Cancellation uses Swift Task propagation only.

struct SkinLaunchRequest: Sendable {
    let expectedApplication: HostApplicationKey
    let operationID: UUID
    let startedAt: TimeInterval
    let deadline: TimeInterval
}

struct SkinInspectRequest: Sendable {
    let expectedApplication: HostApplicationKey
    let operationID: UUID
    let deadline: TimeInterval
    let includePage: Bool
    let previousObservation: PageObservation?
}

struct SkinDisableRequest: Sendable {
    let expectedApplication: HostApplicationKey
    let operationID: UUID
    let deadline: TimeInterval
    let expectedPage: PageObservation
}

struct HostProcessGeneration: Equatable, Sendable {
    let pid: Int32
    let launchTime: TimeInterval?
    let executableURL: URL
}

struct PageLocation: Equatable, Sendable {
    let application: HostApplicationKey
    let process: HostProcessGeneration
    let documentToken: String
}

struct ControllerReceipt: Sendable {
    let location: PageLocation
    let owner: String
    let protocolVersion: Int
    let payloadSHA256: String
    let controllerInstanceID: String
    let createdByOperationID: UUID
}

struct LegacyV1Observation: Sendable {
    let location: PageLocation
    let owner: String
    let protocolVersion: Int // must stay the currently supported Codex value 1.
}

enum PageObservation: Sendable {
    case instance(ControllerReceipt)
    case legacyV1(LegacyV1Observation)
}

enum PageAcquisition: Sendable { case created, alreadyActive }

enum PageEffect: Sendable {
    case notObserved(reason: String)
    case absent(PageLocation)
    case present(PageObservation, acquisition: PageAcquisition)
    case unknown(operationID: UUID, detail: String)
}

extension PageEffect {
    var isNotObserved: Bool {
        if case .notObserved = self { return true }
        return false
    }

    var isInstallationUnknown: Bool {
        if case .unknown = self { return true }
        return false
    }

    func isPresentsLegacyAlreadyActive(owner: String, protocolVersion: Int) -> Bool {
        if case .present(.legacyV1(let observation), acquisition: .alreadyActive) = self {
            return observation.owner == owner && observation.protocolVersion == protocolVersion
        }
        return false
    }
}

enum CleanupState: String, Sendable {
    case notNeeded, complete, partial, unknown
}

struct CleanupReport: Sendable {
    let state: CleanupState
    let released: [String]
    let intentionallyRetained: [String]
    let unconfirmed: [String]
}

enum SkinFailureReason: String, Sendable {
    case targetIdentity
    case targetStale
    case operationCancelled
    case operationTimeout
    case operationBusy
    case ownerConflict
    case protocolError
}

struct SkinOperationFailure: Sendable {
    let reason: SkinFailureReason
    let detail: String
}

enum SkinLaunchResult: Sendable {
    case activated(HostProcessGeneration)
    case ready(ControllerReceipt, runID: Int)
    case skipped(PageEffect, runID: Int, beforeReady: Bool)
    case refused(HostRefusal)
    case partial(SkinOperationFailure, page: PageEffect, cleanup: CleanupReport)
    case failed(SkinOperationFailure, page: PageEffect, cleanup: CleanupReport)
}

enum SkinInspectResult: Sendable {
    case observed(process: HostProcessGeneration?, page: PageEffect)
    case unavailable(HostRefusal)
    case staleTarget(SkinOperationFailure)
}

enum SkinDisableResult: Sendable {
    case removed(CleanupReport)
    case alreadyAbsent(PageLocation)
    case unavailable(HostRefusal)
    case refused(SkinOperationFailure, page: PageEffect)
    case partial(SkinOperationFailure, page: PageEffect, cleanup: CleanupReport)
}
