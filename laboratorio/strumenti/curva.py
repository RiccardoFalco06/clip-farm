"""Curva di entrata/uscita di una parola: per ogni fotogramma, quanto il ritaglio somiglia allo stato finale.
alpha(t) = proiezione di (fotogramma - sfondo) su (finale - sfondo) nel ritaglio, dove lo sfondo è il fotogramma prima dell'entrata.
Stampa anche il riquadro dei pixel "accesi" (per vedere scala/spostamento).
uso: python3 curva.py video t0 durata x y w h t_finale [fps=60]"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid


def curva(path, t0, dur, x, y, w, h, tfin, fps=60):
    f = vid.frames(path, t0, dur, fps=fps, crop=(w, h, x, y)).astype(np.float32)
    h, w = f.shape[1:3]  # ffmpeg arrotonda il ritaglio ai pari
    fin = vid.frame(path, tfin, (w, h, x, y)).astype(np.float32)
    bg = f[0]
    d = fin - bg
    peso = np.abs(d).sum(axis=2) > 120  # solo i pixel che il testo cambia davvero
    out = []
    for i, fr in enumerate(f):
        a = ((fr - bg)[peso] * d[peso]).sum() / max(1.0, (d[peso] ** 2).sum())
        on = (np.abs(fr - bg).sum(axis=2) > 90) & peso
        ys, xs = np.where(on)
        box = (int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())) if len(xs) > 20 else None
        out.append((round(t0 + i / fps, 4), float(a), box))
    return out


if __name__ == "__main__":
    a = sys.argv
    for t, al, box in curva(a[1], float(a[2]), float(a[3]), *map(int, a[4:8]), float(a[8]), int(a[9]) if len(a) > 9 else 60):
        print(f"{t:.3f}  {al:5.2f}  {box}")
