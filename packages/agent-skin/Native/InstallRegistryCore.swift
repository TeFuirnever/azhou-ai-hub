import CoreServices
import Darwin
import Foundation

private let projectID = "azhou.codex-startup-animation"
private let currentIdentity = ("local.azhou.codex-startup", "AzhouCodexStartup")
private let knownBundleIDs = ["local.azhou.codex-startup", "local.aemeath.startup", "local.aemeath.extension"]

struct RegistryFailure: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) { self.description = description }
}

protocol InstallRegistryPlatform {
    var homeDirectory: URL { get }
    func urlsForApplications(withBundleIdentifier identifier: String) -> [URL]
    func register(_ url: URL) -> OSStatus
}

struct InstallRegistryResult {
    let output: [String: Any]
    let exitCode: Int32
}

struct RegistryFileEvidence {
    private static let limit = 1_048_576
    let url: URL
    let device: dev_t
    let inode: ino_t
    let bytes: Data

    private static func sameFile(_ left: stat, _ right: stat) -> Bool {
        left.st_dev == right.st_dev && left.st_ino == right.st_ino && left.st_mode == right.st_mode
            && left.st_size == right.st_size
            && left.st_mtimespec.tv_sec == right.st_mtimespec.tv_sec
            && left.st_mtimespec.tv_nsec == right.st_mtimespec.tv_nsec
            && left.st_ctimespec.tv_sec == right.st_ctimespec.tv_sec
            && left.st_ctimespec.tv_nsec == right.st_ctimespec.tv_nsec
    }

    static func capture(_ url: URL) throws -> RegistryFileEvidence {
        func refused() -> RegistryFailure { RegistryFailure("registration file is missing, unsafe, oversized, or changed") }
        var before = stat()
        guard url.isFileURL, lstat(url.path, &before) == 0, (before.st_mode & S_IFMT) == S_IFREG,
              before.st_size >= 0, before.st_size <= limit else { throw refused() }
        let descriptor = open(url.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard descriptor >= 0 else { throw refused() }
        defer { close(descriptor) }
        var opened = stat()
        guard fstat(descriptor, &opened) == 0, sameFile(before, opened) else { throw refused() }
        var bytes = Data(), buffer = [UInt8](repeating: 0, count: 16_384)
        while true {
            let count = Darwin.read(descriptor, &buffer, buffer.count)
            if count < 0 && errno == EINTR { continue }
            guard count >= 0 else { throw refused() }
            if count == 0 { break }
            guard bytes.count + count <= limit else { throw refused() }
            bytes.append(contentsOf: buffer.prefix(count))
        }
        var after = stat(), current = stat()
        guard fstat(descriptor, &after) == 0, lstat(url.path, &current) == 0,
              sameFile(opened, after), sameFile(after, current), bytes.count == after.st_size else { throw refused() }
        return RegistryFileEvidence(url: url, device: opened.st_dev, inode: opened.st_ino, bytes: bytes)
    }

    func matchesCurrent() -> Bool {
        guard let current = try? Self.capture(url) else { return false }
        return device == current.device && inode == current.inode && bytes == current.bytes
    }
}

private struct BuildMarker: Decodable {
    let schema: Int
    let projectID: String
    let bundleID: String
    let executable: String
    let projectRoot: String
    let version: String
    let build: String
    let inputSHA256: String
}

struct RegistrationEvidence {
    let application: URL
    let info: RegistryFileEvidence
    let marker: RegistryFileEvidence
    let executable: URL

    func isCurrent() -> Bool {
        application.resolvingSymlinksInPath().path == application.path
            && FileManager.default.isExecutableFile(atPath: executable.path)
            && info.matchesCurrent() && marker.matchesCurrent()
    }
}

enum InstallRegistryCLI {
    private enum Command {
        case inventory
        case register(String)

        init(_ arguments: [String]) throws {
            switch arguments.count {
            case 1 where arguments[0] == "inventory": self = .inventory
            case 2 where arguments[0] == "register": self = .register(arguments[1])
            default: throw RegistryFailure("usage: azhou-install-registry inventory | register ABSOLUTE_APP_PATH")
            }
        }
    }

    static func execute(arguments: [String], platform: any InstallRegistryPlatform) -> InstallRegistryResult {
        do {
            switch try Command(arguments) {
            case .inventory:
                return InstallRegistryResult(output: inventory(platform: platform), exitCode: 0)
            case .register(let path):
                let evidence = try inspect(path, home: platform.homeDirectory)
                guard evidence.isCurrent() else { throw RegistryFailure("registration evidence changed before use") }
                let status = platform.register(evidence.application)
                return InstallRegistryResult(output: ["schema": 1, "operation": "register", "path": path,
                                                      "status": status, "ok": status == noErr],
                                             exitCode: status == noErr ? 0 : 1)
            }
        } catch {
            return InstallRegistryResult(output: ["schema": 1, "ok": false, "error": String(describing: error)], exitCode: 1)
        }
    }

    private static func properties(_ data: Data) -> [String: Any]? {
        (try? PropertyListSerialization.propertyList(from: data, options: [], format: nil)) as? [String: Any]
    }

    private static func inventory(platform: any InstallRegistryPlatform) -> [String: Any] {
        let applications: [[String: Any]] = knownBundleIDs.map { identifier in
            var seen = Set<String>()
            var entries: [[String: Any]] = []
            for url in platform.urlsForApplications(withBundleIdentifier: identifier) {
                let path = url.standardizedFileURL.path
                if !seen.insert(path).inserted { continue }
                var directory: ObjCBool = false
                let exists = FileManager.default.fileExists(atPath: path, isDirectory: &directory)
                let evidence = try? RegistryFileEvidence.capture(url.appendingPathComponent("Contents/Info.plist"))
                let metadata = evidence.flatMap { properties($0.bytes) }
                entries.append(["path": path, "realPath": url.resolvingSymlinksInPath().standardizedFileURL.path,
                                "exists": exists, "isDirectory": directory.boolValue,
                                "bundleID": metadata?["CFBundleIdentifier"] ?? NSNull(),
                                "executable": metadata?["CFBundleExecutable"] ?? NSNull()])
            }
            return ["bundleID": identifier, "urls": entries]
        }
        return ["schema": 1, "operation": "inventory", "applications": applications]
    }

    static func inspect(_ path: String, home: @autoclosure () -> URL) throws -> RegistrationEvidence {
        guard path.hasPrefix("/") else { throw RegistryFailure("register requires an absolute application path") }
        let application = URL(fileURLWithPath: path, isDirectory: true).standardizedFileURL
        let applications = home().appendingPathComponent("Applications", isDirectory: true).standardizedFileURL
        guard application.deletingLastPathComponent().path == applications.path,
              application.pathExtension == "app", application.resolvingSymlinksInPath().path == application.path else {
            throw RegistryFailure("register accepts only the canonical user Applications entry without symlinks")
        }
        guard let info = try? RegistryFileEvidence.capture(application.appendingPathComponent("Contents/Info.plist")),
              let metadata = properties(info.bytes),
              metadata["CFBundleIdentifier"] as? String == currentIdentity.0,
              metadata["CFBundleExecutable"] as? String == currentIdentity.1 else {
            throw RegistryFailure("application identity does not match the project launcher")
        }
        guard let name = metadata["CFBundleName"] as? String, !name.isEmpty, !name.contains("/"),
              application.lastPathComponent == name + ".app" else {
            throw RegistryFailure("application path does not match its built bundle name")
        }
        let executable = application.appendingPathComponent("Contents/MacOS/" + currentIdentity.1)
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            throw RegistryFailure("project launcher executable is missing")
        }
        let marker = try RegistryFileEvidence.capture(application.appendingPathComponent("Contents/Resources/azhou-build.json"))
        guard let build = try? JSONDecoder().decode(BuildMarker.self, from: marker.bytes),
              build.schema == 1, build.projectID == projectID, build.bundleID == currentIdentity.0,
              build.executable == currentIdentity.1, build.projectRoot.hasPrefix("/"),
              !build.version.isEmpty, !build.build.isEmpty,
              build.version == metadata["CFBundleShortVersionString"] as? String,
              build.build == metadata["CFBundleVersion"] as? String,
              build.inputSHA256.utf8.count == 64,
              build.inputSHA256.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
            throw RegistryFailure("build provenance marker is missing or inconsistent")
        }
        return RegistrationEvidence(application: application, info: info, marker: marker, executable: executable)
    }

    static func emit(_ value: [String: Any], to handle: FileHandle = .standardOutput) throws {
        let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .withoutEscapingSlashes])
        handle.write(data)
        handle.write(Data([10]))
    }
}
