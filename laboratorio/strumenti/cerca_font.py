"""Classifica i font candidati per somiglianza con il riempimento del testo originale.
Per ogni campione (video, secondo, ritaglio, testo, corsivo?) estrae la maschera del riempimento (bianco) e la confronta con
lo stesso testo reso con ogni font: riquadri allineati, spaziatura cercata su una griglia, punteggio = IoU medio.
uso: python3 cerca_font.py [filtro_nome]"""
import glob
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid

R = "riferimenti/alta/"
CAMPIONI = [  # video, t, (w,h,x,y), testo, soglia bianco
    ("TRG58mooOps", 8.7, (500, 64, 300, 654), "JUST FOR...", 200),
    ("ocTXLR2F5O4", 20.1, (410, 62, 540, 656), "IT’S YOUR", 215),
    ("6lPbHx_dFSo", 9.1, (545, 62, 135, 688), "IT’S MADE OF", 205),
    ("C4iMYNKbPEg", 17.6, (290, 64, 236, 658), "IT YOU", 225),
]


def bbox(m):
    ys, xs = np.where(m)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def maschera(c):
    f = vid.frame(R + c[0] + ".mp4", c[1], c[2])
    m = f.min(axis=2) > c[4]
    x0, y0, x1, y1 = bbox(m)
    return m[y0:y1, x0:x1]


def resa(font, testo, tr):
    """Maschera del testo a 160 px con spaziatura tr (em), ritagliata al riquadro."""
    S = 160
    im = Image.new("L", (int(S * len(testo) * 1.4) + 200, S * 3), 0)
    d = ImageDraw.Draw(im)
    x = 50.0
    for ch in testo:
        d.text((x, S), ch, font=font, fill=255)
        x += font.getlength(ch) + tr * S
    a = np.asarray(im) > 127
    x0, y0, x1, y1 = bbox(a)
    return a[y0:y1, x0:x1]


def iou(a, b):
    return (a & b).sum() / max(1, (a | b).sum())


if __name__ == "__main__":
    masks = [maschera(c) for c in CAMPIONI]
    if len(sys.argv) > 1 and sys.argv[1] == "--mostra":
        H = max(m.shape[0] for m in masks)
        W = max(m.shape[1] for m in masks)
        out = np.zeros((H * len(masks), W), np.uint8)
        for i, m in enumerate(masks):
            out[i * H:i * H + m.shape[0], :m.shape[1]] = m * 255
        Image.fromarray(out).save("tmp/maschere.png")
        print([m.shape for m in masks])
        sys.exit()
    ris = []
    for path in sorted(glob.glob("font/*.ttf")):
        if len(sys.argv) > 1 and sys.argv[1] not in path:
            continue
        try:
            font = ImageFont.truetype(path, 160)
        except Exception as e:
            continue
        best = (0, 0, 0)
        for tr in np.arange(-0.02, 0.26, 0.01):
            tot, sxs = 0, []
            for c, m in zip(CAMPIONI, masks):
                r = resa(font, c[3], tr)
                rr = np.asarray(Image.fromarray((r * 255).astype(np.uint8)).resize((m.shape[1], m.shape[0]), Image.BILINEAR)) > 127
                tot += iou(m, rr)
                sxs.append((m.shape[1] / r.shape[1]) / (m.shape[0] / r.shape[0]))
            if tot / len(masks) > best[0]:
                best = (tot / len(masks), tr, float(np.mean(sxs)))
        ris.append((best, path))
    for (s, tr, sx), p in sorted(ris, reverse=True)[:25]:
        print(f"{s:.3f}  spaziatura {tr:+.2f} em  scalaX {sx:.3f}  {p}")
