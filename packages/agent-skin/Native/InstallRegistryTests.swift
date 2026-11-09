// Compile with Native/InstallRegistryCore.swift; production adapter and CLI stay separate.
import Foundation
import CoreServices
import Darwin

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
        expect(relative.exitCode == 1 && platform.homeReadCount == 0
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
            // InstallRegistryCore binds this field to the physical .app path.
            "CFBundleName": "阿舟 AI 实验室",
            "CFBundleDisplayName": "阿舟 AI 实验室",
            "CFBundleShortVersionString": "0.9.0",
            "CFBundleVersion": "23",
            "CFBundleDevelopmentRegion": "en",
            "CFBundleLocalizations": ["en", "zh-Hans"],
        ]
        let executable = application.appendingPathComponent("Contents/MacOS/AzhouCodexStartup")
        let markerURL = application.appendingPathComponent("Contents/Resources/azhou-build.json")
        try FileManager.default.createDirectory(at: executable.deletingLastPathComponent(), withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: markerURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("#!/bin/sh\nexit 0\n".utf8).write(to: executable)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: executable.path)
        for (locale, name) in [("en", "Azhou AI Lab for Codex"), ("zh-Hans", "阿舟 AI 实验室 for Codex")] {
            let localized = application.appendingPathComponent("Contents/Resources/\(locale).lproj/InfoPlist.strings")
            try FileManager.default.createDirectory(at: localized.deletingLastPathComponent(), withIntermediateDirectories: true)
            let value = "\"CFBundleDisplayName\" = \"\(name)\";\n\"CFBundleName\" = \"\(name)\";\n"
            try Data(value.utf8).write(to: localized)
        }

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
            "projectRoot": root.path, "version": "0.9.0", "build": "23",
            "inputSHA256": String(repeating: "a", count: 64),
        ]
        func writeMarker() throws {
            try JSONSerialization.data(withJSONObject: marker, options: [.sortedKeys]).write(to: markerURL)
        }
        for (key, invalid): (String, Any) in [
            ("schema", 2), ("schema", true), ("projectID", "other.project"), ("bundleID", "other.bundle"),
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
                "projectRoot": root.path, "version": "0.9.0", "build": "23",
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
               "the Codex display labels register through the real core while the bundle name stays path-aligned")

        var mismatchedCandidateInfo = infoValues
        mismatchedCandidateInfo["CFBundleName"] = "阿舟 AI 实验室 for Codex"
        try writeInfo(at: application, values: mismatchedCandidateInfo)
        let candidateNameAsPath = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(candidateNameAsPath.exitCode == 1
               && candidateNameAsPath.output["error"] as? String == "application path does not match its built bundle name",
               "the Codex display label cannot replace the established installation basename")
        try writeInfo(at: application, values: infoValues)

        let custom = root.appendingPathComponent("Applications/自定义实验室.app", isDirectory: true)
        try FileManager.default.copyItem(at: application, to: custom)
        var customInfo = infoValues
        customInfo["CFBundleName"] = "自定义实验室"
        customInfo["CFBundleDisplayName"] = "自定义实验室"
        try writeInfo(at: custom, values: customInfo)
        let customRegistration = InstallRegistryCLI.execute(arguments: ["register", custom.path], platform: platform)
        expect(customRegistration.exitCode == 0 && platform.registeredPaths.last == custom.path,
               "register accepts the verified custom installation name")
        let registrationsBeforeMismatch = platform.registeredPaths.count
        customInfo["CFBundleName"] = "另一个名称"
        try writeInfo(at: custom, values: customInfo)
        let mismatchedName = InstallRegistryCLI.execute(arguments: ["register", custom.path], platform: platform)
        expect(mismatchedName.exitCode == 1 && platform.registeredPaths.count == registrationsBeforeMismatch,
               "register rejects a path that does not match the built bundle name")

        let infoURL = application.appendingPathComponent("Contents/Info.plist")
        let validInfo = try Data(contentsOf: infoURL)
        let validMarker = try Data(contentsOf: markerURL)
        let outside = root.appendingPathComponent("outside-marker.json")
        try validMarker.write(to: outside)
        try FileManager.default.removeItem(at: markerURL)
        try FileManager.default.createSymbolicLink(at: markerURL, withDestinationURL: outside)
        let beforeLinkedMarker = platform.registeredPaths.count
        let linkedMarker = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(linkedMarker.exitCode == 1 && platform.registeredPaths.count == beforeLinkedMarker,
               "registration refuses a linked marker without invoking the backend")
        try FileManager.default.removeItem(at: markerURL)
        try validMarker.write(to: markerURL)

        let outsideInfo = root.appendingPathComponent("outside-info.plist")
        try validInfo.write(to: outsideInfo)
        try FileManager.default.removeItem(at: infoURL)
        try FileManager.default.createSymbolicLink(at: infoURL, withDestinationURL: outsideInfo)
        let beforeLinkedInfo = platform.registeredPaths.count
        let linkedInfo = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(linkedInfo.exitCode == 1 && platform.registeredPaths.count == beforeLinkedInfo,
               "registration refuses linked bundle metadata without invoking the backend")
        try FileManager.default.removeItem(at: infoURL)
        try validInfo.write(to: infoURL)

        try FileManager.default.removeItem(at: markerURL)
        guard mkfifo(markerURL.path, 0o600) == 0 else { throw NSError(domain: "fixture-fifo", code: Int(errno)) }
        let beforeFIFO = platform.registeredPaths.count
        let fifo = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(fifo.exitCode == 1 && platform.registeredPaths.count == beforeFIFO,
               "a FIFO marker is rejected without registration")
        try FileManager.default.removeItem(at: markerURL)
        try validMarker.write(to: markerURL)

        var oversized = validMarker
        oversized.append(Data(repeating: 32, count: 1_048_577))
        try oversized.write(to: markerURL)
        let beforeOversized = platform.registeredPaths.count
        let tooLarge = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(tooLarge.exitCode == 1 && platform.registeredPaths.count == beforeOversized,
               "an oversized marker is rejected before registration")
        try validMarker.write(to: markerURL)

        try Data().write(to: markerURL)
        let beforeEmpty = platform.registeredPaths.count
        let emptyMarker = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(emptyMarker.exitCode == 1 && platform.registeredPaths.count == beforeEmpty,
               "an empty marker cannot authorize registration")
        try validMarker.write(to: markerURL)

        var oversizedInfo = validInfo
        oversizedInfo.append(Data(repeating: 32, count: 1_048_577))
        try oversizedInfo.write(to: infoURL)
        let beforeOversizedInfo = platform.registeredPaths.count
        let tooLargeInfo = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(tooLargeInfo.exitCode == 1 && platform.registeredPaths.count == beforeOversizedInfo,
               "oversized bundle metadata cannot authorize registration")
        try validInfo.write(to: infoURL)

        let binaryInfo = try PropertyListSerialization.data(fromPropertyList: infoValues, format: .binary, options: 0)
        try binaryInfo.write(to: infoURL)
        let binaryResult = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(binaryResult.exitCode == 0 && platform.registeredPaths.last == application.path,
               "binary plist remains compatible with a valid build marker")
        try validInfo.write(to: infoURL)

        try FileManager.default.removeItem(at: infoURL)
        guard mkfifo(infoURL.path, 0o600) == 0 else { throw NSError(domain: "fixture-fifo", code: Int(errno)) }
        let beforeInfoFIFO = platform.registeredPaths.count
        let infoFIFO = InstallRegistryCLI.execute(arguments: ["register", application.path], platform: platform)
        expect(infoFIFO.exitCode == 1 && platform.registeredPaths.count == beforeInfoFIFO,
               "a FIFO plist is rejected without registration")
        try FileManager.default.removeItem(at: infoURL)
        try validInfo.write(to: infoURL)

        let inventoryInfo = inventoryBundle.appendingPathComponent("Contents/Info.plist")
        try FileManager.default.removeItem(at: inventoryInfo)
        try FileManager.default.createSymbolicLink(at: inventoryInfo, withDestinationURL: outsideInfo)
        let linkedInventory = InstallRegistryCLI.execute(arguments: ["inventory"], platform: platform)
        let linkedApplications = linkedInventory.output["applications"] as? [[String: Any]] ?? []
        let linkedURLs = linkedApplications.first(where: { $0["bundleID"] as? String == "local.azhou.codex-startup" })?["urls"] as? [[String: Any]] ?? []
        expect(linkedURLs.count == 1 && linkedURLs[0]["bundleID"] is NSNull && linkedURLs[0]["executable"] is NSNull,
               "inventory keeps the path but does not trust linked metadata")

        let capturedRegistration = try InstallRegistryCLI.inspect(application.path, home: root)
        let beforeCaptureChange = platform.registeredPaths.count
        expect(capturedRegistration.isCurrent(), "valid registration evidence remains current")
        let heldMarker = root.appendingPathComponent("held-marker.json")
        try FileManager.default.moveItem(at: markerURL, to: heldMarker)
        try validMarker.write(to: markerURL)
        expect(!capturedRegistration.isCurrent() && platform.registeredPaths.count == beforeCaptureChange,
               "registration evidence rejects a same-byte marker replacement before backend use")
        try FileManager.default.removeItem(at: markerURL)
        try FileManager.default.moveItem(at: heldMarker, to: markerURL)
        let capturedInfoRegistration = try InstallRegistryCLI.inspect(application.path, home: root)
        try Data("changed".utf8).write(to: infoURL)
        expect(!capturedInfoRegistration.isCurrent() && platform.registeredPaths.count == beforeCaptureChange,
               "registration evidence rejects changed plist bytes before backend use")
        try validInfo.write(to: infoURL)

        do {
            _ = try RegistryFileEvidence.capture(URL(string: "https://example.invalid/Info.plist")!)
            fatalError("non-file URL unexpectedly accepted")
        } catch {
            expect(true, "file evidence rejects non-file URLs")
        }
        let boundaryFile = root.appendingPathComponent("boundary.bin")
        try Data(repeating: 1, count: 1_048_576).write(to: boundaryFile)
        let boundaryEvidence = try RegistryFileEvidence.capture(boundaryFile)
        expect(boundaryEvidence.bytes.count == 1_048_576 && boundaryEvidence.matchesCurrent(),
               "the documented exact size limit remains readable")

        let evidenceFile = root.appendingPathComponent("evidence.txt")
        let savedEvidence = root.appendingPathComponent("saved-evidence.txt")
        try Data("first".utf8).write(to: evidenceFile)
        let evidence = try RegistryFileEvidence.capture(evidenceFile)
        expect(evidence.matchesCurrent(), "captured file evidence matches its original entity and bytes")
        try Data("other".utf8).write(to: evidenceFile)
        expect(!evidence.matchesCurrent(), "in-place evidence content changes are rejected")
        try Data("first".utf8).write(to: evidenceFile)
        try FileManager.default.moveItem(at: evidenceFile, to: savedEvidence)
        try Data("first".utf8).write(to: evidenceFile)
        expect(!evidence.matchesCurrent(), "identical replacement bytes cannot claim the captured entity")

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
    private let home: URL
    private(set) var homeReadCount = 0
    var homeDirectory: URL { homeReadCount += 1; return home }
    var applications: [String: [URL]] = [:]
    var registerStatus: OSStatus = noErr
    private(set) var registeredPaths: [String] = []

    init(homeDirectory: URL) { self.home = homeDirectory }
    func urlsForApplications(withBundleIdentifier identifier: String) -> [URL] {
        applications[identifier] ?? []
    }
    func register(_ url: URL) -> OSStatus {
        registeredPaths.append(url.path)
        return registerStatus
    }
}
