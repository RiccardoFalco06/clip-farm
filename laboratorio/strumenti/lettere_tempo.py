"""Segue nel tempo le lettere di una riga colorata: n. lettere, larghezza totale delle lettere (scala), distanza tra i centri
della prima e dell'ultima (spaziatura), centro della riga, riga superiore/inferiore.
uso: python3 lettere_tempo.py video t0 durata y0 y1 colore(rosso|giallo|verde|bianco|sat) [passo_fotogrammi=10]"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid

COND = {
    "rosso": lambda f: (f[..., 0] > 200) & (f[..., 1] < 90) & (f[..., 2] < 90),
    "giallo": lambda f: (f[..., 0] > 200) & (f[..., 1] > 190) & (f[..., 2] < 120),
    "verde": lambda f: (f[..., 1] > 200) & (f[..., 0] < 150) & (f[..., 2] < 120),
    "bianco": lambda f: f.min(axis=2) > 210,
    "sat": lambda f: (f.max(axis=2) > 200) & (f.max(axis=2) - f.min(axis=2) > 110),
}


def segmenti(m):
    col = m.sum(axis=0) > 1
    out, x = [], 0
    while x < len(col):
        if col[x]:
            x1 = x
            while x1 < len(col) and col[x1]:
                x1 += 1
            if x1 - x > 3:
                out.append((x, x1))
            x = x1
        else:
            x += 1
    return out


if __name__ == "__main__":
    v, t0, dur, y0, y1, colore = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
    passo = int(sys.argv[7]) if len(sys.argv) > 7 else 10
    W = vid.dims(v)[0]
    f = vid.frames(v, t0, dur, crop=(W, y1 - y0, 0, y0)).astype(np.int16)
    fps = round(len(f) / dur)
    for i in range(0, len(f), passo):
        m = COND[colore](f[i])
        s = segmenti(m)
        if len(s) < 2:
            print(f"{t0 + i / fps:.3f} n={len(s)}")
            continue
        ys = np.where(m.sum(axis=1) > 3)[0]
        c = [(a + b) / 2 for a, b in s]
        print(f"{t0 + i / fps:.3f} n={len(s):2d} somma_larghezze {sum(b - a for a, b in s):4d} span_centri {c[-1] - c[0]:6.1f} centro_riga {(s[0][0] + s[-1][1]) / 2:6.1f} y {ys.min() + y0}-{ys.max() + y0}")
