// Facce in un'immagine con Vision di macOS (niente pacchetti da installare).
// uso: volti immagine.png  -> una riga JSON: [{"x":..,"y":..,"w":..,"h":..,"c":..}] in pixel, origine in alto a sinistra
// compilare una volta: swiftc -O strumenti/volti.swift -o strumenti/volti
import Foundation
import Vision
import AppKit

let percorso = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: percorso), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("[]"); exit(0)
}
let W = Double(cg.width), H = Double(cg.height)
let req = VNDetectFaceRectanglesRequest()
try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
var out: [[String: Double]] = []
for f in req.results ?? [] {
    let b = f.boundingBox  // normalizzato, origine in basso a sinistra
    out.append(["x": (b.minX * W).rounded(), "y": ((1 - b.maxY) * H).rounded(), "w": (b.width * W).rounded(), "h": (b.height * H).rounded(), "c": Double(f.confidence)])
}
let dati = try! JSONSerialization.data(withJSONObject: out)
print(String(data: dati, encoding: .utf8)!)
