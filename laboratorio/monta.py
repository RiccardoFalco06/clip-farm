"""Monta una clip dalla scheda scritta dal selezionatore.

uso: python3 -I monta.py scheda.json   -> lavoro/<id>/finale.mp4 (e copia in `uscita` se indicata)
Passi: taglio e layout (ffmpeg) -> parole sincronizzate (script della skill animated-captions, MMS)
       -> sottotitoli, lampi, suoni, musica (Remotion, remotion/src/Clip.tsx).
"""
import array
import difflib
import functools
import hashlib
import http.server
import json
import math
import re
import shutil
import subprocess
import tempfile
import sys
import threading
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
RADICE = QUI.parent if QUI.name == "laboratorio" else QUI  # LAB: suoni, musica, riempitivi e trascrivi.py si leggono dal progetto vero
VE = Path.home() / "Projects/video-editor"  # progetto della skill dei sottotitoli
PRESET = json.loads((QUI / "remotion/presets.json").read_text())
# --- stile "speedy" (campo "stile" della scheda; "classico" = comportamento di sempre) ---
# colori misurati sugli Shorts di riferimento (riempimento e alone), vedi laboratorio/libreria.json
PALETTA = {"verde": {"fill": "#25fb06", "glow": "#00ff00"}, "lime": {"fill": "#98fb05", "glow": "#7dff00"}, "giallo": {"fill": "#f2fd06", "glow": "#ffe600"},
           "arancio": {"fill": "#f7e03a", "glow": "#ffb400"}, "rosso": {"fill": "#f70105", "glow": "#ff0000"}, "magenta": {"fill": "#f909f4", "glow": "#ff00ff"},
           "ciano": {"fill": "#66fcf9", "glow": "#00fff0"}, "biancoBordoRosso": {"glow": "#ff2a10", "edge": "#ff5a4a", "edgeW": 1.6}, "bianco": {},
           # campionati l'11/11 pomeriggio: rosa (sPS9 MY MOM, MATTER OF FACT; IUm COLOR), viola (X8F I NEED Y'ALL BOYS), corallo (X8F ALRIGHT), oro (X8F MAKE US LAUGH)
           "rosa": {"fill": "#ff2db8", "glow": "#ff1aa8"}, "viola": {"fill": "#9359eb", "glow": "#8a3cff"}, "corallo": {"fill": "#ee5464", "glow": "#ff3a4a"}, "oro": {"fill": "#f2cb36", "glow": "#ffc400"}}
# luce che lampeggia sopra il video, predefinita nello stile speedy: c'è in 31 Shorts 2025-2026 su 31 (vedi Effetti.tsx luceVideo); forza tarata con luce3.py
LUCE = {"forza": 0.09}
# vibe: valori predefiniti per tipo di clip, la scheda li può cambiare. "serio" misurato su 4Aj5Z8odhpc (attacco di panico):
# sottotitoli bianchi (colore solo per distinguere chi parla), niente lampi né emoji né finale, immagine desaturata (saturazione media 9,9 contro 15-25),
# niente luce che lampeggia (3,5 al secondo all'1,4% contro 10-14 al 3-7% delle clip giocose). Riccardo: "anche questi video seri sono sempre un'eccezione".
VIBE = {"serio": {"colori": {}, "enfasi": {}, "frasi_colorate": [], "lampi": [], "zoom": [], "effetti": [], "icone": [], "finale": None, "luce": False, "saturazione": 0.6}}
LAMPI_SPEEDY = {"#00ff3c": "#0fff0b", "#ff2a1a": "#ff0604"}  # i lampi del classico diventano i colori misurati (fusione "scolora")
COLORI = {"magenta": "#F506F5", "ciano": "#08D8F8"}  # misurati sulle clip di riferimento
CENSURA = {"fuck": "F*CK", "fucking": "F*CKING", "shit": "SH*T", "bitch": "B*TCH", "nigga": "N***A", "niggas": "N***AS", "ass": "A*S", "dick": "D*CK", "pussy": "P*SSY", "motherfucker": "MF", "motherfucking": "MF"}


def run(*cmd, cwd=None):
    subprocess.run([str(c) for c in cmd], check=True, cwd=cwd)


def lufs_pezzo(f, da, durata):
    """LUFS integrato di un pezzo di un file (None se troppo corto o muto)."""
    err = subprocess.run(["ffmpeg", "-nostdin", "-ss", str(max(0, da)), "-t", str(durata), "-i", str(f), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    v = re.findall(r"I:\s*(-?[\d.]+) LUFS", err)
    return float(v[-1]) if v and float(v[-1]) > -60 else None


# 12/11, agente audio: il pop si perde sotto la voce (+3 dB), boom e drop coprono (-1 dB)
PESO_SUONO = lambda f: 1.41 if "pop" in f.lower() else 0.89 if ("boom" in f.lower() or "bassdrop" in f.lower()) else 1.0


def lufs(f):
    """Volume percepito di un file audio (LUFS integrato)."""
    err = subprocess.run(["ffmpeg", "-nostdin", "-i", str(f), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s*(-?[\d.]+) LUFS", err)[-1])


def livelli(sorgente, da, durata):
    """Volume (dB) ogni 50 ms di un pezzo d'audio."""
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(da), "-t", str(durata), "-i", sorgente, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    a = array.array("h", pcm[: len(pcm) // 2 * 2])
    return [10 * math.log10(sum(x * x for x in a[i: i + 800]) / 800 + 1) for i in range(0, len(a) - 799, 800)]


def pausa(liv, ultima):
    """Centro (in passi da 50 ms) di una pausa del parlato, almeno 150 ms sotto soglia: l'ultima o la prima. None se non ce n'è."""
    if not liv or max(liv) - min(liv) < 10:
        return None
    soglia = min(liv) + 0.35 * (max(liv) - min(liv))
    pause, i = [], 0
    while i < len(liv):
        j = i
        while j < len(liv) and liv[j] < soglia:
            j += 1
        if j - i >= 3:
            pause.append((i + j) / 2)
        i = max(j, i + 1)
    return (pause[-1] if ultima else pause[0]) if pause else None


def aggancia(s):
    """Sposta inizio e fine sulla pausa più vicina. Chi sceglie il momento dà i tempi al secondo e da una trascrizione
    imprecisa: senza aggancio il taglio cadeva a metà frase (clip "I forgot where I was" che partiva da "was")."""
    lungo = float(subprocess.run(["ffprobe", "-v", "0", "-show_entries", "format=duration", "-of", "csv=p=0", s["sorgente"]], capture_output=True, text=True, check=True).stdout)
    da = max(0, s["inizio"] - 3.0)
    p = pausa(livelli(s["sorgente"], da, s["inizio"] + 0.3 - da), ultima=True)
    inizio = da + p * 0.05 if p is not None else max(0, s["inizio"] - 1.0)  # nessuna pausa: meglio un secondo in più che una parola mozza
    p = pausa(livelli(s["sorgente"], s["fine"] - 0.3, 2.8), ultima=False)
    fine = min(lungo, s["fine"] - 0.3 + p * 0.05 if p is not None else s["fine"] + 0.5)
    return round(inizio, 2), round(fine, 2)


def filtro(L, ing, usc, k="", y=None, A=1920):
    """Il pezzo di filtergraph che porta `ing` nel formato 1080x1920 `usc`, e l'altezza della giunzione dove sta la parola."""
    H = L.get("utile", 1080)  # sotto questa altezza ci sono i sottotitoli che lo streamer ha già nella sua live: restano fuori
    if L["tipo"] == "diviso":  # facecam sopra, gioco sotto: il layout delle clip di gioco di riferimento
        fx, fy, fw, fh = L["facecam"]
        if A == 1440:
            # speedy 3:4: due metà con riga bianca in mezzo (misurato su 6 Shorts: riga a 0,489-0,496 dell'altezza, spessa circa 6 px)
            fw2 = min(fw, round(fh * 1080 / 704 / 2) * 2)  # la webcam 16:9 si stringe ai lati per riempire la metà alta
            gw = round(1080 * H / 730 / 2) * 2
            gx = min(max(0, L.get("gioco_cx", 960) - gw // 2), 1920 - gw)
            return (f"{ing}split[a{k}][b{k}];[a{k}]crop={fw2}:{fh}:{fx + (fw - fw2) // 2}:{fy},scale=1080:704:flags=lanczos,pad=1080:710:0:0:white[t{k}];"
                    f"[b{k}]crop={gw}:{H}:{gx}:0,scale=1080:730:flags=lanczos[g{k}];[t{k}][g{k}]vstack{usc}"), 704
        alto = round(1080 * fh / fw / 2) * 2
        basso = A - alto
        gw = round(1080 * H / basso / 2) * 2  # larghezza del gioco che riempie la parte bassa a tutta altezza
        gx = min(max(0, L.get("gioco_cx", 960) - gw // 2), 1920 - gw)
        return (f"{ing}split[a{k}][b{k}];[a{k}]crop={fw}:{fh}:{fx}:{fy},scale=1080:{alto}:flags=lanczos[t{k}];"
                f"[b{k}]crop={gw}:{H}:{gx}:0,scale=1080:{basso}:flags=lanczos[g{k}];[t{k}][g{k}]vstack{usc}"), alto
    if L["tipo"] == "riempitivo":
        # due riquadri orizzontali impilati: video principale sopra, riempitivo muto sotto (misure dagli Shorts: giunzione a 0,55-0,57)
        alto = round(A * L.get("quota", 0.56) / 2) * 2
        basso = A - alto
        cw = round(H * 1080 / alto / 2) * 2
        cx = min(max(0, L.get("cx", 960) - cw // 2), 1920 - cw)
        return (f"{ing}crop={cw}:{H}:{cx}:0,scale=1080:{alto}:flags=lanczos[t{k}];"
                f"[1:v]fps=30,scale=-2:{basso}:flags=lanczos,crop=1080:{basso}[g{k}];[t{k}][g{k}]vstack{usc}"), alto
    if L["tipo"] == "fascia":  # live senza webcam: fascia larga al centro su sfondo sfocato, così il soggetto non esce mai dal ritaglio
        cw = 1216
        cx = min(max(0, L.get("cx", 960) - cw // 2), 1920 - cw)
        # parola appena sopra la fascia: sotto ci sono spesso i sottotitoli che lo streamer ha già nella sua live
        if A == 1440:
            y = (A - round(1080 * H / cw / 2) * 2) // 4 * 2  # speedy 3:4: fascia centrata, la scritta ci passa sopra a metà altezza
        elif y is None:
            y = 480
        return (f"{ing}split[a{k}][b{k}];[a{k}]scale=-2:{A},crop=1080:{A},boxblur=24:4,eq=brightness=-0.12[s{k}];"
                f"[b{k}]crop={cw}:{H}:{cx}:0,scale=1080:{round(1080 * H / cw / 2) * 2}:flags=lanczos[f{k}];[s{k}][f{k}]overlay=0:{y}{usc}"), y - 72
    # pieno: il soggetto riempie lo schermo (30 Short su 30 sopra il milione, ricerca del 12/11). "stretto" > 1 stringe sul volto, "cy" ne dice l'altezza
    ch = round(1080 / max(1.0, L.get("stretto", 1.0)) / 2) * 2
    cw = round(ch * 1080 / A / 2) * 2  # 608 a 9:16, 810 a 3:4 senza stretto
    cx = min(max(0, L.get("cx", 960) - cw // 2), 1920 - cw)
    cy = min(max(0, L.get("cy", 540) - ch // 2), 1080 - ch)
    return f"{ing}crop={cw}:{ch}:{cx}:{cy},scale=1080:{A}:flags=lanczos{usc}", None  # shortcut: il pieno non toglie i sottotitoli dello streamer


def grafo(L, inizio, A=1920):
    """Filtergraph di tutta la clip. Layout "misto" (la scena cambia a metà, es. webcam che va a schermo intero): ogni tratto
    col suo layout, sovrapposto al primo solo nei suoi secondi; la fascia scende sotto la giunzione così la parola resta dov'è."""
    if L["tipo"] != "misto":
        vf, giunzione = filtro(L, "[0:v]fps=30,", "[v]", A=A)
        return vf, giunzione
    tratti = L["tratti"]  # [[da (secondi della sorgente), layout], ...]: il primo vale dall'inizio
    giunzione = next((filtro(l, "", "", A=A)[1] for _, l in tratti if l["tipo"] == "diviso"), round(408 * A / 1920))
    y = min(giunzione + 72, 960)
    pezzi = [f"[0:v]fps=30,split={len(tratti)}" + "".join(f"[i{k}]" for k in range(len(tratti)))]
    pezzi += [filtro(l, f"[i{k}]", f"[o{k}]", k, y, A)[0] for k, (_, l) in enumerate(tratti)]
    for k in range(1, len(tratti)):
        fino = f"*lt(t,{tratti[k + 1][0] - inizio:.3f})" if k + 1 < len(tratti) else ""
        pezzi.append(f"[{'o0' if k == 1 else f'm{k - 1}'}][o{k}]overlay=enable='gte(t,{tratti[k][0] - inizio:.3f}){fino}'" + ("[v]" if k + 1 == len(tratti) else f"[m{k}]"))
    return ";".join(pezzi), giunzione


def layout(s, dst, A=1920):
    """Ritaglia la sorgente nel formato finale 1080xA (1920 classico, 1440 speedy 3:4)."""
    # rincorsa di 4 s, poi scartata: come nel monta.py vivo (su Kick il video della base cominciava fino a 1,9 s dopo l'audio e la clip partiva ferma)
    da = max(0, s["inizio"] - 4.0)
    vf, giunzione = grafo(s["layout"], da, A)
    L = s["layout"]
    riemp = ["-ss", L.get("da", 0), "-t", s["fine"] - da, "-i", RADICE / L["video"]] if L["tipo"] == "riempitivo" else []  # secondo ingresso: il filmato riempitivo, muto
    run("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", da, "-i", s["sorgente"], *riemp,
        "-filter_complex", vf, "-map", "[v]", "-map", "0:a", "-ss", round(s["inizio"] - da, 3), "-t", s["fine"] - s["inizio"],
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", dst)
    return giunzione


def storia(s, dst, fps=30):
    """Montaggio a storia: i tratti di "tagli" ([[da, a], ...] in secondi della sorgente, nell'ordine in cui vanno visti) uniti con
    stacchi secchi in un solo file, che poi si monta come una clip normale. Ricerca del 12/11 (laboratorio/ricerca/): i Short sopra il
    milione tolgono i tempi morti e tengono le frasi intere (TRG58mooOps: 77 s di sorgente in 31 s). Restituisce la durata.
    Ogni tratto ha esattamente N fotogrammi e N/fps secondi d'audio non compresso: il 12/11, con pezzi AAC uniti a copia, il video
    era un fotogramma più lungo dell'audio a ogni tratto (più il ritardo dell'encoder) e a fine clip voce e bocca erano sfasate."""
    pezzi, totale = [], 0
    # voce allo stesso livello in ogni tratto (12/11, agente audio: salti di 7-15 dB tra tratti, il fan al telefono incomprensibile)
    guadagni = [0.0] * len(s["tagli"])
    if (v := s.get("_voce")):
        liv = [lufs_pezzo(v[0], a - v[1], b - a) for a, b in s["tagli"]]
        if (validi := sorted(x for x in liv if x is not None)):
            meta = validi[len(validi) // 2]
            guadagni = [0.0 if x is None else round(min(15.0, max(-9.0, meta - x)), 1) for x in liv]
            print("voce per tratto (LUFS):", liv, "guadagni dB:", guadagni, file=sys.stderr)
    for k, (a, b) in enumerate(s["tagli"]):
        assert b > a, (a, b)
        p = dst.with_name(f"tratto{k}.mkv")
        da = max(0, a - 4.0)  # rincorsa scartata, come in layout(): su Kick il video partiva dopo l'audio
        x = round((a - da) * fps) / fps  # inizio sul passo dei fotogrammi
        n = max(1, round((b - a) * fps))
        sfuma = s.get("_sfuma_da", 1e9) - totale  # sotto il finale la voce della live sfuma in 0,4 s
        coda = f",afade=t=out:st={sfuma:.3f}:d=0.25" if 0 <= sfuma < n / fps else ""
        run("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", da, "-t", round(x + n / fps + 1, 3), "-i", s["sorgente"],
            "-vf", f"fps={fps},scale=1920:1080,trim=start={x:.4f},setpts=PTS-STARTPTS,trim=end_frame={n}",
            "-af", f"aresample=48000,volume={guadagni[k]}dB,atrim=start={x:.4f},asetpts=PTS-STARTPTS,apad,atrim=end_sample={round(n / fps * 48000)},"
                   f"afade=t=in:d=0.015,afade=t=out:st={n / fps - 0.025:.4f}:d=0.025{coda}",  # niente click allo stacco
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-c:a", "pcm_s16le", p)
        pezzi.append(p)
        totale += n / fps
    lista = dst.with_name("tratti.txt")
    lista.write_text("".join(f"file '{p}'\n" for p in pezzi))
    run("ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", dst)
    return round(totale, 3)


def stacchi(tagli, w, voce, da=0.0):
    """Sposta ogni stacco sul silenzio vero più vicino, senza mai entrare in una parola tenuta (12/11: frasi mozzate perché gli stacchi
    venivano dai tempi della trascrizione). `w` = parole sulla sorgente (start/end dal secondo `da`), `voce` = file con la sola voce,
    sugli stessi tempi delle parole. Inizio: l'ultimo tratto quieto prima della prima parola; fine: il primo quieto dopo l'ultima."""
    ws = sorted(({"s": da + x["start"], "e": da + x.get("end", x["start"]), "show": x.get("show", ""), "dubbia": dubbia(x)} for x in w), key=lambda x: x["s"])
    for x, y in zip(ws, ws[1:]):
        if x["dubbia"]:  # 12/11 "$10,000": l'allineatore lavora sulle lettere, i numeri li piazza a caso (punteggio 0) e "thousand" fu mozzato
            x["e"] = max(x["e"], y["s"] - 0.05)
    out = []
    for a, b in tagli:
        dentro = [x for x in ws if a - 0.05 <= x["s"] < b]
        if not dentro:
            out.append([a, b])
            continue
        prima = max((x["e"] for x in ws if x["s"] < dentro[0]["s"]), default=min(a, dentro[0]["s"]) - 0.6)
        dopo = min((x["s"] for x in ws if x["s"] > dentro[-1]["s"] and x not in dentro), default=max(b, dentro[-1]["e"]) + 0.6)
        # un margine chiesto apposta (scena muta prima, reazione o finale dopo) resta: si cerca il silenzio solo intorno al punto chiesto
        # 12/11, agente tagli: lo spostamento sul silenzio non allarga mai la pausa di più di 0,35 s per lato (si sentivano buchi di 1 s)
        lo, hi = (max(prima, a - 0.3), min(dentro[0]["s"] - 0.02, a + 0.3)) if a < dentro[0]["s"] - 0.6 else (max(prima, dentro[0]["s"] - 0.35), dentro[0]["s"] - 0.02)
        na = lo if hi - lo < 0.06 else quieto(voce, lo - da, hi - da, ultimo=True) + da
        lo, hi = (max(dentro[-1]["e"] + 0.02, b - 0.3), min(dopo, b + 0.3)) if b > dentro[-1]["e"] + 0.6 else (dentro[-1]["e"] + 0.02, min(dopo, dentro[-1]["e"] + 0.35))
        nb = hi if hi - lo < 0.06 else quieto(voce, lo - da, hi - da, ultimo=False) + da
        if dentro[-1]["dubbia"]:  # fine vera di un numero: il primo silenzio dopo il suo inizio, prima della parola successiva
            nb = quieto(voce, dentro[-1]["s"] + 0.25 - da, max(dentro[-1]["s"] + 0.35, dopo - 0.02) - da, ultimo=False) + da
        if (i := ws.index(dentro[-1])) + 1 < len(ws) and not re.search(r"[.!?]$", dentro[-1]["show"].strip()) and ws[i + 1]["s"] - dentro[-1]["e"] < 0.5:
            print(f"ATTENZIONE frase interrotta: il tratto {a}-{b} finisce su {dentro[-1]['show']!r} e la frase continua con {ws[i + 1]['show']!r}", file=sys.stderr)
        out.append([round(na, 3), round(max(nb, na + 0.2), 3)])
    return out


def inquadra_tratti(s, A):
    """Layout pieno che segue la faccia tratto per tratto (12/11, agente inquadratura: con un centro fisso Kai usciva dal bordo).
    Per ogni taglio 3 fotogrammi della sorgente, la faccia più grande, mediana del centro; senza facce resta il centro della scheda.
    Restituisce un layout "misto" con i tempi della storia, o quello di partenza se tutti i tratti hanno lo stesso centro."""
    L = {k: v for k, v in s["layout"].items() if k != "cx_tagli"}
    # cx_tagli (catena.chi_parla, 13 nov): per ogni pezzo il centro della faccia di chi parla; dove manca, la faccia più grande come prima
    parla = s["layout"].get("cx_tagli") or []
    parla = parla if len(parla) == len(s["tagli"]) else []
    ch = 1080 / max(1.0, L.get("stretto", 1.0))
    meta = ch * 1080 / A / 2
    tratti, t, prec = [], 0.0, None
    for i, (a, b) in enumerate(s["tagli"]):
        xs = [parla[i]] if parla and parla[i] is not None else []
        for f in (0.2, 0.5, 0.8) if not xs else ():
            facce = trova_volti(s["sorgente"], a + (b - a) * f)
            if facce:
                x, y, w, h = max(facce, key=lambda v: v[2] * v[3])
                xs.append(x + w / 2)
        cx = round(sorted(xs)[len(xs) // 2]) if xs else L.get("cx", 960)
        cx = round(min(max(cx, meta), 1920 - meta, L.get("cx_max", 1920)))  # cx_max: oltre entra la chat della live (12/11)
        if prec is not None and abs(cx - prec) < 120:  # piccoli spostamenti: niente scatto (84 px dentro la stessa ripresa si vedeva)
            cx = prec
        if cx != prec:
            tratti.append([round(t, 3), {**L, "cx": cx}])
        prec, t = cx, t + b - a
    print("inquadratura per tratto (secondo della storia, cx):", [(x[0], x[1]["cx"]) for x in tratti], file=sys.stderr)
    return tratti[0][1] if len(tratti) == 1 else {"tipo": "misto", "tratti": tratti}


def lontani_dagli_stacchi(lampi, tagli, aria=0.4):
    """Un lampo a meno di `aria` secondi da uno stacco passa a `aria` dopo lo stacco (12/11, agente ritmo: stacco, blocco e lampo insieme)."""
    stacchi, t = [], 0.0
    for a, b in (tagli or [])[:-1]:
        t += b - a
        stacchi.append(t)
    out = []
    for l in lampi:
        vicino = [c for c in stacchi if abs(l["t"] - c) < aria]
        out.append({**l, "t": round(vicino[0] + aria, 3)} if vicino else l)
    return out


def dubbia(x):
    """Parola il cui tempo l'allineatore non sa dare: senza lettere ("$10", ",000", "21") o con punteggio esattamente 0 (interpolata)."""
    return not re.search(r"[A-Za-z]", x.get("show", "")) or x.get("score") == 0


def quieto(voce, a, b, ultimo):
    """Secondo (centro di una finestra da 50 ms) più quieto tra a e b: fra quelle entro 3 dB dal minimo, l'ultima o la prima."""
    liv = livelli(str(voce), max(0, a), b - max(0, a))
    if not liv:
        return a if ultimo else b
    zitti = [i for i, v in enumerate(liv) if v <= min(liv) + 3]
    i = zitti[-1] if ultimo else zitti[0]
    return max(0, a) + (i + 0.5) * 0.05


def sposta_parole(w, tagli, da):
    """Parole trascritte sulla sorgente (da `da` in poi) portate sui tempi della storia: restano solo quelle intere dentro un taglio."""
    out, offset = [], 0.0
    for a, b in tagli:
        for x in w:
            if a - 0.05 <= da + x["start"] < b and da + x.get("end", x["start"]) <= b + 0.15:
                out.append({**x, "start": round(offset + da + x["start"] - a, 3), "end": round(min(b, da + x.get("end", x["start"])) - a + offset, 3)})
        offset += b - a
    return out


def parole_sorgente(s, d):
    """Parole e voce isolata della sorgente intorno ai tagli: (parole, file voce, secondo della sorgente da cui contano).
    Whisper sul tratto intero col contesto e non sulla storia già tagliata, dove saltava battute ("What?!", "I found God" il 12/11).
    "parole_da": {"file", "da"} = parole già trascritte (in catena: quelle del blocco visto dal selezionatore), con vocals.wav accanto."""
    if (pd := s.get("parole_da")):
        f = Path(pd["file"]).expanduser()
        return json.loads(f.read_text()), f.with_name("vocals.wav"), pd.get("da", 0)
    da, a = max(0, min(x for x, _ in s["tagli"]) - 1.0), max(y for _, y in s["tagli"]) + 1.0
    f = d / "fonte"
    f.mkdir(exist_ok=True)
    run("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", da, "-i", s["sorgente"], "-t", round(a - da, 3), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "192k", f / "fonte.mp4")
    return parole(f / "fonte.mp4", f, coerenza=False), f / "vocals.wav", da


def riallinea(base, d, attese):
    """Tempi delle parole presi sull'audio finale della storia, col testo già noto (12/11: sottotitoli in anticipo sulla voce).
    Dove l'allineatore si allontana più di 0,5 s dal tempo atteso (urla, voci sovrapposte) resta quello atteso."""
    if not attese:
        return []
    py, pya = VE / ".venv/bin/python", VE / ".venv-align/bin/python"
    run(pya, "-I", "scripts/extract_audio.py", base, d, cwd=VE)
    # Whisper da capo sull'audio finale, senza controllo di coerenza (toglieva ripetizioni vere): serve a togliere i cicli della trascrizione
    # della live PRIMA dell'allineamento (12/11: 4 copie forzate su un audio che ne ha 2 sballavano tutti i tempi) e a riempire i buchi dopo
    run(py, "-I", RADICE / "trascrivi.py", d, "--senza-coerenza")
    asr = json.loads((d / "whisper.json").read_text()).get("words", [])
    attese = senza_cicli(attese, asr)
    righe, r = [], []
    for x in attese:
        r.append(x["show"])
        if x["show"].strip()[-1:] in ".!?":
            righe.append(" ".join(r)); r = []
    (d / "transcript.txt").write_text("\n".join(righe + ([" ".join(r)] if r else [])) + "\n")
    run(pya, "-I", "scripts/align.py", d / "vocals.wav", d / "transcript.txt", "eng", d / "align.json", cwd=VE)
    run(pya, "-I", "scripts/refine.py", d / "vocals.wav", d / "align.json", d / "words.json", "--fps", "30", cwd=VE)
    w = json.loads((d / "words.json").read_text())
    if len(w) != len(attese):
        print(f"riallineo: {len(w)} parole contro {len(attese)} attese, tengo i tempi attesi", file=sys.stderr)
        out = [dict(x) for x in attese]
    else:
        out = [x if abs(x["start"] - y["start"]) <= 0.5 else {**x, "start": y["start"], "end": y["end"]} for x, y in zip(w, attese)]
        print(f"riallineo: {sum(abs(x['start'] - y['start']) > 0.5 for x, y in zip(w, attese))} parole lasciate al tempo atteso, "
              f"scarto medio {sum(abs(x['start'] - y['start']) for x, y in zip(out, attese)) / len(out):.2f} s", file=sys.stderr)
    for x, y in zip(out, out[1:]):  # 12/11, agente sincronia: "THIS" compariva prima di "JUST"; una parola non parte mai prima della precedente
        if y["start"] < x["start"]:
            y["start"] = x["start"] + 0.02
    # parlato senza sottotitolo ("see what happens" saltato dalla trascrizione della live): le parole dell'audio finale nei buchi di 0,6 s
    return aggiungi_nei_buchi(out, asr, 0.6)


def senza_cicli(w, asr):
    """Cicli di Whisper sulla sorgente (12/11: "Who are you today?" scritto 4 volte, detto 2): una frase ripetuta di fila resta tante volte
    quante la sente la trascrizione indipendente dell'audio finale; le copie in più (le ultime) si tolgono."""
    k = lambda x: re.sub(r"[^\w]", "", x).lower()
    seq, sentite = [k(x["show"]) for x in w], [k(x["text"]) for x in asr]
    via, i = set(), 0
    while i < len(seq):
        for n in range(6, 1, -1):
            frase = seq[i:i + n]
            if len(frase) < n:
                continue
            volte = 1
            while seq[i + volte * n: i + (volte + 1) * n] == frase:
                volte += 1
            if volte > 1:
                a, b = w[i]["start"] - 1.5, w[i + volte * n - 1]["start"] + 1.5
                vicino = [x for x, y in zip(sentite, asr) if a <= y["start"] <= b]
                udite = sum(vicino[j:j + n] == frase for j in range(len(vicino)))
                if 0 < udite < volte:  # sentita 0 volte: l'audio finale l'ha persa, non è una prova contro
                    via |= set(range(i + max(1, udite) * n, i + volte * n))
                    print(f"ciclo di Whisper: '{' '.join(frase)}' scritto {volte} volte, sentito {udite}: tolte le copie in più", file=sys.stderr)
                i += volte * n - 1
                break
        i += 1
    return [x for j, x in enumerate(w) if j not in via]


def aggiungi_nei_buchi(w, asr, buco=0.6):
    w = sorted(w, key=lambda x: x["start"])
    confini = [(-1.0, w[0]["start"] if w else 1e9)] + [(a.get("end", a["start"]), b["start"]) for a, b in zip(w, w[1:])] + ([(w[-1].get("end", w[-1]["start"]), 1e9)] if w else [])
    nuove = [{"show": g["text"].strip(), "text": g["text"].strip(), "start": round(g["start"], 3), "end": round(max(g["end"], g["start"] + 0.1), 3), "da_asr": True}
             for g in asr if g.get("text", "").strip() and any(a + 0.15 <= g["start"] and g["end"] <= b - 0.1 and b - a >= buco for a, b in confini)]
    if nuove:
        print(f"buchi riempiti con {len(nuove)} parole sentite nell'audio finale:", " ".join(x["show"] for x in nuove), file=sys.stderr)
    return sorted(w + nuove, key=lambda x: x["start"])


def controlla_stacchi(voce, tagli):
    """Avvisa se a uno stacco la voce è ancora alta (parola mozzata): livello nei 50 ms prima e dopo lo stacco contro il parlato della clip."""
    liv = livelli(str(voce), 0, sum(b - a for a, b in tagli) + 1)
    if not liv:
        return []
    soglia = sorted(liv)[len(liv) // 4] + 0.5 * (max(liv) - sorted(liv)[len(liv) // 4])
    t, male = 0.0, []
    for a, b in tagli[:-1]:
        t += b - a
        i = round(t / 0.05)
        if max(liv[max(0, i - 1): i + 1] or [0]) > soglia:
            male.append(round(t, 2))
    if male:
        print(f"ATTENZIONE stacchi con voce ancora alta (parola forse mozzata) a {male} s", file=sys.stderr)
    return male


def fermi(video, minimo=0.5):
    """[(secondo, durata)] dei tratti in cui tutta l'immagine resta ferma almeno `minimo` secondi: anche gli scatti brevi.
    In una live c'è sempre qualcosa che si muove (webcam, chat): un fermo è un download o una registrazione rovinata, oppure
    fa parte della scena (lo streamer ha staccato tutto). Lo decide il controllo qualità (qualita.py).
    Soglia 0.0001 = fotogrammi identici: con 0.001 uno streamer immobile in posa contava come blocco (misurato: 4 falsi allarmi
    in una clip buona, 1 con 0.0001 e lungo 0,43 s; il download rovinato di Kick dà 3 fermi da 2 s con qualsiasi soglia)."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(video), "-vf", f"freezedetect=n=0.0001:d={minimo}", "-map", "0:v", "-f", "null", "-"], capture_output=True, text=True)
    return list(zip(map(float, re.findall(r"freeze_start: ([\d.]+)", r.stderr)), map(float, re.findall(r"freeze_duration: ([\d.]+)", r.stderr))))


def salto(f, entro=3.0):
    """Di quanti secondi spostare avanti l'inizio perché la clip parta in movimento: la fine dell'ultimo fermo che comincia
    nei primi `entro` secondi (0 = parte già in movimento). Riccardo: "assicurati che l'inizio sia sempre in movimento"."""
    return max((a + lungo for a, lungo in f if a < entro), default=0)


_UNI = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_DEC = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def in_lettere(n):
    """Intero in parole inglesi (fino ai miliardi)."""
    if n < 20:
        return _UNI[n]
    if n < 100:
        return _DEC[n // 10] + ("" if n % 10 == 0 else " " + _UNI[n % 10])
    for v, nome in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand"), (100, "hundred")):
        if n >= v:
            return in_lettere(n // v) + " " + nome + ("" if n % v == 0 else " " + in_lettere(n % v))


def numeri_detti(testo):
    """Cifre scritte come si dicono, per l'allineatore che lavora sulle lettere (12/11: "$10,000" piazzato a caso, "thousand" mozzato)."""
    def via(m):
        dollari, intero, dec, cento = m.group(1), int(m.group(2).replace(",", "")), m.group(3), m.group(4)
        out = in_lettere(intero) + (" point " + " ".join(_UNI[int(c)] for c in dec) if dec else "")
        return out + (" percent" if cento else "") + ((" dollar" if intero == 1 and not dec else " dollars") if dollari else "")
    testo = re.sub(r"(\d) ,(\d{3})\b", r"\1,\2", testo)  # Whisper scrive "$10 ,000"
    return re.sub(r"(\$)?\b(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(%)?(?![\w])", via, testo)


def parole(base, d, coerenza=True):
    """Parole con tempi precisi: voce isolata e allineamento della skill animated-captions (Demucs, MMS); testo da trascrivi.py."""
    py, pya = VE / ".venv/bin/python", VE / ".venv-align/bin/python"
    run(pya, "-I", "scripts/extract_audio.py", base, d, cwd=VE)
    run(py, "-I", RADICE / "trascrivi.py", d, *([] if coerenza else ["--senza-coerenza"]))
    grezze = json.loads((d / "whisper.json").read_text())
    testo = numeri_detti(grezze["text"].strip())
    if not testo:
        return []
    (d / "transcript.txt").write_text("\n".join(x.strip() for x in re.split(r"(?<=[.!?])\s+", testo) if x.strip()) + "\n")
    run(pya, "-I", "scripts/align.py", d / "vocals.wav", d / "transcript.txt", "eng", d / "align.json", cwd=VE)
    run(pya, "-I", "scripts/refine.py", d / "vocals.wav", d / "align.json", d / "words.json", "--fps", "30", cwd=VE)
    return con_tempi_whisper(json.loads((d / "words.json").read_text()), grezze["words"])


def con_tempi_whisper(w, grezze, scarto=1.0):
    """Se l'allineatore spalma le parole (Whisper ha saltato del parlato, urla), dove i due tempi distano più di `scarto` valgono quelli
    di Whisper. Le parole si accoppiano per contenuto (difflib), non per posizione: con i numeri scritti in lettere le liste non sono
    più lunghe uguali (12/11: "Put the camera" messo a 107,7 invece di 111,0 nella clip del cameraman)."""
    norm = lambda x: re.sub(r"[^\w']", "", x).lower()
    sm = difflib.SequenceMatcher(a=[norm(x["show"]) for x in w], b=[norm(g.get("text", g.get("word", ""))) for g in grezze], autojunk=False)
    for blocco in sm.get_matching_blocks():
        for k in range(blocco.size):
            x, g = w[blocco.a + k], grezze[blocco.b + k]
            # solo dove l'allineatore è incerto: i tempi di Whisper sono grossolani ("to" finito dentro "dollars" quando valevano sempre)
            incerto = x.get("score", -9) < -1.0 or x.get("end", x["start"]) - x["start"] > 1.5
            if abs(x["start"] - g["start"]) > scarto and incerto:
                x["start"], x["end"] = round(g["start"], 3), round(max(g["end"], g["start"] + 0.1), 3)
    return w


def gruppi(words, enfasi, durata):
    """Una o due parole alla volta, maiuscole, parolacce censurate, parole chiave colorate."""
    enf = {e.lower(): c for e, c in enfasi.items()}
    out = []
    for w in words:
        grezza = re.sub(r"[^\w'?!-]", "", w["show"]).lstrip("-")
        if not re.search(r"\w", grezza):
            continue
        chiave = re.sub(r"[^\w]", "", grezza).lower()
        txt = CENSURA.get(chiave, grezza.upper())
        parola = {"text": txt, **({"fill": COLORI[enf[chiave]]} if chiave in enf else {})}
        prec = out[-1] if out else None
        # "end" qui è l'inizio dell'ultima parola: la fine data dall'allineatore arriva fino alla parola dopo e non serve
        sola = prec and len(prec["words"]) == 1 and not prec["frase"]  # a frase finita la parola dopo non si attacca
        lampo = sola and w["start"] - prec["end"] < 0.15  # resterebbe a schermo meno di 0,15 s: non si legge (es. "I" + "HATE")
        # le parole corte si attaccano alla precedente se sono vicine, come "WHAT THE-" nei riferimenti
        corte = sola and len(prec["words"][0]["text"]) + len(txt) <= 9 and w["start"] - prec["end"] < 0.45 and "fill" not in parola and "fill" not in prec["words"][0]
        if lampo or corte:
            prec["words"].append(parola)
            prec["end"] = w["start"]
        else:
            out.append({"start": w["start"], "end": w["start"], "words": [parola]})
        out[-1]["frase"] = w["show"].strip()[-1] in ".!?"
    for a, b in zip(out, out[1:] + [None]):
        del a["frase"]
        # resta a schermo fino alla parola dopo, ma nel silenzio sparisce dopo 1 s
        a["end"] = round(min(b["start"] if b else durata, a["end"] + 1.0), 3)
    return out


DEBOLI = set("a an the to of in on at for with from if and but or so my your his her their our i i'm you you're we he she it is was be".split())
RIEMPITIVI = {"bro", "yo", "man", "like", "uh", "um", "oh"}


def ritocca_blocchi(blocchi, riga_max, max_parole=6):
    """Blocchi leggibili (12/11, agenti ritmo e sottotitoli): un blocco non finisce con un articolo, una preposizione o "IF" (la parola
    passa al blocco dopo se arriva subito); un blocco che resterebbe meno di MIN_BLOCCO o una parola di riempimento sola ("BRO")
    si unisce al vicino. Le righe si rifanno; resta al più una parola colorata per blocco."""
    def chiave(p):
        return re.sub(r"[^\w']", "", p["text"]).lower().replace("’", "'")
    def entra(parole):  # al massimo 2 righe di riga_max caratteri
        righe, n = 1, 0
        for p in parole:
            if n and n + len(p["text"]) + 1 > riga_max:
                righe, n = righe + 1, 0
            n += len(p["text"]) + 1
        return righe <= 2 and len(parole) <= max_parole
    bl = [{**b, "p": [p for r in b["righe"] for p in r]} for b in blocchi]
    stessa = lambda x, y: not x["p"][-1].get("fine_frase")  # due frasi diverse (spesso due voci) non si uniscono mai
    for x, y in zip(bl, bl[1:]):
        if (len(x["p"]) > 1 and stessa(x, y) and chiave(x["p"][-1]) in DEBOLI and y["start"] - x["p"][-1]["start"] < 0.8 and entra([x["p"][-1]] + y["p"])
                and x["p"][-1]["start"] - x["p"][0]["start"] >= MIN_BLOCCO):  # il blocco che resta non scende sotto MIN_BLOCCO
            y["p"].insert(0, x["p"].pop())
            y["start"] = y["p"][0]["start"]
    i = 0
    while i < len(bl):
        b = bl[i]
        dopo = bl[i + 1]["start"] if i + 1 < len(bl) else b["start"] + 9
        corto = dopo - b["start"] < MIN_BLOCCO or (len(b["p"]) == 1 and chiave(b["p"][0]) in RIEMPITIVI)
        if corto and i > 0 and stessa(bl[i - 1], b) and entra(bl[i - 1]["p"] + b["p"]) and b["start"] - bl[i - 1]["p"][-1]["start"] < 1.2:
            bl[i - 1]["p"] += b["p"]
            del bl[i]
            continue
        if corto and i + 1 < len(bl) and stessa(b, bl[i + 1]) and entra(b["p"] + bl[i + 1]["p"]):
            bl[i + 1]["p"] = b["p"] + bl[i + 1]["p"]
            bl[i + 1]["start"] = b["start"]
            del bl[i]
            continue
        i += 1
    out = []
    for b in bl:
        visto, righe, n = False, [[]], 0
        for p in b["p"]:
            if "fill" in p:
                if visto:
                    p = {k: v for k, v in p.items() if k not in ("fill", "glow")}
                visto = True
            if righe[-1] and n + len(p["text"]) + 1 > riga_max:
                righe.append([])
                n = 0
            righe[-1].append(p)
            n += len(p["text"]) + 1
        out.append({**{k: v for k, v in b.items() if k != "p"}, "start": b["p"][0]["start"], "righe": righe})
    return out


MIN_BLOCCO = 0.8  # s: un blocco di sottotitoli resta almeno tanto (12/11, Riccardo: "scorrono troppo velocemente per un essere umano")


def frasi_speedy(words, enfasi, durata, narrazioni=(), riga_max=17, parole_max=None):
    """Stile speedy: la frase si costruisce parola per parola su 1-2 righe e resta finché entra la successiva.
    Si chiude a fine frase (. ! ?), dopo una pausa di 0,7 s, o quando due righe sono piene. Le parole in `enfasi` prendono
    colore e alone dalla PALETTA. Le `narrazioni` ({t, durata, testo, colore}) sono le scritte tra asterischi in corsivo
    (*LAUGHING*): entrano tutte insieme e nei loro secondi sostituiscono il parlato.
    `parole_max` (stile mini-storia, 12 nov): blocchi di al massimo tante parole e una sola parola colorata per blocco."""
    enf = {e.lower(): c for e, c in enfasi.items()}
    out, righe, n = [], [[]], 0
    gia_colorate = set()
    unite = []
    for w in words:  # Whisper spezza i numeri ("$10" ",000"): si riattaccano
        if unite and (re.fullmatch(r"[,.]\d+\W*", w["show"].strip()) or w["show"].strip()[:1] in "'’"):  # "$10" ",000", "Y" "'all"
            unite[-1] = {**unite[-1], "show": unite[-1]["show"].strip() + w["show"].strip()}
        else:
            unite.append(w)
    words = unite

    def chiudi(fine):
        nonlocal righe, n
        if righe[0]:
            out.append({"start": righe[0][0]["start"], "end": fine, "righe": righe})
        righe, n = [[]], 0

    prec = None
    for w in words:
        grezza = re.sub(r"[^\w'?!.,$-]", "", w["show"]).lstrip("-").rstrip(",")
        if not re.search(r"\w", grezza):
            continue
        chiave = re.sub(r"[^\w]", "", grezza).lower()
        txt = CENSURA.get(chiave, grezza.upper().rstrip(".").replace("'", "’"))
        pieno = n + len(txt) + 1 > riga_max and len(righe) == 2
        if parole_max:  # stile a storia: si chiude solo dopo MIN_BLOCCO (o a una pausa vera, o a righe piene); "HONG KONG" non si spezza
            durato = w["start"] - righe[0][0]["start"] >= MIN_BLOCCO if righe[0] else False
            nome = prec and prec["maiusc"] and w["show"][:1].isupper() and not prec["frase"] and not prec["virgola"]
            chiude = prec and (w["start"] - prec["start"] > 1.7 or pieno or (durato and not nome and (
                prec["frase"] or sum(map(len, righe)) >= parole_max or (prec["virgola"] and sum(map(len, righe)) >= 2))))
        else:
            chiude = prec and (prec["frase"] or w["start"] - prec["start"] > 1.7 or pieno)
        if parole_max and prec and prec["frase"]:
            chiude = True  # 12/11, Riccardo: chi parla cambia quasi sempre a fine frase; un blocco non finisce con la prima parola della battuta dopo
        if chiude:
            chiudi(w["start"])
        if righe[-1] and n + len(txt) + 1 > riga_max:
            righe.append([])
            n = 0
        colore = PALETTA.get(enf.get(chiave, ""), {})
        if parole_max and (any("fill" in p for r in righe for p in r) or chiave in gia_colorate):
            colore = {}  # 12/11, agente sottotitoli: CAMERA colorata 3 volte, RULES 4: la parola chiave prende colore solo la prima volta
        if colore:
            gia_colorate.add(chiave)
        righe[-1].append({"text": txt, "start": round(w["start"], 3), **colore, **({"fine_frase": True} if w["show"].strip()[-1] in ".!?" else {})})
        n += len(txt) + 1
        prec = {"start": w["start"], "frase": w["show"].strip()[-1] in ".!?", "virgola": w["show"].strip()[-1] == ",",
                "maiusc": w["show"].strip()[:1].isupper() and chiave not in ("i", "im")}
    chiudi(durata)
    if parole_max:
        out = ritocca_blocchi(out, riga_max)
    for a, b in zip(out, out[1:] + [None]):
        ultima = a["righe"][-1][-1]["start"]
        a["end"] = round(min(b["start"] if b else durata, ultima + 1.6), 3)  # nel silenzio la frase sparisce da sola
    for x in narrazioni:
        t0, t1 = x["t"], x["t"] + x.get("durata", 1.5)
        if "baseline" in x:  # narrazione con una posizione sua (es. in alto): convive con il parlato
            t0 = t1 = -1
        # shortcut: nei secondi della narrazione il parlato non si vede (la frase in corso viene accorciata, quelle dentro saltano); se servono insieme, dare alla narrazione una posizione sua
        out = [{**f, "end": min(f["end"], t0)} if f["start"] < t0 else f for f in out if not t0 <= f["start"] < t1]
        out.append({"start": x["t"], "end": x["t"] + max(x.get("durata", 2.2), 2.2) - 0.28, "corsivo": True, **{k: x[k] for k in ("baseline", "cx", "size", "scrivi") if k in x},
                    "righe": [[{"text": "*" + x["testo"].upper().strip("*") + "*", **PALETTA.get(x.get("colore", "giallo"), {})}]]})
    return sorted(out, key=lambda f: f["start"])


def riga_libera(base, facce, A, corpo=68, righe=2, interlinea=67):
    """Linea di base dei sottotitoli che non copre nessuna faccia: quella normale se è libera; altrimenti subito sotto la faccia più
    bassa, se resta sopra la firma; altrimenti subito sopra la più alta. Contano solo le facce nella colonna centrale, dove sta il testo."""
    facce = [f for f in facce if f[0] < 870 and f[0] + f[2] > 210]
    su, giu = base - corpo, base + interlinea * (righe - 1) + 14  # dalla cima della prima riga al fondo della seconda
    if not any(f[1] < giu and f[1] + f[3] > su for f in facce):
        return base
    sotto = max(f[1] + f[3] for f in facce) + 24 + corpo
    if sotto + interlinea * (righe - 1) <= A - 200:
        return round(sotto)
    sopra = min(f[1] for f in facce) - 24 - interlinea * (righe - 1) - 14
    return round(sopra) if sopra - corpo >= 40 else base


def trova_volti(video, t):
    """Facce nel fotogramma `t` del video (Vision di macOS, strumenti/volti): [(x, y, w, h)] in pixel, solo quelle sicure."""
    png = Path(video).with_name("_volto.png")
    run("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", round(max(0, t), 3), "-i", video, "-frames:v", "1", png)
    ris = json.loads(subprocess.run([str(QUI / "strumenti/volti"), str(png)], capture_output=True, text=True).stdout or "[]")
    return [(f["x"], f["y"], f["w"], f["h"]) for f in ris if f["c"] >= 0.6 and f["h"] >= 40]



# Freccia di Grafiche.tsx a size 150, punta in (0,0): ingombro x -166..8, y -26..241; la testa va lungo (57,5, -23) (verso destra e un po' in su)
FRECCIA_BOX, FRECCIA_DIR = (-166, -26, 8, 241), (0.9285, -0.3714)


def _tocca(a, b, aria=0):
    return a[0] < b[2] + aria and b[0] < a[2] + aria and a[1] < b[3] + aria and b[1] < a[3] + aria


def piazza_freccia(fr, volti, frasi, base, A, passo=0.25):
    """Etichetta con freccia che presenta una persona. Riccardo (11 nov): "assicurati che la freccia punti sempre alla persona e che non sia
    troppo invasiva". La scheda dice solo chi ("sinistra", "destra", "unica"), quando e il testo; la faccia la trova `volti(t)` ogni `passo`
    secondi e freccia ed etichetta la seguono (campo "segui"). Punta 15 px fuori dal bordo della faccia, dal lato con più posto, diretta al
    centro della faccia; freccia alta quanto la faccia (size 60-100). Etichetta sotto la coda (o accanto, o più piccola) senza toccare
    freccia, facce e sottotitoli in nessun punto. Se la faccia si perde prima di 1,5 s o manca il posto: None (meglio niente che sbagliata)."""
    t0, d = fr["t"], fr.get("durata", 2.3)
    tutte = volti(t0 + 0.05)
    if not tutte or (fr.get("chi", "unica") == "unica" and len(tutte) != 1):
        return None
    centro = lambda f: (f[0] + f[2] / 2, f[1] + f[3] / 2)
    faccia = {"sinistra": min, "destra": max}.get(fr.get("chi"), min)(tutte, key=lambda f: centro(f)[0])
    # inseguimento: a ogni passo la faccia più vicina alla precedente, spostata meno della sua larghezza e di grandezza simile
    punti, cur = [(t0, faccia, tutte)], faccia
    for tt in [t0 + passo * n for n in range(1, int((d - 0.1) / passo) + 1)] + [t0 + d - 0.05]:
        ff = volti(tt)
        vicine = [f for f in ff if math.dist(centro(f), centro(cur)) < cur[2] and 0.7 < f[3] / cur[3] < 1.4]
        if not vicine:
            d = punti[-1][0] - t0 + 0.1  # persa: si ferma dov'era sicura
            break
        cur = min(vicine, key=lambda f: math.dist(centro(f), centro(cur)))
        punti.append((tt, cur, ff))
    if d < 1.5:
        return None
    (cx, cy), alta = centro(faccia), sorted(p[1][3] for p in punti)[len(punti) // 2]
    box = lambda f: (f[0], f[1], f[0] + f[2], f[1] + f[3])
    sposta = lambda b, dx, dy: (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)
    segui = [(round(tt - t0, 3), centro(f)[0] - cx, centro(f)[1] - cy) for tt, f, _ in punti]
    size = min(100, max(60, 150 * alta / (FRECCIA_BOX[3] - FRECCIA_BOX[1])))
    k = size / 150
    fuori = lambda b: b[0] < 10 or b[2] > 1070 or b[1] < 10 or b[3] > A * 0.9 - 10

    def libero(b, aria=0):  # in ogni punto dell'inseguimento: dentro il quadro e lontano da tutte le facce
        return all(not fuori(sposta(b, dx, dy)) and not any(_tocca(sposta(b, dx, dy), box(f), aria) for f in ff) for (_, dx, dy), (_, _, ff) in zip(segui, punti))

    parlato = [f for f in frasi if not f.get("corsivo") and f["start"] < t0 + d and t0 < f["end"] + 0.28]
    lati = sorted((1, -1), key=lambda v: -(faccia[0] if v == 1 else 1080 - faccia[0] - faccia[2]))  # prima il lato con più posto
    for verso in lati:
        ux, uy = FRECCIA_DIR[0] * verso, FRECCIA_DIR[1]
        uscita = min(faccia[2] / 2 / abs(ux), faccia[3] / 2 / abs(uy))  # dal centro al bordo della faccia, contro la direzione
        px, py = cx - ux * (uscita + 15), cy - uy * (uscita + 15)
        xs = sorted((px + verso * FRECCIA_BOX[0] * k, px + verso * FRECCIA_BOX[2] * k))
        box_f = (xs[0], py + FRECCIA_BOX[1] * k, xs[1], py + FRECCIA_BOX[3] * k)
        if not libero(box_f):
            continue
        coda = (px - verso * 137.5 * k, py + 213 * k)
        for corpo in (68, 56, 46):
            mezza = (len(fr["testo"]) + 2) * corpo * 0.36  # metà larghezza stimata della scritta
            # sotto la coda, spostata dentro il quadro di al massimo mezza scritta (la coda resta sopra la scritta)
            for ex, base_e in ((min(max(coda[0], 20 + mezza - min(x[1] for x in segui), coda[0] - mezza), 1060 - mezza - max(x[1] for x in segui), coda[0] + mezza), box_f[3] + 14 + 0.75 * corpo),
                               (coda[0] - verso * (28 * k + 20 + mezza), coda[1] + 0.3 * corpo)):  # accanto alla coda, verso l'esterno
                box_e = (ex - mezza, base_e - 0.75 * corpo, ex + mezza, base_e + 0.12 * corpo)
                if _tocca(box_e, box_f, 6) or box_e[0] < 20 or box_e[2] > 1060 or not libero(box_e):
                    continue
                # niente sui sottotitoli del parlato (che restano fermi) in nessun punto dello spostamento
                if any(box_e[1] + dy < b and a < box_e[3] + dy for _, _, dy in segui for a, b in map(lambda f: ingombro(f, base), parlato)):
                    continue
                colore = PALETTA.get(fr.get("colore", "verde"), {"fill": fr.get("colore")})
                g = {"tipo": "freccia", "t": t0, "durata": round(d, 3), "x": round(px), "y": round(py), "versoX": verso, "size": round(size), "colore": colore["fill"]}
                # la scritta sfuma in 0,28 s dopo `end`: così esce insieme alla freccia
                e = {"start": t0, "end": round(t0 + d - 0.28, 3), "corsivo": True, "baseline": round(base_e), "cx": round(ex), "size": corpo,
                     "righe": [[{"text": "*" + fr["testo"].upper().strip("*") + "*", **colore}]]}
                if any(dx or dy for _, dx, dy in segui):
                    g["segui"] = e["segui"] = [[tt, round(dx), round(dy)] for tt, dx, dy in segui]
                return g, e, {"faccia": box(faccia), "freccia": box_f, "etichetta": box_e}
    return None


def ingombro(f, base):
    """(alto, basso) in px della scritta di una frase glow: maiuscole alte 0,74 del corpo, seconda riga 67 px più giù."""
    size, b = f.get("size", 68), f.get("baseline", base)
    return b - 0.74 * size, b + (len(f["righe"]) - 1) * 67 * size / 68 + 0.1 * size


def posa_icone(icone, frasi, base, A, gap=20):
    """Icone ed emoji legate a un sottotitolo. Regola di Riccardo (11 nov): "le icone in mezzo o vicino ai sottotitoli devono SEMPRE
    essere in questa zona": centrate sulla scritta, subito sopra (bordo basso a `gap` px dal testo) o subito sotto. La posizione non si
    prende dalla scheda: si sceglie solo "dove". Se da un lato non c'è posto (bordo del quadro, firma, altra scritta attiva) si usa
    l'altro; se manca da tutti e due l'icona si rimpicciolisce. Entra con la parola (t) ed esce con la frase."""
    out = []
    for ic in icone:
        attive = [f for f in frasi if f["start"] <= ic["t"] + 1e-6 < f["end"]]
        if not attive:
            print(f"icona saltata, nessuna scritta al secondo {ic['t']:.2f}", file=sys.stderr)
            continue
        f = max(attive, key=lambda x: x["start"])
        alto, basso = ingombro(f, base)
        altre = [ingombro(g, base) for g in frasi if g is not f and g["start"] < f["end"] and ic["t"] < g["end"] + 0.28
                 and (g.get("baseline"), g.get("cx")) != (f.get("baseline"), f.get("cx"))]
        su = alto - gap - max([10] + [b + gap for a, b in altre if b <= alto])  # posto libero sopra
        giu = min([A * 0.9 - 10] + [a - gap for a, b in altre if a >= basso]) - basso - gap  # sotto, fino alla firma (90% dell'altezza)
        h = ic.get("size", 110)
        dove = ic.get("dove", "sopra")
        posto = {"sopra": su, "sotto": giu}
        if posto[dove] < h:
            altro = "sotto" if dove == "sopra" else "sopra"
            if posto[altro] >= h:
                dove = altro
            else:
                dove = max(posto, key=posto.get)
                h = max(40, posto[dove])
        y = alto - gap - h / 2 if dove == "sopra" else basso + gap + h / 2
        succ = any(g["start"] == f["end"] and (g.get("baseline"), g.get("cx")) == (f.get("baseline"), f.get("cx")) for g in frasi)
        fine = f["end"] if succ else f["end"] + 0.28  # sfuma insieme alla scritta
        out.append({"tipo": "emoji", "t": ic["t"], "durata": round(fine - ic["t"], 3), "x": f.get("cx", 540), "y": round(y), "size": round(h),
                    **{k: ic[k] for k in ("emoji", "src", "alone") if k in ic}})
    return out


def speedy(s, props, w, durata, giunzione, A, t, url=lambda r: r, volti=lambda t: []):
    """Proprietà in più della composizione ClipSpeedy, ricavate dalla stessa scheda del classico più i campi facoltativi dello stile."""
    def tempi(nome):
        return [{**x, "t": t(x["t"])} for x in s.get(nome, []) if t(x["t"]) is not None]

    testo = s.get("testo", "glow")
    # 3:4: prima riga appena sopra la metà (linea di base a 711 su 1440), sia nel pieno sia nel diviso, dove la riga bianca sta a 704-710;
    # 9:16 con due riquadri: a cavallo della giunzione
    base = 711 if A == 1440 else (giunzione + 26 if giunzione else round(A * 0.494))
    effetti, grafiche, narrazioni = tempi("effetti"), tempi("grafiche"), tempi("narrazioni")
    # emoji libere lontano dal testo non si usano più (Riccardo, 11 nov): un'emoji della scheda diventa un'icona legata alla scritta del suo istante
    icone = tempi("icone") + [{k: g[k] for k in ("t", "emoji", "src", "size", "alone", "dove") if k in g} for g in grafiche if g["tipo"] == "emoji"]
    grafiche = [g for g in grafiche if g["tipo"] != "emoji"]
    for ic in icone:
        if "file" in ic:  # immagine scaricata in laboratorio/icone/
            ic["src"] = url(str((QUI / ic.pop("file")).relative_to(RADICE)))
    # Etichetta con freccia: la punta non si dà più a mano (Riccardo, 11 nov: "la freccia è troppo grande e non punta alla faccia").
    # Le frecce scritte a mano nella scheda e le loro etichette si scartano; si usa il campo "freccia" (vedi piazza_freccia).
    if any(g["tipo"] == "freccia" for g in grafiche):
        print("freccia a mano scartata: usare \"freccia\": {\"t\", \"durata\", \"chi\", \"testo\"}", file=sys.stderr)
        grafiche = [g for g in grafiche if g["tipo"] != "freccia"]
        narrazioni = [n for n in narrazioni if "baseline" not in n]
    fin = s.get("finale")
    if fin:
        # finale di riferimento: lampo bianco con mosso, immagine in bianco e nero scurita, emoji grande con alone, scritta in corsivo,
        # puntini che salgono, dissolvenza a nero nell'ultimo mezzo secondo (la firma resta)
        # 12/11: l'emoji finale deve restare abbastanza da leggerla, ma non deve partire sopra l'ultima frase
        dopo_voce = max((x.get("end", x["start"]) for x in w), default=0) + 0.15
        tf = t(fin["t"]) if "t" in fin else (dopo_voce if durata - fin.get("durata", 2.5) < dopo_voce <= durata - 1.0 else max(0, durata - fin.get("durata", 2.5)))
        if tf is not None:
            # fondo: scurito a colori in 4 finali su 6 (FUI, C4i, C1t, 5Jw), in bianco e nero in TRG ("bn": true)
            fondo = {"tipo": "bn", "t": tf, "durata": durata - tf, "scuro": 0.4} if fin.get("bn") else {"tipo": "scuro", "t": tf + 0.1, "durata": durata - tf, "forza": 0.4}
            effetti += [{"tipo": "mosso", "t": tf}, fondo, {"tipo": "nero", "t": durata - 0.5}]
            grafiche += [{"tipo": "particelle", "t": tf + 0.2, "durata": durata - tf}]
            if fin.get("emoji"):
                # emoji larga 135-210 px su 1080 (C1t 135, FUI 150, C4i 170, TRG 210): font 140 = circa 165 px; centrata sopra la scritta
                grafiche.append({"tipo": "emoji", "t": tf + 0.2, "durata": durata - tf, "x": 540, "y": base - 200, "emoji": fin["emoji"], "size": 140})
            if fin.get("testo"):
                narrazioni.append({"t": tf + 0.25, "durata": durata - tf, "testo": fin["testo"], "colore": fin.get("colore", "verde")})
            props["lampi"] = props["lampi"] + [{"t": tf, "colore": "#ffffff", "forza": 1.0, "durata": 0.3}]
            # colpo di bassi sul lampo del finale: 5 finali su 5 misurati (FUI +47 dB, C4i +48,6 dB coda 3 s); "suono": null per toglierlo
            colpo = fin.get("suono", "NUOVO_bassdrop_Base-drop-Doon.m4a")
            if colpo:
                props.setdefault("suoni", []).append({"t": tf, "file": url(f"suoni/approvati/{colpo}"), "volume": fin.get("volume_suono", round(0.8 * PESO_SUONO(colpo), 2))})
            if fin.get("fermo"):  # fondo fermo dal lampo del finale (ocTX 31,4-33,2)
                props["fermo"] = tf + 0.15
    props["lampi"] = [{**l, "colore": LAMPI_SPEEDY.get(l["colore"], l["colore"])} for l in props["lampi"]]
    if s.get("luce", LUCE):  # predefinita; "luce": false la spegne, {"forza": ...} la cambia
        props["luce"] = s.get("luce", LUCE)
    if s.get("saturazione", 1) != 1:
        props["saturazione"] = s["saturazione"]
    props.update(testo=testo, effetti=effetti, grafiche=grafiche)
    if testo == "glow":
        props["glow"] = {"baseline": base, **s.get("glow", {})}
        props["frasi"] = frasi_speedy(w, {**s.get("enfasi", {}), **s.get("colori", {})}, durata, narrazioni, parole_max=s.get("parole_blocco"))  # "colori": come enfasi ma con tutta la PALETTA, solo speedy
        # I sottotitoli non coprono mai una faccia (regola di Riccardo; a webcam piena la riga di metà quadro finiva su occhi e naso).
        # Si decide per tratto di layout, così la scritta non salta su e giù da una frase all'altra: si guardano le facce a metà di
        # quattro frasi del tratto e, se la riga ne tocca una, tutto il parlato del tratto si sposta.
        bordi = [0] + [x[0] - s.get("inizio", 0) for x in (s.get("layout") or {}).get("tratti", [])[1:]] + [durata + 1]
        for da, a in zip(bordi, bordi[1:]):
            tratto = [f for f in props["frasi"] if "baseline" not in f and da <= (f["start"] + f["end"]) / 2 < a]
            campioni = [tratto[round(i * (len(tratto) - 1) / 3)] for i in range(4)] if tratto else []
            facce = [v for f in {id(x): x for x in campioni}.values() for v in volti((f["start"] + f["end"]) / 2)]
            if (libera := riga_libera(props["glow"]["baseline"], facce, A)) != props["glow"]["baseline"]:
                print(f"sottotitoli spostati a {libera} da {da:.1f} a {min(a, durata):.1f} s: a {props['glow']['baseline']} coprivano una faccia", file=sys.stderr)
                for f in tratto:
                    f["baseline"] = libera
        if fin and tf is not None:  # dal lampo del finale resta solo la scritta del finale: il parlato non deve sovrapporsi mentre sfuma
            props["frasi"] = [{**f, "end": min(f["end"], tf)} if f["start"] < tf else f for f in props["frasi"] if f["start"] < tf or f.get("corsivo")]
        # frase intera di un colore (sPS9: 16 frasi su 26 tutte colorate): le parole già colorate restano come sono
        for fc in tempi("frasi_colorate"):
            for f in props["frasi"]:
                if not f.get("corsivo") and f["start"] <= fc["t"] < f["end"]:
                    f["righe"] = [[p if "fill" in p else {**p, **PALETTA[fc["colore"]]} for p in r] for r in f["righe"]]
        for fr in [{**s["freccia"], "t": t(s["freccia"]["t"])}] if s.get("freccia") and t(s["freccia"]["t"]) is not None else []:
            if (messa := piazza_freccia(fr, volti, props["frasi"], props["glow"]["baseline"], A)):
                grafiche.append(messa[0])
                props["frasi"] = sorted(props["frasi"] + [messa[1]], key=lambda f: f["start"])
                print(f"freccia su {fr['testo']!r}: {messa[2]}", file=sys.stderr)
            else:
                print(f"freccia saltata su {fr['testo']!r} al secondo {fr['t']:.2f}: faccia non trovata con sicurezza o senza posto", file=sys.stderr)
        props["grafiche"] = grafiche + posa_icone(icone, props["frasi"], props["glow"]["baseline"], A)
    elif icone:
        print("icone saltate: valgono solo con i sottotitoli glow", file=sys.stderr)
    elif testo == "fumetto":
        props["fumetto"] = {"baseline": (giunzione or round(A * 0.55)) + 34, **s.get("fumetto", {})}
    return props


def main():
    s = json.loads(Path(sys.argv[1]).read_text())
    s = {**VIBE.get(s.get("vibe"), {}), **s}  # "vibe": "serio" mette i suoi valori predefiniti; quello che la scheda scrive vince
    stile = s.get("stile", "classico")
    A = 1440 if stile == "speedy" and s.get("formato", "3:4") == "3:4" and s["layout"]["tipo"] != "riempitivo" else 1920
    d = QUI / "lavoro" / s["id"]
    d.mkdir(parents=True, exist_ok=True)
    base = d / "base.mp4"
    # taglio e parole si rifanno solo se cambia il taglio: ritoccare effetti e suoni costa solo il render
    taglio = {k: s.get(k) for k in ("sorgente", "inizio", "fine", "layout", "tagli")}
    if A != 1920:
        taglio["A"] = A
    if s.get("tagli"):  # i tempi degli effetti contano dall'inizio della storia montata
        s["inizio"], s["fine"] = 0, round(sum(b - a for a, b in s["tagli"]), 2)
    chiesto = s["inizio"]
    memo = d / "taglio.json"
    if memo.exists() and (m := json.loads(memo.read_text()))["taglio"] == taglio:
        s["inizio"], s["fine"] = m["agganciato"]
        giunzione, w = m["giunzione"], json.loads((d / "words.json").read_text())
    else:
        t0 = time.time()
        if s.get("tagli"):
            ws, voce, da_w = parole_sorgente(s, d)
            s["tagli"] = stacchi(s["tagli"], ws, voce, da_w)
            s["_voce"] = (str(voce), da_w)
            print("stacchi sul silenzio:", s["tagli"], file=sys.stderr)
            w = sposta_parole(ws, s["tagli"], da_w)
            if s.get("finale") and w and "t" not in s["finale"]:
                # 12/11: il finale partiva 2,5 s prima della fine e copriva "Hong Kong, bro. Congratulations". Ora parte dopo l'ultima
                # parola tenuta; l'ultimo tratto si allunga quanto serve e lì la voce sfuma, così sotto l'emoji non si sente una frase nuova a metà
                tf = round(max(min(x["end"], x["start"] + 0.8) for x in w) + 0.15, 3)  # l'allineatore allunga l'ultima parola ("way" 2,5 s)
                manca = tf + s["finale"].get("durata", 2.5) - sum(b - a for a, b in s["tagli"])
                if manca > 0:
                    s["tagli"][-1][1] = round(s["tagli"][-1][1] + manca, 3)
                s["finale"]["t"], s["_sfuma_da"] = tf, tf - 0.12  # la voce sfuma subito dopo l'ultima parola: la successiva non si sente
                print(f"finale a {tf} s, dopo l'ultima parola ({w[-1]['show']!r})", file=sys.stderr)
            if s["layout"]["tipo"] == "pieno" and s["layout"].get("segui", True):
                s["layout"] = inquadra_tratti(s, A)
            s["fine"] = storia(s, d / "storia.mp4")
            s["sorgente"] = str(d / "storia.mp4")  # gli stacchi sono già sulle pause scelte guardando le parole: niente aggancio
        else:
            s["inizio"], s["fine"] = aggancia(s)
        giunzione = layout(s, base, A)
        for _ in range(3):  # dopo lo spostamento può capitare un altro fermo nei primi secondi: al massimo tre tentativi, poi decide il controllo qualità
            if not (avanti := salto(fermi(base, 0.3))):
                break
            print(f"inizio fermo: la clip parte {avanti:.2f} s dopo", file=sys.stderr)
            s["inizio"] = round(s["inizio"] + avanti + 0.05, 2)
            giunzione = layout(s, base, A)
        if s.get("tagli"):
            if s["inizio"]:  # la storia parte dopo un fermo: le parole seguono
                w = [{**x, "start": round(x["start"] - s["inizio"], 3), "end": round(x["end"] - s["inizio"], 3)} for x in w if x["start"] >= s["inizio"]]
            w = riallinea(base, d, w)
            (d / "words.json").write_text(json.dumps(w))
            controlla_stacchi(d / "vocals.wav", s["tagli"])
        t1 = time.time()
        # LAB: le parole dipendono solo dal taglio, non dal layout né dallo stile: si calcolano una volta e si riusano (classico e speedy della stessa clip)
        cache = QUI / "lavoro" / "_parole" / hashlib.md5(json.dumps([s["sorgente"], s["inizio"], s["fine"]]).encode()).hexdigest()[:10]
        if s.get("tagli"):
            pass  # parole già prese da parole_storia
        elif (cache / "words.json").exists():
            for f in ("words.json", "vocals.wav"):
                shutil.copy(cache / f, d / f)
            w = json.loads((d / "words.json").read_text())
        else:
            w = parole(base, d)
            cache.mkdir(parents=True, exist_ok=True)
            for f in ("words.json", "vocals.wav"):
                shutil.copy(d / f, cache / f)
        memo.write_text(json.dumps({"taglio": taglio, "giunzione": giunzione, "agganciato": [s["inizio"], s["fine"]]}))
        print(f"tempi: taglio {t1 - t0:.0f} s, parole {time.time() - t1:.0f} s", file=sys.stderr)

    durata = s["fine"] - s["inizio"]
    if (corr := {k.lower(): v for k, v in s.get("correzioni", {}).items()}):  # nomi trascritti male: "Rekha" -> "Rakai" (12/11)
        w = [{**x, "show": re.sub(r"[\w']+", lambda m: corr.get(m.group(0).lower(), m.group(0)), x["show"])} for x in w]
    if "--parole" in sys.argv:  # LAB: solo taglio e parole, per scrivere la scheda guardando la trascrizione
        print(json.dumps([[round(x["start"], 2), x["show"]] for x in w], ensure_ascii=False))
        return
    anticipo = chiesto - s["inizio"]  # i tempi degli effetti erano contati dall'inizio chiesto

    def t(x):
        """Tempo di un effetto: secondi dall'inizio della clip, oppure una parola ("shit", "oh@20" = l'"oh" più vicino al secondo 20)."""
        if not isinstance(x, str):
            return x + anticipo
        chiave, _, vicino = x.partition("@")
        chiave = re.sub(r"[^\w]", "", chiave)  # "can't@9" come la parola trascritta
        vicino = float(vicino) + anticipo if vicino else ""
        volte = [p["start"] for p in w if re.sub(r"[^\w]", "", p["show"]).lower() == chiave.lower()]
        if not volte:  # la trascrizione finale può differire da quella vista dal selezionatore: salta l'effetto, non la clip
            print(f"effetto saltato, parola assente: {x!r}", file=sys.stderr)
            return None
        return min(volte, key=lambda v: abs(v - float(vicino or v)))

    def effetti(nome):
        # visto l'11/11: zoom e suono a "show@29" in una clip di 26 s, mai partiti. Fuori dalla clip = saltati e detti
        fuori = [x["t"] for x in s.get(nome, []) if (v := t(x["t"])) is not None and not 0 <= v < durata]
        if fuori:
            print(f"{nome}: saltati perché fuori dalla clip ({durata:.1f} s): {fuori}", file=sys.stderr)
        return [{**x, "t": v} for x in s.get(nome, []) if (v := t(x["t"])) is not None and 0 <= v < durata]

    riga = dict(PRESET["outline"]["line"])
    if giunzione:  # nel layout diviso la parola sta sulla giunzione tra facecam e gioco
        riga.update(size=150, stroke=17, baseline=giunzione + 52)

    # Remotion legge video e suoni da un server locale: niente copie di file grossi dentro il bundle
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(RADICE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = lambda rel: f"http://127.0.0.1:{srv.server_address[1]}/{rel}"

    vol_musica = 0
    if s.get("musica"):
        # nelle clip di riferimento la musica sta 3-8 dB sotto la voce; qui 10 perché sotto c'è già l'audio del gioco
        sotto = s["musica"].get("db_sotto_voce", 10)
        m = RADICE / "musica" / s["musica"]["file"]  # 12/11, agente audio: si misura il tratto che suona davvero (l'intro è 5 LU più bassa)
        vol_musica = round(min(1.0, 10 ** ((lufs(d / "vocals.wav") - sotto - (lufs_pezzo(m, 0, durata) or lufs(m))) / 20)), 4)

    props = {
        "video": url(f"{d.relative_to(RADICE)}/base.mp4"), "width": 1080, "height": A, "durata": durata, "riga": riga,
        "gruppi": gruppi(w, s.get("enfasi", {}), durata),
        "lampi": lontani_dagli_stacchi(effetti("lampi"), s.get("tagli")), "zoom": effetti("zoom"),
        "suoni": [{"t": max(0, x["t"] + x.get("anticipo", 0)), "file": url(f"suoni/approvati/{x['file']}"), "volume": round(x.get("volume", 0.8) * PESO_SUONO(x["file"]), 2)} for x in effetti("suoni")],
        **({"musica": {"file": url(f"musica/{s['musica']['file']}"), "volume": vol_musica}} if s.get("musica") else {}),
        **({"firma": s["firma"]} if s.get("firma") else {}),
    }
    if stile == "speedy":
        props = speedy(s, props, w, durata, giunzione, A, t, url, lambda x: trova_volti(base, x))
    (d / "props.json").write_text(json.dumps(props, ensure_ascii=False, indent=1))
    lavoro = d / "job.json"
    lavoro.write_text(json.dumps([{"id": "ClipSpeedy" if stile == "speedy" else "Clip", "media": True, "out": str(d / "finale.mp4"), "props": props}]))
    t0 = time.time()
    run("node", "render.mjs", lavoro, cwd=QUI / "remotion")
    print(f"tempi: render {time.time() - t0:.0f} s per {durata:.0f} s di clip", file=sys.stderr)
    srv.shutdown()
    if s.get("uscita"):
        # volume finale a -14 LUFS, quello a cui le piattaforme riportano i video
        # limitatore dopo loudnorm; la codifica AAC può comunque far risalire i picchi fino a 0 dB (visto dal controllo qualità su un beep):
        # si misura il file finito e, se serve, si rifà una volta abbassando di quanto manca a -1 dB
        # 12/11: niente loudnorm dinamico (alzava la musica dove la voce era debole: su e giù). Guadagno fisso fino a -14 LUFS + limitatore
        uscita, filtri = Path(s["uscita"]).expanduser(), f"volume={-14 - lufs(d / 'finale.mp4'):.2f}dB,alimiter=limit=0.794:level=false"
        for _ in range(3):
            run("ffmpeg", "-nostdin", "-v", "error", "-y", "-i", d / "finale.mp4", "-c:v", "copy", "-af", filtri,
                "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", uscita)
            picco = float(re.search(r"max_volume: (-?[\d.]+) dB", subprocess.run(["ffmpeg", "-nostdin", "-i", str(uscita), "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr).group(1))
            # LAB: loudnorm in un passaggio può mancare il bersaglio (Crashout uscito a -12,0 LUFS): si corregge di quanto manca
            scarto = -14 - lufs(uscita)
            if picco <= -1 and abs(scarto) <= 1:
                break
            filtri += f",volume={min(scarto, -1.2 - picco):.1f}dB,alimiter=limit=0.794:level=false"
    print(d / "finale.mp4")


if __name__ == "__main__":
    # autocontrollo del raggruppamento: parole corte unite, parolacce censurate, enfasi colorata e isolata
    g = gruppi([{"show": "what", "start": 0, "end": 0.2}, {"show": "the", "start": 0.22, "end": 0.4}, {"show": "fuck", "start": 0.45, "end": 0.8}, {"show": "Bro!", "start": 2, "end": 2.3}], {"bro": "magenta"}, 5)
    assert [" ".join(x["text"] for x in y["words"]) for y in g] == ["WHAT THE", "F*CK", "BRO!"], g
    assert g[2]["words"][0]["fill"] == COLORI["magenta"] and g[0]["end"] == 0.45 and g[1]["end"] == 1.45 and g[2]["end"] == 3.0
    g = gruppi([{"show": "probably", "start": 0, "end": 1}, {"show": "I", "start": 1, "end": 1.03}, {"show": "hate", "start": 1.03, "end": 1.2}, {"show": "bro.", "start": 1.5, "end": 1.6}, {"show": "Sorry", "start": 1.7, "end": 2}], {"hate": "magenta"}, 5)
    assert [" ".join(x["text"] for x in y["words"]) for y in g] == ["PROBABLY", "I HATE", "BRO", "SORRY"], g
    assert pausa([60] * 20 + [20] * 5 + [60] * 10, True) == 22.5 and pausa([60] * 30, True) is None and pausa([60, 20, 20, 20, 60, 20, 20, 20, 20, 60], False) == 2.5
    assert [x["words"][0]["text"] for x in gruppi([{"show": "-", "start": 0, "end": 1}, {"show": "-hmm", "start": 2, "end": 3}], {}, 5)] == ["HMM"]
    D = {"tipo": "diviso", "facecam": [0, 264, 396, 222], "gioco_cx": 960}
    assert grafo(D, 0) == (filtro(D, "[0:v]fps=30,", "[v]")[0], 606) and grafo({"tipo": "fascia"}, 0)[1] == 408 and grafo({"tipo": "pieno"}, 0)[1] is None
    assert "crop=1216:974:352:0,scale=1080:866" in filtro({"tipo": "fascia", "utile": 974}, "", "")[0] and "crop=800:974:560:0" in filtro({**D, "utile": 974}, "", "")[0]
    vf, g = grafo({"tipo": "misto", "tratti": [[100, D], [108.5, {"tipo": "fascia", "cx": 960}], [112, D]]}, 101)
    assert g == 606 and "overlay=0:678[o1]" in vf and "[o0][o1]overlay=enable='gte(t,7.500)*lt(t,11.000)'[m1]" in vf and vf.endswith("[m1][o2]overlay=enable='gte(t,11.000)'[v]")
    fs = frasi_speedy([{"show": "Who", "start": 0}, {"show": "is", "start": 0.2}, {"show": "the", "start": 0.4}, {"show": "best", "start": 0.6}, {"show": "football", "start": 0.8}, {"show": "player?", "start": 1.2}, {"show": "Ronaldo!", "start": 3}],
                      {"ronaldo": "rosso"}, 6, [{"t": 4.5, "durata": 1, "testo": "tastes it", "colore": "rosso"}])
    assert [[" ".join(x["text"] for x in r) for r in f["righe"]] for f in fs] == [["WHO IS THE BEST", "FOOTBALL PLAYER?"], ["RONALDO!"], ["*TASTES IT*"]], fs
    assert fs[0]["end"] == 2.8 and fs[1]["righe"][0][0]["fill"] == PALETTA["rosso"]["fill"] and fs[1]["end"] == 4.5 and fs[2]["corsivo"]
    assert [x["text"] for x in frasi_speedy([{"show": "$10", "start": 0}, {"show": ",000", "start": 0.5}, {"show": "bro.", "start": 0.9}], {}, 2)[0]["righe"][0]] == ["$10,000", "BRO"]
    with tempfile.TemporaryDirectory() as _t:
        _v = Path(_t) / "v.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=300:d=3", "-af", "volume=enable='between(t,1,1.5)':volume=0", "-ar", "16000", _v], check=True)
        _st = stacchi([[1.45, 2.9], [0.1, 0.9]], [{"show": "one.", "start": 0.05, "end": 0.95}, {"show": "two.", "start": 1.5, "end": 2.95}], _v)
        assert 1.3 <= _st[0][0] <= 1.5 and _st[0][1] >= 2.95 and _st[1][0] <= 0.05 and 1.0 <= _st[1][1] <= 1.5, _st
        assert 2.55 <= stacchi([[0.05, 2.9]], [{"show": "one.", "start": 0.05, "end": 0.95}], _v)[0][1] <= 3.0
        # un numero con tempo inventato (fine a 0,2 s) che in realtà si sente fino a 1 s: lo stacco va nel silenzio dopo, non a 0,2
        assert 1.0 <= stacchi([[0.0, 0.3]], [{"show": "$10", "start": 0.05, "end": 0.2, "score": 0}, {"show": "to", "start": 1.5, "end": 1.7}], _v)[0][1] <= 1.5
        assert [x["t"] for x in lontani_dagli_stacchi([{"t": 2.1}, {"t": 5.0}], [[0, 2], [10, 12], [20, 21]])] == [2.4, 5.0]
    assert dubbia({"show": ",000"}) and dubbia({"show": "ok", "score": 0}) and not dubbia({"show": "ten", "score": -0.1})  # margine chiesto dopo l'ultima parola: resta
    assert numeri_detti("giving you $10,000 to go") == "giving you ten thousand dollars to go" and numeri_detti("It's 21 plus, 2.5% and 1st") == "It's twenty one plus, two point five percent and 1st"
    assert con_tempi_whisper([{"show": "to", "start": 2, "end": 2.2, "score": -0.06}], [{"text": "to", "start": 0.5, "end": 0.6}])[0]["start"] == 2
    assert [x["start"] for x in con_tempi_whisper([{"show": "ten", "start": 1}, {"show": "Put", "start": 2}, {"show": "the", "start": 2.1}],
                                                   [{"text": " Put", "start": 5, "end": 5.2}, {"text": " the", "start": 2.2, "end": 2.3}])] == [1, 5, 2.1]
    _b = aggiungi_nei_buchi([{"show": "a", "start": 0, "end": 0.3}, {"show": "b", "start": 2.0, "end": 2.2}], [{"text": " see", "start": 0.8, "end": 1.0}, {"text": " a", "start": 0.05, "end": 0.3}])
    assert [x["show"] for x in _b] == ["a", "see", "b"], _b
    assert numeri_detti("you $10 ,000 to") == "you ten thousand dollars to"
    assert in_lettere(1999) == "one thousand nine hundred ninety nine" and numeri_detti("$1") == "one dollar"
    assert sposta_parole([{"show": "a", "start": 1, "end": 1.2}, {"show": "b", "start": 5, "end": 5.3}, {"show": "c", "start": 9, "end": 9.5}], [[14, 16], [10, 12]], 10) == \
        [{"show": "b", "start": 1.0, "end": 1.3}, {"show": "a", "start": 3.0, "end": 3.2}]
    _v = [{"show": "Who", "start": 0}, {"show": "are", "start": 0.25}, {"show": "you?", "start": 0.45}, {"show": "A", "start": 0.8}, {"show": "cat.", "start": 0.95}]
    _c = [{"show": x, "start": i * 0.3} for i, x in enumerate("Who are you today? Who are you today? Who are you today? I'm Claudia.".split())]
    _a = [{"text": x, "start": i * 0.3} for i, x in enumerate("Who are you today? Who are you today? You're a cat?".split())]
    assert [x["show"] for x in senza_cicli(_c, _a)] == "Who are you today? Who are you today? I'm Claudia.".split()
    assert senza_cicli(_c[:8], _a) == _c[:8] and senza_cicli([], []) == []
    _f = frasi_speedy(_v, {}, 3, parole_max=4)
    assert [[p["text"] for r in f["righe"] for p in r] for f in _f] == [["WHO", "ARE", "YOU?"], ["A", "CAT"]], _f  # "A CAT" è la risposta dell'altro: blocco suo anche se corto
    _f = frasi_speedy([{"show": x, "start": i * 0.25} for i, x in enumerate("He is going to Hong Kong, bro.".split())], {}, 3, parole_max=4)
    assert not any(r[-1]["text"] == "HONG" for f in _f for r in f["righe"]), _f
    assert all(f["end"] - f["start"] >= MIN_BLOCCO - 1e-9 for f in _f[:-1]), _f
    _r = ritocca_blocchi([{"start": 0, "end": 1, "righe": [[{"text": "TAKE", "start": 0}, {"text": "THAT", "start": 0.4}, {"text": "TO", "start": 0.8}]]}, {"start": 1.2, "end": 2, "righe": [[{"text": "SLEEP", "start": 1.2}]]},
                          {"start": 2.0, "end": 2.2, "righe": [[{"text": "BRO", "start": 2.0}]]}], 17)
    assert [" ".join(p["text"] for r in b["righe"] for p in r) for b in _r] == ["TAKE THAT", "TO SLEEP BRO"], _r
    _r = ritocca_blocchi([{"start": 0, "righe": [[{"text": "SO", "start": 0}, {"text": "WHAT’S", "start": 0.1}, {"text": "YOUR", "start": 0.2}, {"text": "DREAM", "start": 0.3}]]},
                          {"start": 0.6, "righe": [[{"text": "DESTINATION", "start": 0.6}, {"text": "ANTHONY?", "start": 1.0}]]}], 17)
    assert all(len(b["righe"]) <= 2 for b in _r), _r
    _w = [{"show": x, "start": i * 0.45} for i, x in enumerate("CJ tried to kill me, you forgot?".split())]
    fs = frasi_speedy(_w, {"cj": "ciano", "kill": "rosso"}, 4, parole_max=3)
    assert [" ".join(x["text"] for r in f["righe"] for x in r) for f in fs] == ["CJ TRIED", "TO KILL ME", "YOU FORGOT?"], fs
    assert [sum("fill" in x for r in f["righe"] for x in r) for f in fs] == [1, 1, 0]
    assert len(frasi_speedy([{"show": "kill", "start": 0}, {"show": "cj", "start": 0.3}], {"cj": "ciano", "kill": "rosso"}, 1, parole_max=3)[0]["righe"][0]) == 2
    assert filtro({"tipo": "riempitivo", "video": "x.mp4"}, "[0:v]", "[v]")[1] == 1076 and filtro({"tipo": "pieno"}, "", "", A=1440)[0].startswith("crop=810:1080:555:0,scale=1080:1440")
    assert grafo(D, 0, 1440)[1] == 704 and "crop=340:222:28:264,scale=1080:704" in grafo(D, 0, 1440)[0] and "scale=1080:730" in grafo(D, 0, 1440)[0]
    assert abs(salto([(0.93, 0.2), (1.27, 0.63), (9, 2)]) - 1.9) < 1e-9 and salto([(5, 1)]) == 0 and salto([]) == 0 and salto([(2.5, 4)]) == 6.5
    fs = speedy({"finale": {"t": 4.0, "testo": "x"}}, {"lampi": []}, [{"show": "Who", "start": 0}, {"show": "is", "start": 3.8}, {"show": "it", "start": 4.5}], 6, None, 1440, lambda x: x)["frasi"]
    assert all(f["end"] <= 4.0 for f in fs if not f.get("corsivo")) and fs[-1]["corsivo"] and fs[-1]["start"] == 4.25, fs
    # freccia sulla faccia (facce vere di Big Smoke e Kai a 0,4 s): punta 10-20 px fuori dalla faccia giusta, diretta al centro, piccola
    _facce = [(291, 443, 74, 74), (618, 458, 103, 103)]
    _parla = [{"start": 0, "end": 3, "baseline": 1060, "righe": [[{"text": "WHAT"}]]}]
    for _chi, _fc in (("sinistra", _facce[0]), ("destra", _facce[1])):
        _g, _e, _box = piazza_freccia({"t": 0.4, "durata": 2.3, "chi": _chi, "testo": "BIG SMOKE"}, lambda x: _facce, _parla, 711, 1440)
        _cx, _cy = _fc[0] + _fc[2] / 2, _fc[1] + _fc[3] / 2
        _dx, _dy = max(_fc[0] - _g["x"], 0, _g["x"] - _fc[0] - _fc[2]), max(_fc[1] - _g["y"], 0, _g["y"] - _fc[1] - _fc[3])
        assert 10 <= math.hypot(_dx, _dy) <= 20, (_chi, _g)  # punta appena fuori dal bordo
        _ux, _uy = FRECCIA_DIR[0] * _g["versoX"], FRECCIA_DIR[1]
        assert abs((_cx - _g["x"]) * _uy - (_cy - _g["y"]) * _ux) < 1 and (_cx - _g["x"]) * _ux > 0, _g  # la testa va verso il centro della faccia
        assert 60 <= _g["size"] <= 100 and not any(_tocca(_box["freccia"], (f[0], f[1], f[0] + f[2], f[1] + f[3])) for f in _facce)
        assert not _tocca(_box["etichetta"], _box["freccia"]) and not any(_tocca(_box["etichetta"], (f[0], f[1], f[0] + f[2], f[1] + f[3])) for f in _facce)
        assert _box["etichetta"][3] < ingombro(_parla[0], 711)[0] and abs(_e["end"] + 0.28 - (_g["t"] + _g["durata"])) < 1e-6
    assert piazza_freccia({"t": 0.4, "chi": "unica", "testo": "X"}, lambda x: _facce, [], 711, 1440) is None  # due facce: "unica" non sceglie a caso
    assert piazza_freccia({"t": 0.4, "chi": "sinistra", "testo": "X"}, lambda x: [] if x > 1 else _facce, [], 711, 1440) is None  # sparisce a metà: niente
    _g, _e, _ = piazza_freccia({"t": 0.4, "durata": 3.2, "chi": "sinistra", "testo": "X"}, lambda x: _facce if x < 2.5 else [], [], 711, 1440)
    assert abs(_g["durata"] - 2.1) < 1e-6 and "segui" not in _g  # si perde verso la fine: si ferma all'ultimo punto sicuro (2,4 s)
    _mosse = lambda x: [(291 + 40 * (x - 0.4), 443, 74, 74), (618, 458, 103, 103)]  # Big Smoke che scivola a destra di 40 px al secondo
    _g, _e, _ = piazza_freccia({"t": 0.4, "durata": 2.3, "chi": "sinistra", "testo": "X"}, _mosse, [], 711, 1440)
    assert _g["segui"][-1] == [2.25, 88, 0] and _g["segui"] == _e["segui"] and _g["segui"][0] == [0, 0, 0]  # freccia ed etichetta seguono la faccia
    assert piazza_freccia({"t": 0.4, "chi": "sinistra", "testo": "X"}, lambda x: [(291 + 400 * (x - 0.4), 443, 74, 74)], [], 711, 1440) is None  # scappa: niente
    assert piazza_freccia({"t": 0.4, "chi": "unica", "testo": "X"}, lambda x: [(5, 5, 1070, 1300)], [], 711, 1440) is None  # nessun posto: niente
    # icone legate al sottotitolo: centrate, subito sopra o subito sotto, entro 30 px dal testo e senza toccarlo
    _f = [{"start": 1.0, "end": 3.0, "righe": [[{"text": "MONEY"}]]}]
    _a, _b = ingombro(_f[0], 711)
    _su, = posa_icone([{"t": 1.5, "emoji": "💵", "size": 100}], _f, 711, 1440)
    _giu, = posa_icone([{"t": 1.5, "emoji": "💵", "size": 100, "dove": "sotto"}], _f, 711, 1440)
    assert _su["x"] == _giu["x"] == 540 and 0 < _a - (_su["y"] + 50) <= 30 and 0 < (_giu["y"] - 50) - _b <= 30, (_su, _giu)
    assert _su["t"] == 1.5 and abs(_su["t"] + _su["durata"] - 3.28) < 1e-6
    _alto, = posa_icone([{"t": 1.5, "emoji": "💵", "size": 100}], [{**_f[0], "baseline": 90}], 711, 1440)  # in cima al quadro: va sotto
    assert _alto["y"] - 50 > 90 and _alto["size"] == 100
    _stretta, = posa_icone([{"t": 1.5, "emoji": "💵", "size": 300}], [{**_f[0], "baseline": 330}, {"start": 0, "end": 5, "baseline": 711, "righe": [[{"text": "X"}]]}], 711, 1440)
    assert _stretta["size"] < 300 and _stretta["y"] - _stretta["size"] / 2 >= 10, _stretta  # poco posto da tutte e due le parti: si rimpicciolisce
    _p = speedy({"vibe": "serio", **VIBE["serio"]}, {"lampi": []}, [{"show": "hi", "start": 0}], 2, None, 1440, lambda x: x)
    assert "luce" not in _p and _p["saturazione"] == 0.6 and all("fill" not in p for f in _p["frasi"] for r in f["righe"] for p in r)
    _p = speedy({"frasi_colorate": [{"t": 0.1, "colore": "rosa"}], "colori": {"mom": "verde"}}, {"lampi": []}, [{"show": "my", "start": 0}, {"show": "mom", "start": 0.3}], 2, None, 1440, lambda x: x)
    assert _p["luce"] == LUCE and [p["fill"] for p in _p["frasi"][0]["righe"][0]] == [PALETTA["rosa"]["fill"], PALETTA["verde"]["fill"]]
    _p = speedy({"finale": {"emoji": "😂", "testo": "x"}}, {"lampi": []}, [{"show": "hi", "start": 0}], 6, None, 1440, lambda x: x)
    assert [(g["x"], g["y"]) for g in _p["grafiche"] if g["tipo"] == "emoji"] == [(540, 511)]  # emoji del finale al centro, dov'era (Riccardo, 11 nov)
    assert riga_libera(711, [], 1440) == 711 and riga_libera(711, [(313, 340, 165, 165)], 1440) == 711 and riga_libera(711, [(0, 600, 150, 200)], 1440) == 711
    assert riga_libera(711, [(300, 500, 480, 500)], 1440) == 1092 and riga_libera(711, [(300, 500, 480, 760)], 1440) == 395  # sotto il mento, o sopra la testa se sotto non c'è posto
    if len(sys.argv) > 1:
        main()
