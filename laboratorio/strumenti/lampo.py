"""Curva di un lampo colorato: per ogni fotogramma media RGB, e stima di quanto il fotogramma è "tinto".
Modello provato: uscita = sfondo*(1-a) + colore*a  (dissolvenza normale) contro  uscita = sfondo "schermato"/moltiplicato.
uso: python3 lampo.py video t0 durata [fps=60]"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid

v, t0, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
fps = int(sys.argv[4]) if len(sys.argv) > 4 else 60
f = vid.frames(v, t0, dur, fps=fps).astype(np.float32)
for i, fr in enumerate(f):
    m = fr.mean(axis=(0, 1))
    p5, p95 = np.percentile(fr.reshape(-1, 3), [5, 95], axis=0)
    sat = (fr.max(axis=2) - fr.min(axis=2)).mean()
    print(f"{t0 + i / fps:.3f} media {m[0]:5.1f} {m[1]:5.1f} {m[2]:5.1f}  p5 {p5[0]:3.0f} {p5[1]:3.0f} {p5[2]:3.0f}  p95 {p95[0]:3.0f} {p95[1]:3.0f} {p95[2]:3.0f}  sat {sat:5.1f}")
