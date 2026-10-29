import AppKit
import CoreServices
import Foundation

private struct NativeInstallRegistryPlatform: InstallRegistryPlatform {
    var homeDirectory: URL { FileManager.default.homeDirectoryForCurrentUser }
    func urlsForApplications(withBundleIdentifier identifier: String) -> [URL] {
        NSWorkspace.shared.urlsForApplications(withBundleIdentifier: identifier)
    }
    func register(_ url: URL) -> OSStatus { LSRegisterURL(url as CFURL, true) }
}

@main
private struct InstallRegistryMain {
    static func main() throws {
        let result = InstallRegistryCLI.execute(arguments: Array(CommandLine.arguments.dropFirst()),
                                                platform: NativeInstallRegistryPlatform())
        try InstallRegistryCLI.emit(result.output)
        if result.exitCode != 0 { exit(result.exitCode) }
    }
}
