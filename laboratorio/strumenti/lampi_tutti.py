"""Trova i lampi colorati di UNO Short (salto improvviso di saturazione o luminosità che alza anche i neri) e ne misura
colore di picco (dai pixel scuri: con la fusione "scolora" un nero diventa il colore del lampo) e durata.
In flusso a 96 px di larghezza: in memoria restano solo tre numeri per fotogramma.
uso: python3 lampi_tutti.py video.mp4   -> una riga JSON su stdout (da accodare a riferimenti/lampi.jsonl)"""
import json
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid

path = sys.argv[1]
sat, lum, p5 = [], [], []
for f in vid.flusso(path, fps=30, larg=96):
    f = f.astype(np.float32)
    sat.append(float((f.max(axis=2) - f.min(axis=2)).mean()))
    lum.append(float(f.mean()))
    p5.append(np.percentile(f.reshape(-1, 3), 5, axis=0))
sat, lum, p5 = np.array(sat), np.array(lum), np.array(p5)
lampi, i = [], 2
while i < len(sat) - 3:
    ds, dl = sat[i] - sat[i - 1], lum[i] - lum[i - 1]
    scuri = p5[i] - p5[i - 1]
    if (ds > 30 and scuri.max() > 40) or (dl > 50 and scuri.min() > 60):
        serie = sat if ds > 30 else lum
        base, picco = serie[i - 1], serie[i:i + 3].max()
        j = i
        while j < len(sat) - 1 and serie[j] - base > 0.1 * (picco - base):
            j += 1
        c = p5[i + int(np.argmax(serie[i:i + 3]))]
        lampi.append({"t": round(i / 30, 2), "durata": round((j - i) / 30, 2), "colore_neri": [int(x) for x in c], "tipo": "bianco" if c.min() > 0.75 * c.max() else "colore"})
        i = j + 1
    else:
        i += 1
print(json.dumps({"id": path.rsplit("/", 1)[1][:-4], "lampi": lampi}))
