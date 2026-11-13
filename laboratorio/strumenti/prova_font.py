"""Rende lo stesso testo in Remotion con più varianti (font, spaziatura, scalaX, dimensione) e misura la sovrapposizione
del riempimento con l'originale. uso: python3 prova_font.py  (prende il blocco, un solo bundle per tutte le varianti)"""
import itertools
import json
import subprocess
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid
from cerca_font import bbox, iou

LAB = __file__.rsplit("/", 2)[0]
# (video, t, ritaglio (w,h,x,y), righe di testo, soglia del bianco)
CAMPIONI = [
    ("TRG58mooOps", 8.7, (500, 64, 300, 654), "JUST FOR...", 200),
    ("6lPbHx_dFSo", 9.1, (545, 62, 135, 688), "IT’S MADE OF", 205),
    ("C4iMYNKbPEg", 17.6, (830, 64, 120, 658), "WAIT YOU ACTUALLY", 225),
]


def maschera_orig(c):
    m = vid.frame(f"{LAB}/riferimenti/alta/{c[0]}.mp4", c[1], c[2]).min(axis=2) > c[4]
    x0, y0, x1, y1 = bbox(m)
    return m[y0:y1, x0:x1]


def confronto(a, b):
    """IoU migliore spostando b di pochi pixel; a e b ritagliati al proprio riquadro."""
    H, W = max(a.shape[0], b.shape[0]) + 8, max(a.shape[1], b.shape[1]) + 8
    A = np.zeros((H, W), bool)
    A[4:4 + a.shape[0], 4:4 + a.shape[1]] = a
    best = 0
    for dy in range(0, 9):
        for dx in range(0, 9):
            if dy + b.shape[0] > H or dx + b.shape[1] > W:
                continue
            B = np.zeros((H, W), bool)
            B[dy:dy + b.shape[0], dx:dx + b.shape[1]] = b
            best = max(best, iou(A, B))
    return best


if __name__ == "__main__":
    varianti = [dict(font=f, tracking=tr, scaleX=sx, size=sz)
                for f, sxs in (("Figtree", (0.92, 0.94, 0.96)), ("Reddit Sans", (0.98, 1.0, 1.02)))
                for tr, sx, sz in itertools.product((0.10, 0.115, 0.13), sxs, (70, 72, 74))]
    jobs = []
    for i, v in enumerate(varianti):
        for j, c in enumerate(CAMPIONI):
            props = {"video": "", "width": 1080, "height": 1440, "durata": 1, "riga": {"style": "outline", "cx": 540, "baseline": 700, "size": 72}, "gruppi": [], "lampi": [], "zoom": [], "suoni": [],
                     "sfondo": "#000", "glow": {**v, "trackingVel": 0, "glowAlpha": 0, "glow2Alpha": 0, "shadow": [0, 0, 0, 0]},
                     "frasi": [{"start": 0, "end": 9, "righe": [[{"text": c[3]}]]}]}
            jobs.append({"id": "ClipSpeedy", "out": f"{LAB}/tmp/pf/{i}_{j}.png", "frame": 20, "props": props})
    json.dump(jobs, open(f"{LAB}/tmp/pf.json", "w"))
    subprocess.run([f"{LAB}/strumenti/render.sh", f"{LAB}/tmp/pf.json"], check=True, stdout=subprocess.DEVNULL)
    orig = [maschera_orig(c) for c in CAMPIONI]
    ris = []
    for i, v in enumerate(varianti):
        s, dw = [], []
        for j, c in enumerate(CAMPIONI):
            m = vid.png(f"{LAB}/tmp/pf/{i}_{j}.png").min(axis=2) > 127
            x0, y0, x1, y1 = bbox(m)
            r = m[y0:y1, x0:x1]
            s.append(confronto(orig[j], r))
            dw.append((r.shape[1] - orig[j].shape[1], r.shape[0] - orig[j].shape[0]))
        ris.append((float(np.mean(s)), v, [round(x, 3) for x in s], dw))
    for s, v, ss, dw in sorted(ris, key=lambda x: -x[0])[:12]:
        print(f"{s:.3f} {v} per campione {ss} diff riquadro (larg, alt) {dw}")
