"""Secondo giro di misura dello stile glow in Remotion (un solo bundle, sotto blocco):
 a) dimensione e scalaX del font con confronto lettera per lettera (la spaziatura cambia nel tempo, quindi non conta);
 b) alone: profilo del colore in funzione della distanza dal riempimento, originale contro resa, su fondo scuro.
uso: python3 prova_font2.py"""
import itertools
import json
import subprocess
import sys

import numpy as np
from scipy import ndimage

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid
from cerca_font import bbox
from cerca_font2 import lettere, confronta
from prova_font import CAMPIONI, maschera_orig, LAB

BASE = {"video": "", "width": 1080, "height": 1440, "durata": 1, "riga": {"style": "outline", "cx": 540, "baseline": 700, "size": 72}, "gruppi": [], "lampi": [], "zoom": [], "suoni": []}
VERDE = {"fill": "#25fb06", "glow": "#00ff00"}
# originale per l'alone: TRG 4.5 s, "CRISTIANO" verde su fondo scuro
ALONE = ("TRG58mooOps", 4.5, (470, 170, 60, 610))


def profilo(img, fill):
    """Media del verde a distanza 1..40 px dal riempimento (solo pixel fuori dal riempimento)."""
    d = ndimage.distance_transform_edt(~fill)
    g = img[..., 1].astype(np.float32)
    return np.array([g[(d > r - 0.5) & (d <= r + 0.5)].mean() for r in range(1, 41)])


if __name__ == "__main__":
    A = [dict(size=sz, scaleX=sx) for sz, sx in itertools.product((67, 68, 69, 70), (0.90, 0.92, 0.94))]
    B = [dict(glowBlur=gb, glowAlpha=ga, glow2Blur=g2b, glow2Alpha=g2a) for gb, ga, g2b, g2a in itertools.product((4, 7), (0.5, 0.9), (16, 26), (0.35, 0.7))]
    jobs = []
    for i, v in enumerate(A):
        for j, c in enumerate(CAMPIONI):
            jobs.append({"id": "ClipSpeedy", "out": f"{LAB}/tmp/pf/a{i}_{j}.png", "frame": 20, "props": {**BASE, "sfondo": "#000", "glow": {**v, "tracking": 0.115, "trackingVel": 0, "glowAlpha": 0, "glow2Alpha": 0, "shadow": [0, 0, 0, 0]}, "frasi": [{"start": 0, "end": 9, "righe": [[{"text": c[3]}]]}]}})
    for i, v in enumerate(B):
        jobs.append({"id": "ClipSpeedy", "out": f"{LAB}/tmp/pf/b{i}.png", "frame": 20, "props": {**BASE, "sfondo": "#12121a", "glow": {**v, "size": 70, "scaleX": 0.92, "tracking": 0.1, "trackingVel": 0, "shadow": [0, 0, 0, 0]}, "frasi": [{"start": 0, "end": 9, "righe": [[{"text": "CRISTIANO", **VERDE}]]}]}})
    json.dump(jobs, open(f"{LAB}/tmp/pf2.json", "w"))
    subprocess.run([f"{LAB}/strumenti/render.sh", f"{LAB}/tmp/pf2.json"], check=True, stdout=subprocess.DEVNULL)

    orig = [lettere(maschera_orig(c)) for c in CAMPIONI]
    ris = []
    for i, v in enumerate(A):
        tot = []
        for j in range(len(CAMPIONI)):
            m = vid.png(f"{LAB}/tmp/pf/a{i}_{j}.png").min(axis=2) > 127
            x0, y0, x1, y1 = bbox(m)
            L = lettere(m[y0:y1, x0:x1])
            if len(L) == len(orig[j]):
                tot += [confronta(a[2], b[2]) for a, b in zip(orig[j], L)]
        ris.append((float(np.mean(tot)), len(tot), v))
    print("a) font, IoU medio per lettera:")
    for s, n, v in sorted(ris, key=lambda x: -x[0]):
        print(f"   {s:.3f} su {n} lettere  {v}")

    f = vid.frame(f"{LAB}/riferimenti/alta/{ALONE[0]}.mp4", ALONE[1], ALONE[2])
    fill = (f[..., 1] > 200) & (f[..., 0] < 150) & (f[..., 2] < 120)
    po = profilo(f, fill)
    fondo = po[-5:].mean()
    print("b) alone. originale: verde medio a 2,4,8,12,16,24,32 px dal riempimento:", [int(po[r - 1]) for r in (2, 4, 8, 12, 16, 24, 32)])
    rb = []
    for i, v in enumerate(B):
        g = vid.png(f"{LAB}/tmp/pf/b{i}.png")
        fl = (g[..., 1] > 200) & (g[..., 0] < 150) & (g[..., 2] < 120)
        pr = profilo(g, fl)
        # scarto medio del profilo (tolto il fondo, che nell'originale è il video e nella resa un colore fisso)
        rb.append((float(np.abs((po - fondo) - (pr - pr[-5:].mean())).mean()), v, [int(pr[r - 1]) for r in (2, 4, 8, 12, 16, 24, 32)]))
    for e, v, p in sorted(rb, key=lambda x: x[0])[:6]:
        print(f"   scarto medio {e:.1f}/255  {v}  profilo {p}")
