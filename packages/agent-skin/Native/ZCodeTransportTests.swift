import Foundation
@main struct TransportMock {
 @MainActor static func main() async throws {
  let mode=CommandLine.arguments[1],port=Int(CommandLine.arguments[2])!
  if mode.hasPrefix("guard-") { try await deadlineGuardCase(); return }
  if ["empty","blank","login","external","ambiguous","timeout","slow-http","cancel","hot-empty"].contains(mode) {
   try await timingCase(); return
  }
  let endpoint=URL(string:"http://127.0.0.1:\(port)")!
  let process=HostProcessGeneration(pid:123,launchTime:50,executableURL:URL(fileURLWithPath:"/fixture/ZCode"))
  var guards=0
  let client=try ZCodeBoundCDP(process:process,endpoint:endpoint,installedPage:"/fixture/index.html",now:{ProcessInfo.processInfo.systemUptime},guardLive:{guards+=1})
  defer{client.close()}
  let start=ProcessInfo.processInfo.systemUptime
  var outcome="",sent=false
  if mode=="send-timeout" || mode=="receive-timeout" {
   do {_ = try await client.attach(deadline:start+0.20);fatalError("blackhole unexpectedly succeeded")}
   catch let failure as ZCodeBoundCDP.Failure {
    guard case .deadline = failure else { fatalError("socket timeout misclassified") }
    outcome="bounded-deadline"
   }
   precondition(ProcessInfo.processInfo.systemUptime-start<1.2,"deadline did not unblock actual operation")
  } else if mode=="send-cancel" || mode=="receive-cancel" {
   let task=Task { ()->Bool in
    do {_ = try await client.attach(deadline:start+5);return false}
    catch let failure as ZCodeBoundCDP.Failure {
     if case .cancelled = failure { return true }
     return false
    } catch { return false }
   }
   try await Task.sleep(nanoseconds:50_000_000);task.cancel()
   let canceled = await task.value
   precondition(canceled,"canceled operation unexpectedly succeeded")
   precondition(ProcessInfo.processInfo.systemUptime-start<1.2,"cancel did not unblock operation")
   outcome="cancel-unblocked"
  }else{
   let binding=try await client.attach(deadline:start+3)
   precondition(binding.documentToken=="context-1","wrong unique context")
   if mode=="normal" {
    let value=try await client.evaluateSafe("({fixture:true})",deadline:start+3)
    precondition(value["fixture"] as? Bool == true,"mock reply lost");outcome="bound-evaluate-confirmed"
   } else {
    let observation=ZCodeInstallObservation()
    do {_ = try await client.install(factoryBytes:"(metadata=>({installed:true}))",payloadSHA256:String(repeating:"a",count:64),operationID:UUID(),observation:observation,deadline:start+3);fatalError("drift response was accepted")}
    catch {sent=observation.sent;precondition(sent,"fixture never sent install");outcome="sent-drift-refused"}
   }
  }
  let result:[String:Any]=["case":mode,"outcome":outcome,"elapsed":ProcessInfo.processInfo.systemUptime-start,"guardCalls":guards,"installSent":sent,"host":false]
  print(String(decoding:try JSONSerialization.data(withJSONObject:result),as:UTF8.self))
 }
}

import Foundation
@MainActor private func timingCase() async throws {
  let mode=CommandLine.arguments[1], port=Int(CommandLine.arguments[2])!
  let process=HostProcessGeneration(pid:123,launchTime:50,executableURL:URL(fileURLWithPath:"/fixture/ZCode"))
  let start=ProcessInfo.processInfo.systemUptime
  let client=try ZCodeBoundCDP(process:process,endpoint:URL(string:"http://127.0.0.1:\(port)")!,installedPage:"/fixture/index.html",now:{ProcessInfo.processInfo.systemUptime},guardLive:{})
  defer {client.close()}
  let wait = mode != "hot-empty"
  let deadline=start+(["timeout","slow-http"].contains(mode) ? 0.4 : 2.0)
  var outcome="unexpected"
  if mode == "cancel" {
   let task=Task { () -> Bool in
    do {_ = try await client.attach(deadline:deadline,waitForInitialMain:true);return false}
    catch {
     let normalized=ZCodeNativeRuntime.normalizedAttachFailure(error,deadline:deadline,now:ProcessInfo.processInfo.systemUptime,cancelled:Task.isCancelled)
     if let e=normalized as? ZCodeAttachFailure, case .cancelled = e { return true }
     return false
    }
   }
   try await Task.sleep(nanoseconds:200_000_000)
   task.cancel()
   let cancelled = await task.value
   precondition(cancelled,"cancellation succeeded instead of refusing")
   precondition(client.discoveryAttempts >= 1,"cancel did not attempt discovery")
   outcome="cancelled"
  } else if ["empty","blank","normal"].contains(mode) {
   let binding=try await client.attach(deadline:deadline,waitForInitialMain:wait)
   precondition(binding.documentToken=="context-1")
   if mode != "normal" { precondition(client.discoveryAttempts >= 2 && ProcessInfo.processInfo.systemUptime-start >= 0.30,"did not wait for delayed page") }
   outcome="bound"
  } else {
   do { _ = try await client.attach(deadline:deadline,waitForInitialMain:wait); fatalError("unexpected bind") }
   catch {
    if ["timeout","slow-http"].contains(mode) {
     let normalized=ZCodeNativeRuntime.normalizedAttachFailure(error,deadline:deadline,now:ProcessInfo.processInfo.systemUptime,cancelled:Task.isCancelled)
     guard let e=normalized as? ZCodeAttachFailure, case .deadline = e else { fatalError("wrong deadline error type: \(type(of:error))") }
    } else {
     guard let e=error as? ZCodeBoundCDP.Failure, case .identity = e else { fatalError("wrong identity error type: \(type(of:error))") }
    }
    if mode == "ambiguous" { precondition(client.attachmentStage == .mainPageAmbiguous) }
    else if !["timeout","slow-http"].contains(mode) { precondition(client.attachmentStage == .mainPageMissing) }
    if ["login","external","ambiguous","hot-empty"].contains(mode) { precondition(client.discoveryAttempts == 1,"unexpected retry");precondition(ProcessInfo.processInfo.systemUptime-start < 1.0) }
    if mode == "timeout" { precondition(client.discoveryAttempts >= 2 && ProcessInfo.processInfo.systemUptime-start >= 0.30,"deadline path not exercised") }
    outcome = ["timeout","slow-http"].contains(mode) ? "deadline-refused" : "identity-refused"
   }
  }
  let elapsed=ProcessInfo.processInfo.systemUptime-start
  precondition(elapsed < 1.8,"operation exceeded test bound")
  let report:[String:Any]=["case":mode,"outcome":outcome,"elapsed":elapsed,"attempts":client.discoveryAttempts,"stage":client.attachmentStage.rawValue,"initial":client.initialDiscoveryCounts ?? [:],"latest":client.latestDiscoveryCounts ?? [:],"host":false]
  print(String(decoding:try JSONSerialization.data(withJSONObject:report,options:.sortedKeys),as:UTF8.self))
 }
import Foundation
@MainActor private func deadlineGuardCase() async throws {
  let mode=CommandLine.arguments[1],port=Int(CommandLine.arguments[2])!
  let start=ProcessInfo.processInfo.systemUptime
  var simulated=start
  let process=HostProcessGeneration(pid:123,launchTime:50,executableURL:URL(fileURLWithPath:"/fixture/ZCode"))
  var guards=0
  let client=try ZCodeBoundCDP(process:process,endpoint:URL(string:"http://127.0.0.1:\(port)")!,installedPage:"/fixture/index.html",now:{mode.hasPrefix("guard-") ? simulated : ProcessInfo.processInfo.systemUptime},guardLive:{
   guards += 1
   if mode=="guard-error-late" { simulated=start+2;throw NSError(domain:"fixture-identity",code:1) }
   if mode=="guard-return-late" { simulated=start+2 }
   if mode=="guard-cancel-late" { Thread.sleep(forTimeInterval:0.15);throw NSError(domain:"fixture-identity",code:2) }
  })
  defer{client.close()}
  let deadline=start+(mode.hasPrefix("guard-") ? 1.0 : 0.20)
  func describe(_ error: Error, cancelled: Bool) -> String {
   let t=mode.hasPrefix("guard-") ? simulated : ProcessInfo.processInfo.systemUptime
   let normalized=ZCodeNativeRuntime.normalizedAttachFailure(error,deadline:deadline,now:t,cancelled:cancelled)
   if let e=normalized as? ZCodeAttachFailure {
    switch e {case .deadline:return "deadline";case .cancelled:return "cancelled"}
   }
   if let e=normalized as? URLError {return "url-\(e.code.rawValue)"}
   return "other-\(type(of:error))"
  }
  var outcome=""
  if mode=="guard-cancel-late" {
   let task=Task { @MainActor () -> String in
    do {_ = try await client.attach(deadline:deadline,waitForInitialMain:true);return "unexpected-success"}
    catch {return describe(error,cancelled:Task.isCancelled)}
   }
   Task.detached { try? await Task.sleep(nanoseconds:50_000_000);task.cancel() }
   outcome=await task.value
  } else {
   do {_ = try await client.attach(deadline:deadline,waitForInitialMain:true);outcome="unexpected-success"}
   catch {outcome=describe(error,cancelled:Task.isCancelled)}
  }
  let expected = mode == "guard-cancel-late" ? "cancelled" : "deadline"
  precondition(outcome == expected, "guard boundary returned wrong error classification")
  let result:[String:Any]=["case":mode,"outcome":outcome,"guardCalls":guards,"elapsed":ProcessInfo.processInfo.systemUptime-start,"host":false]
  print(String(decoding:try JSONSerialization.data(withJSONObject:result,options:.sortedKeys),as:UTF8.self))
 }
