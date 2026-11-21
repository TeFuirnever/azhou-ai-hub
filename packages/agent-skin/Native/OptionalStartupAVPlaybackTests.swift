import AVFoundation
import Foundation
import QuartzCore

@MainActor
struct OptionalStartupAVPlaybackTests {
    private struct CheckFailure: LocalizedError {
        let detail: String
        var errorDescription: String? { detail }
    }

    private static func require(_ value: Bool, _ description: String) throws {
        guard value else { throw CheckFailure(detail: description) }
    }

    private static func wait(deadline: TimeInterval = ProcessInfo.processInfo.systemUptime + 3,
                             until ready: () -> Bool) async -> Bool {
        while !ready(), ProcessInfo.processInfo.systemUptime < deadline {
            try? await Task.sleep(nanoseconds: 10_000_000)
        }
        return ready()
    }

    private static func makeMedia(_ url: URL) async throws {
        let writer = try AVAssetWriter(outputURL: url, fileType: .mov)
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.jpeg, AVVideoWidthKey: 160, AVVideoHeightKey: 90,
        ])
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input,
            sourcePixelBufferAttributes: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
                                          kCVPixelBufferWidthKey as String: 160, kCVPixelBufferHeightKey as String: 90])
        try require(writer.canAdd(input), "writer accepts synthetic input")
        writer.add(input)
        try require(writer.startWriting(), "synthetic writer starts")
        defer { if writer.status == .writing { writer.cancelWriting() } }
        writer.startSession(atSourceTime: .zero)
        let deadline = ProcessInfo.processInfo.systemUptime + 5
        for index in 0..<54 {
            let ready = await wait(deadline: deadline) { input.isReadyForMoreMediaData || writer.status != .writing }
            try require(ready && writer.status == .writing, "synthetic writer input ready")
            var buffer: CVPixelBuffer?
            try require(CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &buffer) == kCVReturnSuccess,
                    "synthetic buffer allocated")
            let pixel = buffer!
            try require(CVPixelBufferLockBaseAddress(pixel, []) == kCVReturnSuccess, "synthetic buffer locked")
            let base = CVPixelBufferGetBaseAddress(pixel)!.assumingMemoryBound(to: UInt8.self)
            let stride = CVPixelBufferGetBytesPerRow(pixel)
            for y in 0..<90 {
                for x in 0..<160 {
                    let offset = y * stride + x * 4
                    base[offset] = UInt8(50 + index)
                    base[offset + 1] = UInt8(150 + x % 30)
                    base[offset + 2] = UInt8(120 + y % 40)
                    base[offset + 3] = 255
                }
            }
            CVPixelBufferUnlockBaseAddress(pixel, [])
            try require(adaptor.append(pixel, withPresentationTime: CMTime(value: Int64(index), timescale: 24)),
                    "synthetic frame appended")
        }
        input.markAsFinished()
        writer.finishWriting(completionHandler: {})
        let finished = await wait(deadline: deadline) { writer.status != .writing }
        try require(finished && writer.status == .completed, "synthetic media encoded")
    }

    static func run() async throws {
        await lifetimeChecks()
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(
            "agent-skin-generated-media-" + UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
        defer { try? FileManager.default.removeItem(at: directory) }
        let url = directory.appendingPathComponent("fixture.mov")
        try await makeMedia(url)
        let layer = CALayer()
        let frame = CGRect(x: 0, y: 0, width: 160, height: 90)
        layer.frame = frame
        let center = NotificationCenter()
        let key = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let item = AVPlayerItem(url: url)
        var signals: [OptionalStartupAVPlayback.Signal] = []
        var policy = OptionalStartupMedia()
        let now = ProcessInfo.processInfo.systemUptime
        try require(policy.start(.init(timeout: 8, holdAt: 0.8, fadeStart: 1.4, fadeEnd: 1.9), attempt: key, now: now) == [.startMedia(key)],
                "adapter owner starts exact policy generation")
        var revealed = false
        var mismatchedSignal = false
        var advanced: [TimeInterval] = []
        let adapter = OptionalStartupAVPlayback(attempt: key, item: item, notifications: center) { attempt, signal in
            if attempt != key { mismatchedSignal = true }
            signals.append(signal)
            if signal == .firstFrame {
                let effects = policy.receive(.firstFrame(item: attempt.item), generation: attempt.generation,
                                             now: ProcessInfo.processInfo.systemUptime, hostReadyNow: false)
                revealed = effects == [.revealVideo]
            }
            if case .mediaTime(let time) = signal { advanced.append(time) }
        }
        defer { adapter.release() }
        try require(adapter.prepare(in: layer, frame: frame), "old layer prepared")
        try require(adapter.lifetime.paused && adapter.lifetime.muted, "prepare stays paused and muted")
        adapter.play()
        let ready = await wait { revealed && (advanced.last ?? 0) >= 0.25 }
        try require(ready, "actual AVPlayerLayer first frame and decoded clock progression")
        adapter.pause()
        let sample1 = advanced.last ?? -1
        try? await Task.sleep(nanoseconds: 230_000_000)
        let sample2 = advanced.last ?? -1
        try require(adapter.lifetime.paused && abs(sample2 - sample1) < 0.12, "actual clock stays bounded while paused")
        adapter.play()
        let resumed = await wait { (advanced.last ?? 0) - sample2 >= 0.18 }
        try require(resumed, "actual clock resumes")
        try require(signals.filter { $0 == .firstFrame }.count == 1, "first frame once")
        print(String(format: "Synthetic first frame once; media clock pause %.4f → %.4f, resumed %.4f",
                     sample1, sample2, advanced.last ?? -1))

        let count = signals.count
        center.post(name: AVPlayerItem.didPlayToEndTimeNotification, object: item)
        center.post(name: AVPlayerItem.failedToPlayToEndTimeNotification, object: item)
        adapter.release()
        let nextKey = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let nextItem = AVPlayerItem(url: url)
        var newSignals: [OptionalStartupAVPlayback.Signal] = []
        let next = OptionalStartupAVPlayback(attempt: nextKey, item: nextItem, notifications: center) { attempt, signal in
            if attempt != nextKey { mismatchedSignal = true }
            newSignals.append(signal)
        }
        defer { next.release() }
        try require(next.prepare(in: layer, frame: frame), "new layer mounted before stale actor hops")
        // Also post the old item while the new observer is live. A global
        // observer would wrongly turn this into the new attempt's ending.
        center.post(name: AVPlayerItem.didPlayToEndTimeNotification, object: item)
        center.post(name: AVPlayerItem.failedToPlayToEndTimeNotification, object: item)
        try? await Task.sleep(nanoseconds: 150_000_000)
        try require(signals.count == count, "old queued end/failure do not dispatch after release")
        try require(!newSignals.contains(.ended) && !newSignals.contains(.failed), "old queued end/failure do not route to new item")
        try require(next.lifetime.mounted && next.lifetime.hasCurrentItem && layer.sublayers?.count == 1,
                "only new layer remains mounted")
        center.post(name: AVPlayerItem.didPlayToEndTimeNotification, object: nextItem)
        let ended = await wait { newSignals.contains(.ended) }
        try require(!mismatchedSignal && ended && newSignals.filter { $0 == .ended }.count == 1 && !newSignals.contains(.failed),
                "new matching item still delivers its own end exactly once")
        next.release()
        try require(layer.sublayers?.isEmpty != false && next.lifetime.observationCount == 0 &&
                !next.lifetime.hasCurrentItem && next.lifetime.paused, "terminal release cleans owned resources")
        print("Synthetic AVFoundation positive clock plus queued end/failure item-isolation passed")
        try await stitched(url: url, frame: frame)
    }

    private static func stitched(url: URL, frame: CGRect) async throws {
        typealias Presentation = OptionalStartupPresentation
        let key = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let cfg = OptionalStartupMedia.Configuration(timeout: 4, holdAt: 0.35, fadeStart: 0.72, fadeEnd: 1.07)!
        let container = CALayer()
        let monotonic = { ProcessInfo.processInfo.systemUptime }
        var selectedPage = UUID()
        var proof: (page: UUID, attempt: OptionalStartupMedia.Attempt)?
        var output: [Presentation.Output] = []
        var builds = 0
        var probes = 0
        func makeItem() -> AVPlayerItem {
            builds += 1
            return AVPlayerItem(url: url)
        }
        let ended: () -> Bool = { output.contains(.ended(.completed)) }
        func workspace(_ configuredAttempt: OptionalStartupMedia.Attempt) -> Bool {
            probes += 1
            return proof?.page == selectedPage && proof?.attempt == configuredAttempt
        }
        let presentation = Presentation(attempt: key, now: monotonic, workspaceReadyNow: workspace) { output.append($0) }
        presentation.start(nil, in: container, frame: frame, makeItem: makeItem)
        presentation.tick()
        presentation.coverFadeCommitted()
        try require(builds == 0 && probes == 0 && output.isEmpty && container.sublayers?.isEmpty != false,
                    "unconfigured strategy is entirely inert")
        presentation.start(cfg, in: container, frame: frame, makeItem: makeItem)
        guard let video = container.sublayers?.first as? AVPlayerLayer, let player = video.player else {
            throw CheckFailure(detail: "stitched run mounts one actual player")
        }
        let held = await wait { output.contains(.revealVideo) && player.currentTime().seconds >= 0.35 && player.rate == 0 }
        try require(held, "stitched run reveals on actual first frame and pauses at media hold without workspace")
        let heldAt = player.currentTime().seconds
        let previousPage = selectedPage
        selectedPage = UUID()
        proof = (previousPage, key)
        presentation.workspaceReadinessChanged()
        try? await Task.sleep(nanoseconds: 120_000_000)
        try require(player.rate == 0 && abs(player.currentTime().seconds - heldAt) < 0.05 &&
                    !output.contains(.beginHandoff), "stale swapped page proof cannot resume or fade")
        proof = (selectedPage, key)
        presentation.workspaceReadinessChanged()
        let reachedEnd = await wait { output.contains(.coverOpacity(0)) }
        let samples = output.compactMap { value -> Double? in
            guard case .coverOpacity(let alpha) = value else { return nil }
            return alpha
        }
        try require(reachedEnd && player.currentTime().seconds >= 1.07 &&
                    output.filter { $0 == .beginHandoff }.count == 1 && samples.last == 0 &&
                    samples.contains(where: { $0 > 0 && $0 < 1 }) &&
                    zip(samples, samples.dropFirst()).allSatisfy { $0 >= $1 } && !ended() && builds == 1,
                    "current proof resumes once and actual media time fades monotonically to exact zero before owner commit")
        presentation.coverFadeCommitted()
        try require(ended() && container.sublayers?.isEmpty != false && player.currentItem == nil,
                    "current owner completion releases adapter exactly once")
        presentation.skip()
        presentation.coverFadeCommitted()
        try require(output.filter { $0 == .ended(.completed) }.count == 1,
                    "late skip/cover completions are inert")

        let revokedKey = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        proof = (selectedPage, revokedKey)
        output = []
        var restoredWhileOwned = false
        let fading = Presentation(attempt: revokedKey, now: monotonic, workspaceReadyNow: workspace) {
            if $0 == .restoreOpaqueCover { restoredWhileOwned = container.sublayers?.count == 1 }
            output.append($0)
        }
        fading.start(cfg, in: container, frame: frame, makeItem: makeItem)
        let began = await wait { output.contains(.beginHandoff) }
        try require(began, "green fixture reaches fade before proof is revoked")
        proof = nil
        fading.workspaceReadinessChanged()
        try require(output.suffix(2).elementsEqual([.restoreOpaqueCover, .ended(.staticFallback)]) &&
                    restoredWhileOwned && container.sublayers?.isEmpty != false,
                    "revocation restores opaque cover before releasing playback; never restarts Canvas")
        fading.workspaceReadinessChanged()
        try require(output.filter { $0 == .ended(.staticFallback) }.count == 1,
                    "revoked run cannot emit again")

        output = []
        let skipKey = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let skipping = Presentation(attempt: skipKey, now: monotonic, workspaceReadyNow: workspace) { output.append($0) }
        skipping.start(cfg, in: container, frame: frame, makeItem: makeItem)
        skipping.skip()
        proof = (selectedPage, key)
        skipping.workspaceReadinessChanged()
        try? await Task.sleep(nanoseconds: 100_000_000)
        try require(output == [.ended(.skipped)] && container.sublayers?.isEmpty != false && builds == 3,
                    "skip before first frame detaches once and stale readiness cannot replay")
        output = []
        let badKey = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let missing = Presentation(attempt: badKey, now: monotonic, workspaceReadyNow: workspace) { output.append($0) }
        missing.start(cfg, in: container, frame: frame) { throw CheckFailure(detail: "missing synthetic fixture") }
        try require(output == [.restoreOpaqueCover, .ended(.defaultFallback)] &&
                    container.sublayers?.isEmpty != false, "pre-frame failure leaves own cover and permits default fallback only")
        output = []
        var clock: TimeInterval = 0
        var mountedAtFallback = false
        let lateKey = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let lateFactory = Presentation(attempt: lateKey, now: { clock }, workspaceReadyNow: workspace) {
            if $0 == .restoreOpaqueCover { mountedAtFallback = container.sublayers?.isEmpty == false }
            output.append($0)
        }
        lateFactory.start(cfg, in: container, frame: frame) {
            clock = 4
            return AVPlayerItem(asset: AVMutableComposition())
        }
        try require(output == [.restoreOpaqueCover, .ended(.defaultFallback)] && !mountedAtFallback &&
                    container.sublayers?.isEmpty != false, "factory expired before mount never starts and falls back once")

        output = []
        var preparedWhilePaused = false
        let lateMountKey = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let lateMount = Presentation(attempt: lateMountKey, now: {
            container.sublayers?.isEmpty == false ? 4 : 0
        }, workspaceReadyNow: workspace) {
            if $0 == .restoreOpaqueCover, let mounted = container.sublayers?.first as? AVPlayerLayer {
                preparedWhilePaused = mounted.player?.rate == 0
            }
            output.append($0)
        }
        lateMount.start(cfg, in: container, frame: frame) { AVPlayerItem(url: url) }
        try? await Task.sleep(nanoseconds: 100_000_000)
        lateMount.workspaceReadinessChanged()
        try require(preparedWhilePaused && output == [.restoreOpaqueCover, .ended(.defaultFallback)] &&
                    container.sublayers?.isEmpty != false, "mount expired before play releases paused resources and ignores callbacks")

        output = []
        let reentrantKey = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let narrowFade = OptionalStartupMedia.Configuration(timeout: 4, holdAt: 0.1,
                                                            fadeStart: 0.41, fadeEnd: 0.4100000001)!
        proof = (selectedPage, reentrantKey)
        weak var reentrant: Presentation?
        let reentrantOwner = Presentation(attempt: reentrantKey, now: monotonic, workspaceReadyNow: workspace) {
            output.append($0)
            if $0 == .beginHandoff { reentrant?.coverFadeCommitted() }
        }
        reentrant = reentrantOwner
        reentrantOwner.start(narrowFade, in: container, frame: frame) { AVPlayerItem(url: url) }
        let zeroSeen = await wait { output.contains(.coverOpacity(0)) || output.contains(.ended(.completed)) }
        try require(zeroSeen && output.contains(.coverOpacity(0)) && !output.contains(.ended(.completed)),
                    "reentrant owner cannot acknowledge handoff before zero opacity is emitted")
        reentrantOwner.coverFadeCommitted()
        try require(output.last == .ended(.completed) && container.sublayers?.isEmpty != false,
                    "owner can acknowledge zero opacity once it has been emitted")
        print(String(format: "Stitched actual media: held %.4fs; fade samples %d, endpoint %.1f; revoked-fade continuity and skip passed",
                     heldAt, samples.count, samples.last ?? -1))
    }

    private static func lifetimeChecks() async {
        let attempt = OptionalStartupMedia.Attempt(generation: UUID(), item: UUID())
        let center = NotificationCenter()
        let item = AVPlayerItem(asset: AVMutableComposition())
        let parent = CALayer()
        var observed: [OptionalStartupAVPlayback.Signal] = []
        let playback = OptionalStartupAVPlayback(attempt: attempt, item: item, notifications: center) { ownAttempt, signal in
            precondition(ownAttempt.generation == attempt.generation && ownAttempt.item == attempt.item)
            observed.append(signal)
        }
        precondition(playback.lifetime.observationCount == 0)
        precondition(playback.lifetime.muted && playback.lifetime.paused)
        precondition(!playback.prepare(in: parent, frame: .zero) && parent.sublayers?.isEmpty != false)
        let frame = CGRect(x: 20, y: 10, width: 160, height: 90)
        precondition(playback.prepare(in: parent, frame: frame))
        precondition(playback.lifetime.observationCount == 6)
        precondition(playback.lifetime.hasCurrentItem && playback.lifetime.mounted)
        precondition(playback.lifetime.muted && playback.lifetime.paused)
        precondition(parent.sublayers?.first?.frame == frame)
        precondition(!playback.prepare(in: parent, frame: frame))

        // Drive the exact owned notification before release while its actor task
        // is queued. After release, neither that callback nor new ones may emit.
        center.post(name: AVPlayerItem.failedToPlayToEndTimeNotification, object: item)
        playback.release()
        playback.release()
        center.post(name: AVPlayerItem.didPlayToEndTimeNotification, object: item)
        playback.play()
        playback.pause()
        for _ in 0..<8 { await Task.yield() }

        precondition(playback.lifetime.observationCount == 0)
        precondition(!playback.lifetime.hasCurrentItem && !playback.lifetime.mounted)
        precondition(playback.lifetime.paused && observed.isEmpty)
        precondition(parent.sublayers?.isEmpty != false && !playback.prepare(in: parent, frame: frame))
        // Even abandoning an adapter cannot leave an independently retained layer.
        var abandoned: OptionalStartupAVPlayback? = OptionalStartupAVPlayback(
            attempt: attempt, item: AVPlayerItem(asset: AVMutableComposition()), notifications: center
        ) { _, _ in preconditionFailure("abandoned instance emitted a queued signal") }
        precondition(abandoned?.prepare(in: parent, frame: frame) == true)
        precondition(parent.sublayers?.count == 1)
        abandoned = nil
        for _ in 0..<20 where parent.sublayers?.isEmpty == false {
            try? await Task.sleep(nanoseconds: 5_000_000)
        }
        precondition(parent.sublayers?.isEmpty != false)
        print("Optional AVFoundation adapter lifetime checks passed")
    }
}
