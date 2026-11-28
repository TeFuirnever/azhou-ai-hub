import AppKit
import CursorPendantMotion
import OSLog

@main
@MainActor
struct PendantApp {
    static func main() {
        let app = NSApplication.shared
        let delegate = PendantController()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)
        withExtendedLifetime(delegate) {
            app.run()
        }
    }
}

@MainActor
final class PendantController: NSObject, NSApplicationDelegate {
    private let logger = Logger(subsystem: "lab.azhou.cursor-pendant", category: "App")
    private var panel: PendantPanel?
    private var statusItem: NSStatusItem?
    private var followingItem: NSMenuItem?
    private var motion: PendantMotion?
    private var visibility = PendantVisibility()
    private var screenFrame: CGRect?
    private var timer: Timer?
    private var wantsFollowing = true

    func applicationDidFinishLaunching(_ notification: Notification) {
        guard let url = Bundle.main.url(forResource: "Pendant", withExtension: "png"),
              let image = NSImage(contentsOf: url) else {
            logger.error("Pendant.png is missing from the application bundle")
            NSApp.terminate(nil)
            return
        }

        panel = PendantPanel(image: image)
        addMenu(image: image)
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(accessibilityOptionsChanged),
            name: NSWorkspace.accessibilityDisplayOptionsDidChangeNotification,
            object: nil
        )
        updateFollowing()
    }

    func applicationDidChangeScreenParameters(_ notification: Notification) {
        resetMotion()
        if timer != nil, wantsFollowing { tick() }
    }

    func applicationWillTerminate(_ notification: Notification) {
        timer?.invalidate()
        timer = nil
        panel?.orderOut(nil)
        NSWorkspace.shared.notificationCenter.removeObserver(self)
        if let statusItem {
            NSStatusBar.system.removeStatusItem(statusItem)
        }
    }

    private func addMenu(image: NSImage) {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        let mark = NSImage(size: NSSize(width: 18, height: 18), flipped: false) { bounds in
            image.draw(in: bounds)
            return true
        }
        mark.isTemplate = true
        item.button?.image = mark
        item.button?.setAccessibilityLabel("阿舟跟随挂件")
        item.button?.toolTip = "阿舟跟随挂件"
        let menu = NSMenu()
        let following = menu.addItem(withTitle: "暂停跟随", action: #selector(toggleFollowing), keyEquivalent: "")
        following.target = self
        menu.addItem(.separator())
        let quit = menu.addItem(withTitle: "退出阿舟跟随挂件", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        quit.target = NSApp
        item.menu = menu
        followingItem = following
        statusItem = item
    }

    @objc private func toggleFollowing() {
        wantsFollowing.toggle()
        updateFollowing()
    }

    @objc private func accessibilityOptionsChanged(_ notification: Notification) {
        updateFollowing()
    }

    private func updateFollowing() {
        let reduced = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        followingItem?.title = reduced ? "系统已开启「减少动态效果」" : (wantsFollowing ? "暂停跟随" : "恢复跟随")
        followingItem?.action = reduced ? nil : #selector(toggleFollowing)
        if reduced {
            visibility = PendantVisibility()
            stopFollowing()
            return
        }

        visibility.setVisible(wantsFollowing, at: ProcessInfo.processInfo.systemUptime)
        guard wantsFollowing else {
            motion = nil
            screenFrame = nil
            return
        }
        guard timer == nil else { return }
        tick()
        let nextTimer = Timer(timeInterval: 1.0 / 60, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                self?.tick()
            }
        }
        RunLoop.main.add(nextTimer, forMode: .common)
        timer = nextTimer
    }

    private func stopFollowing() {
        timer?.invalidate()
        timer = nil
        resetMotion()
    }

    private func resetMotion() {
        motion = nil
        screenFrame = nil
        panel?.orderOut(nil)
    }

    private func tick() {
        let time = ProcessInfo.processInfo.systemUptime
        let opacity = CGFloat(visibility.opacity(at: time))
        if panel?.alphaValue != opacity { panel?.alphaValue = opacity }
        if !wantsFollowing {
            if opacity == 0 { stopFollowing() }
            return
        }

        let pointer = NSEvent.mouseLocation
        if screenFrame?.contains(pointer) != true {
            guard let frame = NSScreen.screens.first(where: { $0.frame.contains(pointer) })?.frame else {
                if screenFrame != nil { resetMotion() }
                return
            }
            screenFrame = frame
            motion = PendantMotion(pointer: pointer, screen: frame, time: time)
        }

        if let pose = motion?.update(pointer: pointer, time: time) {
            panel?.show(pose)
        }
    }
}
