"""Catena di lavorazione: per ogni blocco chiuso, analisi -> selezione (Sonnet) -> montaggio.

uso: python3 -I catena.py        (launchd, ogni minuto; un giro alla volta: Demucs, Whisper e Remotion insieme non
                                  stanno in 16 GB)
Le clip finite vanno in clip/<live>/ e nel database con stato "montata": da lì le prende il pubblicatore.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con -I la cartella dello script non è nel percorso
from obsidian import nome  # noqa: E402
from stato import CONFIG, QUI, REG, db, evento, kv, uno_alla_volta  # noqa: E402

VE = Path.home() / "Projects/video-editor"
CLAUDE = Path.home() / ".local/bin/claude"
COLORI = {"magenta", "ciano"}


def chiusi(d):
    """Blocchi finiti di scrivere: tutti tranne l'ultimo, finché la registrazione è in corso."""
    b = sorted(d.glob("b_*.ts"))
    return b if (d / "FINE").exists() else b[:-1]


CAMPI_SPEEDY = ("colori", "finale", "narrazioni", "freccia", "vibe")
COLORI_SPEEDY = {"verde", "lime", "giallo", "arancio", "rosso", "magenta", "ciano", "rosa", "viola", "corallo", "oro", "bianco"}


def speedy_campi(k):
    """Campi facoltativi dello stile speedy scelti dal modello (prompt/speedy.md): si tengono solo quelli ben formati.
    Posizioni e sovrapposizioni le garantisce laboratorio/monta.py (freccia sulla faccia, scritte che non si coprono)."""
    out = {}
    if colori := {str(p): c for p, c in (k.get("colori") or {}).items() if c in COLORI_SPEEDY}:
        out["colori"] = dict(list(colori.items())[:8])
    f = k.get("finale")
    if isinstance(f, dict) and isinstance(f.get("testo"), str) and 0 < len(f["testo"]) <= 24:
        out["finale"] = {"testo": f["testo"].upper(), "emoji": str(f.get("emoji") or "😂")[:4], "colore": f["colore"] if f.get("colore") in COLORI_SPEEDY else "verde"}
    n = [{"t": x["t"], "durata": min(3.0, max(1.5, float(x.get("durata", 2)))), "testo": str(x["testo"]).upper()[:24]}
         for x in (k.get("narrazioni") or []) if isinstance(x, dict) and isinstance(x.get("t"), (int, float)) and x.get("testo")][:2]
    if n:
        out["narrazioni"] = n
    fr = k.get("freccia")
    if isinstance(fr, dict) and fr.get("chi") in ("sinistra", "destra", "unica") and fr.get("testo"):
        out["freccia"] = {"t": min(3.0, max(0.0, float(fr.get("t", 0.3)))), "durata": 2.3, "chi": fr["chi"], "testo": str(fr["testo"]).upper()[:18]}
    if k.get("vibe") == "serio":
        out["vibe"] = "serio"
    return out


def valida(k, analisi):
    """La risposta del modello è un dato esterno: si tiene solo ciò che il montaggio può eseguire. None = clip scartata."""
    try:
        i, f, clou = float(k["inizio"]), float(k["fine"]), float(k["clou"])
        z0, z1 = analisi["zona"]
        tagli = storia_da(k.get("tagli"), analisi["durata"])
        if tagli:  # montaggio a storia (12/11): il tratto va dal primo all'ultimo pezzo, la clip è la somma dei pezzi
            i, f = tagli[0][0], max(b for _, b in tagli)
        if not (0 <= i < f <= analisi["durata"] and (tagli or 8 <= f - i <= 60) and z0 <= clou < z1 and i <= clou <= f):
            return None
        suoni = [x for x in k.get("suoni", []) if (QUI / "suoni/approvati" / str(x.get("file"))).is_file() and isinstance(x.get("t"), (int, float, str)) and parola_ok(x["t"], tagli) is not None][:3]
        musica = k.get("musica")
        return {
            "inizio": i, "fine": f, **({"tagli": tagli, "parole_blocco": 4} if tagli else {}),
            "enfasi": {p: c for p, c in k.get("enfasi", {}).items() if c in COLORI},
            "lampi": [{**x, "t": parola_ok(x["t"], tagli)} for x in k.get("lampi", []) if re.fullmatch(r"#[0-9a-fA-F]{6}", str(x.get("colore"))) and "t" in x and parola_ok(x["t"], tagli) is not None][:3],
            "zoom": [{"t": parola_ok(x["t"], tagli), "durata": min(3.0, float(x.get("durata", 2))), "scala": min(1.3, float(x.get("scala", 1.15)))} for x in k.get("zoom", []) if "t" in x and parola_ok(x["t"], tagli) is not None][:1],
            "suoni": [{"t": parola_ok(x["t"], tagli), "file": x["file"], "volume": min(1.0, float(x.get("volume", 0.7))), "anticipo": float(x.get("anticipo", 0))} for x in suoni],
            **({"musica": {"file": musica}} if musica and (QUI / "musica" / str(musica)).is_file() else {}),
            **({a: b for a, b in speedy_campi(k).items() if not (tagli and a in ("narrazioni", "freccia"))} if CONFIG.get("stile") == "speedy" else {}),
            "_titolo": str(k["titolo"])[:100], "_didascalia": str(k.get("didascalia", ""))[:500], "_perche": str(k.get("perche", ""))[:300],
        }
    except (KeyError, TypeError, ValueError):
        return None


def parola_ok(t, tagli):
    """Tempo di un effetto. In una storia i secondi del modello non corrispondono alla clip montata: vale solo la parola ("thousand@19" → "thousand")."""
    if not tagli:
        return t
    return str(t).partition("@")[0] if isinstance(t, str) and re.search(r"[A-Za-z]", t) else None


def storia_da(tagli, durata):
    """I pezzi di una clip a storia, se ben formati: 2-14 pezzi [da, a] dentro il tratto, ognuno di 0,8-12 s, totale 12-45 s, in un
    tratto di al massimo 4 minuti. Altrimenti None (si monta il tratto unico)."""
    try:
        t = [[round(float(a), 2), round(float(b), 2)] for a, b in tagli]
    except (TypeError, ValueError):
        return None
    ok = 2 <= len(t) <= 14 and all(0 <= a and b <= durata and 0.8 <= b - a <= 12 for a, b in t) \
        and 12 <= sum(b - a for a, b in t) <= 45 and max(b for _, b in t) - min(a for a, _ in t) <= 240
    return t if ok else None


def chiedi(prompt, valori, strumenti=()):
    for chiave, valore in valori.items():
        prompt = prompt.replace("{{" + chiave + "}}", str(valore))
    r = subprocess.run([CLAUDE, "-p", prompt, "--model", "claude-sonnet-5-5", "--max-turns", "4", *(["--allowedTools", *strumenti] if strumenti else [])],
                       capture_output=True, text=True, timeout=600,
                       env={**os.environ, "OBSIDIAN_SYNC_CHILD": "1"}, cwd=QUI)  # i giri automatici non generano note "Conversazione" nel vault
    return r.stdout or r.stderr


def primo_json(testo, apre="["):
    """Il primo valore JSON completo nel testo. Il modello a volte aggiunge un commento dopo la risposta (anche con altre
    parentesi dentro): prendere dalla prima all'ultima parentesi dava JSON non valido e il blocco andava perso."""
    for i, ch in enumerate(testo):
        if ch == apre:
            try:
                return json.JSONDecoder().raw_decode(testo[i:])[0]
            except ValueError:
                pass
    raise ValueError("nessun JSON")


def seleziona(analisi, live):
    """Primo passo, solo testo: i momenti candidati, dal più forte."""
    testo = chiedi((QUI / "prompt/seleziona.md").read_text() + ((QUI / "prompt/speedy.md").read_text() if CONFIG.get("stile") == "speedy" else ""), {"STREAMER": live["streamer"], "TITOLO": live["titolo"], "GIOCO": live["gioco"] or "?",
                                                               "MAX": CONFIG["candidati_per_blocco"], "ANALISI": json.dumps(analisi, ensure_ascii=False)})
    try:
        return [k for k in primo_json(testo) if isinstance(k, dict)][: CONFIG["candidati_per_blocco"]]
    except (AttributeError, ValueError, TypeError):
        raise RuntimeError(f"selezione senza JSON valido: {testo[-300:]}")


def promossa(g, minimo=None):
    """Passa solo ciò che uno sconosciuto capisce e si gode: nessun voto insufficiente e media alta."""
    minimo = minimo or CONFIG["voto_minimo"]
    try:
        voti = [float(g[v]) for v in ("capibile", "divertente", "finale")]
    except (KeyError, TypeError, ValueError):
        return False
    return min(voti) >= minimo - 1 and sum(voti) / 3 >= minimo


def giudica(k, analisi, live, lav, tutte=False):
    """Secondo passo, con i fotogrammi: lo "spettatore sconosciuto" vota, corregge il taglio e prepara il montaggio."""
    try:
        i, f, clou = float(k["inizio"]), float(k["fine"]), float(k["clou"])
    except (KeyError, TypeError, ValueError):
        return None
    a, b = max(0, i - 15), min(analisi["durata"], f + 3)  # 15 s prima: la premessa spesso sta lì
    img = lav / "candidato.jpg"
    font = "/System/Library/Fonts/Helvetica.ttc"
    tagli = storia_da(k.get("tagli"), analisi["durata"])
    dentro = (lambda t: any(x - 1 <= t <= y + 1 for x, y in tagli)) if tagli else (lambda t: a - 5 <= t <= b + 5)
    # storia: il giudice vede e legge solo i pezzi che finiscono nella clip (12/11: giudicando tutto il tratto, tempi morti compresi, bocciava storie buone)
    scelta = f"select='{'+'.join(f'between(t,{x - a:.2f},{y - a:.2f})' for x, y in tagli)}',setpts=N/FRAME_RATE/TB," if tagli else ""
    durata = sum(y - x for x, y in tagli) if tagli else b - a
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(a), "-t", str(b - a), "-i", analisi["sorgente"],
                    "-vf", f"{scelta}fps=24/{durata:.2f},scale=480:270" + ("" if tagli else f",drawtext=fontfile={font}:text='%{{eif\\:t+{a:.0f}\\:d}} s':fontsize=28:fontcolor=yellow:box=1:boxcolor=black@0.7:x=6:y=6") + ",tile=6x4",
                    "-frames:v", "1", str(img)], check=True, timeout=180)
    storia = "" if not tagli else (
        f"**Clip a storia**: il montaggio tiene solo questi pezzi (secondi della sorgente) e li unisce con stacchi secchi: {json.dumps(tagli)} "
        f"({durata:.0f} s in tutto). Trascrizione e fotogrammi sono già solo quelli dei pezzi (i fotogrammi senza secondo scritto). Giudica la clip montata, "
        "non il tratto intero: i tempi morti tolti non contano. Puoi correggere i pezzi rimandando `tagli` (ognuno inizia e finisce con una frase intera, "
        "totale 20-40 s) e ignora le regole su durata, inizio e fine più sotto. Per `lampi`, `zoom` e `suoni` scrivi come `t` solo la parola esatta "
        "(\"thousand\"), senza secondi. Titolo: 25-40 caratteri, nome dello streamer, curiosità senza svelare l'esito, 2 emoji uguali alla fine. "
        f"Rimanda anche `finale_scritta` ({{\"emoji\", \"testo\", \"colore\"}}, emoji uguale al titolo, testo che non ripete il titolo); quello del selezionatore: {json.dumps(k.get('finale'), ensure_ascii=False)}.\n\n")
    suoni = json.loads((QUI / "suoni/approvati/suoni.json").read_text())["suoni"]
    testo = chiedi((QUI / "prompt/giudica.md").read_text(), {
        "STREAMER": live["streamer"], "GIOCO": live["gioco"] or "?", "IMMAGINE": img, "INIZIO": i, "FINE": f, "CLOU": clou,
        "PREMESSA": k.get("premessa", "?"), "FINALE": k.get("finale", "?"), "ZONA0": analisi["zona"][0], "ZONA1": analisi["zona"][1], "DURATA": analisi["durata"],
        "PICCHI": ", ".join(f"{x['t']} s forza {x['forza']}" for x in analisi["picchi"] if a <= x["t"] <= b) or "nessuno",
        "FRASI": "\n".join(f"{x['t']:.0f}  {x['testo']}" for x in analisi["frasi"] if dentro(x["t"])), "STORIA": storia,
        "SUONI": "\n".join(f"- {x['file']} | {x['categoria']} | {x['quando']}" for x in suoni),
        "MUSICA": ", ".join(sorted(p.name for p in (QUI / "musica").glob("*.m4a")))}, ["Read"])
    try:
        g = primo_json(testo, "{")
    except (AttributeError, ValueError):
        return None
    print(f"  candidato {i:.0f}-{f:.0f}: capibile {g.get('capibile')}, divertente {g.get('divertente')}, finale {g.get('finale')} — {str(g.get('motivo'))[:160]}", flush=True)
    scritta = g.pop("finale_scritta", None) if isinstance(g.get("finale_scritta"), dict) else k.get("finale")  # "finale" nel giudice è il voto
    if not isinstance(g.get("finale"), (int, float, str)):
        g["finale"] = None
    v = valida({**{x: k[x] for x in ("tagli", "colori") if x in k}, **g, **({"finale": scritta} if isinstance(scritta, dict) else {}), "perche": f"{g.get('cosa_succede', '')} (voti {g.get('capibile')}/{g.get('divertente')}/{g.get('finale')})"}, analisi)
    if v:
        v["_promossa"], v["_media"] = promossa(g), sum(float(g.get(x) or 0) for x in ("capibile", "divertente", "finale")) / 3
    return v if v and (tutte or v["_promossa"]) else None


def stacco(sorgente, a, b, cwd, riquadro=None):
    """Il secondo tra a e b in cui cambia la scena (a metà, se ffmpeg non risponde): il momento in cui l'immagine cambia di più
    DENTRO il riquadro della webcam. Lì l'immagine è continua finché la webcam resta al suo posto, mentre il gioco ha stacchi suoi
    (guardando tutta l'immagine il confine finiva su una schermata del gioco, due secondi prima del cambio vero).
    Senza soglia: il cambio di scena di uno streamer è spesso una transizione animata su più fotogrammi."""
    ritaglio = "crop={2}:{3}:{0}:{1},".format(*riquadro) if riquadro else ""
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", str(sorgente), "-vf", ritaglio + "scale=320:180,select='gte(scene,0)',metadata=print:file=-",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, timeout=300, cwd=cwd)
    punti = re.findall(r"pts_time:([\d.]+)\s+lavfi\.scene_score=([\d.]+)", r.stdout)
    return a + float(max(punti, key=lambda x: float(x[1]))[0]) if punti else (a + b) / 2


def tratti(letti, tempi, stacco):
    """Dai layout letti sui fotogrammi al layout della clip: fotogrammi vicini uguali fanno un tratto solo; se i tratti sono
    più d'uno la scena cambia a metà (webcam che va a schermo intero) e il layout è "misto", col confine sullo stacco di scena."""
    uguali = lambda a, b: a["tipo"] == b["tipo"] and all(abs(x - y) <= 40 for x, y in zip(a.get("facecam", []), b.get("facecam", [])))
    t = [[tempi[0], dict(letti[0])]]
    for i in range(1, len(letti)):
        if not uguali(letti[i], t[-1][1]):
            t.append([round(stacco(tempi[i - 1], tempi[i], t[-1][1].get("facecam") or letti[i].get("facecam")), 3), dict(letti[i])])
        elif "utile" in letti[i]:  # i sottotitoli dello streamer compaiono solo mentre parla: basta un fotogramma che li vede
            t[-1][1]["utile"] = min(letti[i]["utile"], t[-1][1].get("utile", 1080))
    return t[0][1] if len(t) == 1 else {"tipo": "misto", "tratti": t}


def inquadra(live, sorgente, inizio, fine, lav, cwd):
    """Layout della clip, letto da Sonnet su 6 fotogrammi del taglio: facecam sopra e gioco sotto, fascia se la webcam non c'è,
    un tratto per layout se la scena cambia a metà. Si legge per ogni clip: gioco e webcam cambiano durante la live."""
    tempi = [inizio + (fine - inizio) * (i + 0.5) / 6 for i in range(6)]
    img = [lav / f"fotogramma{i}.jpg" for i in range(6)]
    for f, t in zip(img, tempi):
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(sorgente), "-frames:v", "1", "-vf", "scale=1280:720", str(f)], check=True, timeout=120, cwd=cwd)
    prompt = (QUI / "prompt/inquadra.md").read_text().replace("{{IMMAGINI}}", ", ".join(f"`{f}`" for f in img)).replace("{{STREAMER}}", live["streamer"])
    r = subprocess.run([CLAUDE, "-p", prompt, "--model", "claude-sonnet-5-5", "--max-turns", "9", "--allowedTools", "Read"], capture_output=True, text=True, timeout=400,
                       env={**os.environ, "OBSIDIAN_SYNC_CHILD": "1"}, cwd=QUI)
    try:
        letti = primo_json(r.stdout)
        assert len(letti) == 6
    except (ValueError, AssertionError):
        return layout_da(None)
    return tratti([layout_da(x) for x in letti], tempi, lambda a, b, riquadro: stacco(sorgente, a, b, cwd, riquadro))


def layout_da(r):
    """Dalla lettura di un fotogramma (coordinate su 1280x720) al layout su 1920x1080; senza webcam, o se non si capisce, fascia al centro.
    "utile" = altezza della sorgente da tenere: sotto ci sono i sottotitoli che lo streamer ha già, e con i nostri sarebbero doppi."""
    L = {"tipo": "fascia", "cx": 960}  # senza webcam il soggetto si muove: un ritaglio stretto deciso su un fotogramma lo perde (visto su Adin Ross)
    try:
        if r.get("facecam"):
            cx = min(1920, max(0, int(r.get("soggetto_cx", 640) * 1.5)))
            x, y, w, h = (int(v * 1.5) // 2 * 2 for v in r["facecam"])
            if 100 <= w <= 1100 and 80 <= h <= 800 and x >= 0 and y >= 0 and x + w <= 1920 and y + h <= 1080:
                L = {"tipo": "diviso", "facecam": [x, y, w, h], "gioco_cx": cx}
        if isinstance(r.get("sottotitoli_y"), (int, float)) and 400 <= r["sottotitoli_y"] <= 700:  # solo nella parte bassa: più su non sono sottotitoli
            L["utile"] = int(r["sottotitoli_y"] * 1.5 - 8) // 2 * 2
    except (AttributeError, ValueError, TypeError):
        pass
    return L


def chi_parla(live, sorgente, tagli, frasi, lav, cwd):
    """Per ogni pezzo della storia il centro x (su 1920) della faccia di chi parla, o None. Riccardo, 13 nov: "capisci chi sta parlando
    e inquadralo bene". Seguire la faccia più grande inquadrava l'intervistatore mentre rispondeva l'ospite; leggere le labbra non regge
    (col microfono davanti la bocca dell'intervistatore sembrava sempre in movimento): decide Sonnet dal dialogo e da un mosaico con le facce numerate."""
    font, facce = "/System/Library/Fonts/Helvetica.ttc", []
    for i, (a, b) in enumerate(tagli):
        f = lav / f"parla{i}.png"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{(a + b) / 2:.2f}", "-i", str(sorgente), "-frames:v", "1", "-vf", "scale=1280:720", str(f)], check=True, timeout=120, cwd=cwd)
        v = [x for x in json.loads(subprocess.run([str(QUI / "laboratorio/strumenti/volti"), str(f)], capture_output=True, text=True).stdout or "[]") if x["c"] >= 0.6 and x["h"] >= 27]
        facce.append(v)
        segni = [f"drawbox=x={x['x']:.0f}:y={x['y']:.0f}:w={x['w']:.0f}:h={x['h']:.0f}:color=yellow:t=5,drawtext=fontfile={font}:text='{n + 1}':x={x['x']:.0f}:y={max(0, x['y'] - 50):.0f}:fontsize=46:fontcolor=yellow:box=1:boxcolor=black@0.7" for n, x in enumerate(v)]
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(f), "-vf", ",".join(segni + [f"drawtext=fontfile={font}:text='P{i + 1}':x=12:y=12:fontsize=54:fontcolor=white:box=1:boxcolor=black@0.8"]), str(lav / f"parla{i}.jpg")], check=True, timeout=60)
    centro = lambda v, n: (v[n]["x"] + v[n]["w"] / 2) * 1.5
    if all(len(v) <= 1 for v in facce):  # al massimo una faccia per pezzo: non c'è niente da scegliere
        return [centro(v, 0) if v else None for v in facce]
    righe = (len(tagli) + 1) // 2
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(lav / "parla%d.jpg"), "-vf", f"scale=640:360,tile=2x{righe}", "-frames:v", "1", str(lav / "parlanti.jpg")], check=True, timeout=60)
    pezzi = "\n".join(f"- P{i + 1}: «{' '.join(x['testo'] for x in frasi if x.get('fine', x['t'] + 3) > a + 0.3 and x['t'] < b - 0.3) or '(nessuna parola)'}»" for i, (a, b) in enumerate(tagli))
    testo = chiedi((QUI / "prompt/parlante.md").read_text(), {"IMMAGINE": lav / "parlanti.jpg", "STREAMER": live["streamer"], "PEZZI": pezzi, "N": len(tagli)}, ["Read"])
    try:
        scelte = primo_json(testo)
    except ValueError:
        return [None] * len(tagli)
    return [centro(v, n - 1) if isinstance(n, int) and 1 <= n <= len(v) else None for v, n in zip(facce, list(scelte) + [None] * len(tagli))]


def monta_clip(c, live, ident, k, analisi, lav, cwd, t0, etichetta=""):
    """Monta una clip scelta, la registra nel database e (se richiesto) la copia sul Desktop. Restituisce il file o None."""
    file = QUI / "clip" / str(live["id"]) / f"{ident}.mp4"
    file.parent.mkdir(parents=True, exist_ok=True)
    L = inquadra(live, analisi["sorgente"], k["inizio"], k["fine"], lav, cwd)
    if k.get("tagli") and L["tipo"] == "fascia":  # storia: a tutto schermo stretto sulla faccia, che il montaggio segue pezzo per pezzo;
        L = {"tipo": "pieno", "cx": L.get("cx", 960), "cy": 560, "stretto": 1.05, "cx_max": 1300}  # cy/stretto: via il contatore in alto; cx_max: via la chat a destra
        try:
            L["cx_tagli"] = chi_parla(live, analisi["sorgente"], k["tagli"], analisi["frasi"], lav, cwd)  # il montatore segue chi parla, pezzo per pezzo
        except (subprocess.SubprocessError, OSError, ValueError, KeyError) as e:
            print(f"  chi parla: non letto ({type(e).__name__}), si segue la faccia più grande", flush=True)
    scheda = {"id": ident, "sorgente": analisi["sorgente"], "layout": L, "titolo": k["_titolo"], "didascalia": k["_didascalia"], "storia": k["_perche"], "firma": CONFIG["firma"], "uscita": str(file), **{a: b for a, b in k.items() if a[0] != "_"}}
    # Lo stile si cambia con "stile" in config.json: "classico" (monta.py) o "speedy" (laboratorio/monta.py, lo stesso montaggio con in più
    # lo stile Speedy). In speedy una clip buona non si perde per un effetto: scheda completa, poi senza i campi dello stile, infine classico.
    nuda = {a: b for a, b in scheda.items() if a not in CAMPI_SPEEDY}
    prove = [(QUI / "laboratorio/monta.py", {**scheda, "stile": "speedy"}), (QUI / "laboratorio/monta.py", {**nuda, "stile": "speedy"}), (QUI / "monta.py", nuda)] \
        if CONFIG.get("stile") == "speedy" else [(QUI / "monta.py", scheda)]
    for montatore, sch in prove:
        (lav / f"{ident}.json").write_text(json.dumps(sch, ensure_ascii=False, indent=1))
        r = subprocess.run(["python3", "-I", montatore, lav / f"{ident}.json"], capture_output=True, text=True, timeout=1200, cwd=cwd)  # cwd = cartella dei blocchi: "concat:" ha percorsi relativi
        if not r.returncode:
            break
        print(f"  montaggio fallito ({montatore.parent.name}, stile {sch.get('stile', 'classico')}): {r.stderr[-200:]}", flush=True)
    print(ident, *re.findall(r"tempi: .*|parole sicure.*|parole tolte.*|controllo di coerenza.*|effetto saltato.*|freccia.*|inizio fermo.*", r.stderr), sep="\n  ", flush=True)
    if r.returncode:
        evento(c, "errore", f"montaggio {ident} fallito: {r.stderr[-300:]}")
        return None
    # controllo qualità: ogni casella spuntata, altrimenti la clip resta fuori dalla coda di pubblicazione (e dal Desktop)
    q = subprocess.run([str(VE / ".venv/bin/python"), "-I", str(QUI / "qualita.py"), str(lav / f"{ident}.json")], capture_output=True, text=True, timeout=900)
    try:
        mancano = [f"{x['nome']} ({x['nota']})" for x in json.loads(q.stdout)["caselle"] if not x["ok"]]
    except (ValueError, KeyError):
        mancano = [f"il controllo non ha risposto ({q.stderr[-200:]})"]
    print("  controllo qualità:", "; ".join(mancano) or "tutte le caselle spuntate", flush=True)
    shutil.rmtree(QUI / "lavoro" / ident, ignore_errors=True)  # file di lavoro: mezzo giga a clip
    shutil.rmtree(QUI / "laboratorio/lavoro" / ident, ignore_errors=True)
    buona = k.get("_promossa", True) and not mancano
    if buona and CONFIG.get("copia_sul_desktop"):  # Riccardo vuole vedere le clip appena escono
        cartella = Path.home() / "Desktop" / "Clip Farm"  # cartella apposta, chiesta da Riccardo l'11 nov: non più sparse sul Desktop
        cartella.mkdir(exist_ok=True)
        shutil.copy(file, cartella / f"{nome(etichetta + live['streamer'] + ' - ' + k['_titolo'])}.mp4")
    c.execute("insert into clip (live, titolo, didascalia, inizio, fine, file, creato, perche, stato) values (?,?,?,?,?,?,?,?,?)",
              (live["id"], k["_titolo"], k["_didascalia"], t0 + k["inizio"], t0 + k["fine"], str(file), time.time(),
               k["_perche"] + (" — BOCCIATA DAL CONTROLLO QUALITÀ: " + "; ".join(mancano) if mancano else " — controllo qualità superato"), "montata" if buona else "scartata"))
    if mancano:
        evento(c, "clip bocciata", f"{live['streamer']}: {k['_titolo']} — {'; '.join(mancano)}"[:600])
        return None
    evento(c, "clip montata", f"{live['streamer']}: {k['_titolo']}")
    return file


def lavora(c, live, d, blocco, ultimo):
    n = int(blocco.stem[2:])
    prec = d / f"b_{n - 1:05d}.ts"
    lav = QUI / "lavoro" / f"live{live['id']}"
    lav.mkdir(parents=True, exist_ok=True)
    chat = d / "chat.jsonl"
    cmd = [VE / ".venv/bin/python", "-I", QUI / "analizza.py", *(["--chat", chat] if chat.exists() else []), *(["--ultimo"] if ultimo else []),
           *([prec] if prec.exists() else []), blocco]
    t0 = time.time()
    analisi = json.loads(subprocess.run([str(x) for x in cmd], capture_output=True, text=True, check=True, timeout=900).stdout)
    print(f"{time.strftime('%H:%M:%S')} live {live['id']} blocco {n}: analisi {time.time() - t0:.0f} s, picchi {analisi['picchi']}", flush=True)
    (lav / f"analisi_{n}.json").write_text(json.dumps(analisi, ensure_ascii=False, indent=1))
    scelte = []
    for k in seleziona(analisi, live) if analisi["frasi"] else []:  # dal più forte: ci si ferma appena le clip promosse bastano
        if len(scelte) < CONFIG["max_clip_per_blocco"] and (v := giudica(k, analisi, live, lav)):
            scelte.append(v)
    # tempi sulla live: il blocco n parte a n*blocco_secondi, l'analisi parte dal precedente quando c'è
    t0 = (n - (1 if prec.exists() else 0)) * CONFIG["blocco_secondi"]
    for i, k in enumerate(scelte):
        monta_clip(c, live, f"live{live['id']}_b{n}_{i}", k, analisi, lav, d, t0)
    if not CONFIG["tieni_blocchi"]:
        prec.unlink(missing_ok=True)  # il precedente non serve più; questo serve ancora al prossimo giro
        if ultimo:
            blocco.unlink()


def vecchie(righe, ora, giorni=2):
    """I file da togliere: clip già pubblicate o scartate da più di `giorni` giorni, con la loro copia leggera per il caricamento.
    Le clip in coda non si toccano; le copie sul Desktop nemmeno. Senza, 12 MB a clip riempiono il disco in una settimana."""
    return [f for k in righe if k["stato"] in ("pubblicata", "scartata") and k["file"] and ora - k["creato"] > giorni * 86400
            for f in (Path(k["file"]), Path(k["file"]).with_name(Path(k["file"]).stem + "_web.mp4"))]


def giro():
    c = db()
    for d in sorted(p for p in REG.iterdir() if p.name.isdigit()) if REG.exists() else []:
        if not CONFIG["tieni_blocchi"] and (d / "FINE").exists() and time.time() - (d / "FINE").stat().st_mtime > 3 * 3600:
            for b in d.glob("b_*.ts"):  # 12/11: blocchi di live finite rimasti (errore o catena in ritardo): 6 GB sul disco
                b.unlink()
        live = c.execute("select * from live where id=?", (int(d.name),)).fetchone()
        if not live:
            continue
        pronti = chiusi(d)
        nuovi = [b for b in pronti if not c.execute("select 1 from blocco where live=? and n=?", (live["id"], int(b.stem[2:]))).fetchone()]
        for b in nuovi[:-2]:  # arretrato: una clip vecchia di mezz'ora non serve, meglio restare sul presente
            c.execute("insert into blocco (live, n, stato) values (?,?,'saltato')", (live["id"], int(b.stem[2:])))
            if not CONFIG["tieni_blocchi"] and b != nuovi[-3]:  # il più recente dei saltati fa ancora da "precedente"
                b.unlink()
        if nuovi[:-2]:
            evento(c, "arretrato", f"{live['streamer']}: saltati {len(nuovi) - 2} blocchi, la catena era indietro")
        for b in nuovi[-2:]:
            n = int(b.stem[2:])
            c.execute("insert into blocco (live, n, stato) values (?,?,'in corso')", (live["id"], n))
            c.commit()
            try:
                lavora(c, live, d, b, ultimo=(d / "FINE").exists() and b == pronti[-1])
                stato = "fatto"
            except Exception as e:  # un blocco andato male non ferma la live: si segnala e si passa al prossimo
                stato = "errore"
                evento(c, "errore", f"blocco {n} di {live['streamer']}: {type(e).__name__}: {str(e)[-300:]}")
            c.execute("update blocco set stato=? where live=? and n=?", (stato, live["id"], n))
            c.commit()


def folla(c):
    """Ogni 20 minuti, per ogni live che si sta registrando: le clip nuove più viste fatte dagli spettatori, rimontate
    nel nostro stile (ripassa.py). È il segnale più forte che c'è: il momento l'ha già scelto e guardato la folla."""
    for live in c.execute("select * from live where fine is null and registrata=1 and piattaforma in ('twitch','kick')").fetchall():
        if time.time() - (kv(c, f"folla:{live['id']}") or 0) < 1200:
            continue
        kv(c, f"folla:{live['id']}", time.time())
        r = subprocess.run([str(VE / ".venv/bin/python"), "-I", str(QUI / "ripassa.py"), "--" + live["piattaforma"], live["url"].rsplit("/", 1)[-1], live["streamer"],
                            str(CONFIG["max_clip_per_blocco"] * 2), "day", "--live", str(live["id"])], capture_output=True, text=True, timeout=1800)
        print(f"{time.strftime('%H:%M:%S')} folla {live['streamer']}:", *[x for x in (r.stdout + r.stderr).splitlines() if "POC" not in x][-6:], sep="\n  ", flush=True)


if __name__ == "__main__":
    a = {"zona": [575, 1175], "durata": 1200}
    _st = {"titolo": "x", "inizio": 0, "fine": 0, "clou": 610, "tagli": [[600, 604], [610, 616.5], [650, 655], [700, 707]]}
    _v = valida(_st, a)
    assert _v and _v["inizio"] == 600 and _v["fine"] == 707 and _v["tagli"][1] == [610, 616.5] and _v["parole_blocco"] == 4, _v
    _v = valida({**_st, "lampi": [{"t": "thousand@19", "colore": "#00ff3c"}, {"t": 12, "colore": "#00ff3c"}], "zoom": [{"t": 3}]}, a)
    assert _v["lampi"] == [{"t": "thousand", "colore": "#00ff3c"}] and _v["zoom"] == [], _v
    assert storia_da([[600, 600.5], [610, 620]], 1200) is None and storia_da([[0, 5], [300, 310]], 1200) is None and storia_da("x", 9) is None
    buona = {"titolo": "x", "inizio": 600, "fine": 620, "clou": 615, "enfasi": {"shit": "magenta", "bro": "verde"}, "suoni": [{"t": 0, "file": "ding_1.m4a"}, {"t": 1, "file": "../../x"}], "musica": "non-esiste.m4a"}
    _s = speedy_campi({"colori": {"money": "giallo", "x": "fucsia"}, "finale": {"testo": "he lost it", "colore": "boh"}, "narrazioni": [{"t": 3, "testo": "laughing"}, {"testo": "senza tempo"}],
                       "freccia": {"chi": "sopra", "testo": "X"}, "vibe": "allegro"})
    assert _s == {"colori": {"money": "giallo"}, "finale": {"testo": "HE LOST IT", "emoji": "😂", "colore": "verde"}, "narrazioni": [{"t": 3, "durata": 2.0, "testo": "LAUGHING"}]}, _s
    assert speedy_campi({}) == {} and speedy_campi({"freccia": {"chi": "sinistra", "testo": "Big Smoke"}, "vibe": "serio"}) == {"freccia": {"t": 0.3, "durata": 2.3, "chi": "sinistra", "testo": "BIG SMOKE"}, "vibe": "serio"}
    v = valida(buona, a)
    assert v and v["enfasi"] == {"shit": "magenta"} and [x["file"] for x in v["suoni"]] == ["ding_1.m4a"] and "musica" not in v
    assert valida({**buona, "clou": 1190, "fine": 1195, "inizio": 1170}, a) is None  # clou fuori zona: si decide al prossimo giro
    assert valida({**buona, "fine": 700}, a) is None and valida({"titolo": "x"}, a) is None  # troppo lunga; campi mancanti
    D, F = {"tipo": "diviso", "facecam": [0, 264, 396, 222], "gioco_cx": 960}, {"tipo": "fascia", "cx": 960}
    assert layout_da({"facecam": [0, 177, 264, 148], "soggetto_cx": 640}) == D and layout_da({"facecam": None, "soggetto_cx": 400}) == F and layout_da(None) == F
    D2 = {**D, "facecam": [4, 270, 386, 212]}  # stessa webcam letta con qualche pixel di scarto: non è un cambio di scena
    assert tratti([D, D2, D, D, D2, D], [1, 2, 3, 4, 5, 6], None) == D
    assert layout_da({"facecam": None, "sottotitoli_y": 655}) == {**F, "utile": 974} and layout_da({"facecam": None, "sottotitoli_y": 100}) == F
    assert tratti([D, {**D, "utile": 974}, D, {**D2, "utile": 960}, D, D], [1, 2, 3, 4, 5, 6], None) == {**D, "utile": 960}
    assert tratti([D, D, D, F, F, D], [1, 2, 3, 4, 5, 6], lambda a, b, riquadro: a + 0.5 * (riquadro == D["facecam"])) == {"tipo": "misto", "tratti": [[1, D], [3.5, F], [5.5, D]]}
    assert primo_json('Ecco:\n```json\n[{"inizio": 1}]\n```\nSe non convince, la risposta giusta è `[]`.') == [{"inizio": 1}] and primo_json("niente: []") == []
    K = lambda stato, eta: {"stato": stato, "file": "/x/a.mp4", "creato": 1e6 - eta * 86400}
    assert [f.name for f in vecchie([K("pubblicata", 3), K("montata", 9), K("scartata", 1), K("scartata", 2.5)], 1e6)] == ["a.mp4", "a_web.mp4"] * 2
    assert promossa({"capibile": 9, "divertente": 8, "finale": 8}, 8) and not promossa({"capibile": 4, "divertente": 10, "finale": 10}, 8) and not promossa({"capibile": "?"}, 8)
    if "--inquadra" in sys.argv:  # prova: python3 -I catena.py --inquadra FILE INIZIO FINE
        print(inquadra({"streamer": "?"}, Path(sys.argv[2]).resolve(), float(sys.argv[3]), float(sys.argv[4]), QUI / "lavoro", QUI))
    elif "--prova" not in sys.argv:
        with uno_alla_volta("catena"):
            giro()
            folla(db())
            for f in vecchie(db().execute("select stato, file, creato from clip").fetchall(), time.time()):
                f.unlink(missing_ok=True)
