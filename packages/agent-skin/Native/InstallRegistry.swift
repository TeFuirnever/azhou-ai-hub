import AppKit
import CoreServices
import Foundation

// A narrow CLI for public Launch Services APIs. It does not launch, terminate,
// hide, unregister, remove, or reset anything. The installer owns filesystem
// verification and any targeted, host-supported lsregister maintenance.
private let projectID = "azhou.codex-startup-animation"
private let applicationName = "阿舟 AI 实验室.app"
private let currentIdentity = ("local.azhou.codex-startup", "AzhouCodexStartup")
private let knownBundleIDs = [
    "local.azhou.codex-startup",
    "local.aemeath.startup",
    "local.aemeath.extension",
]

private struct RegistryFailure: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) { self.description = description }
}

private func emit(_ value: [String: Any]) throws {
    let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .withoutEscapingSlashes])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data([10]))
}

private func info(at url: URL) -> [String: Any]? {
    guard let data = try? Data(contentsOf: url.appendingPathComponent("Contents/Info.plist")) else { return nil }
    return (try? PropertyListSerialization.propertyList(from: data, options: [], format: nil)) as? [String: Any]
}

private func inventory() -> [String: Any] {
    let manager = FileManager.default
    let applications: [[String: Any]] = knownBundleIDs.map { identifier in
        var seen = Set<String>()
        let urls = NSWorkspace.shared.urlsForApplications(withBundleIdentifier: identifier)
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

private func register(_ path: String) throws -> OSStatus {
    guard path.hasPrefix("/") else { throw RegistryFailure("register requires an absolute application path") }
    let url = URL(fileURLWithPath: path, isDirectory: true).standardizedFileURL
    let expected = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Applications", isDirectory: true)
        .appendingPathComponent(applicationName, isDirectory: true).standardizedFileURL
    guard url.path == expected.path,
          url.resolvingSymlinksInPath().path == url.path else {
        throw RegistryFailure("register accepts only the canonical user Applications entry without symlinks")
    }
    guard let metadata = info(at: url),
          metadata["CFBundleIdentifier"] as? String == currentIdentity.0,
          metadata["CFBundleExecutable"] as? String == currentIdentity.1 else {
        throw RegistryFailure("application identity does not match the project launcher")
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
    return LSRegisterURL(url as CFURL, true)
}

do {
    let arguments = Array(CommandLine.arguments.dropFirst())
    if arguments == ["inventory"] {
        try emit(inventory())
    } else if arguments.count == 2, arguments[0] == "register" {
        let status = try register(arguments[1])
        try emit(["schema": 1, "operation": "register", "path": arguments[1], "status": status, "ok": status == noErr])
        if status != noErr { exit(1) }
    } else {
        throw RegistryFailure("usage: azhou-install-registry inventory | register ABSOLUTE_APP_PATH")
    }
} catch {
    try? emit(["schema": 1, "ok": false, "error": String(describing: error)])
    exit(1)
}
