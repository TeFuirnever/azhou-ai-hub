import Foundation

struct OptionalStartupMediaTests {
    static func run() {
        typealias Policy = OptionalStartupMedia
        let generation = UUID()
        let item = UUID()
        let stale = UUID()
        let wrongItem = UUID()
        let key = Policy.Attempt(generation: generation, item: item)
        let configured = Policy.Configuration(timeout: 3)!
        func expect(_ condition: Bool, _ name: String) {
            guard condition else { print("FAIL " + name); exit(1) }
            print("PASS " + name)
        }

        var policy = Policy()
        expect(Policy.Configuration(timeout: .infinity) == nil &&
               Policy.Configuration(timeout: .nan) == nil &&
               Policy.Configuration(timeout: 0) == nil &&
               Policy.Configuration(timeout: 61) == nil, "configuration bounded")
        expect(policy.start(nil, attempt: key, now: 0).isEmpty &&
               policy.receive(.hostReadinessChanged, generation: generation, now: 1, hostReadyNow: true).isEmpty,
               "no configuration has no effects")
        expect(policy.start(configured, attempt: key, now: .nan).isEmpty &&
               policy.start(configured, attempt: key, now: -.infinity).isEmpty &&
               policy.start(configured, attempt: key, now: -1).isEmpty, "invalid time has no effects")
        expect(policy.start(configured, attempt: key, now: 1) == [.startMedia(key)], "opt-in records attempt")
        expect(policy.start(configured, attempt: key, now: 1).isEmpty, "duplicate start ignored")
        expect(policy.receive(.firstFrame(item: item), generation: stale, now: 99, hostReadyNow: true).isEmpty &&
               policy.receive(.firstFrame(item: wrongItem), generation: generation, now: 99, hostReadyNow: true).isEmpty,
               "stale notifications cannot reveal or time out current attempt")
        expect(policy.receive(.handoffFinished, generation: generation, now: 99, hostReadyNow: true).isEmpty,
               "completion before handoff ignored")
        expect(policy.receive(.hostReadinessChanged, generation: generation, now: 1.1, hostReadyNow: true).isEmpty,
               "early host ready alone does not hand off")
        expect(policy.receive(.firstFrame(item: item), generation: generation, now: 1.2, hostReadyNow: true) ==
               [.revealVideo, .beginHandoff], "first frame plus early host ready enables handoff")
        expect(policy.receive(.firstFrame(item: item), generation: generation, now: 1.3, hostReadyNow: true).isEmpty,
               "duplicate frame has no effects")
        expect(policy.receive(.handoffFinished, generation: generation, now: 1.4, hostReadyNow: true) == [.release],
               "finish releases")
        expect(policy.receive(.skip, generation: generation, now: 1.5, hostReadyNow: true).isEmpty &&
               policy.receive(.firstFrame(item: item), generation: generation, now: 1.5, hostReadyNow: true).isEmpty,
               "terminal ignores late events")

        policy = Policy()
        _ = policy.start(configured, attempt: key, now: 1)
        expect(policy.receive(.firstFrame(item: item), generation: generation, now: 1.1, hostReadyNow: false) == [.revealVideo],
               "display readiness is separate from host readiness")
        expect(policy.receive(.hostReadinessChanged, generation: generation, now: 1, hostReadyNow: true).isEmpty,
               "nonmonotonic timestamp is rejected")
        expect(policy.receive(.hostReadinessChanged, generation: generation, now: 1.2, hostReadyNow: true) == [.beginHandoff],
               "late host ready enables handoff once")
        expect(policy.receive(.tick, generation: generation, now: 4, hostReadyNow: true) == [.release, .fallBackToDefault],
               "handoff also has deadline")

        policy = Policy()
        _ = policy.start(configured, attempt: key, now: 0)
        expect(policy.receive(.mediaFailed(item: wrongItem), generation: generation, now: 0.1, hostReadyNow: true).isEmpty &&
               policy.receive(.mediaFailed(item: item), generation: generation, now: 0.1, hostReadyNow: true) ==
               [.release, .fallBackToDefault], "active media failure falls back")

        policy = Policy()
        _ = policy.start(configured, attempt: key, now: 0)
        expect(policy.receive(.tick, generation: generation, now: 2.99, hostReadyNow: true).isEmpty &&
               policy.receive(.tick, generation: generation, now: 3, hostReadyNow: true) ==
               [.release, .fallBackToDefault], "missing readiness times out once")
        expect(policy.receive(.tick, generation: generation, now: 3.1, hostReadyNow: true).isEmpty, "timeout terminal")

        policy = Policy()
        _ = policy.start(configured, attempt: key, now: 0)
        expect(policy.receive(.hostReadinessChanged, generation: generation, now: 0.1, hostReadyNow: true).isEmpty,
               "initial readiness does not latch across callbacks")
        expect(policy.receive(.firstFrame(item: item), generation: generation, now: 0.2, hostReadyNow: false) == [.revealVideo],
               "replaced workspace blocks premature handoff")
        expect(policy.receive(.hostReadinessChanged, generation: generation, now: 0.3, hostReadyNow: true) == [.beginHandoff],
               "current workspace can authorize handoff")
        expect(policy.receive(.hostReadinessChanged, generation: generation, now: 0.4, hostReadyNow: false) ==
               [.release, .fallBackToDefault], "revocation during handoff releases and falls back")
        expect(policy.receive(.handoffFinished, generation: generation, now: 0.5, hostReadyNow: true).isEmpty,
               "completion from revoked handoff cannot publish")

        policy = Policy()
        _ = policy.start(configured, attempt: key, now: 0)
        expect(policy.receive(.skip, generation: generation, now: 3, hostReadyNow: true) == [.release] &&
               policy.receive(.hostReadinessChanged, generation: generation, now: 3.1, hostReadyNow: true).isEmpty &&
               policy.receive(.firstFrame(item: item), generation: generation, now: 3.1, hostReadyNow: true).isEmpty &&
               policy.receive(.skip, generation: generation, now: 3.2, hostReadyNow: true).isEmpty,
               "skip wins at deadline and never falls back or reveals")
    }
}
