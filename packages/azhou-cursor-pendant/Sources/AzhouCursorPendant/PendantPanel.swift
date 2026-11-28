import AppKit
import CursorPendantMotion

@MainActor
final class PendantPanel: NSPanel {
    private let sprite: PendantView
    private var lastOrigin: CGPoint?
    private static let panelSize = CGSize(width: 84, height: 68)

    init(image: NSImage) {
        let rect = CGRect(origin: .zero, size: Self.panelSize)
        sprite = PendantView(frame: rect, image: image)
        super.init(contentRect: rect, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: true)
        title = "Azhou Cursor Pendant"
        contentView = sprite
        backgroundColor = .clear
        isOpaque = false
        hasShadow = false
        ignoresMouseEvents = true
        hidesOnDeactivate = false
        isMovable = false
        animationBehavior = .none
        level = .statusBar
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
        isExcludedFromWindowsMenu = true
        preventsApplicationTerminationWhenModal = false
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }

    func show(_ pose: PendantMotion.Pose) {
        let origin = CGPoint(
            x: pose.pivot.x - Self.panelSize.width / 2,
            y: pose.pivot.y - Self.panelSize.height + PendantView.topInset
        )
        if !isVisible || lastOrigin?.x != origin.x || lastOrigin?.y != origin.y {
            setFrameOrigin(origin)
            lastOrigin = origin
        }
        sprite.setAngle(pose.angle)
        if !isVisible {
            orderFrontRegardless()
        }
    }
}

@MainActor
private final class PendantView: NSView {
    static let topInset: CGFloat = 8
    private let image: NSImage
    private var angle = 0.0

    init(frame: CGRect, image: NSImage) {
        self.image = image
        super.init(frame: frame)
    }

    required init?(coder: NSCoder) {
        return nil
    }

    override var isFlipped: Bool { true }

    func setAngle(_ value: Double) {
        guard value != angle else { return }
        angle = value
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        guard let context = NSGraphicsContext.current?.cgContext else { return }
        context.clear(dirtyRect)
        context.saveGState()
        defer { context.restoreGState() }
        context.translateBy(x: bounds.midX, y: Self.topInset)
        context.rotate(by: angle * .pi / 180)

        let cord = CGRect(x: -0.5, y: 0, width: 1, height: PendantMotion.cordLength)
        NSColor(srgbRed: 0.45, green: 0.32, blue: 0.25, alpha: 0.9).setFill()
        NSBezierPath(rect: cord).fill()

        let size = PendantMotion.spriteSize
        let rect = CGRect(x: -size / 2, y: PendantMotion.cordLength, width: size, height: size)
        image.draw(in: rect, from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)
    }
}
