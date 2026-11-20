"""Quanto sbaglia misura.py: lo confronta con la verità di una nostra clip (scheda, props, pezzi montati).
uso: python -I ultra/verifica_misura.py lavoro/<id> CARTELLA_MISURE"""
import json, re, subprocess, sys
from pathlib import Path

d, m = Path(sys.argv[1]), json.loads((Path(sys.argv[2]) / "misure.json").read_text())
p, tg = json.loads((d / "props.json").read_text()), json.loads((d / "taglio.json").read_text())["taglio"]
dur = lambda f: float(subprocess.run(["ffprobe", "-v", "0", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout)
pezzi = sorted(d.glob("tratto*.mkv"), key=lambda f: int(f.stem[6:]))
veri, t = [], 0.0
for f in pezzi[:-1]:
    t += dur(f); veri.append(round(t, 2))
def pr(trovati, veri, tol):
    presi = [v for v in veri if any(abs(v - x) <= tol for x in trovati)]
    falsi = [x for x in trovati if not any(abs(v - x) <= tol for v in veri)]
    return f"{len(presi)}/{len(veri)} trovati, {len(falsi)} falsi {falsi}"
print("STACCHI (±0,1 s):", pr(m["stacchi"], veri, 0.1), "| veri:", veri)
print("LAMPI (±0,1 s):", pr([l["t"] for l in m["lampi"]], [l["t"] for l in p["lampi"]], 0.1))
print("MUSICA:", m["musica_libreria"][0], "vero:", Path(p["musica"]["file"]).name)
print("SUONI veri:", [(s["t"], Path(s["file"]).name[:30]) for s in p["suoni"]])
print("   trovati dalla libreria:", m["suoni"]["dalla_libreria"])
# pezzi della live: per ogni pezzo vero, il pezzo misurato che lo copre e lo scarto sull'inizio in live
inizio, err, coperti = 0.0, [], 0
for (a, b), f in zip(tg["tagli"], pezzi):
    L = dur(f)
    mid = inizio + L / 2
    trov = [q for q in m.get("pezzi_live", []) if q["clip"][0] <= mid <= q["clip"][1]]
    if trov:
        q = trov[0]; coperti += 1
        err.append(round((q["live"][0] - q["clip"][0]) - (a - inizio), 2))  # scarto live-clip misurato meno vero
    inizio += L
print(f"PEZZI LIVE: {coperti}/{len(tg['tagli'])} pezzi ritrovati, errore di posizione in live (s): {err}")
print("   misurati:", [(q['clip'], q['live'], q['finestre']) for q in m.get("pezzi_live", [])])
norm = lambda s: re.sub(r"[^A-Z0-9]", "", s.upper())
vere = [norm(x["text"]) for f in p["frasi"] for r in f["righe"] for x in r]
lette = set()
for e in m["scritte"]["eventi"]:
    lette |= {norm(w) for w, _ in e["parole"]} | {norm(w) for w in e["testo"].split()}
presi = [w for w in vere if w in lette]
print(f"SCRITTE: {len(presi)}/{len(vere)} parole dei sottotitoli lette dall'OCR; fisse tolte: {m['scritte']['fisse']}")
print("   mancate:", [w for w in vere if w not in lette][:30])
print("RITARDO SOTTOTITOLI:", {k: v for k, v in m["ritardo_sottotitoli"].items() if k != "valori"})
