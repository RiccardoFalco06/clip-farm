"""Per uno Short di Speedy: trova la live da cui viene e ne scarica UN pezzo continuo che contiene tutti i pezzi usati (il resto
della live non si scarica). Riccardo, 17 nov: "si scarica un solo video unedited integrale dalla live, contenente tutti i pezzi
presenti nella clip virale, il resto della live scartalo".

uso: ~/Projects/video-editor/.venv/bin/python -I ultra/fonte.py ID_SHORT [URL_LIVE]   -> ultra/dati/<id>/
  originale.mp4          lo Short alla qualità più alta
  misure_originale/      misura.py sullo Short (servono le parole dette per cercare)
  sorgente.mp4           il pezzo di live (dal primo pezzo usato meno 20 s all'ultimo più 20 s)
  fonte.json             url della live, inizio e fine del pezzo scaricato, pezzi usati da Speedy (secondi di sorgente.mp4)
Ricerca: sottotitoli automatici delle dirette di IShowSpeed nelle settimane prima dello Short (gruppi di 3 parole in comune),
poi conferma con l'audio (misura.mappa). Con URL_LIVE si salta la ricerca (live trovata a mano o dall'agente col web).
"""
import json
from concurrent.futures import ThreadPoolExecutor
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
import misura  # noqa: E402

YTDLP = str(Path.home() / ".local/bin/yt-dlp")
DATI = QUI / "dati"
SUB = DATI / "_sottotitoli"
ENV = {"SSL_CERT_FILE": "/etc/ssl/cert.pem", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:" + str(Path.home() / ".local/bin")}
MIN_COPERTURA = 0.3  # parte dello Short (in secondi) che l'audio deve ritrovare nella live
CANALI = ["https://www.youtube.com/@IShowSpeed/streams", "https://www.youtube.com/@IShowSpeed/videos", "https://www.youtube.com/channel/UC2bW_AY9BlbYLGJSXAbjS4Q/videos"]  # anche i video caricati: alcuni Short vengono da lì


@contextmanager
def blocco():
    """Il blocco condiviso del Mac per i lavori pesanti (Demucs)."""
    lock = misura.FARM / "state/catena.lock"
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            time.sleep(5)
    try:
        yield
    finally:
        lock.rmdir()


def yt(*a, timeout=900):
    return subprocess.run([YTDLP, "-q", "--no-warnings", *a], capture_output=True, text=True, timeout=timeout, env=ENV)


def parole(testo):
    return re.findall(r"[a-z0-9']+", testo.lower().replace("’", "'"))


def trigrammi(p):
    return {" ".join(p[i:i + 3]) for i in range(len(p) - 2)}


def dirette():
    """Elenco delle dirette (id, data approssimata, durata, titolo), in cache per un giorno."""
    f = DATI / "_dirette.tsv"
    if not f.exists() or (datetime.now().timestamp() - f.stat().st_mtime) > 86400:
        righe = []
        for c in CANALI:
            righe += yt("--flat-playlist", "--extractor-args", "youtubetab:approximate_date", "--print", "%(id)s\t%(upload_date)s\t%(duration)s\t%(title)s", c).stdout.splitlines()
        f.write_text("\n".join(righe))
    return [r.split("\t") for r in f.read_text().splitlines() if r.count("\t") >= 3]


def date_esatte(righe):
    """Data vera di ogni diretta dal 2025 in poi (YouTube nell'elenco dà solo "N mesi fa" / "1 anno fa": tutto il 2025 risultava
    del 18/11/2025). Una richiesta per video, 8 alla volta, in cache per sempre (la data di un video non cambia)."""
    f = DATI / "_date_esatte.tsv"
    note = dict(r.split("\t")[:2] for r in f.read_text().splitlines() if "\t" in r) if f.exists() else {}
    mancano = [vid for vid, up, *_ in righe if vid not in note and up >= "20241118"]

    def una(vid):
        try:
            return vid, yt("--skip-download", "--print", "%(upload_date)s", "--", f"https://www.youtube.com/watch?v={vid}", timeout=120).stdout.strip()
        except subprocess.TimeoutExpired:  # un video che non risponde resta con la data approssimata
            return vid, ""
    with ThreadPoolExecutor(8) as pool, open(f, "a") as out:
        for vid, d in pool.map(una, mancano):
            if re.fullmatch(r"\d{8}", d):
                note[vid] = d
                out.write(f"{vid}\t{d}\n")
                out.flush()
    return note


def sottotitoli(vid):
    """Parole della diretta con il loro secondo, dai sottotitoli automatici (in cache)."""
    SUB.mkdir(parents=True, exist_ok=True)
    f = SUB / f"{vid}.en-orig.json3"
    if not f.exists() and not (SUB / f"{vid}.nessuno").exists():
        yt("--skip-download", "--write-auto-subs", "--sub-langs", "en-orig", "--sub-format", "json3", "-o", str(SUB / vid), "--", f"https://www.youtube.com/watch?v={vid}")
        if not f.exists():
            (SUB / f"{vid}.nessuno").touch()
            return []
    if not f.exists():
        return []
    out = []
    for e in json.loads(f.read_text()).get("events", []):
        for s in e.get("segs", []):
            out += [(w, (e["tStartMs"] + s.get("tOffsetMs", 0)) / 1000) for w in parole(s.get("utf8", ""))]
    return out


def soglia_testo(p):
    """Gruppi di 3 parole in comune per tentare la conferma audio. Misurato il 17/11: live vere 62 su 84 e 40 su 34 gruppi dello
    Short; candidate false quasi tutte 4-15 (frasi comuni: "can i get", "what is my")."""
    return max(10, int(0.35 * len(trigrammi(p))))


def dove(short_parole, live):
    """Il tratto della live con più gruppi di 3 parole dello Short: (gruppi trovati, secondo del primo, secondo dell'ultimo)."""
    cerco = trigrammi(short_parole)
    w = [x for x, _ in live]
    colpi = sorted(live[i][1] for i in range(len(w) - 2) if " ".join(w[i:i + 3]) in cerco)
    best = (0, None, None)
    j = 0
    for i in range(len(colpi)):  # finestra scorrevole di 5 minuti: i pezzi di uno Short stanno vicini
        while colpi[i] - colpi[j] > 300:
            j += 1
        if i - j + 1 > best[0]:
            best = (i - j + 1, colpi[j], colpi[i])
    return best


def cerca(short_parole, data, giorni=30, dopo=3, massimo=80):
    """Dirette nelle settimane prima dello Short (date approssimate di YouTube: si allarga la finestra), dalla più vicina."""
    d0 = datetime.strptime(data, "%Y%m%d")
    vicine = []
    righe = dirette()
    # date esatte solo per le dirette che la data approssimata mette vicine (anno intero se YouTube dice "1 anno fa")
    def vicina(up):
        try:
            du = datetime.strptime(up, "%Y%m%d")
        except ValueError:
            return False
        return d0 - timedelta(days=400) <= du <= d0 + timedelta(days=400) if (datetime.now() - du).days > 330 else d0 - timedelta(days=70) <= du <= d0 + timedelta(days=45)
    esatte = date_esatte([r for r in righe if vicina(r[1])])
    for vid, up, dur, titolo in righe:
        up = esatte.get(vid, up)
        try:
            du = datetime.strptime(up, "%Y%m%d")
        except ValueError:
            continue
        # "dopo": YouTube dà date per mese ("7 mesi fa" = stesso giorno per tutte): una diretta di marzo può risultare di aprile
        if d0 - timedelta(days=giorni) <= du <= d0 + timedelta(days=dopo):
            # gli Short escono di solito pochi giorni DOPO la diretta: prima le dirette appena precedenti, poi le altre
            giorni_prima = (d0 - du).days
            vicine.append((giorni_prima if giorni_prima >= 0 else 100 - giorni_prima, vid, titolo))
    soglia = soglia_testo(short_parole)
    migliore = None
    ordine = sorted(vicine)[:massimo]
    with ThreadPoolExecutor(6) as pool:  # ~1 minuto per diretta da 8 ore: 6 alla volta, nell'ordine della data
        for i in range(0, len(ordine), 6):
            gruppo = ordine[i:i + 6]
            for (_, vid, titolo), live in zip(gruppo, pool.map(lambda x: sottotitoli(x[1]), gruppo)):
                n, a, b = dove(short_parole, live)
                if n and (not migliore or n > migliore[0]):
                    migliore = (n, vid, a, b, titolo)
                    print(f"  {vid} «{titolo[:50]}»: {n} gruppi di parole tra {a:.0f} e {b:.0f} s", flush=True)
            if migliore and migliore[0] >= max(soglia, 8):
                break
    return migliore if migliore and migliore[0] >= soglia else None


def durate(f):
    """Durata di ogni flusso (video, audio) di un file."""
    out = {}
    for t in ("v", "a"):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", f"{t}:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
        try:
            out[t] = float(r.stdout.strip().splitlines()[0])
        except (ValueError, IndexError):
            out[t] = 0.0
    return out


def scarica_tratto(url, da, a, uscita, video=True):
    """Il tratto [da, a] della live. Visto il 18/11: 4 download su 11 con il video o l'audio troncati (SggsKTivDao: video 143 s
    su 357): si controlla che ogni flusso copra il 97% del tratto e si riprova fino a 3 volte."""
    fmt = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]" if video else "ba[ext=m4a]/ba/b"
    fine = yt("--skip-download", "--print", "%(duration)s", "--", url).stdout.strip()
    if fine.replace(".", "").isdigit():
        a = min(a, float(fine))  # il tratto chiesto può andare oltre la fine del video (HZKQ-NQAiJ4: fino a 3988 s, video di 3964)
    flussi = ("v", "a") if video else ("a",)
    errore = ""
    for prova in range(3):
        if prova < 2:
            r = yt("-f", fmt, "--download-sections", f"*{da:.1f}-{a:.1f}", "--force-keyframes-at-cuts", "--merge-output-format", "mp4",
                   "-o", str(uscita), "--force-overwrites", "--", url, timeout=3600)
        else:  # riserva: indirizzi diretti e taglio con ffmpeg (le sezioni di yt-dlp troncavano l'audio sempre allo stesso punto)
            u = yt("-g", "-f", fmt, "--", url).stdout.split()
            ing = [x for v in u for x in ("-ss", f"{da:.2f}", "-i", v)]
            r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *ing, "-t", f"{a - da:.2f}", *[x for i in range(len(u)) for x in ("-map", f"{i}")], "-c", "copy", str(uscita)],
                               capture_output=True, text=True, timeout=3600, env=ENV)
        if not r.returncode and Path(uscita).exists():
            d = durate(uscita)
            if all(d[t] >= 0.97 * (a - da) for t in flussi):
                return
            errore = f"flussi troncati {d} su {a - da:.0f} s"
        else:
            errore = r.stderr[-400:]
    raise RuntimeError(f"download {url} {da:.0f}-{a:.0f} fallito dopo 3 prove: {errore}")


VUOTE = set("i you the a to and it is that what my me so bro he she we they this in of on for oh no yeah not do be can get like just gonna".split())


def cerca_web(short_parole, titolo, soglia):
    """Ricerca di YouTube (canali di fan che caricano pezzi integrali delle dirette, es. "IShowPower of Speed"): col titolo dello
    Short e con le sue parole più particolari; poi gli stessi sottotitoli + gruppi di parole. Dal più promettente."""
    chiave = [w for w in short_parole if w not in VUOTE and len(w) > 2]
    domande = [f"ishowspeed {re.sub(r'[^A-Za-z0-9 ]', ' ', titolo)}", "ishowspeed " + " ".join(chiave[:8])]
    visti, video = set(), []
    for q in domande:
        for riga in yt("--flat-playlist", "--print", "%(id)s\t%(duration)s\t%(title)s", f"ytsearch12:{q}").stdout.splitlines():
            vid, dur, tit = (riga.split("\t") + ["", ""])[:3]
            if vid not in visti and dur.replace(".", "").isdigit() and 90 <= float(dur) <= 40000:
                visti.add(vid)
                video.append((vid, tit))
    out = []
    with ThreadPoolExecutor(6) as pool:
        for (vid, tit), live in zip(video, pool.map(lambda x: sottotitoli(x[0]), video)):
            n, a, b = dove(short_parole, live)
            if n >= soglia:
                out.append((n, vid, a, b, tit))
                print(f"  web {vid} «{tit[:50]}»: {n} gruppi di parole tra {a:.0f} e {b:.0f} s", flush=True)
    return sorted(out, reverse=True)


def conferma(d, url, a, b, voce_short, durata):
    """Audio su una finestra larga intorno al tratto trovato nel testo, voce contro voce (Demucs su tutte e due)."""
    larga = d / "_audio_larga.m4a"
    w0 = max(0, a - 150)
    scarica_tratto(url, w0, b + 150, larga, video=False)
    voce_live = d / "_larga_asr"
    with blocco():
        subprocess.run([str(misura.VE / ".venv-align/bin/python"), "-I", "scripts/extract_audio.py", str(larga.resolve()), str(voce_live.resolve())],
                       check=True, capture_output=True, cwd=misura.VE, timeout=3600)
    pezzi = misura.mappa(voce_short, voce_live / "vocals.wav")
    larga.unlink()
    shutil.rmtree(voce_live, ignore_errors=True)
    return pezzi, w0, round(sum(p["clip"][1] - p["clip"][0] for p in pezzi) / durata, 2)


def fonte(ident, url=None):
    d = DATI / ident
    d.mkdir(parents=True, exist_ok=True)
    orig = d / "originale.mp4"
    if not orig.exists():
        r = yt("-f", "bv*+ba/b", "--merge-output-format", "mp4", "-o", str(orig), "--", f"https://www.youtube.com/shorts/{ident}")
        if r.returncode:
            raise RuntimeError(r.stderr[-300:])
    mo = d / "misure_originale"
    m = json.loads((mo / "misure.json").read_text()) if (mo / "misure.json").exists() else misura.misura(orig, mo)
    sp = parole(" ".join(w for w, _, _ in m["parole_dette"]))
    data, titolo_short = (yt("--skip-download", "--print", "%(upload_date)s\t%(title)s", "--", f"https://www.youtube.com/shorts/{ident}").stdout.strip().split("\t") + [""])[:2]
    soglia = soglia_testo(sp)
    if url:
        vid = url.rsplit("v=", 1)[-1][:11]
        n, a, b = dove(sp, sottotitoli(vid))
        candidati = [(n, vid, a, b, "data a mano")] if a is not None else []
    else:
        c = cerca(sp, data)
        candidati = ([c] if c else []) + cerca_web(sp, titolo_short, soglia)
        candidati = [x for i, x in enumerate(candidati) if x[1] not in {y[1] for y in candidati[:i]}]  # la stessa live una volta sola
    tentativi = []
    for n, vid, a, b, titolo in candidati[:4]:  # al massimo 4 conferme audio (1-2 minuti l'una)
        url = f"https://www.youtube.com/watch?v={vid}"
        pezzi, w0, copertura = conferma(d, url, a, b, mo / "asr/vocals.wav", m["durata"])
        tentativi.append({"url": url, "titolo": titolo, "gruppi_parole": n, "copertura_audio": copertura})
        if copertura >= MIN_COPERTURA:
            break
        print(f"{ident}: testo trovato in {url} ma l'audio conferma solo il {copertura:.0%}", flush=True)
    else:
        (d / "fonte.json").write_text(json.dumps({"id": ident, "data": data, "trovata": False, "tentativi": tentativi}, ensure_ascii=False, indent=1))
        print(f"{ident}: live non trovata ({len(tentativi)} candidate controllate con l'audio)", flush=True)
        return None
    # il tratto copre i pezzi confermati dall'audio E tutta la zona trovata nel testo: con musica forte sopra (Speedy arriva a
    # -6,6 LUFS) l'audio conferma a volte un pezzo solo (TRG58mooOps: 1 pezzo, tratto di 42 s, gli altri pezzi rimasti fuori)
    da = min([w0 + min(p["live"][0] for p in pezzi), a]) - 30
    a_ = max([w0 + max(p["live"][1] for p in pezzi), b]) + 30
    scarica_tratto(url, max(0, da), a_, d / "sorgente.mp4")
    info = {"id": ident, "data": data, "url": url, "titolo_live": titolo, "trovata": True, "inizio_in_live": round(max(0, da), 2), "fine_in_live": round(a_, 2),
            "gruppi_parole": n, "copertura_audio": copertura, "pezzi_speedy": [{"clip": p["clip"], "sorgente": [round(w0 + x - max(0, da), 2) for x in p["live"]]} for p in pezzi]}
    (d / "fonte.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
    print(f"{ident}: {url} da {da:.0f} a {a_:.0f} s ({(a_ - da) / 60:.1f} min), {len(pezzi)} pezzi confermati dall'audio ({copertura:.0%})", flush=True)
    return info


if __name__ == "__main__":
    if sys.argv[1:] == ["--prova"]:
        live = [(w, i * 0.5) for i, w in enumerate("bla bla who is the best football player of all time bla bla".split())] + [(w, 1000 + i) for i, w in enumerate("best football player again".split())]
        n, a, b = dove(parole("Who is the best football player of all time?"), live)
        assert (n, a, b) == (7, 1.0, 4.0), (n, a, b)  # 7 terne in fila; "best football player" a 1000 s è lontano
        print("ok")
    else:
        fonte(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
