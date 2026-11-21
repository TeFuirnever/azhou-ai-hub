import Foundation

/// Pure policy for an opt-in startup presentation. The owner resolves and
/// validates the media slot before constructing this policy, and executes
/// effects on its own isolated presentation resources.
struct OptionalStartupMedia {
    struct Attempt: Equatable {
        let generation: UUID
        let item: UUID
    }

    struct Configuration {
        let timeout: TimeInterval
        init?(timeout: TimeInterval) {
            guard timeout.isFinite, (0.1 ... 60).contains(timeout) else { return nil }
            self.timeout = timeout
        }
    }

    enum Event {
        case firstFrame(item: UUID)
        case hostReadinessChanged
        case handoffFinished
        case skip
        case mediaFailed(item: UUID)
        case tick
    }

    enum Effect: Equatable {
        case startMedia(Attempt)
        case revealVideo
        case beginHandoff
        case release
        case fallBackToDefault
    }

    private enum Phase: Equatable { case inactive, waiting, handingOff, terminal }
    private var phase = Phase.inactive
    private var attempt: Attempt?
    private var deadline = 0.0
    private var lastTime = 0.0
    private var frameReady = false

    mutating func start(_ configuration: Configuration?, attempt: Attempt, now: TimeInterval) -> [Effect] {
        guard phase == .inactive, let configuration, now.isFinite, now >= 0 else { return [] }
        let deadline = now + configuration.timeout
        guard deadline.isFinite, deadline > now else { return [] }
        self.attempt = attempt
        self.deadline = deadline
        lastTime = now
        phase = .waiting
        return [.startMedia(attempt)]
    }

    /// The owner must validate the provisional workspace evidence for this
    /// exact generation at the decision, not reuse the final startup receipt.
    mutating func receive(_ event: Event, generation: UUID, now: TimeInterval,
                          hostReadyNow: Bool) -> [Effect] {
        guard phase == .waiting || phase == .handingOff,
              let attempt, generation == attempt.generation,
              now.isFinite, now >= lastTime else { return [] }
        // Invalid item notifications can never advance time or affect a run.
        switch event {
        case .firstFrame(let item), .mediaFailed(let item):
            guard item == attempt.item else { return [] }
        case .handoffFinished:
            guard phase == .handingOff else { return [] }
        default: break
        }
        lastTime = now
        // A terminal user action wins at the exact timeout boundary.
        if case .skip = event { return finish(fallback: false) }
        if now >= deadline || phase == .handingOff && !hostReadyNow { return finish(fallback: true) }

        var effects: [Effect] = []
        switch event {
        case .firstFrame:
            if !frameReady {
                frameReady = true
                effects.append(.revealVideo)
            }
        case .handoffFinished:
            return finish(fallback: false)
        case .mediaFailed: return finish(fallback: true)
        case .skip, .tick, .hostReadinessChanged: break
        }
        if phase == .waiting && frameReady && hostReadyNow {
            phase = .handingOff
            effects.append(.beginHandoff)
        }
        return effects
    }

    private mutating func finish(fallback: Bool) -> [Effect] {
        phase = .terminal
        attempt = nil
        return fallback ? [.release, .fallBackToDefault] : [.release]
    }
}
