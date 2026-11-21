import Foundation

struct OptionalStartupMediaTests {
    static func run() {
        typealias Policy = OptionalStartupMedia
        let key = Policy.Attempt(generation: UUID(), item: UUID())
        let wrong = UUID()
        let configured = Policy.Configuration(timeout: 18, holdAt: 11.3, fadeStart: 12.7, fadeEnd: 13.65)!
        func expect(_ condition: Bool, _ name: String) {
            guard condition else { print("FAIL " + name); exit(1) }
            print("PASS " + name)
        }

        var policy = Policy()
        func send(_ event: Policy.Event, _ now: TimeInterval, host: Bool = false,
                  generation: UUID? = nil) -> [Policy.Effect] {
            policy.receive(event, generation: generation ?? key.generation, now: now, hostReadyNow: host)
        }
        func media(_ seconds: TimeInterval, _ now: TimeInterval, host: Bool = false,
                   item: UUID? = nil, generation: UUID? = nil) -> [Policy.Effect] {
            send(.mediaTime(item: item ?? key.item, seconds: seconds), now, host: host, generation: generation)
        }
        func active() {
            policy = Policy()
            expect(policy.start(configured, attempt: key, now: 0) == [.startMedia(key)], "configured attempt starts once")
        }
        func config(timeout: TimeInterval = 18, hold: TimeInterval = 11.3, fade: TimeInterval = 12.7,
                    end: TimeInterval = 13.65) -> Policy.Configuration? {
            .init(timeout: timeout, holdAt: hold, fadeStart: fade, fadeEnd: end)
        }
        func opacity(_ fixed: Double, in effects: [Policy.Effect]) -> Bool {
            guard effects.count == 1, case .setCoverOpacity(let value) = effects[0] else { return false }
            return abs(value - fixed) < 1e-9
        }

        expect(config(timeout: .infinity) == nil && config(timeout: .nan) == nil && config(timeout: 61) == nil &&
               config(timeout: 13.65) == nil && config(hold: 0) == nil && config(hold: .nan) == nil &&
               config(hold: 12.7) == nil && config(fade: .infinity) == nil && config(fade: 13.65) == nil &&
               config(end: .nan) == nil, "ordered finite milestones fit original deadline")
        expect(policy.start(nil, attempt: key, now: 0).isEmpty &&
               send(.hostReadinessChanged, 1, host: true).isEmpty, "no configuration has no side effects")
        expect(policy.start(configured, attempt: key, now: .nan).isEmpty &&
               policy.start(configured, attempt: key, now: -.infinity).isEmpty &&
               policy.start(configured, attempt: key, now: -1).isEmpty &&
               policy.start(configured, attempt: key, now: .greatestFiniteMagnitude).isEmpty,
               "invalid or nonrepresentable wall clock cannot start")

        active()
        expect(policy.start(configured, attempt: key, now: 1).isEmpty, "duplicate start ignored")
        expect(send(.firstFrame(item: wrong), 99, host: true).isEmpty &&
               send(.firstFrame(item: key.item), 99, host: true, generation: wrong).isEmpty &&
               media(13.65, 99, host: true).isEmpty &&
               send(.handoffFinished, 99, host: true).isEmpty,
               "wrong signals and pre-frame media clock cannot consume deadline")
        expect(send(.hostReadinessChanged, 0.1, host: true).isEmpty &&
               send(.firstFrame(item: key.item), 0.2, host: true) == [.revealVideo],
               "first frame plus host proof reveals but cannot begin fade without media clock")
        expect(send(.firstFrame(item: key.item), 0.3, host: true).isEmpty &&
               send(.hostReadinessChanged, 0.1, host: true).isEmpty,
               "duplicate frame and backward wall clock do not drive presentation")
        expect(media(11.3, 1, host: true).isEmpty && media(12.69, 2, host: true).isEmpty &&
               send(.tick, 10, host: true).isEmpty, "early host ready plays through hold, wall ticks do not fade")
        expect(media(12.7, 11, host: true) == [.beginHandoff, .setCoverOpacity(1)], "fade starts at true media threshold")
        expect(send(.handoffFinished, 99, host: true).isEmpty, "premature completion cannot consume deadline")
        expect(opacity(0.84375, in: media(12.9375, 11.1, host: true)) &&
               opacity(0.5, in: media(13.175, 11.2, host: true)) &&
               opacity(0.15625, in: media(13.4125, 11.3, host: true)),
               "smoothstep fade has independent quarter/midpoint/three-quarter values")
        expect(media(13.65, 11.4, host: true) == [.setCoverOpacity(0)] &&
               media(13.7, 11.45, host: true).isEmpty, "fade ends at zero without repeated alpha effects")
        expect(send(.handoffFinished, 11.5, host: true) == [.release] &&
               send(.skip, 11.6).isEmpty, "only completed fade releases and late skip is inert")

        active()
        expect(send(.hostReadinessChanged, 0.05, host: true).isEmpty &&
               send(.firstFrame(item: key.item), 0.1) == [.revealVideo],
               "host proof is not latched across first frame")
        expect(media(11.29, 1).isEmpty && media(11.3, 1.1) == [.pauseVideo], "crossing hold without current proof pauses once")
        expect(media(11.31, 1.2).isEmpty && send(.tick, 3).isEmpty &&
               media(11.31, 99, host: true).isEmpty, "held duplicate samples cannot advance or consume budget")
        expect(send(.hostReadinessChanged, 3.1, host: true) == [.resumeVideo] &&
               send(.hostReadinessChanged, 3.2, host: true).isEmpty,
               "current proof only resumes once on same item")
        expect(send(.hostReadinessChanged, 3.3) == [.pauseVideo] &&
               send(.hostReadinessChanged, 3.4, host: true) == [.resumeVideo],
               "revoked proof before fade re-enters hold")
        expect(media(13.65, 99, host: true, item: wrong).isEmpty &&
               media(13.65, 99, host: true, generation: wrong).isEmpty &&
               media(.nan, 99, host: true).isEmpty && media(.infinity, 99, host: true).isEmpty &&
               media(-1, 99, host: true).isEmpty && media(11.25, 99, host: true).isEmpty,
               "stale, foreign and invalid media time cannot advance wall or media clocks")
        expect(media(12.7, 3.5, host: true) == [.beginHandoff, .setCoverOpacity(1)] &&
               send(.hostReadinessChanged, 3.6) == [.release, .fallBackToStatic],
               "host proof revoked during fade stops without replaying Canvas")
        expect(send(.handoffFinished, 3.7, host: true).isEmpty, "revoked run never completes")

        active()
        _ = send(.firstFrame(item: key.item), 0.1)
        expect(media(13.8, 0.2) == [.pauseVideo] && send(.hostReadinessChanged, 0.3, host: true) == [.resumeVideo] &&
               send(.tick, 0.4, host: true).isEmpty,
               "coalesced clock crossing both thresholds cannot bypass hold or drive fade on host callback")
        expect(media(13.9, 0.5, host: true) == [.beginHandoff, .setCoverOpacity(0)] &&
               send(.tick, 18, host: true) == [.release, .fallBackToStatic],
               "clamp at media fade endpoint and bound missing cover completion")

        active()
        expect(send(.mediaFailed(item: wrong), 99).isEmpty &&
               send(.mediaFailed(item: key.item), 0.1) == [.release, .fallBackToDefault],
               "before visual presentation the owner may fall back to default within its budget")
        active()
        expect(send(.tick, 17.99).isEmpty && send(.tick, 18) == [.release, .fallBackToDefault],
               "missing first frame times out once")
        active()
        _ = send(.firstFrame(item: key.item), 0.1)
        _ = media(11.3, 0.2)
        expect(send(.tick, 18) == [.release, .fallBackToStatic] &&
               send(.hostReadinessChanged, 18.1, host: true).isEmpty,
               "hold never extends deadline, even if workspace becomes ready later")
        active()
        _ = send(.firstFrame(item: key.item), 0.1)
        expect(send(.mediaFailed(item: key.item), 0.2) == [.release, .fallBackToStatic],
               "failed after video reveal only allows static fallback")
        active()
        _ = send(.firstFrame(item: key.item), 0.1)
        _ = media(11.3, 0.2)
        expect(send(.skip, 18) == [.release] && media(13.65, 18.1, host: true).isEmpty &&
               send(.skip, 18.2).isEmpty, "skip wins at deadline during hold and never resumes or falls back")
    }
}
