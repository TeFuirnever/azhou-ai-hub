// Compile with Native/InstallRegistryCore.swift; production adapter and CLI stay separate.
import Foundation
import CoreServices

@main
struct InstallRegistryTests {
    static func main() throws {
        var checks = 0
        func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
            guard condition() else { fatalError("FAILED: \(label)") }
            checks += 1
        }

        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let platform = FakeInstallRegistryPlatform(homeDirectory: root)

        let inventoryBundle = root.appendingPathComponent("Codex.app", isDirectory: true)
        try writeInfo(at: inventoryBundle, values: [
            "CFBundleIdentifier": "com.openai.codex", "CFBundleExecutable": "Codex",
        ])
        platform.applications = ["local.azhou.codex-startup": [inventoryBundle, inventoryBundle]]
        let inventory = InstallRegistryCLI.execute(arguments: ["inventory"], platform: platform)
        let applications = inventory.output["applications"] as? [[String: Any]] ?? []
        let firstURLs = applications.first(where: { $0["bundleID"] as? String == "local.azhou.codex-startup" })?["urls"] as? [[String: Any]] ?? []
        expect(inventory.exitCode == 0 && inventory.output["schema"] as? Int == 1,
               "inventory returns the versioned success envelope")
        expect(applications.count == 3 && firstURLs.count == 1,
               "inventory includes all known identities and deduplicates exact paths")
        expect(firstURLs[0]["bundleID"] as? String == "com.openai.codex"
               && firstURLs[0]["executable"] as? String == "Codex"
               && firstURLs[0]["exists"] as? Bool == true
               && firstURLs[0]["isDirectory"] as? Bool == true,
               "inventory reports bundle metadata and directory state from the supplied catalog")
        let unknownOperation = InstallRegistryCLI.execute(arguments: ["unknown"], platform: platform)
        expect(unknownOperation.exitCode == 1
               && (unknownOperation.output["error"] as? String)?.hasPrefix("usage:") == true,
               "unknown commands return a bounded usage error")

        let relative = InstallRegistryCLI.execute(arguments: ["register", "relative.app"], platform: platform)
        expect(relative.exitCode == 1
               && relative.output["error"] as? String == "register requires an absolute application path",
               "register rejects relative paths before platform access")
        let wrongPath = InstallRegistryCLI.execute(arguments: ["register", "/tmp/other.app"], platform: platform)
        expect(wrongPath.exitCode == 1
               && wrongPath.output["error"] as? String == "register accepts only the canonical user Applications entry without symlinks",
               "register rejects paths outside the one canonical per-user entry")
        expect(platform.registeredPaths.isEmpty,
               "refused paths never call the Launch Services backend")

        let application = root.appendingPathComponent("Applications/阿舟 AI 实验室.app", isDirectory: true)
        let infoValues: [String: Any] = [
            "CFBundleIdentifier": "local.azhou.codex-startup",
            "CFBundleExecutable": "AzhouCodexStartup",
            "CFBundleShortVersionString": "1.2.3",
            "CFBundleVersion": "123",
        ]
        let executable = application.appendingPathComponent("Contents/MacOS/AzhouCodexStartup")
        let markerURL = application.appendingPathComponent("Contents/Resources/azhou-build.json")
        try FileManager.default.createDirectory(at: executable.deletingLastPathComponent(), withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: markerURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("#!/bin/sh\nexit 0\n".utf8).write(to: executable)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: executable.path)

        let missingInfo = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(missingInfo.output["error"] as? String == "application identity does not match the project launcher",
               "register refuses a missing bundle identity")
        try writeInfo(at: application, values: ["CFBundleIdentifier": "other.bundle", "CFBundleExecutable": "AzhouCodexStartup"])
        let wrongIdentity = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(wrongIdentity.output["error"] as? String == "application identity does not match the project launcher",
               "register refuses a different bundle identifier")
        try writeInfo(at: application, values: ["CFBundleIdentifier": "local.azhou.codex-startup", "CFBundleExecutable": "other"])
        let wrongExecutable = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(wrongExecutable.output["error"] as? String == "application identity does not match the project launcher",
               "register refuses a different launcher executable")

        try writeInfo(at: application, values: infoValues)
        try FileManager.default.removeItem(at: executable)
        let missingExecutable = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(missingExecutable.output["error"] as? String == "project launcher executable is missing",
               "register requires an executable launcher")
        try Data("#!/bin/sh\nexit 0\n".utf8).write(to: executable)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: executable.path)

        let missingMarker = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(missingMarker.exitCode == 1 && platform.registeredPaths.isEmpty,
               "register refuses a missing build marker without calling Launch Services")
        try Data("not json".utf8).write(to: markerURL)
        let malformedMarker = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(malformedMarker.exitCode == 1 && platform.registeredPaths.isEmpty,
               "register refuses malformed provenance JSON")

        var marker: [String: Any] = [
            "schema": 1, "projectID": "azhou.codex-startup-animation",
            "bundleID": "local.azhou.codex-startup", "executable": "AzhouCodexStartup",
            "projectRoot": root.path, "version": "1.2.3", "build": "123",
            "inputSHA256": String(repeating: "a", count: 64),
        ]
        func writeMarker() throws {
            try JSONSerialization.data(withJSONObject: marker, options: [.sortedKeys]).write(to: markerURL)
        }
        for (key, invalid): (String, Any) in [
            ("schema", 2), ("projectID", "other.project"), ("bundleID", "other.bundle"),
            ("executable", "other"), ("projectRoot", "relative/path"), ("version", ""),
            ("build", ""), ("inputSHA256", String(repeating: "A", count: 64)),
        ] {
            marker[key] = invalid
            try writeMarker()
            let result = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
            expect(result.exitCode == 1 && result.output["error"] as? String == "build provenance marker is missing or inconsistent",
                   "register rejects inconsistent marker field \(key)")
            marker[key] = [
                "schema": 1, "projectID": "azhou.codex-startup-animation",
                "bundleID": "local.azhou.codex-startup", "executable": "AzhouCodexStartup",
                "projectRoot": root.path, "version": "1.2.3", "build": "123",
                "inputSHA256": String(repeating: "a", count: 64),
            ][key]
        }
        try writeMarker()
        platform.registerStatus = -10810
        let registrationFailure = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(registrationFailure.exitCode == 1 && registrationFailure.output["ok"] as? Bool == false
               && registrationFailure.output["status"] as? Int32 == -10810,
               "nonzero Launch Services status remains a failed operation")
        expect(platform.registeredPaths == [application.path],
               "the fake backend receives the canonical bundle only after every local check passes")
        platform.registerStatus = noErr
        let registrationSuccess = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(registrationSuccess.exitCode == 0 && registrationSuccess.output["ok"] as? Bool == true,
               "a verified synthetic bundle returns the successful register receipt")

        let output = root.appendingPathComponent("receipt.json")
        FileManager.default.createFile(atPath: output.path, contents: nil)
        let handle = try FileHandle(forWritingTo: output)
        defer { try? handle.close() }
        try InstallRegistryCLI.emit(registrationSuccess.output, to: handle)
        let receipt = try String(contentsOf: output, encoding: .utf8)
        let parsedReceipt = try JSONSerialization.jsonObject(with: Data(receipt.utf8))
        expect(receipt.hasSuffix("\n") && parsedReceipt is [String: Any],
               "registry receipts are one-line JSON")

        print("Install registry checks passed: \(checks). Scope: fake Launch Services backend and temporary synthetic bundle only.")
    }

    private static func writeInfo(at bundle: URL, values: [String: Any]) throws {
        let path = bundle.appendingPathComponent("Contents/Info.plist")
        try FileManager.default.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
        let data = try PropertyListSerialization.data(fromPropertyList: values, format: .xml, options: 0)
        try data.write(to: path)
    }
}

private final class FakeInstallRegistryPlatform: InstallRegistryPlatform {
    let homeDirectory: URL
    var applications: [String: [URL]] = [:]
    var registerStatus: OSStatus = noErr
    private(set) var registeredPaths: [String] = []

    init(homeDirectory: URL) { self.homeDirectory = homeDirectory }
    func urlsForApplications(withBundleIdentifier identifier: String) -> [URL] {
        applications[identifier] ?? []
    }
    func register(_ url: URL) -> OSStatus {
        registeredPaths.append(url.path)
        return registerStatus
    }
}
