"""Ripasso di una trasmissione già andata in onda: cerca i picchi su tutto l'audio e ci fa lavorare la stessa
selezione della diretta (candidati -> giudice -> montaggio). Serve anche da riserva se una live è sfuggita.

uso: ~/Projects/video-editor/.venv/bin/python -I ripassa.py URL "Streamer" [PICCHI] [--audio FILE_GIÀ_SCARICATO]
     ~/Projects/video-editor/.venv/bin/python -I ripassa.py --kick|--twitch CANALE "Streamer" [QUANTE] [day|week]
Con --kick o --twitch parte dalle clip più viste fatte dagli spettatori: il momento l'ha già scelto la folla, noi lo
giudichiamo e lo rimontiamo nel nostro stile. Con --live ID (lo fa la catena ogni 20 minuti per le live in corso)
le clip vanno su quella live e si prendono solo quelle sopra `folla_minimo_viste` di config.json.
Se le clip promosse sono meno di 3, monta anche le migliori bocciate con l'etichetta "SOTTO SOGLIA": servono a tarare.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con -I la cartella dello script non è nel percorso
import analizza  # noqa: E402
import catena  # noqa: E402
from stato import CONFIG, QUI, REG, db, kv  # noqa: E402

os.environ["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"  # l'ffmpeg installato non trova da solo i certificati: senza, https fallisce
YTDLP = Path.home() / ".local/bin/yt-dlp"
PRIMA, DOPO = 150, 45  # secondi di filmato presi attorno a ogni picco


def volume(audio):
    """dB per secondo, letto a pezzi: 48 ore di audio non stanno in memoria."""
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], stdout=subprocess.PIPE)
    db_ = []
    while len(pezzo := p.stdout.read(32000 * 600)) >= 32000:
        a = np.frombuffer(pezzo[: len(pezzo) // 32000 * 32000], dtype=np.int16).astype(np.float32).reshape(-1, 16000) / 32768
        db_.extend(20 * np.log10(np.sqrt((a**2).mean(1)) + 1e-6))
    return np.array(db_)


def tratto(playlist, inizio, durata, uscita):
    """Scarica solo i segmenti dell'archivio che coprono il tratto e li unisce (sono MPEG-TS: basta accodarli).
    Con ffmpeg -ss su un archivio di 48 ore la ricerca restava appesa. Restituisce il secondo da cui parte davvero il file."""
    testo = urllib.request.urlopen(playlist, timeout=30).read().decode()
    t, parte, scelti = 0.0, None, []
    righe = testo.splitlines()
    for i, r in enumerate(righe):
        if r.startswith("#EXTINF:"):
            lungo = float(r[8:].split(",")[0])
            if t + lungo > inizio and t < inizio + durata:
                scelti.append(righe[i + 1])
                parte = t if parte is None else parte
            t += lungo
    with open(uscita, "wb") as f:
        for nome in scelti:
            f.write(urllib.request.urlopen(urllib.parse.urljoin(playlist, nome), timeout=60).read())
    return parte


def intervalli(righe):
    """Dalla playlist di una clip di Kick a [(file, da, quanti byte)]: senza @ l'intervallo continua da dove finiva il precedente."""
    esito, tag, fine = [], None, {}
    for r in righe:
        if m := re.match(r"#EXT-X-BYTERANGE:(\d+)(?:@(\d+))?", r):
            tag = m.groups()
        elif r and not r.startswith("#"):
            n, da = (int(tag[0]), int(tag[1]) if tag[1] else fine.get(r, 0)) if tag else (None, 0)
            esito.append((r, da, n))
            fine[r], tag = da + (n or 0), None
    return esito


def kick_clip(playlist, uscita):
    """Scarica una clip di Kick. I segmenti sono intervalli di byte dentro pochi file: ffmpeg ne sbagliava uno per file
    ("Unexpected offset") e la clip aveva un fermo immagine di 2 secondi ogni 12. Qui ogni file si scarica intero una volta
    e gli intervalli si ritagliano nell'ordine della playlist (sono MPEG-TS: basta accodarli)."""
    leggi = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
    file = {}
    with open(uscita, "wb") as f:
        for nome, da, n in intervalli(leggi(playlist).decode().splitlines()):
            if nome not in file:
                file[nome] = leggi(urllib.parse.urljoin(playlist, nome))
            f.write(file[nome][da: da + n if n else None])


if __name__ == "__main__":
    assert intervalli(["#EXTM3U", "#EXT-X-BYTERANGE:10@90", "#EXTINF:2,", "a.ts", "#EXT-X-BYTERANGE:20@0", "#EXTINF:2,", "b.ts", "#EXT-X-BYTERANGE:5", "#EXTINF:2,", "b.ts", "#EXTINF:2,", "c.ts"]) \
        == [("a.ts", 90, 10), ("b.ts", 0, 20), ("b.ts", 20, 5), ("c.ts", 0, None)]
    arg = sys.argv[1:]
    folla = "kick" if "--kick" in arg else "twitch" if "--twitch" in arg else None
    arg = [a for a in arg if a not in ("--kick", "--twitch")]
    audio = Path(arg[arg.index("--audio") + 1]) if "--audio" in arg else None
    url, streamer = arg[0], arg[1]
    quanti = int(arg[2]) if len(arg) > 2 and arg[2].isdigit() else 8
    c = db()
    in_diretta = "--live" in arg  # lanciato dalla catena per una live in corso: le clip vanno su quella live, solo sopra il minimo di visualizzazioni
    if in_diretta:
        live = dict(c.execute("select * from live where id=?", (arg[arg.index("--live") + 1],)).fetchone())
    else:
        c.execute("insert into live (streamer, piattaforma, url, titolo, gioco, inizio, fine) values (?,?,?,?,?,?,?)", (streamer, "ripasso", url, "ripasso di una trasmissione passata", "", time.time(), time.time()))
        live = dict(c.execute("select * from live where id=last_insert_rowid()").fetchone())
    d = REG / f"ripasso{live['id']}"
    lav = QUI / "lavoro" / f"ripasso{live['id']}"
    d.mkdir(parents=True, exist_ok=True), lav.mkdir(parents=True, exist_ok=True)
    fatte, riserva = 0, []

    def tratta(sez, inizio, etichetta, candidati=None, folla_dice=""):
        """Un tratto di filmato: candidati (dal selezionatore, o già dati dalla folla) -> giudice -> montaggio o riserva."""
        global fatte
        an = json.loads(subprocess.run([str(catena.VE / ".venv/bin/python"), "-I", str(QUI / "analizza.py"), "--ultimo", str(sez)], capture_output=True, text=True, check=True, timeout=600).stdout)
        print(f"{time.strftime('%H:%M:%S')} {etichetta}: {len(an['frasi'])} frasi", flush=True)
        tenere = False
        for k in (candidati(an) if candidati else catena.seleziona(an, live) if an["frasi"] else [])[:2]:
            if v := catena.giudica(k, an, live, lav, tutte=True):
                # Riccardo, 12 nov: anche le clip degli spettatori passano dal montaggio a storia e dal voto del giudice;
                # la folla indica solo dove guardare (prima uscivano intere e promosse d'ufficio: le più "non originali" di tutte)
                if v["_promossa"] and (v.get("tagli") or not folla_dice):  # se il giudice toglie i pezzi, una clip della folla resta fuori
                    v["_promossa"] = True
                    fatte += bool(catena.monta_clip(c, live, f"ripasso{live['id']}_{sez.stem}_{int(v['inizio'])}", v, an, lav, d, inizio, etichetta=folla_dice))
                else:
                    riserva.append((v["_media"], sez.stem, v, an, inizio))
                    tenere = True
        if not tenere:
            sez.unlink()

    if folla:
        # clip degli spettatori, dalla più vista: [(id, titolo, visualizzazioni, durata, funzione che la scarica in `sez`)]
        if folla == "kick":
            req = urllib.request.Request(f"https://kick.com/api/v2/channels/{url}/clips?sort=view&time={'week' if 'week' in arg else 'day'}", headers={"User-Agent": "Mozilla/5.0"})
            clip = [(k["id"][-8:], k["title"], k["view_count"], float(k["duration"]), lambda sez, k=k: kick_clip(k["clip_url"], sez))
                    for k in json.loads(urllib.request.urlopen(req, timeout=20).read())["clips"]]
        else:
            elenco = subprocess.run([YTDLP, "-q", "--no-warnings", "--flat-playlist", "--playlist-end", "40", "--print", "%(id)s\t%(view_count)s\t%(duration)s\t%(url)s\t%(title)s",
                                     f"https://www.twitch.tv/{url}/clips?range={'7d' if 'week' in arg else '24hr'}"], capture_output=True, text=True, check=True).stdout
            clip = [(r[0][-8:], r[4], int(r[1]), float(r[2]), lambda sez, u=r[3]: subprocess.run([YTDLP, "-q", "--no-warnings", "-f", "best", "--force-overwrites", "-o", str(sez), u], check=True, timeout=600)) for r in (x.split("\t") for x in elenco.splitlines())]
        gia = kv(c, "folla_fatte") or []  # ogni clip degli spettatori si rimonta una volta sola
        minimo = CONFIG["folla_minimo_viste"][folla] if in_diretta else 0
        for ident, titolo, viste, dur, scarica in [k for k in clip if k[3] >= 10 and k[0] not in gia and k[2] >= minimo][:quanti]:
            kv(c, "folla_fatte", (gia := gia + [ident])[-2000:])
            sez = d / f"k_{ident}.{'ts' if folla == 'kick' else 'mp4'}"
            scarica(sez)
            # il momento l'hanno scelto gli spettatori: la storia la costruisce il selezionatore dai pezzi della loro clip, solo candidati a storia
            tratta(sez, 0, f"clip degli spettatori «{titolo[:40]}» ({viste} visualizzazioni, {dur:.0f} s)",
                   lambda an: [k for k in (catena.seleziona(an, live) if an["frasi"] else []) if catena.storia_da(k.get("tagli"), an["durata"])],
                   folla_dice=f"{viste} viste - ")
    elif not audio:
        audio = d / "audio.mp4"
        subprocess.run([YTDLP, "-q", "--no-warnings", "-f", "Audio_Only/bestaudio", "-N", "16", "-o", str(audio), url], check=True)
    if not folla:
        db_ = np.maximum(volume(audio), -50)  # il silenzio totale (pausa, notte) non deve far sembrare un urlo il primo rumore
        # scarto dalla norma calcolato su tratti da 10 minuti, come nella diretta: su 48 ore intere notte e urla falsano la media
        liscio = np.concatenate([np.convolve(analizza.z(db_[i: i + 600]), np.ones(3) / 3, "same") for i in range(0, len(db_), 600)])
        picchi = sorted(analizza.picchi(liscio, k=quanti, distanza=600), key=lambda x: -x[1])
        print(f"{len(db_) / 3600:.1f} ore, picchi: {[(t, round(f, 1)) for t, f in picchi]}", flush=True)
        video = subprocess.run([YTDLP, "-q", "--no-warnings", "-f", "best", "-g", url], capture_output=True, text=True, check=True).stdout.strip()
        for t, forza in picchi:
            sez = d / f"s_{t}.ts"
            tratta(sez, tratto(video, max(0, t - PRIMA), PRIMA + DOPO, sez), f"picco a {t // 3600}h{t % 3600 // 60:02d} (forza {forza:.1f})")
    for media, t, v, an, inizio in sorted(riserva, key=lambda x: -x[0])[: 0 if in_diretta else max(0, 3 - fatte)]:
        catena.monta_clip(c, live, f"ripasso{live['id']}_{t}_{int(v['inizio'])}", v, an, lav, d, inizio, etichetta=f"SOTTO SOGLIA {media:.1f} - ")
    for f in [*d.glob("s_*.ts"), *d.glob("k_*.*")]:
        f.unlink()
    print(f"finito: {fatte} promosse, {min(len(riserva), max(0, 3 - fatte))} sotto soglia montate per tarare", flush=True)
