"""Confronta il modello del lampo (fusione scolora, picco immediato, calo a coseno) con i fotogrammi veri.
Per ogni lampo: prende il fotogramma subito prima come sfondo, applica il modello fotogramma per fotogramma e misura
lo scarto medio per canale (0-255) tra media RGB prevista e vera, e lo scarto medio pixel per pixel a 96 px.
uso: python3 verifica_lampo.py video t_lampo colore(#rrggbb) [durata=0.5] [forza=0.8]"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid


def verifica(path, t0, colore, D=0.5, forza=0.8, fps=60):
    C = np.array([int(colore[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    fr = [f.astype(np.float32) / 255 for f in vid.flusso(path, t0 - 2 / fps, D + 4 / fps, fps=fps, larg=96)]
    # il primo fotogramma tinto è quello in cui la saturazione salta
    sat = [float((f.max(axis=2) - f.min(axis=2)).mean()) for f in fr]
    k0 = int(np.argmax(np.diff(sat[:6]))) + 1
    bg = fr[k0 - 1]
    em, ep = [], []
    for k in range(k0, len(fr)):
        x = (k - k0) / fps / D
        a = forza * (1 + np.cos(np.pi * min(1, x))) / 2
        prev = 1 - (1 - bg) * (1 - a * C)
        em.append(np.abs(prev.mean(axis=(0, 1)) - fr[k].mean(axis=(0, 1))).mean() * 255)
        ep.append(np.abs(prev - fr[k]).mean() * 255)
    return float(np.mean(em)), float(np.mean(ep)), float(np.max(em))


if __name__ == "__main__":
    a = sys.argv
    em, ep, mx = verifica(a[1], float(a[2]), a[3], float(a[4]) if len(a) > 4 else 0.5, float(a[5]) if len(a) > 5 else 0.8)
    print(f"scarto medio delle medie RGB {em:.1f}/255 (massimo {mx:.1f}), scarto medio pixel per pixel {ep:.1f}/255")
