import Foundation
@MainActor final class Fixture {
    let key = HostApplicationKey(host: .zcode, bundleURL: URL(fileURLWithPath:"/Applications/ZCode.app"), executableURL: URL(fileURLWithPath:"/Applications/ZCode.app/Contents/MacOS/ZCode"), bundleIdentifier:"dev.zcode.app", version:"3.17.1", build:"3.17.1.9553", executableSHA256:String(repeating:"a",count:64))
    var processes: [HostProcessGeneration] = []
    var calls: [String] = []
    var purposes: [ZCodeAttachPurpose] = []
    var enforceLock = false
    var lockHeld = false
    var mode = "ready"
    var inspection: PageEffect?
    var payloadHash = String(repeating:"b",count:64)
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
        ControllerReceipt(location:PageLocation(application:key,process:binding.process,documentToken:binding.documentToken),owner:ZCodeSkinDriver.owner,protocolVersion:1,payloadSHA256:payloadHash,controllerInstanceID:"instance-1",createdByOperationID:op ?? request.operationID)
    }
    var binding: ZCodePageBinding { ZCodePageBinding(process:process,endpoint:URL(string:endpoint)!,pageURL:URL(string:page)!,targetID:"target1",documentToken:"context1") }
    func assembly() -> ZCodeSkinAssembly {
        ZCodeSkinAssembly(now:{self.clock},runningProcesses:{self.calls.append("running");return self.processes},validateProcess:{p in self.calls.append("validate");if self.expired { throw NSError(domain:"synthetic",code:1) }},activateExisting:{_ in self.calls.append("activate");return true},openApplication:{_ in self.calls.append("open");return self.process},attach:{_,deadline,purpose in
            self.calls.append("attach");self.purposes.append(purpose)
            if self.mode == "listener-46" {
                let limit=purpose.stageDeadline(caller:deadline,now:self.clock)
                self.clock += 46
                if self.clock >= limit { throw ZCodeAttachFailure.deadline }
            }
            if self.mode == "attach-deadline" { throw ZCodeAttachFailure.deadline }
            if self.mode == "attach-cancelled" { throw ZCodeAttachFailure.cancelled }
            return self.binding
        },install:{b,r,obs in
            self.calls.append("install")
            if self.mode == "before-send" { throw NSError(domain:"synthetic",code:1) }
            if self.mode == "skip-before-send" { return .skipped(.notObserved(reason:"fixture"),runID:1,beforeReady:true) }
            obs.markSent()
            if self.mode == "skip-after-send" { return .skipped(.notObserved(reason:"fixture"),runID:1,beforeReady:true) }
            if self.mode == "hold" || self.mode == "hold-ready" || self.mode == "hold-existing" {
                await withCheckedContinuation { self.waiting = $0 }
                if self.mode == "hold" { throw NSError(domain:"synthetic",code:3) }
            }
            if self.mode == "lost-reply" { throw NSError(domain:"synthetic",code:2) }
            if self.mode == "drift-after-send" { self.expired = true }
            if self.mode == "ready-timeout" { self.clock = 161 }
            if self.mode == "hold-existing" { return .skipped(.present(.instance(self.receipt(b,op:UUID())),acquisition:.alreadyActive),runID:2,beforeReady:true) }
            if self.mode == "already-active" { return .skipped(.present(.instance(self.receipt(b,op:UUID())),acquisition:.alreadyActive),runID:2,beforeReady:true) }
            if self.mode.hasPrefix("direct-") {
                let acquisition: PageAcquisition = self.mode.contains("existing") ? .alreadyActive : .created
                let original = self.receipt(b,op:self.mode.contains("existing") ? UUID() : nil)
                let receipt = self.mode.contains("foreign") ? ControllerReceipt(location:original.location,owner:"foreign",protocolVersion:1,payloadSHA256:original.payloadSHA256,controllerInstanceID:original.controllerInstanceID,createdByOperationID:original.createdByOperationID) : original
                let page = PageEffect.present(.instance(receipt), acquisition:acquisition)
                let cleanup = CleanupReport(state:.notNeeded,released:[],intentionallyRetained:["confirmed-controller"],unconfirmed:[])
                let failure = SkinOperationFailure(reason:.operationCancelled,detail:"synthetic-known-page")
                if self.mode.contains("failed") {return .failed(failure,page:page,cleanup:cleanup)}
                return .partial(failure,page:page,cleanup:cleanup)
            }
            if self.mode == "bad-receipt" { return .ready(self.receipt(b,op:UUID()),runID:1) }
            return .ready(self.receipt(b),runID:1)
        },inspectPage:{b,_ in
            self.calls.append("inspect")
            if self.mode == "hold-inspect" { await withCheckedContinuation { self.waiting = $0 } }
            if self.mode == "inspection-error" { throw NSError(domain:"synthetic-inspection",code:1) }
            return self.inspection ?? .present(.instance(self.receipt(b)),acquisition:.alreadyActive)
        },dispose:{_,_,_ in self.calls.append("dispose");return self.mode != "dispose-failed"},acquireOperation:{_ in
            self.calls.append("lock")
            if self.mode == "lock-failed" { throw NSError(domain:"synthetic",code:9) }
            if self.mode == "lock-expired-busy" { self.clock = 201;throw ZCodeOperationLockFailure.busy }
            if self.mode == "lock-cancel-busy" { Thread.sleep(forTimeInterval:0.12);throw ZCodeOperationLockFailure.busy }
            if self.mode == "lock-expired-success" { self.clock = 201;self.lockHeld = true;return Lease(self) }
            if self.mode == "lock-cancel-success" { Thread.sleep(forTimeInterval:0.12);self.lockHeld = true;return Lease(self) }
            if self.enforceLock && self.lockHeld { throw ZCodeOperationLockFailure.busy }
            self.lockHeld = true
            return Lease(self)
        })
    }
    func driver(_ capabilities: [SkinCapability] = SkinCapability.allCases) -> ZCodeSkinDriver { ZCodeSkinDriver(inputs:inputs(capabilities),assembly:assembly()) }
}
@MainActor final class Lease: ZCodeOperationLease { let f:Fixture;init(_ f:Fixture){self.f=f};func release(){f.calls.append("release");f.lockHeld = false} }
@main struct ZCodeTests {
    @MainActor static func main() async {
        var count = 0
        func expect(_ value: Bool, _ name: String) { precondition(value,name);count += 1 }
        do {
            expect(ZCodeAttachPurpose.coldLaunch.stageDeadline(caller:200,now:100)==145,"cold stage capped to 45")
            expect(ZCodeAttachPurpose.coldLaunch.stageDeadline(caller:120,now:100)==120,"cold honors caller deadline")
            expect(ZCodeAttachPurpose.existingPage.stageDeadline(caller:200,now:100)==200,"existing page preserves deadline")
        }
        do {
            let f=Fixture();f.mode="listener-46";let result=await f.driver().launch(f.request)
            if case .failed(let failure,_,_) = result { expect(failure.reason == .operationTimeout,"cold 46s listener hits stage deadline") } else { fatalError("cold 46s accepted") }
            expect(f.purposes == [.coldLaunch],"cold attaches with cold purpose")
        }
        do {
            let f=Fixture();f.mode="listener-46";f.processes=[f.process]
            let result=await f.driver().inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil))
            if case .observed = result { expect(f.purposes == [.existingPage] && f.clock == 146,"page inspect honors caller deadline after 46s") } else { fatalError("inspect deadline shortened") }
        }
        do {
            let f=Fixture();f.mode="listener-46";f.processes=[f.process]
            let result=await f.driver().disable(SkinDisableRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,expectedPage:.instance(f.receipt(f.binding))))
            if case .removed = result { expect(f.purposes == [.existingPage] && f.clock == 146,"disable honors caller deadline after 46s") } else { fatalError("disable deadline shortened") }
        }
        do {
            let f=Fixture();let driver=f.driver();f.mode="lock-failed";_ = await driver.launch(f.request)
            expect(f.purposes.isEmpty,"failed cold lock never attaches")
            f.mode="ready";f.processes=[f.process]
            let result=await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil))
            if case .observed = result { expect(f.purposes == [.existingPage],"failed cold operation cannot leak wait purpose") } else { fatalError("post-lock inspect failed") }
        }
        for (mode,reason) in [("attach-deadline",SkinFailureReason.operationTimeout),("attach-cancelled",SkinFailureReason.operationCancelled)] {
            let f=Fixture();f.mode=mode;let result=await f.driver().launch(f.request)
            if case .failed(let error,_,_) = result { expect(error.reason == reason,mode+" preserves error class") } else { fatalError(mode+" did not fail") }
        }
        do {
            let f=Fixture();f.mode="hold-inspect";f.processes=[f.process];let driver=f.driver()
            let first=Task { await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil)) }
            while f.waiting == nil { await Task.yield() }
            let second=await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil))
            if case .staleTarget(let failure)=second { expect(failure.reason == .operationBusy,"second page inspect refuses while busy") } else { fatalError("overlapping page inspect accepted") }
            let disabled=await driver.disable(SkinDisableRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,expectedPage:.instance(f.receipt(f.binding))))
            if case .refused(let failure,_) = disabled { expect(failure.reason == .operationBusy,"disable refuses while inspect owns connection") } else { fatalError("overlapping disable accepted") }
            let appOnly=await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:false,previousObservation:nil))
            if case .observed(_, .notObserved) = appOnly { expect(true,"application-only inspect remains available") } else { fatalError("application-only inspect blocked") }
            expect(f.calls.filter{$0=="attach"}.count == 1,"overlap does not attach a replacement")
            f.waiting?.resume()
            if case .observed = await first.value { expect(f.calls.filter{$0=="release"}.count == 1,"first inspect finishes and releases exactly once") } else { fatalError("original inspect interrupted") }
        }
        do {
            let f=Fixture();f.mode="hold-ready";let driver=f.driver()
            let first=Task { await driver.launch(f.request) }
            while f.waiting == nil { await Task.yield() }
            let inspected=await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil))
            if case .staleTarget(let failure)=inspected { expect(failure.reason == .operationBusy,"inspect refuses while launch owns connection") } else { fatalError("inspect raced launch") }
            expect(f.calls.filter{$0=="attach"}.count == 1,"inspect did not replace launch connection")
            f.waiting?.resume()
            if case .ready = await first.value { expect(f.calls.filter{$0=="release"}.count == 1,"launch finishes and releases exactly once") } else { fatalError("launch interrupted") }
        }
        do {
            let f=Fixture();f.mode="hold-inspect";f.enforceLock=true;f.processes=[f.process]
            let firstDriver=f.driver(), secondDriver=f.driver()
            let first=Task { await firstDriver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil)) }
            while f.waiting == nil { await Task.yield() }
            let second=await secondDriver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil))
            if case .staleTarget(let failure) = second { expect(failure.reason == .operationBusy && f.calls.filter{$0=="attach"}.count == 1,"cross-driver lock reports busy before replacement attach") } else { fatalError("cross-driver lock bypassed") }
            f.waiting?.resume()
            if case .observed = await first.value { expect(!f.lockHeld && f.calls.filter{$0=="release"}.count == 1,"cross-driver contention preserves first and releases once") } else { fatalError("cross-driver contention interrupted first") }
        }
        for mode in ["attach-deadline","attach-cancelled","inspection-error"] {
            let f=Fixture();f.mode=mode;f.processes=[f.process];let driver=f.driver()
            let first=await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil))
            if case .staleTarget(let failure) = first {
                if mode == "attach-deadline" { expect(failure.reason == .operationTimeout,"inspect deadline preserved") }
                if mode == "attach-cancelled" { expect(failure.reason == .operationCancelled,"inspect cancellation preserved") }
                expect(f.calls.filter{$0=="release"}.count == 1,"inspect failure releases once: "+mode)
            } else { fatalError("failing inspect reported success") }
            f.mode="ready"
            if case .observed = await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil)) {
                expect(f.calls.filter{$0=="release"}.count == 2,"inspect can be reused after failure: "+mode)
            } else { fatalError("inspect remained busy after failure") }
        }
        do {
            let f=Fixture();f.processes=[f.process];f.mode="lock-expired-busy"
            let result=await f.driver().inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil))
            if case .staleTarget(let failure)=result { expect(failure.reason == .operationTimeout && !f.calls.contains("attach"),"deadline takes precedence over late busy lock") } else { fatalError("late busy lock accepted") }
        }
        do {
            let f=Fixture();f.processes=[f.process];f.mode="lock-cancel-busy"
            let task=Task { await f.driver().inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil)) }
            Task.detached { try? await Task.sleep(nanoseconds:20_000_000);task.cancel() }
            if case .staleTarget(let failure)=await task.value { expect(failure.reason == .operationCancelled && !f.calls.contains("attach"),"cancellation takes precedence over late busy lock") } else { fatalError("cancelled busy lock accepted") }
        }
        do {
            let f=Fixture();f.processes=[f.process];f.mode="lock-expired-success";let driver=f.driver()
            let result=await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil))
            if case .staleTarget(let failure)=result { expect(failure.reason == .operationTimeout && !f.calls.contains("attach") && f.calls.filter{$0=="release"}.count == 1,"successful lock after deadline releases once without attach") } else { fatalError("expired acquired lock accepted") }
            f.mode="ready";f.clock=100
            if case .observed = await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil)) { expect(f.calls.filter{$0=="release"}.count == 2,"inspect reusable after expired lock") } else { fatalError("expired lock did not release") }
        }
        do {
            let f=Fixture();f.processes=[f.process];f.mode="lock-cancel-success";let driver=f.driver()
            let task=Task { await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil)) }
            Task.detached { try? await Task.sleep(nanoseconds:20_000_000);task.cancel() }
            if case .staleTarget(let failure)=await task.value { expect(failure.reason == .operationCancelled && !f.calls.contains("attach") && f.calls.filter{$0=="release"}.count == 1,"successful lock after cancellation releases once without attach") } else { fatalError("cancelled acquired lock accepted") }
            f.mode="ready"
            if case .observed = await driver.inspect(SkinInspectRequest(expectedApplication:f.key,operationID:UUID(),deadline:200,includePage:true,previousObservation:nil)) { expect(f.calls.filter{$0=="release"}.count == 2,"inspect reusable after cancelled lock") } else { fatalError("cancelled lock did not release") }
        }
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
        do {let f=Fixture();f.payloadHash += "\n";let result=await f.driver().launch(f.request);if case .failed(_,let page,let cleanup)=result {expect(page.isInstallationUnknown && cleanup.state == .unknown,"payload digest exact length rejects newline")}else{fatalError("hash suffix accepted")}}
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
        for mode in ["direct-partial", "direct-failed", "direct-existing-partial"] {let f=Fixture();f.mode=mode;let result=await f.driver().launch(f.request);let page:PageEffect;let cleanup:CleanupReport;switch result {case .partial(_,let p,let c),.failed(_,let p,let c):page=p;cleanup=c;default:fatalError("direct confirmed result lost")};if case .present(.instance(let receipt),let acquisition)=page {expect(receipt.owner == ZCodeSkinDriver.owner && cleanup.state == .notNeeded,"direct result preserves confirmed page/cleanup "+mode);if mode.contains("existing") {if case .alreadyActive=acquisition {expect(true,"existing acquisition preserved")}else{fatalError("rollback right upgraded")}}}else{fatalError("direct page erased")};expect(!f.calls.contains("dispose"),"no automatic rollback "+mode)}
        do {let f=Fixture();f.mode="direct-foreign-partial";let result=await f.driver().launch(f.request);if case .failed(_,let p,let c)=result {expect(p.isInstallationUnknown && c.state == .unknown,"foreign confirmed receipt rejected")}else{fatalError("foreign direct accepted")}}
        do {let f=Fixture();f.mode="hold-existing";let driver=f.driver();let task=Task {await driver.launch(f.request)};while f.waiting == nil {await Task.yield()};task.cancel();f.waiting?.resume();let result=await task.value;if case .partial(_,.present(.instance(let receipt),.alreadyActive),let c)=result {expect(receipt.createdByOperationID != f.request.operationID && c.state == .notNeeded,"cancel after existing skip preserves acquisition without rollback");expect(!f.calls.contains("dispose"),"cancel existing never disposes")}else{fatalError("existing cancellation receipt erased")}}
        // Binding and inspection counterexamples: synthetic ports only.
        do {
            let f = Fixture(), original = Fixture().inputs()
            let inputs = BoundHostInputs(identity: original.identity, findings: original.findings, contractVersion: "unsupported-contract")
            let result = await ZCodeSkinDriver(inputs: inputs, assembly: f.assembly()).launch(f.request)
            if case .refused(let refusal) = result { expect(refusal.reason == .identityMismatch && f.calls.isEmpty, "wrong bound contract refuses before IO") }
            else { fatalError("bound contract accepted") }
        }
        do {
            let f = Fixture(), original = Fixture().inputs()
            let finding = original.findings[0]
            let inputs = BoundHostInputs(identity: original.identity, findings: [finding, finding], contractVersion: original.contractVersion)
            let result = await ZCodeSkinDriver(inputs: inputs, assembly: f.assembly()).launch(f.request)
            if case .refused(let refusal) = result { expect(refusal.reason == .evidenceMismatch && f.calls.isEmpty, "conflicting evidence refuses before IO") }
            else { fatalError("duplicate evidence accepted") }
        }
        do {
            let f = Fixture(); f.processes = [f.process]
            let result = await f.driver().inspect(SkinInspectRequest(expectedApplication: f.key, operationID: UUID(), deadline: 200, includePage: true, previousObservation: .instance(f.receipt(f.binding))))
            if case .observed(let process, .present(.instance(let receipt), .alreadyActive)) = result {
                expect(process == f.process && receipt.location == f.receipt(f.binding).location, "inspect preserves same-generation confirmed receipt")
                expect(!f.calls.contains("install") && !f.calls.contains("dispose"), "page inspect performs no install or disposal")
            } else { fatalError("same generation inspection lost") }
        }
        for legacy in [false, true] {
            let f = Fixture(); f.processes = [f.process]
            let old = PageLocation(application: f.key, process: f.process, documentToken: "old-context")
            let receipt = f.receipt(f.binding)
            let previous: PageObservation = legacy
                ? .legacyV1(LegacyV1Observation(location: old, owner: "azhou-codex-startup", protocolVersion: 1))
                : .instance(ControllerReceipt(location: old, owner: receipt.owner, protocolVersion: receipt.protocolVersion, payloadSHA256: receipt.payloadSHA256, controllerInstanceID: receipt.controllerInstanceID, createdByOperationID: receipt.createdByOperationID))
            let result = await f.driver().inspect(SkinInspectRequest(expectedApplication: f.key, operationID: UUID(), deadline: 200, includePage: true, previousObservation: previous))
            if case .staleTarget(let failure) = result {
                expect(failure.reason == .targetStale && !f.calls.contains("inspect"), "old instance/legacy document refuses before page read")
            } else { fatalError("old document observed as current") }
        }
        do {
            let f = Fixture(); f.processes = [f.process]; f.payloadHash = "invalid"
            let result = await f.driver().inspect(SkinInspectRequest(expectedApplication: f.key, operationID: UUID(), deadline: 200, includePage: true, previousObservation: nil))
            if case .staleTarget(let failure) = result { expect(failure.reason == .ownerConflict, "inspect refuses malformed confirmed receipt") }
            else { fatalError("malformed inspection receipt accepted") }
        }
        for sameLocation in [true, false] {
            let f = Fixture(); f.processes = [f.process]
            let location = PageLocation(application: f.key, process: f.process, documentToken: sameLocation ? f.binding.documentToken : "other-document")
            f.inspection = .absent(location)
            let result = await f.driver().inspect(SkinInspectRequest(expectedApplication: f.key, operationID: UUID(), deadline: 200, includePage: true, previousObservation: nil))
            if sameLocation {
                if case .observed(_, .absent(let observed)) = result { expect(observed == location, "absence is accepted only for the bound document") }
                else { fatalError("bound absence lost") }
            } else {
                if case .staleTarget(let failure) = result { expect(failure.reason == .targetStale, "another document cannot prove absence") }
                else { fatalError("foreign absence accepted") }
            }
        }
        do {
            let f = Fixture(); f.processes = [f.process]
            f.inspection = .present(.legacyV1(LegacyV1Observation(location: f.receipt(f.binding).location, owner: "azhou-codex-startup", protocolVersion: 1)), acquisition: .alreadyActive)
            let result = await f.driver().inspect(SkinInspectRequest(expectedApplication: f.key, operationID: UUID(), deadline: 200, includePage: true, previousObservation: nil))
            if case .staleTarget(let failure) = result { expect(failure.reason == .ownerConflict && !f.calls.contains("dispose"), "Codex legacy controller is refused without disposal") }
            else { fatalError("legacy controller promoted to ZCode") }
        }
        for unknown in [false, true] {
            let f = Fixture(); f.processes = [f.process]
            let operationID = UUID()
            f.inspection = unknown ? .unknown(operationID: operationID, detail: "synthetic-unconfirmed") : .notObserved(reason: "synthetic-not-read")
            let result = await f.driver().inspect(SkinInspectRequest(expectedApplication: f.key, operationID: UUID(), deadline: 200, includePage: true, previousObservation: nil))
            if case .observed(_, let page) = result {
                if unknown { if case .unknown(let id, _) = page { expect(id == operationID, "inspect preserves unknown operation provenance") } else { fatalError("unknown was invented as absence") } }
                else { expect(page.isNotObserved, "inspect preserves not-observed without invented absence") }
            } else { fatalError("unconfirmed observation lost") }
        }

        print("ZCode native synthetic checks: \(count) passed; real host not run")
    }
}
