// Agent Skin 原生入口。
//
// 本文件的职责划分按“谁拥有状态、谁提供操作”重画，而不是沿旧流程搬运：
//
//   LauncherCommandLine   命令行契约（一次解析，值类型；消灭散落的 args.contains）
//   LauncherIdentity      入口身份（初始化时定格 host/双端 bundle id，不再逐次重开 Bundle）
//   LauncherJournal       遥测编排（事件信封 + 可选 JSONL sink + smoke 事件门）
//   PlayerMessage         页面消息语法层（纯解码：action 提取、locale 校验、时长归一化）
//   PlayerStage           播放器会话（窗口呈现、显示语言、进度、看门狗、快照句柄）
//   SnapshotPlan          快照时间点纯计算（解析与过滤无副作用）
//   TrustedLaunchSession  受信启动会话（实例锁、目标解析、事件流、载荷与端口）
//   ExitLedger            终局账本（terminating/failed/promoted/退出码/smoke 结果）
//   BoundedTargetOpen     有界打开过程（预算内的 NSWorkspace open + 身份核验）
//   AppDelegate          编排门面：仅协议入口与跨部件流程，不再持有零散布尔状态
//
// 对外合同（事件序列、字段、reason 词表、时序语义）逐项保持不变；变化的是
// 状态所有权与数据流方向。消息的“语法验证”与“状态机推进”由此分离：解码层
// 无副作用，执行层只消费已验证的语义值。

import CryptoKit
import AppKit
import WebKit
import Darwin
import CoreFoundation

// MARK: - 入口命令行与身份

/// 启动器命令行契约。解析一次后以值语义共享，调用方不再各自翻查原始参数。
struct LauncherCommandLine {
    /// 只影响本地播放器窗口的独占模式（预览 / 冒烟）。
    let playerExclusive: Bool
    let isSmokeTest: Bool
    let isProbe: Bool
    let wantsInspector: Bool
    private let raw: [String]

    init(arguments: [String]) {
        self.raw = arguments
        self.isSmokeTest = arguments.contains("--smoke-test")
        self.playerExclusive = isSmokeTest || arguments.contains("--preview")
        self.isProbe = arguments.contains("--probe")
        self.wantsInspector = arguments.contains("--inspect")
    }

    /// 取紧跟在开关后的参数值（旧 option(_:) 语义）。
    func value(after flag: String) -> String? {
        guard let index = raw.firstIndex(of: flag), index + 1 < raw.count else { return nil }
        return raw[index + 1]
    }

    var snapshotDirectory: String? { value(after: "--snapshot") }
    var snapshotTimes: String { value(after: "--snapshot-times") ?? "0.4,1.4,2.3,3.5,5.5,7.3" }
    var zcodeStateRoot: String? { value(after: "--zcode-state-root") }
    var arguments: [String] { raw }
}

/// 符号链接解析 + 标准化的统一入口，保证全文件对“同一物理路径”判定一致。
enum PathCanonicalization {
    static func resolved(_ url: URL) -> URL {
        url.resolvingSymlinksInPath().standardizedFileURL
    }
}

/// 启动器自身的身份快照：由自身 bundle 推出宿主阵营、锁标识与目标应用标识。
/// 旧实现把这一步做成计算属性（每次访问重开 Bundle）；这里在构造时定格。
struct LauncherIdentity {
    let host: SkinHostID?
    /// 实例锁与 duplicate-entry 检测使用的启动器 bundle id；身份不明时仍需
    /// 一个稳定的非法标识，让锁路径可预测但永不匹配合法宿主。
    let launcherBundleID: String
    /// 受信启动的目标应用 bundle id（ZCode 或 Codex）。
    let targetBundleID: String

    init(bundleURL: URL) {
        let bundle = Bundle(url: bundleURL)
        let resolved = NativeEntryIdentity.host(
            bundleIdentifier: bundle?.bundleIdentifier,
            declaredHost: bundle?.object(forInfoDictionaryKey: "AzhouTargetHost"))
        self.host = resolved
        switch resolved {
        case .zcode:
            launcherBundleID = "local.azhou.zcode-startup"
            targetBundleID = "dev.zcode.app"
        case .codex:
            launcherBundleID = "local.azhou.codex-startup"
            targetBundleID = "com.openai.codex"
        case nil:
            launcherBundleID = "local.azhou.invalid-entry"
            targetBundleID = "com.openai.codex"
        }
    }
}

// MARK: - 遥测

/// v1 事件信封写入器：为每条记录补齐 schema/event/seconds/launcherPID/launcherPath，
/// 并以互斥锁保证 seconds 单调不减（时钟回退或非有限读数沿用上一秒值）。
final class NativeEventWriter: @unchecked Sendable {
    static let schema = "azhou-startup.event.v1"

    private let startedAt: TimeInterval
    private let launcherPID: Int
    private let launcherPath: String
    private let now: () -> TimeInterval
    private let sink: ([String: Any]) -> Void
    private let lock = NSLock()
    private var lastSeconds: Double = 0

    init(startedAt: TimeInterval, launcherPID: Int, launcherPath: String,
         now: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime },
         sink: @escaping ([String: Any]) -> Void) {
        self.startedAt = startedAt
        self.launcherPID = launcherPID
        self.launcherPath = launcherPath
        self.now = now
        self.sink = sink
    }

    func emit(_ event: String, fields: [String: Any] = [:], at uptime: TimeInterval? = nil) {
        lock.lock()
        defer { lock.unlock() }

        let elapsed = (uptime ?? now()) - startedAt
        let seconds = elapsed.isFinite ? max(lastSeconds, max(0, elapsed)) : lastSeconds
        lastSeconds = seconds
        var record = fields
        record["schema"] = Self.schema
        record["event"] = event
        record["seconds"] = seconds
        record["launcherPID"] = launcherPID
        record["launcherPath"] = launcherPath
        sink(record)
    }

    /// 只读探测事件：携带核验过的目标路径、bundle id、运行中实例与前台应用。
    func emitProbe(targetPath: String, targetBundleID: String, running: [[String: Any]],
                   frontmost: [String: Any], at uptime: TimeInterval? = nil) {
        emit("probe", fields: ["targetPath": targetPath, "targetBundleID": targetBundleID,
                               "running": running, "frontmost": frontmost], at: uptime)
    }
}

/// 启动器遥测编排：自由事件（旧 log 路径）、smoke 门控事件、ZCode 运行时诊断
/// 与可选 JSONL sink 的唯一属主。事件信封字段在这里集中补齐。
@MainActor
final class LauncherJournal {
    private let runtime: any NativeAppRuntime
    private let epoch: TimeInterval
    private let smokeOnly: Bool
    private let sinkLock = NSLock()
    private var fileSink: FileHandle?

    /// 协议生命周期事件共用的信封写入器；惰性构造，sink 回落到本类的线程安全写径。
    lazy var eventWriter = NativeEventWriter(
        startedAt: epoch,
        launcherPID: runtime.processIdentifier,
        launcherPath: PathCanonicalization.resolved(runtime.bundleURL).path,
        sink: { [weak self] in self?.writeRecord($0) })

    init(runtime: any NativeAppRuntime, epoch: TimeInterval, smokeOnly: Bool) {
        self.runtime = runtime
        self.epoch = epoch
        self.smokeOnly = smokeOnly
    }

    /// 按策略打开可选事件 sink（--log 或每日目录）；失败只提示，不阻塞启动。
    func openSink(arguments: [String], host: SkinHostID?) {
        guard let path = StartupLogPolicy.filePath(arguments: arguments,
                                                   dailyEventDirectory: StartupEventJournal.directory(host: host)) else { return }
        fileSink = StartupEventJournal.appendHandle(path: path)
        if fileSink == nil { print("LOG ERROR: startup event sink unavailable at \(path)") }
    }

    /// 自由（非协议）事件：播放器/Codex 诊断沿用既有日志路径与字段。
    func record(_ event: String, _ fields: [String: Any] = [:]) {
        var data = fields
        data["event"] = event
        data["seconds"] = ((runtime.uptime - epoch) * 1000).rounded() / 1000
        data["launcherPID"] = runtime.processIdentifier
        data["launcherPath"] = PathCanonicalization.resolved(runtime.bundleURL).path
        writeRecord(data)
    }

    /// smoke 模式专属事件；非 smoke 调用是空操作，调用方无需自行判断模式。
    func recordSmoke(_ event: String, _ fields: [String: Any] = [:]) {
        guard smokeOnly else { return }
        eventWriter.emit(event, fields: fields)
    }

    /// ZCode 运行时诊断走与入口生命周期一致的严格信封，不额外补字段。
    func emitRuntimeDiagnostic(_ fields: [String: Any]) {
        eventWriter.emit("zcode-runtime", fields: fields, at: runtime.uptime)
    }

    func emitProbe(targetPath: String, targetBundleID: String,
                   running: [[String: Any]], frontmost: [String: Any]) {
        eventWriter.emitProbe(targetPath: targetPath, targetBundleID: targetBundleID,
                              running: running, frontmost: frontmost)
    }

    /// 应用观测的固定字段化表示（pid/bundleID/path/active/hidden/terminated）。
    func applicationRecord(_ application: (any NativeApplication)?) -> [String: Any] {
        guard let application else { return [:] }
        return ["pid": Int(application.processIdentifier),
                "bundleID": application.bundleIdentifier ?? "",
                "path": application.bundleURL.map { PathCanonicalization.resolved($0).path } ?? "",
                "active": application.isActive,
                "hidden": application.isHidden,
                "terminated": application.isTerminated]
    }

    func closeSink() {
        try? fileSink?.close()
    }

    private func writeRecord(_ data: [String: Any]) {
        sinkLock.lock()
        defer { sinkLock.unlock() }
        guard let json = try? JSONSerialization.data(withJSONObject: data, options: [.sortedKeys, .withoutEscapingSlashes]),
              let line = String(data: json, encoding: .utf8) else { return }
        runtime.writeStandardOutput(line)
        try? fileSink?.write(contentsOf: json + Data([10]))
    }
}

// MARK: - 启动协议状态机

/// 一次受信启动在安装瞬间的观测快照。
struct NativeStartupObservation {
    let targetPID: Int32
    let installedAt: TimeInterval?
    let status: NativeStartupStatus?
    let statusAt: TimeInterval?
    var pageID: String? = nil
}

/// 安装观测状态机：只有“本启动器亲手安装且此前不活跃”的控制器才建立归属；
/// 归属一旦绑定到某个 runID，外来 run 不能替换它，只能由同一 run 推进。
final class NativeStartupCapture: @unchecked Sendable {
    private enum Phase {
        case awaitingInstallation
        case installed(at: TimeInterval)
        case bound(installedAt: TimeInterval, runID: Int, status: NativeStartupStatus, statusAt: TimeInterval)
    }

    private let lock = NSLock()
    let targetPID: Int32
    private var phase: Phase = .awaitingInstallation
    private var pageID: String?

    init(targetPID: Int32) { self.targetPID = targetPID }

    /// 页面重绑定：换页后旧安装证据全部作废，观测回到待安装态。
    func bindPage(_ id: String?) {
        lock.lock()
        defer { lock.unlock() }
        pageID = id
        phase = .awaitingInstallation
    }

    /// 喂入一条 evaluate 响应；仅当首次绑定 run 时返回 (runID, installedAt)。
    /// 状态吸收在互斥区内完成（absorb）；页面身份不符的响应直接忽略。
    func observe(_ response: [String: Any], at uptime: TimeInterval, pageID: String? = nil) -> (runID: Int, installedAt: TimeInterval)? {
        lock.lock()
        defer { lock.unlock() }
        guard self.pageID == pageID else { return nil }
        return absorb(response, at: uptime)
    }

    func snapshot() -> NativeStartupObservation {
        lock.lock()
        defer { lock.unlock() }
        switch phase {
        case .awaitingInstallation:
            return NativeStartupObservation(targetPID: targetPID, installedAt: nil, status: nil, statusAt: nil, pageID: pageID)
        case .installed(let installedAt):
            return NativeStartupObservation(targetPID: targetPID, installedAt: installedAt, status: nil, statusAt: nil, pageID: pageID)
        case .bound(let installedAt, _, let status, let statusAt):
            return NativeStartupObservation(targetPID: targetPID, installedAt: installedAt, status: status, statusAt: statusAt, pageID: pageID)
        }
    }

    /// 状态吸收（锁内调用）：安装回执只在“本启动器安装且此前不活跃”时建立
    /// 归属；随后第一条有效状态绑定 run，外来 run 被拒、同 run 可推进。
    private func absorb(_ response: [String: Any], at uptime: TimeInterval) -> (runID: Int, installedAt: TimeInterval)? {
        if case .awaitingInstallation = phase,
           NativeStartupStatus.boolean(response["installed"]) == true,
           NativeStartupStatus.boolean(response["alreadyActive"]) == false {
            phase = .installed(at: uptime)
        }
        guard let raw = response["status"], let observed = NativeStartupStatus.parse(raw) else { return nil }
        switch phase {
        case .awaitingInstallation:
            return nil
        case .installed(let installedAt):
            phase = .bound(installedAt: installedAt, runID: observed.runID, status: observed, statusAt: uptime)
            return (observed.runID, installedAt)
        case .bound(let installedAt, let boundRunID, _, _):
            guard boundRunID == observed.runID else { return nil }
            phase = .bound(installedAt: installedAt, runID: boundRunID, status: observed, statusAt: uptime)
            return nil
        }
    }
}

/// 启动终局：三档成功（activated/ready/skipped）、一档中断（partial, 退出码 2）、
/// 一档行为未证实（behaviorNotProven, 退出码 1）。
enum NativeStartupFinalOutcome: Equatable {
    case activated
    case ready
    case skipped
    case partial(reason: String)
    case behaviorNotProven(reason: String)

    var exitCode: Int32 {
        switch self {
        case .activated, .ready, .skipped: return 0
        case .partial: return 2
        case .behaviorNotProven: return 1
        }
    }

    var event: String {
        switch self {
        case .activated: return "target-activated"
        case .ready: return "startup-ready"
        case .skipped: return "startup-skipped"
        case .partial: return "startup-interrupted"
        case .behaviorNotProven: return "startup-failed"
        }
    }

    var exitName: String {
        switch self {
        case .activated: return "activated"
        case .ready: return "startup-ready"
        case .skipped: return "skipped"
        case .partial: return "partial"
        case .behaviorNotProven: return "behavior-not-proven"
        }
    }

    var reason: String? {
        switch self {
        case .partial(let reason), .behaviorNotProven(let reason): return reason
        default: return nil
        }
    }
}

/// 启动事件流：把 launcher-start → … → launcher-exit 折叠成单调记录序列。
/// 四态生命周期（未开始/进行中/已定局/已离场）之上的裁决顺序：
/// 端口错误 > 挂起失败 > 挂起中断 > 依里程碑推导的结论；成功结论没有配套
/// 里程碑时按 protocol-error 拒绝（宁可失败，不虚构证据）。
final class NativeStartupEventStream: @unchecked Sendable {
    private enum Stage {
        case dormant
        case running
        case decided(NativeStartupFinalOutcome)
        case exited(NativeStartupFinalOutcome)
    }

    private let lock = NSLock()
    private let writer: NativeEventWriter
    private var stage: Stage = .dormant
    private var pendingFailure: String?
    private var pendingInterruption: String?
    private var openedPID: Int32?
    private var installedPID: Int32?
    private var installedRunID: Int?
    private var pageID: String?

    init(writer: NativeEventWriter) { self.writer = writer }

    /// 统一互斥入口：状态转换与事件发射同处一锁，记录顺序永远与状态一致。
    private func underLock<T>(_ transition: () -> T) -> T {
        lock.lock()
        defer { lock.unlock() }
        return transition()
    }

    func begin(at uptime: TimeInterval) {
        underLock {
            guard case .dormant = stage else { return }
            stage = .running
            writer.emit("launcher-start", at: uptime)
        }
    }

    /// 首个正向 PID 生效；后续同 PID 幂等，异 PID 或非正 PID 一律忽略。
    func targetOpened(pid: Int32, at uptime: TimeInterval) {
        underLock {
            guard case .running = stage, pid > 0, openedPID == nil else { return }
            openedPID = pid
            writer.emit("target-opened", fields: ["targetPID": Int(pid)], at: uptime)
        }
    }

    /// 页面重绑定：仅在启动进行中且无挂起结论时允许；清空安装里程碑。
    func bindPage(pid: Int32, pageID: String?) -> Bool {
        underLock {
            guard case .running = stage, openedPID == pid,
                  pendingFailure == nil, pendingInterruption == nil else { return false }
            self.pageID = pageID
            installedPID = nil; installedRunID = nil
            return true
        }
    }

    /// 安装里程碑只在“已打开同 PID 且尚未记录安装”时成立；页面身份不符忽略。
    func startupInstalled(pid: Int32, runID: Int, at uptime: TimeInterval, pageID: String? = nil) {
        underLock {
            guard case .running = stage, pid > 0, runID > 0,
                  openedPID == pid, installedPID == nil, self.pageID == pageID else { return }
            installedPID = pid
            installedRunID = runID
            var fields: [String: Any] = ["targetPID": Int(pid), "runId": runID]
            if let pageID { fields["pageTargetID"] = pageID }
            writer.emit("startup-installed", fields: fields, at: uptime)
        }
    }

    /// 端口错误具有最高裁决权：直接覆盖任何挂起结论并即时落事件。
    func portError(operation: String, errno: Int32, at uptime: TimeInterval) {
        underLock {
            guard case .running = stage else { return }
            pendingFailure = "listener-mismatch"
            writer.emit("startup-port-error", fields: ["reason": "listener-mismatch",
                                                       "operation": operation, "errno": Int(errno)], at: uptime)
        }
    }

    func latchFailure(_ reason: String) {
        underLock {
            guard case .running = stage, pendingFailure == nil else { return }
            pendingFailure = Self.fixedReason(reason)
        }
    }

    /// 用户侧中断统一收敛为固定 reason，调用方文本不进入协议。
    func latchInterruption(_ reason: String = "startup-interrupted") {
        underLock {
            guard case .running = stage, pendingFailure == nil, pendingInterruption == nil else { return }
            pendingInterruption = "startup-interrupted"
        }
    }

    var isPending: Bool {
        underLock {
            if case .running = stage { return true }
            return false
        }
    }

    /// 依 Codex 里程碑推导终局。定局只发生一次，之后的 resolve 一律返回 nil。
    @discardableResult
    func resolve(_ outcome: StartupOutcome, observation: NativeStartupObservation?, at uptime: TimeInterval) -> NativeStartupFinalOutcome? {
        underLock { () -> NativeStartupFinalOutcome? in
            guard case .running = stage else { return nil }
            let decided = verdict(outcome: outcome, observation: observation)
            stage = .decided(decided)
            emitFinal(decided, outcome: outcome, observation: observation, at: uptime)
            return decided
        }
    }

    /// ZCode 驱动交回的是类型化控制器回执，不是 Codex 状态捕获：证据只保留
    /// 回执里真实存在的字段，不虚构 Codex 阶段、complete 事件或更早的时间戳。
    @discardableResult
    func resolveZCode(_ result: SkinLaunchResult, expectedApplication: HostApplicationKey,
                      at uptime: TimeInterval) -> NativeStartupFinalOutcome? {
        underLock { () -> NativeStartupFinalOutcome? in
            guard case .running = stage else { return nil }
            var fields: [String: Any] = ["host": "zcode", "evidence": "typed-controller-receipt",
                                         "completion_not_inferred": true]
            let decided = typedVerdict(result, expectedApplication: expectedApplication, fields: &fields)
            stage = .decided(decided)
            if let reason = decided.reason { fields["reason"] = reason }
            writer.emit(decided.event, fields: fields, at: uptime)
            return decided
        }
    }

    /// 离场：已定局则补 launcher-exit；仍在进行中则先按挂起结论定局（无挂起时
    /// 失败关闭为 partial）。重复调用幂等并返回同一终局。
    @discardableResult
    func finish(at uptime: TimeInterval) -> NativeStartupFinalOutcome? {
        underLock { () -> NativeStartupFinalOutcome? in
            switch stage {
            case .dormant:
                return nil
            case .exited(let settled):
                return settled
            case .decided(let settled):
                writer.emit("launcher-exit", fields: ["outcome": settled.exitName, "exitCode": Int(settled.exitCode)], at: uptime)
                stage = .exited(settled)
                return settled
            case .running:
                let fallback: NativeStartupFinalOutcome
                if let pendingFailure { fallback = .behaviorNotProven(reason: pendingFailure) }
                else if let pendingInterruption { fallback = .partial(reason: pendingInterruption) }
                else { fallback = .partial(reason: "startup-interrupted") }
                stage = .decided(fallback)
                emitFinal(fallback, outcome: nil, observation: nil, at: uptime)
                writer.emit("launcher-exit", fields: ["outcome": fallback.exitName, "exitCode": Int(fallback.exitCode)], at: uptime)
                stage = .exited(fallback)
                return fallback
            }
        }
    }

    /// 裁决（锁内调用）：挂起失败 > 挂起中断 > 证据推导。
    private func verdict(outcome: StartupOutcome, observation: NativeStartupObservation?) -> NativeStartupFinalOutcome {
        if let pendingFailure { return .behaviorNotProven(reason: pendingFailure) }
        if let pendingInterruption { return .partial(reason: pendingInterruption) }
        return Self.outcomeRequiringEvidence(for: outcome, observation: observation,
                                             openedPID: openedPID, installedPID: installedPID,
                                             installedRunID: installedRunID, pageID: pageID)
    }

    /// 类型化裁决（锁内调用）：宿主不符直接拒绝；成功结论必须由通过核验的
    /// 回执/进程代支撑；失败族折叠回既有词表。
    private func typedVerdict(_ result: SkinLaunchResult, expectedApplication: HostApplicationKey,
                              fields: inout [String: Any]) -> NativeStartupFinalOutcome {
        if let pendingFailure { return .behaviorNotProven(reason: pendingFailure) }
        if let pendingInterruption { return .partial(reason: pendingInterruption) }
        guard expectedApplication.host == .zcode else { return .behaviorNotProven(reason: "target-identity") }
        switch result {
        case .activated(let process):
            guard Self.matchesExpectedGeneration(process, expectedApplication) else {
                return .behaviorNotProven(reason: "target-identity")
            }
            fields["targetPID"] = Int(process.pid)
            return .activated
        case .ready(let receipt, let runID):
            guard runID > 0, let receiptFields = Self.verifiedReceiptFields(receipt, expectedApplication) else {
                return .behaviorNotProven(reason: "protocol-error")
            }
            fields.merge(receiptFields, uniquingKeysWith: { _, new in new })
            fields["runId"] = runID; fields["ready"] = true
            return .ready
        case .skipped(let page, let runID, let beforeReady):
            guard runID > 0, case .present(.instance(let receipt), let acquisition) = page,
                  let receiptFields = Self.verifiedReceiptFields(receipt, expectedApplication) else {
                return .behaviorNotProven(reason: "protocol-error")
            }
            fields.merge(receiptFields, uniquingKeysWith: { _, new in new })
            fields["runId"] = runID; fields["beforeReady"] = beforeReady
            fields["acquisition"] = acquisition == .created ? "created" : "alreadyActive"
            return .skipped
        case .partial, .failed, .refused:
            return Self.outcomeRequiringEvidence(for: startupLegacyOutcome(from: result), observation: nil,
                                                 openedPID: nil, installedPID: nil, installedRunID: nil)
        }
    }

    /// 终局事件；ready/skipped 只在拥有配套观测时才发，缺证不发也不降级。
    private func emitFinal(_ final: NativeStartupFinalOutcome, outcome: StartupOutcome?,
                           observation: NativeStartupObservation?, at uptime: TimeInterval) {
        switch final {
        case .activated:
            if case .activated(let pid)? = outcome {
                writer.emit(final.event, fields: ["targetPID": Int(pid)], at: uptime)
            }
        case .ready:
            guard let observation, let status = observation.status, let runID = installedRunID else { return }
            var fields: [String: Any] = ["targetPID": Int(observation.targetPID), "runId": runID,
                                         "ready": true, "phase": status.phase]
            if let pageID { fields["pageTargetID"] = pageID }
            writer.emit(final.event, fields: fields, at: observation.statusAt ?? uptime)
        case .skipped:
            guard let observation, let status = observation.status, let runID = installedRunID,
                  let beforeReady = status.completionBeforeReady else { return }
            var fields: [String: Any] = ["targetPID": Int(observation.targetPID), "runId": runID,
                                         "completed": true,
                                         "completion": ["cause": "skip", "beforeReady": beforeReady],
                                         "overlay": false]
            if let pageID { fields["pageTargetID"] = pageID }
            writer.emit(final.event, fields: fields, at: observation.statusAt ?? uptime)
        case .partial(let reason), .behaviorNotProven(let reason):
            writer.emit(final.event, fields: ["reason": reason], at: uptime)
        }
    }

    /// 成功结论的证据要求：ready 需要“同一 PID 上安装了同一 run 且状态就绪”，
    /// skipped 需要“同一 run 的完成态且完成原因为 skip”；任一缺口即 protocol-error。
    /// 页面身份（#438）：观测与安装必须来自当前绑定的页面。
    private static func outcomeRequiringEvidence(for outcome: StartupOutcome, observation: NativeStartupObservation?,
                                                 openedPID: Int32?, installedPID: Int32?, installedRunID: Int?,
                                                 pageID: String? = nil) -> NativeStartupFinalOutcome {
        switch outcome {
        case .activated(let pid):
            return pid > 0 ? .activated : .behaviorNotProven(reason: "target-identity")
        case .ready(let runID):
            guard let observation, let status = observation.status,
                  observation.pageID == pageID,
                  observation.targetPID > 0, openedPID == observation.targetPID,
                  installedPID == observation.targetPID, installedRunID == runID,
                  runID > 0, status.runID == runID, status.ready,
                  ["playing", "settings", "complete"].contains(status.phase) else {
                return .behaviorNotProven(reason: "protocol-error")
            }
            return .ready
        case .skipped(let runID, let beforeReady):
            guard let observation, let status = observation.status,
                  observation.pageID == pageID,
                  observation.targetPID > 0, openedPID == observation.targetPID,
                  installedPID == observation.targetPID, installedRunID == runID,
                  runID > 0, status.runID == runID, status.completed, !status.overlay,
                  status.completionCause == "skip", status.completionBeforeReady == beforeReady else {
                return .behaviorNotProven(reason: "protocol-error")
            }
            return .skipped
        case .partial(let reason) where reason == "startup-interrupted":
            return .partial(reason: reason)
        case .partial(let reason):
            return .behaviorNotProven(reason: fixedReason(reason))
        case .failed(let reason):
            return .behaviorNotProven(reason: fixedReason(reason))
        }
    }

    /// reason 白名单：协议只承认既有词表，未知词折叠为 protocol-error。
    private static func fixedReason(_ reason: String) -> String {
        let allowed: Set<String> = [
            "target-missing", "target-identity", "listener-mismatch", "page-pending", "page-unsupported",
            "owner-conflict", "protocol-error", "attach-timeout", "asset-invalid", "storage-unavailable",
            "wallpaper-unsupported", "overlay-timeout", "ambiguous-main-page", "startup-active",
            "startup-interrupted", "settings-conflict", "operation-timeout"
        ]
        return allowed.contains(reason) ? reason : "protocol-error"
    }

    private static func matchesExpectedGeneration(_ process: HostProcessGeneration,
                                                  _ expected: HostApplicationKey) -> Bool {
        process.pid > 0 && process.launchTime.map { $0.isFinite && $0 > 0 } == true &&
            process.executableURL == expected.executableURL
    }

    /// 回执核验：位置绑定期望应用与进程代、owner/protocolVersion 为已知组合、
    /// 实例 ID 是合法 UUID、载荷哈希是小写十六进制 64 位、文档令牌非空。
    /// 文档令牌本身不落日志，只落其 SHA-256。
    private static func verifiedReceiptFields(_ receipt: ControllerReceipt,
                                              _ expected: HostApplicationKey) -> [String: Any]? {
        guard receipt.location.application == expected,
              matchesExpectedGeneration(receipt.location.process, expected),
              receipt.owner == "azhou-zcode-startup", receipt.protocolVersion == 1,
              receipt.controllerInstanceID.utf8.count == 36,
              UUID(uuidString: receipt.controllerInstanceID) != nil,
              receipt.payloadSHA256.utf8.count == 64,
              receipt.payloadSHA256.allSatisfy({ "0123456789abcdef".contains($0) }),
              !receipt.location.documentToken.isEmpty else { return nil }
        return ["targetPID": Int(receipt.location.process.pid), "owner": receipt.owner,
                "version": receipt.protocolVersion, "controllerInstanceID": receipt.controllerInstanceID,
                "createdByOperationID": receipt.createdByOperationID.uuidString,
                "payloadSHA256": receipt.payloadSHA256,
                "documentTokenSHA256": SHA256.hash(data: Data(receipt.location.documentToken.utf8))
                    .map { String(format: "%02x", $0) }.joined()]
    }
}

/// evaluate 观测装饰器：在传输层响应中捕获安装与状态里程碑，转发其余调用。
final class NativeStartupEventTransport: StartupTransport, @unchecked Sendable {
    private let base: any StartupTransport
    private let capture: NativeStartupCapture
    private let events: NativeStartupEventStream
    private let now: () -> TimeInterval
    private let pageLock = NSLock()
    private var pageID: String?

    init(base: any StartupTransport, capture: NativeStartupCapture, events: NativeStartupEventStream,
         now: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }) {
        self.base = base
        self.capture = capture
        self.events = events
        self.now = now
    }

    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        try await base.pages(port: port, timeout: timeout)
    }

    func targets(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        try await base.targets(port: port, timeout: timeout)
    }

    func connect(to url: URL, timeout: TimeInterval) throws {
        try Task.checkCancellation()
        let id = url.lastPathComponent
        guard events.bindPage(pid: capture.targetPID, pageID: id) else { throw CancellationError() }
        capture.bindPage(id)
        pageLock.lock(); pageID = id; pageLock.unlock()
        try base.connect(to: url, timeout: timeout)
    }

    private func currentPageID() -> String? {
        pageLock.lock(); defer { pageLock.unlock() }; return pageID
    }

    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        let boundPageID = currentPageID()
        let response = try await base.evaluate(source, timeout: timeout)
        try Task.checkCancellation()
        if let installation = capture.observe(response, at: now(), pageID: boundPageID) {
            events.startupInstalled(pid: capture.targetPID, runID: installation.runID,
                                    at: installation.installedAt, pageID: boundPageID)
        }
        return response
    }

    func disposeController(href: String, timeout: TimeInterval) async throws -> [String: Any] {
        try await base.disposeController(href: href, timeout: timeout)
    }

    func disconnectPage() {
        base.disconnectPage()
        pageLock.lock(); pageID = nil; pageLock.unlock()
        capture.bindPage(nil)
        _ = events.bindPage(pid: capture.targetPID, pageID: nil)
    }

    func close() { base.close() }
}

/// 冒烟报告验收：完成态、非跳过、完整资源计数（framesPending 为零）、
/// 正数视口/坐标系、明确的 rAF 统计口径与合法分位数。
enum NativeSmokeReportValidator {
    private static let resourceCounters = [
        "createdImages", "releasedImages", "liveImages",
        "createdBitmaps", "releasedBitmaps", "liveBitmaps",
        "createdCanvases", "releasedCanvases", "liveCanvases",
        "createdPaths", "releasedPaths", "livePaths",
        "createdRAF", "cancelledRAF", "liveRAF",
        "createdObjectURLs", "revokedObjectURLs", "liveObjectURLs",
        "framesPending"
    ]

    static func isSuccessfulCompletion(skipped: Any?, reportJSON: String?, evaluationFailed: Bool) -> Bool {
        guard !evaluationFailed,
              NativeStartupStatus.boolean(skipped) == false,
              let reportJSON, let data = reportJSON.data(using: .utf8),
              let raw = try? JSONSerialization.jsonObject(with: data),
              let report = raw as? [String: Any],
              NativeStartupStatus.boolean(report["completed"]) == true,
              NativeStartupStatus.boolean(report["skipped"]) == false,
              NativeStartupStatus.boolean(report["reduced"]) != nil,
              let elapsed = finiteNumber(report["elapsed"]),
              let duration = finiteNumber(report["duration"]),
              duration > 0, elapsed >= duration,
              report["stage"] as? String == "complete",
              finiteNumber(report["animationProgress"]) == 1,
              let viewport = report["viewport"] as? [String: Any],
              positiveNumber(viewport["width"]), positiveNumber(viewport["height"]),
              positiveNumber(viewport["dpr"]),
              let coordinateSize = report["coordinateSize"] as? [String: Any],
              positiveNumber(coordinateSize["width"]), positiveNumber(coordinateSize["height"]),
              let resources = report["resources"] as? [String: Any],
              resourceCounters.allSatisfy({ finiteNumber(resources[$0]) != nil }),
              finiteNumber(resources["framesPending"]) == 0,
              let jsFrame = report["jsFrame"] as? [String: Any],
              jsFrame["scope"] as? String == "JavaScript rAF interval and 2D canvas submission; excludes GPU/compositor/presentation timing",
              validStats(jsFrame["rafIntervalMs"]), validStats(jsFrame["renderSubmissionMs"]) else {
            return false
        }
        return true
    }

    private static func positiveNumber(_ value: Any?) -> Bool {
        guard let number = finiteNumber(value) else { return false }
        return number > 0
    }

    /// NSNumber 但排除布尔桥接值。
    private static func finiteNumber(_ value: Any?) -> Double? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let double = number.doubleValue
        return double.isFinite ? double : nil
    }

    /// 分位数统计：NSNull 表示“无测量”，否则需要正整数 count 与有限 median/p95/max。
    private static func validStats(_ value: Any?) -> Bool {
        guard let value else { return false }
        if value is NSNull { return true }
        guard let stats = value as? [String: Any],
              let count = finiteNumber(stats["count"]), count > 0, count.rounded() == count,
              finiteNumber(stats["median"]) != nil,
              finiteNumber(stats["p95"]) != nil,
              finiteNumber(stats["max"]) != nil else { return false }
        return true
    }
}

/// 打开请求等待器：continuation 只被恢复一次；后注册的超时若已晚于完成则立即
/// 取消，注册与完成并发竞速时同样保证已注册句柄被取消（互斥状态机）。
final class StartupApplicationWaiter: @unchecked Sendable {
    private enum State {
        case waiting(CheckedContinuation<any NativeApplication, Error>, DispatchWorkItem?)
        case finished
    }

    private let lock = NSLock()
    private var state: State

    init(_ continuation: CheckedContinuation<any NativeApplication, Error>) {
        state = .waiting(continuation, nil)
    }

    /// 替换语义：最新注册的超时句柄生效，旧句柄由调用方自行管理。
    func setTimeout(_ timeout: DispatchWorkItem) {
        lock.lock()
        switch state {
        case .waiting(let continuation, _):
            state = .waiting(continuation, timeout)
            lock.unlock()
        case .finished:
            lock.unlock()
            timeout.cancel()
        }
    }

    /// 首个结果获胜；此后的一切调用（包括重复 finish）都是空操作。
    func finish(_ result: Result<any NativeApplication, Error>) {
        lock.lock()
        guard case .waiting(let continuation, let timeout) = state else { lock.unlock(); return }
        state = .finished
        lock.unlock()
        timeout?.cancel()
        continuation.resume(with: result)
    }
}

// MARK: - 显示语言

/// 原生窗口只在显式预览/冒烟运行中保留。语言跟随系统，直到受信 ready 消息
/// 带来官方宿主 locale 才切换；错误文案按当前语言出双语表。
enum NativeDisplayLocale: Equatable {
    case chinese
    case english

    static func systemFallback(preferredLanguages: [String] = Locale.preferredLanguages) -> NativeDisplayLocale {
        let language = (preferredLanguages.first ?? Locale.current.identifier).lowercased()
        return language.hasPrefix("zh") ? .chinese : .english
    }

    /// 只接受受信 ready 消息里声明且受支持的 locale。
    static func verifiedReadyLocale(_ value: Any?) -> NativeDisplayLocale? {
        switch value as? String {
        case "zh-CN": return .chinese
        case "en": return .english
        default: return nil
        }
    }

    var identifier: String {
        switch self {
        case .chinese: return "zh-CN"
        case .english: return "en"
        }
    }

    var displayName: String {
        displayName(in: .main)
    }

    /// 优先读取 bundle 内对应语言的本地化显示名，缺失时回落 InfoPlist 声明。
    func displayName(in bundle: Bundle) -> String {
        let fallback = bundle.infoDictionary?["CFBundleDisplayName"] as? String ?? "Azhou"
        let language = self == .chinese ? "zh-Hans" : "en"
        guard let path = bundle.path(forResource: language, ofType: "lproj"),
              let localized = Bundle(path: path) else { return fallback }
        return localized.localizedString(forKey: "CFBundleDisplayName", value: fallback, table: "InfoPlist")
    }

    var quitTitle: String {
        switch self {
        case .chinese: return "退出\(displayName)"
        case .english: return "Quit \(displayName)"
        }
    }

    var closeTitle: String {
        switch self {
        case .chinese: return "关闭"
        case .english: return "Close"
        }
    }

    /// 固定 reason → 双语文案表；未知 reason 使用中性兜底，绝不透出原始错误文本。
    /// 文案为自有表述，仅受三条外部约束：英文不得出现汉字、page-missing 的
    /// 英文须含 "page"、renderer-ready-timeout 的英文须含 "ready"。
    func message(for reason: String) -> String {
        let zh = self == .chinese
        switch reason {
        case "resources-missing":
            return zh ? "资源目录当前无法访问。" : "The resources folder cannot be reached right now."
        case "page-missing":
            return zh ? "包内找不到动画页面，请重新构建后再试。"
                      : "The animation page is absent from the bundle; rebuild and retry."
        case "target-launch-timeout":
            return zh ? "等待 Codex 就绪超时，请改从原应用入口重试。"
                      : "Codex did not come up within the time limit; retry from its original app entry."
        case "renderer-ready-timeout":
            return zh ? "播放器迟迟没有就绪，请关闭窗口后重试。"
                      : "The player never became ready; close the window and try again."
        case "renderer-complete-timeout":
            return zh ? "播放未在期限内结束，请关闭窗口后重试。"
                      : "Playback ran past its deadline; close the window and try again."
        case "playback-start-error":
            return zh ? "这段动画未能开始播放。" : "Playback of the animation could not be started."
        case "javascript-error":
            return zh ? "动画脚本执行时出错。" : "The animation script hit an error while running."
        case "asset-error":
            return zh ? "阿舟素材读取失败，请检查本地素材后重新构建。"
                      : "Azhou assets failed to load; inspect the local assets and rebuild."
        case "target-exited":
            return zh ? "交接完成前 Codex 已经退出。" : "Codex went away before the handoff could finish."
        case "activation-rejected":
            return zh ? "系统拒绝了 Codex 的激活请求；请关闭本窗口，改由原应用入口打开。"
                      : "The system declined to activate Codex; close this window and use its original app entry."
        case "renderer-terminated":
            return zh ? "WebKit 渲染进程已终止。" : "The WebKit renderer process has terminated."
        case "target-missing":
            return zh ? "未发现可用的 Codex 主应用。" : "No usable Codex application was found."
        case "target-identity":
            return zh ? "Codex 进程身份或签名核验失败。" : "Codex failed its process identity or signature check."
        case "listener-mismatch":
            return zh ? "调试端口与已核验的 Codex 主进程不匹配。"
                      : "The debug port does not match the verified Codex process."
        case "page-pending":
            return zh ? "Codex 主页面还没就位。" : "The Codex main page is not in place yet."
        case "page-unsupported":
            return zh ? "这个 Codex 页面不满足启动接入条件。"
                      : "This Codex page does not satisfy the startup integration conditions."
        case "ambiguous-main-page":
            return zh ? "出现多个 Codex 主页面，本次接入已中止。"
                      : "More than one Codex main page appeared; this integration attempt was aborted."
        case "owner-conflict", "startup-active":
            return zh ? "页面上已有启动控制器，本次不覆盖、也不重播。"
                      : "The page already carries a startup controller; it was neither replaced nor replayed."
        case "startup-interrupted":
            return zh ? "接入期间 Codex 页面发生了变化。" : "The Codex page changed while integration was in progress."
        case "attach-timeout":
            return zh ? "启动接入超出了阶段或总时限。" : "Startup integration outran its stage or overall time limit."
        case "asset-invalid":
            return zh ? "包内缺少可用的 startup/install.js 生产载荷，本次不打开、也不注入 Codex。"
                      : "No usable production startup/install.js payload is in the bundle; Codex was neither opened nor injected."
        case "preview-promotion-error":
            return zh ? "预览切换到启动失败。" : "Switching from preview to launch failed."
        case "navigation-error":
            return zh ? "动画页面打开失败。" : "Opening the animation page failed."
        default:
            return zh ? "Codex 启动接入未完成，Codex 进程仍在运行。"
                      : "Codex startup integration did not complete; the Codex process is still running."
        }
    }
}

// MARK: - 宿主进程端口

@MainActor
protocol NativeApplication: AnyObject {
    var processIdentifier: Int32 { get }
    var bundleIdentifier: String? { get }
    var bundleURL: URL? { get }
    var executableURL: URL? { get }
    var launchTime: TimeInterval? { get }
    var isTerminated: Bool { get }
    var isActive: Bool { get }
    var isHidden: Bool { get }
    @discardableResult func activate() -> Bool
}

/// NSRunningApplication 适配器；激活动作可注入以便测试驱动宿主边界。
@MainActor
final class SystemNativeApplication: NativeApplication {
    let application: NSRunningApplication
    private let activateBody: () -> Bool
    init(_ application: NSRunningApplication, activate: (() -> Bool)? = nil) {
        self.application = application
        self.activateBody = activate ?? { application.activate(options: []) }
    }
    var processIdentifier: Int32 { application.processIdentifier }
    var bundleIdentifier: String? { application.bundleIdentifier }
    var bundleURL: URL? { application.bundleURL }
    var executableURL: URL? { application.executableURL }
    var launchTime: TimeInterval? { application.launchDate?.timeIntervalSince1970 }
    var isTerminated: Bool { application.isTerminated }
    var isActive: Bool { application.isActive }
    var isHidden: Bool { application.isHidden }
    func activate() -> Bool { activateBody() }
}

@MainActor
protocol NativeInstanceLock: AnyObject {
    func release()
}

/// flock 文件锁句柄；release 幂等。
@MainActor
private final class FileDescriptorNativeInstanceLock: NativeInstanceLock {
    private var descriptor: Int32
    init(_ descriptor: Int32) { self.descriptor = descriptor }
    func release() {
        guard descriptor >= 0 else { return }
        flock(descriptor, LOCK_UN)
        Darwin.close(descriptor)
        descriptor = -1
    }
}

enum NativeLockAcquisition {
    case acquired(any NativeInstanceLock)
    case busy
    case failed(Int32)
}

struct NativeLoopbackPortError: Error {
    let operation: String
    let code: Int32
}

/// 原生运行时端口：进程参数、时钟、应用枚举/打开、实例锁、回环端口分配、
/// 协议部件工厂与生命周期动作全部经由该协议，生产实现与测试替身同形。
@MainActor
protocol NativeAppRuntime: AnyObject {
    var arguments: [String] { get }
    var epoch: TimeInterval { get }
    var uptime: TimeInterval { get }
    var processIdentifier: Int { get }
    var bundleURL: URL { get }
    var resourceURL: URL? { get }
    func appearanceTheme() -> String
    var frontmostApplication: (any NativeApplication)? { get }
    func runningApplications(bundleIdentifier: String) -> [any NativeApplication]
    func application(processIdentifier: Int32) -> (any NativeApplication)?
    func urlForApplication(bundleIdentifier: String) -> URL?
    func openApplication(at url: URL, debuggingPort: Int,
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void)
    func openApplication(at url: URL, debuggingPort: Int, environment: [String: String],
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void)
    func acquireInstanceLock(identifier: String) -> NativeLockAcquisition
    func allocateLoopbackPort() throws -> Int
    func makeStartupTargetSystem() -> any StartupTargetSystem
    func makeStartupTransport(capture: NativeStartupCapture, events: NativeStartupEventStream) -> any StartupTransport
    func systemFallbackLocale() -> NativeDisplayLocale
    func setAccessoryPolicy()
    func activateIgnoringOtherApps()
    func terminate()
    func exit(code: Int32)
    func writeStandardOutput(_ line: String)
}

extension NativeAppRuntime {
    /// 只实现了原始 open 方法的旧运行时不得静默丢弃环境隔离：非空环境直接拒绝。
    func openApplication(at url: URL, debuggingPort: Int, environment: [String: String],
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void) {
        guard environment.isEmpty else {
            completion(nil, NSError(domain: "local.azhou.zcode-startup", code: 1)); return
        }
        openApplication(at: url, debuggingPort: debuggingPort, completion: completion)
    }
}

/// 系统调用返回值的可核验包装：ensured 将非零结果就地转成带操作名的类型化
/// 错误，让端口分配主流程保持“调用 → 核验”的直线结构。
private struct SyscallOutcome {
    let raw: Int32
    init(_ raw: Int32) { self.raw = raw }
    func ensured(otherwise operation: String, failure: (String) -> NativeLoopbackPortError) throws {
        guard raw == 0 else { throw failure(operation) }
    }
}

/// 生产运行时：AppKit/NSWorkspace/Darwin 边界的唯一实现，副作用可注入。
@MainActor
final class SystemNativeAppRuntime: NativeAppRuntime {
    private let openApplicationBody: (URL, NSWorkspace.OpenConfiguration,
                                      @escaping (NSRunningApplication?, Error?) -> Void) -> Void
    private let setAccessoryPolicyBody: () -> Void
    private let activateIgnoringOtherAppsBody: () -> Void
    private let terminateBody: () -> Void
    private let exitBody: (Int32) -> Void
    private let standardOutputBody: (String) -> Void

    init(openApplication: ((URL, NSWorkspace.OpenConfiguration,
                           @escaping (NSRunningApplication?, Error?) -> Void) -> Void)? = nil,
         setAccessoryPolicy: (() -> Void)? = nil,
         activateIgnoringOtherApps: (() -> Void)? = nil,
         terminate: (() -> Void)? = nil,
         exit: ((Int32) -> Void)? = nil,
         standardOutput: ((String) -> Void)? = nil) {
        self.openApplicationBody = openApplication ?? { url, configuration, completion in
            NSWorkspace.shared.openApplication(at: url, configuration: configuration) { application, error in
                DispatchQueue.main.async { completion(application, error) }
            }
        }
        self.setAccessoryPolicyBody = setAccessoryPolicy ?? { NSApp.setActivationPolicy(.accessory) }
        self.activateIgnoringOtherAppsBody = activateIgnoringOtherApps ?? { NSApp.activate(ignoringOtherApps: true) }
        self.terminateBody = terminate ?? { NSApp.terminate(nil) }
        self.exitBody = exit ?? { Darwin.exit($0) }
        self.standardOutputBody = standardOutput ?? { print($0); fflush(stdout) }
    }

    var arguments: [String] { CommandLine.arguments }
    var epoch: TimeInterval { ProcessInfo.processInfo.systemUptime }
    var uptime: TimeInterval { ProcessInfo.processInfo.systemUptime }
    var processIdentifier: Int { Int(ProcessInfo.processInfo.processIdentifier) }
    var bundleURL: URL { Bundle.main.bundleURL }
    var resourceURL: URL? { Bundle.main.resourceURL }
    func appearanceTheme() -> String {
        NSApp.effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua ? "dark" : "light"
    }
    var frontmostApplication: (any NativeApplication)? {
        NSWorkspace.shared.frontmostApplication.map { SystemNativeApplication($0) }
    }
    func runningApplications(bundleIdentifier: String) -> [any NativeApplication] {
        NSRunningApplication.runningApplications(withBundleIdentifier: bundleIdentifier).map { SystemNativeApplication($0) }
    }
    func application(processIdentifier: Int32) -> (any NativeApplication)? {
        NSRunningApplication(processIdentifier: processIdentifier).map { SystemNativeApplication($0) }
    }
    func urlForApplication(bundleIdentifier: String) -> URL? {
        NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleIdentifier)
    }
    func openApplication(at url: URL, debuggingPort: Int,
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void) {
        requestLaunch(url, configuration: launchConfiguration(debuggingPort: debuggingPort, environment: nil),
                      completion: completion)
    }
    func openApplication(at url: URL, debuggingPort: Int, environment: [String: String],
                         completion: @escaping ((any NativeApplication)?, Error?) -> Void) {
        requestLaunch(url, configuration: launchConfiguration(debuggingPort: debuggingPort, environment: environment),
                      completion: completion)
    }

    /// 组装 NSWorkspace 打开配置。环境参数只用于 ZCode 隔离启动：显式环境 ⇒
    /// 激活启动；空字典不覆盖继承环境（日常启动保持用户自己的 profile）。
    private func launchConfiguration(debuggingPort: Int, environment: [String: String]?) -> NSWorkspace.OpenConfiguration {
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = environment != nil
        configuration.hides = false
        configuration.hidesOthers = false
        configuration.createsNewApplicationInstance = false
        configuration.allowsRunningApplicationSubstitution = false
        configuration.addsToRecentItems = false
        configuration.arguments = ["--remote-debugging-address=127.0.0.1",
                                    "--remote-debugging-port=\(debuggingPort)"]
        if let environment, !environment.isEmpty { configuration.environment = environment }
        return configuration
    }

    private func requestLaunch(_ url: URL, configuration: NSWorkspace.OpenConfiguration,
                               completion: @escaping ((any NativeApplication)?, Error?) -> Void) {
        openApplicationBody(url, configuration) { application, error in
            completion(application.map { SystemNativeApplication($0) }, error)
        }
    }

    /// 每用户每启动器一把非阻塞 flock；路径带 uid 防跨用户互撞，O_NOFOLLOW
    /// 拒绝符号链接，失败分类为 busy（已被持有）或 failed（errno）。
    func acquireInstanceLock(identifier: String) -> NativeLockAcquisition {
        let descriptor = Darwin.open(lockFilePath(identifier: identifier),
                                     O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, S_IRUSR | S_IWUSR)
        guard descriptor >= 0 else { return .failed(errno) }
        guard flock(descriptor, LOCK_EX | LOCK_NB) == 0 else {
            let code = errno
            Darwin.close(descriptor)
            return (code == EWOULDBLOCK || code == EAGAIN) ? .busy : .failed(code)
        }
        return .acquired(FileDescriptorNativeInstanceLock(descriptor))
    }

    private func lockFilePath(identifier: String) -> String {
        URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("\(identifier)-\(getuid()).lock").path
    }

    /// bind 127.0.0.1:0 后 getsockname 取临时端口；句柄 CLOEXEC，全程核验
    /// 地址族与回环地址，任何一步失败抛出带操作名的类型化错误（操作名是
    /// startup-port-error 事件的既有诊断合同）。
    func allocateLoopbackPort() throws -> Int {
        func failure(_ operation: String) -> NativeLoopbackPortError { NativeLoopbackPortError(operation: operation, code: errno) }
        let descriptor = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else { throw failure("socket") }
        defer { Darwin.close(descriptor) }
        guard fcntl(descriptor, F_SETFD, FD_CLOEXEC) == 0 else { throw failure("close-on-exec") }

        var address = loopbackAddress()
        try withAddressPointer(&address) { pointer in
            Darwin.bind(descriptor, pointer, socklen_t(MemoryLayout<sockaddr_in>.size))
        }.ensured(otherwise: "bind-loopback", failure: failure)
        var reported = socklen_t(MemoryLayout<sockaddr_in>.size)
        try withMutableAddressPointer(&address) { pointer in
            Darwin.getsockname(descriptor, pointer, &reported)
        }.ensured(otherwise: "getsockname", failure: failure)

        let port = Int(UInt16(bigEndian: address.sin_port))
        guard (1...65535).contains(port), address.sin_family == sa_family_t(AF_INET),
              address.sin_addr.s_addr == inet_addr("127.0.0.1") else {
            throw NativeLoopbackPortError(operation: "verify-loopback", code: 0)
        }
        return port
    }

    private func loopbackAddress() -> sockaddr_in {
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = 0
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        return address
    }

    private func withAddressPointer(_ address: inout sockaddr_in,
                                    _ call: (UnsafePointer<sockaddr>) -> Int32) -> SyscallOutcome {
        SyscallOutcome(withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { call($0) }
        })
    }

    private func withMutableAddressPointer(_ address: inout sockaddr_in,
                                           _ call: (UnsafeMutablePointer<sockaddr>) -> Int32) -> SyscallOutcome {
        SyscallOutcome(withUnsafeMutablePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { call($0) }
        })
    }
    func makeStartupTargetSystem() -> any StartupTargetSystem { CodexStartupTargetSystem() }
    func makeStartupTransport(capture: NativeStartupCapture, events: NativeStartupEventStream) -> any StartupTransport {
        NativeStartupEventTransport(base: WallpaperTransport(), capture: capture, events: events)
    }
    func systemFallbackLocale() -> NativeDisplayLocale { NativeDisplayLocale.systemFallback() }
    func setAccessoryPolicy() { setAccessoryPolicyBody() }
    func activateIgnoringOtherApps() { activateIgnoringOtherAppsBody() }
    func terminate() { terminateBody() }
    func exit(code: Int32) { exitBody(code) }
    func writeStandardOutput(_ line: String) { standardOutputBody(line) }
}

// MARK: - 播放器呈现端口

@MainActor
protocol NativeScheduledAction: AnyObject {
    func cancel()
}

@MainActor
protocol NativePlayerPresentation: AnyObject {
    var geometry: [String: Any] { get }
    func createPlayer(locale: NativeDisplayLocale, mode: String, theme: String, inspect: Bool,
                      messageHandler: WKScriptMessageHandler, navigationDelegate: WKNavigationDelegate)
    func loadPlayer(page: URL, allowingReadAccessTo root: URL)
    func updateLabels(_ locale: NativeDisplayLocale)
    func showReady()
    func setNormalLevel()
    func makeVisible()
    func orderOut()
    func evaluateJavaScript(_ source: String, completion: ((Any?, Error?) -> Void)?)
    func fadeOut(duration: TimeInterval, completion: @escaping () -> Void)
    func schedule(after delay: TimeInterval, _ action: @escaping () -> Void) -> any NativeScheduledAction
    func takeSnapshot(_ completion: @escaping (NSImage?, Error?) -> Void)
    func stopLoading()
    func removeMessageHandler(named name: String)
    func showError(title: String, message: String, closeTitle: String)
}

@MainActor
private final class NativeTimerAction: NativeScheduledAction {
    private let timer: Timer
    init(_ timer: Timer) { self.timer = timer }
    func cancel() { timer.invalidate() }
}

/// AppKit/WebKit 呈现实现。窗口构造拆为“菜单 → 面板 → 视图”三步辅助方法，
/// 视觉常量集中命名；注入脚本的变量名与 freeze 结构是 animation.js 的消费
/// 合同，保持不变。激活、置前与模态框均为注入端口。窗口创建前的一切调用
/// 安全降级（几何为空、脚本求值/截图回错误、淡出直接完成）。
@MainActor
final class AppKitNativePlayerPresentation: NativePlayerPresentation {
    /// 暖纸底色（sRGB 分量以 0–1 计）与面板最小可用尺寸。
    private static let paperTint = NSColor(srgbRed: 0.945, green: 0.918, blue: 0.875, alpha: 1)
    private static let minimumPanel = NSSize(width: 640, height: 420)
    private static let fallbackPanel = NSRect(x: 0, y: 0, width: 1440, height: 900)

    private var panel: NSWindow?
    private var webView: WKWebView?
    private var quitEntry: NSMenuItem?
    private var appMenuEntry: NSMenuItem?
    private let activateApp: () -> Void
    private let revealPanel: (NSWindow) -> Void
    private let runAlert: (NSAlert) -> Void

    init(activateApp: (() -> Void)? = nil,
         makeVisible: ((NSWindow) -> Void)? = nil,
         runAlert: ((NSAlert) -> Void)? = nil) {
        self.activateApp = activateApp ?? { NSApp.activate(ignoringOtherApps: true) }
        self.revealPanel = makeVisible ?? { $0.makeKeyAndOrderFront(nil) }
        self.runAlert = runAlert ?? { _ = $0.runModal() }
    }

    var geometry: [String: Any] {
        guard let panel else { return [:] }
        return describeGeometry(of: panel)
    }

    func createPlayer(locale: NativeDisplayLocale, mode: String, theme: String, inspect: Bool,
                      messageHandler: WKScriptMessageHandler, navigationDelegate: WKNavigationDelegate) {
        installQuitMenu(locale: locale)
        let panel = makePanel(locale: locale)
        self.panel = panel
        panel.delegate = messageHandler as? NSWindowDelegate
        let view = makeWebView(mode: mode, locale: locale, theme: theme, inspect: inspect,
                               messageHandler: messageHandler, navigationDelegate: navigationDelegate)
        self.webView = view
        panel.contentView?.addSubview(view)
    }
    func loadPlayer(page: URL, allowingReadAccessTo root: URL) {
        webView?.loadFileURL(page, allowingReadAccessTo: root)
    }

    func updateLabels(_ locale: NativeDisplayLocale) {
        appMenuEntry?.title = locale.displayName
        quitEntry?.title = locale.quitTitle
        panel?.title = locale.displayName
    }
    func showReady() {
        panel?.level = .floating
        if let panel { revealPanel(panel) }
        activateApp()
    }
    func setNormalLevel() { panel?.level = .normal }
    func makeVisible() { if let panel { revealPanel(panel) } }
    func orderOut() { panel?.orderOut(nil) }
    func evaluateJavaScript(_ source: String, completion: ((Any?, Error?) -> Void)?) {
        guard let webView else { completion?(nil, CocoaError(.fileNoSuchFile)); return }
        webView.evaluateJavaScript(source, completionHandler: completion)
    }
    func fadeOut(duration: TimeInterval, completion: @escaping () -> Void) {
        guard let panel else { completion(); return }
        NSAnimationContext.beginGrouping()
        NSAnimationContext.current.duration = duration
        NSAnimationContext.current.completionHandler = completion
        panel.animator().alphaValue = 0
        NSAnimationContext.endGrouping()
    }
    func schedule(after delay: TimeInterval, _ action: @escaping () -> Void) -> any NativeScheduledAction {
        NativeTimerAction(Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { _ in action() })
    }
    func takeSnapshot(_ completion: @escaping (NSImage?, Error?) -> Void) {
        guard let webView else { completion(nil, CocoaError(.fileNoSuchFile)); return }
        webView.takeSnapshot(with: nil, completionHandler: completion)
    }
    func stopLoading() { webView?.stopLoading() }
    func removeMessageHandler(named name: String) {
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: name)
    }
    func showError(title: String, message: String, closeTitle: String) {
        let dialog = NSAlert()
        dialog.messageText = title
        dialog.informativeText = message
        dialog.addButton(withTitle: closeTitle)
        activateApp()
        runAlert(dialog)
    }

    // MARK: 构造辅助

    /// 主菜单挂一个“显示名 + 退出”项，语言切换时原地改标题。
    private func installQuitMenu(locale: NativeDisplayLocale) {
        let submenu = NSMenu()
        quitEntry = submenu.addItem(withTitle: locale.quitTitle,
                                    action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let topLevel = NSMenuItem()
        topLevel.submenu = submenu
        appMenuEntry = topLevel
        let menu = NSMenu()
        menu.addItem(topLevel)
        NSApp.mainMenu = menu
    }

    private func makePanel(locale: NativeDisplayLocale) -> NSWindow {
        let usable = (NSScreen.main ?? NSScreen.screens.first)?.visibleFrame ?? Self.fallbackPanel
        let panel = NSWindow(contentRect: usable,
                             styleMask: [.titled, .closable, .resizable, .fullSizeContentView],
                             backing: .buffered, defer: false)
        panel.backgroundColor = Self.paperTint
        panel.title = locale.displayName
        panel.titlebarAppearsTransparent = true
        panel.titleVisibility = .hidden
        panel.isReleasedWhenClosed = false
        panel.minSize = NSSize(width: min(Self.minimumPanel.width, usable.width),
                               height: min(Self.minimumPanel.height, usable.height))
        panel.setFrame(usable, display: false)
        return panel
    }

    /// 非持久数据存储 + launcher 消息通道 + 文档起始注入的外观脚本。
    /// 变量名与 Object.freeze 结构由 animation.js 消费，属对外合同。
    private func makeWebView(mode: String, locale: NativeDisplayLocale, theme: String, inspect: Bool,
                             messageHandler: WKScriptMessageHandler,
                             navigationDelegate: WKNavigationDelegate) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let controller = configuration.userContentController
        controller.add(messageHandler, name: "launcher")
        controller.addUserScript(WKUserScript(source: appearanceBootstrap(mode: mode, locale: locale, theme: theme),
                                              injectionTime: .atDocumentStart,
                                              forMainFrameOnly: true))
        let view = WKWebView(frame: panel?.contentView?.bounds ?? .zero, configuration: configuration)
        view.autoresizingMask = [.width, .height]
        view.navigationDelegate = navigationDelegate
        if let backgroundColor = panel?.backgroundColor { view.underPageBackgroundColor = backgroundColor }
        if #available(macOS 13.3, *), inspect { view.isInspectable = true }
        return view
    }

    private func appearanceBootstrap(mode: String, locale: NativeDisplayLocale, theme: String) -> String {
        let payload: [String: String] = ["locale": locale.identifier, "theme": theme]
        let encoded = (try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]))
            .flatMap { String(data: $0, encoding: .utf8) }
            ?? "{\"locale\":\"en\",\"theme\":\"light\"}"
        return "window.__agentSkinNativeMode = '\(mode)'; "
            + "window.__agentSkinAppearance = Object.freeze(\(encoded));"
    }

    private func describeGeometry(of panel: NSWindow) -> [String: Any] {
        func rect(_ value: NSRect) -> [String: Double] {
            ["x": value.origin.x, "y": value.origin.y, "width": value.width, "height": value.height]
        }
        let screen = panel.screen ?? NSScreen.main
        return ["frame": rect(panel.frame),
                "visibleFrame": screen.map { rect($0.visibleFrame) } ?? [:],
                "contentBounds": rect(panel.contentView?.bounds ?? .zero),
                "screen": screen?.localizedName ?? "",
                "backingScale": panel.backingScaleFactor]
    }
}

// MARK: - 资产与导航

/// 入口身份判定：ZCode 启动器必须显式声明 zcode；既有 Codex/旧入口缺省为
/// Codex；任何其他组合（错误声明、陌生 bundle）拒绝，绝不猜宿主。
enum NativeEntryIdentity {
    static func host(bundleIdentifier: String?, declaredHost: Any?) -> SkinHostID? {
        if bundleIdentifier == "local.azhou.zcode-startup" {
            return declaredHost as? String == "zcode" ? .zcode : nil
        }
        guard let declaredHost else { return .codex } // 既有 Codex/旧入口。
        return declaredHost as? String == "codex" && bundleIdentifier == "local.azhou.codex-startup" ? .codex : nil
    }
}

/// 播放器进度状态机：waiting → ready → completed，或 waiting → skippedBeforeReady
/// → completed。核心不变式：完成只能被接受一次，早关窗不能伪造就绪，迟到的
/// ready 不能把已跳过的播放器再完成一次。
struct NativePlayerProgress {
    private enum State {
        case waiting, ready, skippedBeforeReady, completed
    }

    private var state: State = .waiting

    var isReady: Bool { state == .ready || state == .completed }
    var isDone: Bool { state == .skippedBeforeReady || state == .completed }

    mutating func markReady() {
        switch state {
        case .waiting: state = .ready
        case .skippedBeforeReady: state = .completed
        case .ready, .completed: break
        }
    }

    /// 只有 ready 态接受一次完成；返回是否首次接受。
    mutating func acceptCompletion() -> Bool {
        guard state == .ready else { return false }
        state = .completed
        return true
    }

    mutating func markClosed() {
        switch state {
        case .waiting: state = .skippedBeforeReady
        case .ready: state = .completed
        case .skippedBeforeReady, .completed: break
        }
    }
}

/// 生产载荷读取，按“打开 → 读取 → 复核”三段组织：
/// 打开链全部走 openat 相对路径（目录标志 O_NOFOLLOW|O_DIRECTORY，载荷句柄
/// 追加 O_NONBLOCK 以对 FIFO 立即失败而非阻塞等待 writer）；读取段设 24 MiB
/// 硬顶、EINTR 重试并兼容短读；复核段在读取完成后重新 stat 每一层，确认
/// 同一 inode 的同一文件未被移动、替换或增长。任何一段不过即返回 nil。
enum StartupPayloadReader {
    private static let sizeCeiling = 24 * 1024 * 1024
    private static let chunkCapacity = 64 * 1024
    private static let directoryFlags = O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC
    private static let payloadFlags = O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC

    /// 打开成功的三级目录/文件句柄及其打开时的 stat 快照。
    private struct OpenedPayload {
        let rootFD: Int32
        let startupFD: Int32
        let sourceFD: Int32
        let rootSnapshot: stat
        let startupSnapshot: stat
        let sourceSnapshot: stat
    }

    static func read(from root: URL,
                     readChunk: (Int32, UnsafeMutableRawPointer?, Int) -> Int = { Darwin.read($0, $1, $2) }) -> String? {
        guard let opened = openChain(root) else { return nil }
        defer {
            Darwin.close(opened.sourceFD)
            Darwin.close(opened.startupFD)
            Darwin.close(opened.rootFD)
        }
        guard let bytes = drain(opened.sourceFD, expected: opened.sourceSnapshot, readChunk: readChunk),
              isUntampered(opened, root: root) else { return nil }
        return String(data: bytes, encoding: .utf8)
    }

    /// 逐层相对打开并快照：root → startup → install.js；载荷必须是尺寸在
    /// (0, sizeCeiling) 区间的常规文件。
    private static func openChain(_ root: URL) -> OpenedPayload? {
        let rootFD = Darwin.open(root.path, directoryFlags)
        guard rootFD >= 0 else { return nil }
        var rootSnapshot = stat()
        guard fstat(rootFD, &rootSnapshot) == 0 else { Darwin.close(rootFD); return nil }

        let startupFD = openat(rootFD, "startup", directoryFlags)
        guard startupFD >= 0 else { Darwin.close(rootFD); return nil }
        var startupSnapshot = stat()
        guard fstat(startupFD, &startupSnapshot) == 0 else {
            Darwin.close(startupFD); Darwin.close(rootFD); return nil
        }

        let sourceFD = openat(startupFD, "install.js", payloadFlags)
        guard sourceFD >= 0 else { Darwin.close(startupFD); Darwin.close(rootFD); return nil }
        var sourceSnapshot = stat()
        guard fstat(sourceFD, &sourceSnapshot) == 0,
              sourceSnapshot.st_mode & mode_t(S_IFMT) == mode_t(S_IFREG),
              sourceSnapshot.st_size > 0, sourceSnapshot.st_size < sizeCeiling else {
            Darwin.close(sourceFD); Darwin.close(startupFD); Darwin.close(rootFD); return nil
        }
        return OpenedPayload(rootFD: rootFD, startupFD: startupFD, sourceFD: sourceFD,
                             rootSnapshot: rootSnapshot, startupSnapshot: startupSnapshot,
                             sourceSnapshot: sourceSnapshot)
    }

    /// 读取全量字节；中途 I/O 错误、越过硬顶或最终长度与快照不符都返回 nil。
    private static func drain(_ descriptor: Int32, expected: stat,
                              readChunk: (Int32, UnsafeMutableRawPointer?, Int) -> Int) -> Data? {
        var bytes = Data()
        var chunk = [UInt8](repeating: 0, count: chunkCapacity)
        while bytes.count < expected.st_size {
            let allowance = min(chunk.count, sizeCeiling - bytes.count)
            guard allowance > 0 else { return nil }
            let received = chunk.withUnsafeMutableBufferPointer { buffer in
                readChunk(descriptor, buffer.baseAddress, allowance)
            }
            if received < 0 {
                if errno == EINTR { continue }
                return nil
            }
            if received == 0 { break }
            bytes.append(contentsOf: chunk[..<received])
        }
        guard bytes.count == expected.st_size, bytes.count < sizeCeiling else { return nil }
        return bytes
    }

    /// 复核三级路径仍是打开时的同一对象，且载荷文件自身未被替换或改动：
    /// 先看句柄上的 stat，再按名重查并要求与句柄一致，最后逐层复核目录。
    private static func isUntampered(_ opened: OpenedPayload, root: URL) -> Bool {
        var onHandle = stat()
        guard fstat(opened.sourceFD, &onHandle) == 0,
              isSameFile(opened.sourceSnapshot, onHandle) else { return false }
        var byName = stat()
        guard fstatat(opened.startupFD, "install.js", &byName, AT_SYMLINK_NOFOLLOW) == 0,
              isSameFile(onHandle, byName) else { return false }
        var startupNow = stat()
        guard fstatat(opened.rootFD, "startup", &startupNow, AT_SYMLINK_NOFOLLOW) == 0,
              isSameNode(opened.startupSnapshot, startupNow) else { return false }
        var rootNow = stat()
        return lstat(root.path, &rootNow) == 0 && isSameNode(opened.rootSnapshot, rootNow)
    }

    private static func isSameNode(_ left: stat, _ right: stat) -> Bool {
        left.st_dev == right.st_dev && left.st_ino == right.st_ino && left.st_mode == right.st_mode
    }

    private static func isSameFile(_ left: stat, _ right: stat) -> Bool {
        isSameNode(left, right) && left.st_size == right.st_size
            && left.st_mtimespec.tv_sec == right.st_mtimespec.tv_sec
            && left.st_mtimespec.tv_nsec == right.st_mtimespec.tv_nsec
            && left.st_ctimespec.tv_sec == right.st_ctimespec.tv_sec
            && left.st_ctimespec.tv_nsec == right.st_ctimespec.tv_nsec
    }
}

/// 本地文件导航策略：仅允许 file URL、无凭据/端口、host 仅限空或 localhost、
/// 解析符号链接后必须严格位于根目录之内（前缀路径分量匹配）。
enum LocalWebNavigation {
    static func decide(url: URL?, root: URL?, completion: (WKNavigationActionPolicy) -> Void) {
        guard let url, let root, url.isFileURL, root.isFileURL else { completion(.cancel); return }
        for item in [url, root] {
            if item.user != nil || item.password != nil || item.port != nil {
                completion(.cancel); return
            }
            if let host = item.host, !host.isEmpty, host.lowercased() != "localhost" {
                completion(.cancel); return
            }
        }
        let base = root.resolvingSymlinksInPath().standardizedFileURL.pathComponents
        let candidate = url.resolvingSymlinksInPath().standardizedFileURL.pathComponents
        completion(base.count > 1 && candidate.count > base.count && candidate.starts(with: base) ? .allow : .cancel)
    }
}

// MARK: - 页面消息与会话部件

/// 页面消息语法层：只负责从原始 body 提取并验证字段（action、locale、时长、
/// 跳过标记），不做任何状态推进。执行层据此只消费已验证的语义值。
enum PlayerMessage {
    case ready(verifiedLocale: NativeDisplayLocale?, durationSeconds: Double)
    case complete(skipped: Any?, report: Any?)
    case close
    case scriptFailure
    case assetFailure
    case unrecognized(action: String)

    static func decode(_ body: Any) -> PlayerMessage {
        let fields = body as? [String: Any] ?? [:]
        let action = (body as? String) ?? fields["action"] as? String ?? ""
        switch action {
        case "ready":
            return .ready(verifiedLocale: NativeDisplayLocale.verifiedReadyLocale(fields["locale"]),
                          durationSeconds: normalizedDuration(fields["duration"]))
        case "complete":
            return .complete(skipped: fields["skipped"], report: fields["report"] ?? [:])
        case "close": return .close
        case "jsError": return .scriptFailure
        case "assetError": return .assetFailure
        default: return .unrecognized(action: action)
        }
    }

    /// 毫秒 → 秒；非有限或非正时长归零（由看门狗兜底）。
    private static func normalizedDuration(_ value: Any?) -> Double {
        let milliseconds = (value as? NSNumber)?.doubleValue ?? 0
        return milliseconds.isFinite && milliseconds > 0 ? milliseconds / 1000 : 0
    }
}

/// 快照时间点计算：解析逗号分隔秒值，剔除非有限/负值/超出动画时长的点；
/// index 保留解析前的原始序号，文件命名与旧约定一致（%02d-%.2fs）。
enum SnapshotPlan {
    static func points(_ raw: String, duration: Double) -> [(index: Int, seconds: Double)] {
        raw.split(separator: ",").compactMap { Double($0) }.enumerated().compactMap { index, seconds in
            (seconds.isFinite && seconds >= 0 && (duration == 0 || seconds < duration))
                ? (index, seconds) : nil
        }
    }
}

/// 播放器会话：窗口呈现、显示语言、进度状态机、看门狗与快照句柄的唯一属主。
/// 到期动作（看门狗/快照）经回调端口交给编排层，部件本身不跨域。
@MainActor
final class PlayerStage {
    var presentation: (any NativePlayerPresentation)?
    private(set) var displayLocale: NativeDisplayLocale
    private(set) var progress = NativePlayerProgress()
    private(set) var webRoot: URL?
    private var watchdog: (any NativeScheduledAction)?
    private(set) var captures: [any NativeScheduledAction] = []
    /// 看门狗到期端口；捕获的是注册时刻的处理器。
    var watchdogExpiry: ((String) -> Void)?

    init(presentation: (any NativePlayerPresentation)?, locale: NativeDisplayLocale) {
        self.presentation = presentation
        self.displayLocale = locale
    }

    var isReady: Bool { progress.isReady }
    var isDone: Bool { progress.isDone }

    func markRendererReady() { progress.markReady() }
    @discardableResult func acceptRendererCompletion() -> Bool { progress.acceptCompletion() }
    func markWindowClosed() { progress.markClosed() }

    /// 采纳受信 locale：切换语言并同步原生窗口标签。
    func adoptDisplayLocale(_ locale: NativeDisplayLocale) {
        displayLocale = locale
        presentation?.updateLabels(locale)
    }

    func installPresentation(_ value: any NativePlayerPresentation) { presentation = value }

    func createPlayer(mode: String, theme: String, inspect: Bool,
                      messageHandler: WKScriptMessageHandler, navigationDelegate: WKNavigationDelegate) {
        presentation?.createPlayer(locale: displayLocale, mode: mode, theme: theme, inspect: inspect,
                                   messageHandler: messageHandler, navigationDelegate: navigationDelegate)
    }

    func adoptWebRoot(_ root: URL) { webRoot = PathCanonicalization.resolved(root) }

    func armWatchdog(_ seconds: Double, reason: String) {
        watchdog?.cancel()
        let expiry = watchdogExpiry
        watchdog = presentation?.schedule(after: seconds) { expiry?(reason) }
    }

    func scheduleCapture(after delay: TimeInterval, action: @escaping () -> Void) {
        guard let handle = presentation?.schedule(after: delay, action) else { return }
        captures.append(handle)
    }

    func cancelWatchdog() { watchdog?.cancel() }
    func cancelAllTimers() { watchdog?.cancel(); captures.forEach { $0.cancel() } }

    func presentReady() { presentation?.showReady() }
    func normalizeWindowLevel() { presentation?.setNormalLevel() }
    func makeVisible() { presentation?.makeVisible() }
    func orderOut() { presentation?.orderOut() }
    func evaluate(_ source: String, completion: ((Any?, Error?) -> Void)?) {
        presentation?.evaluateJavaScript(source, completion: completion)
    }
    func fadeOut(duration: TimeInterval, completion: @escaping () -> Void) {
        presentation?.fadeOut(duration: duration, completion: completion)
    }
    func takeSnapshot(_ completion: @escaping (NSImage?, Error?) -> Void) {
        presentation?.takeSnapshot(completion)
    }
    func geometryRecord() -> [String: Any] { presentation?.geometry ?? [:] }
    func stopLoading() { presentation?.stopLoading() }
    func removeMessageHandler() { presentation?.removeMessageHandler(named: "launcher") }
    func presentError(title: String, message: String, closeTitle: String) {
        presentation?.showError(title: title, message: message, closeTitle: closeTitle)
    }
}

/// 受信启动会话：实例锁、目标解析与核验、启动事件流、安装捕获、生产载荷与
/// 回环端口的属主。所有方法只操作本会话状态；跨部件流程由编排层组合。
@MainActor
final class TrustedLaunchSession {
    private(set) var eventStream: NativeStartupEventStream?
    private(set) var capture: NativeStartupCapture?
    private(set) var instanceLock: (any NativeInstanceLock)?
    private(set) var lockFailureReason: String?
    private(set) var startupRequested = false
    private(set) var requested = false
    private(set) var targetURL: URL?
    private(set) var target: (any NativeApplication)?
    /// 冷启动 open 是否在途（交接前的等待提示依据）。
    var opening = false
    /// 目标激活是否已被请求且成功（激活只做一次）。
    var activated = false

    /// 幂等开启事件流；首个调用发出 launcher-start。
    func beginEventStream(writer: NativeEventWriter, at uptime: TimeInterval) {
        guard eventStream == nil else { return }
        let stream = NativeStartupEventStream(writer: writer)
        eventStream = stream
        stream.begin(at: uptime)
    }

    /// 标记受信启动已被请求（启动请求与重开面板共用一个标志）。
    func markLaunchRequested() {
        startupRequested = true
        requested = true
    }

    /// 记录本轮发现的目标地址（可能是 nil：发现失败）。
    func recordDiscoveredTarget(_ url: URL?) { targetURL = url }

    var isStreamPending: Bool { eventStream?.isPending == true }
    func latchStreamFailure(_ reason: String) { eventStream?.latchFailure(reason) }
    func latchStreamInterruption() { eventStream?.latchInterruption() }
    @discardableResult
    func concludeEventStream(_ outcome: StartupOutcome, at uptime: TimeInterval) -> NativeStartupFinalOutcome? {
        eventStream?.resolve(outcome, observation: capture?.snapshot(), at: uptime)
    }
    @discardableResult
    func finishEventStream(at uptime: TimeInterval) -> NativeStartupFinalOutcome? {
        eventStream?.finish(at: uptime)
    }
    func recordCapture(_ value: NativeStartupCapture) { capture = value }
    func recordTarget(_ application: any NativeApplication) { target = application }

    /// 实例锁获取：busy 时尝试唤起既有入口并记录 duplicate-entry；errno 失败
    /// 记录 lock-error 并以 protocol-error 收场。
    func acquireInstanceLock(runtime: any NativeAppRuntime, journal: LauncherJournal,
                             launcherBundleID: String) -> Bool {
        switch runtime.acquireInstanceLock(identifier: launcherBundleID) {
        case .acquired(let lock):
            instanceLock = lock
            return true
        case .failed(let code):
            lockFailureReason = "protocol-error"
            journal.record("lock-error", ["errno": Int(code)])
            return false
        case .busy:
            lockFailureReason = "startup-active"
            let existing = runtime.runningApplications(bundleIdentifier: launcherBundleID)
                .first { $0.processIdentifier != runtime.processIdentifier && !$0.isTerminated }
            let result = existing?.activate() ?? false
            journal.record("duplicate-entry", ["existing": journal.applicationRecord(existing),
                                               "activationRequested": result])
            return false
        }
    }

    func releaseInstanceLock() {
        instanceLock?.release()
        instanceLock = nil
    }

    /// 按启动模式策略发现目标（preview/smoke 不做发现；probe 与已晋升预览做）。
    func discoverTarget(arguments: [String], promoted: Bool,
                        runtime: any NativeAppRuntime, identity: LauncherIdentity) -> URL? {
        StartupModePolicy.resolveTarget(arguments: arguments, promoted: promoted) {
            resolveInstalledTarget(runtime: runtime, identity: identity)
        }
    }

    /// 候选顺序：运行中的目标实例 → 平台默认安装路径 → LaunchServices 注册位置；
    /// 每个候选都过完整核验链，取首个通过者。
    private func resolveInstalledTarget(runtime: any NativeAppRuntime, identity: LauncherIdentity) -> URL? {
        var candidates = runtime.runningApplications(bundleIdentifier: identity.targetBundleID).compactMap { $0.bundleURL }
        candidates += identity.host == .zcode ? [URL(fileURLWithPath: "/Applications/ZCode.app")]
            : [URL(fileURLWithPath: "/Applications/ChatGPT.app"), URL(fileURLWithPath: "/Applications/Codex.app")]
        if let url = runtime.urlForApplication(bundleIdentifier: identity.targetBundleID) { candidates.append(url) }
        return candidates.compactMap { Self.verifiedBundle($0, runtime: runtime, identity: identity) }.first
    }

    /// 目标 bundle 核验：候选通过“独立 .app 外壳 → 目标身份 → 自有可执行文件”
    /// 三段谓词后原样返回，任一段不过即 nil。
    static func verifiedBundle(_ candidate: URL, runtime: any NativeAppRuntime, identity: LauncherIdentity) -> URL? {
        let url = PathCanonicalization.resolved(candidate)
        guard isStandaloneAppBundle(url, runtime: runtime),
              ownedExecutable(of: url, identity: identity) != nil else { return nil }
        return url
    }

    /// 外壳谓词：阵营已定、是 .app、不嵌在其他 .app 内、不是启动器自身。
    private static func isStandaloneAppBundle(_ url: URL, runtime: any NativeAppRuntime) -> Bool {
        guard url.pathExtension.lowercased() == "app",
              !url.deletingLastPathComponent().pathComponents.contains(where: { $0.lowercased().hasSuffix(".app") }),
              url != PathCanonicalization.resolved(runtime.bundleURL) else { return false }
        return true
    }

    /// 身份 + 可执行谓词：bundle id 与目标一致，可执行文件解析后位于
    /// Contents/MacOS 之下且确实可执行。
    private static func ownedExecutable(of url: URL, identity: LauncherIdentity) -> URL? {
        guard identity.host != nil,
              let bundle = Bundle(url: url), bundle.bundleIdentifier == identity.targetBundleID,
              let executable = bundle.executableURL.map({ PathCanonicalization.resolved($0) }),
              executable.path.hasPrefix(url.appendingPathComponent("Contents/MacOS").path + "/"),
              FileManager.default.isExecutableFile(atPath: executable.path) else { return nil }
        return executable
    }

    /// 安装身份键：bundle id、版本、构建号来自已核验 bundle；可执行哈希仅 ZCode
    /// 分支计算（Codex 链路按操作分支做 codesign 核验，不在组装期伪造摘要）。
    func hostApplicationKey(for url: URL, identity: LauncherIdentity) -> HostApplicationKey? {
        guard let bundle = Bundle(url: url), let bundleID = bundle.bundleIdentifier,
              let executable = bundle.executableURL.map({ PathCanonicalization.resolved($0) }),
              executable.path.hasPrefix(PathCanonicalization.resolved(url).appendingPathComponent("Contents/MacOS").path + "/"),
              let host = identity.host else { return nil }
        // ZCode 必须给出可计算的真实指纹；读不到可执行文件时整体拒绝。
        var executableHash = ""
        if host == .zcode {
            guard let digest = Self.executableSHA256(of: executable) else { return nil }
            executableHash = digest
        }
        let info = bundle.infoDictionary ?? [:]
        return HostApplicationKey(
            host: host, bundleURL: PathCanonicalization.resolved(url), executableURL: executable,
            bundleIdentifier: bundleID,
            version: (info["CFBundleShortVersionString"] as? String) ?? "",
            build: (info["CFBundleVersion"] as? String) ?? "",
            executableSHA256: executableHash)
    }

    /// ZCode 安装指纹：读入可执行文件计算 SHA-256（十六进制小写）。
    private static func executableSHA256(of executable: URL) -> String? {
        guard let bytes = try? Data(contentsOf: executable) else { return nil }
        return SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    }

    /// 生产载荷：资源目录缺失或读取防御未通过都以 asset-invalid 拒绝。
    func productionPayload(runtime: any NativeAppRuntime) throws -> String {
        guard let resources = runtime.resourceURL else {
            throw StartupFailure(reason: "asset-invalid", message: "资源目录缺失，本次不启动也不注入 Codex。")
        }
        guard let text = StartupPayloadReader.read(from: PathCanonicalization.resolved(resources)) else {
            throw StartupFailure(reason: "asset-invalid", message: "startup/install.js 生产载荷缺失或无效，本次不启动也不注入 Codex。")
        }
        return text
    }

    /// 运行中目标的完整身份；任一字段缺失即 target-identity 拒绝。
    func targetFacts(_ application: any NativeApplication) throws -> StartupTargetFacts {
        guard !application.isTerminated, let bundle = application.bundleURL, let executable = application.executableURL,
              let bundleID = application.bundleIdentifier else {
            throw StartupFailure(reason: "target-identity", message: "Codex 进程身份信息不完整。")
        }
        return StartupTargetFacts(pid: application.processIdentifier,
                                  bundle: PathCanonicalization.resolved(bundle),
                                  executable: PathCanonicalization.resolved(executable),
                                  bundleID: bundleID, launchTime: application.launchTime)
    }

    /// 回环端口准备：分配失败记录 startup-port-error（无事件流时也留痕）并
    /// 以 listener-mismatch 拒绝。
    func prepareLoopbackPort(runtime: any NativeAppRuntime, journal: LauncherJournal) throws -> Int {
        do {
            let port = try runtime.allocateLoopbackPort()
            journal.record("startup-port-selected", ["port": port, "requiresTargetListenerVerification": true])
            return port
        } catch let error as NativeLoopbackPortError {
            if let stream = eventStream {
                stream.portError(operation: error.operation, errno: error.code, at: runtime.uptime)
            } else {
                journal.eventWriter.emit("startup-port-error",
                                         fields: ["reason": "listener-mismatch",
                                                  "operation": error.operation, "errno": Int(error.code)])
            }
            throw StartupFailure(reason: "listener-mismatch", message: "本机回环调试端口准备失败。")
        } catch {
            throw StartupFailure(reason: "listener-mismatch", message: "本机回环调试端口准备失败。")
        }
    }
}

/// 终局账本：terminating/failed/promoted/退出码/smoke 结果的属主。写入点分散
/// 在各编排流程，读取点集中在拆除序列。
@MainActor
final class ExitLedger {
    private let smokeOnly: Bool
    var terminating = false
    var failed = false
    var promoted = false
    var processExitCode: Int32 = 0
    var smokeResultSucceeded = false

    init(smokeOnly: Bool) { self.smokeOnly = smokeOnly }

    /// 关闭即失败：smoke 未验证完成时以退出码 1 记账。
    func markSmokeFailureExit() {
        failed = true
        processExitCode = 1
    }

    /// 拆除前对 smoke 结果收口：未成功则强制失败并保底退出码 1。
    func enforceSmokeTeardown() {
        guard smokeOnly, !smokeResultSucceeded else { return }
        failed = true
        processExitCode = max(processExitCode, 1)
    }
}

/// 有界打开过程：在阶段/总预算内请求 NSWorkspace 打开，超时、回调错误、
/// 身份不符与核验失败分别映射到固定的 reason 词表。等待器保证 continuation
/// 只恢复一次，先到的超时或回调获胜。回调内的裁定收拢在 classify() 里，
/// 主路径只负责把裁定结果交还等待器。
@MainActor
enum BoundedTargetOpen {
    static func run(runtime: any NativeAppRuntime, targetBundleID: String, url: URL, port: Int,
                    deadline: TimeInterval, system: any StartupTargetSystem,
                    log: @escaping (String, [String: Any]) -> Void) async throws -> any NativeApplication {
        let openTimeout = try StartupBudget.boundedTimeout(
            maximum: 45, stageDeadline: deadline, totalDeadline: deadline,
            now: runtime.uptime
        )
        return try await withCheckedThrowingContinuation { continuation in
            let waiter = StartupApplicationWaiter(continuation)
            armStageTimeout(waiter, timeout: openTimeout)
            log("target-open-request", ["path": url.path, "bundleID": targetBundleID, "debuggingPort": port])
            runtime.openApplication(at: url, debuggingPort: port) { application, error in
                DispatchQueue.main.async {
                    if let verdict = classify(application, error: error, expectedBundle: url,
                                              targetBundleID: targetBundleID, deadline: deadline,
                                              now: runtime.uptime, system: system) {
                        waiter.finish(.failure(verdict))
                    } else if let application {
                        waiter.finish(.success(application))
                    }
                }
            }
        }
    }

    private static func armStageTimeout(_ waiter: StartupApplicationWaiter, timeout: TimeInterval) {
        let expiry = DispatchWorkItem {
            waiter.finish(.failure(StartupFailure(reason: "attach-timeout", message: "打开请求超出了阶段预算。")))
        }
        waiter.setTimeout(expiry)
        DispatchQueue.main.asyncAfter(deadline: .now() + timeout, execute: expiry)
    }

    /// 打开回调裁定：返回 nil 表示应用通过全部检查；返回 StartupFailure 表示
    /// 应以该失败结束等待。deadline 逾期优先于一切回调内容。
    private static func classify(_ application: (any NativeApplication)?, error: Error?,
                                 expectedBundle: URL, targetBundleID: String,
                                 deadline: TimeInterval, now: TimeInterval,
                                 system: any StartupTargetSystem) -> StartupFailure? {
        guard now < deadline else {
            return StartupFailure(reason: "attach-timeout", message: "打开回调抵达时预算已耗尽。")
        }
        if error != nil { return StartupFailure(reason: "target-missing", message: "目标应用打开失败。") }
        guard let application, !application.isTerminated,
              let bundle = application.bundleURL, let executable = application.executableURL,
              let bundleID = application.bundleIdentifier,
              bundle.resolvingSymlinksInPath().standardizedFileURL == expectedBundle,
              bundleID == targetBundleID else {
            return StartupFailure(reason: "target-identity", message: "系统返回的应用与预期路径不一致。")
        }
        let facts = StartupTargetFacts(pid: application.processIdentifier,
                                       bundle: bundle.resolvingSymlinksInPath().standardizedFileURL,
                                       executable: executable.resolvingSymlinksInPath().standardizedFileURL,
                                       bundleID: bundleID, launchTime: application.launchTime)
        do {
            try system.validate(facts, deadline: deadline)
            return nil
        } catch let failure as StartupFailure where failure.reason == "attach-timeout" {
            return failure
        } catch let failure as WallpaperFailure where failure.state == "inspection-timeout" {
            return StartupFailure(reason: "attach-timeout", message: "进程核验超出了阶段预算。")
        } catch {
            return StartupFailure(reason: "target-identity", message: "进程或签名核验未通过。")
        }
    }
}

// MARK: - 编排门面

/// 应用门面：NSApplication/WK 导航/脚本消息的协议入口，以及跨部件流程
/// （入口管线、消息分发、失败呈现、交接、终局、拆除）。逐部件状态分别由
/// LauncherCommandLine/LauncherIdentity/LauncherJournal/PlayerStage/
/// TrustedLaunchSession/ExitLedger 持有。
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    private let runtime: any NativeAppRuntime
    private let commandLine: LauncherCommandLine
    private let identity: LauncherIdentity
    private let journal: LauncherJournal
    private let stage: PlayerStage
    private let session: TrustedLaunchSession
    private let exitLedger: ExitLedger

    /// 独占播放器模式（预览/冒烟）；一经晋升即转正为受信启动。
    private var isPlayerExclusive: Bool { !exitLedger.promoted && commandLine.playerExclusive }

    init(runtime: (any NativeAppRuntime)? = nil,
         presentation: (any NativePlayerPresentation)? = nil) {
        let resolvedRuntime = runtime ?? SystemNativeAppRuntime()
        let parsedArguments = LauncherCommandLine(arguments: resolvedRuntime.arguments)
        self.runtime = resolvedRuntime
        self.commandLine = parsedArguments
        self.identity = LauncherIdentity(bundleURL: resolvedRuntime.bundleURL)
        self.journal = LauncherJournal(runtime: resolvedRuntime, epoch: resolvedRuntime.epoch,
                                       smokeOnly: parsedArguments.isSmokeTest)
        self.exitLedger = ExitLedger(smokeOnly: parsedArguments.isSmokeTest)
        self.stage = PlayerStage(presentation: presentation, locale: resolvedRuntime.systemFallbackLocale())
        self.session = TrustedLaunchSession()
        super.init()
        stage.watchdogExpiry = { [weak self] reason in self?.handleWatchdogExpiry(reason) }
    }

    // MARK: 入口管线

    func applicationDidFinishLaunching(_ notification: Notification) {
        runtime.setAccessoryPolicy()
        journal.openSink(arguments: commandLine.arguments, host: identity.host)
        if commandLine.isProbe {
            runReadonlyProbe()
            exitLedger.terminating = true; runtime.terminate(); return
        }
        if !isPlayerExclusive {
            session.beginEventStream(writer: journal.eventWriter, at: runtime.uptime)
        }
        guard session.acquireInstanceLock(runtime: runtime, journal: journal,
                                          launcherBundleID: identity.launcherBundleID) else {
            if let final = session.concludeEventStream(.failed(reason: session.lockFailureReason ?? "protocol-error"),
                                                       at: runtime.uptime) {
                exitLedger.processExitCode = final.exitCode
            } else if commandLine.isSmokeTest {
                exitLedger.markSmokeFailureExit()
            }
            exitLedger.terminating = true; runtime.terminate(); return
        }
        if !isPlayerExclusive {
            beginTrustedLaunch()
            return
        }
        presentPlayerWindow()
    }

    /// 只读探测：发现目标并单发 probe 事件；不取锁、不开窗口。
    private func runReadonlyProbe() {
        session.recordDiscoveredTarget(session.discoverTarget(arguments: commandLine.arguments, promoted: exitLedger.promoted,
                                                             runtime: runtime, identity: identity))
        journal.emitProbe(
            targetPath: session.targetURL?.path ?? "",
            targetBundleID: session.targetURL.flatMap { Bundle(url: $0)?.bundleIdentifier } ?? "",
            running: runtime.runningApplications(bundleIdentifier: identity.targetBundleID).map { journal.applicationRecord($0) },
            frontmost: journal.applicationRecord(runtime.frontmostApplication))
    }

    /// 独占播放器窗口装配：本地页面加载就绪前保持不可见，20 秒 ready 看门狗兜底。
    private func presentPlayerWindow() {
        if commandLine.isSmokeTest { journal.recordSmoke("player-start", ["mode": "smoke"]) }
        else { journal.record("player-start", ["mode": "preview", "targetPath": session.targetURL?.path ?? ""]) }
        if stage.presentation == nil { stage.installPresentation(AppKitNativePlayerPresentation()) }
        stage.createPlayer(mode: isPlayerExclusive ? "preview" : "launch",
                           theme: runtime.appearanceTheme(), inspect: commandLine.wantsInspector,
                           messageHandler: self, navigationDelegate: self)
        guard let resources = runtime.resourceURL else {
            presentFailure(stage.displayLocale.message(for: "resources-missing"), "resources-missing"); return
        }
        let webDirectory = resources.appendingPathComponent("web", isDirectory: true)
        stage.adoptWebRoot(webDirectory)
        let page = webDirectory.appendingPathComponent("index.html")
        guard FileManager.default.fileExists(atPath: page.path) else {
            presentFailure(stage.displayLocale.message(for: "page-missing"), "page-missing"); return
        }
        stage.presentation?.loadPlayer(page: page, allowingReadAccessTo: webDirectory)
        stage.armWatchdog(20, reason: "renderer-ready-timeout")
        journal.record("window-created", stage.geometryRecord())
    }

    // MARK: 页面消息（语法已由 PlayerMessage 验证，这里只推进状态机）

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        receivePlayerMessage(body: message.body, isMainFrame: message.frameInfo.isMainFrame)
    }

    func receivePlayerMessage(body: Any, isMainFrame: Bool) {
        guard isMainFrame, !exitLedger.terminating else { return }
        switch PlayerMessage.decode(body) {
        case .ready(let locale, let duration):
            rendererBecameReady(locale: locale, duration: duration)
        case .complete(let skipped, let report):
            rendererCompleted(skipped: skipped, report: report)
        case .close:
            abandonPlayerWindow()
        case .scriptFailure:
            presentFailure(stage.displayLocale.message(for: "javascript-error"), "javascript-error")
        case .assetFailure:
            presentFailure(stage.displayLocale.message(for: "asset-error"), "asset-error")
        case .unrecognized(let action):
            journal.record("unhandled-message", ["action": action])
        }
    }

    private func rendererBecameReady(locale: NativeDisplayLocale?, duration: Double) {
        guard !stage.isReady else { journal.record("duplicate-ready-ignored"); return }
        if let locale { stage.adoptDisplayLocale(locale) }
        stage.markRendererReady()
        stage.presentReady()
        let startExpression = isPlayerExclusive ? "window.launcherUI.replay()" : "window.launcherUI.beginLaunch()"
        stage.evaluate(startExpression) { [weak self] _, error in
            guard let self, !self.exitLedger.terminating else { return }
            if let error { self.presentFailure(error.localizedDescription, "playback-start-error"); return }
            if self.commandLine.isSmokeTest {
                self.journal.recordSmoke("playback-start", ["durationSeconds": duration])
            } else {
                self.journal.record("playback-start", ["durationSeconds": duration, "window": self.stage.geometryRecord()])
            }
            self.stage.armWatchdog(max(25, duration + 12), reason: "renderer-complete-timeout")
            self.scheduleSnapshots(duration)
            if !self.isPlayerExclusive { self.beginTrustedLaunch() }
        }
    }

    private func rendererCompleted(skipped: Any?, report: Any?) {
        guard !exitLedger.failed, stage.acceptRendererCompletion() else { return }
        if commandLine.isSmokeTest { journal.recordSmoke("animation-complete") }
        else { journal.record("animation-complete", ["report": report ?? [:]]) }
        guard isPlayerExclusive else { finishHandoffIfReady("animation-complete"); return }
        // 预览/冒烟是一次性的：完成后取渲染器报告判定成败，随即退出。
        stage.cancelWatchdog()
        stage.evaluate("JSON.stringify(window.launcherUI.report())") { [weak self] result, error in
            guard let self else { return }
            let succeeded: Bool
            if self.commandLine.isSmokeTest {
                succeeded = NativeSmokeReportValidator.isSuccessfulCompletion(
                    skipped: skipped,
                    reportJSON: result as? String,
                    evaluationFailed: error != nil
                )
            } else {
                succeeded = error == nil && (result as? String)?.isEmpty == false
            }
            if self.commandLine.isSmokeTest {
                self.exitLedger.smokeResultSucceeded = succeeded
                if !succeeded { self.exitLedger.markSmokeFailureExit() }
                self.journal.recordSmoke("preview-result", ["success": succeeded])
            } else {
                self.journal.record("preview-result", ["success": succeeded,
                                                       "measurementScope": "front-end JS/rAF only, not GPU/presentation timing"])
            }
            self.exitLedger.terminating = true; self.runtime.terminate()
        }
    }

    /// 用户主动放弃窗口（close 消息或窗口关闭）：smoke 未验证即失败退出，
    /// 进行中的事件流记为中断。
    private func abandonPlayerWindow() {
        if commandLine.isSmokeTest && !exitLedger.smokeResultSucceeded { exitLedger.markSmokeFailureExit() }
        if session.isStreamPending { session.latchStreamInterruption() }
        exitLedger.terminating = true; runtime.terminate()
    }

    /// 看门狗到期：已完成的等待视为目标启动超时，否则维持本档 reason。
    private func handleWatchdogExpiry(_ reason: String) {
        guard !exitLedger.terminating else { return }
        let effectiveReason = stage.isDone ? "target-launch-timeout" : reason
        presentFailure(stage.displayLocale.message(for: effectiveReason), effectiveReason)
    }

    // MARK: 快照

    private func scheduleSnapshots(_ duration: Double) {
        guard let directory = commandLine.snapshotDirectory else { return }
        do { try FileManager.default.createDirectory(atPath: directory, withIntermediateDirectories: true) }
        catch { journal.record("snapshot-error", ["message": error.localizedDescription]); return }
        for point in SnapshotPlan.points(commandLine.snapshotTimes, duration: duration) {
            let base = URL(fileURLWithPath: directory)
                .appendingPathComponent(String(format: "%02d-%.2fs", point.index + 1, point.seconds))
            stage.scheduleCapture(after: point.seconds) { [weak self] in
                self?.captureSnapshot(at: base, scheduledSeconds: point.seconds)
            }
        }
    }

    private func captureSnapshot(at base: URL, scheduledSeconds: Double) {
        guard !exitLedger.terminating else { return }
        stage.evaluate("JSON.stringify(window.launcherUI.report())") { result, _ in
            if let report = result as? String {
                try? report.write(to: base.appendingPathExtension("json"), atomically: true, encoding: .utf8)
            }
        }
        stage.takeSnapshot { [weak self] image, error in
            guard let data = image?.tiffRepresentation, let bitmap = NSBitmapImageRep(data: data),
                  let png = bitmap.representation(using: .png, properties: [:]) else {
                self?.journal.record("snapshot-error", ["message": error?.localizedDescription ?? "no image"]); return
            }
            do {
                try png.write(to: base.appendingPathExtension("png"))
                self?.journal.record("snapshot-saved", ["path": base.path + ".png", "scheduledSeconds": scheduledSeconds])
            } catch {
                self?.journal.record("snapshot-error", ["message": error.localizedDescription])
            }
        }
    }

    // MARK: 受信启动

    /// 启动受信会话：目标发现与核验 → 唯一性检查 → 交给共享宿主工厂执行。
    /// 完成后按宿主阵营走类型化（ZCode）或既有（Codex）终局。
    private func beginTrustedLaunch() {
        guard !session.startupRequested, !exitLedger.terminating else { return }
        session.beginEventStream(writer: journal.eventWriter, at: runtime.uptime)
        session.markLaunchRequested()
        session.recordDiscoveredTarget(session.discoverTarget(arguments: commandLine.arguments, promoted: exitLedger.promoted,
                                                             runtime: runtime, identity: identity))
        guard let url = session.targetURL,
              TrustedLaunchSession.verifiedBundle(url, runtime: runtime, identity: identity) == url else {
            concludeStartupRun(.failed(reason: "target-missing")); return
        }
        guard let expectedApplication = session.hostApplicationKey(for: url, identity: identity) else {
            concludeStartupRun(.failed(reason: "target-identity")); return
        }
        let running = runtime.runningApplications(bundleIdentifier: identity.targetBundleID).filter { !$0.isTerminated }
        let matching = running.filter { $0.bundleURL.map({ PathCanonicalization.resolved($0) }) == url }
        guard running.isEmpty || (running.count == 1 && matching.count == 1) else {
            concludeStartupRun(.failed(reason: "target-identity")); return
        }
        Task { @MainActor [weak self] in
            guard let self else { return }
            let result = await self.launchThroughSkinHost(expectedApplication: expectedApplication)
            self.session.opening = false
            if expectedApplication.host == .zcode {
                self.finishZCodeStartup(result, expectedApplication: expectedApplication, promoted: self.exitLedger.promoted)
            } else {
                self.concludeStartupRun(startupLegacyOutcome(from: result))
            }
        }
    }

    /// 组装共享宿主工厂并运行驱动。热/冷分支策略由驱动器持有；这里只绑定
    /// 身份、证据与 App 拥有的装配端口（激活、打开、载荷、端口、事件流）。
    @MainActor
    private func launchThroughSkinHost(expectedApplication: HostApplicationKey) async -> SkinLaunchResult {
        let contractVersion = SkinHostContract.version
        // 组装期只有工作区观测到的身份；codesign 在各操作分支内执行。
        let observed = HostIdentityEvidence(key: expectedApplication,
                                            signingIdentity: "workspace-observed; codesign validated per operation branch",
                                            evidenceID: "workspace-bundle-identity")
        let installObservation = CodexInstallObservation()
        let system = runtime.makeStartupTargetSystem()
        let budget = StartupBudget(startedAt: runtime.uptime)
        let hostRuntime = runtime
        let assembly = CodexSkinAssembly(
            preflightBundle: { bundle, startupBudget in
                do { try system.preflightBundle(bundle, deadline: startupBudget.preflightDeadline) }
                catch let error as WallpaperFailure where error.state == "inspection-timeout" {
                    throw StartupFailure(reason: "attach-timeout", message: "签名预检未在预算内完成。")
                } catch let error as WallpaperFailure where error.state == "signature-refused" {
                    throw StartupFailure(reason: "target-identity", message: "目标应用未通过签名核验。")
                } catch {
                    throw error
                }
            },
            activateExisting: { [weak self] facts in
                guard let self else {
                    throw StartupFailure(reason: "target-identity", message: "入口生命周期已结束。")
                }
                guard let application = self.runtime.application(processIdentifier: facts.pid), !application.isTerminated,
                      application.bundleIdentifier == facts.bundleID,
                      application.bundleURL.map({ PathCanonicalization.resolved($0) }) == facts.bundle,
                      application.executableURL.map({ PathCanonicalization.resolved($0) }) == facts.executable,
                      application.launchTime == facts.launchTime else {
                    throw StartupFailure(reason: "target-identity", message: "先前核验的进程已发生变化。")
                }
                self.session.recordTarget(application)
                let activated = application.activate()
                self.session.activated = activated
                return activated
            },
            preparePort: { [weak self] in
                guard let self else { throw StartupFailure(reason: "listener-mismatch", message: "入口生命周期已结束。") }
                return try self.session.prepareLoopbackPort(runtime: self.runtime, journal: self.journal)
            },
            openApplication: { [weak self] url, port, deadline, openSystem in
                guard let self else { throw StartupFailure(reason: "target-identity", message: "入口生命周期已结束。") }
                return try await self.boundedOpen(url: url, port: port, deadline: deadline, system: openSystem)
            },
            onTargetOpened: { [weak self] application in self?.session.recordTarget(application) },
            onCaptureReady: { [weak self] capture in self?.session.recordCapture(capture) },
            eventStream: { [weak self] in self?.session.eventStream },
            onOpeningChanged: { [weak self] value in self?.session.opening = value },
            startupFacts: { [weak self] application in
                guard let self else { throw StartupFailure(reason: "target-identity", message: "入口生命周期已结束。") }
                return try self.session.targetFacts(application)
            },
            performDisable: nil)
        let dependencies = SkinAssemblyDependencies(
            // 该入口从不通过依赖探测身份：它直接观测已核验的目标 bundle。
            // 如实上报“无独立身份探针”，不虚构观测。
            inspectIdentity: { host, _ in
                .unavailable(HostRefusal(
                    host: host, reason: .identityUnavailable, findings: [],
                    detail: "identity comes from the verified target bundle observed this launch; no standalone identity probe is wired into this entry",
                    nextProbe: nil))
            },
            capabilityEvidence: { [weak self] evidence in
                self?.capabilityFindings(for: evidence.key, contractVersion: contractVersion) ?? []
            },
            makeCodexDriver: { [weak self] inputs in
                guard let self else {
                    return PlaceholderUnavailableDriver()
                }
                return CodexSkinDriver(
                    inputs: inputs, runtime: hostRuntime,
                    readPayload: { [weak self] in
                        guard let self else { throw StartupFailure(reason: "asset-invalid", message: "入口生命周期已结束。") }
                        return try self.session.productionPayload(runtime: self.runtime)
                    },
                    makeTargetSystem: { hostRuntime.makeStartupTargetSystem() },
                    makeConnector: { facts, port, connectorSystem, capture, events in
                        StartupConnector(
                            target: facts, expectedPort: port, system: connectorSystem,
                            transport: InstallObservingStartupTransport(
                                base: hostRuntime.makeStartupTransport(capture: capture, events: events),
                                recorder: installObservation))
                    },
                    installObservation: installObservation, assembly: assembly)
            },
            makeZCodeDriver: { [weak self] inputs in
                guard let self else { return PlaceholderUnavailableDriver() }
                let stateRoot = self.commandLine.zcodeStateRoot.map { URL(fileURLWithPath: $0) }
                    ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Azhou AI Lab/ZCode")
                let bridge = ZCodeNativeRuntime(inputs: inputs, runtime: hostRuntime, readPayload: { [weak self] in
                    guard let self else { throw StartupFailure(reason: "asset-invalid", message: "入口生命周期已结束。") }
                    return try self.session.productionPayload(runtime: self.runtime)
                }, stateRoot: stateRoot, onEvent: { [weak self] fields in self?.journal.emitRuntimeDiagnostic(fields) })
                return ZCodeSkinDriver(inputs: inputs, assembly: bridge.makeAssembly())
            })
        switch SkinHostFactory.make(host: expectedApplication.host,
                                    expectedApplication: expectedApplication,
                                    observed: observed,
                                    findings: capabilityFindings(for: expectedApplication, contractVersion: contractVersion),
                                    contractVersion: contractVersion,
                                    dependencies: dependencies) {
        case .unavailable(let refusal):
            return .refused(refusal)
        case .ready(let driver):
            return await driver.launch(
                SkinLaunchRequest(expectedApplication: expectedApplication, operationID: UUID(),
                                  startedAt: budget.startedAt, deadline: budget.totalDeadline))
        }
    }

    /// 合同静态入口：测试与驱动器装配共用同一条有界打开路径。
    @MainActor
    static func openTargetApplication(
        runtime: any NativeAppRuntime, targetBundleID: String, url: URL, port: Int,
        deadline: TimeInterval, system: any StartupTargetSystem,
        log: @escaping (String, [String: Any]) -> Void
    ) async throws -> any NativeApplication {
        try await BoundedTargetOpen.run(runtime: runtime, targetBundleID: targetBundleID, url: url,
                                        port: port, deadline: deadline, system: system, log: log)
    }

    private func boundedOpen(url: URL, port: Int, deadline: TimeInterval,
                             system: any StartupTargetSystem) async throws -> any NativeApplication {
        try await Self.openTargetApplication(runtime: runtime, targetBundleID: identity.targetBundleID,
                                             url: url, port: port, deadline: deadline, system: system,
                                             log: { [weak self] event, fields in self?.journal.record(event, fields) })
    }

    /// 逐能力证据表：只在该能力确有具名验证来源时标 verified；缺证如实
    /// unverified。签名核验在 preflight/validate 分支内执行，组装期不声称。
    private func capabilityFindings(for key: HostApplicationKey, contractVersion: String) -> [CapabilityFinding] {
        if key.host == .zcode { return ZCodeNativeRuntime.findings(for: key, resources: runtime.resourceURL) }
        return codexCapabilityFindings(for: key, contractVersion: contractVersion)
    }

    private func codexCapabilityFindings(for key: HostApplicationKey,
                                         contractVersion: String) -> [CapabilityFinding] {
        let evidence: [SkinCapability: (IDs: [String], reason: String)] = [
            .applicationIdentity: (["workspace-bundle-identity", "tools/test-startup-native.py"],
                                   "identity observed this launch from the verified target bundle and workspace"),
            .activateExistingApplication: (["tools/test-startup-native.py"],
                                           "hot-branch validate→activate order and activation result checks"),
            .mainWindowAttachment: (["tools/test-startup-native.py"],
                                    "connector attach with single main-page selection and port ownership"),
            .mainPageIdentification: (["tools/test-startup-native.py", "tools/test-startup-browser.mjs"],
                                      "main-page identification against injected and real pages"),
            .ownedAppearanceSurface: (["tools/startup.test.mjs", "tools/test-startup-browser.mjs"],
                                      "appearance tokens, entry mounting and fallback placement"),
            .persistentSettings: (["tools/settings-save.unit.test.mjs", "tools/image-settings.test.mjs"],
                                  "IndexedDB save/apply two-phase transactions and namespace contract"),
            .lifecycleInvalidation: (["tools/startup.test.mjs"],
                                     "dispose generation invalidation; late callbacks cannot revive a run"),
            .ownedResourceRemoval: (["Native/WallpaperValidationTests.swift", "tools/startup.test.mjs"],
                                    "owned controller disposal via restore/retry receipts"),
        ]
        return SkinCapability.allCases.map { capability in
            let entry = evidence[capability] ?? ([], "no recorded evidence for this capability")
            return CapabilityFinding(
                subject: CapabilityEvidenceSubject(
                    application: key, surface: SkinHostContract.surface(for: capability),
                    contractVersion: contractVersion),
                capability: capability,
                state: entry.IDs.isEmpty ? .unverified : .verified,
                evidenceIDs: entry.IDs, reason: entry.reason)
        }
    }

    // MARK: 终局

    /// Codex 路径的终局：以既有 StartupOutcome 词表定局并执行终局编排。
    private func concludeStartupRun(_ outcome: StartupOutcome) {
        session.beginEventStream(writer: journal.eventWriter, at: runtime.uptime)
        guard let final = session.concludeEventStream(outcome, at: runtime.uptime) else { return }
        carryOutFinalOutcome(final, promoted: exitLedger.promoted)
    }

    /// ZCode 路径的终局（模块内可见：生命周期测试驱动真实终局/退出路径）。
    func finishZCodeStartup(_ result: SkinLaunchResult, expectedApplication: HostApplicationKey,
                            promoted: Bool) {
        session.beginEventStream(writer: journal.eventWriter, at: runtime.uptime)
        guard let final = session.eventStream?.resolveZCode(result, expectedApplication: expectedApplication,
                                                            at: runtime.uptime) else { return }
        carryOutFinalOutcome(final, promoted: promoted)
    }

    /// 终局编排：ready/skipped 尝试激活目标；失败两档按晋升与否决定可见错误
    /// 还是直接退出；成功档在晋升窗口等动画完成，否则立即退场。
    private func carryOutFinalOutcome(_ final: NativeStartupFinalOutcome, promoted: Bool) {
        exitLedger.processExitCode = final.exitCode
        switch final {
        case .activated:
            break
        case .ready:
            if let target = session.target, !target.isTerminated {
                let allowed = target.activate()
                session.activated = allowed
                journal.record("target-activation-after-startup",
                               ["allowed": allowed, "targetPID": Int(target.processIdentifier)])
            }
        case .skipped:
            if let target = session.target, !target.isTerminated { session.activated = target.activate() }
        case .partial(let reason), .behaviorNotProven(let reason):
            if promoted { presentFailure(stage.displayLocale.message(for: reason), reason) }
            else { exitLedger.terminating = true; runtime.terminate() }
            return
        }
        if promoted {
            if stage.isDone { finishHandoffIfReady("startup-ready") }
            return
        }
        exitLedger.terminating = true
        runtime.terminate()
    }

    /// 交接编排：动画完成且目标可用时淡出退场；目标在途则提示等待；激活被拒
    /// 或目标先退则按各自 reason 失败呈现。
    private func finishHandoffIfReady(_ reason: String) {
        guard stage.isDone, !isPlayerExclusive, !exitLedger.terminating, !exitLedger.failed else { return }
        if let target = session.target, target.isTerminated {
            presentFailure(stage.displayLocale.message(for: "target-exited"), "target-exited"); return
        }
        guard !session.opening, let target = session.target, !target.isTerminated else {
            stage.evaluate("window.launcherUI.waiting()", completion: nil)
            journal.record("waiting-for-target"); return
        }
        guard activateOnce(reason) else {
            presentFailure(stage.displayLocale.message(for: "activation-rejected"), "activation-rejected"); return
        }
        exitLedger.terminating = true; stage.cancelAllTimers()
        journal.record("handoff-fade-start", ["frontmost": journal.applicationRecord(runtime.frontmostApplication)])
        stage.fadeOut(duration: 0.28) {
            self.journal.record("handoff-fade-complete",
                                ["frontmost": self.journal.applicationRecord(self.runtime.frontmostApplication),
                                 "target": self.journal.applicationRecord(self.session.target)])
            self.stage.orderOut(); self.runtime.terminate()
        }
    }

    /// 目标激活只请求一次；成功后幂等返回。
    @discardableResult
    private func activateOnce(_ reason: String) -> Bool {
        if session.activated { return true }
        guard let target = session.target, !target.isTerminated else { return false }
        let result = target.activate()
        session.activated = result
        journal.record("target-activation-request",
                       ["reason": reason, "allowed": result, "target": journal.applicationRecord(target)])
        return result
    }

    /// 失败呈现：取消计时、窗口降级、failure 事件；smoke 直接失败退出；受信
    /// 启动中先挂起失败再按就绪状态选页面错误或原生对话框。
    private func presentFailure(_ message: String, _ reason: String) {
        guard !exitLedger.failed, !exitLedger.terminating else { return }
        exitLedger.failed = true
        stage.cancelAllTimers()
        stage.normalizeWindowLevel()
        journal.record("failure", ["reason": reason,
                                   "targetPID": session.target.map { Int($0.processIdentifier) } ?? 0])
        if commandLine.isSmokeTest {
            exitLedger.processExitCode = 1
            exitLedger.terminating = true; runtime.terminate(); return
        }
        if session.startupRequested { session.latchStreamFailure(reason) }
        if stage.isReady,
           let data = try? JSONSerialization.data(withJSONObject: [message]),
           let json = String(data: data, encoding: .utf8) {
            stage.makeVisible()
            stage.evaluate("window.launcherUI.error(\(json)[0])") { [weak self] _, error in
                if error != nil { self?.presentNativeDialog(message) }
            }
        } else { presentNativeDialog(message) }
    }

    private func presentNativeDialog(_ message: String) {
        stage.presentError(title: stage.displayLocale.displayName, message: message,
                           closeTitle: stage.displayLocale.closeTitle)
        exitLedger.terminating = true; runtime.terminate()
    }

    /// ZCode 运行时诊断出口：复用严格信封，不添加额外字段。
    func emitZCodeRuntimeEvent(_ fields: [String: Any]) {
        journal.emitRuntimeDiagnostic(fields)
    }

    // MARK: 应用生命周期

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        guard !exitLedger.terminating else { return false }
        if stage.isReady || exitLedger.failed { stage.makeVisible() }
        journal.record("reopen-existing-player", ["launchRequested": session.requested, "completed": stage.isDone])
        // 预览晋升：一次性窗口在渲染器就绪后可升级为受信启动。
        if isPlayerExclusive && !stage.isDone && !exitLedger.failed && !commandLine.isSmokeTest {
            exitLedger.promoted = true
            guard stage.isReady else { journal.record("preview-launch-pending"); return false }
            stage.evaluate("window.launcherUI.promoteLaunch()") { [weak self] _, error in
                guard let self else { return }
                if let error { self.presentFailure(error.localizedDescription, "preview-promotion-error"); return }
                self.journal.record("preview-promoted-to-launch"); self.beginTrustedLaunch()
            }
        }
        return false
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if isPlayerExclusive || exitLedger.failed {
            abandonPlayerWindow()
        } else {
            stage.markWindowClosed(); journal.record("window-close-as-skip"); finishHandoffIfReady("window-close")
        }
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if !exitLedger.terminating {
            if commandLine.isSmokeTest && !exitLedger.smokeResultSucceeded { exitLedger.markSmokeFailureExit() }
            if session.isStreamPending { session.latchStreamInterruption() }
            else if !isPlayerExclusive && !exitLedger.failed { activateOnce("user-quit") }
            exitLedger.terminating = true
        }
        return .terminateNow
    }

    /// 拆除序列：停计时 → smoke/常规收口事件 → 呈现层拆除 → 锁与 sink 释放 →
    /// 非零退出码显式上抛。
    func applicationWillTerminate(_ notification: Notification) {
        stage.cancelAllTimers()
        if commandLine.isSmokeTest {
            exitLedger.enforceSmokeTeardown()
            journal.recordSmoke("player-terminated",
                                ["completed": stage.isDone && exitLedger.smokeResultSucceeded && !exitLedger.failed,
                                 "failed": exitLedger.failed || !exitLedger.smokeResultSucceeded])
        } else {
            journal.record("player-terminated",
                           ["failed": exitLedger.failed, "completed": stage.isDone,
                            "frontmost": journal.applicationRecord(runtime.frontmostApplication)])
            if let final = session.finishEventStream(at: runtime.uptime) {
                exitLedger.processExitCode = final.exitCode
            }
        }
        stage.stopLoading(); stage.removeMessageHandler()
        session.releaseInstanceLock()
        journal.closeSink()
        if exitLedger.processExitCode != 0 { runtime.exit(code: exitLedger.processExitCode) }
    }

    // MARK: WebKit 导航

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        LocalWebNavigation.decide(url: action.request.url, root: stage.webRoot, completion: decisionHandler)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { presentFailure(error.localizedDescription, "navigation-error") }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { presentFailure(error.localizedDescription, "navigation-error") }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { presentFailure(stage.displayLocale.message(for: "renderer-terminated"), "renderer-terminated") }
}

/// 入口已消失时仍需返回一个可用的驱动占位（明确拒绝而非崩溃）。
@MainActor
private final class PlaceholderUnavailableDriver: SkinHostDriver {
    func launch(_ request: SkinLaunchRequest) async -> SkinLaunchResult {
        .refused(HostRefusal(host: .codex, reason: .implementationUnavailable, findings: [],
                             detail: "launcher entry deallocated", nextProbe: nil))
    }
    func inspect(_ request: SkinInspectRequest) async -> SkinInspectResult {
        .unavailable(HostRefusal(host: .codex, reason: .implementationUnavailable, findings: [],
                                 detail: "launcher entry deallocated", nextProbe: nil))
    }
    func disable(_ request: SkinDisableRequest) async -> SkinDisableResult {
        .unavailable(HostRefusal(host: .codex, reason: .implementationUnavailable, findings: [],
                                 detail: "launcher entry deallocated", nextProbe: nil))
    }
}

/// 共享宿主结果 → 既有 StartupOutcome 词表的桥接：旧消费者不会收到未识别的
/// reason；拒绝类折叠为两个既有失败身份，失败/中断保留原 reason 字符串。
func startupLegacyOutcome(from result: SkinLaunchResult) -> StartupOutcome {
    switch result {
    case .activated(let generation): return .activated(pid: generation.pid)
    case .ready(_, let runID): return .ready(runID: runID)
    case .skipped(_, let runID, let beforeReady): return .skipped(runID: runID, beforeReady: beforeReady)
    case .partial(let failure, _, _): return .partial(reason: failure.detail)
    case .failed(let failure, _, _): return .failed(reason: failure.detail)
    case .refused(let refusal):
        switch refusal.reason {
        case .identityUnavailable, .identityMismatch, .capabilityUnverified:
            return .failed(reason: "target-identity")
        case .evidenceMismatch, .implementationUnavailable, .capabilityUnsupported:
            return .failed(reason: "protocol-error")
        }
    }
}

#if !AGENT_SKIN_NATIVE_EVENT_TESTS
@main
struct AzhouStartupMain {
    static func main() {
        if WallpaperCLI.handles(CommandLine.arguments) {
            // 该模式不创建 NSApplication、播放器窗口或启动请求。
            exit(WallpaperCLI.run(CommandLine.arguments))
        }
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        // NSApplication.delegate 是弱引用；以显式存活期覆盖整个运行循环，
        // 优化构建下也不丢委托。
        withExtendedLifetime(delegate) { app.run() }
    }
}
#endif
