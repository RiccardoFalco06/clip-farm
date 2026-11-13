"""Quale file di musica/ è il brano sentito in uno Short: spettro a 32 bande (10 fotogrammi al secondo) di un tratto
di 10 s dello Short fatto scorrere su tutto il file; punteggio = somiglianza coseno media nel punto migliore.
Un file alla volta in memoria (audio mono 11025 Hz, pochi MB).
uso: python confronta_musica.py "id:secondo,id:secondo" file1.m4a file2.m4a ...  -> tabella id x file"""
import subprocess
import sys

import numpy as np

SR, HOP, NFFT = 11025, 1102, 4096


def audio(f, da=0, dur=None):
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(da)] + (["-t", str(dur)] if dur else []) + ["-i", f, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32)


def bande(x):
    fr = np.lib.stride_tricks.sliding_window_view(x, NFFT)[::HOP] * np.hanning(NFFT)
    S = np.abs(np.fft.rfft(fr, axis=1))
    lim = np.geomspace(100, 4000, 33) * NFFT / SR
    B = np.stack([S[:, int(a):max(int(a) + 1, int(b))].sum(1) for a, b in zip(lim, lim[1:])], 1)
    B = np.log1p(B)
    B -= B.mean(1, keepdims=True)
    return B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-9)


def punteggio(seg, mus):
    n = len(seg)
    if len(mus) < n:
        return 0.0
    win = np.lib.stride_tricks.sliding_window_view(mus, (n, mus.shape[1]))[:, 0]
    return float(np.einsum("pij,ij->p", win, seg).max() / n)


if __name__ == "__main__":
    tratti = [x.split(":") for x in sys.argv[1].split(",")]
    segs = {f"{i}@{t}": bande(audio(f"riferimenti/audio/{i}.wav", float(t), 10)) for i, t in tratti}
    print("tratto\t" + "\t".join(f.split("/")[-1][:22] for f in sys.argv[2:]))
    righe = {k: [] for k in segs}
    for f in sys.argv[2:]:
        m = bande(audio(f))
        for k, s in segs.items():
            righe[k].append(punteggio(s, m))
        del m
    for k, v in righe.items():
        print(k + "\t" + "\t".join(f"{x:.2f}" for x in v))
    # autocontrollo: un tratto del file confrontato con il file stesso dà 1
    x = audio(sys.argv[2], 5, 10)
    assert punteggio(bande(x), bande(audio(sys.argv[2]))) > 0.95
