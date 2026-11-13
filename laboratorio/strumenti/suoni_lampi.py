"""Suoni sui lampi: per ogni lampo rilevato (riferimenti/lampi.jsonl) cerca l'attacco audio più vicino (±0,3 s) e ne
misura la forma: banda dominante, salto di energia nei bassi (<150 Hz) e negli alti (>5 kHz), coda dei bassi (secondi sopra metà salto).
Un file audio alla volta. uso: python3 suoni_lampi.py  -> riferimenti/suoni_lampi.json + tabella per colore"""
import collections
import json
import statistics as st
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from audio import carica, spettro, SR

HOP = 256


def colore(c, tipo):
    r, g, b = c
    if tipo == "bianco":
        return "bianco"
    if r > 120 and g > 120 and b < 90:
        return "giallo"
    if g > r + 40 and g > b + 40:
        return "verde"
    if r > g + 60 and r > b + 60:
        return "rosso"
    return "altro"


out = []
for riga in open("riferimenti/lampi.jsonl"):
    d = json.loads(riga)
    if not d["lampi"]:
        continue
    x = carica(f"riferimenti/audio/{d['id']}.wav")
    f, t, S = spettro(x)
    db = lambda a, z: 20 * np.log10(S[(f >= a) & (f < z)].mean(axis=0) + 1e-6)
    bassi, alti, medi = db(20, 150), db(5000, 11000), db(300, 3000)
    fr = lambda sec: int(sec * SR / HOP)
    for l in d["lampi"]:
        i = fr(l["t"])
        if i < fr(0.6) or i > len(bassi) - fr(1.2):
            continue
        prima = slice(i - fr(0.5), i - fr(0.1))
        dopo = slice(i - fr(0.05), i + fr(0.3))
        sb = float(bassi[dopo].max() - np.median(bassi[prima]))
        sa = float(alti[dopo].max() - np.median(alti[prima]))
        sm = float(medi[dopo].max() - np.median(medi[prima]))
        # anticipo: quando i bassi/alti superano metà del salto, rispetto all'immagine
        serie, salto = (bassi, sb) if sb >= sa else (alti, sa)
        base = np.median(serie[prima])
        sopra = np.where(serie[i - fr(0.3): i + fr(0.3)] > base + salto / 2)[0]
        scarto = (sopra[0] - fr(0.3)) * HOP / SR if len(sopra) else None
        coda = 0
        if sb > 8:
            k = i
            while k < len(bassi) and bassi[k:k + fr(0.2)].max() > np.median(bassi[prima]) + sb / 2:
                k += fr(0.1)
            coda = (k - i) * HOP / SR
        out.append({"id": d["id"], "t": l["t"], "colore": colore(l["colore_neri"], l["tipo"]), "salto_bassi_db": round(sb, 1), "salto_alti_db": round(sa, 1), "salto_voce_db": round(sm, 1),
                    "scarto_s": None if scarto is None else round(float(scarto), 2), "coda_bassi_s": round(float(coda), 1)})
    del x, S
json.dump(out, open("riferimenti/suoni_lampi.json", "w"), indent=1)
per = collections.defaultdict(list)
for o in out:
    per[o["colore"]].append(o)
print(f"lampi con audio misurato: {len(out)}")
for c, v in per.items():
    boom = [o for o in v if o["salto_bassi_db"] > 10]
    alto = [o for o in v if o["salto_alti_db"] > 10 and o["salto_bassi_db"] <= 10]
    niente = [o for o in v if o["salto_bassi_db"] <= 10 and o["salto_alti_db"] <= 10]
    sc = [o["scarto_s"] for o in boom + alto if o["scarto_s"] is not None]
    print(f"{c:7s} n={len(v):3d}  colpo di bassi (>10 dB) {len(boom):3d} ({100 * len(boom) // len(v)}%), coda mediana {st.median([o['coda_bassi_s'] for o in boom]) if boom else 0:.1f} s  |  solo alti (>10 dB: fruscio/ding) {len(alto):3d} ({100 * len(alto) // len(v)}%)  |  nessun attacco {len(niente):3d} ({100 * len(niente) // len(v)}%)  |  scarto mediano suono-immagine {st.median(sc) if sc else 0:+.2f} s")
