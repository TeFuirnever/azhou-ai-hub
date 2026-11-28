// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AzhouCursorPendant",
    platforms: [.macOS(.v14)],
    targets: [
        .target(name: "CursorPendantMotion"),
        .executableTarget(name: "AzhouCursorPendant", dependencies: ["CursorPendantMotion"]),
        .testTarget(name: "CursorPendantMotionTests", dependencies: ["CursorPendantMotion"]),
    ]
)
