// Compile separately from the application; no private assets or live target.
// swiftc Native/Wallpaper.swift Native/WallpaperValidationTests.swift \
//   -o .build/wallpaper-validation-tests -framework AppKit
import Foundation

@main
struct WallpaperValidationTests {
    static func main() throws {
        var checks = 0
        func expect(_ condition: @autoclosure () throws -> Bool, _ label: String) throws {
            guard try condition() else { fatalError("FAILED: \(label)") }; checks += 1
        }
        func refuses(_ label: String, _ operation: () throws -> Void) {
            do { try operation(); fatalError("FAILED: \(label)") }
            catch { checks += 1 }
        }
        try expect(WallpaperMessages.localized(
            chinese: "壁纸操作未完成。", english: "The wallpaper operation did not finish.",
            preferredLanguages: ["en-GB"]
        ) == "The wallpaper operation did not finish.", "wallpaper messages follow an English system preference")
        try expect(WallpaperMessages.localized(
            chinese: "壁纸操作未完成。", english: "The wallpaper operation did not finish.",
            preferredLanguages: ["zh-Hans"]
        ) == "壁纸操作未完成。", "wallpaper messages follow a Chinese system preference")
        try expect(try WallpaperValidation.loopbackPorts("p123\nn127.0.0.1:49221\n", pid: 123) == [49221], "exact PID loopback listener")
        try expect(try WallpaperValidation.loopbackPorts("p123\nn127.0.0.1:49221\nn*:49221\n", pid: 123).isEmpty, "wildcard on the same port is refused")
        try expect(try WallpaperValidation.loopbackPorts("p123\nn[::1]:49221\nn192.168.1.2:49222\n", pid: 123).isEmpty, "non-IPv4-loopback listeners are refused")
        try expect(try WallpaperValidation.loopbackPorts("p123\nn127.0.0.1:0\nn127.0.0.1:65536\n", pid: 123).isEmpty, "invalid discovered ports")
        try expect(try WallpaperValidation.loopbackPorts("", pid: 123).isEmpty, "no CDP listener")
        refuses("wrong listener owner") { _ = try WallpaperValidation.loopbackPorts("p124\nn127.0.0.1:49221\n", pid: 123) }
        refuses("missing listener owner") { _ = try WallpaperValidation.loopbackPorts("n127.0.0.1:49221\n", pid: 123) }

        func page(_ url: String, _ type: String = "page") -> [String: Any] { ["type": type, "url": url] }
        try expect(WallpaperValidation.mainPage(page("app://-/index.html?initialRoute=%2F")), "official main page")
        try expect(!WallpaperValidation.mainPage(page("https://example.com/index.html")), "web content is excluded")
        try expect(!WallpaperValidation.mainPage(page("app://other/index.html")), "other app origin is excluded")
        try expect(!WallpaperValidation.mainPage(page("app://-/index.html", "iframe")), "child target is excluded")
        for route in ["avatar", "quick-chat", "detached", "mini", "popover", "notification"] {
            try expect(!WallpaperValidation.mainPage(page("app://-/index.html?initialRoute=/\(route)")), "auxiliary route \(route)")
        }
        try expect(try WallpaperValidation.pageSocket("ws://127.0.0.1:49221/devtools/page/AB12-34", port: 49221).host == "127.0.0.1", "exact local page socket")
        for socket in [
            "ws://localhost:49221/devtools/page/AB", "ws://127.0.0.1:49222/devtools/page/AB",
            "wss://127.0.0.1:49221/devtools/page/AB", "ws://user@127.0.0.1:49221/devtools/page/AB",
            "ws://127.0.0.1:49221/devtools/browser/AB", "ws://127.0.0.1:49221/devtools/page/",
            "ws://127.0.0.1:49221/devtools/page/AB?redirect=x", "ws://127.0.0.1:49221/devtools/page/AB#x"
        ] { refuses("nonexact socket \(socket)") { _ = try WallpaperValidation.pageSocket(socket, port: 49221) } }

        let state: [String: Any] = [
            "applied": true, "version": "0.7.1", "imageDecoded": true,
            "matchedSurfaces": 3, "transparentSurfaces": 3, "backgroundMatched": true,
            "coverMatched": true, "fixedViewport": true, "rootClear": true,
            "workspaceBackgroundClear": true, "footerSurfaces": 2, "footerBackgroundClear": true,
            "footerFadeSurfaces": 1, "footerFadeClear": true, "topFadeSurfaces": 1, "topFadeClear": true, "decorationEffectsClear": true,
            "unsupportedDecorations": [String](),
        ]
        try expect(WallpaperValidation.verifiedState(state, version: "0.7.1"), "complete renderer acknowledgement")
        try expect(!WallpaperValidation.verifiedState(state, version: "0.7.0"), "version mismatch is not success")
        for key in ["applied", "imageDecoded", "matchedSurfaces", "transparentSurfaces",
                    "backgroundMatched", "version", "rootClear", "workspaceBackgroundClear",
                    "coverMatched", "fixedViewport", "footerSurfaces", "footerBackgroundClear",
                    "footerFadeSurfaces", "footerFadeClear", "topFadeSurfaces", "topFadeClear", "decorationEffectsClear", "unsupportedDecorations"] {
            var missing = state; missing.removeValue(forKey: key)
            try expect(!WallpaperValidation.verifiedState(missing, version: "0.7.1"), "missing \(key) is not success")
        }
        // Contradictory reports keep applied=true; independent fields must win.
        for key in ["imageDecoded", "backgroundMatched", "rootClear", "workspaceBackgroundClear",
                    "coverMatched", "fixedViewport", "footerBackgroundClear", "footerFadeClear", "topFadeClear", "decorationEffectsClear"] {
            var broken = state; broken[key] = false
            try expect(!WallpaperValidation.verifiedState(broken, version: nil), "false \(key) overrides stale applied=true")
        }
        for count in [0, -1, 0.5, true, "3", Double.infinity, 1e30] as [Any] {
            var invalid = state; invalid["matchedSurfaces"] = count
            try expect(!WallpaperValidation.verifiedState(invalid, version: "0.7.1"), "invalid matched surface count")
        }
        for key in ["footerSurfaces", "footerFadeSurfaces", "topFadeSurfaces"] {
            for count in [-1, 0.5, true, "1"] as [Any] {
                var invalid = state; invalid[key] = count
                try expect(!WallpaperValidation.verifiedState(invalid, version: nil), "invalid decoration count")
            }
        }
        var incomplete = state; incomplete["transparentSurfaces"] = 2
        try expect(!WallpaperValidation.verifiedState(incomplete, version: nil), "partial shell coverage is not success")
        var home = state; home["footerSurfaces"] = 0; home["footerFadeSurfaces"] = 0
        try expect(WallpaperValidation.verifiedState(home, version: nil), "a non-chat route may legitimately have no footer")
        var unsupported = state; unsupported["unsupportedDecorations"] = ["unknown-decoration"]
        try expect(!WallpaperValidation.verifiedState(unsupported, version: nil), "unknown painted decoration fails closed")
        var malformedReasons = state; malformedReasons["unsupportedDecorations"] = "none"
        try expect(!WallpaperValidation.verifiedState(malformedReasons, version: nil), "malformed diagnostic list is not success")
        var forged = state; forged["applied"] = 1
        try expect(!WallpaperValidation.verifiedState(forged, version: "0.7.1"), "numeric applied flag is not a Boolean acknowledgement")
        forged = state; forged["footerFadeClear"] = 1
        try expect(!WallpaperValidation.verifiedState(forged, version: nil), "numeric visual flag is not a Boolean acknowledgement")
        var malformed = state; malformed["version"] = "untrusted renderer text"
        try expect(!WallpaperValidation.verifiedState(malformed, version: nil), "diagnostic version is a bounded version string")
        let legacy: [String: Any] = ["applied": true, "version": "0.7.0", "imageDecoded": true,
                                   "matchedSurfaces": 3, "backgroundMatched": true]
        try expect(!WallpaperValidation.verifiedState(legacy, version: nil), "old partial acknowledgement cannot certify the new contract")
        try expect(!WallpaperValidation.verifiedPages([], version: nil), "empty page set is not success")
        try expect(WallpaperValidation.verifiedPages([state, state], version: nil), "all verified pages share a version")
        try expect(!WallpaperValidation.verifiedPages([state, unsupported], version: nil), "one failed page fails aggregation")
        var differentVersion = state; differentVersion["version"] = "0.7.2"
        try expect(!WallpaperValidation.verifiedPages([state, differentVersion], version: nil), "mixed renderer versions are not one success")
        try expect(!WallpaperValidation.verifiedPages(Array(repeating: state, count: 13), version: nil), "oversized page set is refused")
        var untrusted = unsupported
        untrusted["unsupportedDecorations"] = ["private page text must never be forwarded"]
        let diagnostic = WallpaperValidation.diagnostic(untrusted, index: 2, version: nil)
        let diagnosticJSON = String(decoding: try JSONSerialization.data(withJSONObject: diagnostic), as: UTF8.self)
        try expect(!diagnosticJSON.contains("private page text"), "diagnostics do not forward arbitrary renderer strings")
        try expect(diagnostic["unsupportedDecorationCount"] as? Int == 1, "diagnostics preserve bounded issue counts")
        try expect((diagnostic["verificationIssues"] as? [String])?.contains("unsupported-decorations") == true,
                   "diagnostics name the fixed failure category")
        var rejectedCandidate = state; rejectedCandidate["footerFadeClear"] = false
        let partial = WallpaperValidation.applicationFailure(priorStates: [state], failedState: rejectedCandidate,
            totalPages: 3, version: "0.7.1", failureState: "renderer-not-applied")
        try expect(partial["applied"] as? Bool == false, "partial apply cannot report overall success")
        try expect(partial["completedPageCount"] as? Int == 1 && partial["uninspectedPageCount"] as? Int == 1,
                   "failed apply preserves completed and uninspected counts")
        let failedPages = partial["pages"] as? [[String: Any]] ?? []
        try expect(failedPages.count == 2 && failedPages[1]["pageIndex"] as? Int == 1,
                   "failed apply preserves the rejected page index")
        try expect((failedPages[1]["verificationIssues"] as? [String])?.contains("footerFadeClear-not-confirmed") == true,
                   "failed apply preserves the specific visual failure")
        let exception = WallpaperValidation.applicationFailure(priorStates: [state], failedState: nil,
            totalPages: 2, version: "0.7.1", failureState: "renderer-rejected")
        let exceptionPages = exception["pages"] as? [[String: Any]] ?? []
        try expect(exceptionPages.count == 2 && exception["verifiedPageCount"] as? Int == 1,
                   "a renderer exception preserves earlier successful pages")
        try expect((exceptionPages[1]["verificationIssues"] as? [String]) == ["renderer-state-unavailable"],
                   "a renderer exception reports unavailable state without inventing details")
        print("Wallpaper validation checks passed: \(checks). Scope: pure validation only; no Codex, socket, injection or visual check.")
    }
}
