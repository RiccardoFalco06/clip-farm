"""Classifica i font per una o più PAROLE intere (stili a una parola alla volta: fumetto, outline).
Maschera del riempimento dall'originale, stessa parola resa con ogni font, riquadri allineati, IoU. La scalaX risultante dice
quanto il font andrebbe stretto o allargato per avere le stesse proporzioni.
uso: python3 cerca_font_parola.py campioni.json [filtro]   campioni: [[video, t, [w,h,x,y], "TESTO", "bianco"|"ciano"|"verde"|"giallo"], ...]"""
import glob
import json
import sys

import numpy as np
from PIL import Image, ImageFont

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid
from cerca_font import bbox, iou, resa

COND = {"bianco": lambda f: f.min(axis=2) > 232, "ciano": lambda f: (f[..., 2] > 190) & (f[..., 1] > 160) & (f[..., 0] < 110),
        "verde": lambda f: (f[..., 1] > 190) & (f[..., 0] < 110) & (f[..., 2] < 110), "giallo": lambda f: (f[..., 0] > 200) & (f[..., 1] > 190) & (f[..., 2] < 110)}

camp = json.load(open(sys.argv[1]))
masks = []
for v, t, crop, testo, col in camp:
    m = COND[col](vid.frame(f"riferimenti/alta/{v}.mp4", t, tuple(crop)).astype(int))
    x0, y0, x1, y1 = bbox(m)
    masks.append(m[y0:y1, x0:x1])
    print(testo, "riquadro", x1 - x0, "x", y1 - y0)
Image.fromarray((np.concatenate([np.pad(m, ((0, 0), (0, max(x.shape[1] for x in masks) - m.shape[1]))) for m in masks]) * 255).astype(np.uint8)).save("tmp/maschere_parola.png")
ris = []
for path in sorted(glob.glob("font/*.ttf")):
    if len(sys.argv) > 2 and sys.argv[2] not in path:
        continue
    try:
        font = ImageFont.truetype(path, 160)
        best = (0, 0, 0)
        for tr in (-0.03, -0.015, 0, 0.015, 0.03, 0.05):
            tot, sxs = 0, []
            for (v, t, crop, testo, col), m in zip(camp, masks):
                r = resa(font, testo, tr)
                rr = np.asarray(Image.fromarray((r * 255).astype(np.uint8)).resize((m.shape[1], m.shape[0]), Image.BILINEAR)) > 127
                tot += iou(m, rr)
                sxs.append((m.shape[1] / r.shape[1]) / (m.shape[0] / r.shape[0]))
            if tot / len(masks) > best[0]:
                best = (tot / len(masks), tr, float(np.mean(sxs)))
        ris.append((best, path))
    except Exception:
        pass
for (s, tr, sx), p in sorted(ris, reverse=True)[:10]:
    print(f"{s:.3f}  spaziatura {tr:+.3f} em  scalaX {sx:.3f}  {p}")
