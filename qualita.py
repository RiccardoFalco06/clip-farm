"""Controllo qualità di una clip finita: ogni casella va spuntata, altrimenti la clip non entra nella coda di pubblicazione.

uso: ~/Projects/video-editor/.venv/bin/python -I qualita.py SCHEDA.json     (serve numpy)
Stampa {"ok": true|false, "caselle": [{"nome": ..., "ok": ..., "nota": ...}]}.
Le misure le fa il codice; quello che si può solo guardare (inquadratura, sottotitoli doppi) lo guarda Sonnet su 8 fotogrammi.
Una casella che non si riesce a verificare conta come non spuntata.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con -I la cartella dello script non è nel percorso
import catena  # noqa: E402
import monta  # noqa: E402
from stato import CONFIG, QUI  # noqa: E402

VISTE = {"streamer_inquadrato": "lo streamer si vede (o la sua assenza fa parte della scena)", "inquadratura_pulita": "inquadratura pulita",
         "sottotitoli_leggibili": "sottotitoli interi e leggibili", "sottotitoli_non_doppi": "niente sottotitoli doppi",
         "sottotitoli_sensati": "il testo dei sottotitoli ha senso"}


def sonda(f):
    r = json.loads(subprocess.run(["ffprobe", "-v", "0", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,duration", "-of", "json", str(f)],
                                  capture_output=True, text=True, check=True).stdout)["streams"]
    return next(x for x in r if x["codec_type"] == "video"), next((x for x in r if x["codec_type"] == "audio"), None)


def rilevati(f, filtro, chiave, audio=False):
    """Secondi in cui un filtro di ffmpeg (blackdetect, silencedetect) segnala qualcosa."""
    err = subprocess.run(["ffmpeg", "-nostdin", "-i", str(f), "-af" if audio else "-vf", filtro, "-map", "0:a" if audio else "0:v", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(chiave + r":\s*([\d.]+)", err)]


def inviluppo(f):
    """Volume ogni 10 ms."""
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(f), "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.abs(np.frombuffer(pcm, dtype=np.float32))
    return x[: len(x) // 80 * 80].reshape(-1, 80).mean(axis=1)


def ritardo(a, b, massimo=100):
    """Di quanti secondi b è spostato rispetto ad a (positivo = b in ritardo), cercando entro un secondo."""
    n = min(len(a), len(b)) - massimo
    a, b = a[:n] - a[:n].mean(), b - b.mean()
    return max(range(-massimo, massimo + 1), key=lambda k: float(np.dot(a[max(0, -k): n - max(0, k)], b[max(0, k): n - max(0, -k)]))) / 100


def scritte(gruppi, durata):
    """Sottotitoli nostri: ci sono, uno alla volta, dentro la clip, nessuno fermo a schermo più di 4 secondi."""
    if not gruppi:
        return "nessun sottotitolo"
    for g, dopo in zip(gruppi, gruppi[1:] + [None]):
        testo = " ".join(w["text"] for w in g["words"])
        if dopo and g["end"] > dopo["start"] + 0.001:
            return f"«{testo}» è ancora a schermo quando arriva il successivo (secondo {dopo['start']:.1f})"
        if g["start"] < 0 or g["end"] > durata + 0.05:
            return f"«{testo}» esce dalla clip"
        if g["end"] - g["start"] > 4:
            return f"«{testo}» resta a schermo {g['end'] - g['start']:.1f} s"
    return ""


def guarda(finale, gruppi, durata, d, s, sospetti):
    """Le caselle che si possono solo guardare: 8 fotogrammi della clip finita, presi dove c'è un sottotitolo e nei momenti
    sospetti (immagine ferma o nera). Restituisce le caselle, se i momenti sospetti fanno parte della scena, e le note."""
    extra = [min(t + lungo / 2, durata - 0.1) for t, lungo, _ in sospetti[:3]]
    tempi, n = [(g["start"] + g["end"]) / 2 for g in gruppi], 8 - len(extra)
    tempi = [tempi[round(i * (len(tempi) - 1) / (n - 1))] for i in range(n)] if len(tempi) >= n else tempi + [durata * (i + 0.5) / (n - len(tempi)) for i in range(n - len(tempi))]
    tempi = sorted(tempi + extra)
    for i, t in enumerate(tempi):
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{min(t, durata - 0.1):.2f}", "-i", str(finale), "-frames:v", "1", "-vf", "scale=480:-2", str(d / f"qc{i}.jpg")], check=True)
    foglio = d / "qualita.jpg"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *[x for i in range(8) for x in ("-i", str(d / f"qc{i}.jpg"))], "-filter_complex", "xstack=inputs=8:grid=4x2", str(foglio)], check=True)
    segnalati = "\n".join(f"- al secondo {t:.1f} l'immagine è {cosa} per {lungo:.1f} s (fotogramma {tempi.index(e) + 1})" for (t, lungo, cosa), e in zip(sospetti, extra)) \
        + (f"\n- e altri {len(sospetti) - 3} momenti simili" if len(sospetti) > 3 else "")
    try:
        r = catena.primo_json(catena.chiedi((QUI / "prompt/qualita.md").read_text(), {"IMMAGINE": foglio, "TITOLO": s.get("titolo", "?"), "STORIA": s.get("storia", "?"),
                                                                                    "SOSPETTI": segnalati or "nessuno",
                                                                                    "SCRITTE": " / ".join(" ".join(w["text"] for w in g["words"]) for g in gruppi) or "(nessuna)"}, ["Read"]), "{")
    except ValueError:
        r = {}
    return [(nome, r.get(k) is True, "" if r.get(k) is True else str(r.get("note") or "non verificato")[:200]) for k, nome in VISTE.items()], r.get("blocchi_voluti") is True, str(r.get("note") or "")[:200]


def controlla(s):
    speedy = s.get("stile") == "speedy"  # montato da laboratorio/monta.py: file di lavoro là, formato 3:4 ammesso
    finale, d = Path(s["uscita"]).expanduser(), (QUI / "laboratorio" if speedy else QUI) / "lavoro" / s["id"]
    base = d / "base.mp4"
    props = json.loads((d / "props.json").read_text()) if (d / "props.json").exists() else None
    v, a = sonda(finale)
    dv, da = float(v["duration"]), float(a["duration"]) if a else 0
    c = [("formato 1080×1920 (o 1080×1440 in speedy), 30 fps, H.264 + AAC", (v["width"], v["r_frame_rate"], v["codec_name"], a and a["codec_name"]) == (1080, "30/1", "h264", "aac") and v["height"] in ((1920, 1440) if speedy else (1920,)),
          f"{v['width']}×{v['height']} {v['r_frame_rate']} {v['codec_name']} {a and a['codec_name']}"),
         ("durata tra 8 e 60 secondi", 8 <= dv <= 60, f"{dv:.1f} s"),
         ("audio e video lunghi uguali", abs(dv - da) <= 0.15, f"video {dv:.2f} s, audio {da:.2f} s")]
    # immagine ferma (anche scatti brevi, da 0,3 s) o nera: può essere un difetto o far parte della scena; si decide guardando, più sotto
    neri = list(zip(rilevati(finale, "blackdetect=d=0.3:pix_th=0.10", "black_start"), rilevati(finale, "blackdetect=d=0.3:pix_th=0.10", "black_duration")))
    sospetti = sorted([(t, x, "ferma") for t, x in monta.fermi(base if base.exists() else finale)] + [(t, x, "nera") for t, x in neri])
    err = subprocess.run(["ffmpeg", "-nostdin", "-i", str(finale), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    forte, picco = float(re.findall(r"I:\s*(-?[\d.]+) LUFS", err)[-1]), float(re.findall(r"Peak:\s*(-?[\d.]+) dBFS", err)[-1])
    c.append(("volume a −14 LUFS senza distorsione", -16 <= forte <= -12 and picco <= -0.3, f"{forte:.1f} LUFS, picco {picco:.1f} dB"))
    muti = rilevati(finale, "silencedetect=noise=-50dB:d=2", "silence_start", audio=True)
    c.append(("niente buchi di silenzio", not muti, ", ".join(f"secondo {t:.0f}" for t in muti)))
    if base.exists() and props:
        sposta = ritardo(inviluppo(base), inviluppo(finale))
        c.append(("audio in sincrono col video", abs(sposta) <= 0.08, f"audio spostato di {sposta:+.2f} s"))
        # niente sottotitoli è ammesso: se nessuno parla (versi, risate, musica) è meglio niente che parole inventate (Riccardo, 11 nov)
        nota = scritte(props["gruppi"], props["durata"]) if props["gruppi"] else ""
        c.append(("sottotitoli uno alla volta (o nessuno, se non si parla)", not nota, nota))
    else:  # i file di lavoro non ci sono più (clip vecchia): non si può dire che vada bene
        c += [("audio in sincrono col video", False, "file di lavoro assenti: non verificabile"), ("sottotitoli presenti, uno alla volta", False, "file di lavoro assenti: non verificabile")]
    titolo, dida = str(s.get("titolo") or ""), str(s.get("didascalia") or "")
    c.append(("titolo e didascalia pronti", 0 < len(titolo) <= 91 and 0 < len(dida) <= 2200, f"titolo {len(titolo)} caratteri, didascalia {len(dida)}"))  # 91 + " #shorts" = 100, il limite di YouTube
    c.append(("firma del canale giusta", s.get("firma") == CONFIG["firma"], f"firma {s.get('firma')!r}, canale {CONFIG['firma']!r}"))
    viste, voluti, note = guarda(finale, props["gruppi"] if props else [], dv, d if d.exists() else finale.parent, s, sospetti)
    c.append(("l'immagine non si blocca e non va a nero (o fa parte della scena)", not sospetti or voluti,
              ", ".join(f"{cosa} {x:.1f} s al secondo {t:.0f}" for t, x, cosa in sospetti[:6]) + f" — {note}"))
    # regola fissa, non la decide il modello: nei primi 3 secondi l'immagine non resta mai ferma (un fermo voluto sta alla fine, non all'inizio)
    # si misura il video FINITO, quello che esce: la base da sola non bastava (l'11 nov il video della base cominciava dopo l'audio,
    # senza fotogrammi fermi da contare, e il fermo nasceva nel render)
    avvio = "; ".join(x for x in (monta.avvio_fermo(finale), monta.avvio_fermo(base) if base.exists() else "") if x)
    c.append(("l'inizio è in movimento", not avvio, avvio))
    c += viste
    caselle = [{"nome": n, "ok": bool(ok), "nota": "" if ok else nota} for n, ok, nota in c]
    return {"ok": all(x["ok"] for x in caselle), "caselle": caselle}


if __name__ == "__main__":
    onda = np.concatenate([np.zeros(300), np.ones(50), np.zeros(400), np.ones(20), np.zeros(600)])
    assert ritardo(onda, np.roll(onda, 7)) == 0.07 and ritardo(onda, np.roll(onda, -12)) == -0.12 and ritardo(onda, onda) == 0
    G = lambda a, b, t="OH": {"start": a, "end": b, "words": [{"text": t}]}
    assert scritte([G(0, 1), G(1, 2)], 5) == "" and "nessun" in scritte([], 5) and "ancora a schermo" in scritte([G(0, 1.5), G(1, 2)], 5)
    assert "resta a schermo" in scritte([G(0, 4.5)], 5) and "esce" in scritte([G(4, 5.5)], 5)
    if len(sys.argv) > 1:
        print(json.dumps(controlla(json.loads(Path(sys.argv[1]).read_text())), ensure_ascii=False))
