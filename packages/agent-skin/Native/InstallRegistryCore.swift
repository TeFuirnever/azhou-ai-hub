import CoreServices
import Foundation

private let projectID = "azhou.codex-startup-animation"
private let currentIdentity = ("local.azhou.codex-startup", "AzhouCodexStartup")
private let knownBundleIDs = [
    "local.azhou.codex-startup",
    "local.aemeath.startup",
    "local.aemeath.extension",
]

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

enum InstallRegistryCLI {
    static func execute(arguments: [String], platform: any InstallRegistryPlatform) -> InstallRegistryResult {
        do {
            if arguments == ["inventory"] {
                return InstallRegistryResult(output: inventory(platform: platform), exitCode: 0)
            }
            if arguments.count == 2, arguments[0] == "register" {
                let status = try register(arguments[1], platform: platform)
                return InstallRegistryResult(
                    output: ["schema": 1, "operation": "register", "path": arguments[1], "status": status, "ok": status == noErr],
                    exitCode: status == noErr ? 0 : 1
                )
            }
            throw RegistryFailure("usage: azhou-install-registry inventory | register ABSOLUTE_APP_PATH")
        } catch {
            return InstallRegistryResult(output: ["schema": 1, "ok": false, "error": String(describing: error)], exitCode: 1)
        }
    }

    private static func info(at url: URL) -> [String: Any]? {
        guard let data = try? Data(contentsOf: url.appendingPathComponent("Contents/Info.plist")) else { return nil }
        return (try? PropertyListSerialization.propertyList(from: data, options: [], format: nil)) as? [String: Any]
    }

    private static func inventory(platform: any InstallRegistryPlatform) -> [String: Any] {
        let manager = FileManager.default
        let applications: [[String: Any]] = knownBundleIDs.map { identifier in
            var seen = Set<String>()
            let urls = platform.urlsForApplications(withBundleIdentifier: identifier)
            let entries: [[String: Any]] = urls.compactMap { url in
                let path = url.standardizedFileURL.path
                guard seen.insert(path).inserted else { return nil }
                let metadata = info(at: url)
                var isDirectory: ObjCBool = false
                let exists = manager.fileExists(atPath: path, isDirectory: &isDirectory)
                return [
                    "path": path,
                    "realPath": url.resolvingSymlinksInPath().standardizedFileURL.path,
                    "exists": exists,
                    "isDirectory": isDirectory.boolValue,
                    "bundleID": metadata?["CFBundleIdentifier"] ?? NSNull(),
                    "executable": metadata?["CFBundleExecutable"] ?? NSNull(),
                ]
            }
            return ["bundleID": identifier, "urls": entries]
        }
        return ["schema": 1, "operation": "inventory", "applications": applications]
    }

    private static func register(_ path: String, platform: any InstallRegistryPlatform) throws -> OSStatus {
        guard path.hasPrefix("/") else { throw RegistryFailure("register requires an absolute application path") }
        let url = URL(fileURLWithPath: path, isDirectory: true).standardizedFileURL
        let applications = platform.homeDirectory
            .appendingPathComponent("Applications", isDirectory: true).standardizedFileURL
        guard url.deletingLastPathComponent().path == applications.path,
              url.pathExtension == "app",
              url.resolvingSymlinksInPath().path == url.path else {
            throw RegistryFailure("register accepts only the canonical user Applications entry without symlinks")
        }
        guard let metadata = info(at: url),
              metadata["CFBundleIdentifier"] as? String == currentIdentity.0,
              metadata["CFBundleExecutable"] as? String == currentIdentity.1 else {
            throw RegistryFailure("application identity does not match the project launcher")
        }
        guard let bundleName = metadata["CFBundleName"] as? String,
              !bundleName.isEmpty,
              !bundleName.contains("/"),
              url.lastPathComponent == bundleName + ".app" else {
            throw RegistryFailure("application path does not match its built bundle name")
        }
        let executable = url.appendingPathComponent("Contents/MacOS/" + currentIdentity.1)
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            throw RegistryFailure("project launcher executable is missing")
        }
        let markerURL = url.appendingPathComponent("Contents/Resources/azhou-build.json")
        let markerData = try Data(contentsOf: markerURL)
        guard let marker = try JSONSerialization.jsonObject(with: markerData) as? [String: Any],
              marker["schema"] as? Int == 1,
              marker["projectID"] as? String == projectID,
              marker["bundleID"] as? String == currentIdentity.0,
              marker["executable"] as? String == currentIdentity.1,
              let root = marker["projectRoot"] as? String, root.hasPrefix("/"),
              let version = marker["version"] as? String, !version.isEmpty,
              let build = marker["build"] as? String, !build.isEmpty,
              version == metadata["CFBundleShortVersionString"] as? String,
              build == metadata["CFBundleVersion"] as? String,
              let inputSHA = marker["inputSHA256"] as? String,
              inputSHA.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil else {
            throw RegistryFailure("build provenance marker is missing or inconsistent")
        }
        // The installer has already verified the exact package fingerprint,
        // current projectRoot and codesign before reaching this operation.
        return platform.register(url)
    }

    static func emit(_ value: [String: Any], to handle: FileHandle = .standardOutput) throws {
        let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .withoutEscapingSlashes])
        handle.write(data)
        handle.write(Data([10]))
    }
}
