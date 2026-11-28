import CoreGraphics
import CursorPendantMotion
import Testing

@Test func followsWithFortyMillisecondEaseOut() {
    let screen = CGRect(x: 0, y: 0, width: 1200, height: 800)
    let start = CGPoint(x: 400, y: 300)
    let end = CGPoint(x: 500, y: 300)
    var motion = PendantMotion(pointer: start, screen: screen, time: 0)

    #expect(motion.update(pointer: start, time: 0).pivot.x == 438)
    #expect(motion.update(pointer: end, time: 0).pivot.x == 438)
    let halfway = motion.update(pointer: end, time: 0.020)

    // CSS ease-out covers about 68.46% of the distance at half the duration.
    #expect(abs(halfway.pivot.x - 506.46) < 0.05)
    #expect(motion.update(pointer: end, time: 0.040).pivot.x == 538)
}

@Test func swingUsesTheChosenReturnSpeedAndSettles() {
    let screen = CGRect(x: 0, y: 0, width: 3000, height: 800)
    let start = CGPoint(x: 200, y: 300)
    let end = CGPoint(x: 350, y: 300)
    var motion = PendantMotion(pointer: start, screen: screen, time: 0)

    #expect(motion.update(pointer: end, time: 0.016).angle == 0)
    let angle = motion.update(pointer: end, time: 0.032).angle

    // At 120%, the 16 ms frame advances the original spring by 19.2 ms.
    #expect(abs(angle - (-2.326)) < 0.01)
    var peak = abs(angle)
    for frame in 3..<24 {
        let pointer = CGPoint(x: 200 + 100 * frame, y: 300)
        peak = max(peak, abs(motion.update(pointer: pointer, time: Double(frame) * 0.016).angle))
    }
    #expect(peak == 20)
    let last = CGPoint(x: 2500, y: 300)
    for frame in 24..<180 {
        _ = motion.update(pointer: last, time: Double(frame) * 0.016)
    }
    #expect(motion.update(pointer: last, time: 2.9).angle == 0)
}

@Test func flipsInsideAnOffsetDisplay() {
    let screen = CGRect(x: -1600, y: -300, width: 1600, height: 900)
    let pointer = CGPoint(x: -3, y: -294)
    var motion = PendantMotion(pointer: pointer, screen: screen, time: 0)
    let pose = motion.update(pointer: pointer, time: 0)

    #expect(pose.pivot.x < pointer.x)
    #expect(pose.pivot.y > pointer.y)
    #expect(screen.contains(pose.pivot))
}
