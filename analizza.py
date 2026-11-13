"""Trova i momenti candidati in un blocco di registrazione.

uso: ~/Projects/video-editor/.venv/bin/python -I analizza.py [--chat chat.jsonl] [--ultimo] [PRECEDENTE.ts] BLOCCO.ts > candidati.json
Dà al selezionatore la trascrizione del tratto nuovo e i picchi di volume (urla, risate) e di messaggi in chat.

Momenti a cavallo di due blocchi: si analizza il blocco insieme al precedente, come un filmato unico
("concat:prec|blocco", i blocchi hanno tempi continui). Un picco negli ultimi 25 s del blocco non ha ancora il
suo "dopo": si rimanda al giro successivo, che lo ritrova nel precedente. Così nessuna clip viene tagliata a metà.
Con --ultimo (live finita) non si rimanda niente. Il blocco precedente si cancella solo dopo questo giro.
"""
import json
import subprocess
import sys

import numpy as np

SR = 16000
FINESTRA = (20, 25)  # secondi che una clip può volere prima e dopo il momento clou
MAX_CANDIDATI = 6


def volume_per_secondo(video):
    pcm = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", video, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    a = a[: len(a) // SR * SR].reshape(-1, SR)
    return 20 * np.log10(np.sqrt((a**2).mean(1)) + 1e-6), a


def secondi(video, cosa):
    return float(subprocess.run(["ffprobe", "-v", "0", "-show_entries", f"format={cosa}", "-of", "csv=p=0", video], capture_output=True, text=True, check=True).stdout)


def chat_per_secondo(path, n, t0):
    c = np.zeros(n)
    if path:
        for riga in open(path):
            t = int(json.loads(riga)["t"] - t0)  # "t" = secondi dall'inizio della registrazione, come i tempi dei blocchi
            if 0 <= t < n:
                c[t] += 1
    return c


def z(x):
    # scarto dalla norma del canale: un canale rumoroso non deve scattare sempre
    med = np.median(x)
    mad = max(np.median(np.abs(x - med)) * 1.4826, 1.0)  # almeno 1 (dB o messaggi): una chat quasi ferma non deve dare picchi enormi per due messaggi
    return (x - med) / mad


def picchi(punteggio, k=MAX_CANDIDATI, distanza=40):
    p = punteggio.copy()
    out = []
    for _ in range(k):
        t = int(p.argmax())
        if p[t] < 2.0:  # sotto due scarti non è un momento
            break
        out.append((t, float(p[t])))
        p[max(0, t - distanza): t + distanza] = -np.inf
    return sorted(out)


def utili(punteggio, n_prec, ultimo):
    """Tiene solo i picchi da decidere in questo giro: non quelli già visti, non quelli senza ancora il "dopo"."""
    p = punteggio.copy()
    p[: max(0, n_prec - FINESTRA[1])] = -np.inf
    if not ultimo:
        p[len(p) - FINESTRA[1]:] = -np.inf
    return p


def main():
    arg = sys.argv[1:]
    ultimo = "--ultimo" in arg
    chat = arg[arg.index("--chat") + 1] if "--chat" in arg else None
    blocchi = [a for a in arg if a != "--ultimo" and a != chat and a != "--chat"]
    video = blocchi[0] if len(blocchi) == 1 else "concat:" + "|".join(blocchi)
    n_prec = int(secondi(blocchi[0], "duration")) if len(blocchi) > 1 else 0
    db, audio = volume_per_secondo(video)
    n = len(db)
    liscio = np.convolve(z(db), np.ones(3) / 3, "same")
    c = chat_per_secondo(chat, n, secondi(blocchi[0], "start_time"))
    punteggio = utili(liscio + (np.convolve(z(c), np.ones(5) / 5, "same") if c.any() else 0), n_prec, ultimo)

    import mlx_whisper

    # si trascrive tutto il tratto nuovo (più 60 s di precedente): i picchi sono solo indizi, i momenti buoni
    # detti a voce normale si trovano dal testo. Senza contesto tra le frasi Whisper non entra in ripetizioni infinite.
    da = max(0, n_prec - 60)
    r = mlx_whisper.transcribe(audio[da:].reshape(-1), path_or_hf_repo="mlx-community/whisper-large-v3-turbo", condition_on_previous_text=False)
    frasi = []
    for g in r["segments"]:
        f = {"t": round(da + g["start"], 1), "fine": round(da + g["end"], 1), "testo": g["text"].strip()}
        if f["testo"] and not (frasi and frasi[-1]["testo"] == f["testo"]):  # via le ripetizioni identiche di fila
            frasi.append(f)
    json.dump({
        "sorgente": video, "durata": n, "lingua": r["language"],
        # il momento clou di una clip deve cadere qui dentro: prima è già stato deciso, dopo si decide al prossimo giro
        "zona": [max(0, n_prec - FINESTRA[1]), n if ultimo else n - FINESTRA[1]],
        "picchi": [{"t": t, "forza": round(f, 2)} for t, f in picchi(punteggio)],
        "frasi": frasi,
    }, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    # autocontrollo: un picco isolato deve essere trovato, il rumore di fondo no
    x = np.zeros(300); x[120] = 9.0
    assert picchi(x) == [(120, 9.0)] and picchi(np.zeros(300)) == []
    # a cavallo dei blocchi: un picco a 10 s dalla fine si rimanda, e il giro dopo (precedente di 300 s) lo prende una volta sola
    y = np.zeros(300); y[290] = 9.0; y[100] = 5.0
    assert picchi(utili(y, 0, False)) == [(100, 5.0)] and picchi(utili(y, 0, True)) == [(100, 5.0), (290, 9.0)]
    assert picchi(utili(np.concatenate([y, np.zeros(300)]), 300, False)) == [(290, 9.0)]
    if len(sys.argv) > 1:
        main()
