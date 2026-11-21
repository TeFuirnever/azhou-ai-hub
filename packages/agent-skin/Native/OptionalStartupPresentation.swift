import AVFoundation
import Foundation
import QuartzCore

/// Composition only: the existing cold-run owner supplies cover, current proof,
/// clock and terminal actions. This object never selects assets or starts a host.
@MainActor
final class OptionalStartupPresentation {
    enum End: Equatable { case completed, skipped, defaultFallback, staticFallback }
    enum Output: Equatable {
        case revealVideo
        case beginHandoff
        case coverOpacity(Double)
        case restoreOpaqueCover
        case ended(End)
    }

    private let attempt: OptionalStartupMedia.Attempt
    private let now: () -> TimeInterval
    private let workspaceReadyNow: (OptionalStartupMedia.Attempt) -> Bool
    private let output: (Output) -> Void
    private var policy = OptionalStartupMedia()
    private var playback: OptionalStartupAVPlayback?
    private var started = false
    private var terminal = false
    private var emittedZeroOpacity = false

    init(attempt: OptionalStartupMedia.Attempt, now: @escaping () -> TimeInterval,
         workspaceReadyNow: @escaping (OptionalStartupMedia.Attempt) -> Bool,
         output: @escaping (Output) -> Void) {
        self.attempt = attempt
        self.now = now
        self.workspaceReadyNow = workspaceReadyNow
        self.output = output
    }

    func start(_ config: OptionalStartupMedia.Configuration?, in container: CALayer,
               frame: CGRect, makeItem: () throws -> AVPlayerItem) {
        guard policy.start(config, attempt: attempt, now: now()) == [.startMedia(attempt)] else { return }
        started = true
        do {
            let item = try makeItem()
            send(.tick)
            guard !terminal else { return }
            let adapter = OptionalStartupAVPlayback(attempt: attempt, item: item) { [weak self] attempt, signal in
                guard let self, self.attempt == attempt else { return }
                switch signal {
                case .firstFrame: self.send(.firstFrame(item: attempt.item))
                case .mediaTime(let seconds): self.send(.mediaTime(item: attempt.item, seconds: seconds))
                case .ended, .failed: self.send(.mediaFailed(item: attempt.item))
                }
            }
            playback = adapter
            guard adapter.prepare(in: container, frame: frame) else {
                send(.mediaFailed(item: attempt.item))
                return
            }
            send(.tick)
            guard !terminal else { return }
            adapter.play()
        } catch {
            send(.mediaFailed(item: attempt.item))
        }
    }

    func workspaceReadinessChanged() { send(.hostReadinessChanged) }
    func tick() { send(.tick) }
    func skip() { send(.skip) }
    /// The synchronous output sink must acknowledge only after applying opacity zero.
    func coverFadeCommitted() {
        guard emittedZeroOpacity else { return }
        send(.handoffFinished)
    }

    private func send(_ event: OptionalStartupMedia.Event) {
        guard started, !terminal else { return }
        let ready: Bool
        if case .skip = event { ready = false } else { ready = workspaceReadyNow(attempt) }
        guard !terminal else { return }
        let effects = policy.receive(event, generation: attempt.generation, now: now(), hostReadyNow: ready)
        if effects.contains(.release) {
            terminal = true
            let end: End
            if effects.contains(.fallBackToDefault) {
                end = .defaultFallback
            } else if effects.contains(.fallBackToStatic) {
                end = .staticFallback
            } else if case .skip = event {
                end = .skipped
            } else {
                end = .completed
            }
            if end == .defaultFallback || end == .staticFallback {
                output(.restoreOpaqueCover)
            }
            playback?.release()
            playback = nil
            output(.ended(end))
            return
        }
        for effect in effects {
            guard !terminal else { return }
            switch effect {
            case .revealVideo: output(.revealVideo)
            case .pauseVideo: playback?.pause()
            case .resumeVideo: playback?.play()
            case .beginHandoff: output(.beginHandoff)
            case .setCoverOpacity(let opacity):
                // A synchronous begin callback may have revoked current proof.
                guard workspaceReadyNow(attempt) else { send(.hostReadinessChanged); return }
                guard !terminal else { return }
                if opacity == 0 { emittedZeroOpacity = true }
                output(.coverOpacity(opacity))
            case .startMedia, .release, .fallBackToDefault, .fallBackToStatic: break
            }
        }
    }
}
