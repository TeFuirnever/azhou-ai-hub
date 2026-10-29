// Compile separately from the application; no private assets or live target.
// swiftc Native/Wallpaper.swift Native/WallpaperValidationTests.swift \
//   -o .build/wallpaper-validation-tests -framework AppKit
import Foundation
import Darwin

@main
struct WallpaperValidationTests {
    static func main() async throws {
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
        try expect(WallpaperMessages.localized(
            chinese: "壁纸操作未完成。", english: "The wallpaper operation did not finish.",
            preferredLanguages: ["fr-FR", "zh_CN"]
        ) == "壁纸操作未完成。", "locale selection skips unsupported languages and normalizes underscores")
        try expect(WallpaperFailure(state: "sample", chinese: "失败", english: "Failed").errorDescription == "Failed",
                   "wallpaper failure exposes its localized description")
        try expect(StartupFailure(reason: "sample", message: "Startup failed").errorDescription == "Startup failed",
                   "startup failure exposes its diagnostic description")
        try expect(try WallpaperValidation.loopbackPorts("p123\nn127.0.0.1:49221\n", pid: 123) == [49221], "exact PID loopback listener")
        try expect(try WallpaperValidation.loopbackPorts("p123\nn127.0.0.1:49221\nn*:49221\n", pid: 123).isEmpty, "wildcard on the same port is refused")
        try expect(try WallpaperValidation.loopbackPorts("p123\nn[::1]:49221\nn192.168.1.2:49222\n", pid: 123).isEmpty, "non-IPv4-loopback listeners are refused")
        try expect(try WallpaperValidation.loopbackPorts("p123\nn127.0.0.1:0\nn127.0.0.1:65536\n", pid: 123).isEmpty, "invalid discovered ports")
        try expect(try WallpaperValidation.loopbackPorts("", pid: 123).isEmpty, "no CDP listener")
        try expect(try WallpaperValidation.loopbackPorts("xignored\np123\nnmalformed\nn127.0.0.1:49221\n", pid: 123) == [49221],
                   "unknown and malformed listener rows do not add endpoints")
        refuses("wrong listener owner") { _ = try WallpaperValidation.loopbackPorts("p124\nn127.0.0.1:49221\n", pid: 123) }
        refuses("malformed listener owner") { _ = try WallpaperValidation.loopbackPorts("pnot-a-pid\nn127.0.0.1:49221\n", pid: 123) }
        refuses("missing listener owner") { _ = try WallpaperValidation.loopbackPorts("n127.0.0.1:49221\n", pid: 123) }

        func page(_ url: String, _ type: String = "page") -> [String: Any] { ["type": type, "url": url] }
        try expect(WallpaperValidation.mainPage(page("app://-/index.html?initialRoute=%2F")), "official main page")
        try expect(WallpaperValidation.mainPage(page("app://-/index.html?theme=dark")), "missing route defaults to the main page")
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
        let fallbackFailure = WallpaperValidation.applicationFailure(priorStates: [], failedState: nil,
            totalPages: 0, version: nil, failureState: "untrusted exception text")
        let fallbackPages = fallbackFailure["pages"] as? [[String: Any]] ?? []
        try expect(fallbackFailure["state"] as? String == "renderer-not-applied"
                   && fallbackFailure["uninspectedPageCount"] as? Int == 0,
                   "unknown renderer failure categories use the fixed safe fallback")
        try expect(fallbackPages.first?["failureState"] as? String == "renderer-not-applied",
                   "fallback page diagnostics do not forward exception text")

        for code in ["shell-timeout", "shell-unsupported", "invalid-local-payload", "invalid-local-image",
                     "image-decode-failed", "image-decode-timeout", "unsupported-shell-no-surfaces",
                     "page-changed-during-decode", "styles-not-effective", "styles-not-effective-after-replacement",
                     "namespace-conflict", "namespace-changed-during-decode", "style-id-conflict",
                     "style-id-conflict-after-decode", "apply-unavailable", "apply-failed", "retry-timeout"] {
            try expect(WallpaperValidation.failureDiagnostic(["failureCode": code])["failureStage"] != nil,
                       "known renderer failure maps to a fixed stage: \(code)")
        }
        try expect(WallpaperValidation.failureDiagnostic(["failureCode": "untrusted-page-text"]).isEmpty,
                   "unknown renderer failure details are discarded")
        try expect(WallpaperValidation.retryFailure(["retried": true, "wallpaper": ["applied": true]]) == nil,
                   "a successful retry receipt with an applied state succeeds")
        try expect(WallpaperValidation.retryFailure(["retried": true, "wallpaper": ["applied": false]]) == "retry-failed",
                   "a retry receipt without an applied state fails")
        try expect(WallpaperValidation.retryFailure(["reason": "already-applied", "wallpaper": ["applied": true]]) == nil,
                   "an already-applied receipt succeeds only with a verified applied flag")
        try expect(WallpaperValidation.retryFailure([:]) == "retry-failed",
                   "a missing retry reason uses the fixed retry failure")
        for reason in ["busy", "disabled", "no-request", "disposed", "unknown-owner", "owner-conflict", "timeout", "operation-cancelled"] {
            try expect(WallpaperValidation.retryFailure(["reason": reason]) == reason,
                       "retry refusal preserves a fixed category: \(reason)")
        }
        try expect(WallpaperValidation.retryFailure(["reason": "private page error"]) == "retry-failed",
                   "retry failure never forwards arbitrary page text")
        var mappedFailure = state; mappedFailure["failureCode"] = "styles-not-effective"
        let mappedDiagnostic = WallpaperValidation.diagnostic(mappedFailure, index: 4, version: "0.7.1")
        try expect(mappedDiagnostic["failureCode"] as? String == "styles-not-effective"
                   && mappedDiagnostic["failureStage"] as? String == "styles",
                   "page diagnostics retain only a mapped failure code and stage")
        try expect((WallpaperValidation.diagnostic([:], index: 0, version: nil)["unsupportedDecorationCount"] as? Int) == -1,
                   "missing decoration details use the documented sentinel")

        checks += try wallpaperJournalChecks()
        checks += try codexTargetEnvironmentChecks()
        checks += try await wallpaperStartupBoundaryChecks()
        checks += try await wallpaperPerformBoundaryChecks()
        checks += try await wallpaperTransportChecks()
        checks += try await wallpaperCoordinatorChecks()
        checks += try wallpaperCommandChecks()
        checks += wallpaperCLIRunChecks()
        print("Wallpaper native checks passed: \(checks). Scope: pure validation, temporary journal, mocked network/socket, and fake-host coordinator; no Codex host or visual check.")
    }
}

private func wallpaperTransportChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    func refuses(_ label: String, _ operation: () async throws -> Void) async {
        do { try await operation(); fatalError("FAILED: \(label)") }
        catch let error as WallpaperFailure { expect(error.state == "endpoint-unavailable", label) }
        catch let error as StartupFailure { expect(error.reason == "protocol-error", label) }
        catch { fatalError("FAILED: \(label), unexpected error: \(error)") }
    }
    func session() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [WallpaperTestURLProtocol.self]
        return URLSession(configuration: configuration)
    }
    func response(_ request: URLRequest, status: Int = 200, url: URL? = nil, body: Data) -> (HTTPURLResponse, Data) {
        (HTTPURLResponse(url: url ?? request.url!, statusCode: status, httpVersion: nil,
                         headerFields: ["Content-Type": "application/json"])!, body)
    }
    func expectPagesError(_ responder: @escaping WallpaperTestURLProtocol.Responder, _ label: String) async {
        WallpaperTestURLProtocol.handler = responder
        let transport = WallpaperTransport(session: session())
        await refuses(label, { _ = try await transport.pages(port: 49221) })
        transport.close()
    }

    let pageList: [[String: Any]] = [
        ["type": "page", "url": "app://-/index.html?initialRoute=%2F"],
        ["type": "page", "url": "app://-/index.html?initialRoute=%2Fquick-chat"],
        ["type": "worker", "url": "app://-/index.html?initialRoute=%2F"],
        ["type": "page", "url": "https://example.com/index.html"],
    ]
    WallpaperTestURLProtocol.reset()
    WallpaperTestURLProtocol.handler = { request in
        (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil,
                         headerFields: ["Content-Type": "application/json"])!,
         try JSONSerialization.data(withJSONObject: pageList))
    }
    let pagesTransport = WallpaperTransport(session: session())
    let pages = try await pagesTransport.pages(port: 49221)
    expect(pages.count == 1 && WallpaperValidation.mainPage(pages[0]),
           "the HTTP list is filtered to verified main pages")
    expect(WallpaperTestURLProtocol.requests.first?.url?.absoluteString == "http://127.0.0.1:49221/json/list",
           "page discovery is confined to the selected IPv4 loopback port")
    pagesTransport.close()

    await expectPagesError({ request in response(request, status: 503, body: Data("[]".utf8)) },
                           "non-success HTTP responses are refused")
    await expectPagesError({ request in
        response(request, url: URL(string: "http://127.0.0.1:49221/elsewhere")!, body: Data("[]".utf8))
    }, "unexpected response URLs are refused")
    await expectPagesError({ request in response(request, body: Data("[\"not-a-page-object\"]".utf8)) },
                           "malformed page lists are refused")
    await expectPagesError({ request in response(request, body: Data(repeating: 0x20, count: 2 * 1024 * 1024)) },
                           "oversized page lists are refused before parsing")
    await expectPagesError({ _ in throw URLError(.notConnectedToInternet) },
                           "transport failures collapse to the fixed endpoint category")

    let redirectSession = session()
    let redirectTransport = WallpaperTransport(session: redirectSession)
    var followedRedirect: URLRequest?
    let redirectRequest = URLRequest(url: URL(string: "http://127.0.0.1:49221/elsewhere")!)
    let redirectResponse = HTTPURLResponse(url: URL(string: "http://127.0.0.1:49221/json/list")!, statusCode: 302,
                                           httpVersion: nil, headerFields: nil)!
    redirectTransport.urlSession(redirectSession, task: redirectSession.dataTask(with: redirectRequest),
                                 willPerformHTTPRedirection: redirectResponse, newRequest: redirectRequest) {
        followedRedirect = $0
    }
    expect(followedRedirect == nil, "the URL session delegate refuses HTTP redirects")
    redirectTransport.close()

    let endpoint = URL(string: "ws://127.0.0.1:49221/devtools/page/unit-page")!
    let zeroTimeoutTransport = WallpaperTransport(session: session(), socketFactory: { _ in
        fatalError("zero-timeout connect must not allocate a socket")
    })
    await refuses("zero-timeout startup connection is rejected", {
        try zeroTimeoutTransport.connect(to: endpoint, timeout: 0)
    })
    zeroTimeoutTransport.close()

    let startupSocket = FakeWallpaperSocket(responses: [
        .string("{\"method\":\"Runtime.consoleAPICalled\"}"),
        .data(Data("{\"id\":1,\"result\":{\"result\":{\"value\":{\"ok\":true}}}}".utf8)),
        .string("{\"id\":2,\"result\":{\"result\":{\"value\":{\"second\":true}}}}"),
    ])
    var capturedRequests: [URLRequest] = []
    let startupTransport = WallpaperTransport(session: session(), socketFactory: { request in
        capturedRequests.append(request)
        return startupSocket
    })
    do {
        try startupTransport.connect(to: endpoint, timeout: 1)
        await refuses("a startup connection cannot be replaced", {
            try startupTransport.connect(to: endpoint, timeout: 0)
        })
        let first = try await startupTransport.evaluate("return 1", timeout: 2)
        let second = try await startupTransport.evaluate("return 2", timeout: 2)
        expect(first["ok"] as? Bool == true && second["second"] as? Bool == true,
               "startup CDP evaluation skips events and decodes string and data replies")
        expect(startupSocket.sentTexts.count == 2 && startupSocket.resumeCount == 1
               && startupSocket.maximumMessageSize == 2 * 1024 * 1024,
               "startup transport sends bounded evaluate requests over one socket")
        let firstCommand = try JSONSerialization.jsonObject(with: Data(startupSocket.sentTexts[0].utf8)) as? [String: Any]
        let parameters = firstCommand?["params"] as? [String: Any]
        expect(firstCommand?["method"] as? String == "Runtime.evaluate"
               && parameters?["expression"] as? String == "return 1"
               && parameters?["timeout"] as? Int == 2_000,
               "startup CDP requests preserve the source and bounded timeout")
        expect(capturedRequests.first?.url == endpoint && capturedRequests.first?.timeoutInterval == 1,
               "startup websocket creation uses the requested endpoint and timeout")
    }
    startupTransport.close()
    expect(startupSocket.cancelCount == 1, "closing the startup transport cancels its socket")

    let sendFailureSocket = FakeWallpaperSocket(responses: [], sendFails: true)
    let sendFailureTransport = WallpaperTransport(session: session(), socketFactory: { _ in sendFailureSocket })
    try sendFailureTransport.connect(to: endpoint, timeout: 1)
    await refuses("startup send failures use the fixed protocol category", {
        _ = try await sendFailureTransport.evaluate("source", timeout: 1)
    })
    sendFailureTransport.close()

    let receiveFailureSocket = FakeWallpaperSocket(responses: [], receiveFails: true)
    let receiveFailureTransport = WallpaperTransport(session: session(), socketFactory: { _ in receiveFailureSocket })
    try receiveFailureTransport.connect(to: endpoint, timeout: 1)
    await refuses("startup receive failures use the fixed protocol category", {
        _ = try await receiveFailureTransport.evaluate("source", timeout: 1)
    })
    receiveFailureTransport.close()

    let missingSocketTransport = WallpaperTransport(session: session(), socketFactory: { _ in
        fatalError("socket factory must not run before connect")
    })
    await refuses("startup evaluation without a connection is rejected", {
        _ = try await missingSocketTransport.evaluate("return 1", timeout: 2)
    })
    missingSocketTransport.close()

    let pageSocket = FakeWallpaperSocket(responses: [
        .string("{\"id\":1,\"result\":{\"result\":{\"value\":{\"page\":true}}}}"),
    ])
    let pageTransport = WallpaperTransport(session: session(), socketFactory: { _ in pageSocket })
    let pageSession = pageTransport.pageSession(endpoint)
    let pageState = try await pageSession.evaluate("page status", timeout: 1)
    pageSession.close()
    expect(pageState["page"] as? Bool == true && pageSocket.sentTexts.count == 1,
           "page sessions evaluate and return by value through the shared transport")
    expect(pageSocket.cancelCount == 1, "closing a page session cancels its socket")
    pageTransport.close()

    let errorSocket = FakeWallpaperSocket(responses: [
        .string("{\"id\":1,\"result\":{\"exceptionDetails\":{\"exception\":{\"description\":\"AZHOU_WALLPAPER:unsupported-shell-no-surfaces\"}}}}"),
    ])
    let errorTransport = WallpaperTransport(session: session(), socketFactory: { _ in errorSocket })
    let errorPage = errorTransport.pageSession(endpoint)
    do {
        _ = try await errorPage.evaluate("private image payload", timeout: 1)
        fatalError("FAILED: unsupported wallpaper shell must wait for the page")
    } catch let error as WallpaperFailure {
        expect(error.state == "renderer-not-ready" && !error.message.contains("private image payload"),
               "renderer readiness errors are mapped without leaking the source")
    }
    errorPage.close(); errorTransport.close()

    let malformedSocket = FakeWallpaperSocket(responses: [
        .string("{\"id\":1,\"result\":{\"exceptionDetails\":{\"exception\":{\"description\":\"private page details\"}}}}"),
    ])
    let malformedTransport = WallpaperTransport(session: session(), socketFactory: { _ in malformedSocket })
    let malformedPage = malformedTransport.pageSession(endpoint)
    do {
        _ = try await malformedPage.evaluate("payload", timeout: 1)
        fatalError("FAILED: arbitrary page exceptions must be rejected")
    } catch let error as WallpaperFailure {
        expect(error.state == "renderer-rejected" && !error.message.contains("private page details"),
               "unknown renderer errors collapse to a fixed, private-safe category")
    }
    malformedPage.close(); malformedTransport.close()

    let noValueSocket = FakeWallpaperSocket(responses: [
        .string("{\"id\":1,\"error\":{\"message\":\"private text\"}}"),
    ])
    let noValueTransport = WallpaperTransport(session: session(), socketFactory: { _ in noValueSocket })
    let noValuePage = noValueTransport.pageSession(endpoint)
    do {
        _ = try await noValuePage.evaluate("payload", timeout: 1)
        fatalError("FAILED: missing renderer return values must be rejected")
    } catch let error as WallpaperFailure {
        expect(error.state == "renderer-rejected" && !error.message.contains("private text"),
               "missing renderer values report a fixed rejection")
    }
    noValuePage.close(); noValueTransport.close()

    let categorizedFailureSocket = FakeWallpaperSocket(responses: [
        .string("{\"id\":1,\"result\":{\"exceptionDetails\":{\"exception\":{\"description\":\"AZHOU_WALLPAPER:invalid-local-image\"}}}}"),
    ])
    let categorizedTransport = WallpaperTransport(session: session(), socketFactory: { _ in categorizedFailureSocket })
    let categorizedPage = categorizedTransport.pageSession(endpoint)
    do {
        _ = try await categorizedPage.evaluate("payload", timeout: 1)
        fatalError("FAILED: invalid local image must be rejected")
    } catch let error as WallpaperFailure {
        expect(error.state == "renderer-rejected" && !error.message.contains("payload"),
               "known renderer failures map to a fixed non-readiness category")
    }
    categorizedPage.close(); categorizedTransport.close()

    let defaultTransport = WallpaperTransport()
    defaultTransport.close()
    expect(true, "default transport initializes and closes its ephemeral URL session without connecting")

    return checks
}

private func wallpaperJournalChecks() throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }

    let root = FileManager.default.temporaryDirectory
        .appendingPathComponent("azhou-wallpaper-journal-\(UUID().uuidString)", isDirectory: true)
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: root) }
    expect(WallpaperJournal.directory.path.hasSuffix("Library/Logs/AzhouCodexStartup"),
           "the production journal retains its established home-directory location")

    let journal = root.appendingPathComponent("journal", isDirectory: true)
    expect(WallpaperJournal.latest(requestID: "first", directory: journal) == nil,
           "an absent journal has no latest result")
    WallpaperJournal.record(["requestID": "first", "state": "applied"], directory: journal)
    let recorded = WallpaperJournal.latest(requestID: "first", directory: journal)
    expect(recorded?["state"] as? String == "applied", "the journal reads back its matching latest result")
    expect(WallpaperJournal.latest(requestID: "other", directory: journal) == nil,
           "the journal does not return a result for another request")

    let latestURL = journal.appendingPathComponent("latest.json")
    let latestAttributes = try FileManager.default.attributesOfItem(atPath: latestURL.path)
    let latestMode = (latestAttributes[.posixPermissions] as? NSNumber)?.intValue
    expect(latestMode.map { $0 & 0o777 } == 0o600, "latest results are stored with owner-only permissions")
    let directoryAttributes = try FileManager.default.attributesOfItem(atPath: journal.path)
    let directoryMode = (directoryAttributes[.posixPermissions] as? NSNumber)?.intValue
    expect(directoryMode.map { $0 & 0o777 } == 0o700, "journal directories are created with owner-only permissions")

    WallpaperJournal.record(["requestID": "second", "state": "restored"], directory: journal)
    let logURL = journal.appendingPathComponent("wallpaper.jsonl")
    let appended = try String(contentsOf: logURL, encoding: .utf8).split(separator: "\n")
    expect(appended.count == 2, "journal records append one JSON line per result")
    expect(WallpaperJournal.latest(requestID: "second", directory: journal)?["state"] as? String == "restored",
           "the newest record replaces the latest result")

    try Data(repeating: 0x78, count: 2 * 1024 * 1024 + 1).write(to: logURL)
    WallpaperJournal.record(["requestID": "bounded", "state": "applied"], directory: journal)
    let boundedLog = try Data(contentsOf: logURL)
    expect(boundedLog.count < 4_096 && String(decoding: boundedLog, as: UTF8.self).contains("bounded"),
           "an oversized journal log is truncated before appending")

    try Data("not-json".utf8).write(to: latestURL)
    expect(WallpaperJournal.latest(requestID: "bounded", directory: journal) == nil,
           "malformed journal JSON is ignored")

    let blockedPath = root.appendingPathComponent("not-a-directory")
    try Data("block".utf8).write(to: blockedPath)
    WallpaperJournal.record(["requestID": "blocked"], directory: blockedPath)
    expect(WallpaperJournal.latest(requestID: "blocked", directory: blockedPath) == nil,
           "file-system failures cannot interrupt a wallpaper operation")

    let directoryTarget = root.appendingPathComponent("directory-target", isDirectory: true)
    try FileManager.default.createDirectory(at: directoryTarget, withIntermediateDirectories: true)
    let directoryLink = root.appendingPathComponent("directory-link", isDirectory: true)
    try FileManager.default.createSymbolicLink(at: directoryLink, withDestinationURL: directoryTarget)
    expect(WallpaperJournal.latest(requestID: "linked", directory: directoryLink) == nil,
           "a symbolic-link journal directory is refused")
    WallpaperJournal.record(["requestID": "linked"], directory: directoryLink)
    expect(!FileManager.default.fileExists(atPath: directoryTarget.appendingPathComponent("latest.json").path),
           "recording does not follow a symbolic-link journal directory")

    let targetLatest = root.appendingPathComponent("target-latest.json")
    let targetBytes = try JSONSerialization.data(withJSONObject: ["requestID": "target", "state": "unchanged"])
    try targetBytes.write(to: targetLatest)
    let latestLinkDirectory = root.appendingPathComponent("latest-link-directory", isDirectory: true)
    try FileManager.default.createDirectory(at: latestLinkDirectory, withIntermediateDirectories: true)
    let latestLink = latestLinkDirectory.appendingPathComponent("latest.json")
    try FileManager.default.createSymbolicLink(at: latestLink, withDestinationURL: targetLatest)
    expect(WallpaperJournal.latest(requestID: "target", directory: latestLinkDirectory) == nil,
           "a symbolic-link latest file is refused")
    WallpaperJournal.record(["requestID": "attacker", "state": "replacement"], directory: latestLinkDirectory)
    let unchangedTargetBytes = try Data(contentsOf: targetLatest)
    expect(unchangedTargetBytes == targetBytes,
           "recording does not overwrite a symbolic-link destination")

    let targetLog = root.appendingPathComponent("target-wallpaper.jsonl")
    try Data("untouched".utf8).write(to: targetLog)
    let logLinkDirectory = root.appendingPathComponent("log-link-directory", isDirectory: true)
    try FileManager.default.createDirectory(at: logLinkDirectory, withIntermediateDirectories: true)
    try FileManager.default.createSymbolicLink(at: logLinkDirectory.appendingPathComponent("wallpaper.jsonl"),
                                               withDestinationURL: targetLog)
    WallpaperJournal.record(["requestID": "linked-log"], directory: logLinkDirectory)
    let unchangedLog = try String(contentsOf: targetLog, encoding: .utf8)
    expect(unchangedLog == "untouched",
           "append-only journal opens refuse a symbolic-link log")
    expect(WallpaperJournal.latest(requestID: "linked-log", directory: logLinkDirectory)?["requestID"] as? String == "linked-log",
           "latest-result recording remains available when the append-only log is blocked")

    return checks
}

@MainActor
private func wallpaperCoordinatorChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    func refuses(_ state: String, _ operation: () async throws -> Void, _ label: String) async {
        do { try await operation(); fatalError("FAILED: \(label)") }
        catch let error as WallpaperFailure { expect(error.state == state, label) }
        catch { fatalError("FAILED: \(label), unexpected error: \(error)") }
    }

    let resolver = FakeWallpaperTargetResolver()
    let goodState: [String: Any] = [
        "applied": true, "version": "0.9.0", "imageDecoded": true,
        "matchedSurfaces": 3, "transparentSurfaces": 3, "backgroundMatched": true,
        "coverMatched": true, "fixedViewport": true, "rootClear": true,
        "workspaceBackgroundClear": true, "footerSurfaces": 2, "footerBackgroundClear": true,
        "footerFadeSurfaces": 1, "footerFadeClear": true, "topFadeSurfaces": 1,
        "topFadeClear": true, "decorationEffectsClear": true, "unsupportedDecorations": [String](),
    ]
    let absentState: [String: Any] = ["applied": false, "version": "0.9.0"]
    let page: [String: Any] = [
        "type": "page", "url": "app://-/index.html?initialRoute=%2F",
        "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/unit-page",
    ]
    func request(_ action: String, cold: Bool = false) throws -> WallpaperRequest {
        var arguments = ["--action", action, "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app", "--port", "49221"]
        if cold { arguments.append("--cold") }
        return try WallpaperRequest(arguments, resolver: resolver)
    }
    func coordinator(_ system: FakeWallpaperSystem, _ transport: FakeWallpaperOperationTransport,
                    now: @escaping () -> TimeInterval = { 0 },
                    sleep: @escaping (TimeInterval) async throws -> Void = { _ in })
        -> (WallpaperRequest) async throws -> [String: Any] {
        { request in
            try await WallpaperCLI.perform(
                request, began: 0, system: system, transport: transport, now: now,
                expectedVersion: "0.9.0", sourceLoader: { "synthetic-wallpaper-payload" },
                sleep: sleep
            )
        }
    }

    await refuses("invalid-request", { _ = try WallpaperRequest(["--action", "unknown"], resolver: resolver) },
                  "request parsing refuses unsupported actions")
    await refuses("invalid-request", { _ = try WallpaperRequest(["--action", "apply", "--target-pid", "-1", "--target-bundle", "/tmp/Codex.app"], resolver: resolver) },
                  "request parsing refuses nonpositive process identities")
    await refuses("invalid-request", { _ = try WallpaperRequest(["--action", "doctor", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app", "--port", "0"], resolver: resolver) },
                  "request parsing bounds explicit ports")
    for arguments in [
        ["--action", "apply"],
        ["--action", "apply", "--target-pid", "invalid", "--target-bundle", "/tmp/Codex.app"],
        ["--action", "apply", "--target-pid", "0", "--target-bundle", "/tmp/Codex.app"],
        ["--action", "apply", "--target-pid", "4123", "--target-bundle", "relative/Codex.app"],
        ["--action", "apply", "--target-pid", "4123", "--target-bundle"],
        ["--wallpaper-status", "--target-pid", "4123"],
        ["--wallpaper-status", "--port", "49221"],
        ["--action", "status", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app", "--port", "not-a-port"],
        ["--action", "status", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app", "--port", "65536"],
    ] {
        await refuses("invalid-request", { _ = try WallpaperRequest(arguments, resolver: resolver) },
                      "request parsing refuses malformed arguments: \(arguments.joined(separator: " "))")
    }
    let resolveCountBeforeStatus = resolver.resolveCount
    let statusRequest = try WallpaperRequest(["--wallpaper-status"], resolver: resolver)
    expect(statusRequest.action == .status && statusRequest.target.pid == 4123,
           "the read-only status shortcut resolves through the injected target catalog")
    expect(resolver.resolveCount == resolveCountBeforeStatus + 1 && resolver.lastPID == nil && resolver.lastBundle == nil,
           "the status shortcut resolves only through the injected catalog")
    let resolveCountBeforeExplicit = resolver.resolveCount
    let explicitRequest = try WallpaperRequest([
        "--wallpaper-status", "--action", "restore", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app",
        "--target-start-time", "123", "--port", "49221", "--cold", "--request-id", "request-unit-1",
    ], resolver: resolver)
    expect(explicitRequest.action == .status && explicitRequest.port == 49221 && explicitRequest.cold
           && explicitRequest.requestID == "request-unit-1",
           "the status shortcut wins while retaining explicit bounded options")
    expect(resolver.resolveCount == resolveCountBeforeExplicit + 1 && resolver.lastPID == 4123
           && resolver.lastBundle?.path == "/tmp/Codex.app" && resolver.lastLaunchTime == 123,
           "explicit target identity and launch time are passed to the resolver")
    let noPortRequest = try WallpaperRequest([
        "--action", "status", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app", "--port",
    ], resolver: resolver)
    expect(noPortRequest.port == nil && noPortRequest.requestID.isEmpty == false,
           "an absent option value leaves the optional port unset and creates a request ID")
    let resolverFailure = FakeWallpaperTargetResolver(failureState: "target-unavailable")
    do {
        _ = try WallpaperRequest(["--wallpaper-status"], resolver: resolverFailure)
        fatalError("FAILED: target resolution failure must propagate")
    } catch let error as WallpaperFailure {
        expect(error.state == "target-unavailable", "request parsing preserves resolver failure categories")
    }
    expect(WallpaperCLI.handles(["--wallpaper-helper"])
           && WallpaperCLI.handles(["--wallpaper-status"])
           && !WallpaperCLI.handles(["--action", "status"]),
           "the command dispatcher recognizes only wallpaper entry flags")
    expect(WallpaperCLI.exitCode(for: "applied") == 0 && WallpaperCLI.exitCode(for: "restored") == 0
           && WallpaperCLI.exitCode(for: "ready") == 0 && WallpaperCLI.exitCode(for: "timeout") == 2,
           "wallpaper exit codes reflect terminal outcomes")
    expect(!WallpaperCLI.restoreMessage.isEmpty, "restore exposes its localized user message")

    let applySystem = FakeWallpaperSystem()
    let applySession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.applyGuardSource: ["state": "ready"],
        "synthetic-wallpaper-payload": goodState,
        WallpaperCLI.statusSource: goodState,
    ])
    let applyTransport = FakeWallpaperOperationTransport(pages: [page], session: applySession)
    let applied = try await coordinator(applySystem, applyTransport)(request("apply"))
    expect(applied["state"] as? String == "applied" && applied["applied"] as? Bool == true,
           "apply requires ownership approval, successful installation, and a verified status")
    expect(applySession.evaluatedSources == [WallpaperCLI.applyGuardSource, "synthetic-wallpaper-payload", WallpaperCLI.statusSource],
           "apply sends only the guard, injected payload, and independent verification")
    expect(applyTransport.closeCount == 1 && applySession.closeCount == 1
           && applySystem.lockAcquired == 1 && applySystem.lockReleased == 1,
           "apply releases its fake operation lock and page transport on success")

    let lockRefusalSystem = FakeWallpaperSystem(lockFailureState: "busy")
    let lockRefusalTransport = FakeWallpaperOperationTransport(pages: [page], session: FakeWallpaperPageSession(responses: [:]))
    await refuses("busy", { _ = try await coordinator(lockRefusalSystem, lockRefusalTransport)(request("apply")) },
                  "an operation lock refusal stops before target or page work")
    expect(lockRefusalSystem.lockAcquired == 0 && lockRefusalTransport.pagesCount == 0
           && lockRefusalTransport.closeCount == 1,
           "an operation lock refusal still closes the transport")

    let preflightFailureSystem = FakeWallpaperSystem(validationFailures: [1: "target-changed"])
    let preflightFailureTransport = FakeWallpaperOperationTransport(pages: [page], session: FakeWallpaperPageSession(responses: [:]))
    await refuses("target-changed", { _ = try await coordinator(preflightFailureSystem, preflightFailureTransport)(request("apply")) },
                  "target identity is revalidated before opening a page")
    expect(preflightFailureSystem.lockReleased == 1 && preflightFailureTransport.closeCount == 1
           && preflightFailureTransport.pagesCount == 0,
           "preflight failures release the lock and never request a page list")

    let listenerFailureSystem = FakeWallpaperSystem(portFailures: [1: "inspection-timeout"])
    let listenerFailureTransport = FakeWallpaperOperationTransport(pages: [page], session: FakeWallpaperPageSession(responses: [:]))
    await refuses("inspection-timeout", { _ = try await coordinator(listenerFailureSystem, listenerFailureTransport)(request("apply")) },
                  "listener inspection errors stop the operation")
    expect(listenerFailureSystem.lockReleased == 1 && listenerFailureTransport.pagesCount == 0,
           "listener inspection errors release ownership before page discovery")

    let wrongPortSystem = FakeWallpaperSystem(portResponses: [[49222]])
    let wrongPortTransport = FakeWallpaperOperationTransport(pages: [page], session: FakeWallpaperPageSession(responses: [:]))
    await refuses("endpoint-refused", { _ = try await coordinator(wrongPortSystem, wrongPortTransport)(request("apply")) },
                  "an explicit port must remain owned by the verified target")
    expect(wrongPortTransport.pagesCount == 0 && wrongPortSystem.lockReleased == 1,
           "a port ownership refusal happens before the HTTP request")

    let noEndpointTransport = FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:]),
                                                               failureState: "endpoint-unavailable")
    let noEndpoint = try await coordinator(FakeWallpaperSystem(), noEndpointTransport)(request("status"))
    expect(noEndpoint["state"] as? String == "needs-restart" && noEndpoint["applied"] as? Bool == false,
           "an unavailable local endpoint returns the restart guidance")
    let networkFailureTransport = FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:]),
                                                                   throwGenericError: true)
    let networkFailure = try await coordinator(FakeWallpaperSystem(), networkFailureTransport)(request("status"))
    expect(networkFailure["state"] as? String == "needs-restart",
           "unexpected page-list transport errors stay inside the restart result")

    let pageLimitTransport = FakeWallpaperOperationTransport(pages: Array(repeating: page, count: 13),
                                                              session: FakeWallpaperPageSession(responses: [:]))
    await refuses("page-count-refused", { _ = try await coordinator(FakeWallpaperSystem(), pageLimitTransport)(request("status")) },
                  "the operation refuses more pages than its bounded limit")
    expect(pageLimitTransport.closeCount == 1, "a page count refusal closes its transport")

    let missingSocketPage: [String: Any] = ["type": "page", "url": "app://-/index.html"]
    let missingSocketSession = FakeWallpaperPageSession(responses: [:])
    let missingSocketTransport = FakeWallpaperOperationTransport(pages: [missingSocketPage], session: missingSocketSession)
    await refuses("endpoint-changed", { _ = try await coordinator(FakeWallpaperSystem(), missingSocketTransport)(request("status")) },
                  "a page without its debug socket is treated as an endpoint change")

    for guardState in ["owner-conflict", "unrecognized-state"] {
        let guardSession = FakeWallpaperPageSession(responses: [WallpaperCLI.applyGuardSource: ["state": guardState]])
        let guardTransport = FakeWallpaperOperationTransport(pages: [page], session: guardSession)
        await refuses("owner-conflict", { _ = try await coordinator(FakeWallpaperSystem(), guardTransport)(request("apply")) },
                      "apply refuses an unknown current owner: \(guardState)")
        expect(guardSession.evaluatedSources == [WallpaperCLI.applyGuardSource]
               && guardTransport.closeCount == 1,
               "owner refusal never evaluates the wallpaper payload")
    }

    let rejectedPayloadSession = FakeWallpaperPageSession(
        responses: [WallpaperCLI.applyGuardSource: ["state": "ready"]],
        failures: ["synthetic-wallpaper-payload": "renderer-rejected"]
    )
    let rejectedPayload = try await coordinator(FakeWallpaperSystem(),
        FakeWallpaperOperationTransport(pages: [page], session: rejectedPayloadSession))(request("apply"))
    expect(rejectedPayload["state"] as? String == "renderer-rejected"
           && rejectedPayload["attemptedPageCount"] as? Int == 1,
           "a renderer exception produces a bounded failure receipt")

    let rejectedStateSession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.applyGuardSource: ["state": "ready"],
        "synthetic-wallpaper-payload": absentState,
    ])
    let rejectedState = try await coordinator(FakeWallpaperSystem(),
        FakeWallpaperOperationTransport(pages: [page], session: rejectedStateSession))(request("apply"))
    expect(rejectedState["state"] as? String == "renderer-not-applied"
           && rejectedState["completedPageCount"] as? Int == 0,
           "a renderer that declines application cannot report success")

    let verifyFailureSession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.applyGuardSource: ["state": "ready"],
        "synthetic-wallpaper-payload": goodState,
        WallpaperCLI.statusSource: absentState,
    ])
    let verifyFailure = try await coordinator(FakeWallpaperSystem(),
        FakeWallpaperOperationTransport(pages: [page], session: verifyFailureSession))(request("apply"))
    expect(verifyFailure["state"] as? String == "verification-failed"
           && verifyFailure["verifiedPageCount"] as? Int == 0,
           "post-apply inspection independently verifies the visual state")

    let partialSession = FakeWallpaperPageSession(
        responses: [WallpaperCLI.applyGuardSource: ["state": "ready"], WallpaperCLI.statusSource: goodState],
        sequences: ["synthetic-wallpaper-payload": [goodState, absentState]]
    )
    let partialApply = try await coordinator(FakeWallpaperSystem(),
        FakeWallpaperOperationTransport(pages: [page, page], session: partialSession))(request("apply"))
    expect(partialApply["state"] as? String == "renderer-not-applied"
           && partialApply["completedPageCount"] as? Int == 1
           && partialApply["attemptedPageCount"] as? Int == 2,
           "multi-page apply stops after the first rejected page and retains completed counts")

    let targetChangedSession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.applyGuardSource: ["state": "ready"],
        "synthetic-wallpaper-payload": goodState,
        WallpaperCLI.statusSource: goodState,
    ])
    await refuses("target-changed", {
        _ = try await coordinator(FakeWallpaperSystem(validationFailures: [4: "target-changed"]),
            FakeWallpaperOperationTransport(pages: [page], session: targetChangedSession))(request("apply"))
    }, "the verified target is checked again after page evaluation")
    expect(targetChangedSession.evaluatedSources == [WallpaperCLI.applyGuardSource,
           "synthetic-wallpaper-payload", WallpaperCLI.statusSource],
           "a post-evaluation identity change prevents a success receipt")

    let activeSession = FakeWallpaperPageSession(responses: [WallpaperCLI.applyGuardSource: ["state": "startup-active"]])
    let activeSystem = FakeWallpaperSystem()
    let activeTransport = FakeWallpaperOperationTransport(pages: [page], session: activeSession)
    await refuses("startup-active", { _ = try await coordinator(activeSystem, activeTransport)(request("apply")) },
                  "apply refuses to replace an active startup controller")
    expect(activeTransport.closeCount == 1 && activeSession.closeCount == 1
           && activeSystem.lockReleased == 1 && activeSession.evaluatedSources.count == 1,
           "ownership refusal closes resources without evaluating the payload")

    let doctorSystem = FakeWallpaperSystem()
    let doctorSession = FakeWallpaperPageSession(responses: [:])
    let doctorTransport = FakeWallpaperOperationTransport(pages: [page], session: doctorSession)
    let doctor = try await coordinator(doctorSystem, doctorTransport)(request("doctor"))
    expect(doctor["state"] as? String == "ready" && doctor["canApply"] as? Bool == true,
           "doctor reports the verified page without applying wallpaper")
    expect(doctorSystem.lockAcquired == 0 && doctorSession.evaluatedSources.isEmpty,
           "doctor has no operation lock and does not open a page session")

    let retrySession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.retrySource: ["retried": true, "wallpaper": goodState],
        WallpaperCLI.statusSource: goodState,
    ])
    let retrySystem = FakeWallpaperSystem()
    let retryTransport = FakeWallpaperOperationTransport(pages: [page], session: retrySession)
    let retried = try await coordinator(retrySystem, retryTransport)(request("retry"))
    expect(retried["state"] as? String == "applied" && retried["applied"] as? Bool == true
           && (retried["retries"] as? [[String: Any]])?.first?["retried"] as? Bool == true,
           "retry returns success only after its receipt and follow-up status verification")
    expect(retrySession.evaluatedSources == [WallpaperCLI.retrySource, WallpaperCLI.statusSource],
           "retry reuses the existing page and checks its independent status")

    let retainedFailureSession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.retrySource: [
            "retried": true, "wallpaper": goodState,
            "previousFailure": ["failureCode": "styles-not-effective", "reason": "wallpaper-unsupported",
                                "pageText": "private page content"],
        ],
        WallpaperCLI.statusSource: goodState,
    ])
    let retainedFailure = try await coordinator(FakeWallpaperSystem(),
        FakeWallpaperOperationTransport(pages: [page], session: retainedFailureSession))(request("retry"))
    let retainedRetries = retainedFailure["retries"] as? [[String: Any]] ?? []
    let retainedReceipt = retainedRetries.first?["previousFailure"] as? [String: Any] ?? [:]
    let retainedJSON = String(decoding: try JSONSerialization.data(withJSONObject: retainedFailure), as: UTF8.self)
    expect(retainedFailure["state"] as? String == "applied"
           && retainedReceipt["failureStage"] as? String == "styles"
           && retainedReceipt["reason"] as? String == "wallpaper-unsupported",
           "retry keeps only an allowlisted previous failure receipt")
    expect(!retainedJSON.contains("private page content"),
           "retry receipts do not forward arbitrary previous page text")

    let retryStateCases: [(String, String)] = [
        ("owner-conflict", "owner-conflict"), ("retry-unavailable", "retry-unavailable"),
        ("untrusted page reason", "retry-failed"),
    ]
    for (reported, expected) in retryStateCases {
        let stateSession = FakeWallpaperPageSession(responses: [WallpaperCLI.retrySource: ["state": reported]])
        let stateTransport = FakeWallpaperOperationTransport(pages: [page], session: stateSession)
        let stateResult = try await coordinator(FakeWallpaperSystem(), stateTransport)(request("retry"))
        expect(stateResult["state"] as? String == expected && stateResult["applied"] as? Bool == false,
               "retry terminal states are reduced to fixed categories: \(reported)")
        expect(stateSession.evaluatedSources == [WallpaperCLI.retrySource] && stateTransport.closeCount == 1,
               "a retry controller failure does not continue page work")
    }

    let malformedRetrySession = FakeWallpaperPageSession(responses: [WallpaperCLI.retrySource: ["retried": true]])
    await refuses("retry-failed", {
        _ = try await coordinator(FakeWallpaperSystem(),
            FakeWallpaperOperationTransport(pages: [page], session: malformedRetrySession))(request("retry"))
    }, "retry refuses a receipt missing its wallpaper state")

    let retryDiagnosticSession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.retrySource: [
            "retried": false, "reason": "disabled",
            "wallpaper": ["applied": false, "failureCode": "apply-failed", "reason": "not-installed",
                          "private": "do not forward"],
        ],
        WallpaperCLI.statusSource: absentState,
    ])
    let retryDiagnostic = try await coordinator(FakeWallpaperSystem(),
        FakeWallpaperOperationTransport(pages: [page], session: retryDiagnosticSession))(request("retry"))
    let retryPages = retryDiagnostic["pages"] as? [[String: Any]] ?? []
    let retryPage = retryPages.first ?? [:]
    let retryDiagnosticJSON = String(decoding: try JSONSerialization.data(withJSONObject: retryDiagnostic), as: UTF8.self)
    expect(retryDiagnostic["state"] as? String == "retry-refused"
           && retryPage["failureCode"] as? String == "apply-failed"
           && retryPage["failureStage"] as? String == "apply"
           && retryPage["reason"] == nil,
           "a refused retry preserves mapped failure categories without forwarding reasons")
    expect(!retryDiagnosticJSON.contains("do not forward"),
           "retry diagnostic pages drop arbitrary controller strings")

    let retryRefusalSession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.retrySource: ["retried": false, "reason": "disabled", "wallpaper": goodState],
        WallpaperCLI.statusSource: goodState,
    ])
    let retryRefusal = try await coordinator(FakeWallpaperSystem(), FakeWallpaperOperationTransport(pages: [page], session: retryRefusalSession))(request("retry"))
    expect(retryRefusal["state"] as? String == "retry-refused" && retryRefusal["applied"] as? Bool == false,
           "a healthy retained wallpaper does not hide a refused retry")

    let restoreSession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.restoreSource: ["restored": true], WallpaperCLI.statusSource: absentState,
    ])
    let restored = try await coordinator(FakeWallpaperSystem(), FakeWallpaperOperationTransport(pages: [page], session: restoreSession))(request("restore"))
    expect(restored["state"] as? String == "restored" && restored["restored"] as? Bool == true,
           "restore reports success only after the subsequent page status confirms removal")

    let restoreOwnerConflict = FakeWallpaperPageSession(responses: [
        WallpaperCLI.restoreSource: ["restored": false, "reason": "owner-conflict"],
    ])
    await refuses("owner-conflict", {
        _ = try await coordinator(FakeWallpaperSystem(),
            FakeWallpaperOperationTransport(pages: [page], session: restoreOwnerConflict))(request("restore"))
    }, "restore does not remove a wallpaper with an unknown owner")
    let restoreFailure = FakeWallpaperPageSession(responses: [
        WallpaperCLI.restoreSource: ["restored": false, "reason": "untrusted-page-text"],
    ])
    await refuses("restore-unconfirmed", {
        _ = try await coordinator(FakeWallpaperSystem(),
            FakeWallpaperOperationTransport(pages: [page], session: restoreFailure))(request("restore"))
    }, "restore requires an explicit removal receipt")
    let restoreStillApplied = FakeWallpaperPageSession(responses: [
        WallpaperCLI.restoreSource: ["restored": true], WallpaperCLI.statusSource: goodState,
    ])
    await refuses("restore-unconfirmed", {
        _ = try await coordinator(FakeWallpaperSystem(),
            FakeWallpaperOperationTransport(pages: [page], session: restoreStillApplied))(request("restore"))
    }, "restore requires the subsequent status to confirm removal")

    var emptyPageClock = 0.0
    let emptyPageOutcome = try await coordinator(
        FakeWallpaperSystem(), FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])),
        now: { emptyPageClock }, sleep: { _ in emptyPageClock = 28 }
    )(request("status"))
    expect(emptyPageOutcome["state"] as? String == "timeout"
           && emptyPageOutcome["reason"] as? String == "main-page-unavailable",
           "an empty main-page list exits after the bounded wait")

    var coldClock = 0.0
    let coldRequest = try WallpaperRequest([
        "--action", "status", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app", "--cold",
    ], resolver: resolver)
    let coldOutcome = try await WallpaperCLI.perform(
        coldRequest, began: 0, system: FakeWallpaperSystem(portResponses: [[]]),
        transport: FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])),
        now: { coldClock }, expectedVersion: "0.9.0", sourceLoader: { "unused" },
        sleep: { _ in coldClock = 28 }
    )
    expect(coldOutcome["state"] as? String == "timeout" && coldOutcome["reason"] as? String == "endpoint-unavailable",
           "cold status waits within budget when no listener has appeared")

    var evaluationClock = 0.0
    let evaluationFailureSession = FakeWallpaperPageSession(
        responses: [:], failures: [WallpaperCLI.statusSource: "renderer-not-ready"]
    )
    let evaluationFailure = try await coordinator(
        FakeWallpaperSystem(), FakeWallpaperOperationTransport(pages: [page], session: evaluationFailureSession),
        now: { evaluationClock }, sleep: { _ in evaluationClock = 28 }
    )(request("status"))
    expect(evaluationFailure["state"] as? String == "timeout"
           && evaluationFailure["reason"] as? String == "renderer-not-ready",
           "transient page-evaluation failures remain bounded and classified")

    let noPortsSystem = FakeWallpaperSystem(portResponses: [[]])
    let noPortsRequest = try WallpaperRequest(
        ["--action", "status", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app"],
        resolver: resolver
    )
    let noPorts = try await coordinator(noPortsSystem,
                                        FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])))(noPortsRequest)
    expect(noPorts["state"] as? String == "needs-restart",
           "status without a listener returns the documented restart requirement")

    let endpointChangedSystem = FakeWallpaperSystem(portResponses: [[49221], [], []])
    let endpointChangedSession = FakeWallpaperPageSession(responses: [:])
    await refuses("endpoint-changed", {
        _ = try await coordinator(endpointChangedSystem,
                                  FakeWallpaperOperationTransport(pages: [page], session: endpointChangedSession))(request("status"))
    }, "a target listener change aborts before evaluation")

    let missingPayloadSystem = FakeWallpaperSystem()
    let missingPayloadTransport = FakeWallpaperOperationTransport(pages: [page], session: FakeWallpaperPageSession(responses: [:]))
    do {
        _ = try await WallpaperCLI.perform(
            request("apply"), began: 0, system: missingPayloadSystem, transport: missingPayloadTransport,
            now: { 0 }, expectedVersion: "0.9.0",
            sourceLoader: { throw WallpaperFailure(state: "resource-missing", chinese: "missing", english: "missing") },
            sleep: { _ in }
        )
        fatalError("FAILED: apply refuses a missing packaged script")
    } catch let error as WallpaperFailure { expect(error.state == "resource-missing", "missing packaged script is a fixed failure") }

    let expiredSession = FakeWallpaperPageSession(responses: [WallpaperCLI.retrySource: [:]])
    let expired = try await WallpaperCLI.perform(
        request("retry"), began: 0, system: FakeWallpaperSystem(),
        transport: FakeWallpaperOperationTransport(pages: [page], session: expiredSession),
        now: { 16.1 }, expectedVersion: "0.9.0", sourceLoader: { "unused" }, sleep: { _ in }
    )
    expect(expired["state"] as? String == "timeout" && expired["reason"] as? String == "retry-budget-exhausted"
           && expiredSession.evaluatedSources.isEmpty,
           "retry does not start a page request after its bounded evaluation budget is exhausted")

    return checks
}

private func codexTargetEnvironmentChecks() throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    func wallpaperFailure(_ expected: String, _ label: String, _ operation: () throws -> Void) {
        do {
            try operation()
            fatalError("FAILED: \(label) unexpectedly succeeded")
        } catch let error as WallpaperFailure {
            expect(error.state == expected, "\(label) reports \(expected)")
        } catch {
            fatalError("FAILED: \(label) reported an unexpected error: \(error)")
        }
    }
    func startupFailure(_ expected: String, _ label: String, _ operation: () throws -> Void) {
        do {
            try operation()
            fatalError("FAILED: \(label) unexpectedly succeeded")
        } catch let error as StartupFailure {
            expect(error.reason == expected, "\(label) reports \(expected)")
        } catch {
            fatalError("FAILED: \(label) reported an unexpected error: \(error)")
        }
    }

    let pid: Int32 = 4123
    let bundle = URL(fileURLWithPath: "/tmp/Agent-Skin-Codex-Fixture.app")
    let executable = bundle.appendingPathComponent("Contents/MacOS/Codex")
    let launchedAt = Date(timeIntervalSince1970: 123.456)
    let launchTime = launchedAt.timeIntervalSince1970
    let fixture = FakeCodexTargetEnvironmentState(pid: pid, bundle: bundle, executable: executable,
                                                   launchDate: launchedAt)
    let system = CodexStartupTargetSystem(environment: fixture.environment())
    let resolved = try system.resolveTarget(pid: pid, bundle: bundle, launchTime: launchTime)
    expect(resolved.pid == pid && resolved.bundle == bundle && resolved.executable == executable
           && resolved.bundleID == "com.openai.codex" && resolved.launchTime == launchTime,
           "explicit target resolution returns the verified fake Codex identity")
    let processCall = fixture.commandCalls.first { $0.file == "/bin/ps" }
    expect(processCall?.arguments == ["-ww", "-p", String(pid), "-o", "uid=", "-o", "comm="]
           && processCall?.timeout == 2 && processCall?.emptyExit == nil,
           "target validation inspects the exact process identity with a bounded command")

    try system.preflightBundle(bundle, deadline: 105)
    let signatureCall = fixture.commandCalls.last { $0.file == "/usr/bin/codesign" }
    expect(signatureCall?.arguments == [
        "--verify", "--deep", "--strict", "-R",
        "=anchor apple generic and identifier \"com.openai.codex\" and certificate leaf[subject.OU] = \"2DC432GLL2\"",
        bundle.path,
    ] && signatureCall?.timeout == 5,
           "signature inspection preserves the Apple anchor, bundle ID, team ID, and remaining deadline")

    fixture.commandCalls.removeAll()
    try system.validate(resolved, deadline: 106)
    expect(fixture.commandCalls.filter { $0.file == "/usr/bin/codesign" }.count == 1
           && fixture.commandCalls.filter { $0.file == "/bin/ps" }.count == 2,
           "full target validation checks the signature and process before and after")

    fixture.commandCalls.removeAll()
    fixture.commandResponses["/usr/sbin/lsof"] = "p\(pid)\nn127.0.0.1:49221\nn127.0.0.1:49222\n"
    let ports = try system.listeningPorts(resolved, deadline: 107)
    let listenerCall = fixture.commandCalls.last { $0.file == "/usr/sbin/lsof" }
    expect(ports == [49221, 49222]
           && listenerCall?.arguments == ["-nP", "-a", "-p", String(pid), "-iTCP", "-sTCP:LISTEN", "-Fpn"]
           && listenerCall?.timeout == 3 && listenerCall?.emptyExit == 1,
           "listener discovery remains scoped to the verified process and treats no listeners as empty")

    fixture.processCandidates = [fixture.processes[pid]!]
    fixture.commandCalls.removeAll()
    let discovered = try system.resolveTarget(pid: nil, bundle: nil, launchTime: nil)
    expect(discovered.pid == pid && fixture.runningProcessIdentifiers == ["com.openai.codex"],
           "implicit status resolution accepts exactly one running Codex process")

    fixture.processCandidates = []
    wallpaperFailure("target-unavailable", "missing implicit process") {
        _ = try system.resolveTarget(pid: nil, bundle: nil, launchTime: nil)
    }
    fixture.processCandidates = [fixture.processes[pid]!, fixture.processes[pid]!]
    wallpaperFailure("target-unavailable", "ambiguous implicit processes") {
        _ = try system.resolveTarget(pid: nil, bundle: nil, launchTime: nil)
    }
    fixture.processCandidates = [fixture.process(pid: pid, isTerminated: true)]
    wallpaperFailure("target-unavailable", "terminated implicit process") {
        _ = try system.resolveTarget(pid: nil, bundle: nil, launchTime: nil)
    }
    fixture.processCandidates = [fixture.process(pid: pid, omitBundleURL: true)]
    wallpaperFailure("target-unavailable", "implicit process without a bundle") {
        _ = try system.resolveTarget(pid: nil, bundle: nil, launchTime: nil)
    }
    wallpaperFailure("invalid-request", "explicit PID without bundle") {
        _ = try system.resolveTarget(pid: pid, bundle: nil, launchTime: nil)
    }
    wallpaperFailure("invalid-request", "explicit bundle without PID") {
        _ = try system.resolveTarget(pid: nil, bundle: bundle, launchTime: nil)
    }
    wallpaperFailure("invalid-request", "launch time without explicit identity") {
        _ = try system.resolveTarget(pid: nil, bundle: nil, launchTime: launchTime)
    }

    func refusesTarget(_ label: String, _ configure: (FakeCodexTargetEnvironmentState) -> Void) {
        let state = FakeCodexTargetEnvironmentState(pid: pid, bundle: bundle, executable: executable,
                                                   launchDate: launchedAt)
        configure(state)
        let candidate = CodexStartupTargetSystem(environment: state.environment())
        wallpaperFailure("target-mismatch", label) {
            _ = try candidate.resolveTarget(pid: pid, bundle: bundle, launchTime: launchTime)
        }
    }
    let invalidPIDState = FakeCodexTargetEnvironmentState(pid: pid, bundle: bundle, executable: executable,
                                                           launchDate: launchedAt)
    let invalidPIDSystem = CodexStartupTargetSystem(environment: invalidPIDState.environment())
    wallpaperFailure("target-mismatch", "nonpositive process ID") {
        _ = try invalidPIDSystem.resolveTarget(pid: 0, bundle: bundle, launchTime: launchTime)
    }
    let invalidExtension = URL(fileURLWithPath: "/tmp/Codex-executable")
    let invalidExtensionState = FakeCodexTargetEnvironmentState(pid: pid, bundle: bundle, executable: executable,
                                                                 launchDate: launchedAt)
    let invalidExtensionSystem = CodexStartupTargetSystem(environment: invalidExtensionState.environment())
    wallpaperFailure("target-mismatch", "target bundle extension") {
        _ = try invalidExtensionSystem.resolveTarget(pid: pid, bundle: invalidExtension, launchTime: launchTime)
    }
    refusesTarget("the helper cannot target its own main bundle") { state in state.mainBundleURL = bundle }
    let nestedBundle = URL(fileURLWithPath: "/tmp/Outer.app/Contents/Frameworks/Inner.app")
    let nestedState = FakeCodexTargetEnvironmentState(pid: pid, bundle: bundle, executable: executable,
                                                       launchDate: launchedAt)
    let nestedSystem = CodexStartupTargetSystem(environment: nestedState.environment())
    wallpaperFailure("target-mismatch", "nested app bundle") {
        _ = try nestedSystem.resolveTarget(pid: pid, bundle: nestedBundle, launchTime: launchTime)
    }
    refusesTarget("missing target bundle metadata") { $0.bundles.removeValue(forKey: bundle.path) }
    refusesTarget("unexpected target bundle identity") {
        $0.bundles[bundle.path] = CodexBundleFacts(identifier: "not.codex", executableURL: executable)
    }
    refusesTarget("missing target executable") {
        $0.bundles[bundle.path] = CodexBundleFacts(identifier: "com.openai.codex", executableURL: nil)
    }
    let outsideExecutable = URL(fileURLWithPath: "/tmp/Codex.app/Contents/Resources/Codex")
    refusesTarget("executable outside the app's main binary directory") {
        $0.bundles[bundle.path] = CodexBundleFacts(identifier: "com.openai.codex", executableURL: outsideExecutable)
    }
    refusesTarget("non-executable target binary") { $0.executablePaths.remove(executable.path) }
    refusesTarget("target process is unavailable") { $0.processes.removeValue(forKey: pid) }
    refusesTarget("target process is terminated") {
        $0.processes[pid] = $0.process(pid: pid, isTerminated: true)
    }
    refusesTarget("unexpected process bundle identity") {
        $0.processes[pid] = $0.process(pid: pid, bundleIdentifier: "not.codex")
    }
    refusesTarget("process belongs to another app bundle") {
        $0.processes[pid] = $0.process(pid: pid, bundleURL: URL(fileURLWithPath: "/tmp/Other.app"))
    }
    refusesTarget("process uses another executable") {
        $0.processes[pid] = $0.process(pid: pid, executableURL: URL(fileURLWithPath: "/tmp/Other.app/Contents/MacOS/Other"))
    }
    wallpaperFailure("target-changed", "stale launch time") {
        _ = try system.resolveTarget(pid: pid, bundle: bundle, launchTime: launchTime + 10)
    }
    startupFailure("target-identity", "caller-supplied bundle ID") {
        try system.validate(StartupTargetFacts(pid: pid, bundle: bundle, executable: executable,
                                              bundleID: "not.codex", launchTime: launchTime), deadline: 105)
    }
    let executableMismatch = StartupTargetFacts(pid: pid, bundle: bundle,
                                               executable: URL(fileURLWithPath: "/tmp/Other"),
                                               bundleID: "com.openai.codex", launchTime: launchTime)
    startupFailure("target-identity", "caller-supplied executable path") {
        try system.validateProcess(executableMismatch, deadline: 105)
    }

    fixture.commandResponses["/bin/ps"] = "999 /tmp/Agent-Skin-Codex-Fixture.app/Contents/MacOS/Codex\n"
    wallpaperFailure("target-mismatch", "process owner UID mismatch") {
        _ = try system.resolveTarget(pid: pid, bundle: bundle, launchTime: launchTime)
    }
    fixture.commandResponses["/bin/ps"] = "501 /tmp/Other.app/Contents/MacOS/Other\n"
    wallpaperFailure("target-mismatch", "process executable mismatch") {
        _ = try system.resolveTarget(pid: pid, bundle: bundle, launchTime: launchTime)
    }
    fixture.commandResponses["/bin/ps"] = "malformed\n"
    wallpaperFailure("target-mismatch", "malformed process inspection output") {
        _ = try system.resolveTarget(pid: pid, bundle: bundle, launchTime: launchTime)
    }
    fixture.now = 200
    startupFailure("attach-timeout", "expired process inspection deadline") {
        try system.validateProcess(resolved, deadline: 100)
    }
    startupFailure("attach-timeout", "expired signature inspection deadline") {
        try system.preflightBundle(bundle, deadline: 100)
    }

    fixture.now = 100
    fixture.commandFailures["/usr/bin/codesign"] = "inspection-timeout"
    wallpaperFailure("inspection-timeout", "signature inspection timeout") {
        try system.preflightBundle(bundle, deadline: 105)
    }
    fixture.commandFailures["/usr/bin/codesign"] = "inspection-failed"
    wallpaperFailure("signature-refused", "signature verification failure") {
        try system.preflightBundle(bundle, deadline: 105)
    }
    wallpaperFailure("signature-refused", "signature refuses non-app paths") {
        try system.preflightBundle(invalidExtension, deadline: 105)
    }

    let processChangeState = FakeCodexTargetEnvironmentState(pid: pid, bundle: bundle, executable: executable,
                                                             launchDate: launchedAt)
    processChangeState.afterCommand = { file in
        guard file == "/usr/bin/codesign" else { return }
        processChangeState.afterCommand = nil
        processChangeState.processes[pid] = processChangeState.process(pid: pid, isTerminated: true)
    }
    let processChangeSystem = CodexStartupTargetSystem(environment: processChangeState.environment())
    wallpaperFailure("target-changed", "process changes during target validation") {
        try processChangeSystem.validate(resolved, deadline: 105)
    }

    let live = CodexTargetEnvironment.live
    expect(live.mainBundleURL == Bundle.main.bundleURL && live.currentUID() == UInt32(getuid())
           && live.now().isFinite,
           "the default environment retains current process identity and uptime providers")
    let helperPID = ProcessInfo.processInfo.processIdentifier
    let helperFacts = live.processFacts(helperPID)
    expect(helperFacts == nil || helperFacts?.processIdentifier == helperPID,
           "default process lookup observes only the current unit-test helper")
    let absentBundleID = "com.example.agent-skin-coverage-\(UUID().uuidString.lowercased())"
    expect(live.runningProcesses(absentBundleID).isEmpty,
           "default process discovery can return no match for an unrelated bundle ID")
    let fixtureRoot = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("agent-skin-codex-bundle-\(UUID().uuidString)", isDirectory: true)
    let liveBundle = fixtureRoot.appendingPathComponent("Codex.app", isDirectory: true)
    let liveExecutable = liveBundle.appendingPathComponent("Contents/MacOS/Codex")
    try FileManager.default.createDirectory(at: liveExecutable.deletingLastPathComponent(),
                                            withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: fixtureRoot) }
    let info: [String: Any] = [
        "CFBundleIdentifier": "com.openai.codex",
        "CFBundleExecutable": "Codex",
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
    ]
    let infoData = try PropertyListSerialization.data(fromPropertyList: info, format: .xml, options: 0)
    try infoData.write(to: liveBundle.appendingPathComponent("Contents/Info.plist"))
    try Data("#!/bin/sh\nexit 0\n".utf8).write(to: liveExecutable)
    try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: liveExecutable.path)
    let liveFacts = live.bundleFacts(liveBundle)
    expect(liveFacts?.identifier == "com.openai.codex" && liveFacts?.executableURL?.standardizedFileURL == liveExecutable.standardizedFileURL
           && live.isExecutableFile(liveExecutable),
           "default bundle and executable facts inspect only the temporary fixture")

    let operationPID = Int32.max - ProcessInfo.processInfo.processIdentifier
    let operationPath = WallpaperOperationLock.path(uid: UInt32(getuid()), pid: operationPID)
    expect(operationPath.hasSuffix("local.azhou.wallpaper-\(getuid())-\(operationPID).lock"),
           "per-process operation lock path includes the current user and target PID")
    guard !FileManager.default.fileExists(atPath: operationPath) else {
        fatalError("FAILED: synthetic operation lock path already exists")
    }
    let operationLock = try WallpaperOperationLock.acquire(pid: operationPID)
    defer {
        operationLock.release()
        try? FileManager.default.removeItem(atPath: operationPath)
    }
    wallpaperFailure("busy", "a second operation cannot acquire the same lock") {
        _ = try WallpaperOperationLock.acquire(pid: operationPID)
    }
    operationLock.release()
    operationLock.release()
    let reacquiredLock = try WallpaperOperationLock.acquire(pid: operationPID)
    reacquiredLock.release()

    let adapterPID = operationPID - 3
    let adapterPath = WallpaperOperationLock.path(uid: UInt32(getuid()), pid: adapterPID)
    guard !FileManager.default.fileExists(atPath: adapterPath) else {
        fatalError("FAILED: synthetic adapter lock path already exists")
    }
    let adapterLock = try system.acquireOperationLock(pid: adapterPID)
    adapterLock.release()
    try FileManager.default.removeItem(atPath: adapterPath)

    let symlinkPID = operationPID - 1
    let symlinkPath = WallpaperOperationLock.path(uid: UInt32(getuid()), pid: symlinkPID)
    let symlinkTarget = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("agent-skin-wallpaper-lock-target-\(UUID().uuidString)")
    try Data("fixture".utf8).write(to: symlinkTarget)
    try FileManager.default.createSymbolicLink(atPath: symlinkPath, withDestinationPath: symlinkTarget.path)
    wallpaperFailure("busy", "lock acquisition refuses symbolic links") {
        _ = try WallpaperOperationLock.acquire(pid: symlinkPID)
    }
    try FileManager.default.removeItem(atPath: symlinkPath)
    try FileManager.default.removeItem(at: symlinkTarget)

    let directoryPID = operationPID - 2
    let directoryPath = WallpaperOperationLock.path(uid: UInt32(getuid()), pid: directoryPID)
    try FileManager.default.createDirectory(atPath: directoryPath, withIntermediateDirectories: false)
    wallpaperFailure("busy", "lock acquisition refuses a directory at the lock path") {
        _ = try WallpaperOperationLock.acquire(pid: directoryPID)
    }
    try FileManager.default.removeItem(atPath: directoryPath)
    return checks
}

private func wallpaperCommandChecks() throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    func wallpaperFailure(_ expected: String, _ label: String, _ operation: () throws -> Void) {
        do {
            try operation()
            fatalError("FAILED: \(label) unexpectedly succeeded")
        } catch let error as WallpaperFailure {
            expect(error.state == expected, "\(label) reports \(expected)")
        } catch {
            fatalError("FAILED: \(label) reported an unexpected error: \(error)")
        }
    }

    let environment = CodexTargetEnvironment.live
    let echoed = try environment.runCommand("/bin/echo", ["owned wallpaper command fixture"], 2, nil)
    expect(echoed == "owned wallpaper command fixture\n",
           "the default command wrapper captures output from an owned fixture process")
    let empty = try environment.runCommand("/usr/bin/false", [], 2, 1)
    expect(empty.isEmpty, "a documented empty exit status returns an empty result")
    wallpaperFailure("inspection-failed", "unexpected child exit status") {
        _ = try environment.runCommand("/usr/bin/false", [], 2, nil)
    }
    wallpaperFailure("inspection-timeout", "command timeout terminates its owned child") {
        _ = try environment.runCommand("/bin/sleep", ["1"], 0.01, nil)
    }
    do {
        _ = try environment.runCommand("/tmp/agent-skin-command-that-does-not-exist", [], 2, nil)
        fatalError("FAILED: unavailable command unexpectedly launched")
    } catch {
        expect(true, "a missing executable fails before registering an active child")
    }

    let commandDone = DispatchSemaphore(value: 0)
    let commandState = FakeWallpaperCommandResult()
    DispatchQueue.global().async {
        do {
            _ = try environment.runCommand("/bin/sleep", ["30"], 1, nil)
            commandState.finish("unexpected-return")
        } catch let error as WallpaperFailure {
            commandState.finish(error.state)
        } catch {
            commandState.finish("unexpected-error")
        }
        commandDone.signal()
    }
    Thread.sleep(forTimeInterval: 0.1)
    let cancelled = WallpaperCLI.run(
        ["--wallpaper-helper", "--action", "invalid"],
        resolver: FakeWallpaperTargetResolver(),
        system: FakeWallpaperSystem(),
        transportFactory: { FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])) },
        now: { ProcessInfo.processInfo.systemUptime },
        expectedVersion: "0.9.0",
        sourceLoader: { "unused-test-payload" },
        sleep: { _ in },
        journal: { _ in },
        output: { _ in }
    )
    expect(cancelled == 2, "the cancellation fixture enters the helper's rejected-request exit path")
    expect(commandDone.wait(timeout: .now() + 2) == .success,
           "helper cancellation stops the owned inspection command promptly")
    expect(["cancelled", "inspection-failed"].contains(commandState.value),
           "active command cancellation returns a fixed failure category")
    wallpaperFailure("cancelled", "commands are refused after helper cancellation") {
        _ = try environment.runCommand("/bin/echo", ["must-not-run"], 2, nil)
    }
    return checks
}

private func wallpaperStartupBoundaryChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    let target = StartupTargetFacts(
        pid: 4123,
        bundle: URL(fileURLWithPath: "/tmp/Codex.app"),
        executable: URL(fileURLWithPath: "/tmp/Codex.app/Contents/MacOS/Codex"),
        bundleID: "com.openai.codex",
        launchTime: 123
    )
    let startupURL = "app://-/index.html?initialRoute=%2F"
    let page: [String: Any] = [
        "type": "page", "url": startupURL,
        "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/unit-startup",
    ]
    let nowAtZero: () -> TimeInterval = { 0 }
    let noSleep: (TimeInterval) async throws -> Void = { _ in }
    func run(
        _ system: FakeWallpaperSystem,
        _ transport: FakeWallpaperStartupTransport,
        port: Int = 49221,
        payload: String = "fixture-payload",
        deadline: TimeInterval = 1,
        now: @escaping () -> TimeInterval,
        sleep: @escaping (TimeInterval) async throws -> Void
    ) async -> StartupOutcome {
        await StartupConnector(target: target, expectedPort: port, system: system, transport: transport,
                               now: now, sleep: sleep).run(payload: payload, deadline: deadline)
    }

    let disabledWallpaperStatus: [String: Any] = [
        "owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": 19,
        "ready": true, "completed": false, "overlay": true, "reason": "",
        "wallpaper": ["applied": false, "reason": "disabled", "imageDecoded": false],
        "completion": NSNull(),
    ]
    let disabledWallpaperStartup = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(pages: [page], evaluations: [
            ["href": startupURL, "controllerPresent": false],
            ["installed": true, "alreadyActive": false],
            ["href": startupURL, "missing": false, "status": disabledWallpaperStatus],
        ]), now: nowAtZero, sleep: noSleep)
    expect(disabledWallpaperStartup == .ready(runID: 19),
           "disabled wallpaper does not prevent the startup controller becoming ready")

    let defaultSleep = StartupConnector(
        target: target, expectedPort: 49221, system: FakeWallpaperSystem(),
        transport: FakeWallpaperStartupTransport()
    ).sleep
    try await defaultSleep(0)
    expect(true, "the production startup sleep adapter accepts an immediate bounded sleep")

    do {
        _ = try await StartupLaunchFlow.run(
            existing: target, preflightBundle: {}, validate: { _ in },
            activate: { _ in false }, coldStart: { .ready(runID: 1) }
        )
        fatalError("FAILED: an unconfirmed existing session activation unexpectedly succeeded")
    } catch let error as StartupFailure {
        expect(error.reason == "target-identity",
               "an unconfirmed existing session activation uses the fixed identity failure")
    }
    var preflightCount = 0
    let coldStart = try await StartupLaunchFlow.run(
        existing: nil,
        preflightBundle: { preflightCount += 1 },
        validate: { _ in fatalError("FAILED: cold startup must not validate an existing target") },
        activate: { _ in fatalError("FAILED: cold startup must not activate an existing target") },
        coldStart: { .ready(runID: 2) }
    )
    expect(coldStart == .ready(runID: 2) && preflightCount == 1,
           "a cold launch validates the bundle before starting without an existing process")

    let malformedJSON = await run(FakeWallpaperSystem(), FakeWallpaperStartupTransport(),
                                  port: 0, now: nowAtZero, sleep: noSleep)
    expect(malformedJSON == .failed(reason: "asset-invalid"),
           "the startup connector rejects an invalid local port before host access")
    let emptyPayload = await run(FakeWallpaperSystem(), FakeWallpaperStartupTransport(),
                                 payload: "", now: nowAtZero, sleep: noSleep)
    expect(emptyPayload == .failed(reason: "asset-invalid"),
           "the startup connector rejects an empty local payload")
    let expired = await run(FakeWallpaperSystem(), FakeWallpaperStartupTransport(),
                            now: { 1 }, sleep: noSleep)
    expect(expired == .failed(reason: "attach-timeout"),
           "the startup connector checks its absolute deadline before process inspection")

    let busy = await run(FakeWallpaperSystem(lockFailureState: "busy"),
                         FakeWallpaperStartupTransport(), now: nowAtZero, sleep: noSleep)
    expect(busy == .partial(reason: "startup-active"),
           "an existing wallpaper/startup operation lock maps to the active partial result")
    let inspectionTimeout = await run(FakeWallpaperSystem(portFailures: [1: "inspection-timeout"]),
                                      FakeWallpaperStartupTransport(), now: nowAtZero, sleep: noSleep)
    expect(inspectionTimeout == .failed(reason: "attach-timeout"),
           "a bounded process inspection timeout maps to the attach deadline")
    let changedTarget = await run(FakeWallpaperSystem(validationFailures: [1: "target-changed"]),
                                  FakeWallpaperStartupTransport(), now: nowAtZero, sleep: noSleep)
    expect(changedTarget == .failed(reason: "target-identity"),
           "target changes map to the fixed startup identity category")
    let otherInspectionFailure = await run(FakeWallpaperSystem(portFailures: [1: "endpoint-refused"]),
                                           FakeWallpaperStartupTransport(), now: nowAtZero, sleep: noSleep)
    expect(otherInspectionFailure == .failed(reason: "protocol-error"),
           "unrecognized inspection failures map to the fixed protocol category")
    let genericSystemFailure = await run(FakeWallpaperSystem(genericValidationFailures: [1]),
                                         FakeWallpaperStartupTransport(), now: nowAtZero, sleep: noSleep)
    expect(genericSystemFailure == .failed(reason: "protocol-error"),
           "unexpected startup system errors do not escape as raw diagnostics")
    let genericTransportFailure = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(throwGenericPageError: true),
        now: nowAtZero, sleep: noSleep
    )
    expect(genericTransportFailure == .failed(reason: "protocol-error"),
           "unexpected page-list transport errors use the fixed protocol result")

    let initialListenerMissing = await run(
        FakeWallpaperSystem(portResponses: [[49222]]), FakeWallpaperStartupTransport(),
        now: nowAtZero, sleep: noSleep
    )
    expect(initialListenerMissing == .failed(reason: "listener-mismatch"),
           "startup refuses a listener not owned by the verified process")
    let listenerDisappeared = await run(
        FakeWallpaperSystem(portResponses: [[49221], []]), FakeWallpaperStartupTransport(),
        now: nowAtZero, sleep: noSleep
    )
    expect(listenerDisappeared == .failed(reason: "listener-mismatch"),
           "startup rechecks listener ownership inside its bounded page lookup")
    let listenerChangedAfterPage = await run(
        FakeWallpaperSystem(portResponses: [[49221], [49221], []]),
        FakeWallpaperStartupTransport(pages: [page]), now: nowAtZero, sleep: noSleep
    )
    expect(listenerChangedAfterPage == .failed(reason: "listener-mismatch"),
           "startup rechecks listener ownership after selecting the page")
    let listenerChangedBeforePayload = await run(
        FakeWallpaperSystem(portResponses: [[49221], [49221], [49221], []]),
        FakeWallpaperStartupTransport(
            pages: [page], evaluations: [["href": startupURL, "controllerPresent": false]]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(listenerChangedBeforePayload == .failed(reason: "listener-mismatch"),
           "startup rechecks listener ownership immediately before installing the payload")

    var pageLookupTime: TimeInterval = 0
    let pendingPage = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(pages: []), deadline: 0.2,
        now: { pageLookupTime }, sleep: { pageLookupTime += $0 }
    )
    expect(pendingPage == .failed(reason: "attach-timeout"),
           "startup stops polling when no main page appears before the deadline")
    let ambiguousPages = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(pages: [page, page]),
        now: nowAtZero, sleep: noSleep
    )
    expect(ambiguousPages == .failed(reason: "ambiguous-main-page"),
           "startup refuses multiple simultaneous main pages")
    let pageWithoutSocket = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(pages: [["type": "page", "url": startupURL]]),
        now: nowAtZero, sleep: noSleep
    )
    expect(pageWithoutSocket == .failed(reason: "page-unsupported"),
           "startup refuses a main page without its page-scoped socket")
    let nonPageSocket = await run(
        FakeWallpaperSystem(),
        FakeWallpaperStartupTransport(pages: [[
            "type": "page", "url": startupURL,
            "webSocketDebuggerUrl": "ws://localhost:49221/devtools/page/unit-startup",
        ]]), now: nowAtZero, sleep: noSleep
    )
    expect(nonPageSocket == .failed(reason: "protocol-error"),
           "startup refuses an unverified socket endpoint without exposing it")

    let unsupportedPage = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page], evaluations: [["href": "https://example.com/", "controllerPresent": false]]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(unsupportedPage == .failed(reason: "page-unsupported"),
           "startup verifies the page URL again after connecting")
    let existingController = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page], evaluations: [["href": startupURL, "controllerPresent": true]]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(existingController == .partial(reason: "startup-active"),
           "startup does not install a second controller when one is already present")

    let malformedInstall = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["reason": "owner-conflict"],
            ]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(malformedInstall == .failed(reason: "protocol-error"),
           "startup requires a Boolean installation acknowledgement")
    let rejectedInstall = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": false, "reason": "storage-unavailable"],
            ]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(rejectedInstall == .failed(reason: "storage-unavailable"),
           "startup preserves a fixed storage-unavailable install category")
    let untrustedInstallFailure = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": false, "reason": "private renderer error"],
            ]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(untrustedInstallFailure == .failed(reason: "protocol-error"),
           "untrusted install error text is reduced to the protocol category")
    let missingActiveFlagTransport = FakeWallpaperStartupTransport(
        pages: [page],
        evaluations: [
            ["href": startupURL, "controllerPresent": false],
            ["installed": true],
        ]
    )
    let missingActiveFlag = await run(FakeWallpaperSystem(), missingActiveFlagTransport,
                                      now: nowAtZero, sleep: noSleep)
    expect(missingActiveFlag == .failed(reason: "protocol-error")
           && missingActiveFlagTransport.closeCount == 1
           && missingActiveFlagTransport.disposeCount == 1,
           "an incomplete install receipt triggers bounded cleanup before the protocol failure")
    let alreadyActiveInstall = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": true],
            ]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(alreadyActiveInstall == .partial(reason: "startup-active"),
           "an installation receipt for an already-active controller stays partial")

    let missingMarker = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": "not-a-boolean"],
            ]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(missingMarker == .failed(reason: "protocol-error"),
           "startup refuses a malformed controller-presence marker")
    let failedStatus: [String: Any] = [
        "owner": "azhou-codex-startup", "version": 1, "phase": "failed", "runId": 17,
        "ready": false, "completed": false, "overlay": false, "reason": "target-missing",
        "wallpaper": ["applied": false, "reason": "", "imageDecoded": false],
        "completion": NSNull(),
    ]
    let failedStartup = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page],
            evaluations: [
                ["href": startupURL, "controllerPresent": false],
                ["installed": true, "alreadyActive": false],
                ["href": startupURL, "missing": false, "status": failedStatus],
            ]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(failedStartup == .failed(reason: "target-missing"),
           "a valid failed startup status retains its fixed failure reason")

    let invalidReply = Data("[]".utf8)
    do {
        _ = try StartupCDPProtocol.decode(invalidReply, expectedID: 1)
        fatalError("FAILED: a non-object CDP reply unexpectedly decoded")
    } catch let error as StartupFailure {
        expect(error.reason == "protocol-error", "non-object CDP replies use the protocol category")
    }
    do {
        _ = try StartupCDPProtocol.decode(Data("{}".utf8), expectedID: 1)
        fatalError("FAILED: an unknown CDP event unexpectedly decoded")
    } catch let error as StartupFailure {
        expect(error.reason == "protocol-error", "unrecognized CDP events use the protocol category")
    }
    return checks
}

private func wallpaperPerformBoundaryChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    let resolver = FakeWallpaperTargetResolver()
    let page: [String: Any] = [
        "type": "page",
        "url": "app://-/index.html?initialRoute=%2F",
        "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/status-rejection",
    ]
    let request = try WallpaperRequest(
        ["--action", "status", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app"],
        resolver: resolver
    )
    let listenerSystem = FakeWallpaperSystem(portResponses: [[49221], []])
    let listenerLoss = try await WallpaperCLI.perform(
        request, began: 0, system: listenerSystem,
        transport: FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])),
        now: { 0 }, expectedVersion: "0.9.0", sourceLoader: { "unused" }, sleep: { _ in }
    )
    expect(listenerLoss["state"] as? String == "needs-restart"
           && listenerLoss["applied"] as? Bool == false,
           "a listener that disappears after preflight returns the restart guidance")

    let applyRequest = try WallpaperRequest(
        ["--action", "apply", "--target-pid", "4123", "--target-bundle", "/tmp/Codex.app"],
        resolver: resolver
    )
    let goodState: [String: Any] = [
        "applied": true, "version": "0.9.0", "imageDecoded": true,
        "matchedSurfaces": 1, "transparentSurfaces": 1, "backgroundMatched": true,
        "coverMatched": true, "fixedViewport": true, "rootClear": true,
        "workspaceBackgroundClear": true, "footerSurfaces": 0, "footerBackgroundClear": true,
        "footerFadeSurfaces": 0, "footerFadeClear": true, "topFadeSurfaces": 0,
        "topFadeClear": true, "decorationEffectsClear": true, "unsupportedDecorations": [String](),
    ]
    let session = FakeWallpaperPageSession(
        responses: [
            WallpaperCLI.applyGuardSource: ["state": "ready"],
            "fixture-wallpaper-payload": goodState,
        ],
        failures: [WallpaperCLI.statusSource: "renderer-rejected"]
    )
    let transport = FakeWallpaperOperationTransport(pages: [page], session: session)
    let rejectedStatus = try await WallpaperCLI.perform(
        applyRequest, began: 0, system: FakeWallpaperSystem(), transport: transport,
        now: { 0 }, expectedVersion: "0.9.0", sourceLoader: { "fixture-wallpaper-payload" }, sleep: { _ in }
    )
    expect(rejectedStatus["state"] as? String == "renderer-rejected"
           && rejectedStatus["applied"] as? Bool == false
           && rejectedStatus["attemptedPageCount"] as? Int == 1
           && transport.closeCount == 1,
           "a renderer status exception after apply preserves a bounded failed-page receipt")
    return checks
}

private func wallpaperCLIRunChecks() -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: \(label)") }
        checks += 1
    }
    func run(_ arguments: [String], resolver: any WallpaperTargetResolver,
             system: FakeWallpaperSystem, transport: FakeWallpaperOperationTransport)
        -> (Int32, [String: Any]?, [[String: Any]]) {
        var output: Data?
        var journal: [[String: Any]] = []
        let code = WallpaperCLI.run(
            arguments, resolver: resolver, system: system, transportFactory: { transport },
            now: { ProcessInfo.processInfo.systemUptime }, expectedVersion: "0.9.0",
            sourceLoader: { "unused-test-payload" }, sleep: { _ in },
            journal: { journal.append($0) }, output: { output = $0 }
        )
        let result = output.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        return (code, result, journal)
    }

    let goodState: [String: Any] = [
        "applied": true, "version": "0.9.0", "imageDecoded": true,
        "matchedSurfaces": 3, "transparentSurfaces": 3, "backgroundMatched": true,
        "coverMatched": true, "fixedViewport": true, "rootClear": true,
        "workspaceBackgroundClear": true, "footerSurfaces": 2, "footerBackgroundClear": true,
        "footerFadeSurfaces": 1, "footerFadeClear": true, "topFadeSurfaces": 1,
        "topFadeClear": true, "decorationEffectsClear": true, "unsupportedDecorations": [String](),
    ]
    let page: [String: Any] = [
        "type": "page", "url": "app://-/index.html?initialRoute=%2F",
        "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/unit-page",
    ]
    let statusSession = FakeWallpaperPageSession(responses: [WallpaperCLI.statusSource: goodState])
    let statusTransport = FakeWallpaperOperationTransport(pages: [page], session: statusSession)
    let status = run(["--wallpaper-status"], resolver: FakeWallpaperTargetResolver(),
                     system: FakeWallpaperSystem(), transport: statusTransport)
    expect(status.0 == 0 && status.1?["state"] as? String == "applied"
           && status.1?["action"] as? String == "status"
           && status.1?["targetPID"] as? Int == 4123
           && status.1?["targetPath"] as? String == "/tmp/Codex.app",
           "CLI status routes a resolved fake target through verified page inspection")
    expect(status.1?["requestID"] as? String != nil && status.1?["timestamp"] as? String != nil
           && status.1?["seconds"] as? Double != nil && status.2.isEmpty,
           "CLI output adds request timing while status avoids journal writes")
    expect(statusTransport.closeCount == 1 && statusSession.closeCount == 1,
           "CLI completion closes the injected page and transport resources")

    let invalid = run(["--wallpaper-helper", "--action", "invalid"], resolver: FakeWallpaperTargetResolver(),
                      system: FakeWallpaperSystem(),
                      transport: FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])))
    expect(invalid.0 == 2 && invalid.1?["state"] as? String == "invalid-request"
           && invalid.1?["action"] as? String == "invalid",
           "CLI converts a rejected request into its fixed error result")
    expect(invalid.2.isEmpty, "invalid requests never create journal entries")

    let resolverError = run(["--wallpaper-status"], resolver: FakeWallpaperTargetResolver(throwGenericError: true),
                            system: FakeWallpaperSystem(),
                            transport: FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])))
    expect(resolverError.0 == 2 && resolverError.1?["state"] as? String == "invalid-request",
           "unexpected target resolver failures collapse to the invalid-request result")

    let targetError = run(["--wallpaper-status"], resolver: FakeWallpaperTargetResolver(),
                          system: FakeWallpaperSystem(validationFailures: [1: "target-changed"]),
                          transport: FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])))
    expect(targetError.0 == 2 && targetError.1?["state"] as? String == "target-changed",
           "CLI retains a fixed target validation failure")

    let genericSystem = FakeWallpaperSystem(genericValidationFailures: [1])
    let generic = run(["--wallpaper-helper", "--action", "apply", "--target-pid", "4123",
                       "--target-bundle", "/tmp/Codex.app", "--port", "49221"],
                      resolver: FakeWallpaperTargetResolver(), system: genericSystem,
                      transport: FakeWallpaperOperationTransport(pages: [], session: FakeWallpaperPageSession(responses: [:])))
    expect(generic.0 == 2 && generic.1?["state"] as? String == "connection-failed",
           "unexpected coordinator failures collapse to the fixed connection category")
    expect(generic.2.count == 1 && generic.2[0]["action"] as? String == "apply"
           && generic.2[0]["state"] as? String == "connection-failed",
           "mutating CLI actions journal the final result through the injected sink")
    return checks
}

private final class FakeWallpaperTargetResolver: WallpaperTargetResolver {
    private(set) var resolveCount = 0
    private(set) var lastPID: Int32?
    private(set) var lastBundle: URL?
    private(set) var lastLaunchTime: TimeInterval?
    private let failureState: String?
    private let throwGenericError: Bool

    init(failureState: String? = nil, throwGenericError: Bool = false) {
        self.failureState = failureState; self.throwGenericError = throwGenericError
    }

    func resolveTarget(pid: Int32?, bundle: URL?, launchTime: TimeInterval?) throws -> StartupTargetFacts {
        resolveCount += 1
        lastPID = pid; lastBundle = bundle; lastLaunchTime = launchTime
        if let failureState {
            throw WallpaperFailure(state: failureState, chinese: "unavailable", english: "unavailable")
        }
        if throwGenericError { throw URLError(.cannotConnectToHost) }
        return StartupTargetFacts(pid: 4123, bundle: URL(fileURLWithPath: "/tmp/Codex.app"),
                                  executable: URL(fileURLWithPath: "/tmp/Codex.app/Contents/MacOS/Codex"),
                                  bundleID: "com.openai.codex", launchTime: 123)
    }
}

private final class FakeWallpaperSystem: StartupTargetSystem {
    private let portResponses: [[Int]]
    private let validationFailures: [Int: String]
    private let genericValidationFailures: Set<Int>
    private let portFailures: [Int: String]
    private let lockFailureState: String?
    private var portIndex = 0
    private var validationCount = 0
    private(set) var lockAcquired = 0
    private(set) var lockReleased = 0
    init(portResponses: [[Int]] = [[49221]], validationFailures: [Int: String] = [:],
         genericValidationFailures: Set<Int> = [],
         portFailures: [Int: String] = [:], lockFailureState: String? = nil) {
        self.portResponses = portResponses
        self.validationFailures = validationFailures
        self.genericValidationFailures = genericValidationFailures
        self.portFailures = portFailures
        self.lockFailureState = lockFailureState
    }
    func preflightBundle(_ bundle: URL, deadline: TimeInterval) throws {}
    func validate(_ target: StartupTargetFacts, deadline: TimeInterval) throws {
        validationCount += 1
        if let state = validationFailures[validationCount] {
            throw WallpaperFailure(state: state, chinese: "failure", english: "failure")
        }
        if genericValidationFailures.contains(validationCount) { throw URLError(.cannotConnectToHost) }
    }
    func listeningPorts(_ target: StartupTargetFacts, deadline: TimeInterval) throws -> [Int] {
        let call = portIndex + 1
        if let state = portFailures[call] {
            throw WallpaperFailure(state: state, chinese: "failure", english: "failure")
        }
        let ports = portResponses[min(portIndex, portResponses.count - 1)]
        portIndex += 1
        return ports
    }
    func acquireOperationLock(pid: Int32) throws -> any StartupOperationLock {
        if let state = lockFailureState {
            throw WallpaperFailure(state: state, chinese: "failure", english: "failure")
        }
        lockAcquired += 1
        return FakeWallpaperOperationLock { [weak self] in self?.lockReleased += 1 }
    }
}

private final class FakeWallpaperStartupTransport: StartupTransport {
    private let responsePages: [[String: Any]]
    private var evaluationResponses: [[String: Any]]
    private let throwGenericPageError: Bool
    private(set) var closeCount = 0
    private(set) var disposeCount = 0

    init(pages: [[String: Any]] = [], evaluations: [[String: Any]] = [],
         throwGenericPageError: Bool = false) {
        responsePages = pages
        evaluationResponses = evaluations
        self.throwGenericPageError = throwGenericPageError
    }

    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        if throwGenericPageError { throw URLError(.cannotConnectToHost) }
        return responsePages
    }

    func connect(to url: URL, timeout: TimeInterval) throws {}

    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        if source.contains("dispose.value.call(api)") { disposeCount += 1 }
        return evaluationResponses.isEmpty ? [:] : evaluationResponses.removeFirst()
    }

    func close() { closeCount += 1 }
}

private final class FakeWallpaperOperationLock: StartupOperationLock {
    private var releaseBody: (() -> Void)?
    init(release: @escaping () -> Void) { releaseBody = release }
    func release() { let body = releaseBody; releaseBody = nil; body?() }
}

private final class FakeWallpaperPageSession: WallpaperPageSession {
    private let responses: [String: [String: Any]]
    private let sequences: [String: [[String: Any]]]
    private let failures: [String: String]
    private var responseCounts: [String: Int] = [:]
    private(set) var evaluatedSources: [String] = []
    private(set) var closeCount = 0
    init(responses: [String: [String: Any]], sequences: [String: [[String: Any]]] = [:],
         failures: [String: String] = [:]) {
        self.responses = responses; self.sequences = sequences; self.failures = failures
    }
    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        evaluatedSources.append(source)
        if let state = failures[source] {
            throw WallpaperFailure(state: state, chinese: "failure", english: "failure")
        }
        if let sequence = sequences[source], !sequence.isEmpty {
            let index = responseCounts[source, default: 0]
            responseCounts[source] = index + 1
            return sequence[min(index, sequence.count - 1)]
        }
        return responses[source] ?? [:]
    }
    func close() { closeCount += 1 }
}

private final class FakeWallpaperOperationTransport: WallpaperOperationTransport {
    private let responsePages: [[String: Any]]
    private let session: FakeWallpaperPageSession
    private let failureState: String?
    private let throwGenericError: Bool
    private(set) var pagesCount = 0
    private(set) var closeCount = 0
    init(pages: [[String: Any]], session: FakeWallpaperPageSession,
         failureState: String? = nil, throwGenericError: Bool = false) {
        responsePages = pages; self.session = session
        self.failureState = failureState; self.throwGenericError = throwGenericError
    }
    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        pagesCount += 1
        if let failureState {
            throw WallpaperFailure(state: failureState, chinese: "failure", english: "failure")
        }
        if throwGenericError { throw URLError(.cannotConnectToHost) }
        return responsePages
    }
    func pageSession(_ url: URL) -> any WallpaperPageSession { session }
    func close() { closeCount += 1 }
}

private final class WallpaperTestURLProtocol: URLProtocol {
    typealias Responder = (URLRequest) throws -> (HTTPURLResponse, Data)
    static var handler: Responder?
    static var requests: [URLRequest] = []

    static func reset() { handler = nil; requests = [] }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.requests.append(request)
        guard let handler = Self.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}

private final class FakeWallpaperSocket: WallpaperSocketTask, @unchecked Sendable {
    private var responses: [URLSessionWebSocketTask.Message]
    private let sendFails: Bool
    private let receiveFails: Bool
    private(set) var sentTexts: [String] = []
    private(set) var resumeCount = 0
    private(set) var cancelCount = 0
    var maximumMessageSize = 0

    init(responses: [URLSessionWebSocketTask.Message], sendFails: Bool = false, receiveFails: Bool = false) {
        self.responses = responses
        self.sendFails = sendFails
        self.receiveFails = receiveFails
    }

    func resume() { resumeCount += 1 }

    func send(_ message: URLSessionWebSocketTask.Message) async throws {
        if sendFails { throw URLError(.cannotConnectToHost) }
        if case .string(let text) = message { sentTexts.append(text) }
    }

    func receive() async throws -> URLSessionWebSocketTask.Message {
        if receiveFails || responses.isEmpty { throw URLError(.cannotConnectToHost) }
        return responses.removeFirst()
    }

    func cancel(with closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) { cancelCount += 1 }
}

private struct FakeCodexCommandInvocation {
    let file: String
    let arguments: [String]
    let timeout: TimeInterval
    let emptyExit: Int32?
}

private final class FakeCodexTargetEnvironmentState: @unchecked Sendable {
    let pid: Int32
    let bundle: URL
    let executable: URL
    let launchDate: Date
    var mainBundleURL = URL(fileURLWithPath: "/tmp/Agent-Skin-Helper.app")
    var bundles: [String: CodexBundleFacts] = [:]
    var processes: [Int32: CodexProcessFacts] = [:]
    var processCandidates: [CodexProcessFacts] = []
    var executablePaths: Set<String> = []
    var currentUID: UInt32 = 501
    var now: TimeInterval = 100
    var commandResponses: [String: String] = [:]
    var commandFailures: [String: String] = [:]
    var commandCalls: [FakeCodexCommandInvocation] = []
    var runningProcessIdentifiers: [String] = []
    var afterCommand: ((String) -> Void)?

    init(pid: Int32 = 4123,
         bundle: URL = URL(fileURLWithPath: "/tmp/Agent-Skin-Codex-Fixture.app"),
         executable: URL = URL(fileURLWithPath: "/tmp/Agent-Skin-Codex-Fixture.app/Contents/MacOS/Codex"),
         launchDate: Date = Date(timeIntervalSince1970: 123.456)) {
        self.pid = pid
        self.bundle = bundle
        self.executable = executable
        self.launchDate = launchDate
        bundles[bundle.path] = CodexBundleFacts(identifier: "com.openai.codex", executableURL: executable)
        let process = self.process(pid: pid)
        processes[pid] = process
        processCandidates = [process]
        executablePaths.insert(executable.path)
    }

    func process(pid: Int32, isTerminated: Bool = false, bundleIdentifier: String? = nil,
                 bundleURL: URL? = nil, executableURL: URL? = nil, launchDate: Date? = nil,
                 omitBundleURL: Bool = false, omitExecutableURL: Bool = false,
                 omitLaunchDate: Bool = false) -> CodexProcessFacts {
        CodexProcessFacts(
            processIdentifier: pid,
            isTerminated: isTerminated,
            bundleIdentifier: bundleIdentifier ?? "com.openai.codex",
            bundleURL: omitBundleURL ? nil : (bundleURL ?? bundle),
            executableURL: omitExecutableURL ? nil : (executableURL ?? executable),
            launchDate: omitLaunchDate ? nil : (launchDate ?? self.launchDate)
        )
    }

    func environment() -> CodexTargetEnvironment {
        CodexTargetEnvironment(
            mainBundleURL: mainBundleURL,
            bundleFacts: { [self] url in bundles[url.resolvingSymlinksInPath().standardizedFileURL.path] },
            processFacts: { [self] pid in processes[pid] },
            runningProcesses: { [self] identifier in
                runningProcessIdentifiers.append(identifier)
                return processCandidates
            },
            isExecutableFile: { [self] url in executablePaths.contains(url.path) },
            runCommand: { [self] file, arguments, timeout, emptyExit in
                commandCalls.append(FakeCodexCommandInvocation(file: file, arguments: arguments,
                                                               timeout: timeout, emptyExit: emptyExit))
                if let state = commandFailures[file] {
                    throw WallpaperFailure(state: state, chinese: "fixture failure", english: "fixture failure")
                }
                let response: String
                if let configured = commandResponses[file] {
                    response = configured
                } else if file == "/bin/ps" {
                    response = "\(currentUID) \(executable.path)\n"
                } else if file == "/usr/sbin/lsof" {
                    response = "p\(self.pid)\n"
                } else {
                    response = ""
                }
                afterCommand?(file)
                return response
            },
            currentUID: { [self] in currentUID },
            now: { [self] in now }
        )
    }
}

private final class FakeWallpaperCommandResult: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue = ""

    var value: String {
        lock.lock()
        defer { lock.unlock() }
        return storedValue
    }

    func finish(_ value: String) {
        lock.lock()
        storedValue = value
        lock.unlock()
    }
}
