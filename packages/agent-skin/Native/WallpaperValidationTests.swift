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
        let listeners: [(String, [Int], String)] = [
            ("p123\nn127.0.0.1:49221\n", [49221], "loopback port"),
            ("p123\nn127.0.0.1:49221\nn*:49221\n", [], "wildcard conflict"),
            ("p123\nn[::1]:49221\nn192.168.1.2:49222\n", [], "other interfaces"),
            ("p123\nn127.0.0.1:0\nn127.0.0.1:65536\n", [], "invalid ports"),
            ("", [], "missing listener"),
            ("xignored\np123\nnmalformed\nn127.0.0.1:49221\n", [49221], "unknown rows"),
        ]
        for (records, expected, label) in listeners {
            try expect(try WallpaperValidation.loopbackPorts(records, pid: 123) == expected, label)
        }
        for (records, label) in [
            ("p124\nn127.0.0.1:49221\n", "wrong owner"),
            ("pnot-a-pid\nn127.0.0.1:49221\n", "malformed owner"),
            ("n127.0.0.1:49221\n", "missing owner"),
        ] {
            refuses(label) { _ = try WallpaperValidation.loopbackPorts(records, pid: 123) }
        }

        let pageCases: [(String, String, Bool)] = [
            ("app://-/index.html?initialRoute=%2F", "page", true),
            ("app://-/index.html?theme=dark", "page", true),
            ("https://example.com/index.html", "page", false),
            ("app://other/index.html", "page", false),
            ("app://-/index.html", "iframe", false),
        ]
        for (url, type, expected) in pageCases {
            let target: [String: Any] = ["type": type, "url": url]
            try expect(WallpaperValidation.mainPage(target) == expected, "page selection: \(url) / \(type)")
        }
        for route in ["avatar", "quick-chat", "detached", "mini", "popover", "notification"] {
            let target: [String: Any] = ["type": "page", "url": "app://-/index.html?initialRoute=/\(route)"]
            try expect(WallpaperValidation.mainPage(target) == false, "auxiliary page: \(route)")
        }
        let validSocket = try WallpaperValidation.pageSocket("ws://127.0.0.1:49221/devtools/page/AB12-34", port: 49221)
        try expect(validSocket.host == "127.0.0.1", "local page socket retains the IPv4 host")
        let rejectedSockets = [
            "ws://localhost:49221/devtools/page/AB", "ws://127.0.0.1:49222/devtools/page/AB",
            "wss://127.0.0.1:49221/devtools/page/AB", "ws://user@127.0.0.1:49221/devtools/page/AB",
            "ws://127.0.0.1:49221/devtools/browser/AB", "ws://127.0.0.1:49221/devtools/page/",
            "ws://127.0.0.1:49221/devtools/page/AB?redirect=x", "ws://127.0.0.1:49221/devtools/page/AB#x",
        ]
        for candidate in rejectedSockets {
            refuses("page socket must be exact: \(candidate)") {
                _ = try WallpaperValidation.pageSocket(candidate, port: 49221)
            }
        }

        var acknowledgement: [String: Any] = [:]
        let positiveFlags = ["applied", "imageDecoded", "backgroundMatched", "coverMatched", "fixedViewport",
                             "rootClear", "workspaceBackgroundClear", "footerBackgroundClear", "footerFadeClear",
                             "topFadeClear", "decorationEffectsClear"]
        for name in positiveFlags { acknowledgement[name] = true }
        for (name, count) in [("matchedSurfaces", 3), ("transparentSurfaces", 3), ("footerSurfaces", 2),
                              ("footerFadeSurfaces", 1), ("topFadeSurfaces", 1)] {
            acknowledgement[name] = count
        }
        acknowledgement["version"] = "0.7.1"
        acknowledgement["unsupportedDecorations"] = [String]()
        let state = acknowledgement
        try expect(WallpaperValidation.verifiedState(state, version: "0.7.1"), "complete acknowledgement succeeds")
        try expect(!WallpaperValidation.verifiedState(state, version: "0.7.0"), "wrong renderer version fails")
        for name in positiveFlags + ["matchedSurfaces", "transparentSurfaces", "footerSurfaces", "footerFadeSurfaces",
                                     "topFadeSurfaces", "version", "unsupportedDecorations"] {
            var sample = state
            sample[name] = nil
            try expect(!WallpaperValidation.verifiedState(sample, version: "0.7.1"), "missing acknowledgement field: \(name)")
        }
        for name in positiveFlags where name != "applied" {
            var sample = state
            sample[name] = false
            try expect(!WallpaperValidation.verifiedState(sample, version: nil), "false field overrides applied: \(name)")
        }
        for value in [0, -1, 0.5, true, "3", Double.infinity, 1e30] as [Any] {
            var sample = state
            sample["matchedSurfaces"] = value
            try expect(!WallpaperValidation.verifiedState(sample, version: "0.7.1"), "invalid matched surface count")
        }
        for name in ["footerSurfaces", "footerFadeSurfaces", "topFadeSurfaces"] {
            for value in [-1, 0.5, true, "1"] as [Any] {
                var sample = state
                sample[name] = value
                try expect(!WallpaperValidation.verifiedState(sample, version: nil), "invalid count for \(name)")
            }
        }
        var sample = state
        sample["transparentSurfaces"] = 2
        try expect(!WallpaperValidation.verifiedState(sample, version: nil), "partial coverage fails")
        sample = state
        sample["footerSurfaces"] = 0
        sample["footerFadeSurfaces"] = 0
        try expect(WallpaperValidation.verifiedState(sample, version: nil), "footer is optional outside chat")
        var unsupported = state
        unsupported["unsupportedDecorations"] = ["unknown-decoration"]
        try expect(!WallpaperValidation.verifiedState(unsupported, version: nil), "unknown decoration fails")
        sample = state
        sample["unsupportedDecorations"] = "none"
        try expect(!WallpaperValidation.verifiedState(sample, version: nil), "decoration list must be an array")
        for name in ["applied", "footerFadeClear"] {
            sample = state
            sample[name] = 1
            try expect(!WallpaperValidation.verifiedState(sample, version: name == "applied" ? "0.7.1" : nil), "numeric flag fails: \(name)")
        }
        sample = state
        sample["version"] = "untrusted renderer text"
        try expect(!WallpaperValidation.verifiedState(sample, version: nil), "version diagnostics reject unbounded text")
        let partialLegacy: [String: Any] = ["applied": true, "version": "0.7.0", "imageDecoded": true,
                                            "matchedSurfaces": 3, "backgroundMatched": true]
        try expect(!WallpaperValidation.verifiedState(partialLegacy, version: nil), "partial old state fails")
        let pageSets: [([[String: Any]], Bool, String)] = [([], false, "empty"), ([state, state], true, "verified"),
            ([state, unsupported], false, "one failed"), (Array(repeating: state, count: 13), false, "oversized")]
        for (pages, expected, label) in pageSets {
            try expect(WallpaperValidation.verifiedPages(pages, version: nil) == expected, "page set aggregation: \(label)")
        }
        sample = state
        sample["version"] = "0.7.2"
        try expect(!WallpaperValidation.verifiedPages([state, sample], version: nil), "mixed page versions fail")

        var untrusted = unsupported
        untrusted["unsupportedDecorations"] = ["private page text must never be forwarded"]
        let diagnostic = WallpaperValidation.diagnostic(untrusted, index: 2, version: nil)
        let diagnosticJSON = String(decoding: try JSONSerialization.data(withJSONObject: diagnostic), as: UTF8.self)
        try expect(!diagnosticJSON.contains("private page text"), "private renderer text is omitted")
        try expect(diagnostic["unsupportedDecorationCount"] as? Int == 1, "issue count remains available")
        try expect((diagnostic["verificationIssues"] as? [String])?.contains("unsupported-decorations") == true,
                   "diagnostic identifies the fixed issue category")
        var rejected = state
        rejected["footerFadeClear"] = false
        let result = WallpaperValidation.applicationFailure(priorStates: [state], failedState: rejected,
            totalPages: 3, version: "0.7.1", failureState: "renderer-not-applied")
        try expect(result["applied"] as? Bool == false, "partial apply is not success")
        try expect(result["completedPageCount"] as? Int == 1 && result["uninspectedPageCount"] as? Int == 1,
                   "completed and uninspected page counts remain visible")
        let failed = result["pages"] as? [[String: Any]] ?? []
        try expect(failed.count == 2 && failed[1]["pageIndex"] as? Int == 1, "rejected page index remains visible")
        try expect((failed[1]["verificationIssues"] as? [String])?.contains("footerFadeClear-not-confirmed") == true,
                   "specific visual failure remains visible")
        let thrown = WallpaperValidation.applicationFailure(priorStates: [state], failedState: nil,
            totalPages: 2, version: "0.7.1", failureState: "renderer-rejected")
        let thrownPages = thrown["pages"] as? [[String: Any]] ?? []
        try expect(thrownPages.count == 2 && thrown["verifiedPageCount"] as? Int == 1,
                   "an exception retains earlier verified pages")
        try expect((thrownPages[1]["verificationIssues"] as? [String]) == ["renderer-state-unavailable"],
                   "an exception reports unavailable state")
        let fallback = WallpaperValidation.applicationFailure(priorStates: [], failedState: nil,
            totalPages: 0, version: nil, failureState: "untrusted exception text")
        let fallbackPages = fallback["pages"] as? [[String: Any]] ?? []
        try expect(fallback["state"] as? String == "renderer-not-applied" && fallback["uninspectedPageCount"] as? Int == 0,
                   "unknown failures use the bounded fallback")
        try expect(fallbackPages.first?["failureState"] as? String == "renderer-not-applied",
                   "page fallback does not forward exception text")

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
        checks += try await startupSignatureBoundaryChecks()
        checks += try await standaloneSignatureBoundaryChecks()
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
    let targets = try await pagesTransport.targets(port: 49221, timeout: 1)
    expect(targets.count == pageList.count && targets.contains { $0["type"] as? String == "worker" },
           "replacement proof retains the complete target list while wallpaper discovery stays filtered")
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

    let unknownHandshakeSocket = FakeWallpaperSocket(responses: [], sendError: URLError(.badServerResponse))
    let unknownHandshakeTransport = WallpaperTransport(session: session(), socketFactory: { _ in unknownHandshakeSocket })
    try unknownHandshakeTransport.connect(to: endpoint, timeout: 1)
    do {
        _ = try await unknownHandshakeTransport.evaluate("source", timeout: 1)
        fatalError("FAILED: an unclassified handshake error was accepted")
    } catch let error as StartupFailure {
        expect(error.reason == "protocol-error" && !error.pageConnectionLost,
               "HTTP handshake failure without an explicit 404 cannot authorize replacement proof")
    }
    unknownHandshakeTransport.close()

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

    let interleavedSocket = FakeWallpaperSocket(responses: [
        .string("{\"method\":\"Runtime.consoleAPICalled\"}"),
        .string("{\"id\":99,\"result\":{\"result\":{\"value\":{\"wrong\":true}}}}"),
        .data(Data("{\"id\":1,\"result\":{\"result\":{\"value\":{\"page\":true}}}}".utf8)),
    ])
    let interleavedTransport = WallpaperTransport(session: session(), socketFactory: { _ in interleavedSocket })
    let interleavedPage = interleavedTransport.pageSession(endpoint)
    let interleavedState = try await interleavedPage.evaluate("page status", timeout: 1)
    expect(interleavedState["page"] as? Bool == true && interleavedState["wrong"] == nil,
           "page sessions ignore events and other request IDs before accepting a binary response")
    interleavedPage.close(); interleavedTransport.close()

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

    let padding = String(repeating: "x", count: 800_000)
    for index in 0..<3 {
        WallpaperJournal.record(["requestID": "large-\(index)", "padding": padding], directory: journal)
    }
    let oversizedOwnedLog = try Data(contentsOf: logURL)
    expect(oversizedOwnedLog.count > 2 * 1024 * 1024, "owned journal crosses the rotation threshold")
    WallpaperJournal.record(["requestID": "bounded", "state": "applied"], directory: journal)
    let boundedLog = try Data(contentsOf: logURL)
    expect(boundedLog.count < 4_096 && String(decoding: boundedLog, as: UTF8.self).contains("bounded"),
           "an oversized journal log is truncated before appending")

    let oversizedDirectory = root.appendingPathComponent("oversized-record", isDirectory: true)
    let oversizedPayload: [String: Any] = ["requestID": "oversized", "padding": String(repeating: "x", count: 1024 * 1024 + 1024)]
    expect(!WallpaperJournal.record(oversizedPayload, directory: oversizedDirectory),
           "a record past the per-record write limit is refused")
    expect(!FileManager.default.fileExists(atPath: oversizedDirectory.appendingPathComponent("latest.json").path)
           && !FileManager.default.fileExists(atPath: oversizedDirectory.appendingPathComponent("wallpaper.jsonl").path),
           "a refused oversized record leaves no journal files")
    expect(WallpaperJournal.record(["requestID": "within-limit"], directory: oversizedDirectory),
           "a record within the per-record write limit is still accepted")
    expect(FileManager.default.fileExists(atPath: oversizedDirectory.appendingPathComponent("latest.json").path)
           && FileManager.default.fileExists(atPath: oversizedDirectory.appendingPathComponent("wallpaper.jsonl").path),
           "an accepted bounded record publishes the journal files")

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

    let largeDirectory = root.appendingPathComponent("large-journal", isDirectory: true)
    try FileManager.default.createDirectory(at: largeDirectory, withIntermediateDirectories: true)
    let largeURL = largeDirectory.appendingPathComponent("latest.json")
    let largeData = try JSONSerialization.data(withJSONObject: ["requestID": "large", "padding": String(repeating: "x", count: 1024 * 1024)])
    try largeData.write(to: largeURL)
    expect(WallpaperJournal.latest(requestID: "large", directory: largeDirectory) == nil,
           "oversized latest results are not read as valid")
    expect((try? Data(contentsOf: largeURL)) == largeData, "oversized latest data is retained")

    let readDirectory = root.appendingPathComponent("chunked-journal", isDirectory: true)
    WallpaperJournal.record(["requestID": "chunked", "state": "applied"], directory: readDirectory)
    var readCalls = 0
    let chunked = WallpaperJournal.latest(requestID: "chunked", directory: readDirectory) { fd, buffer, count in
        readCalls += 1
        if readCalls == 1 { errno = EINTR; return -1 }
        return Darwin.read(fd, buffer, min(count, 7))
    }
    expect(chunked?["state"] as? String == "applied" && readCalls > 2,
           "latest retries interrupted and short reads")
    let failedRead = WallpaperJournal.latest(requestID: "chunked", directory: readDirectory) { _, _, _ in errno = EIO; return -1 }
    expect(failedRead == nil, "latest refuses an I/O error")
    let readPath = readDirectory.appendingPathComponent("latest.json")
    let savedPath = readDirectory.appendingPathComponent("saved-latest.json")
    var replaced = false
    let replacedRead = WallpaperJournal.latest(requestID: "chunked", directory: readDirectory) { fd, buffer, count in
        let result = Darwin.read(fd, buffer, count)
        if result > 0 && !replaced {
            try? FileManager.default.moveItem(at: readPath, to: savedPath)
            try? Data("foreign synthetic bytes".utf8).write(to: readPath)
            replaced = true
        }
        return result
    }
    expect(replaced && replacedRead == nil, "latest refuses a path replaced during reading")
    expect((try? Data(contentsOf: readPath)) == Data("foreign synthetic bytes".utf8)
           && FileManager.default.fileExists(atPath: savedPath.path), "latest preserves both replaced files")

    let fifoDirectory = root.appendingPathComponent("fifo-journal", isDirectory: true)
    try FileManager.default.createDirectory(at: fifoDirectory, withIntermediateDirectories: true)
    let fifoLatest = fifoDirectory.appendingPathComponent("latest.json")
    expect(mkfifo(fifoLatest.path, 0o600) == 0, "synthetic latest FIFO is created")
    expect(WallpaperJournal.latest(requestID: "fifo", directory: fifoDirectory) == nil, "latest refuses a FIFO")
    WallpaperJournal.record(["requestID": "fifo"], directory: fifoDirectory)
    var fifoInfo = stat()
    expect(lstat(fifoLatest.path, &fifoInfo) == 0 && fifoInfo.st_mode & mode_t(S_IFMT) == mode_t(S_IFIFO),
           "record preserves an existing latest FIFO")

    let fifoLogDirectory = root.appendingPathComponent("fifo-log-journal", isDirectory: true)
    try FileManager.default.createDirectory(at: fifoLogDirectory, withIntermediateDirectories: true)
    let fifoLog = fifoLogDirectory.appendingPathComponent("wallpaper.jsonl")
    expect(mkfifo(fifoLog.path, 0o600) == 0, "synthetic append FIFO is created")
    let fifoReader = Darwin.open(fifoLog.path, O_RDONLY | O_NONBLOCK | O_CLOEXEC)
    expect(fifoReader >= 0, "synthetic FIFO reader opens")
    defer { Darwin.close(fifoReader) }
    WallpaperJournal.record(["requestID": "fifo-log"], directory: fifoLogDirectory)
    var fifoBytes = [UInt8](repeating: 0, count: 512)
    let fifoCount = Darwin.read(fifoReader, &fifoBytes, fifoBytes.count)
    expect(fifoCount <= 0, "record never appends data to a FIFO even when it has a reader")
    expect(WallpaperJournal.latest(requestID: "fifo-log", directory: fifoLogDirectory) != nil,
           "latest remains available when append FIFO is refused")

    let switchedDirectory = root.appendingPathComponent("switched-log-journal", isDirectory: true)
    WallpaperJournal.record(["requestID": "before"], directory: switchedDirectory)
    let switchedLog = switchedDirectory.appendingPathComponent("wallpaper.jsonl")
    let savedLog = switchedDirectory.appendingPathComponent("saved.jsonl")
    let priorLog = try Data(contentsOf: switchedLog)
    var didSwitch = false
    WallpaperJournal.record(["requestID": "after"], directory: switchedDirectory, openLog: { path, flags, mode in
        let fd = Darwin.open(path, flags, mode)
        if fd >= 0 {
            try? FileManager.default.moveItem(at: switchedLog, to: savedLog)
            try? Data("foreign synthetic log".utf8).write(to: switchedLog)
            didSwitch = true
        }
        return fd
    })
    expect(didSwitch && (try? Data(contentsOf: savedLog)) == priorLog,
           "append refuses an open descriptor after its path is replaced")
    expect((try? Data(contentsOf: switchedLog)) == Data("foreign synthetic log".utf8),
           "append preserves the foreign replacement")

    let foreignLatestDir = root.appendingPathComponent("foreign-latest", isDirectory: true)
    try FileManager.default.createDirectory(at: foreignLatestDir, withIntermediateDirectories: true)
    let foreignLatest = foreignLatestDir.appendingPathComponent("latest.json")
    let foreignLatestBytes = Data("{\"requestID\":\"legacy\",\"state\":\"kept\"}".utf8)
    try foreignLatestBytes.write(to: foreignLatest)
    WallpaperJournal.record(["requestID": "new"], directory: foreignLatestDir)
    expect((try? Data(contentsOf: foreignLatest)) == foreignLatestBytes, "an unbound latest file is not replaced")
    expect(WallpaperJournal.latest(requestID: "legacy", directory: foreignLatestDir)?["state"] as? String == "kept",
           "an unbound legacy latest remains readable")
    expect(!FileManager.default.fileExists(atPath: foreignLatestDir.appendingPathComponent("wallpaper.jsonl").path),
           "an unbound latest prevents subsequent log creation")

    let foreignLogDir = root.appendingPathComponent("foreign-log", isDirectory: true)
    try FileManager.default.createDirectory(at: foreignLogDir, withIntermediateDirectories: true)
    let foreignLog = foreignLogDir.appendingPathComponent("wallpaper.jsonl")
    let foreignLogBytes = Data(repeating: 0x78, count: 2 * 1024 * 1024 + 1)
    try foreignLogBytes.write(to: foreignLog)
    WallpaperJournal.record(["requestID": "new"], directory: foreignLogDir)
    expect((try? Data(contentsOf: foreignLog)) == foreignLogBytes, "an unbound oversized log is not truncated")
    expect(WallpaperJournal.latest(requestID: "new", directory: foreignLogDir) != nil,
           "an independently safe latest remains available when the log is foreign")

    let editedDir = root.appendingPathComponent("edited-journal", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: editedDir)
    let editedLatest = editedDir.appendingPathComponent("latest.json")
    let editedLog = editedDir.appendingPathComponent("wallpaper.jsonl")
    let editedLogBefore = try Data(contentsOf: editedLog)
    let editedLatestBytes = Data("foreign in-place change".utf8)
    try editedLatestBytes.write(to: editedLatest)
    WallpaperJournal.record(["requestID": "later"], directory: editedDir)
    expect((try? Data(contentsOf: editedLatest)) == editedLatestBytes, "a changed bound latest is preserved")
    expect((try? Data(contentsOf: editedLog)) == editedLogBefore, "a changed latest prevents log updates")

    let editedLogDir = root.appendingPathComponent("edited-log", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: editedLogDir)
    let editedLogPath = editedLogDir.appendingPathComponent("wallpaper.jsonl")
    let editedLogBytes = Data("foreign edited log".utf8)
    try editedLogBytes.write(to: editedLogPath)
    WallpaperJournal.record(["requestID": "later"], directory: editedLogDir)
    expect((try? Data(contentsOf: editedLogPath)) == editedLogBytes, "a changed bound log is preserved")

    let hardlinkDir = root.appendingPathComponent("hardlink-journal", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: hardlinkDir)
    let hardlinkLatest = hardlinkDir.appendingPathComponent("latest.json")
    let hardlinkAlias = hardlinkDir.appendingPathComponent("alias")
    try FileManager.default.linkItem(at: hardlinkLatest, to: hardlinkAlias)
    let hardlinkBefore = try Data(contentsOf: hardlinkLatest)
    WallpaperJournal.record(["requestID": "later"], directory: hardlinkDir)
    expect((try? Data(contentsOf: hardlinkLatest)) == hardlinkBefore && (try? Data(contentsOf: hardlinkAlias)) == hardlinkBefore,
           "a bound file with an extra hard link is not modified")

    let copiedDir = root.appendingPathComponent("copied-latest", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: copiedDir)
    let copiedLatest = copiedDir.appendingPathComponent("latest.json")
    let savedOriginal = copiedDir.appendingPathComponent("saved-original")
    let copiedFile = copiedDir.appendingPathComponent("copy")
    try FileManager.default.copyItem(at: copiedLatest, to: copiedFile)
    try FileManager.default.moveItem(at: copiedLatest, to: savedOriginal)
    try FileManager.default.moveItem(at: copiedFile, to: copiedLatest)
    let copiedBytes = try Data(contentsOf: copiedLatest)
    WallpaperJournal.record(["requestID": "later"], directory: copiedDir)
    expect((try? Data(contentsOf: copiedLatest)) == copiedBytes && FileManager.default.fileExists(atPath: savedOriginal.path),
           "a copied file cannot inherit inode-bound ownership")

    let extraMetadataDir = root.appendingPathComponent("extra-metadata", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: extraMetadataDir)
    let extraLatest = extraMetadataDir.appendingPathComponent("latest.json")
    let extraLog = extraMetadataDir.appendingPathComponent("wallpaper.jsonl")
    let extraBefore = try Data(contentsOf: extraLatest), extraLogBefore = try Data(contentsOf: extraLog)
    let extraFD = Darwin.open(extraLatest.path, O_RDWR | O_NOFOLLOW | O_CLOEXEC)
    let extraValue = Data("synthetic user attribute".utf8)
    let setExtra = extraValue.withUnsafeBytes { fsetxattr(extraFD, "com.example.user-data", $0.baseAddress, $0.count, 0, 0) }
    expect(extraFD >= 0 && setExtra == 0, "synthetic extra extended attribute is installed")
    Darwin.close(extraFD)
    WallpaperJournal.record(["requestID": "later"], directory: extraMetadataDir)
    let checkExtraFD = Darwin.open(extraLatest.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
    let extraLength = fgetxattr(checkExtraFD, "com.example.user-data", nil, 0, 0, 0)
    Darwin.close(checkExtraFD)
    expect((try? Data(contentsOf: extraLatest)) == extraBefore && (try? Data(contentsOf: extraLog)) == extraLogBefore
           && extraLength == extraValue.count, "unrecognized extended attributes are preserved")

    let aclDir = root.appendingPathComponent("acl-journal", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: aclDir)
    let aclLatest = aclDir.appendingPathComponent("latest.json")
    let aclLog = aclDir.appendingPathComponent("wallpaper.jsonl")
    let aclBefore = try Data(contentsOf: aclLatest), aclLogBefore = try Data(contentsOf: aclLog)
    let chmod = Process()
    chmod.executableURL = URL(fileURLWithPath: "/bin/chmod")
    chmod.arguments = ["+a", "everyone deny write", aclLatest.path]
    try chmod.run(); chmod.waitUntilExit()
    expect(chmod.terminationStatus == 0, "synthetic ACL is installed")
    WallpaperJournal.record(["requestID": "later"], directory: aclDir)
    let aclFD = Darwin.open(aclLatest.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
    let actualACL = acl_get_fd_np(aclFD, ACL_TYPE_EXTENDED)
    expect((try? Data(contentsOf: aclLatest)) == aclBefore && (try? Data(contentsOf: aclLog)) == aclLogBefore
           && actualACL != nil, "an ACL-bearing file is preserved")
    if let actualACL { acl_free(UnsafeMutableRawPointer(actualACL)) }
    Darwin.close(aclFD)

    let permissionsDir = root.appendingPathComponent("permissions-journal", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: permissionsDir)
    let permissionsLatest = permissionsDir.appendingPathComponent("latest.json")
    let permissionBefore = try Data(contentsOf: permissionsLatest)
    try FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: permissionsLatest.path)
    WallpaperJournal.record(["requestID": "later"], directory: permissionsDir)
    let permissionMode = try FileManager.default.attributesOfItem(atPath: permissionsLatest.path)[.posixPermissions] as? NSNumber
    expect((try? Data(contentsOf: permissionsLatest)) == permissionBefore && permissionMode?.intValue == 0o644,
           "a changed permission mode is preserved rather than repaired")

    let lockSwapDir = root.appendingPathComponent("lock-swap", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: lockSwapDir)
    let lockLatest = lockSwapDir.appendingPathComponent("latest.json")
    let lockBefore = try Data(contentsOf: lockLatest)
    let lockPath = lockSwapDir.appendingPathComponent(".azhou-wallpaper.lock")
    let lockSaved = lockSwapDir.appendingPathComponent("saved-lock")
    var lockChanged = false
    var lockIO = WallpaperJournal.IO()
    lockIO.step = { phase in
        if phase == "staged-latest" && !lockChanged {
            try? FileManager.default.moveItem(at: lockPath, to: lockSaved)
            try? Data("foreign lock".utf8).write(to: lockPath)
            lockChanged = true
        }
    }
    WallpaperJournal.record(["requestID": "later"], directory: lockSwapDir, io: lockIO)
    expect(lockChanged && (try? Data(contentsOf: lockLatest)) == lockBefore,
           "replacing the locked name prevents publication")
    expect((try? Data(contentsOf: lockPath)) == Data("foreign lock".utf8)
           && FileManager.default.fileExists(atPath: lockSaved.path), "replaced lock entries are retained")

    for phase in ["append-log", "appended-log"] {
        let changedLogDir = root.appendingPathComponent("change-" + phase, isDirectory: true)
        WallpaperJournal.record(["requestID": "original"], directory: changedLogDir)
        let changedLogPath = changedLogDir.appendingPathComponent("wallpaper.jsonl")
        let replacement = Data("foreign in-place log".utf8)
        var changed = false
        var io = WallpaperJournal.IO()
        io.step = { observed in
            if observed == phase && !changed {
                try? replacement.write(to: changedLogPath)
                changed = true
            }
        }
        WallpaperJournal.record(["requestID": "later"], directory: changedLogDir, io: io)
        expect(changed && (try? Data(contentsOf: changedLogPath)) == replacement,
               "concurrent log changes are retained at " + phase)
        WallpaperJournal.record(["requestID": "retry"], directory: changedLogDir)
        expect((try? Data(contentsOf: changedLogPath)) == replacement, "unverified log blocks retry at " + phase)
    }

    let metadataRaceDir = root.appendingPathComponent("append-extra-metadata", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: metadataRaceDir)
    let metadataRaceLog = metadataRaceDir.appendingPathComponent("wallpaper.jsonl")
    var metadataRaceChanged = false
    var metadataRaceIO = WallpaperJournal.IO()
    metadataRaceIO.step = { phase in
        if phase == "appended-log" && !metadataRaceChanged {
            let fd = Darwin.open(metadataRaceLog.path, O_RDWR | O_NOFOLLOW | O_CLOEXEC)
            let value = Data("do not remove".utf8)
            metadataRaceChanged = value.withUnsafeBytes { fsetxattr(fd, "com.example.added", $0.baseAddress, $0.count, 0, 0) } == 0
            Darwin.close(fd)
        }
    }
    WallpaperJournal.record(["requestID": "second"], directory: metadataRaceDir, io: metadataRaceIO)
    let metadataRaceBytes = try Data(contentsOf: metadataRaceLog)
    WallpaperJournal.record(["requestID": "retry"], directory: metadataRaceDir)
    let metadataCheckFD = Darwin.open(metadataRaceLog.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
    let metadataLength = fgetxattr(metadataCheckFD, "com.example.added", nil, 0, 0, 0)
    Darwin.close(metadataCheckFD)
    expect(metadataRaceChanged && metadataLength > 0 && (try? Data(contentsOf: metadataRaceLog)) == metadataRaceBytes,
           "new metadata after append is preserved and never silently adopted")

    let appendFailureDir = root.appendingPathComponent("append-sync-failure", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: appendFailureDir)
    let appendFailureLog = appendFailureDir.appendingPathComponent("wallpaper.jsonl")
    var syncCalls = 0
    var appendFailureIO = WallpaperJournal.IO()
    appendFailureIO.sync = { fd in
        syncCalls += 1
        if syncCalls == 4 { errno = EIO; return -1 }
        return fsync(fd)
    }
    WallpaperJournal.record(["requestID": "second"], directory: appendFailureDir, io: appendFailureIO)
    let partialLog = try Data(contentsOf: appendFailureLog)
    expect(syncCalls == 4 && String(decoding: partialLog, as: UTF8.self).contains("second"),
           "an append sync failure retains the written bytes")
    WallpaperJournal.record(["requestID": "retry"], directory: appendFailureDir)
    expect((try? Data(contentsOf: appendFailureLog)) == partialLog, "a log with stale binding is not rewritten on retry")

    let stagedDir = root.appendingPathComponent("unknown-stage", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: stagedDir)
    let stagedLatest = stagedDir.appendingPathComponent("latest.json")
    let stagedBefore = try Data(contentsOf: stagedLatest)
    let foreignStage = stagedDir.appendingPathComponent(".azhou-wallpaper-stage")
    try Data("unknown stage".utf8).write(to: foreignStage)
    WallpaperJournal.record(["requestID": "later"], directory: stagedDir)
    expect((try? Data(contentsOf: stagedLatest)) == stagedBefore && (try? Data(contentsOf: foreignStage)) == Data("unknown stage".utf8),
           "an unverified fixed stage blocks further writes and is preserved")

    for phase in ["staged-latest", "published-latest", "cleanup-latest"] {
        let swapDir = root.appendingPathComponent("swap-" + phase, isDirectory: true)
        WallpaperJournal.record(["requestID": "original"], directory: swapDir)
        let latest = swapDir.appendingPathComponent("latest.json")
        let log = swapDir.appendingPathComponent("wallpaper.jsonl")
        let originalLatest = try Data(contentsOf: latest), originalLog = try Data(contentsOf: log)
        let stage = swapDir.appendingPathComponent(".azhou-wallpaper-stage")
        let saved = swapDir.appendingPathComponent("saved")
        var changed = false
        var io = WallpaperJournal.IO()
        io.step = { observed in
            if observed == phase && !changed {
                let target = phase == "staged-latest" ? latest : stage
                try? FileManager.default.moveItem(at: target, to: saved)
                try? Data("foreign swapped bytes".utf8).write(to: target)
                changed = true
            }
        }
        WallpaperJournal.record(["requestID": "new"], directory: swapDir, io: io)
        expect(changed, "fault was injected at " + phase)
        let preservedForeign = ((try? Data(contentsOf: stage)) == Data("foreign swapped bytes".utf8))
            || ((try? Data(contentsOf: latest)) == Data("foreign swapped bytes".utf8))
        expect(preservedForeign, "unknown file is preserved at " + phase)
        expect((try? Data(contentsOf: saved)) == originalLatest, "old latest is retained at " + phase)
        expect((try? Data(contentsOf: log)) == originalLog, "log remains unchanged at " + phase)
        let beforeRetry = try Data(contentsOf: stage)
        WallpaperJournal.record(["requestID": "retry"], directory: swapDir)
        expect((try? Data(contentsOf: stage)) == beforeRetry, "unknown stage blocks retry at " + phase)
    }

    for failure in ["marker", "sync", "partial-write"] {
        let failedDir = root.appendingPathComponent("write-failure-" + failure, isDirectory: true)
        var io = WallpaperJournal.IO()
        var calls = 0
        if failure == "marker" { io.setMarker = { _, _ in false } }
        if failure == "sync" { io.sync = { _ in errno = EIO; return -1 } }
        if failure == "partial-write" {
            io.writeChunk = { fd, bytes, count in
                calls += 1
                if calls > 1 { errno = EIO; return -1 }
                return Darwin.write(fd, bytes, min(count, 7))
            }
        }
        WallpaperJournal.record(["requestID": "failure"], directory: failedDir, io: io)
        let stage = failedDir.appendingPathComponent(".azhou-wallpaper-stage")
        expect(FileManager.default.fileExists(atPath: stage.path), "failed stage is retained for " + failure)
        expect(!FileManager.default.fileExists(atPath: failedDir.appendingPathComponent("latest.json").path),
               "failed write does not publish latest for " + failure)
        let stageBytes = try Data(contentsOf: stage)
        WallpaperJournal.record(["requestID": "retry"], directory: failedDir)
        expect((try? Data(contentsOf: stage)) == stageBytes, "retry preserves the failed stage for " + failure)
    }

    let missingMarkerDir = root.appendingPathComponent("missing-marker", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: missingMarkerDir)
    let missingMarkerLatest = missingMarkerDir.appendingPathComponent("latest.json")
    let missingMarkerLog = missingMarkerDir.appendingPathComponent("wallpaper.jsonl")
    let missingMarkerBefore = try Data(contentsOf: missingMarkerLatest), missingMarkerLogBefore = try Data(contentsOf: missingMarkerLog)
    let missingMarkerFD = Darwin.open(missingMarkerLatest.path, O_RDWR | O_NOFOLLOW | O_CLOEXEC)
    expect(missingMarkerFD >= 0 && fremovexattr(missingMarkerFD, "com.azhou.agent-skin.wallpaper.v1", 0) == 0,
           "synthetic ownership marker is removed")
    Darwin.close(missingMarkerFD)
    WallpaperJournal.record(["requestID": "later"], directory: missingMarkerDir)
    expect((try? Data(contentsOf: missingMarkerLatest)) == missingMarkerBefore && (try? Data(contentsOf: missingMarkerLog)) == missingMarkerLogBefore,
           "a missing ownership marker preserves latest and log")

    for failure in ["rename", "unlink", "directory-sync"] {
        let failureDir = root.appendingPathComponent("publish-failure-" + failure, isDirectory: true)
        WallpaperJournal.record(["requestID": "original"], directory: failureDir)
        let latest = failureDir.appendingPathComponent("latest.json")
        let log = failureDir.appendingPathComponent("wallpaper.jsonl")
        let oldLatest = try Data(contentsOf: latest), oldLog = try Data(contentsOf: log)
        let stage = failureDir.appendingPathComponent(".azhou-wallpaper-stage")
        var io = WallpaperJournal.IO()
        var syncCount = 0
        if failure == "rename" { io.rename = { _, _, _, _, _ in errno = EIO; return -1 } }
        if failure == "unlink" { io.unlink = { _, _, _ in errno = EIO; return -1 } }
        if failure == "directory-sync" {
            io.sync = { fd in syncCount += 1; if syncCount == 3 { errno = EIO; return -1 }; return fsync(fd) }
        }
        WallpaperJournal.record(["requestID": "new"], directory: failureDir, io: io)
        expect((try? Data(contentsOf: log)) == oldLog, "publication failure keeps the prior log for " + failure)
        if failure == "rename" {
            expect((try? Data(contentsOf: latest)) == oldLatest && FileManager.default.fileExists(atPath: stage.path),
                   "rename failure preserves the old latest and new stage")
        } else if failure == "unlink" {
            expect((try? Data(contentsOf: stage)) == oldLatest && WallpaperJournal.latest(requestID: "new", directory: failureDir) != nil,
                   "unlink failure retains the old stage and published latest")
        } else {
            expect(syncCount == 3 && WallpaperJournal.latest(requestID: "new", directory: failureDir) != nil,
                   "directory sync failure reports a possibly published latest")
        }
        if failure != "directory-sync" {
            let stageBefore = try Data(contentsOf: stage)
            WallpaperJournal.record(["requestID": "retry"], directory: failureDir)
            expect((try? Data(contentsOf: stage)) == stageBefore, "failed publication stage blocks retry for " + failure)
        }
    }

    let collisionDir = root.appendingPathComponent("target-collision", isDirectory: true)
    try FileManager.default.createDirectory(at: collisionDir, withIntermediateDirectories: true)
    let collisionTarget = collisionDir.appendingPathComponent("latest.json")
    var collisionIO = WallpaperJournal.IO()
    collisionIO.step = { phase in
        if phase == "staged-latest" { try? Data("foreign target".utf8).write(to: collisionTarget) }
    }
    WallpaperJournal.record(["requestID": "new"], directory: collisionDir, io: collisionIO)
    expect((try? Data(contentsOf: collisionTarget)) == Data("foreign target".utf8),
           "exclusive first publication preserves a concurrently created target")
    expect(FileManager.default.fileExists(atPath: collisionDir.appendingPathComponent(".azhou-wallpaper-stage").path),
           "first publication collision retains the staged object")

    let markerFailureDir = root.appendingPathComponent("append-marker-failure", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: markerFailureDir)
    let markerFailureLog = markerFailureDir.appendingPathComponent("wallpaper.jsonl")
    var markerCalls = 0
    var markerIO = WallpaperJournal.IO()
    let normalMarker = markerIO.setMarker
    markerIO.setMarker = { fd, data in
        markerCalls += 1
        return markerCalls == 2 ? false : normalMarker(fd, data)
    }
    WallpaperJournal.record(["requestID": "second"], directory: markerFailureDir, io: markerIO)
    let unboundAppend = try Data(contentsOf: markerFailureLog)
    expect(markerCalls == 2 && String(decoding: unboundAppend, as: UTF8.self).contains("second"),
           "marker update failure preserves appended bytes")
    WallpaperJournal.record(["requestID": "retry"], directory: markerFailureDir)
    expect((try? Data(contentsOf: markerFailureLog)) == unboundAppend,
           "marker update failure blocks future modification of the log")

    let lockedDir = root.appendingPathComponent("held-lock", isDirectory: true)
    WallpaperJournal.record(["requestID": "original"], directory: lockedDir)
    let lockedLatest = lockedDir.appendingPathComponent("latest.json")
    let lockedBefore = try Data(contentsOf: lockedLatest)
    let lockedFD = Darwin.open(lockedDir.appendingPathComponent(".azhou-wallpaper.lock").path, O_RDWR | O_CLOEXEC)
    expect(lockedFD >= 0 && flock(lockedFD, LOCK_EX | LOCK_NB) == 0, "synthetic cooperating lock is held")
    WallpaperJournal.record(["requestID": "later"], directory: lockedDir)
    expect((try? Data(contentsOf: lockedLatest)) == lockedBefore, "a busy lock prevents journal changes")
    flock(lockedFD, LOCK_UN); Darwin.close(lockedFD)

    let shortDir = root.appendingPathComponent("short-write", isDirectory: true)
    var shortIO = WallpaperJournal.IO()
    var shortCalls = 0
    shortIO.writeChunk = { fd, bytes, count in
        shortCalls += 1
        if shortCalls == 1 { errno = EINTR; return -1 }
        return Darwin.write(fd, bytes, min(count, 7))
    }
    WallpaperJournal.record(["requestID": "short"], directory: shortDir, io: shortIO)
    expect(shortCalls > 2 && WallpaperJournal.latest(requestID: "short", directory: shortDir) != nil,
           "short writes are completed before publication")

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
        journal: { _ in true },
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

private func startupSignatureBoundaryChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: signature boundaries: \(label)") }
        checks += 1
    }
    func scans(_ fixture: FakeCodexTargetEnvironmentState) -> Int {
        fixture.commandCalls.filter { $0.file == "/usr/bin/codesign" }.count
    }
    func facts(_ fixture: FakeCodexTargetEnvironmentState) -> StartupTargetFacts {
        StartupTargetFacts(pid: fixture.pid, bundle: fixture.bundle, executable: fixture.executable,
                           bundleID: "com.openai.codex", launchTime: fixture.launchDate.timeIntervalSince1970)
    }
    func environment() -> FakeCodexTargetEnvironmentState {
        let fixture = FakeCodexTargetEnvironmentState(
            bundle: URL(fileURLWithPath: "/private/Agent-Skin-Signature-Fixture.app"),
            executable: URL(fileURLWithPath: "/private/Agent-Skin-Signature-Fixture.app/Contents/MacOS/Codex"))
        fixture.commandResponses["/usr/sbin/lsof"] = "p\(fixture.pid)\nn127.0.0.1:49221\n"
        return fixture
    }

    // The production witness table is the regression boundary: the old
    // extension-only method silently dispatched back into full codesign.
    let dispatchFixture = environment()
    let existential: any StartupTargetSystem = CodexStartupTargetSystem(environment: dispatchFixture.environment())
    try existential.validateProcess(facts(dispatchFixture), deadline: 110)
    expect(scans(dispatchFixture) == 0
           && dispatchFixture.commandCalls.filter { $0.file == "/bin/ps" }.count == 2,
           "production existential process validation freshly checks identity without codesign")
    try existential.validate(facts(dispatchFixture), deadline: 110)
    expect(scans(dispatchFixture) == 1, "full production validation still executes the signature command")

    typealias Pages = Result<[[String: Any]], Error>
    typealias Evaluation = Result<[String: Any], Error>
    let href = "app://-/index.html?initialRoute=%2F"
    func page(_ id: String) -> [String: Any] {
        ["id": id, "type": "page", "url": href,
         "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/\(id)"]
    }
    let a = page("signature-a"), b = page("signature-b")
    let inspected: Evaluation = .success(["href": href, "controllerPresent": false, "shellReady": true])
    let installed: Evaluation = .success(["installed": true, "alreadyActive": false])
    let ready: Evaluation = .success([
        "href": href, "missing": false,
        "status": ["owner": "azhou-codex-startup", "version": 1, "phase": "playing", "runId": 19,
                   "ready": true, "completed": false, "overlay": true, "reason": "",
                   "wallpaper": ["applied": false, "reason": "disabled", "imageDecoded": false],
                   "completion": NSNull()] as [String: Any],
    ])
    let completed: Evaluation = .success([
        "href": href, "missing": false,
        "status": ["owner": "azhou-codex-startup", "version": 1, "phase": "complete", "runId": 19,
                   "ready": true, "completed": true, "overlay": false, "reason": "",
                   "wallpaper": ["applied": false, "reason": "disabled", "imageDecoded": false],
                   "completion": ["cause": "natural", "beforeReady": false]] as [String: Any],
    ])
    let lost: Evaluation = .failure(StartupFailure(reason: "protocol-error", message: "fixture page retired", pageConnectionLost: true))
    let transient: Pages = .failure(WallpaperFailure(state: "endpoint-unavailable", chinese: "fixture timeout", english: "fixture timeout",
                                                     retryableListFailure: true))
    struct Observation {
        let outcome: StartupOutcome
        let fixture: FakeCodexTargetEnvironmentState
        let system: ProductionWallpaperTestSystem
        let transport: FakeWallpaperStartupTransport
        let invalidated: Bool
        let payloads: Int
    }
    func run(discovery: Int = 0, replacement: Bool = false, lag: Int = 0, rechecks: Int = 0,
             refusal: Int? = nil, refuseAfterProof: Bool = false,
             drift: String? = nil, driftPhase: String = "discovery") async -> Observation {
        let fixture = environment()
        let system = ProductionWallpaperTestSystem(fixture.environment())
        var pages = Array(repeating: Pages.success([]), count: discovery) + [.success([a]), .success([a])]
        var evaluations: [Evaluation] = [inspected, installed]
        var targetSteps: [Pages]?
        let current = replacement ? b : a
        if replacement {
            evaluations += [lost, inspected, installed]
            pages += [.success([b])]
            targetSteps = Array(repeating: Pages.success([a, b]), count: lag) + [.success([b])]
        }
        evaluations += [ready]
        pages += Array(repeating: transient, count: rechecks) + [.success([current])]
        if rechecks > 0 { pages += [.success([current])]; evaluations += [ready] }
        pages += [.success([current])]; evaluations += [completed]
        let transport = FakeWallpaperStartupTransport(pageSteps: pages, targetSteps: targetSteps, evaluationSteps: evaluations)
        if refusal == 1 { fixture.commandFailures["/usr/bin/codesign"] = "inspection-failed" }
        fixture.afterCommand = { [weak fixture] file in
            guard let fixture else { return }
            if let refusal, file == "/usr/bin/codesign", scans(fixture) == refusal - 1 {
                fixture.commandFailures[file] = "inspection-failed"
            }
        }
        var invalidated = false
        func invalidate() {
            guard let drift, !invalidated else { return }
            invalidated = true
            switch drift {
            case "pid": fixture.processes[fixture.pid] = nil
            case "start": fixture.processes[fixture.pid] = fixture.process(pid: fixture.pid, launchDate: fixture.launchDate.addingTimeInterval(1))
            case "uid": fixture.commandResponses["/bin/ps"] = "502 \(fixture.executable.path)\n"
            case "executable": fixture.processes[fixture.pid] = fixture.process(pid: fixture.pid, executableURL: URL(fileURLWithPath: "/tmp/other-fixture"))
            case "listener": fixture.commandResponses["/usr/sbin/lsof"] = "p\(fixture.pid)\nn127.0.0.1:49222\n"
            case "cancel": withUnsafeCurrentTask { $0?.cancel() }
            case "budget": fixture.now = 160
            default: fatalError("unknown signature guard fixture")
            }
        }
        transport.onPages = { count in
            if refuseAfterProof && count == discovery + (replacement ? 3 : 2) {
                fixture.commandFailures["/usr/bin/codesign"] = "inspection-failed"
            }
            if driftPhase == "discovery" && count == 1 { invalidate() }
            if driftPhase == "recheck" && count == discovery + (replacement ? 4 : 3) { invalidate() }
        }
        transport.onTargets = { count in if driftPhase == "replacement" && count == 1 { invalidate() } }
        let connector = StartupConnector(target: facts(fixture), expectedPort: 49221, system: system, transport: transport,
                                         now: { fixture.now }, sleep: { fixture.now += $0 })
        let outcome: StartupOutcome
        if drift == "cancel" {
            // Cancellation is raised inside a child task at a scripted read,
            // never by poisoning the main test task or waiting on wall time.
            outcome = await Task { await connector.run(payload: "signature-fixture-payload", deadline: 160) }.value
        } else { outcome = await connector.run(payload: "signature-fixture-payload", deadline: 160) }
        let payloads = transport.evaluatedSources.filter { $0.contains("signature-fixture-payload") }.count
        return Observation(outcome: outcome, fixture: fixture, system: system, transport: transport,
                           invalidated: invalidated, payloads: payloads)
    }
    func closed(_ result: Observation) {
        expect(result.system.lockAcquired == 1 && result.system.lockReleased == 1
               && !result.system.validationWithoutLock && result.transport.closeCount == 1,
               "the same operation lock spans all generation checks and closes once")
    }
    for polls in [0, 8] {
        let normal = await run(discovery: polls); closed(normal)
        expect(normal.outcome == .ready(runID: 19) && normal.payloads == 1 && scans(normal.fixture) == 3
               && normal.system.fullValidations == 3 && normal.system.processValidations > 0,
               "a normal startup keeps exactly entry/connect/pre-install signatures despite \(polls) discovery polls")
        expect(normal.transport.pagesCount == polls + 4 && normal.transport.targetsCount == 0
               && normal.transport.connectedURLs.map(\.lastPathComponent) == ["signature-a"],
               "discovery polls neither connect extra pages nor manufacture a replacement proof")
        let refreshed = await run(rechecks: polls); closed(refreshed)
        expect(refreshed.outcome == .ready(runID: 19) && refreshed.payloads == 1 && scans(refreshed.fixture) == 3
               && refreshed.system.fullValidations == 3 && refreshed.transport.pagesCount == (polls == 0 ? 4 : polls + 5),
               "same-target transient waits do not rescan signatures or replay the payload")
        let statuses = refreshed.transport.evaluatedSources.filter { $0 == StartupConnector.statusExpression }.count
        expect(statuses == (polls == 0 ? 2 : 3), "a waited proof still rereads the same run's current status")
        let replaced = await run(discovery: polls, replacement: true, lag: polls, rechecks: polls); closed(replaced)
        expect(replaced.outcome == .ready(runID: 19) && replaced.payloads == 2 && scans(replaced.fixture) == 5
               && replaced.system.fullValidations == 5 && replaced.transport.targetsCount == polls + 1,
               "each replacement generation adds its own connect and pre-install signatures, independent of proof lag")
        expect(replaced.transport.connectedURLs.map(\.lastPathComponent) == ["signature-a", "signature-b"]
               && replaced.transport.disconnectCount == 1,
               "old-target proof waiting authorizes only the proven replacement and one page disconnect")
    }
    for boundary in 1...3 {
        let refused = await run(discovery: 4, refusal: boundary); closed(refused)
        expect(refused.outcome == .failed(reason: "target-identity") && scans(refused.fixture) == boundary
               && refused.payloads == 0 && refused.transport.targetsCount == 0,
               "signature refusal at original boundary \(boundary) remains fail-closed")
        expect(refused.transport.pagesCount == (boundary == 1 ? 0 : boundary == 2 ? 5 : 6)
               && refused.transport.connectedURLs.count == (boundary == 3 ? 1 : 0)
               && refused.transport.evaluatedSources.count == (boundary == 3 ? 1 : 0),
               "entry/connect/pre-install refusal sends no prohibited later page or action request")
    }
    for boundary in [4, 5] {
        let refused = await run(replacement: true, lag: 4, refusal: boundary); closed(refused)
        expect(refused.outcome == .failed(reason: "target-identity") && scans(refused.fixture) == boundary
               && refused.payloads == 1 && refused.transport.connectedURLs.count == (boundary == 4 ? 1 : 2),
               "the replacement's own signature refusal cannot send a replacement payload")
        expect(refused.transport.targetsCount == 5 && refused.transport.disconnectCount == 1,
               "signature checking follows a complete, still-bounded old-target absence proof")
    }
    for replacement in [false, true] {
        let refused = await run(replacement: replacement, refuseAfterProof: true); closed(refused)
        expect(refused.outcome == .failed(reason: "target-identity") && scans(refused.fixture) == (replacement ? 5 : 3)
               && refused.payloads == (replacement ? 1 : 0),
               "a signature rejection armed by the final same-page read is caught before that generation's payload")
    }
    for phase in ["discovery", "replacement", "recheck"] {
        for drift in ["pid", "start", "uid", "executable", "listener", "cancel", "budget"] {
            let result = await run(replacement: phase == "replacement", drift: drift, driftPhase: phase); closed(result)
            let expected: StartupOutcome = drift == "cancel" ? .partial(reason: "startup-interrupted")
                : .failed(reason: drift == "budget" ? "attach-timeout" : drift == "listener" ? "listener-mismatch" : "target-identity")
            expect(result.invalidated && result.outcome == expected,
                   "\(phase) polls still enforce \(drift) using the original run budget and fresh ownership")
            expect(result.transport.connectedURLs.count == (phase == "discovery" ? 0 : 1)
                   && result.payloads == (phase == "discovery" ? 0 : 1),
                   "ownership/cancellation/deadline failure cannot connect or install a later page")
            if drift == "budget" { expect(result.fixture.now == 160, "polling never resets or extends the original absolute deadline") }
        }
    }
    return checks
}

private func standaloneSignatureBoundaryChecks() async throws -> Int {
    var checks = 0
    func expect(_ condition: @autoclosure () -> Bool, _ label: String) {
        guard condition() else { fatalError("FAILED: standalone signature boundaries: \(label)") }
        checks += 1
    }
    func scans(_ fixture: FakeCodexTargetEnvironmentState) -> Int {
        fixture.commandCalls.filter { $0.file == "/usr/bin/codesign" }.count
    }
    let goodState: [String: Any] = [
        "applied": true, "version": "0.9.0", "imageDecoded": true,
        "matchedSurfaces": 3, "transparentSurfaces": 3, "backgroundMatched": true,
        "coverMatched": true, "fixedViewport": true, "rootClear": true,
        "workspaceBackgroundClear": true, "footerSurfaces": 2, "footerBackgroundClear": true,
        "footerFadeSurfaces": 1, "footerFadeClear": true, "topFadeSurfaces": 1,
        "topFadeClear": true, "decorationEffectsClear": true, "unsupportedDecorations": [String](),
    ]
    let page: [String: Any] = ["type": "page", "url": "app://-/index.html?initialRoute=%2F",
                               "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/standalone-signature"]
    let payload = "standalone-signature-payload"
    for action in ["apply", "retry", "restore"] {
        for refusal in [0, 3, 4] {
            let fixture = FakeCodexTargetEnvironmentState(
                bundle: URL(fileURLWithPath: "/private/Agent-Skin-Signature-Fixture.app"),
                executable: URL(fileURLWithPath: "/private/Agent-Skin-Signature-Fixture.app/Contents/MacOS/Codex"))
            fixture.commandResponses["/usr/sbin/lsof"] = "p\(fixture.pid)\nn127.0.0.1:49221\n"
            let resolver = CodexStartupTargetSystem(environment: fixture.environment())
            let request = try WallpaperRequest([
                "--action", action, "--target-pid", String(fixture.pid), "--target-bundle", fixture.bundle.path,
                "--target-start-time", String(fixture.launchDate.timeIntervalSince1970), "--port", "49221",
            ], resolver: resolver)
            // Request construction uses the same injected target facts. Count
            // only the actual standalone operation after resolution completes.
            fixture.commandCalls.removeAll()
            fixture.afterCommand = { [weak fixture] file in
                guard let fixture, refusal > 0 else { return }
                if file == "/usr/bin/codesign", scans(fixture) == refusal - 1 {
                    fixture.commandFailures[file] = "inspection-failed"
                }
            }
            let system = ProductionWallpaperTestSystem(fixture.environment())
            let state = action == "restore" ? ["applied": false, "version": "0.9.0"] as [String: Any] : goodState
            let session = FakeWallpaperPageSession(responses: [
                WallpaperCLI.applyGuardSource: ["state": "ready"], payload: goodState,
                WallpaperCLI.retrySource: ["retried": true, "wallpaper": goodState],
                WallpaperCLI.restoreSource: ["restored": true], WallpaperCLI.statusSource: state,
            ])
            let transport = FakeWallpaperOperationTransport(pages: [page], session: session)
            var result: [String: Any]?
            var failureState: String?
            do {
                result = try await WallpaperCLI.perform(
                    request, began: 100, system: system, transport: transport, now: { fixture.now },
                    expectedVersion: "0.9.0", sourceLoader: { payload }, sleep: { fixture.now += $0 })
            } catch let error as WallpaperFailure { failureState = error.state }
            let expectedSources = action == "apply" ? [WallpaperCLI.applyGuardSource, payload, WallpaperCLI.statusSource]
                : [action == "retry" ? WallpaperCLI.retrySource : WallpaperCLI.restoreSource, WallpaperCLI.statusSource]
            expect(system.processValidations == 0 && system.lockAcquired == 1 && system.lockReleased == 1
                   && !system.validationWithoutLock && transport.closeCount == 1 && transport.pagesCount == 1,
                   "standalone \(action) preserves full validation and its lock/transport lifecycle")
            if refusal == 0 {
                expect(failureState == nil && result?["state"] as? String == (action == "restore" ? "restored" : "applied")
                       && scans(fixture) == 4 && system.fullValidations == 4,
                       "standalone \(action) keeps entry, outer-poll, pre-action and post-status signature checks")
                expect(session.evaluatedSources == expectedSources && session.closeCount == 1,
                       "successful \(action) sends exactly its original action and independent status sequence")
            } else {
                // The existing CLI catches the first per-page signature error,
                // then its next outer validation refuses before another page
                // read. Preserve that behavior; do not invent an early return.
                expect(result == nil && failureState == "signature-refused" && scans(fixture) == refusal + 1
                       && system.fullValidations == refusal + 1,
                       "standalone \(action) retains its existing signature-refusal behavior at boundary \(refusal)")
                expect(session.evaluatedSources == (refusal == 3 ? [] : expectedSources)
                       && session.closeCount == (refusal == 3 ? 0 : 1),
                       "pre-action refusal sends nothing; post-status refusal never replays an already sent action")
            }
        }
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
        "id": "unit-startup", "type": "page", "url": startupURL,
        "webSocketDebuggerUrl": "ws://127.0.0.1:49221/devtools/page/unit-startup",
    ]
    let nowAtZero: () -> TimeInterval = { 0 }
    let noSleep: (TimeInterval) async throws -> Void = { _ in }
    func run(
        _ system: FakeWallpaperSystem,
        _ transport: FakeWallpaperStartupTransport,
        port: Int = 49221,
        payload: String = "fixture-payload",
        deadline: TimeInterval = 45,
        now: @escaping () -> TimeInterval,
        sleep: @escaping (TimeInterval) async throws -> Void
    ) async -> StartupOutcome {
        await StartupConnector(target: target, expectedPort: port, system: system, transport: transport,
                               now: now, sleep: sleep).run(payload: payload, deadline: deadline)
    }

    let disabledWallpaperStatus: [String: Any] = [
        "owner": "azhou-codex-startup", "version": 1, "phase": "complete", "runId": 19,
        "ready": true, "completed": true, "overlay": false, "reason": "",
        "wallpaper": ["applied": false, "reason": "disabled", "imageDecoded": false],
        "completion": ["cause": "natural", "beforeReady": false],
    ]
    let disabledWallpaperStartup = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(pages: [page], evaluations: [
            ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
                            now: { 45 }, sleep: noSleep)
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
            pages: [page], evaluations: [["href": startupURL, "controllerPresent": false, "shellReady": true]]
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
    for id in [NSNull(), "other-target"] as [Any] {
        var unboundPage = page; unboundPage["id"] = id
        let unbound = await run(FakeWallpaperSystem(), FakeWallpaperStartupTransport(pages: [unboundPage]),
                                now: nowAtZero, sleep: noSleep)
        expect(unbound == .failed(reason: "page-unsupported"),
               "startup requires an explicit target ID matching its websocket")
    }
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
            pages: [page], evaluations: [["href": "https://example.com/", "controllerPresent": false, "shellReady": true]]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(unsupportedPage == .failed(reason: "page-unsupported"),
           "startup verifies the page URL again after connecting")
    let existingController = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page], evaluations: [["href": startupURL, "controllerPresent": true, "shellReady": true]]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(existingController == .partial(reason: "startup-active"),
           "startup does not install a second controller when one is already present")

    let malformedInstall = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page],
            evaluations: [
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
                ["installed": false, "reason": "private renderer error"],
            ]
        ), now: nowAtZero, sleep: noSleep
    )
    expect(untrustedInstallFailure == .failed(reason: "protocol-error"),
           "untrusted install error text is reduced to the protocol category")
    let missingActiveFlagTransport = FakeWallpaperStartupTransport(
        pages: [page],
        evaluations: [
            ["href": startupURL, "controllerPresent": false, "shellReady": true],
            ["installed": true],
        ]
    )
    let missingActiveFlag = await run(FakeWallpaperSystem(), missingActiveFlagTransport,
                                      now: nowAtZero, sleep: noSleep)
    expect(missingActiveFlag == .failed(reason: "protocol-error")
           && missingActiveFlagTransport.closeCount == 1
           && missingActiveFlagTransport.disposeCount == 0,
           "an incomplete install receipt cannot authorize cleanup without a retained controller binding")
    let alreadyActiveInstall = await run(
        FakeWallpaperSystem(), FakeWallpaperStartupTransport(
            pages: [page],
            evaluations: [
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
                ["href": startupURL, "controllerPresent": false, "shellReady": true],
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
             system: FakeWallpaperSystem, transport: FakeWallpaperOperationTransport,
             journalComplete: Bool = true)
        -> (Int32, [String: Any]?, [[String: Any]]) {
        var output: Data?
        var journal: [[String: Any]] = []
        let code = WallpaperCLI.run(
            arguments, resolver: resolver, system: system, transportFactory: { transport },
            now: { ProcessInfo.processInfo.systemUptime }, expectedVersion: "0.9.0",
            sourceLoader: { "unused-test-payload" }, sleep: { _ in },
            journal: { journal.append($0); return journalComplete }, output: { output = $0 }
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

    let applySession = FakeWallpaperPageSession(responses: [
        WallpaperCLI.applyGuardSource: ["state": "ready"],
        "unused-test-payload": goodState,
        WallpaperCLI.statusSource: goodState,
    ])
    let incomplete = run(["--wallpaper-helper", "--action", "apply", "--target-pid", "4123",
                          "--target-bundle", "/tmp/Codex.app", "--port", "49221"],
                         resolver: FakeWallpaperTargetResolver(), system: FakeWallpaperSystem(),
                         transport: FakeWallpaperOperationTransport(pages: [page], session: applySession),
                         journalComplete: false)
    expect(incomplete.0 == 0 && incomplete.1?["state"] as? String == "applied"
           && incomplete.1?["journalStatus"] as? String == "not-recorded"
           && incomplete.2.count == 1 && incomplete.2[0]["journalStatus"] == nil,
           "CLI reports an incomplete journal without changing a successful wallpaper result")

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
    private var pageSteps: [Result<[[String: Any]], Error>]?
    private var targetSteps: [Result<[[String: Any]], Error>]?
    private var evaluationSteps: [Result<[String: Any], Error>]?
    var onPages: ((Int) -> Void)?
    var onTargets: ((Int) -> Void)?
    private(set) var pagesCount = 0
    private(set) var targetsCount = 0
    private(set) var connectedURLs: [URL] = []
    private(set) var evaluatedSources: [String] = []
    private(set) var disconnectCount = 0
    private(set) var closeCount = 0
    private(set) var disposeCount = 0

    init(pages: [[String: Any]] = [], evaluations: [[String: Any]] = [],
         throwGenericPageError: Bool = false,
         pageSteps: [Result<[[String: Any]], Error>]? = nil,
         targetSteps: [Result<[[String: Any]], Error>]? = nil,
         evaluationSteps: [Result<[String: Any], Error>]? = nil) {
        responsePages = pages
        evaluationResponses = evaluations
        self.throwGenericPageError = throwGenericPageError
        self.pageSteps = pageSteps
        self.targetSteps = targetSteps
        self.evaluationSteps = evaluationSteps
    }

    func pages(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        pagesCount += 1
        onPages?(pagesCount)
        if var steps = pageSteps {
            guard !steps.isEmpty else { throw StartupFailure(reason: "protocol-error", message: "fixture page steps exhausted") }
            let step = steps.removeFirst(); pageSteps = steps
            return try step.get()
        }
        if throwGenericPageError { throw URLError(.cannotConnectToHost) }
        return responsePages
    }

    func targets(port: Int, timeout: TimeInterval) async throws -> [[String: Any]] {
        targetsCount += 1
        onTargets?(targetsCount)
        // Unscripted test transports still have no complete-inventory authority.
        guard var steps = targetSteps, !steps.isEmpty else {
            throw StartupFailure(reason: "protocol-error", message: "fixture has no complete target inventory")
        }
        let step = steps.removeFirst(); targetSteps = steps
        return try step.get()
    }

    func connect(to url: URL, timeout: TimeInterval) throws { connectedURLs.append(url) }

    func evaluate(_ source: String, timeout: TimeInterval) async throws -> [String: Any] {
        evaluatedSources.append(source)
        if source.contains("dispose.value.call(api)") { disposeCount += 1 }
        if var steps = evaluationSteps {
            guard !steps.isEmpty else { throw StartupFailure(reason: "protocol-error", message: "fixture evaluation steps exhausted") }
            let step = steps.removeFirst(); evaluationSteps = steps
            return try step.get()
        }
        return evaluationResponses.isEmpty ? [:] : evaluationResponses.removeFirst()
    }

    func disconnectPage() { disconnectCount += 1 }

    func close() { closeCount += 1 }
}

private final class FakeWallpaperOperationLock: StartupOperationLock {
    private var releaseBody: (() -> Void)?
    init(release: @escaping () -> Void) { releaseBody = release }
    func release() { let body = releaseBody; releaseBody = nil; body?() }
}

/// Identity/listener/signature checks run through the real production system's
/// existential witness table. Only the operation lock is a local test double.
private final class ProductionWallpaperTestSystem: StartupTargetSystem {
    private let base: any StartupTargetSystem
    private(set) var fullValidations = 0
    private(set) var processValidations = 0
    private(set) var listenerValidations = 0
    private(set) var lockAcquired = 0
    private(set) var lockReleased = 0
    private(set) var validationWithoutLock = false
    init(_ environment: CodexTargetEnvironment) { base = CodexStartupTargetSystem(environment: environment) }
    func preflightBundle(_ bundle: URL, deadline: TimeInterval) throws { try base.preflightBundle(bundle, deadline: deadline) }
    func validate(_ target: StartupTargetFacts, deadline: TimeInterval) throws {
        fullValidations += 1
        validationWithoutLock = validationWithoutLock || lockAcquired != 1 || lockReleased != 0
        try base.validate(target, deadline: deadline)
    }
    func validateProcess(_ target: StartupTargetFacts, deadline: TimeInterval) throws {
        processValidations += 1
        validationWithoutLock = validationWithoutLock || lockAcquired != 1 || lockReleased != 0
        try base.validateProcess(target, deadline: deadline)
    }
    func listeningPorts(_ target: StartupTargetFacts, deadline: TimeInterval) throws -> [Int] {
        listenerValidations += 1
        return try base.listeningPorts(target, deadline: deadline)
    }
    func acquireOperationLock(pid: Int32) throws -> any StartupOperationLock {
        lockAcquired += 1
        return FakeWallpaperOperationLock { [weak self] in self?.lockReleased += 1 }
    }
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
    private let sendError: Error?
    private(set) var sentTexts: [String] = []
    private(set) var resumeCount = 0
    private(set) var cancelCount = 0
    var maximumMessageSize = 0

    init(responses: [URLSessionWebSocketTask.Message], sendFails: Bool = false, receiveFails: Bool = false, sendError: Error? = nil) {
        self.responses = responses
        self.sendFails = sendFails
        self.receiveFails = receiveFails
        self.sendError = sendError
    }

    func resume() { resumeCount += 1 }

    func send(_ message: URLSessionWebSocketTask.Message) async throws {
        if let sendError { throw sendError }
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
