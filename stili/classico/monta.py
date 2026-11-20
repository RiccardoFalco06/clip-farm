"""Monta una clip dalla scheda scritta dal selezionatore.

uso: python3 -I monta.py scheda.json   -> lavoro/<id>/finale.mp4 (e copia in `uscita` se indicata)
Passi: taglio e layout (ffmpeg) -> parole sincronizzate (script della skill animated-captions, MMS)
       -> sottotitoli, lampi, suoni, musica (Remotion, remotion/src/Clip.tsx).
"""
import array
import functools
import http.server
import json
import math
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
VE = Path.home() / "Projects/video-editor"  # progetto della skill dei sottotitoli
PRESET = json.loads((QUI / "remotion/presets.json").read_text())
COLORI = {"magenta": "#F506F5", "ciano": "#08D8F8"}  # misurati sulle clip di riferimento
CENSURA = {"fuck": "F*CK", "fucking": "F*CKING", "shit": "SH*T", "bitch": "B*TCH", "nigga": "N***A", "niggas": "N***AS", "ass": "A*S", "dick": "D*CK", "pussy": "P*SSY", "motherfucker": "MF", "motherfucking": "MF"}


def run(*cmd, cwd=None):
    subprocess.run([str(c) for c in cmd], check=True, cwd=cwd)


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


def filtro(L, ing, usc, k="", y=480):
    """Il pezzo di filtergraph che porta `ing` nel formato 1080x1920 `usc`, e l'altezza della giunzione dove sta la parola."""
    H = L.get("utile", 1080)  # sotto questa altezza ci sono i sottotitoli che lo streamer ha già nella sua live: restano fuori
    if L["tipo"] == "diviso":  # facecam sopra, gioco sotto: il layout delle clip di gioco di riferimento
        fx, fy, fw, fh = L["facecam"]
        alto = round(1080 * fh / fw / 2) * 2
        basso = 1920 - alto
        gw = round(1080 * H / basso / 2) * 2  # larghezza del gioco che riempie la parte bassa a tutta altezza
        gx = min(max(0, L.get("gioco_cx", 960) - gw // 2), 1920 - gw)
        return (f"{ing}split[a{k}][b{k}];[a{k}]crop={fw}:{fh}:{fx}:{fy},scale=1080:{alto}:flags=lanczos[t{k}];"
                f"[b{k}]crop={gw}:{H}:{gx}:0,scale=1080:{basso}:flags=lanczos[g{k}];[t{k}][g{k}]vstack{usc}"), alto
    if L["tipo"] == "fascia":  # live senza webcam: fascia larga al centro su sfondo sfocato, così il soggetto non esce mai dal ritaglio
        cw = 1216
        cx = min(max(0, L.get("cx", 960) - cw // 2), 1920 - cw)
        # parola appena sopra la fascia: sotto ci sono spesso i sottotitoli che lo streamer ha già nella sua live
        return (f"{ing}split[a{k}][b{k}];[a{k}]scale=-2:1920,crop=1080:1920,boxblur=24:4,eq=brightness=-0.12[s{k}];"
                f"[b{k}]crop={cw}:{H}:{cx}:0,scale=1080:{round(1080 * H / cw / 2) * 2}:flags=lanczos[f{k}];[s{k}][f{k}]overlay=0:{y}{usc}"), y - 72
    cw = 608  # pieno: zoom stretto sul soggetto
    cx = min(max(0, L.get("cx", 960) - cw // 2), 1920 - cw)
    return f"{ing}crop={cw}:1080:{cx}:0,scale=1080:1920:flags=lanczos{usc}", None  # shortcut: il pieno non toglie i sottotitoli dello streamer; oggi nessuno lo sceglie


def grafo(L, inizio):
    """Filtergraph di tutta la clip. Layout "misto" (la scena cambia a metà, es. webcam che va a schermo intero): ogni tratto
    col suo layout, sovrapposto al primo solo nei suoi secondi; la fascia scende sotto la giunzione così la parola resta dov'è."""
    if L["tipo"] != "misto":
        vf, giunzione = filtro(L, "[0:v]fps=30,", "[v]")
        return vf, giunzione
    tratti = L["tratti"]  # [[da (secondi della sorgente), layout], ...]: il primo vale dall'inizio
    giunzione = next((filtro(l, "", "")[1] for _, l in tratti if l["tipo"] == "diviso"), 408)
    y = min(giunzione + 72, 960)
    pezzi = [f"[0:v]fps=30,split={len(tratti)}" + "".join(f"[i{k}]" for k in range(len(tratti)))]
    pezzi += [filtro(l, f"[i{k}]", f"[o{k}]", k, y)[0] for k, (_, l) in enumerate(tratti)]
    for k in range(1, len(tratti)):
        fino = f"*lt(t,{tratti[k + 1][0] - inizio:.3f})" if k + 1 < len(tratti) else ""
        pezzi.append(f"[{'o0' if k == 1 else f'm{k - 1}'}][o{k}]overlay=enable='gte(t,{tratti[k][0] - inizio:.3f}){fino}'" + ("[v]" if k + 1 == len(tratti) else f"[m{k}]"))
    return ";".join(pezzi), giunzione


def layout(s, dst):
    """Ritaglia la sorgente nel formato finale 1080x1920."""
    vf, giunzione = grafo(s["layout"], s["inizio"])
    run("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", s["inizio"], "-t", s["fine"] - s["inizio"], "-i", s["sorgente"],
        "-filter_complex", vf, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
        "-c:a", "aac", "-b:a", "192k", dst)
    return giunzione


def fermi(video, minimo=0.5):
    """[(secondo, durata)] dei tratti in cui tutta l'immagine resta ferma almeno `minimo` secondi: anche gli scatti brevi.
    In una live c'è sempre qualcosa che si muove (webcam, chat): un fermo è un download o una registrazione rovinata, oppure
    fa parte della scena (lo streamer ha staccato tutto). Lo decide il controllo qualità (qualita.py).
    Soglia 0.0001 = fotogrammi identici: con 0.001 uno streamer immobile in posa contava come blocco (misurato: 4 falsi allarmi
    in una clip buona, 1 con 0.0001 e lungo 0,43 s; il download rovinato di Kick dà 3 fermi da 2 s con qualsiasi soglia)."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(video), "-vf", f"freezedetect=n=0.0001:d={minimo}", "-map", "0:v", "-f", "null", "-"], capture_output=True, text=True)
    return list(zip(map(float, re.findall(r"freeze_start: ([\d.]+)", r.stderr)), map(float, re.findall(r"freeze_duration: ([\d.]+)", r.stderr))))


def parole(base, d):
    """Parole con tempi precisi: voce isolata e allineamento della skill animated-captions (Demucs, MMS); testo da trascrivi.py."""
    py, pya = VE / ".venv/bin/python", VE / ".venv-align/bin/python"
    run(pya, "-I", "scripts/extract_audio.py", base, d, cwd=VE)
    run(py, "-I", QUI / "trascrivi.py", d)
    grezze = json.loads((d / "whisper.json").read_text())
    testo = grezze["text"].strip()
    if not testo:
        return []
    (d / "transcript.txt").write_text("\n".join(x.strip() for x in re.split(r"(?<=[.!?])\s+", testo) if x.strip()) + "\n")
    run(pya, "-I", "scripts/align.py", d / "vocals.wav", d / "transcript.txt", "eng", d / "align.json", cwd=VE)
    run(pya, "-I", "scripts/refine.py", d / "vocals.wav", d / "align.json", d / "words.json", "--fps", "30", cwd=VE)
    w = json.loads((d / "words.json").read_text())
    # se Whisper ha saltato del parlato, l'allineatore spalma le parole sul vuoto: lì valgono i tempi di Whisper
    if len(w) == len(grezze["words"]):
        for a, g in zip(w, grezze["words"]):
            if abs(a["start"] - g["start"]) > 1.0:
                a["start"], a["end"] = g["start"], g["end"]
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


def main():
    s = json.loads(Path(sys.argv[1]).read_text())
    d = QUI / "lavoro" / s["id"]
    d.mkdir(parents=True, exist_ok=True)
    base = d / "base.mp4"
    # taglio e parole si rifanno solo se cambia il taglio: ritoccare effetti e suoni costa solo il render
    taglio = {k: s.get(k) for k in ("sorgente", "inizio", "fine", "layout")}
    chiesto = s["inizio"]
    memo = d / "taglio.json"
    if memo.exists() and (m := json.loads(memo.read_text()))["taglio"] == taglio:
        s["inizio"], s["fine"] = m["agganciato"]
        giunzione, w = m["giunzione"], json.loads((d / "words.json").read_text())
    else:
        t0 = time.time()
        s["inizio"], s["fine"] = aggancia(s)
        giunzione = layout(s, base)
        t1 = time.time()
        w = parole(base, d)
        memo.write_text(json.dumps({"taglio": taglio, "giunzione": giunzione, "agganciato": [s["inizio"], s["fine"]]}))
        print(f"tempi: taglio {t1 - t0:.0f} s, parole {time.time() - t1:.0f} s", file=sys.stderr)

    durata = s["fine"] - s["inizio"]
    anticipo = chiesto - s["inizio"]  # i tempi degli effetti erano contati dall'inizio chiesto

    def t(x):
        """Tempo di un effetto: secondi dall'inizio della clip, oppure una parola ("shit", "oh@20" = l'"oh" più vicino al secondo 20)."""
        if not isinstance(x, str):
            return x + anticipo
        chiave, _, vicino = x.partition("@")
        vicino = float(vicino) + anticipo if vicino else ""
        volte = [p["start"] for p in w if re.sub(r"[^\w]", "", p["show"]).lower() == chiave.lower()]
        if not volte:  # la trascrizione finale può differire da quella vista dal selezionatore: salta l'effetto, non la clip
            print(f"effetto saltato, parola assente: {x!r}", file=sys.stderr)
            return None
        return min(volte, key=lambda v: abs(v - float(vicino or v)))

    def effetti(nome):
        return [{**x, "t": t(x["t"])} for x in s.get(nome, []) if t(x["t"]) is not None]

    riga = dict(PRESET["outline"]["line"])
    if giunzione:  # nel layout diviso la parola sta sulla giunzione tra facecam e gioco
        riga.update(size=150, stroke=17, baseline=giunzione + 52)

    # Remotion legge video e suoni da un server locale: niente copie di file grossi dentro il bundle
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(QUI)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = lambda rel: f"http://127.0.0.1:{srv.server_address[1]}/{rel}"

    vol_musica = 0
    if s.get("musica"):
        # nelle clip di riferimento la musica sta 3-8 dB sotto la voce; qui 10 perché sotto c'è già l'audio del gioco
        sotto = s["musica"].get("db_sotto_voce", 10)
        vol_musica = round(min(1.0, 10 ** ((lufs(d / "vocals.wav") - sotto - lufs(QUI / "musica" / s["musica"]["file"])) / 20)), 4)

    props = {
        "video": url(f"lavoro/{s['id']}/base.mp4"), "width": 1080, "height": 1920, "durata": durata, "riga": riga,
        "gruppi": gruppi(w, s.get("enfasi", {}), durata),
        "lampi": effetti("lampi"), "zoom": effetti("zoom"),
        "suoni": [{"t": max(0, x["t"] + x.get("anticipo", 0)), "file": url(f"suoni/approvati/{x['file']}"), "volume": x.get("volume", 0.8)} for x in effetti("suoni")],
        **({"musica": {"file": url(f"musica/{s['musica']['file']}"), "volume": vol_musica}} if s.get("musica") else {}),
        **({"firma": s["firma"]} if s.get("firma") else {}),
    }
    (d / "props.json").write_text(json.dumps(props, ensure_ascii=False, indent=1))
    lavoro = d / "job.json"
    lavoro.write_text(json.dumps([{"id": "Clip", "media": True, "out": str(d / "finale.mp4"), "props": props}]))
    t0 = time.time()
    run("node", "render.mjs", lavoro, cwd=QUI / "remotion")
    print(f"tempi: render {time.time() - t0:.0f} s per {durata:.0f} s di clip", file=sys.stderr)
    srv.shutdown()
    if s.get("uscita"):
        # volume finale a -14 LUFS, quello a cui le piattaforme riportano i video
        # limitatore dopo loudnorm; la codifica AAC può comunque far risalire i picchi fino a 0 dB (visto dal controllo qualità su un beep):
        # si misura il file finito e, se serve, si rifà una volta abbassando di quanto manca a -1 dB
        uscita, filtri = Path(s["uscita"]).expanduser(), "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.794:level=false"
        for _ in range(2):
            run("ffmpeg", "-nostdin", "-v", "error", "-y", "-i", d / "finale.mp4", "-c:v", "copy", "-af", filtri,
                "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", uscita)
            picco = float(re.search(r"max_volume: (-?[\d.]+) dB", subprocess.run(["ffmpeg", "-nostdin", "-i", str(uscita), "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr).group(1))
            if picco <= -1:
                break
            filtri += f",volume={-1.2 - picco:.1f}dB"
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
    if len(sys.argv) > 1:
        main()
