// Scritte in una serie di immagini con Vision di macOS (OCR), per misurare i sottotitoli dal video finito.
// uso: testi img1.jpg img2.jpg ...  -> una riga JSON per immagine: {"f": percorso, "t": [{"s": testo, "x","y","w","h" in pixel (origine in alto a sinistra), "c": fiducia}]}
// compilare: swiftc -O strumenti/testi.swift -o strumenti/testi
import Foundation
import Vision
import AppKit

let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false  // gergo e parole urlate ("NAHHH"): la correzione le cambierebbe
req.recognitionLanguages = ["en-US"]
for percorso in CommandLine.arguments.dropFirst() {
    var out: [[String: Any]] = []
    if let img = NSImage(contentsOfFile: percorso), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) {
        let W = Double(cg.width), H = Double(cg.height)
        try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
        for r in req.results ?? [] {
            guard let c = r.topCandidates(1).first else { continue }
            let b = r.boundingBox
            out.append(["s": c.string, "x": (b.minX * W).rounded(), "y": ((1 - b.maxY) * H).rounded(), "w": (b.width * W).rounded(), "h": (b.height * H).rounded(), "c": Double(c.confidence)])
        }
    }
    let riga = try! JSONSerialization.data(withJSONObject: ["f": percorso, "t": out])
    print(String(data: riga, encoding: .utf8)!)
}
