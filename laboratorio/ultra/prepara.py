"""Sceglie gli Short di Speedy per il ciclo e ne prepara la live (fonte.py), dal più visto in giù.
Solo Short dal 2025 in poi (formato 3:4 e sottotitoli "glow": lo stile di oggi; quelli 2022-2024 hanno formato e scritte di
un altro periodo e uno stile solo non può somigliare a tutti e due). Allenamento = i primi 8 con la live trovata,
verifica = i 4 successivi. Riprende da dove era arrivato.

uso: ~/Projects/video-editor/.venv/bin/python -I ultra/prepara.py   -> ultra/dati/elenco.json
"""
import json
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
import fonte  # noqa: E402

DA = "20250101"
ALLENAMENTO, VERIFICA = 8, 4  # Riccardo, 17 nov: 8+4 per stare in ~11-12 ore (era 20+10)


def candidati():
    viste = {r.split("\t")[0]: int(r.split("\t")[1]) for r in (QUI.parent / "shorts_elenco.tsv").read_text().splitlines() if r.count("\t") >= 2}
    date = {r.split("\t")[0]: r.split("\t")[1] for r in (QUI / "shorts_date.tsv").read_text().splitlines() if r.count("\t") >= 1}
    return [i for i in sorted(viste, key=lambda i: -viste[i]) if date.get(i, "0") >= DA]


def prova(ident):
    f = fonte.DATI / ident / "fonte.json"
    try:
        return json.loads(f.read_text()) if f.exists() else fonte.fonte(ident)
    except Exception as e:  # uno Short che non si scarica non ferma gli altri
        print(f"{ident}: errore {type(e).__name__}: {str(e)[-200:]}", flush=True)
        return "errore"


def main():
    trovati, scartati, rifare = [], [], []
    for ident in candidati():
        if len(trovati) >= ALLENAMENTO + VERIFICA:
            break
        info = prova(ident)
        if info == "errore":
            rifare.append(ident)
            continue
        (trovati if info and info.get("trovata") else scartati).append(ident)
        scrivi(trovati, scartati)
    for ident in rifare:  # gli Short andati in errore (rete, download) si riprovano una volta in fondo
        if len(trovati) < ALLENAMENTO + VERIFICA:
            info = prova(ident)
            (trovati if isinstance(info, dict) and info.get("trovata") else scartati).append(ident)
    scrivi(trovati, scartati)
    print(f"pronti {len(trovati)}, senza live {len(scartati)}", flush=True)


def scrivi(trovati, scartati):
    (fonte.DATI / "elenco.json").write_text(json.dumps({"allenamento": trovati[:ALLENAMENTO], "verifica": trovati[ALLENAMENTO:], "senza_live": scartati,
                                                        "completo": len(trovati) >= ALLENAMENTO + VERIFICA}, indent=1))


if __name__ == "__main__":
    main()
