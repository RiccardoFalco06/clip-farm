"""Trova le righe orizzontali fisse (giunzioni tra riquadri) in un video: salto di colore tra righe vicine, mediato su molti fotogrammi.
uso: python3 giunzione.py video.mp4 [fps=1]"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid

# in flusso: si tiene solo il salto riga->riga di ogni fotogramma (un vettore lungo quanto l'altezza)
d = np.array([np.abs(np.diff(f.astype(np.float32), axis=0)).mean(axis=(1, 2)) for f in vid.flusso(sys.argv[1], fps=float(sys.argv[2]) if len(sys.argv) > 2 else 1)])
med = np.median(d, axis=0)  # una giunzione c'è in (quasi) tutti i fotogrammi
h = d.shape[1] + 1
top = np.argsort(med)[::-1][:8]
print("altezza", h, "fotogrammi", len(d))
for y in sorted(top):
    print(f"riga {y + 1:5d}  ({(y + 1) / h:.4f})  salto mediano {med[y]:.1f}")
