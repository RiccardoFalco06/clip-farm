"""Agente 2 di speedy-ultra: confronta la clip dell'agente 1 con lo Short originale di Speedy nato dalla stessa live.
Misure uguali per le due clip (ultra/misura.py), differenze numeriche (ultra/confronta.py), poi Opus guarda i fotogrammi e dà
un voto per sezione. Il totale è la media pesata dei voti, calcolata qui (non dal modello): stabile da un giro all'altro.

uso: python3 -I ultra/giudice/giudica.py MISURE_ORIGINALE MISURE_NOSTRA USCITA.json [fonte.json]
  MISURE_* = cartelle di misura.py (misure.json, fogli/, fotogrammi/); fonte.json dà i pezzi di live dell'originale.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
import confronta  # noqa: E402

CLAUDE = Path.home() / ".local/bin/claude"
MODELLO = "claude-opus-5-5"
PESI = {"scelta_pezzi": 1.5, "hook": 1.5, "struttura": 1.2, "finale": 1.2, "storia_valore": 1.5, "ritmo_tagli": 1.0, "sottotitoli_testo": 1.0,
        "sottotitoli_colori": 0.8, "sincronizzazione": 1.0, "effetti_visivi": 1.0, "grafiche": 0.8, "inquadratura": 0.8, "musica": 0.8, "suoni": 0.7}


def totale(voti):
    """Media pesata dei voti (0-10). Un voto mancante o non numerico vale 0: il giudice deve votare tutto."""
    v = {k: float(voti.get(k)) if isinstance(voti.get(k), (int, float)) else 0.0 for k in PESI}
    return round(sum(v[k] * p for k, p in PESI.items()) / sum(PESI.values()), 2)


def corte(m):
    ev = [{"da": e["da"], "a": e["a"], "testo": e["testo"], "parole": e["parole"], "y": e["y"], "colori": e["colori"][:2]} for e in m["scritte"]["eventi"]]
    return json.dumps(ev, ensure_ascii=False)


def primo_json(t):
    for i, ch in enumerate(t):
        if ch == "{":
            try:
                return json.JSONDecoder().raw_decode(t[i:])[0]
            except ValueError:
                pass
    raise ValueError("nessun JSON: " + t[-300:])


def giudica(cart_a, cart_b, uscita, fonte=None):
    cart_a, cart_b = Path(cart_a).resolve(), Path(cart_b).resolve()
    a, b = json.loads((cart_a / "misure.json").read_text()), json.loads((cart_b / "misure.json").read_text())
    if fonte and not a.get("pezzi_live"):  # l'originale si misura senza sorgente: i suoi pezzi li ha trovati fonte.py
        a["pezzi_live"] = [{"clip": p["clip"], "live": p["sorgente"]} for p in json.loads(Path(fonte).read_text()).get("pezzi_speedy", [])]
    c = confronta.confronta(a, b)
    val = {"FOGLI_A": ", ".join(f"`{f}`" for f in sorted((cart_a / "fogli").glob("*.jpg"))), "FOGLI_B": ", ".join(f"`{f}`" for f in sorted((cart_b / "fogli").glob("*.jpg"))),
           "FOTO_A": cart_a / "fotogrammi", "FOTO_B": cart_b / "fotogrammi", "CONFRONTO": json.dumps(c, ensure_ascii=False, indent=1),
           "SCRITTE_A": corte(a), "SCRITTE_B": corte(b),
           "PAROLE_A": " ".join(f"{w}@{t}" for w, t, _ in a["parole_dette"]), "PAROLE_B": " ".join(f"{w}@{t}" for w, t, _ in b["parole_dette"]),
           "LAMPI_A": json.dumps(a["lampi"]), "LAMPI_B": json.dumps(b["lampi"]), "STACCHI_A": a["stacchi"], "STACCHI_B": b["stacchi"],
           "PEZZI_A": [p["live"] for p in a.get("pezzi_live") or []], "PEZZI_B": [p["live"] for p in b.get("pezzi_live") or []],
           "SUONI_A": json.dumps({"attacchi_forti": [x for x in a["suoni"]["attacchi"] if x["forza"] >= 5], "libreria": a["suoni"]["dalla_libreria"]}),
           "SUONI_B": json.dumps({"attacchi_forti": [x for x in b["suoni"]["attacchi"] if x["forza"] >= 5], "libreria": b["suoni"]["dalla_libreria"]}),
           "MUSICA_A": json.dumps({"titolo": a.get("musica_titolo"), "volume": a["volume"]}), "MUSICA_B": json.dumps({"titolo": b.get("musica_titolo"), "volume": b["volume"]})}
    prompt = (QUI / "prompt/confronta.md").read_text()
    for k, v in val.items():
        prompt = prompt.replace("{{" + k + "}}", str(v))
    for prova in range(2):
        r = subprocess.run([str(CLAUDE), "-p", prompt, "--model", MODELLO, "--max-turns", "60", "--allowedTools", "Read"], capture_output=True, text=True,
                           timeout=1800, cwd=QUI, env={**os.environ, "OBSIDIAN_SYNC_CHILD": "1"})
        try:
            g = primo_json(r.stdout)
            break
        except ValueError as e:
            errore = e
    else:
        raise RuntimeError(f"giudice senza JSON: {errore}")
    g["totale"] = totale(g.get("voti", {}))
    g["misure"] = c
    Path(uscita).write_text(json.dumps(g, ensure_ascii=False, indent=1))
    return g


if __name__ == "__main__":
    if sys.argv[1:] == ["--prova"]:
        assert totale({k: 10 for k in PESI}) == 10 and totale({}) == 0 and totale({**{k: 5 for k in PESI}, "hook": "x"}) < 5
        print("ok")
    else:
        g = giudica(*sys.argv[1:5])
        print(json.dumps({"totale": g["totale"], "voti": g.get("voti")}, ensure_ascii=False))
