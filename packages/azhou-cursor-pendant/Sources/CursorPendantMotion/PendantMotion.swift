import CoreGraphics
import Foundation

public struct PendantMotion {
    public struct Pose {
        public let pivot: CGPoint
        public let angle: Double
    }

    public static let spriteSize: CGFloat = 32
    public static let cordLength: CGFloat = 16

    private static let followDuration = 0.040
    private static let swingLimit = 20.0
    private static let settleSpeed = 1.2
    private static let springLimit = 25.0
    private static let maximumStep = 0.032

    private let screen: CGRect
    private var pointer: CGPoint
    private var from: CGPoint
    private var target: CGPoint
    private var lastInput: TimeInterval
    private var lastFrame: TimeInterval?
    private var springAngle = 0.0
    private var velocity = 0.0

    public init(pointer: CGPoint, screen: CGRect, time: TimeInterval) {
        let pivot = Self.pivot(for: pointer, on: screen)
        self.screen = screen
        self.pointer = pointer
        self.from = pivot
        self.target = pivot
        self.lastInput = time
    }

    public mutating func update(pointer newPointer: CGPoint, time: TimeInterval) -> Pose {
        if newPointer.x != pointer.x || newPointer.y != pointer.y {
            from = position(at: time)
            target = Self.pivot(for: newPointer, on: screen)
            lastInput = time
            velocity = min(180, max(-180, velocity - (newPointer.x - pointer.x) * 3))
            pointer = newPointer
        }

        if springAngle != 0 || velocity != 0 {
            let elapsed = lastFrame.map { min(max(time - $0, 0), Self.maximumStep) } ?? 0
            let scaledTime = elapsed * Self.settleSpeed
            let steps = max(1, Int(ceil(scaledTime / Self.maximumStep)))
            let step = scaledTime / Double(steps)
            for _ in 0..<steps {
                velocity = (velocity - springAngle * 55 * step) * exp(-9 * step)
                springAngle = min(Self.springLimit, max(-Self.springLimit, springAngle + velocity * step))
            }
            if abs(springAngle) < 0.08 && abs(velocity) < 0.08 {
                springAngle = 0
                velocity = 0
                lastFrame = nil
            } else {
                lastFrame = time
            }
        }

        return Pose(pivot: position(at: time), angle: springAngle * Self.swingLimit / Self.springLimit)
    }

    private func position(at time: TimeInterval) -> CGPoint {
        let progress = min(1, max(0, (time - lastInput) / Self.followDuration))
        if progress == 1 { return target }
        if progress == 0 { return from }
        let fraction = MotionCurve.follow.sample(progress)
        return CGPoint(
            x: from.x + (target.x - from.x) * fraction,
            y: from.y + (target.y - from.y) * fraction
        )
    }

    // AppKit flips Quartz's display coordinates in Y, so the top edge belongs to this screen.
    public static func screenContains(_ point: CGPoint, on screen: CGRect) -> Bool {
        point.x >= screen.minX && point.x < screen.maxX && point.y > screen.minY && point.y <= screen.maxY
    }

    private static func pivot(for pointer: CGPoint, on screen: CGRect) -> CGPoint {
        let x = pointer.x - screen.minX
        let y = screen.maxY - pointer.y
        let width = spriteSize
        let height = spriteSize + cordLength
        let offsetX: CGFloat = 22
        let offsetY: CGFloat = 18
        let left = x + offsetX + width + 18 <= screen.width ? x + offsetX : x - offsetX - width
        let top = y + offsetY + height + 4 <= screen.height ? y + offsetY : y - offsetY - height

        // Room for the sprite at full swing, including its width and the cord.
        let sideMargin = min(34, screen.width / 2)
        let bottomMargin = min(52, screen.height)
        let pivotX = min(screen.width - sideMargin, max(sideMargin, left + width / 2))
        let pivotY = min(screen.height - bottomMargin, max(2, top))
        return CGPoint(x: screen.minX + pivotX, y: screen.maxY - pivotY)
    }
}

private struct MotionCurve {
    static let follow = Self(x1: 0, y1: 0, x2: 0.58, y2: 1)
    static let state = Self(x1: 0.23, y1: 1, x2: 0.32, y2: 1)

    let x1: Double
    let y1: Double
    let x2: Double
    let y2: Double

    // Invert the horizontal Bézier component to sample its vertical component.
    func sample(_ progress: Double) -> Double {
        var lower = 0.0
        var upper = 1.0
        for _ in 0..<14 {
            let t = (lower + upper) / 2
            if component(t, x1, x2) < progress {
                lower = t
            } else {
                upper = t
            }
        }
        return component((lower + upper) / 2, y1, y2)
    }

    private func component(_ t: Double, _ c1: Double, _ c2: Double) -> Double {
        let remaining = 1 - t
        return 3 * remaining * remaining * t * c1 + 3 * remaining * t * t * c2 + t * t * t
    }
}

public struct PendantVisibility {
    private var from = 0.0
    private var target = 0.0
    private var start = 0.0

    public init() {}

    public mutating func setVisible(_ visible: Bool, at time: TimeInterval) {
        let next = visible ? 1.0 : 0.0
        guard next != target else { return }
        from = opacity(at: time)
        target = next
        start = time
    }

    public func opacity(at time: TimeInterval) -> Double {
        let progress = min(1, max(0, (time - start) / 0.160))
        if progress == 1 { return target }
        if progress == 0 { return from }
        return from + (target - from) * MotionCurve.state.sample(progress)
    }
}
