import AVFoundation
import Foundation
import QuartzCore

/// Owns exactly one prepared native media item. The caller supplies a fresh item
/// backed by already authorized bytes and keeps the cover above this layer until
/// the first-frame signal. This type never resolves assets or observes a host.
@MainActor
final class OptionalStartupAVPlayback {
    enum Signal: Equatable {
        case firstFrame
        case mediaTime(TimeInterval)
        case ended
        case failed
    }

    private enum State: Equatable { case idle, prepared, released }

    private let attempt: OptionalStartupMedia.Attempt
    private let resources = PlaybackResources()
    private let notifications: NotificationCenter
    private var player: AVPlayer { resources.player }
    private var layer: AVPlayerLayer { resources.layer }
    private var item: AVPlayerItem?
    private var receive: ((OptionalStartupMedia.Attempt, Signal) -> Void)?
    private var state = State.idle
    private var firstFrameSent = false
    private var terminalSent = false
    private var lastMediaTime: TimeInterval?

    init(attempt: OptionalStartupMedia.Attempt, item: AVPlayerItem,
         notifications: NotificationCenter = .default,
         receive: @escaping (OptionalStartupMedia.Attempt, Signal) -> Void) {
        self.attempt = attempt
        self.item = item
        self.notifications = notifications
        self.receive = receive
        player.isMuted = true
        layer.videoGravity = .resizeAspectFill
    }

    /// Mount under the existing opaque cover. Mounting/observing never plays.
    @discardableResult
    func prepare(in container: CALayer, frame: CGRect) -> Bool {
        guard state == .idle, let item,
              frame.origin.x.isFinite, frame.origin.y.isFinite,
              frame.width.isFinite, frame.height.isFinite,
              frame.width > 0, frame.height > 0 else { return false }
        state = .prepared
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layer.frame = frame
        container.addSublayer(layer)
        CATransaction.commit()

        player.replaceCurrentItem(with: item)
        layer.player = player
        let lease = ObservationLease(player: player, notifications: notifications)
        resources.observers = lease
        lease.properties = [
            item.observe(\.status, options: [.initial, .new]) { [weak self] _, _ in
                Task { @MainActor [weak self] in self?.sample() }
            },
            player.observe(\.status, options: [.initial, .new]) { [weak self] _, _ in
                Task { @MainActor [weak self] in self?.sample() }
            },
            layer.observe(\.isReadyForDisplay, options: [.initial, .new]) { [weak self] _, _ in
                Task { @MainActor [weak self] in self?.sample() }
            },
        ]
        lease.notifications = [
            notifications.addObserver(forName: AVPlayerItem.failedToPlayToEndTimeNotification,
                                      object: item, queue: .main) { [weak self] _ in
                Task { @MainActor [weak self] in self?.terminal(.failed) }
            },
            notifications.addObserver(forName: AVPlayerItem.didPlayToEndTimeNotification,
                                      object: item, queue: .main) { [weak self] _ in
                Task { @MainActor [weak self] in self?.terminal(.ended) }
            },
        ]
        lease.time = player.addPeriodicTimeObserver(forInterval: CMTime(value: 1, timescale: 30),
                                                    queue: .main) { [weak self] _ in
            Task { @MainActor [weak self] in self?.sample() }
        }
        return true
    }

    func play() {
        guard activeItem != nil else { return }
        player.play()
    }

    func pause() {
        guard activeItem != nil else { return }
        player.pause()
    }

    /// The owner calls this on every terminal path. Queued callbacks become inert
    /// before the first resource is touched and can never reach a later attempt.
    func release() {
        guard state != .released else { return }
        state = .released
        receive = nil
        resources.release()
        item = nil
    }

    deinit {
        // A layer can outlive the adapter if its container still owns it. The
        // normal path is synchronous release; this is only an abandonment guard.
        let abandoned = resources
        Task { @MainActor in abandoned.release() }
    }

    private var activeItem: AVPlayerItem? {
        guard state == .prepared, !terminalSent, let item, player.currentItem === item else { return nil }
        return item
    }

    private func sample() {
        guard let item = activeItem else { return }
        if player.status == .failed || item.status == .failed {
            terminal(.failed)
            return
        }
        if !firstFrameSent, item.status == .readyToPlay, layer.isReadyForDisplay {
            firstFrameSent = true
            receive?(attempt, .firstFrame)
        }
        // The owner is allowed to release synchronously while receiving a signal.
        guard activeItem != nil else { return }
        let mediaTime = player.currentTime().seconds
        if mediaTime.isFinite, mediaTime >= 0, mediaTime != lastMediaTime {
            lastMediaTime = mediaTime
            receive?(attempt, .mediaTime(mediaTime))
        }
    }

    private func terminal(_ signal: Signal) {
        guard activeItem != nil else { return }
        terminalSent = true
        player.pause()
        receive?(attempt, signal)
    }

    /// Internal seams let an isolated fixture assert real resource disposal.
    var lifetime: (observationCount: Int, hasCurrentItem: Bool, mounted: Bool, muted: Bool, paused: Bool) {
        (resources.observers?.count ?? 0, player.currentItem != nil, layer.superlayer != nil, player.isMuted, player.rate == 0)
    }
}

@MainActor
private final class PlaybackResources {
    let player = AVPlayer()
    let layer = AVPlayerLayer(player: nil)
    var observers: ObservationLease?
    private var released = false

    func release() {
        guard !released else { return }
        released = true
        observers?.removeAll()
        observers = nil
        player.pause()
        player.currentItem?.cancelPendingSeeks()
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layer.removeFromSuperlayer()
        layer.player = nil
        CATransaction.commit()
        player.replaceCurrentItem(with: nil)
    }
}

@MainActor
private final class ObservationLease {
    private let player: AVPlayer
    private let center: NotificationCenter
    var properties: [NSKeyValueObservation] = []
    var notifications: [NSObjectProtocol] = []
    var time: Any?

    init(player: AVPlayer, notifications: NotificationCenter) {
        self.player = player
        center = notifications
    }

    var count: Int { properties.count + notifications.count + (time == nil ? 0 : 1) }

    func removeAll() {
        if let token = time {
            time = nil
            player.removeTimeObserver(token)
        }
        properties.forEach { $0.invalidate() }
        properties.removeAll()
        notifications.forEach { center.removeObserver($0) }
        notifications.removeAll()
    }

}
