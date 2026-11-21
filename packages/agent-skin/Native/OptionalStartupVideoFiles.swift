import CryptoKit
import Darwin
import Foundation

/// Only reads fixed signed-bundle resources. Caller owns the trusted product and
/// cold/enabled eligibility; neither this port nor the marker authenticates a signer.
enum OptionalStartupVideoFiles {
    static let maxClipBytes = 64 * 1024 * 1024
    private static let manifestKey = "assets/private/startup-video.json"
    private static let clipKey = "assets/private/startup-video.mp4"
    private static let maxMarkerBytes = 256 * 1024

    enum Failure: Error {
        case unsafePath, invalidMarker, missingFile, fileChanged, invalidBounds, io
    }

    private struct Marker: Decodable {
        let schema: Int
        let projectID: String
        let bundleID: String
        let executable: String
        let inputSHA256: String
        let inputs: [String: String]
    }

    /// Absence of both optional pins is disabled, not an invitation to look for a clip.
    static func pins(in resources: URL) throws -> OptionalStartupVideoResolver.Pins? {
        let directory = try VideoDirectoryChain(root: resources)
        guard let data = try directory.read("azhou-build.json", limit: maxMarkerBytes, allowMissing: true) else {
            return nil
        }
        guard let marker = try? JSONDecoder().decode(Marker.self, from: data),
              marker.schema == 1, marker.projectID == "azhou.codex-startup-animation",
              marker.bundleID == "local.azhou.codex-startup", marker.executable == "AzhouCodexStartup" else {
            throw Failure.invalidMarker
        }
        let reportedManifest = marker.inputs[manifestKey]
        let reportedClip = marker.inputs[clipKey]
        if reportedManifest == nil && reportedClip == nil { return nil }
        guard let manifest = reportedManifest, let clip = reportedClip,
              try aggregate(marker.inputs) == marker.inputSHA256 else { throw Failure.invalidMarker }
        return OptionalStartupVideoResolver.Pins(manifestSHA256: manifest, clipSHA256: clip)
    }

    static func read(_ resource: OptionalStartupVideoResolver.Resource, in resources: URL,
                     maxBytes: Int) throws -> Data {
        let name: String
        let ceiling: Int
        switch resource {
        case .manifest: (name, ceiling) = ("manifest.json", 4096)
        case .clip: (name, ceiling) = ("clip.mp4", maxClipBytes)
        }
        guard (1...ceiling).contains(maxBytes) else { throw Failure.invalidBounds }
        let directory = try VideoDirectoryChain(root: resources)
        try directory.append("startup")
        try directory.append("native-video")
        guard let bytes = try directory.read(name, limit: maxBytes) else { throw Failure.missingFile }
        return bytes
    }

    // Match verify-artifacts.py::aggregate_inputs (sorted UTF-8 name, NUL, raw digest).
    private static func aggregate(_ inputs: [String: String]) throws -> String {
        var hash = SHA256()
        for name in inputs.keys.sorted(by: { $0.utf8.lexicographicallyPrecedes($1.utf8) }) {
            let parts = name.split(separator: "/", omittingEmptySubsequences: false)
            guard !name.utf8.contains(0), !parts.contains(where: { $0.isEmpty || $0 == "." || $0 == ".." }),
                  let digest = inputs[name], digest.utf8.count == 64,
                  digest.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
                throw Failure.invalidMarker
            }
            var raw = [UInt8]()
            var bytes = digest.utf8.makeIterator()
            while let high = bytes.next(), let low = bytes.next() {
                func hex(_ value: UInt8) -> UInt8 { value <= 57 ? value - 48 : value - 87 }
                raw.append(hex(high) * 16 + hex(low))
            }
            hash.update(data: Data(name.utf8))
            hash.update(data: Data([0]))
            hash.update(data: Data(raw))
        }
        return hash.finalize().map { String(format: "%02x", $0) }.joined()
    }
}

/// Same openat/no-follow, bounded read, then identity recheck used by StartupPayloadReader.
/// This binary-only lane avoids changing the existing JavaScript payload reader or its call sites.
private final class VideoDirectoryChain {
    typealias Failure = OptionalStartupVideoFiles.Failure
    private static let directoryFlags = O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC
    private var levels: [(name: String, fd: Int32, identity: stat)] = []
    var lastFD: Int32 { levels[levels.count - 1].fd }
    var parentFD: Int32 { levels[levels.count - 2].fd }
    var lastIdentity: stat { levels[levels.count - 1].identity }

    init(root: URL) throws {
        guard root.isFileURL, (root.host ?? "").isEmpty, root.query == nil, root.fragment == nil,
              root.path.hasPrefix("/") else { throw Failure.unsafePath }
        try remember(root.path, fd: Darwin.open(root.path, Self.directoryFlags))
    }

    func append(_ name: String) throws {
        try remember(name, fd: openat(lastFD, name, Self.directoryFlags))
    }

    private func remember(_ name: String, fd: Int32) throws {
        guard fd >= 0 else { throw Failure.unsafePath }
        var info = stat()
        guard fstat(fd, &info) == 0 else {
            Darwin.close(fd)
            throw Failure.io
        }
        levels.append((name, fd, info))
    }

    func current() -> Bool {
        for (index, level) in levels.enumerated() {
            var named = stat()
            let result = index == 0 ? lstat(level.name, &named)
                : fstatat(levels[index - 1].fd, level.name, &named, AT_SYMLINK_NOFOLLOW)
            guard result == 0, Self.sameNode(level.identity, named) else { return false }
        }
        return true
    }

    func read(_ name: String, limit: Int, allowMissing: Bool = false) throws -> Data? {
        let fd = openat(lastFD, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        if fd < 0 && allowMissing && errno == ENOENT && current() { return nil }
        guard fd >= 0 else { throw Failure.unsafePath }
        defer { Darwin.close(fd) }
        var initial = stat()
        guard fstat(fd, &initial) == 0, initial.st_mode & mode_t(S_IFMT) == mode_t(S_IFREG),
              initial.st_size > 0, initial.st_size <= Int64(limit) else { throw Failure.invalidBounds }
        var bytes = Data()
        var buffer = [UInt8](repeating: 0, count: 65536)
        let expected = Int(initial.st_size)
        while bytes.count < expected {
            let count = min(buffer.count, expected - bytes.count)
            let received = buffer.withUnsafeMutableBytes { Darwin.read(fd, $0.baseAddress, count) }
            if received < 0 && errno == EINTR { continue }
            guard received > 0 else { throw Failure.io }
            bytes.append(contentsOf: buffer[..<received])
        }
        var opened = stat(), named = stat()
        guard fstat(fd, &opened) == 0, fstatat(lastFD, name, &named, AT_SYMLINK_NOFOLLOW) == 0,
              Self.sameFile(initial, opened), Self.sameFile(opened, named), current() else {
            throw Failure.fileChanged
        }
        return bytes
    }

    static func sameNode(_ first: stat, _ second: stat) -> Bool {
        first.st_dev == second.st_dev && first.st_ino == second.st_ino && first.st_mode == second.st_mode
    }

    private static func sameFile(_ first: stat, _ second: stat) -> Bool {
        sameNode(first, second) && first.st_size == second.st_size
            && first.st_mtimespec.tv_sec == second.st_mtimespec.tv_sec
            && first.st_mtimespec.tv_nsec == second.st_mtimespec.tv_nsec
            && first.st_ctimespec.tv_sec == second.st_ctimespec.tv_sec
            && first.st_ctimespec.tv_nsec == second.st_ctimespec.tv_nsec
    }

    deinit { levels.reversed().forEach { Darwin.close($0.fd) } }
}

/// Owns only a fresh 0700 directory and its exact 0400 clip. The AV caller takes a
/// file URL, not a mutable source name, and must keep this lease until it detaches.
@MainActor
final class StartupVideoOwnedFile: StartupVideoTemporaryClip {
    let fileURL: URL
    private let owned: OwnedVideoFileScope

    private init(fileURL: URL, owned: OwnedVideoFileScope) {
        self.fileURL = fileURL
        self.owned = owned
    }

    static func stageAsync(_ bytes: Data, temporaryDirectory: URL = FileManager.default.temporaryDirectory,
                           onOwned: (StartupVideoOwnedFile) throws -> Void = { _ in }) async throws -> StartupVideoOwnedFile {
        let (lease, path, fd) = try openDraft(byteCount: bytes.count, temporaryDirectory: temporaryDirectory)
        defer { Darwin.close(fd) } // the detached borrower cannot outlive this await
        do {
            // The run can unlink this exact private inode immediately on Skip,
            // even if the worker is still writing to its borrowed descriptor.
            try onOwned(lease)
            try Task.checkCancellation()
            let writer = Task.detached(priority: .utility) { try write(bytes, fd: fd) }
            try await withTaskCancellationHandler {
                try await writer.value
            } onCancel: {
                writer.cancel()
            }
            try Task.checkCancellation()
            try lease.seal(path: path, fd: fd, byteCount: bytes.count)
            return lease
        } catch {
            lease.release()
            throw error
        }
    }

    static func stage(_ bytes: Data, temporaryDirectory: URL = FileManager.default.temporaryDirectory) throws -> StartupVideoOwnedFile {
        let (lease, path, fd) = try openDraft(byteCount: bytes.count, temporaryDirectory: temporaryDirectory)
        defer { Darwin.close(fd) }
        try write(bytes, fd: fd)
        try lease.seal(path: path, fd: fd, byteCount: bytes.count)
        return lease
    }

    private static func openDraft(byteCount: Int, temporaryDirectory: URL)
      throws -> (StartupVideoOwnedFile, VideoDirectoryChain, Int32) {
        typealias Failure = OptionalStartupVideoFiles.Failure
        guard (1...OptionalStartupVideoFiles.maxClipBytes).contains(byteCount) else { throw Failure.invalidBounds }
        let path = try VideoDirectoryChain(root: temporaryDirectory)
        let name = "azhou-startup-video-" + UUID().uuidString
        guard mkdirat(path.lastFD, name, 0o700) == 0 else { throw Failure.io }
        try path.append(name)
        guard path.lastIdentity.st_uid == geteuid(), path.lastIdentity.st_mode & 0o777 == 0o700 else {
            throw Failure.unsafePath
        }
        let owned = OwnedVideoFileScope(directory: path, name: name)
        let fd = openat(path.lastFD, "clip.mp4", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw Failure.io }
        var initial = stat()
        guard fstat(fd, &initial) == 0 else { Darwin.close(fd); throw Failure.io }
        owned.identity = initial
        let url = temporaryDirectory.appendingPathComponent(name, isDirectory: true).appendingPathComponent("clip.mp4")
        return (StartupVideoOwnedFile(fileURL: url, owned: owned), path, fd)
    }

    nonisolated private static func write(_ bytes: Data, fd: Int32) throws {
        typealias Failure = OptionalStartupVideoFiles.Failure
        try bytes.withUnsafeBytes { data in
            guard let start = data.baseAddress else { throw Failure.io }
            var offset = 0
            while offset < data.count {
                try Task.checkCancellation()
                let count = min(65536, data.count - offset)
                let written = Darwin.write(fd, start.advanced(by: offset), count)
                if written < 0 && errno == EINTR { continue }
                guard written > 0 else { throw Failure.io }
                offset += written
            }
        }
    }

    private func seal(path: VideoDirectoryChain, fd: Int32, byteCount: Int) throws {
        typealias Failure = OptionalStartupVideoFiles.Failure
        guard path.current() else { throw Failure.fileChanged }
        guard fchmod(fd, 0o400) == 0 else { throw Failure.io }
        var final = stat(), named = stat()
        guard fstat(fd, &final) == 0 else { throw Failure.io }
        owned.identity = final
        guard fstatat(path.lastFD, "clip.mp4", &named, AT_SYMLINK_NOFOLLOW) == 0,
              VideoDirectoryChain.sameNode(final, named), final.st_size == Int64(byteCount),
              path.current() else { throw Failure.fileChanged }
    }

    func release() { owned.release() }
}

private final class OwnedVideoFileScope {
    private var directory: VideoDirectoryChain?
    private let name: String
    var identity: stat?

    init(directory: VideoDirectoryChain, name: String) {
        self.directory = directory
        self.name = name
    }

    func release() {
        guard let directory else { return }
        self.directory = nil
        guard directory.current() else { return }
        if let identity {
            var named = stat()
            guard fstatat(directory.lastFD, "clip.mp4", &named, AT_SYMLINK_NOFOLLOW) == 0,
                  VideoDirectoryChain.sameNode(identity, named),
                  unlinkat(directory.lastFD, "clip.mp4", 0) == 0 else { return }
        }
        // Directory removal is deliberately nonrecursive: replacements and unexpected contents survive.
        if directory.current() { _ = unlinkat(directory.parentFD, name, AT_REMOVEDIR) }
    }

    deinit { release() }
}
