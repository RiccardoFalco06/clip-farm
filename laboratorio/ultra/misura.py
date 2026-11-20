"""Misure di UNA clip finita (nostra o di Speedy) prese dal video e dall'audio, mai dalla scheda: le due clip di un
confronto si misurano allo stesso modo. Sostituisce strumenti/pacco_valutazione.py per il confronto (quello legge la
scheda, cioè quello che volevamo mettere, e non funziona sugli originali).

uso: ~/Projects/video-editor/.venv/bin/python -I ultra/misura.py CLIP.mp4 CARTELLA [--sorgente LIVE.mp4]
  CARTELLA/fotogrammi/f_CCCCC.jpg  tutti i fotogrammi (fps della clip, almeno 20), 432 px, CCCCC = tempo in centesimi
  CARTELLA/fogli/foglio_NN.jpg     4 al secondo, 24 per foglio, tempo stampato sopra
  CARTELLA/misure.json             formato, layout, stacchi, lampi, scritte (OCR) con tempi/posizione/colore, parole
                                   dette (Whisper) e ritardo dei sottotitoli, volume, musica, suoni aggiunti, e con
                                   --sorgente i pezzi della live usati (mappa tempo clip -> tempo live dall'audio)
"""
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal

QUI = Path(__file__).resolve().parent
LAB = QUI.parent
FARM = LAB.parent
VE = Path.home() / "Projects/video-editor"
sys.path.insert(0, str(LAB / "strumenti"))
import vid  # noqa: E402
import audio as au  # noqa: E402


def run(*a, **k):
    return subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True, **k)


def sonda(clip):
    j = json.loads(run("ffprobe", "-v", "0", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration", "-of", "json", clip).stdout)
    s = j["streams"][0]
    n, d = map(float, s["r_frame_rate"].split("/"))
    return {"durata": round(float(j["format"]["duration"]), 3), "w": s["width"], "h": s["height"], "fps": round(n / d, 3)}


def fotogrammi(clip, out, fps):
    """Tutti i fotogrammi (Riccardo: almeno 20 al secondo) e i fogli a 4 fps per guardarli."""
    (out / "fotogrammi").mkdir(parents=True, exist_ok=True)
    (out / "fogli").mkdir(exist_ok=True)
    run("ffmpeg", "-v", "error", "-y", "-i", clip, "-vf", f"fps={fps},scale=432:-2", "-q:v", "5", out / "fotogrammi" / "tmp_%05d.jpg")
    for f in sorted((out / "fotogrammi").glob("tmp_*.jpg")):
        f.rename(f.with_name(f"f_{round((int(f.stem[4:]) - 1) / fps * 100):05d}.jpg"))
    run("ffmpeg", "-v", "error", "-y", "-i", clip, "-vf",
        "fps=4,scale=270:-2,drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial Bold.ttf:text='%{pts\\:flt}':x=6:y=6:fontsize=26:fontcolor=yellow:box=1:boxcolor=black,tile=6x4",
        out / "fogli" / "foglio_%02d.jpg")


def stacchi(clip, fps, lampi):
    """Cambi d'inquadratura dai pixel: salto forte tra due fotogrammi che non torna indietro (un lampo torna)."""
    g = np.array([f.astype(np.float32).mean(axis=2) for f in vid.flusso(str(clip), fps=fps, larg=64)])
    # luminosità e contrasto tolti da ogni fotogramma: luce lampeggiante, lampi e B/N cambiano tutto il quadro ma non la forma
    # (misurato su lunga2_expedia: stacchi veri 0,30-0,62, effetti 0,03-0,13)
    g = (g - g.mean(axis=(1, 2), keepdims=True)) / (g.std(axis=(1, 2), keepdims=True) + 1e-6)
    d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))
    out = []
    for i in range(1, len(d) - 5):
        base = np.median(d[max(0, i - 15): i + 15]) + 1e-6
        resta = np.abs(g[i + 5] - g[max(0, i - 1)]).mean()  # 5 fotogrammi dopo è ancora diverso da prima?
        if d[i] > max(0.2, 4 * base) and resta > 0.2 and d[i] >= d[max(0, i - 1)] and d[i] >= d[i + 1]:
            t = round((i + 1) / fps, 3)
            if not any(abs(t - l["t"]) < 0.1 for l in lampi) and (not out or t - out[-1] > 0.2):
                out.append(t)
    return out


def bianco_nero(clip, fps=10):
    """Tratti in bianco e nero (saturazione mediana quasi zero per almeno 0,2 s: emoji e scritte colorate sopra non contano)."""
    sat = [float(np.median(f.max(axis=2).astype(np.int16) - f.min(axis=2))) for f in vid.flusso(str(clip), fps=fps, larg=64)]
    out, da = [], None
    for i, v in enumerate(sat + [99]):
        if v < 6 and da is None:
            da = i
        elif v >= 6 and da is not None:
            if i - da >= 2:
                out.append([round(da / fps, 1), round(i / fps, 1)])
            da = None
    return out


def lampi(clip):
    return json.loads(run(sys.executable, "-I", LAB / "strumenti/lampi_tutti.py", clip).stdout)["lampi"]


def layout(clip):
    righe = [l.split() for l in run(sys.executable, "-I", LAB / "strumenti/giunzione.py", clip, "2").stdout.splitlines() if l.startswith("riga")]
    # una giunzione vera (riquadri impilati) ha un salto mediano alto e sta tra il 30% e il 70% dell'altezza
    forti = [(float(r[2].strip("()")), float(r[5])) for r in righe if float(r[5]) > 25 and 0.3 < float(r[2].strip("()")) < 0.7]
    return {"tipo": "diviso" if forti else "pieno", "giunzioni": [round(y, 3) for y, _ in forti]}


def norm(s):
    return re.sub(r"[^A-Z0-9*?!']", "", s.upper())


def scritte(clip, out, fps=10):
    """Scritte a schermo con l'OCR di Vision a 10 fps. Toglie quelle fisse (firma, marchi). Colore = mediana dei pixel più accesi e saturi nel riquadro."""
    tmp = out / "_ocr"
    tmp.mkdir(exist_ok=True)
    run("ffmpeg", "-v", "error", "-y", "-i", clip, "-vf", f"fps={fps},scale=720:-2", "-q:v", "3", tmp / "o_%05d.jpg")
    files = sorted(tmp.glob("o_*.jpg"))
    letti = []
    for i in range(0, len(files), 200):
        letti += [json.loads(l) for l in run(LAB / "strumenti/testi", *files[i:i + 200]).stdout.splitlines()]
    colori = []
    for k, f in enumerate(vid.flusso(str(clip), fps=fps, larg=720)):
        if k >= len(letti):
            break
        cc = []
        for t in letti[k]["t"]:
            x, y, w, h = (int(t[q]) for q in "xywh")
            p = f[max(0, y):y + h, max(0, x):x + w].reshape(-1, 3).astype(np.float32)
            if len(p) == 0:
                cc.append(None)
                continue
            forza = p.max(1) + (p.max(1) - p.min(1))
            sel = p[forza >= np.percentile(forza, 85)]
            cc.append("#%02x%02x%02x" % tuple(int(v) for v in np.median(sel, axis=0)))
        colori.append(cc)
    H = vid.dims(str(clip))[1] * 720 / vid.dims(str(clip))[0]
    simile = lambda u, v: difflib.SequenceMatcher(None, u, v).ratio()
    fascia = lambda t: round((t["y"] + t["h"] / 2) / H / 0.04)
    # scritte fisse (firma, marchi): stessa fascia in più di metà dei fotogrammi e testo quasi uguale ogni volta (l'OCR legge
    # la firma un po' diversa a ogni fotogramma: @SPEEDYBOYKINS, @SPEEUYBOYKINS...)
    per_fascia = {}
    for r in letti:
        for t in r["t"]:
            per_fascia.setdefault(fascia(t), []).append(norm(t["s"]))
    fisse = {}
    for f_, testi in per_fascia.items():
        moda = max(set(testi), key=testi.count)
        if len(moda) > 3 and sum(simile(x, moda) > 0.7 for x in testi) > 0.5 * len(letti):
            fisse[f_] = moda
    eventi, aperti = [], {}  # una scritta per fascia; la frase che si costruisce resta un evento solo, con il tempo di ogni parola
    for k, r in enumerate(letti):
        ora = round(k / fps, 2)
        visti = set()
        for j, t in enumerate(r["t"]):
            s, f_ = norm(t["s"]), fascia(t)
            if t["c"] < 0.5 or not s or (f_ in fisse and simile(s, fisse[f_]) > 0.5):
                continue
            visti.add(f_)
            e = aperti.get(f_)
            if e and (s == e["_n"] or simile(s, e["_n"]) > 0.8):
                pass
            elif e and s.startswith(e["_n"]):  # parola nuova nella stessa frase
                e["parole"].append([t["s"].split()[-1], ora])
            else:
                if e:
                    eventi.append(aperti.pop(f_))
                e = aperti[f_] = {"da": ora, "parole": [[w, ora] for w in t["s"].split()], "y": round((t["y"] + t["h"] / 2) / H, 3),
                                  "altezza_lettere": round(t["h"] / H, 3), "x": round((t["x"] + t["w"] / 2) / 720, 3), "colori": []}
            if len(s) >= len(e.get("_n", "")):
                e["_n"], e["testo"] = s, t["s"]
            c = colori[k][j] if k < len(colori) else None
            if c and c not in e["colori"] and len(e["colori"]) < 6:
                e["colori"].append(c)
            e["a"] = round((k + 1) / fps, 2)
        for f_ in [f_ for f_ in aperti if f_ not in visti]:
            eventi.append(aperti.pop(f_))
    eventi += aperti.values()
    eventi = [{k: v for k, v in e.items() if k != "_n"} for e in eventi if e["a"] - e["da"] >= 0.2]  # 1 fotogramma = lettura sbagliata
    for f in files:
        f.unlink()
    tmp.rmdir()
    return {"fisse": sorted(fisse.values()), "eventi": sorted(eventi, key=lambda e: e["da"])}


def audio_parti(clip, out):
    """Voce e resto (musica + suoni + gioco) con Demucs, parole con Whisper. Passi pesanti: prende il blocco condiviso."""
    asr = out / "asr"
    if not (asr / "whisper.json").exists():
        lock = FARM / "state/catena.lock"
        while True:
            try:
                lock.mkdir()
                break
            except FileExistsError:
                subprocess.run(["sleep", "5"])
        try:
            run(VE / ".venv-align/bin/python", "-I", "scripts/extract_audio.py", Path(clip).resolve(), asr.resolve(), cwd=VE)
            run(VE / ".venv/bin/python", "-I", FARM / "trascrivi.py", asr.resolve())
        finally:
            lock.rmdir()
    resto = next((asr / "demucs").rglob("no_vocals.wav"))
    return asr, resto, json.loads((asr / "whisper.json").read_text()).get("words", [])


def lufs(f):
    err = subprocess.run(["ffmpeg", "-nostdin", "-i", str(f), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    v = re.findall(r"I:\s*(-?[\d.]+) LUFS", err)
    return float(v[-1]) if v else None


def musica(resto):
    """Brano della nostra libreria più simile (spettro a bande, come confronta_musica.py) su tre tratti del resto dell'audio."""
    import confronta_musica as cm
    x = cm.audio(str(resto))
    dur = len(x) / cm.SR
    tratti = [cm.bande(x[int(t * cm.SR): int((t + 8) * cm.SR)]) for t in (2, dur / 2 - 4, dur - 10) if t >= 0 and t + 8 <= dur]
    voti = []
    for m in sorted((FARM / "musica").glob("*.m4a")):
        b = cm.bande(cm.audio(str(m)))
        voti.append((round(float(np.mean([cm.punteggio(t, b) for t in tratti])), 3), m.name))
    return sorted(voti, reverse=True)[:3]


def shazam(resto, out):
    """Titolo del brano con Shazam (manda solo l'impronta audio), riusa strumenti/riconosci.py."""
    cart = out / "_shazam"
    (cart / "riferimenti").mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(resto), str(cart / "resto.wav")], check=True)
    r = subprocess.run([str(LAB / ".venv-audio/bin/python"), "-I", str(LAB / "strumenti/riconosci.py"), "resto.wav"], cwd=cart, capture_output=True, text=True, timeout=600)
    f = cart / "riferimenti/musica.json"
    return json.loads(f.read_text()).get("resto", []) if f.exists() else {"errore": r.stderr[-300:]}


def titolo_musica(resto, out):
    """Un nome solo per confrontare le due clip: se il brano è uno della nostra libreria (somiglianza ≥ 0,5: il vero dava 0,61-0,64,
    il secondo 0,17) vale il titolo Shazam di quel file (ultra/musica_titoli.json); altrimenti il titolo Shazam più ripetuto."""
    lib = musica(resto)
    titoli = json.loads((QUI / "musica_titoli.json").read_text()) if (QUI / "musica_titoli.json").exists() else {}
    if lib and lib[0][0] >= 0.5:
        t = titoli.get(lib[0][1][:-4]) or []
        return max(t, key=lambda x: len(x["tratti"]))["titolo"] if t else lib[0][1]  # Shazam a volte sente brani diversi su tratti diversi
    sh = json.loads((out / "_shazam/riferimenti/musica.json").read_text()).get("resto", []) if (out / "_shazam/riferimenti/musica.json").exists() else []
    return max(sh, key=lambda x: len(x["tratti"]))["titolo"] if sh else None


def suoni_aggiunti(resto, parole):
    """Attacchi forti nel resto dell'audio (senza voce) e quali file della nostra libreria ci si trovano."""
    ev = [{"t": round(t, 2), "banda": b, "forza": round(z, 1)} for t, b, z in au.eventi(str(resto), soglia=3.5)]
    trovati = []
    for cart in (FARM / "suoni/approvati", FARM / "suoni/scartati"):
        trovati += [{"file": s, "t": round(t, 2), "somiglianza": round(n, 2)} for n, t, s in au.cerca(str(resto), str(cart), soglia=0.4)]  # veri 0,43-0,75, primo falso 0,35 (lunga2_expedia)
    return {"attacchi": ev, "dalla_libreria": trovati}


def ritardo_sottotitoli(eventi, parole):
    """Per ogni scritta che è una parola detta: inizio della scritta meno inizio della parola (positivo = sottotitolo in ritardo)."""
    dette = [(norm(w["text"]), w["start"]) for w in parole]
    out = []
    for e in eventi:
        for w, quando in e["parole"]:  # ogni parola mostrata contro la stessa parola detta più vicina
            vicine = [t for s, t in dette if s and s == norm(w) and abs(t - quando) < 1.5]
            if vicine:
                out.append(round(quando - min(vicine, key=lambda t: abs(t - quando)), 2))
    return {"misurati": len(out), "mediana": float(np.median(out)) if out else None, "peggiore": max(out, key=abs) if out else None, "valori": out}


DEBUG = ""


def mappa(voce, sorgente, passo=0.25, finestra=1.0, SR=4000):
    """Da dove viene ogni pezzo della clip: la voce della clip (Demucs: senza musica e suoni) cercata nell'audio della live.
    Banda voce, spettro sbiancato su tutto il file (così le parti forti della live non vincono sempre), correlazione normalizzata
    per finestre da 1 s; un pezzo vale se almeno 3 finestre di fila danno lo stesso punto della live (±0,05 s).
    Pezzi più corti di ~1,5 s possono mancare: gli stacchi dai pixel restano la misura dei tagli.
    Ritorna [{"clip": [da, a], "live": [da, a], "finestre": n}]."""
    def carica(f):
        raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(f), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
        x = signal.sosfilt(signal.butter(4, [150, 1900], "bp", fs=SR, output="sos"), np.frombuffer(raw, np.float32))
        X = np.fft.rfft(x)
        liscio = np.convolve(np.abs(X), np.ones(201) / 201, "same")  # ~±10 Hz su un file di qualche minuto
        return np.fft.irfft(X / (liscio + 1e-9), len(x))
    x, y = carica(voce), carica(sorgente)
    L = int(finestra * SR)
    e = np.sqrt(np.maximum(signal.fftconvolve(y ** 2, np.ones(L), "valid"), 1e-12))
    candidati = []  # per ogni finestra: (t, [scarti possibili live - clip])
    for t in np.arange(0, len(x) / SR - finestra, passo):
        seg = x[int(t * SR): int(t * SR) + L]
        c = signal.fftconvolve(y, seg[::-1], "valid") / (e * np.linalg.norm(seg) + 1e-9)
        picchi, _ = signal.find_peaks(c, distance=SR // 10)
        top = picchi[np.argsort(c[picchi])[-5:]]
        candidati.append((round(float(t), 2), [(i / SR - t, float(c[i])) for i in top]))
    catene = []  # catene aperte: {"scarto", "da", "a", "n"}
    for t, scarti in candidati:
        for k in catene:
            presi = [v for o, v in scarti if abs(o - k["scarto"]) < 0.05]
            if k["a"] >= t - passo - 1e-6 and presi:
                k["a"], k["n"], k["ncc"] = t, k["n"] + 1, k["ncc"] + max(presi)
                scarti = [(o, v) for o, v in scarti if abs(o - k["scarto"]) >= 0.05]
        catene += [{"scarto": o, "da": t, "a": t, "n": 1, "ncc": v} for o, v in scarti]
    for k in catene:
        k["ncc"] /= k["n"]
    if DEBUG:
        for k in sorted(catene, key=lambda k: -k["n"])[:40]:
            print(DEBUG, round(k["da"], 2), round(k["a"], 2), round(k["scarto"], 2), k["n"], round(k["ncc"], 3))
    # le finestre si sovrappongono, quindi un falso allineamento dura qualche finestra: su una clip con musica forte i falsi
    # arrivavano a 4 finestre con correlazione ≤ 0,20, i veri da 6 finestre in su con 0,16-0,63 (prova sintetica su expedia)
    buone = sorted([k for k in catene if k["n"] >= 5 or (k["n"] >= 3 and k["ncc"] >= 0.3)], key=lambda k: -k["n"] * k["ncc"])
    tenute = []
    for k in buone:  # ogni tratto di clip ha una sola origine: vince la catena più lunga
        if all(k["a"] + finestra <= q["da"] or k["da"] >= q["a"] + finestra - 0.5 for q in tenute):
            tenute.append(k)
    # un pezzo corto lontano più di 90 s da tutti gli altri è un falso (visto: il fermo immagine finale "trovato" a 37 s di una live
    # i cui pezzi stanno tutti tra 285 e 368 s); la live scaricata contiene solo il tratto dei pezzi, quindi è raro
    tenute = [k for k in tenute if k["n"] >= 6 or len(tenute) < 3 or any(abs((q["da"] + q["scarto"]) - (k["da"] + k["scarto"])) < 90 for q in tenute if q is not k)]
    return [{"clip": [k["da"], round(k["a"] + finestra, 2)], "live": [round(k["da"] + k["scarto"], 2), round(k["a"] + finestra + k["scarto"], 2)], "finestre": k["n"]}
            for k in sorted(tenute, key=lambda k: k["da"])]


def misura(clip, out, sorgente=None):
    out.mkdir(parents=True, exist_ok=True)
    info = sonda(clip)
    fps = min(30, max(20, round(info["fps"])))
    fotogrammi(clip, out, fps)
    lp = lampi(clip)
    sc = scritte(clip, out)
    asr, resto, parole = audio_parti(clip, out)
    m = {
        **info, "formato": f"{info['w']}x{info['h']} ({info['w'] / info['h']:.3f})", "fotogrammi_fps": fps,
        "layout": layout(clip), "stacchi": stacchi(clip, fps, lp), "lampi": lp, "bianco_nero": bianco_nero(clip),
        "scritte": sc, "parole_dette": [[w["text"].strip(), round(w["start"], 2), round(w["end"], 2)] for w in parole],
        "ritardo_sottotitoli": ritardo_sottotitoli(sc["eventi"], parole),
        "volume": {"tutto_lufs": lufs(clip), "voce_lufs": lufs(asr / "vocals.wav"), "resto_lufs": lufs(resto)},
        "musica_libreria": musica(resto), "musica_shazam": shazam(resto, out),
        "musica_titolo": titolo_musica(resto, out), "suoni": suoni_aggiunti(resto, parole),
    }
    if sorgente:
        m["pezzi_live"] = mappa(asr / "vocals.wav", sorgente)
    (out / "misure.json").write_text(json.dumps(m, ensure_ascii=False, indent=1))
    return m


if __name__ == "__main__":
    a = sys.argv[1:]
    src = a[a.index("--sorgente") + 1] if "--sorgente" in a else None
    m = misura(Path(a[0]), Path(a[1]), src)
    print(json.dumps({k: (v if k in ("durata", "formato", "layout", "stacchi", "lampi", "volume", "musica_libreria") else "...") for k, v in m.items()}, ensure_ascii=False)[:2000])
