"""Materiale comune per gli agenti che valutano una clip: si estrae una volta, ognuno legge solo quello che gli serve.

uso: python -I strumenti/pacco_valutazione.py <id scheda> ...   →  laboratorio/valuta/<id>/
  fogli/foglio_NN.jpg   4 fotogrammi al secondo, 24 per foglio (6 s), col tempo stampato sopra
  fotogrammi/f_XXXX.jpg 15 al secondo, 540 px di larghezza (per guardare da vicino un istante: XXXX = tempo in centesimi)
  dati.json             durata, tagli sui tempi della clip, sottotitoli mostrati, effetti, parole attese, trascrizione
                        indipendente dell'audio finale (Whisper da capo), volume, livelli della voce intorno agli stacchi
"""
import json
import math
import subprocess
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
VE = Path.home() / "Projects/video-editor"
sys.path.insert(0, str(QUI))


def run(*a, **k):
    return subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True, **k)


def main(ident):
    d, out = QUI / "lavoro" / ident, QUI / "valuta" / ident
    s = json.loads((QUI / "schede" / f"{ident}.json").read_text())
    clip = d / "finale.mp4"
    (out / "fogli").mkdir(parents=True, exist_ok=True)
    (out / "fotogrammi").mkdir(exist_ok=True)
    durata = float(run("ffprobe", "-v", "0", "-show_entries", "format=duration", "-of", "csv=p=0", clip).stdout)
    run("ffmpeg", "-v", "error", "-y", "-i", clip, "-vf",
        "fps=4,scale=270:-2,drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial Bold.ttf:text='%{pts\\:flt}':x=6:y=6:fontsize=26:fontcolor=yellow:box=1:boxcolor=black,tile=6x4",
        out / "fogli" / "foglio_%02d.jpg")
    run("ffmpeg", "-v", "error", "-y", "-i", clip, "-vf", "fps=15,scale=540:-2", "-q:v", "4", out / "fotogrammi" / "tmp_%05d.jpg")
    for f in sorted((out / "fotogrammi").glob("tmp_*.jpg")):
        n = int(f.stem[4:]) - 1
        f.rename(f.with_name(f"f_{round(n / 15 * 100):04d}.jpg"))
    # trascrizione indipendente dell'audio finale: serve a vedere parole mozzate o mancanti e sottotitoli fuori tempo
    asr = out / "asr"
    asr.mkdir(exist_ok=True)
    run(VE / ".venv-align/bin/python", "-I", "scripts/extract_audio.py", clip, asr, cwd=VE)
    run(VE / ".venv/bin/python", "-I", QUI.parent / "trascrivi.py", asr)
    whisper = json.loads((asr / "whisper.json").read_text())
    props = json.loads((d / "props.json").read_text())
    taglio = json.loads((d / "taglio.json").read_text())
    stacchi, t = [], 0.0
    for a, b in (s.get("tagli") or []):
        t += b - a
        stacchi.append(round(t, 3))
    # i tagli veri (dopo lo spostamento sul silenzio) non sono nella scheda: si ricavano dai pezzi montati
    pezzi = sorted(d.glob("tratto*.mkv"), key=lambda p: int(p.stem[6:]))
    if pezzi:
        stacchi, t = [], 0.0
        for p in pezzi[:-1]:
            t += float(run("ffprobe", "-v", "0", "-show_entries", "format=duration", "-of", "csv=p=0", p).stdout)
            stacchi.append(round(t, 3))
    from monta import livelli, lufs
    voce = livelli(str(asr / "vocals.wav"), 0, durata)
    intorno = [{"t": x, "voce_db_prima": round(max(voce[max(0, round(x / 0.05) - 2): round(x / 0.05)] or [0]), 1),
                "voce_db_dopo": round(max(voce[round(x / 0.05): round(x / 0.05) + 2] or [0]), 1)} for x in stacchi]
    frasi = [{"da": f["start"], "a": f["end"], "testo": " / ".join(" ".join(p["text"] for p in r) for r in f["righe"]),
              "colorate": [p["text"] for r in f["righe"] for p in r if "fill" in p],
              "parole_con_tempo": [[p["text"], p.get("start")] for r in f["righe"] for p in r], **({"narrazione": True} if f.get("corsivo") else {}),
              **({"baseline": f["baseline"]} if "baseline" in f else {})} for f in props.get("frasi", [])]
    dati = {
        "id": ident, "titolo": s.get("titolo"), "durata": round(durata, 2), "risoluzione": "1080x1440 (3:4)",
        "sorgente_secondi_usati": [round(min(a for a, _ in s["tagli"]), 1), round(max(b for _, b in s["tagli"]), 1)] if s.get("tagli") else None,
        "stacchi_secondi_clip": stacchi,
        "livelli_voce_agli_stacchi": intorno,
        "livello_voce_parlato_tipico_db": round(sorted(voce)[len(voce) * 3 // 4], 1) if voce else None,
        "sottotitoli_mostrati": frasi,
        "lampi": props.get("lampi"), "zoom": props.get("zoom"), "suoni": [{"t": x["t"], "file": Path(x["file"]).name} for x in props.get("suoni", [])],
        "finale_scheda": s.get("finale"), "fermo_dal": props.get("fermo"),
        "musica": props.get("musica"),
        "parole_attese_con_tempi": [[w["show"], round(w["start"], 2), round(w.get("end", w["start"]), 2)] for w in json.loads((d / "words.json").read_text())],
        "trascrizione_indipendente_audio_finale": [[w["text"].strip(), round(w["start"], 2), round(w["end"], 2)] for w in whisper.get("words", [])],
        "volume_integrato_lufs": round(lufs(clip), 1),
        "volume_voce_lufs": round(lufs(asr / "vocals.wav"), 1),
    }
    (out / "dati.json").write_text(json.dumps(dati, ensure_ascii=False, indent=1))
    print(out, len(list((out / "fogli").glob("*.jpg"))), "fogli")


if __name__ == "__main__":
    for x in sys.argv[1:]:
        main(x)
