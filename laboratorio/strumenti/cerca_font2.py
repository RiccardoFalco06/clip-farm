"""Classifica i font lettera per lettera (più severo e più giusto di cerca_font.py: la spaziatura non conta).
Ogni lettera alta della maschera originale è confrontata con la stessa lettera del font, scalata con un unico fattore
(altezza delle maiuscole) e un unico allargamento orizzontale scalaX cercato su griglia. Punteggio = IoU medio delle lettere.
uso: python3 cerca_font2.py [filtro]"""
import glob
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cerca_font import CAMPIONI, maschera, bbox, iou


def lettere(m):
    """Componenti per colonne vuote: [(x0, x1, sottomaschera ritagliata)], solo quelle alte quasi quanto la riga."""
    col = m.any(axis=0)
    out, x = [], 0
    while x < len(col):
        if col[x]:
            x1 = x
            while x1 < len(col) and col[x1]:
                x1 += 1
            sub = m[:, x:x1]
            ys = np.where(sub.any(axis=1))[0]
            if ys.max() - ys.min() + 1 > 0.8 * m.shape[0] or (ys.max() - ys.min() + 1 > 0.7 * m.shape[0] and x1 - x > 8):
                out.append((x, x1, sub[ys.min():ys.max() + 1]))
            x = x1
        else:
            x += 1
    return out


def glifo(font, ch):
    im = Image.new("L", (500, 500), 0)
    ImageDraw.Draw(im).text((120, 120), ch, font=font, fill=255)
    a = np.asarray(im) > 127
    x0, y0, x1, y1 = bbox(a)
    return a[y0:y1, x0:x1]


def confronta(a, b):
    """IoU di due maschere allineate al centro del riquadro."""
    H, W = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
    A, B = np.zeros((H, W), bool), np.zeros((H, W), bool)
    for src, dst in ((a, A), (b, B)):
        y, x = (H - src.shape[0]) // 2, (W - src.shape[1]) // 2
        dst[y:y + src.shape[0], x:x + src.shape[1]] = src
    return iou(A, B)


def punteggio(font, campioni_lettere, sxs=np.arange(0.84, 1.13, 0.01)):
    hH = glifo(font, "H").shape[0]
    best = (0, 1, 0)
    cache = {}
    for sx in sxs:
        tot, n, werr = 0, 0, 0
        for testo, comps, Hm in campioni_lettere:
            k = Hm / hH
            for ch, (_, _, sub) in zip(testo, comps):
                if ch not in cache:
                    cache[ch] = glifo(font, ch)
                g = cache[ch]
                w, h = max(1, round(g.shape[1] * k * sx)), max(1, round(g.shape[0] * k))
                r = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)) > 127
                tot += confronta(sub, r)
                werr += abs(w - sub.shape[1]) / sub.shape[1]
                n += 1
        if tot / n > best[0]:
            best = (tot / n, float(sx), werr / n)
    return best


def prepara():
    out = []
    for c in CAMPIONI:
        m = maschera(c)
        comps = lettere(m)
        testo = [ch for ch in c[3] if ch.isalnum()]
        assert len(testo) == len(comps), (c[3], len(comps))
        Hm = float(np.median([s.shape[0] for ch, (_, _, s) in zip(testo, comps) if ch in "EFHIKLMNTUVWXYZ"]))
        out.append((testo, comps, Hm))
    return out


if __name__ == "__main__":
    cl = prepara()
    print("altezze maiuscole (px):", [c[2] for c in cl])
    ris = []
    for path in sorted(glob.glob("font/*.ttf")):
        if len(sys.argv) > 1 and sys.argv[1] not in path:
            continue
        try:
            ris.append((punteggio(ImageFont.truetype(path, 200), cl), path))
        except Exception as e:
            print("salto", path, e)
    for (s, sx, we), p in sorted(ris, reverse=True)[:30]:
        print(f"{s:.3f}  scalaX {sx:.2f}  errore larghezze {we * 100:.1f}%  {p}")
