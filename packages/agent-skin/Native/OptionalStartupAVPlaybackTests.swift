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
        try require(policy.start(.init(timeout: 8), attempt: key, now: now) == [.startMedia(key)],
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
