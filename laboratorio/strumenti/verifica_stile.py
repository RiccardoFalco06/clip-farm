"""Fermi immagine di verifica dello stile speedy (un bundle, sotto blocco) e misure contro gli originali:
 1) spaziatura che si allarga: "*CLOSES THE WINDOW*" a 0,87 e 2,87 s dall'inizio della frase, distanza tra i centri della prima e
    dell'ultima lettera contro l'originale (NpM_oB_aH0s a 12,87 e 14,87 s: 835,0 e 884,0 px)
 2) fogli di confronto a occhio: tmp/vs_testi.png (righe di testo), tmp/vs_grafiche.png (freccia, cerchio, finale)
uso: python3 verifica_stile.py"""
import json
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import vid
from lettere_tempo import COND, segmenti
from prova_font import LAB

P = {"verde": {"fill": "#25fb06", "glow": "#00ff00"}, "lime": {"fill": "#98fb05", "glow": "#7dff00"}, "giallo": {"fill": "#f2fd06", "glow": "#ffe600"}, "rosso": {"fill": "#f70105", "glow": "#ff0000"},
     "magenta": {"fill": "#f909f4", "glow": "#ff00ff"}, "ciano": {"fill": "#66fcf9", "glow": "#00fff0"}, "bbr": {"glow": "#ff2a10", "edge": "#ff5a4a", "edgeW": 1.6}}
BASE = {"video": "", "width": 1080, "height": 1440, "durata": 6, "riga": {"style": "outline", "cx": 540, "baseline": 700, "size": 72}, "gruppi": [], "lampi": [], "zoom": [], "suoni": [], "sfondo": "#16161c"}
w = lambda t, c=None, **k: {"text": t, **(P[c] if c else {}), **k}
TESTI = [  # (frasi, fotogramma)
    ([{"start": 0, "end": 9, "righe": [[w("BEST", "lime"), w("FOOTBALL", "lime"), w("PLAYER", "lime")]]}], 20),
    ([{"start": 0, "end": 9, "righe": [[w("CRISTIANO", "verde"), w("RONALDO!", "rosso")]]}], 30),
    ([{"start": 0, "end": 9, "righe": [[w("JUST"), w("FOR...")], [w("YOU!", "verde")]]}], 45),
    ([{"start": 0, "end": 9, "corsivo": True, "righe": [[w("*TELLS", "giallo"), w("HER", "giallo"), w("TO", "giallo"), w("ROLL", "giallo")], [w("THE"), w("WINDOW", "bbr"), w("DOWN*", "bbr", start=1.6)]]}], 50),
    ([{"start": 0, "end": 9, "righe": [[w("IT’S"), w("MADE"), w("OF"), w("CAKE!", "magenta")]]}], 30),
]
ORIG = [("TRG58mooOps", 1.8, 580), ("TRG58mooOps", 4.3, 580), ("TRG58mooOps", 8.7, 580), ("NpM_oB_aH0s", 9.1, 580), ("6lPbHx_dFSo", 9.1, 580)]
CLOSES = {"start": 0, "end": 9, "corsivo": True, "righe": [[w("*CLOSES", "rosso"), w("THE", "rosso"), w("WINDOW*", "rosso")]]}

jobs = [{"id": "ClipSpeedy", "out": f"{LAB}/tmp/vs/t{i}.png", "frame": fr, "props": {**BASE, "frasi": fs}} for i, (fs, fr) in enumerate(TESTI)]
jobs += [{"id": "ClipSpeedy", "out": f"{LAB}/tmp/vs/c{k}.png", "frame": round(t * 30), "props": {**BASE, "sfondo": "#000", "frasi": [CLOSES]}} for k, t in enumerate((0.87, 2.87))]
G = {**BASE, "sfondo": "#3a3a44", "firma": "@iamclipfarmer67"}
jobs += [
    {"id": "ClipSpeedy", "out": f"{LAB}/tmp/vs/g0.png", "frame": 30, "props": {**G, "grafiche": [{"tipo": "freccia", "t": 0, "durata": 5, "x": 480, "y": 300, "colore": "#ff2e9a"}], "frasi": [{"start": 0, "end": 9, "corsivo": True, "cx": 540, "baseline": 640, "righe": [[w("*MR", "ciano"), w("BEAST*", "ciano")]]}]}},
    {"id": "ClipSpeedy", "out": f"{LAB}/tmp/vs/g1.png", "frame": 30, "props": {**G, "grafiche": [{"tipo": "cerchio", "t": 0, "durata": 5, "x": 190, "y": 1130, "r": 150}], "frasi": []}},
    {"id": "ClipSpeedy", "out": f"{LAB}/tmp/vs/g2.png", "frame": 40, "props": {**G, "effetti": [{"tipo": "scuro", "t": 0, "durata": 9, "forza": 0.5}], "grafiche": [{"tipo": "particelle", "t": 0, "durata": 9}, {"tipo": "emoji", "t": 0, "durata": 9, "x": 540, "y": 1090, "emoji": "😂", "size": 120}],
                                                                       "frasi": [{"start": 0, "end": 9, "corsivo": True, "baseline": 1240, "righe": [[w("*PUSHING", "verde"), w("30", "verde"), w("BTW*", "verde")]]}]}},
]
json.dump(jobs, open(f"{LAB}/tmp/vs.json", "w"))
subprocess.run([f"{LAB}/strumenti/render.sh", f"{LAB}/tmp/vs.json"], check=True, stdout=subprocess.DEVNULL)

print("1) spaziatura nel tempo (distanza tra i centri di prima e ultima lettera, px): originale 835.0 -> 884.0")
sp = []
for k in range(2):
    m = COND["rosso"](vid.png(f"{LAB}/tmp/vs/c{k}.png").astype(int))
    s = segmenti(m)
    c = [(a + b) / 2 for a, b in s]
    sp.append(c[-1] - c[0])
    print(f"   resa a {(0.87, 2.87)[k]} s: {len(s)} lettere, distanza {c[-1] - c[0]:.1f}, somma larghezze lettere {sum(b - a for a, b in s)} (originale 678-680)")
print(f"   crescita resa {sp[1] - sp[0]:.1f} px in 2 s contro 49.0 dell'originale")

righe = []
for i, (v, t, y) in enumerate(ORIG):
    o = vid.frame(f"{LAB}/riferimenti/alta/{v}.mp4", t)[y:y + 220]
    r = vid.png(f"{LAB}/tmp/vs/t{i}.png")[580:800]
    righe.append(np.concatenate([o, r], axis=1))
Image.fromarray(np.concatenate(righe)).resize((1440, 733)).save(f"{LAB}/tmp/vs_testi.png")
g = [np.asarray(Image.open(f"{LAB}/tmp/vs/g{k}.png").convert("RGB").resize((540, 720))) for k in range(3)]
Image.fromarray(np.concatenate(g, axis=1)).save(f"{LAB}/tmp/vs_grafiche.png")
