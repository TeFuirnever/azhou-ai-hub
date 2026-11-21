import AVFoundation
import CryptoKit
import Foundation

/// The caller supplies a private, exclusive, run-owned file made from the exact bytes
/// received by the stage port. It retains the lease until its player has detached.
@MainActor
protocol StartupVideoTemporaryClip: AnyObject {
    var fileURL: URL { get }
    func release()
}

@MainActor
enum OptionalStartupVideoResolver {
    enum Resource: Sendable { case manifest, clip }

    struct Pins {
        let manifestSHA256: String
        let clipSHA256: String
    }

    struct Timeline: Decodable {
        let schema: Int
        let clipSHA256: String
        let byteLength: Int
        let holdMs: Int
        let fadeStartMs: Int
        let fadeEndMs: Int
    }

    struct Prepared {
        let item: AVPlayerItem
        let timeline: Timeline
        let temporaryClip: any StartupVideoTemporaryClip
    }

    enum Rejection: Error, Equatable {
        case invalidManifest, invalidClip, invalidSnapshot, unplayable, durationTooShort, deadline
    }

    private static let maxManifestBytes = 4096
    private static let maxClipBytes = 64 * 1024 * 1024
    // Leave a nonzero media-clock window after the visual endpoint. This is not
    // a promise that periodic callbacks are delivered or frames are presented.
    private static let minimumPostFadeMs = 125

    /// Bounded file I/O is injected so the caller can reuse the native no-follow reader
    /// off the main actor. The existing launch owner must cancel a stalled inspection;
    /// the guards below also prevent a late completion from admitting a player item.
    static func prepare(
        coldVideoAllowed: Bool, pins: Pins?, deadline: TimeInterval,
        playbackDeadline: TimeInterval? = nil, now: () -> TimeInterval,
        read: (Resource, Int) async throws -> Data,
        stage: (Data) async throws -> any StartupVideoTemporaryClip,
        inspect: @MainActor (AVURLAsset) async throws -> CMTime = { asset in
            try await OptionalStartupVideoResolver.playableDuration(asset)
        }
    ) async throws -> Prepared? {
        guard coldVideoAllowed, let pins else { return nil }
        try requireTime(deadline, now())
        let manifest = try await read(.manifest, maxManifestBytes)
        let timeline = try validate(manifest, pins: pins)
        try requireTime(deadline, now())
        try requirePlaybackTime(playbackDeadline, timeline: timeline, now: now())
        let clip = try await read(.clip, timeline.byteLength)
        guard clip.count == timeline.byteLength else { throw Rejection.invalidClip }
        let digest = await Task.detached(priority: .utility) { sha256(clip) }.value
        guard digest == pins.clipSHA256 else { throw Rejection.invalidClip }
        try requireTime(deadline, now())
        try requirePlaybackTime(playbackDeadline, timeline: timeline, now: now())
        let lease = try await stage(clip)
        let pending = PendingClip(lease)
        defer { pending.abandon() }
        try requireTime(deadline, now())
        let url = lease.fileURL
        guard url.isFileURL, (url.host ?? "").isEmpty, url.query == nil, url.fragment == nil else {
            throw Rejection.invalidSnapshot
        }
        let asset = AVURLAsset(url: url, options: [
            AVURLAssetPreferPreciseDurationAndTimingKey: true,
            AVURLAssetReferenceRestrictionsKey: NSNumber(value: AVAssetReferenceRestrictions.forbidAll.rawValue),
        ])
        pending.asset = asset
        let duration = try await withTaskCancellationHandler {
            try await inspect(asset)
        } onCancel: {
            Task { @MainActor in pending.abandon() }
        }
        try requireTime(deadline, now())
        try requirePlaybackTime(playbackDeadline, timeline: timeline, now: now())
        let requiredEnd = CMTime(value: Int64(timeline.fadeEndMs + minimumPostFadeMs), timescale: 1000)
        guard duration.seconds.isFinite, CMTimeCompare(duration, requiredEnd) >= 0 else {
            throw Rejection.durationTooShort
        }
        pending.transfer()
        return Prepared(item: AVPlayerItem(asset: asset), timeline: timeline, temporaryClip: lease)
    }

    private static func validate(_ bytes: Data, pins: Pins) throws -> Timeline {
        let keys: Set<String> = ["schema", "clipSHA256", "byteLength", "holdMs", "fadeStartMs", "fadeEndMs"]
        guard !bytes.isEmpty, bytes.count <= maxManifestBytes, sha256(bytes) == pins.manifestSHA256,
              let object = (try? JSONSerialization.jsonObject(with: bytes)) as? [String: Any],
              Set(object.keys) == keys,
              let stored = try? JSONDecoder().decode(Timeline.self, from: bytes),
              stored.schema == 1, stored.clipSHA256 == pins.clipSHA256,
              (1...maxClipBytes).contains(stored.byteLength),
              0 < stored.holdMs, stored.holdMs < stored.fadeStartMs,
              stored.fadeStartMs < stored.fadeEndMs, stored.fadeEndMs <= 60_000 else {
            throw Rejection.invalidManifest
        }
        return stored
    }

    private static func requirePlaybackTime(_ deadline: TimeInterval?, timeline: Timeline, now: TimeInterval) throws {
        guard let deadline else { return }
        guard deadline.isFinite, now.isFinite, deadline > now + Double(timeline.fadeEndMs) / 1000 else {
            throw Rejection.deadline
        }
    }

    private static func requireTime(_ deadline: TimeInterval, _ now: TimeInterval) throws {
        try Task.checkCancellation()
        guard deadline.isFinite, now.isFinite, now < deadline else { throw Rejection.deadline }
    }

    private static func playableDuration(_ asset: AVURLAsset) async throws -> CMTime {
        let (isPlayable, duration) = try await asset.load(.isPlayable, .duration)
        guard isPlayable else { throw Rejection.unplayable }
        let tracks = try await asset.loadTracks(withMediaType: .video)
        guard tracks.count == 1, let track = tracks.first else { throw Rejection.unplayable }
        let (enabled, range, formats) = try await track.load(.isEnabled, .timeRange, .formatDescriptions)
        let trackEnd = CMTimeRangeGetEnd(range)
        guard enabled, !formats.isEmpty,
              formats.allSatisfy({ CMFormatDescriptionGetMediaSubType($0) == kCMVideoCodecType_H264 }),
              range.start.seconds.isFinite, CMTimeCompare(range.start, .zero) <= 0,
              trackEnd.seconds.isFinite, duration.seconds.isFinite else {
            throw Rejection.unplayable
        }
        // A longer audio track must not conceal a video stream that ends early.
        return CMTimeCompare(trackEnd, duration) < 0 ? trackEnd : duration
    }

    nonisolated private static func sha256(_ bytes: Data) -> String {
        SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    }
}

@MainActor
private final class PendingClip {
    private var lease: (any StartupVideoTemporaryClip)?
    var asset: AVURLAsset?

    init(_ lease: any StartupVideoTemporaryClip) { self.lease = lease }

    func transfer() { lease = nil }

    func abandon() {
        guard let lease else { return }
        self.lease = nil
        asset?.cancelLoading()
        lease.release()
    }
}
