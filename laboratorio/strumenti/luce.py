"""Misura la "luce che lampeggia" sopra un video: scatti di luminosità di tutto il quadro da un fotogramma all'altro.
Per ogni fotogramma: luma media di 4x4 blocchi (video rimpicciolito 48x64, in flusso: niente fotogrammi tenuti in RAM).
Scarto di un fotogramma = luma - media dei due vicini (seconda differenza). Se tutti i blocchi vanno nello stesso verso
lo scatto è di tutto il quadro (velo chiaro/scuro), non un movimento del soggetto.
uso: python3 -I luce.py video.mp4 [video2 ...]  -> una riga per video
"""
import subprocess
import sys

import numpy as np

W, H = 48, 64


def blocchi(video):
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", video, "-vf", f"fps=30,scale={W}:{H},format=gray", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    out = []
    while (b := p.stdout.read(W * H)) and len(b) == W * H:
        f = np.frombuffer(b, np.uint8).reshape(H, W).astype(float)
        out.append(f.reshape(4, H // 4, 4, W // 4).mean(axis=(1, 3)).ravel())
    p.wait()
    return np.array(out)


def misura(video, soglia=1.5):
    b = blocchi(video)
    d = b[1:-1] - (b[:-2] + b[2:]) / 2  # scarto di ogni blocco rispetto ai vicini nel tempo
    concordi = (np.sign(d) == np.sign(np.median(d, axis=1))[:, None]).mean(axis=1)
    forza = np.median(d, axis=1)
    scatti = (concordi >= 0.875) & (np.abs(forza) >= soglia)  # almeno 14 blocchi su 16 nello stesso verso
    s = np.flatnonzero(scatti)
    intervalli = np.diff(s) / 30 if len(s) > 1 else np.array([])
    return {"fotogrammi": len(b), "scatti": int(scatti.sum()), "al_secondo": round(scatti.sum() / (len(b) / 30), 2),
            "chiari": int((forza[scatti] > 0).sum()), "scuri": int((forza[scatti] < 0).sum()),
            "forza_mediana": round(float(np.median(np.abs(forza[scatti]))), 1) if len(s) else 0,
            "intervallo_mediano_s": round(float(np.median(intervalli)), 2) if len(intervalli) else None}


if __name__ == "__main__":
    for v in sys.argv[1:]:
        print(v.rsplit("/", 1)[-1], misura(v))
