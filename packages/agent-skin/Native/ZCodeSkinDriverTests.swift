import Foundation
@MainActor final class Fixture {
    let key = HostApplicationKey(host: .zcode, bundleURL: URL(fileURLWithPath:"/Applications/ZCode.app"), executableURL: URL(fileURLWithPath:"/Applications/ZCode.app/Contents/MacOS/ZCode"), bundleIdentifier:"dev.zcode.app", version:"3.17.1", build:"3.17.1.9553", executableSHA256:String(repeating:"a",count:64))
    var processes: [HostProcessGeneration] = []
    var calls: [String] = []
    var mode = "ready"
    var endpoint = "http://127.0.0.1:1234"
    var page = "file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html?locale=en"
    var waiting: CheckedContinuation<Void, Never>?
    var expired = false
    var clock: Double = 100
    lazy var process = HostProcessGeneration(pid:123,launchTime:50,executableURL:key.executableURL)
    lazy var request = SkinLaunchRequest(expectedApplication:key,operationID:UUID(),startedAt:100,deadline:200)
    func inputs(_ capabilities: [SkinCapability] = SkinCapability.allCases) -> BoundHostInputs {
        BoundHostInputs(identity:HostIdentityEvidence(key:key,signingIdentity:"fixture",evidenceID:"synthetic"),findings:capabilities.map { CapabilityFinding(subject:CapabilityEvidenceSubject(application:key,surface:SkinHostContract.surface(for:$0),contractVersion:SkinHostContract.version),capability:$0,state:.verified,evidenceIDs:["synthetic-only"],reason:"fixture") },contractVersion:SkinHostContract.version)
    }
    func receipt(_ binding: ZCodePageBinding, op: UUID? = nil) -> ControllerReceipt {
        ControllerReceipt(location:PageLocation(application:key,process:binding.process,documentToken:binding.documentToken),owner:ZCodeSkinDriver.owner,protocolVersion:1,payloadSHA256:String(repeating:"b",count:64),controllerInstanceID:"instance-1",createdByOperationID:op ?? request.operationID)
    }
    var binding: ZCodePageBinding { ZCodePageBinding(process:process,endpoint:URL(string:endpoint)!,pageURL:URL(string:page)!,targetID:"target1",documentToken:"context1") }
    func assembly() -> ZCodeSkinAssembly {
        ZCodeSkinAssembly(now:{self.clock},runningProcesses:{self.calls.append("running");return self.processes},validateProcess:{p in self.calls.append("validate");if self.expired { throw NSError(domain:"synthetic",code:1) }},activateExisting:{_ in self.calls.append("activate");return true},openApplication:{_ in self.calls.append("open");return self.process},attach:{_,_ in self.calls.append("attach");return self.binding},install:{b,r,obs in
            self.calls.append("install")
            if self.mode == "before-send" { throw NSError(domain:"synthetic",code:1) }
            if self.mode == "skip-before-send" { return .skipped(.notObserved(reason:"fixture"),runID:1,beforeReady:true) }
            obs.markSent()
            if self.mode == "skip-after-send" { return .skipped(.notObserved(reason:"fixture"),runID:1,beforeReady:true) }
            if self.mode == "hold" || self.mode == "hold-ready" {
                await withCheckedContinuation { self.waiting = $0 }
                if self.mode == "hold" { throw NSError(domain:"synthetic",code:3) }
            }
            if self.mode == "lost-reply" { throw NSError(domain:"synthetic",code:2) }
            if self.mode == "drift-after-send" { self.expired = true }
            if self.mode == "ready-timeout" { self.clock = 161 }
            if self.mode == "already-active" { return .skipped(.present(.instance(self.receipt(b,op:UUID())),acquisition:.alreadyActive),runID:2,beforeReady:true) }
            if self.mode == "bad-receipt" { return .ready(self.receipt(b,op:UUID()),runID:1) }
            return .ready(self.receipt(b),runID:1)
        },inspectPage:{b,_ in self.calls.append("inspect");return .present(.instance(self.receipt(b)),acquisition:.alreadyActive)},dispose:{_,_,_ in self.calls.append("dispose");return self.mode != "dispose-failed"},acquireOperation:{_ in self.calls.append("lock");return Lease(self)})
    }
    func driver(_ capabilities: [SkinCapability] = SkinCapability.allCases) -> ZCodeSkinDriver { ZCodeSkinDriver(inputs:inputs(capabilities),assembly:assembly()) }
}
@MainActor final class Lease: ZCodeOperationLease { let f:Fixture;init(_ f:Fixture){self.f=f};func release(){f.calls.append("release")} }
@main struct ZCodeTests {
    @MainActor static func main() async {
        var count = 0
        func expect(_ value: Bool, _ name: String) { precondition(value,name);count += 1 }
        do { let f=Fixture();_ = f.driver();expect(f.calls.isEmpty,"constructor no IO") }
        do { let f=Fixture();f.processes=[f.process];let result=await f.driver([.applicationIdentity,.activateExistingApplication]).launch(f.request);if case .activated(let p)=result {expect(p==f.process,"hot generation") }else{fatalError("hot")};expect(!f.calls.contains("open") && !f.calls.contains("attach") && !f.calls.contains("install"),"hot no replay or attach") }
        do { let f=Fixture();let result=await f.driver().launch(f.request);if case .ready = result {expect(true,"cold ready") }else{fatalError("cold")};expect(f.calls.filter{$0=="lock"}.count==1 && f.calls.filter{$0=="release"}.count==1,"one operation lock") }
        do { let f=Fixture();let result=await f.driver([.applicationIdentity]).launch(f.request);if case .refused = result {expect(!f.calls.contains("open"),"cold missing capability before side effect")}else{fatalError("gate")}}
        do { let f=Fixture();f.processes=[f.process,f.process];let result=await f.driver().launch(f.request);if case .failed = result {expect(!f.calls.contains("activate"),"ambiguous process refuses")}else{fatalError("ambiguous")}}
        for (mode,sent) in [("before-send",false),("lost-reply",true),("bad-receipt",true),("skip-after-send",true)] {
            let f=Fixture();f.mode=mode;let result=await f.driver().launch(f.request)
            if case .failed(_,let page,let cleanup)=result {expect(page.isInstallationUnknown == sent && cleanup.state == (sent ? .unknown : .notNeeded),mode+" unknown semantics")}else{fatalError(mode)}
            expect(f.calls.contains("release"),mode+" releases lock")
        }
        for (endpoint,page) in [("http://192.0.2.1:1234", "file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html"),("http://127.0.0.1:1234", "file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/login.html"),("http://127.0.0.1:1234", "file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html?locale=en&locale=zh"),("http://127.0.0.1:1234", "file:///Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html?unknown=value")] {
            let f=Fixture();f.endpoint=endpoint;f.page=page;_ = await f.driver().launch(f.request);expect(!f.calls.contains("install"),"wrong endpoint/page refuses before install")
        }
        do {let f=Fixture();f.clock=161;_ = await f.driver().launch(f.request);expect(f.calls.isEmpty,"60second total budget before IO")}
        do {let f=Fixture();f.mode="already-active";let result=await f.driver().launch(f.request);if case .skipped(_,_,let beforeReady)=result {expect(beforeReady,"alreadyActive preserves existing instance")}else{fatalError("alreadyActive")}}
        do {let f=Fixture();f.processes=[f.process];let result=await f.driver().inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:false,previousObservation:nil));if case .observed(_,let p)=result {expect(p.isNotObserved && !f.calls.contains("attach"),"application inspect never attaches")}else{fatalError("inspect")}}
        do {let f=Fixture();f.processes=[f.process];let r=f.receipt(f.binding);let result=await f.driver().disable(SkinDisableRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,expectedPage:.instance(r)));if case .removed(let c)=result {expect(c.state == .complete,"owned disposal complete")}else{fatalError("disable")};expect(f.calls.filter{$0=="release"}.count==1,"disable releases once")}
        do {let f=Fixture();let r=f.receipt(f.binding);let result=await f.driver().disable(SkinDisableRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,expectedPage:.instance(r)));if case .alreadyAbsent=result {expect(!f.calls.contains("dispose"),"repeated dispose absent")}else{fatalError("absent")}}
        do {let f=Fixture();f.mode="dispose-failed";f.processes=[f.process];let r=f.receipt(f.binding);let result=await f.driver().disable(SkinDisableRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,expectedPage:.instance(r)));if case .partial(_,let p,let c)=result {expect(p.isInstallationUnknown && c.state == .unknown,"dispose reply missing unknown")}else{fatalError("partial")}}
        do {let f=Fixture();f.processes=[f.process];let r=f.receipt(f.binding);let foreign=ControllerReceipt(location:r.location,owner:"azhou-codex-startup",protocolVersion:1,payloadSHA256:r.payloadSHA256,controllerInstanceID:r.controllerInstanceID,createdByOperationID:r.createdByOperationID);let result=await f.driver().disable(SkinDisableRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,expectedPage:.instance(foreign)));if case .refused=result {expect(f.calls.isEmpty,"foreign owner never touches process")}else{fatalError("foreign")}}
        do {let f=Fixture();let task=Task { await f.driver().launch(f.request) };task.cancel();let result=await task.value;if case .failed(let e,_,let c)=result {expect(e.reason == .operationCancelled && c.state == .notNeeded && f.calls.isEmpty,"cancel before IO")}else{fatalError("cancel")}}
        do {let f=Fixture();f.mode="hold";let driver=f.driver();let first=Task {await driver.launch(f.request)};while f.waiting == nil {await Task.yield()};let second=await driver.launch(f.request);if case .failed(let e,_,_)=second {expect(e.reason == .operationBusy,"overlap refused")}else{fatalError("busy")};first.cancel();f.waiting?.resume();let result=await first.value;if case .failed(_,let p,let c)=result {expect(p.isInstallationUnknown && c.state == .unknown,"cancel after send unknown")}else{fatalError("cancel sent")}}
        do {let f=Fixture();f.process=HostProcessGeneration(pid:123,launchTime:nil,executableURL:f.key.executableURL);_ = await f.driver().launch(f.request);expect(!f.calls.contains("attach"),"missing birth refused")}
        do {let f=Fixture();f.page += "&windowKind=update-status";_ = await f.driver().launch(f.request);expect(!f.calls.contains("install"),"non-main windowKind refused")}
        do {let f=Fixture();f.page += "&windowKind=main";let result=await f.driver().launch(f.request);if case .ready=result {expect(true,"explicit main kind accepted")}else{fatalError("main kind")}}
        do {let f=Fixture();f.mode="skip-before-send";let result=await f.driver().launch(f.request);if case .skipped=result {expect(true,"unobserved skip allowed only before send")}else{fatalError("skip before")}}
        for mode in ["drift-after-send", "ready-timeout"] {let f=Fixture();f.mode=mode;let result=await f.driver().launch(f.request);if case .partial(let failure,.present(.instance(let receipt),_),let cleanup)=result {expect(receipt.createdByOperationID == f.request.operationID,"confirmed receipt retained after "+mode);expect(cleanup.state == (mode == "ready-timeout" ? .notNeeded : .unknown),"confirmed receipt cleanup scoped "+mode);if mode == "ready-timeout" {expect(failure.reason == .operationTimeout,"confirmed commit timeout reason")}}else{fatalError(mode+" committed receipt lost")}}
        do {let f=Fixture();f.mode="hold-ready";let driver=f.driver();let task=Task {await driver.launch(f.request)};while f.waiting == nil {await Task.yield()};task.cancel();f.waiting?.resume();let result=await task.value;if case .partial(let error,.present(.instance(let receipt),let acquisition),let cleanup)=result {expect(error.reason == .operationCancelled && receipt.createdByOperationID == f.request.operationID && cleanup.state == .notNeeded,"confirmed receipt retained after cancellation");if case .created=acquisition {expect(true,"confirmed commit acquisition preserved")}else{fatalError("acquisition")}}else{fatalError("confirmed cancellation")}}
        print("ZCode native synthetic checks: \(count) passed; real host not run")
    }
}
