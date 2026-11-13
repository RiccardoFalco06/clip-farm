"""Analisi audio senza ascolto: eventi (attacchi improvvisi) con la loro "forma" e ricerca dei suoni approvati dentro uno Short.
uso: python3 audio.py eventi file.wav            -> elenco degli attacchi con banda dominante e durata
     python3 audio.py cerca file.wav suoni_dir   -> dove compaiono i file di suoni_dir (correlazione normalizzata)
     python3 audio.py livelli file.wav           -> volume ogni 0,5 s in tre bande (basso <150 Hz, voce 300-3000, alti >5 k)"""
import subprocess
import sys

import numpy as np
from scipy import signal

SR = 22050


def carica(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def spettro(x, n=1024, hop=256):
    f, t, S = signal.stft(x, SR, nperseg=n, noverlap=n - hop, boundary=None)
    return f, t, np.abs(S)


def bande(f, S):
    b = {"basso": (20, 150), "medio": (300, 3000), "alto": (5000, 11000)}
    return {k: 20 * np.log10(S[(f >= a) & (f < z)].mean(axis=0) + 1e-6) for k, (a, z) in b.items()}


def eventi(path, soglia=2.5):
    x = carica(path)
    f, t, S = spettro(x)
    L = np.log1p(30 * S)
    flux = np.maximum(0, L[:, 1:] - L[:, :-1])
    out = []
    for nome, (a, z) in {"basso": (20, 150), "medio": (300, 3000), "alto": (5000, 11000)}.items():
        fl = flux[(f >= a) & (f < z)].mean(axis=0)
        med = signal.medfilt(fl, 87)  # ~1 s
        z_ = (fl - med) / (fl.std() + 1e-9)
        picchi, _ = signal.find_peaks(z_, height=soglia, distance=int(0.15 * SR / 256))
        out += [(float(t[p + 1]), nome, float(z_[p])) for p in picchi]
    return sorted(out)


def cerca(path, cartella, soglia=0.25):
    import glob
    x = carica(path)
    x = signal.sosfilt(signal.butter(4, 200, "hp", fs=SR, output="sos"), x)
    ris = []
    for s in sorted(glob.glob(cartella + "/*.m4a")):
        y = carica(s)
        y = signal.sosfilt(signal.butter(4, 200, "hp", fs=SR, output="sos"), y)
        y = y[: int(1.2 * SR)]  # l'attacco basta a riconoscerlo
        if len(y) < 2000 or len(y) > len(x):
            continue
        c = signal.fftconvolve(x, y[::-1], mode="valid")
        e = np.sqrt(signal.fftconvolve(x ** 2, np.ones(len(y)), mode="valid").clip(1e-9)) * np.sqrt((y ** 2).sum())
        n = np.abs(c) / (e + 1e-9)
        i = int(n.argmax())
        if n[i] > soglia:
            ris.append((float(n[i]), i / SR, s.rsplit("/", 1)[1]))
    return sorted(ris, reverse=True)


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "eventi":
        for t, nome, z in eventi(path):
            print(f"{t:6.2f}  {nome:6s} {z:4.1f}")
    elif cmd == "cerca":
        for n, t, s in cerca(path, sys.argv[3]):
            print(f"{n:.2f}  a {t:6.2f} s  {s}")
    elif cmd == "livelli":
        x = carica(path)
        f, t, S = spettro(x)
        b = bande(f, S)
        passo = int(0.5 * SR / 256)
        for i in range(0, S.shape[1] - passo, passo):
            print(f"{t[i]:5.1f}  " + "  ".join(f"{k} {b[k][i:i + passo].mean():6.1f}" for k in b))
