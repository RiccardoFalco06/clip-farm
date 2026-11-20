"""Agente 1 di speedy-ultra: da un pezzo di live grezzo alla clip finita, senza vedere lo Short originale.
Parte identico allo stile speedy del sistema vivo (stessi passi della catena: analisi -> selezione -> giudice che prepara il
montaggio -> inquadratura -> monta.py); il ciclo di miglioramento cambia SOLO i file di questa cartella (prompt/, monta.py,
remotion/, questo file).

uso: python3 -I ultra/editore/edita.py SORGENTE.mp4 USCITA.mp4 [STREAMER]
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

QUI = Path(__file__).resolve().parent
FARM = next(p for p in QUI.parents if (p / "config.json").exists())
sys.path.insert(0, str(FARM))
import catena  # noqa: E402

PROMPT = QUI / "prompt"
LOCK = FARM / "state/catena.lock"
MUSICHE = ("phonk_Untitled-Super-Slowed.m4a", "funk_MONTAGEM-ALQUIMIA.m4a", "funk_MONTAGEM-PERIGOSA.m4a")  # la prima è quella normale
_spec = importlib.util.spec_from_file_location("monta_ultra", QUI / "monta.py")  # il monta.py di questa cartella, non quello del progetto
monta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(monta)


@contextmanager
def blocco():
    """Un solo lavoro pesante alla volta su tutto il Mac (Whisper, Demucs, Remotion): lo stesso blocco del sistema vivo."""
    while True:
        try:
            LOCK.mkdir()
            break
        except FileExistsError:
            time.sleep(5)
    try:
        yield
    finally:
        LOCK.rmdir()


SICURO = ("\n\n## Questo tratto\nQuesto pezzo di live è stato scelto perché contiene un momento da clip: proponi sempre almeno un candidato "
          "(il migliore che trovi), anche se ti sembra debole.\n")


def seleziona(analisi, live, quanti=3, sicuro=False):
    testo = catena.chiedi((PROMPT / "seleziona.md").read_text() + (PROMPT / "speedy.md").read_text() + (SICURO if sicuro else ""),
                          {"STREAMER": live["streamer"], "TITOLO": live["titolo"], "GIOCO": live["gioco"] or "?", "MAX": quanti, "ANALISI": json.dumps(analisi, ensure_ascii=False)})
    return [k for k in catena.primo_json(testo) if isinstance(k, dict)][:quanti]


def come_suona(tagli, frasi):
    """La storia come la sente lo spettatore: per ogni pezzo le frasi che ci cadono dentro."""
    return [f"P{i + 1} [{a}-{b}]: «{' '.join(x['testo'] for x in frasi if x.get('fine', x['t'] + 3) > a + 0.3 and x['t'] < b - 0.3) or '(nessuna parola)'}»"
            for i, (a, b) in enumerate(tagli)]


def rivedi(candidati, analisi, live):
    """Ultra g03: un montatore capo (Opus) rilegge ogni storia come la sente lo spettatore, con la trascrizione intera e quello che
    viene dopo l'ultimo pezzo, e corregge apertura, esito mancante, perché, riempitivi, chiusura, narrazioni e icone (scelta_pezzi,
    hook, struttura e finale i voti più bassi in 3 giri). Un candidato corretto male resta quello di prima."""
    frasi = analisi["frasi"]
    righe = []
    for c in candidati:
        t = catena.storia_da(c.get("tagli"), analisi["durata"]) or []
        fine = max((b for _, b in t), default=float(c.get("fine", 0)))
        inizio = min((a for a, _ in t), default=float(c.get("inizio", 0)))
        # g04: in 3 clip su 8 l'innesco stava 15-30 s prima del primo pezzo (la domanda, la prima reazione) e la revisione non lo vedeva
        righe.append({**c, "_come_suona": come_suona(t, frasi),
                      "_prima_dell_inizio": " ".join(f"[{x['t']:.0f}] {x['testo']}" for x in frasi if inizio - 40 <= x["t"] < inizio - 0.3),
                      "_dopo_la_fine": " ".join(f"[{x['t']:.0f}] {x['testo']}" for x in frasi if fine - 0.3 < x["t"] <= fine + 60)})
    prompt = (PROMPT / "rivedi.md").read_text()
    for chiave, valore in {"STILE": (PROMPT / "speedy.md").read_text().strip(), "STREAMER": live["streamer"], "FRASI": "\n".join(f"{x['t']:.1f}–{x.get('fine', x['t']):.1f} {x['testo']}" for x in frasi),
                           "CANDIDATI": json.dumps(righe, ensure_ascii=False)}.items():
        prompt = prompt.replace("{{" + chiave + "}}", str(valore))
    try:
        r = subprocess.run([catena.CLAUDE, "-p", prompt, "--model", "claude-opus-5-5", "--max-turns", "2"], capture_output=True, text=True,
                           timeout=900, env={**os.environ, "OBSIDIAN_SYNC_CHILD": "1"}, cwd=QUI)
        nuovi = catena.primo_json(r.stdout or r.stderr)
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f"  revisione non riuscita ({type(e).__name__}): restano i candidati del selezionatore", flush=True)
        return candidati
    out = []
    for vecchio, nuovo in zip(candidati, nuovi if isinstance(nuovi, list) else []):
        unito = {**vecchio, **{a: b for a, b in nuovo.items() if a[0] != "_"}} if isinstance(nuovo, dict) else vecchio
        forma = bool(catena.storia_da(unito.get("tagli"), analisi["durata"]))
        ok = unito is not vecchio and forma and catena.valida({"titolo": "x", **unito}, analisi) is not None
        out.append(unito if ok else vecchio)
        perche = "" if ok else " (non è un dizionario)" if unito is vecchio else " (pezzi fuori misura: 2-14 pezzi di 0,8-12 s, 12-45 s)" if not forma else " (clou o tempi non validi)"
        print(f"  revisione: {'tenuta' if ok else 'scartata'}{perche} — {json.dumps(nuovo.get('arco') if isinstance(nuovo, dict) else None, ensure_ascii=False)[:300]}", flush=True)
    return out + candidati[len(out):]


def giudica(k, analisi, live, lav):
    """Come catena.giudica ma con il prompt di questa cartella; tiene sempre il risultato (serve la clip migliore, non un sì/no)."""
    salvato = catena.QUI
    vero = (FARM / "prompt/giudica.md")
    testo_vero = vero.read_text()
    try:
        # catena.giudica legge prompt/giudica.md dal progetto: per non toccarlo si passa da una cartella ombra con il nostro prompt
        ombra = QUI / "_ombra"
        (ombra / "prompt").mkdir(parents=True, exist_ok=True)
        shutil.copy(PROMPT / "giudica.md", ombra / "prompt/giudica.md")
        for nome in ("suoni", "musica"):
            if not (ombra / nome).exists():
                (ombra / nome).symlink_to(FARM / nome)
        catena.QUI = ombra
        return catena.giudica(k, analisi, live, lav, tutte=True)
    finally:
        catena.QUI = salvato
        assert vero.read_text() == testo_vero


def parole_live(sorgente, lav, analisi):
    """Ultra g02: la live intera trascritta come le clip (voce isolata, più prove di Whisper, parole allineate) -> frasi brevi per il
    selezionatore e parole riusate dal montaggio. Se esce molto meno parlato di prima (Demucs che mangia la voce) restano le frasi dell'analisi."""
    d = lav / "parole"
    f = d / "parole.json"
    if not f.exists():
        d.mkdir(exist_ok=True)
        with blocco():
            f.write_text(json.dumps(monta.parole(Path(sorgente), d, coerenza=False), ensure_ascii=False))
    w = json.loads(f.read_text())
    vere = lambda x: x.split() if len(set(x.split())) * 3 >= len(x.split()) else []  # un ciclo ("y'all" x 50) non conta
    if len(w) < 0.5 * sum(len(vere(x["testo"])) for x in analisi["frasi"]):
        print(f"  trascrizione fine scartata: {len(w)} parole contro le frasi dell'analisi", flush=True)
        return None
    analisi["frasi"] = monta.frasi_da_parole(w)
    return {"file": str(f), "da": 0}


def storia_extra(k, v):
    """catena.valida toglie narrazioni e freccia dalle storie (i secondi del modello non sono quelli della clip montata): qui si tengono
    quelle del selezionatore con il secondo della live ("live"), che monta.py porta sulla storia. Solo se cadono dentro un pezzo."""
    dentro = lambda t: isinstance(t, (int, float)) and any(a <= t < b for a, b in v["tagli"])
    n = [{"live": float(x["t"]), "durata": min(2.0, max(1.2, float(x.get("durata", 1.5)))), "testo": str(x["testo"]).upper().strip("*")[:24],
          **({"colore": x["colore"]} if x.get("colore") in catena.COLORI_SPEEDY else {})}
         for x in (k.get("narrazioni") or []) if isinstance(x, dict) and x.get("testo") and dentro(x.get("t"))][:6]  # g03: Speedy 3-16 per clip, noi 1-4
    fr = k.get("freccia")
    ok = isinstance(fr, dict) and fr.get("chi") in ("sinistra", "destra", "unica") and fr.get("testo") and dentro(fr.get("t"))
    # g03: emoji sulla parola che nomina una cosa (catena.valida non le conosce); monta.py le posa sopra o sotto la scritta di quell'istante
    ic = [{"t": str(x["t"]).lower().strip(" .,!?\"'"), "emoji": str(x["emoji"])[:4]} for x in (k.get("icone") or [])
          if isinstance(x, dict) and isinstance(x.get("t"), str) and x["t"].strip() and x.get("emoji")][:4]
    return {**({"narrazioni": n} if n else {}), **({"icone": ic} if ic else {}),
            **({"freccia": {"live": float(fr["t"]), "durata": 2.3, "chi": fr["chi"], "testo": str(fr["testo"]).upper()[:18]}} if ok else {})}


def edita(sorgente, uscita, streamer="IShowSpeed"):
    sorgente, uscita = Path(sorgente).resolve(), Path(uscita).resolve()
    ident = uscita.stem
    lav = QUI / "lavoro" / f"{ident}_regia"  # monta.py usa lavoro/<id>: cartelle separate
    lav.mkdir(parents=True, exist_ok=True)
    live = {"id": 0, "streamer": streamer, "titolo": "live", "gioco": None}
    f_an = lav / "analisi.json"
    if not f_an.exists():
        with blocco():
            f_an.write_text(subprocess.run([str(catena.VE / ".venv/bin/python"), "-I", str(FARM / "analizza.py"), "--ultimo", str(sorgente)],
                                           capture_output=True, text=True, check=True, timeout=1800).stdout)
    analisi = json.loads(f_an.read_text())
    try:
        parole_da = parole_live(analisi["sorgente"], lav, analisi) if analisi["frasi"] else None
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as e:  # senza la trascrizione fine si va avanti con quella dell'analisi
        print(f"  trascrizione fine non riuscita ({type(e).__name__}): uso le frasi dell'analisi", flush=True)
        parole_da = None
    candidati = (seleziona(analisi, live) or seleziona(analisi, live, sicuro=True)) if analisi["frasi"] else []
    candidati = rivedi(candidati, analisi, live) if candidati else []
    giudicati = [{**v, **(storia_extra(c, v) if v.get("tagli") else {})} for c in candidati if (v := giudica(c, analisi, live, lav))]
    if not giudicati:
        raise RuntimeError(f"nessun candidato montabile ({len(candidati)} proposti)")
    k = max(giudicati, key=lambda v: v["_media"])
    if parole_da and k.get("tagli"):  # il montaggio riusa le parole già trascritte invece di rifarle sul tratto
        k["parole_da"] = parole_da
    # g01: Speedy usa sempre slowed/phonk, mai il piano allegro. g03: solo basi con un titolo riconoscibile (Shazam le trova quasi
    # ovunque); phonk_slowed-phonk, scelta in 8 clip su 8, veniva presa per 3 brani diversi o per nessuno
    if (k.get("musica") or {}).get("file") not in MUSICHE:
        k["musica"] = {"file": MUSICHE[0]}
    L = catena.inquadra(live, analisi["sorgente"], k["inizio"], k["fine"], lav, lav)
    if k.get("tagli") and L["tipo"] == "fascia":  # come catena.monta_clip
        L = {"tipo": "pieno", "cx": L.get("cx", 960), "cy": 560, "stretto": 1.05, "cx_max": 1300}
        try:
            L["cx_tagli"] = catena.chi_parla(live, analisi["sorgente"], k["tagli"], analisi["frasi"], lav, lav)
        except (subprocess.SubprocessError, OSError, ValueError, KeyError):
            pass
    scheda = {"id": ident, "stile": "speedy", "sorgente": analisi["sorgente"], "layout": L, "titolo": k["_titolo"], "didascalia": k["_didascalia"],
              "storia": k["_perche"], "firma": "@iamclipfarmer67", "uscita": str(uscita), **{a: b for a, b in k.items() if a[0] != "_"}}
    (lav / "scheda.json").write_text(json.dumps(scheda, ensure_ascii=False, indent=1))
    nuda = {a: b for a, b in scheda.items() if a not in catena.CAMPI_SPEEDY}
    for sch in (scheda, nuda):  # una clip non si perde per un effetto: come nel vivo, se fallisce si riprova senza i campi di stile
        (lav / "scheda_usata.json").write_text(json.dumps(sch, ensure_ascii=False, indent=1))
        with blocco():
            r = subprocess.run(["python3", "-I", str(QUI / "monta.py"), str(lav / "scheda_usata.json")], capture_output=True, text=True, timeout=2400)
        if not r.returncode:
            break
        print(f"  montaggio fallito: {r.stderr[-400:]}", flush=True)
    if r.returncode:
        raise RuntimeError(f"montaggio fallito: {r.stderr[-400:]}")
    return {"uscita": str(uscita), "titolo": k["_titolo"], "tagli": k.get("tagli"), "voti": k.get("_media")}


if __name__ == "__main__":
    print(json.dumps(edita(*sys.argv[1:4]), ensure_ascii=False))
