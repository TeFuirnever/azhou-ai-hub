import Foundation

/// Pure policy for one opt-in startup presentation. The owner validates the
/// media and workspace evidence and executes effects on its own resources.
struct OptionalStartupMedia {
    struct Attempt: Equatable {
        let generation: UUID
        let item: UUID
    }

    struct Configuration {
        let timeout: TimeInterval
        let holdAt: TimeInterval
        let fadeStart: TimeInterval
        let fadeEnd: TimeInterval

        init?(timeout: TimeInterval, holdAt: TimeInterval, fadeStart: TimeInterval, fadeEnd: TimeInterval) {
            guard timeout.isFinite, (0.1 ... 60).contains(timeout),
                  holdAt.isFinite, fadeStart.isFinite, fadeEnd.isFinite,
                  0 < holdAt, holdAt < fadeStart, fadeStart < fadeEnd, fadeEnd < timeout else { return nil }
            self.timeout = timeout
            self.holdAt = holdAt
            self.fadeStart = fadeStart
            self.fadeEnd = fadeEnd
        }
    }

    enum Event {
        case firstFrame(item: UUID)
        case mediaTime(item: UUID, seconds: TimeInterval)
        case hostReadinessChanged
        case handoffFinished
        case skip
        case motionDisabled
        case mediaFailed(item: UUID)
        case tick
    }

    enum Effect: Equatable {
        case startMedia(Attempt)
        case revealVideo
        case pauseVideo
        case resumeVideo
        case beginHandoff
        case setCoverOpacity(Double)
        case release
        /// The owner may choose Canvas only if its original budget allows it.
        case fallBackToDefault
        case fallBackToStatic
    }

    private enum Phase { case inactive, playing, held, fading, fadeComplete, terminal }
    private var phase = Phase.inactive
    private var attempt: Attempt?
    private var configuration: Configuration?
    private var deadline = 0.0
    private var lastTime = 0.0
    private var lastMediaTime: TimeInterval?
    private var frameReady = false

    mutating func start(_ configuration: Configuration?, attempt: Attempt, now: TimeInterval, deadlineLimit: TimeInterval? = nil) -> [Effect] {
        guard phase == .inactive, let configuration, now.isFinite, now >= 0 else { return [] }
        if let deadlineLimit, !deadlineLimit.isFinite { return [] }
        let deadline = min(now + configuration.timeout, deadlineLimit ?? .infinity)
        guard deadline.isFinite, deadline > now + configuration.fadeEnd else { return [] }
        self.attempt = attempt
        self.configuration = configuration
        self.deadline = deadline
        lastTime = now
        phase = .playing
        return [.startMedia(attempt)]
    }

    /// Host proof is provisional, current and owned by the same generation.
    /// It must be checked at every decision; the final startup receipt comes later.
    mutating func receive(_ event: Event, generation: UUID, now: TimeInterval,
                          hostReadyNow: Bool) -> [Effect] {
        guard let attempt, let configuration, generation == attempt.generation,
              now.isFinite, now >= lastTime else { return [] }
        switch event {
        case .firstFrame(let item):
            guard item == attempt.item, !frameReady else { return [] }
        case .mediaFailed(let item):
            guard item == attempt.item else { return [] }
        case .mediaTime(let item, let seconds):
            guard item == attempt.item, frameReady, phase != .fadeComplete,
                  seconds.isFinite, seconds >= 0, lastMediaTime.map({ seconds > $0 }) ?? true else { return [] }
        case .handoffFinished:
            guard phase == .fadeComplete else { return [] }
        default: break
        }

        lastTime = now
        if case .skip = event { return finish(fallback: false) }
        if case .motionDisabled = event { return finish(fallback: true, alwaysStatic: true) }
        if now >= deadline || (phase == .fading || phase == .fadeComplete) && !hostReadyNow {
            return finish(fallback: true)
        }
        switch event {
        case .firstFrame:
            frameReady = true
            return [.revealVideo]
        case .handoffFinished: return finish(fallback: false)
        case .mediaFailed: return finish(fallback: true)
        default: break
        }

        var freshMediaTime: TimeInterval?
        if case .mediaTime(_, let seconds) = event {
            lastMediaTime = seconds
            freshMediaTime = seconds
        }
        if phase == .held {
            guard hostReadyNow else { return [] }
            phase = .playing
            return [.resumeVideo]
        }
        if phase == .playing, !hostReadyNow, (lastMediaTime ?? 0) >= configuration.holdAt {
            phase = .held
            return [.pauseVideo]
        }
        guard let seconds = freshMediaTime, seconds >= configuration.fadeStart else { return [] }
        var effects: [Effect] = []
        if phase == .playing {
            phase = .fading
            effects.append(.beginHandoff)
        }
        let progress = min(1, (seconds - configuration.fadeStart) / (configuration.fadeEnd - configuration.fadeStart))
        effects.append(.setCoverOpacity(1 - progress * progress * (3 - 2 * progress)))
        if progress >= 1 { phase = .fadeComplete }
        return effects
    }

    private mutating func finish(fallback: Bool, alwaysStatic: Bool = false) -> [Effect] {
        phase = .terminal
        attempt = nil
        configuration = nil
        if !fallback { return [.release] }
        return [.release, frameReady || alwaysStatic ? .fallBackToStatic : .fallBackToDefault]
    }
}
