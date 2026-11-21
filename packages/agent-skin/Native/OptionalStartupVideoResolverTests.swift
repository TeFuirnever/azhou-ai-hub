import AVFoundation
import CryptoKit
import Foundation

@MainActor
private final class FixtureLease: StartupVideoTemporaryClip {
    let fileURL: URL
    private(set) var releases = 0

    init(_ url: URL = URL(fileURLWithPath: "/synthetic-optional-startup/clip.mp4")) {
        fileURL = url
    }
    func release() { releases += 1 }
}

@MainActor
private final class PausedInspection {
    var continuation: CheckedContinuation<CMTime, Never>?
    func wait() async -> CMTime {
        await withCheckedContinuation { continuation = $0 }
    }
    func finish() {
        let handle = continuation
        continuation = nil
        handle?.resume(returning: CMTime(value: 675, timescale: 1000))
    }
}

struct OptionalStartupVideoResolverTests {
    @MainActor
    static func run() async throws {
        let clip = Data("synthetic bytes; not a codec fixture".utf8)
        func digest(_ bytes: Data) -> String {
            SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
        }
        let encoded = try JSONSerialization.data(withJSONObject: [
            "schema": 1, "clipSHA256": digest(clip), "byteLength": clip.count,
            "holdMs": 300, "fadeStartMs": 400, "fadeEndMs": 550,
        ], options: [.sortedKeys])
        let pins = OptionalStartupVideoResolver.Pins(manifestSHA256: digest(encoded), clipSHA256: digest(clip))
        let neverRead: (OptionalStartupVideoResolver.Resource, Int) async throws -> Data = { _, _ in
            preconditionFailure("an inactive launch must not read media")
        }
        let neverStage: (Data) async throws -> any StartupVideoTemporaryClip = { _ in
            preconditionFailure("an inactive or unverified launch must not stage media")
        }
        for (cold, optional) in [(false, Optional(pins)), (true, nil)] {
            let result = try await OptionalStartupVideoResolver.prepare(
                coldVideoAllowed: cold, pins: optional, deadline: 2, now: { 1 },
                read: neverRead, stage: neverStage
            )
            precondition(result == nil)
        }
        func read(_ kind: OptionalStartupVideoResolver.Resource, _ limit: Int) async throws -> Data {
            switch kind {
            case .manifest:
                precondition(limit == 4096)
                return encoded
            case .clip:
                precondition(limit == clip.count)
                return clip
            }
        }
        for deadline in [1.55, .infinity] {
            do {
                _ = try await OptionalStartupVideoResolver.prepare(coldVideoAllowed: true, pins: pins,
                    deadline: 2, playbackDeadline: deadline, now: { 1 }, read: { kind, cap in
                        if case .clip = kind { preconditionFailure("insufficient playback budget read clip") }
                        return try await read(kind, cap)
                    }, stage: neverStage)
                preconditionFailure("insufficient playback budget admitted")
            } catch OptionalStartupVideoResolver.Rejection.deadline {}
        }
        do {
            _ = try await OptionalStartupVideoResolver.prepare(coldVideoAllowed: true, pins: pins,
                deadline: 2, now: { 1 }, read: { kind, cap in
                    if case .clip = kind { return Data(repeating: 0, count: clip.count) }
                    return try await read(kind, cap)
                }, stage: neverStage)
            preconditionFailure("wrong clip hash admitted")
        } catch OptionalStartupVideoResolver.Rejection.invalidClip {}
        for earlyEnd in [550, 674] {
            let short = FixtureLease()
            do {
                _ = try await OptionalStartupVideoResolver.prepare(coldVideoAllowed: true, pins: pins,
                    deadline: 2, now: { 1 }, read: read, stage: { bytes in
                        precondition(bytes == clip); return short
                    }, inspect: { _ in CMTime(value: Int64(earlyEnd), timescale: 1000) })
                preconditionFailure("a clip without the required post-fade media tail admitted")
            } catch OptionalStartupVideoResolver.Rejection.durationTooShort {}
            precondition(short.releases == 1)
        }

        let equal = FixtureLease()
        let prepared = try await OptionalStartupVideoResolver.prepare(coldVideoAllowed: true, pins: pins,
            deadline: 2, now: { 1 }, read: read, stage: { bytes in
                precondition(bytes == clip); return equal
            }, inspect: { asset in
                precondition(asset.url == equal.fileURL)
                return CMTime(value: 27, timescale: 40)
            })
        precondition(prepared?.timeline.fadeEndMs == 550 && equal.releases == 0)
        prepared?.temporaryClip.release()
        precondition(equal.releases == 1)

        let late = FixtureLease()
        var time = 1.0
        do {
            _ = try await OptionalStartupVideoResolver.prepare(coldVideoAllowed: true, pins: pins,
                deadline: 2, now: { time }, read: read, stage: { _ in late },
                inspect: { _ in time = 2; return CMTime(value: 2, timescale: 1) })
            preconditionFailure("result returned at expired deadline")
        } catch OptionalStartupVideoResolver.Rejection.deadline {}
        precondition(late.releases == 1)

        let stalled = FixtureLease()
        let probe = PausedInspection()
        let task = Task<Void, Error> { @MainActor in
            _ = try await OptionalStartupVideoResolver.prepare(coldVideoAllowed: true, pins: pins,
                deadline: 2, now: { 1 }, read: read, stage: { _ in stalled },
                inspect: { _ in await probe.wait() })
        }
        for _ in 0..<20 where probe.continuation == nil { try await Task.sleep(nanoseconds: 5_000_000) }
        precondition(probe.continuation != nil)
        task.cancel()
        for _ in 0..<20 where stalled.releases == 0 { try await Task.sleep(nanoseconds: 5_000_000) }
        precondition(stalled.releases == 1, "cleanup must not wait for a stalled inspection to return")
        probe.finish()
        do {
            try await task.value
            preconditionFailure("cancelled inspection admitted a late item")
        } catch is CancellationError {}
        precondition(stalled.releases == 1)
        print("Optional startup video resolver contract passed with fake bundle and probe")
    }
}
