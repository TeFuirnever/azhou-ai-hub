import Foundation
@main struct TransportMock {
 @MainActor static func main() async throws {
  let mode=CommandLine.arguments[1],port=Int(CommandLine.arguments[2])!
  let endpoint=URL(string:"http://127.0.0.1:\(port)")!
  let process=HostProcessGeneration(pid:123,launchTime:50,executableURL:URL(fileURLWithPath:"/fixture/ZCode"))
  var guards=0
  let client=try ZCodeBoundCDP(process:process,endpoint:endpoint,installedPage:"/fixture/index.html",now:{ProcessInfo.processInfo.systemUptime},guardLive:{guards+=1})
  defer{client.close()}
  let start=ProcessInfo.processInfo.systemUptime
  var outcome="",sent=false
  if mode=="send-timeout" || mode=="receive-timeout" {
   do {_ = try await client.attach(deadline:start+0.20);fatalError("blackhole unexpectedly succeeded")}
   catch {outcome="bounded-error"}
   precondition(ProcessInfo.processInfo.systemUptime-start<1.2,"deadline did not unblock actual operation")
  } else if mode=="send-cancel" || mode=="receive-cancel" {
   let task=Task { ()->Bool in
    do {_ = try await client.attach(deadline:start+5);return false}catch{return true}
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
