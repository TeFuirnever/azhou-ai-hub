import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers
import Vision

private let avatarSize = 512
private let artworkWidth = 1536
private let artworkHeight = 1024
private let maximumSourcePixels = 48_000_000
private let maximumPaths = 1_200
private let maximumPoints = 300_000

private func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

private func image(at path: String) -> CGImage {
    let url = URL(fileURLWithPath: path)
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          CGImageSourceGetType(source) as String? == UTType.png.identifier,
          let image = CGImageSourceCreateImageAtIndex(source, 0, [kCGImageSourceShouldCache: false] as CFDictionary),
          image.width > 0, image.height > 0,
          image.width <= maximumSourcePixels / image.height else {
        fail("Startup defaults require a readable PNG within the 48 megapixel source limit: \(path)")
    }
    return image
}

private func cropCenterCover(_ input: CGImage, width: Int, height: Int) -> CGImage {
    let inputWidth = input.width
    let inputHeight = input.height
    let targetAspect = Double(width) / Double(height)
    let inputAspect = Double(inputWidth) / Double(inputHeight)
    let cropWidth: Int
    let cropHeight: Int
    if inputAspect > targetAspect {
        cropHeight = inputHeight
        cropWidth = max(1, min(inputWidth, Int((Double(inputHeight) * targetAspect).rounded())))
    } else {
        cropWidth = inputWidth
        cropHeight = max(1, min(inputHeight, Int((Double(inputWidth) / targetAspect).rounded())))
    }
    let cropX = (inputWidth - cropWidth) / 2
    let cropY = (inputHeight - cropHeight) / 2
    guard let cropped = input.cropping(to: CGRect(x: cropX, y: cropY, width: cropWidth, height: cropHeight)) else {
        fail("Could not crop startup default image.")
    }
    guard let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
          let context = CGContext(data: nil, width: width, height: height,
                                  bitsPerComponent: 8, bytesPerRow: width * 4,
                                  space: colorSpace,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
                                    | CGBitmapInfo.byteOrder32Big.rawValue) else {
        fail("Could not create the startup default image canvas.")
    }
    context.setFillColor(red: 16.0 / 255.0, green: 17.0 / 255.0, blue: 20.0 / 255.0, alpha: 1)
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.interpolationQuality = .high
    context.draw(cropped, in: CGRect(x: 0, y: 0, width: width, height: height))
    guard let output = context.makeImage() else { fail("Could not finish the startup default image.") }
    return output
}

private func writePNG(_ image: CGImage, to path: String) {
    let url = URL(fileURLWithPath: path)
    try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(),
                                             withIntermediateDirectories: true)
    guard let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        fail("Could not create generated PNG: \(path)")
    }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else { fail("Could not encode generated PNG: \(path)") }
}

private func contours(for image: CGImage) -> [[[Double]]] {
    let request = VNDetectContoursRequest()
    request.revision = VNDetectContourRequestRevision1
    request.maximumImageDimension = 768
    request.detectsDarkOnLight = false
    request.contrastAdjustment = 1.4
    do {
        try VNImageRequestHandler(cgImage: image, orientation: .up, options: [:]).perform([request])
    } catch {
        fail("Vision could not trace the cropped startup artwork: \(error.localizedDescription)")
    }
    guard let observation = request.results?.first else { fail("Vision returned no contour observation.") }
    var paths: [[SIMD2<Float>]] = []
    paths.reserveCapacity(min(observation.contourCount, maximumPaths * 2))
    for index in 0..<observation.contourCount {
        guard let contour = try? observation.contour(at: index) else { continue }
        let points = contour.normalizedPoints
        if points.count >= 2 { paths.append(points) }
    }
    paths.sort { $0.count > $1.count }
    var result: [[[Double]]] = []
    var totalPoints = 0
    for source in paths.prefix(maximumPaths) {
        let remaining = maximumPoints - totalPoints
        if remaining < 2 { break }
        let stride = max(1, Int(ceil(Double(source.count) / Double(remaining))))
        var path: [[Double]] = []
        path.reserveCapacity(min(source.count, remaining))
        for index in Swift.stride(from: 0, to: source.count, by: stride) {
            let point = source[index]
            guard point.x.isFinite, point.y.isFinite else { continue }
            let x = min(Double(artworkWidth), max(0, Double(point.x) * Double(artworkWidth)))
            let y = min(Double(artworkHeight), max(0, (1 - Double(point.y)) * Double(artworkHeight)))
            path.append([((x * 1000).rounded() / 1000), ((y * 1000).rounded() / 1000)])
        }
        if path.count < 2 { continue }
        if path.count > remaining { path = Array(path.prefix(remaining)) }
        totalPoints += path.count
        result.append(path)
    }
    guard !result.isEmpty else { fail("The cropped default artwork produced no usable contours.") }
    return result
}

guard CommandLine.arguments.count == 6 else {
    fail("Usage: build-startup-assets <working.png> <wallpaper.png> <avatar.png> <artwork.png> <contours.json>")
}
let working = image(at: CommandLine.arguments[1])
let wallpaper = image(at: CommandLine.arguments[2])
let avatar = cropCenterCover(working, width: avatarSize, height: avatarSize)
let artwork = cropCenterCover(wallpaper, width: artworkWidth, height: artworkHeight)
writePNG(avatar, to: CommandLine.arguments[3])
writePNG(artwork, to: CommandLine.arguments[4])
let paths = contours(for: artwork)
do {
    let data = try JSONSerialization.data(withJSONObject: paths, options: [.fragmentsAllowed])
    try data.write(to: URL(fileURLWithPath: CommandLine.arguments[5]), options: .atomic)
} catch {
    fail("Could not serialize startup contours: \(error.localizedDescription)")
}
