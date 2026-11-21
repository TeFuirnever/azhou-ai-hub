import AVFoundation
import CryptoKit
import Darwin
import Foundation

struct OptionalStartupVideoFilesTests {
    @MainActor
    static func run() async throws {
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent("azhou-video-io-tests-" + UUID().uuidString, isDirectory: true)
        try fm.createDirectory(at: root, withIntermediateDirectories: false)
        defer { try? fm.removeItem(at: root) }
        try await exercisePackagedProvider(in: root)
        func folder(_ base: URL, _ name: String) throws -> URL {
            let url = base.appendingPathComponent(name, isDirectory: true)
            try fm.createDirectory(at: url, withIntermediateDirectories: false)
            return url
        }
        func reject(_ act: () throws -> Void) {
            do {
                try act()
                preconditionFailure("untrusted fixture input was accepted")
            } catch { }
        }
        let resources = try folder(root, "Resources")
        let marker = resources.appendingPathComponent("azhou-build.json")
        let startup = try folder(resources, "startup")
        let native = startup.appendingPathComponent("native-video", isDirectory: true)
        let other = try folder(root, "other")
        try fm.createSymbolicLink(at: native, withDestinationURL: other)
        let missing = try OptionalStartupVideoFiles.pins(in: resources)
        precondition(missing == nil, "absent marker must not inspect disabled video")
        let a = String(repeating: "a", count: 64), b = String(repeating: "b", count: 64)
        let c = String(repeating: "c", count: 64)
        func putMarker(_ inputs: [String: String], aggregate: String) throws {
            let metadata: [String: Any] = [
                "schema": 1, "projectID": "azhou.codex-startup-animation",
                "bundleID": "local.azhou.codex-startup", "executable": "AzhouCodexStartup",
                "inputSHA256": aggregate, "inputs": inputs,
            ]
            try JSONSerialization.data(withJSONObject: metadata).write(to: marker)
        }
        try putMarker(["Native/App.swift": c], aggregate: c)
        let baseline = try OptionalStartupVideoFiles.pins(in: resources)
        precondition(baseline == nil, "no clip pins must ignore a forbidden optional path")
        let cannotStage: (Data, (any StartupVideoTemporaryClip) throws -> Void) async throws -> any StartupVideoTemporaryClip = { _, _ in
            preconditionFailure("a non-opt-in bundle must not stage any media")
        }
        let wrongOwner = NativeStartupMediaSlot.packagedProvider(resources: resources, bundleID: "test.other",
            now: { 1 }, stage: cannotStage)
        precondition(wrongOwner == nil, "only self-bundle identity can create provider")
        let stock = NativeStartupMediaSlot.packagedProvider(resources: resources, bundleID: "local.azhou.codex-startup",
            now: { 1 }, stage: cannotStage)
        precondition(stock != nil && stock?() == nil, "stock marker never activates an optional preparation")
        try putMarker(["assets/private/startup-video.json": a], aggregate: c)
        reject { _ = try OptionalStartupVideoFiles.pins(in: resources) }
        let pair = [
            "Native/App.swift": c, "assets/private/startup-video.json": a, "assets/private/startup-video.mp4": b,
        ]
        try putMarker(pair, aggregate: c)
        reject { _ = try OptionalStartupVideoFiles.pins(in: resources) }
        try putMarker(pair, aggregate: "191a8a701ec75f9c8c113b2d194cb476acd0d4f57f09fad260c33002bbd77c91")
        let pins = try OptionalStartupVideoFiles.pins(in: resources)
        precondition(pins?.manifestSHA256 == a && pins?.clipSHA256 == b)
        reject { _ = try OptionalStartupVideoFiles.read(.clip, in: resources, maxBytes: 4) }

        try fm.removeItem(at: native)
        _ = try folder(startup, "native-video")
        var cancelledPath: URL?
        do {
            _ = try await StartupVideoOwnedFile.stageAsync(Data(repeating: 125, count: 500_000), temporaryDirectory: root) { lease in
                cancelledPath = lease.fileURL
                precondition(fm.fileExists(atPath: lease.fileURL.path), "exclusive file must be known before async write")
                lease.release()
                precondition(!fm.fileExists(atPath: lease.fileURL.deletingLastPathComponent().path),
                             "owner unlinks directory synchronously before worker/exit")
            }
            preconditionFailure("unlinked draft cannot be admitted")
        } catch OptionalStartupVideoFiles.Failure.fileChanged {}
        precondition(cancelledPath.map { !fm.fileExists(atPath: $0.path) } == true)
        let outside = other.appendingPathComponent("future.mp4")
        let bytes = Data([0, 2, 25, 255])
        try bytes.write(to: outside)
        let clip = native.appendingPathComponent("clip.mp4")
        try fm.createSymbolicLink(at: clip, withDestinationURL: outside)
        reject { _ = try OptionalStartupVideoFiles.read(.clip, in: resources, maxBytes: bytes.count) }
        try fm.removeItem(at: clip)
        precondition(mkfifo(clip.path, 0o600) == 0)
        reject { _ = try OptionalStartupVideoFiles.read(.clip, in: resources, maxBytes: bytes.count) }
        try fm.removeItem(at: clip)
        try bytes.write(to: clip)
        reject { _ = try OptionalStartupVideoFiles.read(.clip, in: resources, maxBytes: bytes.count - 1) }
        let verified = try OptionalStartupVideoFiles.read(.clip, in: resources, maxBytes: bytes.count)
        precondition(verified == bytes)

        let lease = try StartupVideoOwnedFile.stage(verified, temporaryDirectory: root)
        let slot = lease.fileURL
        let vault = slot.deletingLastPathComponent()
        let original = try Data(contentsOf: slot)
        let fileMode = try fm.attributesOfItem(atPath: slot.path)[.posixPermissions] as? NSNumber
        let dirMode = try fm.attributesOfItem(atPath: vault.path)[.posixPermissions] as? NSNumber
        precondition(original == bytes && fileMode?.intValue == 0o400 && dirMode?.intValue == 0o700)
        try Data([99]).write(to: clip)
        let snapshot = try Data(contentsOf: slot)
        precondition(snapshot == bytes, "source replacement cannot change the snapshot")
        lease.release()
        lease.release()
        precondition(!fm.fileExists(atPath: vault.path))

        let substituted = try StartupVideoOwnedFile.stage(verified, temporaryDirectory: root)
        let replaced = substituted.fileURL
        let originalName = replaced.deletingLastPathComponent().appendingPathComponent("preserved-original")
        try fm.moveItem(at: replaced, to: originalName)
        try Data([99]).write(to: replaced)
        substituted.release()
        let untouched = try Data(contentsOf: replaced)
        let retained = try Data(contentsOf: originalName)
        precondition(untouched == Data([99]) && retained == bytes, "lost identity must not delete existing files")
        print("Fixed bundle/video files: marker, no-follow, bounds, 0400 lease, cleanup and replacement passed")
    }

    // Generated from flat geometric colors with libx264: 160x90, 24fps,
    // 48 frames, silent. This is test input only, never packaged as Azhou media.
    @MainActor
    private static func exercisePackagedProvider(in root: URL) async throws {
        let fixture = """
        AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAVybW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAB9AAAQAA
        AQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
        AAAAAgAABJ10cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAB9AAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAA
        AAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAKAAAABaAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAfQAAAEAAABAAAAAAQV
        bWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAAwAAAAYABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRl
        b0hhbmRsZXIAAAADwG1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAA
        AQAAA4BzdGJsAAAAwHN0c2QAAAAAAAAAAQAAALBhdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAKAAWgBIAAAASAAAAAAA
        AAABFUxhdmM2MS4xOS4xMDEgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAANmF2Y0MBZAAK/+EAGWdkAAqs2UKN+TARAAADAAEA
        AAMAMA8SJZYBAAZo6+PLIsD9+PgAAAAAEHBhc3AAAAABAAAAAQAAABRidHJ0AAAAAAAAGXQAAAAAAAAAGHN0dHMAAAAAAAAA
        AQAAADAAAAIAAAAAFHN0c3MAAAAAAAAAAQAAAAEAAAGIY3R0cwAAAAAAAAAvAAAAAQAABAAAAAABAAAKAAAAAAEAAAQAAAAA
        AQAAAAAAAAABAAACAAAAAAEAAAoAAAAAAQAABAAAAAABAAAAAAAAAAEAAAIAAAAAAQAACgAAAAABAAAEAAAAAAEAAAAAAAAA
        AQAAAgAAAAABAAAKAAAAAAEAAAQAAAAAAQAAAAAAAAABAAACAAAAAAEAAAoAAAAAAQAABAAAAAABAAAAAAAAAAEAAAIAAAAA
        AQAACgAAAAABAAAEAAAAAAEAAAAAAAAAAQAAAgAAAAABAAAKAAAAAAEAAAQAAAAAAQAAAAAAAAABAAACAAAAAAEAAAoAAAAA
        AQAABAAAAAABAAAAAAAAAAEAAAIAAAAAAQAACgAAAAABAAAEAAAAAAEAAAAAAAAAAQAAAgAAAAABAAAKAAAAAAEAAAQAAAAA
        AQAAAAAAAAABAAACAAAAAAEAAAoAAAAAAQAABAAAAAABAAAAAAAAAAEAAAIAAAAAAQAACAAAAAACAAACAAAAABxzdHNjAAAA
        AAAAAAEAAAABAAAAMAAAAAEAAADUc3RzegAAAAAAAAAAAAAAMAAAA5kAAAAQAAAADQAAAAwAAAAMAAAAFgAAAA8AAAAMAAAA
        DAAAABYAAAAPAAAADAAAAAwAAAAWAAAADwAAAAwAAAAMAAAAFgAAAA8AAAAMAAAADAAAABYAAAAPAAAADAAAAAwAAAAWAAAA
        DwAAAAwAAAAMAAAAFgAAAA8AAAAMAAAADAAAABYAAAAPAAAADAAAAAwAAAAVAAAADwAAAAwAAAAMAAAAFQAAAA8AAAAMAAAA
        DAAAABUAAAAOAAAADAAAABRzdGNvAAAAAAAAAAEAAAWiAAAAYXVkdGEAAABZbWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAbWRp
        cmFwcGwAAAAAAAAAAAAAAAAsaWxzdAAAACSpdG9vAAAAHGRhdGEAAAABAAAAAExhdmY2MS43LjEwMwAAAAhmcmVlAAAGZW1k
        YXQAAAKuBgX//6rcRem95tlIt5Ys2CDZI+7veDI2NCAtIGNvcmUgMTY0IHIzMTA4IDMxZTE5ZjkgLSBILjI2NC9NUEVHLTQg
        QVZDIGNvZGVjIC0gQ29weWxlZnQgMjAwMy0yMDIzIC0gaHR0cDovL3d3dy52aWRlb2xhbi5vcmcveDI2NC5odG1sIC0gb3B0
        aW9uczogY2FiYWM9MSByZWY9MyBkZWJsb2NrPTE6MDowIGFuYWx5c2U9MHgzOjB4MTEzIG1lPWhleCBzdWJtZT03IHBzeT0x
        IHBzeV9yZD0xLjAwOjAuMDAgbWl4ZWRfcmVmPTEgbWVfcmFuZ2U9MTYgY2hyb21hX21lPTEgdHJlbGxpcz0xIDh4OGRjdD0x
        IGNxbT0wIGRlYWR6b25lPTIxLDExIGZhc3RfcHNraXA9MSBjaHJvbWFfcXBfb2Zmc2V0PS0yIHRocmVhZHM9MyBsb29rYWhl
        YWRfdGhyZWFkcz0xIHNsaWNlZF90aHJlYWRzPTAgbnI9MCBkZWNpbWF0ZT0xIGludGVybGFjZWQ9MCBibHVyYXlfY29tcGF0
        PTAgY29uc3RyYWluZWRfaW50cmE9MCBiZnJhbWVzPTMgYl9weXJhbWlkPTIgYl9hZGFwdD0xIGJfYmlhcz0wIGRpcmVjdD0x
        IHdlaWdodGI9MSBvcGVuX2dvcD0wIHdlaWdodHA9MiBrZXlpbnQ9MjUwIGtleWludF9taW49MjQgc2NlbmVjdXQ9NDAgaW50
        cmFfcmVmcmVzaD0wIHJjX2xvb2thaGVhZD00MCByYz1jcmYgbWJ0cmVlPTEgY3JmPTIzLjAgcWNvbXA9MC42MCBxcG1pbj0w
        IHFwbWF4PTY5IHFwc3RlcD00IGlwX3JhdGlvPTEuNDAgYXE9MToxLjAwAIAAAADjZYiEADv//uOr+BTOq0HPNEpDMK0Y0/PF
        Jds8hM3HLBVs+2cOWrAA20N1o80ecSAGYReDxlEKyd2avNS23pdsMd9sFLCR9LDIUYEOq9AYjkE015+MXx/3K5F4yQgITMLY
        EMGD3AJMBNFA9VyWA9TOt3JBPxVIupn63K464l8lTpJZUvDdg8rF1DXzRjLfC7q18eCjT8ToWw/bfrxdn6UNpPfHq3Ciqvc9
        +Fem7FbnSXUgVd2p6PoyphOS7mgHRRZxkdb9HutMgjObNQQ1aXHuXlveTDijcUQ7JZ7W4KjRDtfNGkkAAAAMQZokbEO//qmW
        AOaAAAAACUGeQniF/wDzgQAAAAgBnmF0Qr8BUwAAAAgBnmNqQr8BUwAAABJBmmhJqEFomUwId//+qZYA5oEAAAALQZ6GRREs
        L/8A84EAAAAIAZ6ldEK/AVMAAAAIAZ6nakK/AVMAAAASQZqsSahBbJlMCHf//qmWAOaAAAAAC0GeykUVLC//APOBAAAACAGe
        6XRCvwFTAAAACAGe62pCvwFTAAAAEkGa8EmoQWyZTAh3//6plgDmgQAAAAtBnw5FFSwv/wDzgQAAAAgBny10Qr8BUwAAAAgB
        ny9qQr8BUwAAABJBmzRJqEFsmUwId//+qZYA5oAAAAALQZ9SRRUsL/8A84EAAAAIAZ9xdEK/AVMAAAAIAZ9zakK/AVMAAAAS
        QZt4SahBbJlMCHf//qmWAOaBAAAAC0GflkUVLC//APOAAAAACAGftXRCvwFTAAAACAGft2pCvwFTAAAAEkGbvEmoQWyZTAh3
        //6plgDmgAAAAAtBn9pFFSwv/wDzgQAAAAgBn/l0Qr8BUwAAAAgBn/tqQr8BUwAAABJBm+BJqEFsmUwId//+qZYA5oEAAAAL
        QZ4eRRUsL/8A84AAAAAIAZ49dEK/AVMAAAAIAZ4/akK/AVMAAAASQZokSahBbJlMCHf//qmWAOaAAAAAC0GeQkUVLC//APOB
        AAAACAGeYXRCvwFTAAAACAGeY2pCvwFTAAAAEUGaaEmoQWyZTAhv//6nhAHHAAAAC0GehkUVLC//APOBAAAACAGepXRCvwFT
        AAAACAGep2pCvwFTAAAAEUGarEmoQWyZTAhn//6eEAbMAAAAC0GeykUVLC//APOBAAAACAGe6XRCvwFTAAAACAGe62pCvwFT
        AAAAEUGa70moQWyZTAhX//44QBoxAAAACkGfDUUVLCv/AVMAAAAIAZ8uakK/AVM=
        """
        let clip = Data(base64Encoded: fixture, options: .ignoreUnknownCharacters)!
        let manifest = Data(base64Encoded: "eyJieXRlTGVuZ3RoIjogMzA3MSwgImNsaXBTSEEyNTYiOiAiM2U3Y2ExZTU3ZDczM2FmMjcxNjhkNmI5NjFjZWQ3MDcxMTE2NDk2MTZkM2FlZTlhOWNkOGIxOGY5MDQ1MmFhYiIsICJmYWRlRW5kTXMiOiAxMDAwLCAiZmFkZVN0YXJ0TXMiOiA2NTAsICJob2xkTXMiOiAzNTAsICJzY2hlbWEiOiAxfQo=")!
        let resources = root.appendingPathComponent("PackedFixture", isDirectory: true)
        let capsule = resources.appendingPathComponent("startup/native-video", isDirectory: true)
        try FileManager.default.createDirectory(at: capsule, withIntermediateDirectories: true)
        try manifest.write(to: capsule.appendingPathComponent("manifest.json"))
        let original = capsule.appendingPathComponent("clip.mp4")
        try clip.write(to: original)
        func hex(_ bytes: some Sequence<UInt8>) -> String {
            bytes.map { String(format: "%02x", $0) }.joined()
        }
        let identities = [("assets/private/startup-video.json", manifest), ("assets/private/startup-video.mp4", clip)]
        var aggregate = Data()
        var inputs = [String: String]()
        for (name, bytes) in identities {
            let digest = SHA256.hash(data: bytes)
            inputs[name] = hex(digest)
            aggregate.append(contentsOf: name.utf8)
            aggregate.append(0)
            aggregate.append(contentsOf: digest)
        }
        let marker: [String: Any] = [
            "schema": 1, "projectID": "azhou.codex-startup-animation", "bundleID": "local.azhou.codex-startup",
            "executable": "AzhouCodexStartup", "inputs": inputs, "inputSHA256": hex(SHA256.hash(data: aggregate)),
        ]
        try JSONSerialization.data(withJSONObject: marker).write(to: resources.appendingPathComponent("azhou-build.json"))
        let now = { ProcessInfo.processInfo.systemUptime }
        var earlyOwned: URL?
        let provider = NativeStartupMediaSlot.packagedProvider(resources: resources,
            bundleID: "local.azhou.codex-startup", now: now, stage: { bytes, onOwned in
                try await StartupVideoOwnedFile.stageAsync(bytes, temporaryDirectory: root) {
                    try onOwned($0)
                }
            })!
        let deadline = now() + 5
        let slot = try await provider()!(.init(resolveBy: deadline, finishBy: deadline, onOwned: {
            earlyOwned = $0.fileURL
            precondition(FileManager.default.fileExists(atPath: $0.fileURL.path))
        }))!
        defer { slot.clipLease?.release() }
        let item = try slot.makeItem()
        let staged = (item.asset as? AVURLAsset)?.url
        precondition(staged != nil && staged != original && staged == earlyOwned,
                     "packaged bytes give AVPlayerItem only the registered private snapshot")
        precondition(slot.configuration.holdAt == 0.35 && slot.configuration.fadeStart == 0.65 &&
                     slot.configuration.fadeEnd == 1, "real H.264 tracks match the sealed timing contract")
        slot.clipLease?.release()
        precondition(staged.map { !FileManager.default.fileExists(atPath: $0.path) } == true)
    }
}
