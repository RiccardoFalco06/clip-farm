"""Luce che lampeggia, misurata su OGNI fotogramma del file (fps nativi), in flusso con ffmpeg signalstats.
Zona: fascia alta del quadro (0-38% dell'altezza), dove negli Shorts 3:4 non passano sottotitoli né firma.
Per ogni fotogramma: YAVG, YMIN, YMAX e punteggio di stacco (scdet). Scarto = YAVG - mediana dei 4 fotogrammi prima
e dei 4 dopo. Un "lampeggio" = scarto di almeno 1,0 luma (0-255), lontano almeno 2 fotogrammi da uno stacco,
sotto 15 luma (sopra è un lampo colorato o un cambio di scena). Fotogrammi consecutivi con lo stesso verso = un lampeggio.
uso: python3 -I luce3.py video ...   (una riga di numeri per video; con --serie stampa anche i primi 120 scarti)
"""
import re
import subprocess
import sys

import numpy as np


def serie(video):
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", video, "-vf", "crop=iw:ih*0.38:0:0,signalstats,scdet=threshold=100,metadata=print:file=-",
                          "-an", "-f", "null", "-"], stdout=subprocess.PIPE, text=True)
    righe, cur = [], {}
    for r in p.stdout:
        if r.startswith("frame:"):
            if cur:
                righe.append(cur)
            cur = {}
        elif m := re.match(r"lavfi\.(signalstats\.(YAVG|YMIN|YMAX)|scd\.score)=([\d.]+)", r):
            cur[m.group(2) or "scd"] = float(m.group(3))
    if cur:
        righe.append(cur)
    p.wait()
    fps = eval(subprocess.run(["ffprobe", "-v", "0", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", video], capture_output=True, text=True).stdout.strip())
    return fps, np.array([[x.get("YAVG", 0), x.get("YMIN", 0), x.get("YMAX", 0), x.get("scd", 0)] for x in righe])


def misura(video, stampa=False):
    fps, a = serie(video)
    y, scd = a[:, 0], a[:, 3]
    n = len(y)
    rif = np.array([np.median(np.r_[y[max(0, i - 4):i], y[i + 1:i + 5]]) for i in range(n)])
    d = y - rif
    stacco = scd > 10
    vicino = np.convolve(stacco, np.ones(5), mode="same") > 0
    ev = (np.abs(d) >= 1.0) & (np.abs(d) < 15) & ~vicino
    lampeggi = []  # (inizio, durata in fotogrammi, scarto massimo con segno)
    i = 0
    while i < n:
        if ev[i]:
            j = i
            while j + 1 < n and ev[j + 1] and np.sign(d[j + 1]) == np.sign(d[i]):
                j += 1
            k = i + int(np.argmax(np.abs(d[i:j + 1])))
            lampeggi.append((i, j - i + 1, d[k]))
            i = j + 1
        else:
            i += 1
    sec = n / fps
    utili = (~vicino).sum() / fps
    durate = np.bincount([l[1] for l in lampeggi], minlength=5)[1:5] if lampeggi else []
    amp = np.abs([l[2] for l in lampeggi]) if lampeggi else np.array([0])
    inter = np.diff([l[0] for l in lampeggi]) / fps if len(lampeggi) > 1 else np.array([0])
    out = {"fps": round(fps, 2), "secondi": round(sec, 1), "stacchi": int(stacco.sum()), "lampeggi": len(lampeggi),
           "al_secondo": round(len(lampeggi) / max(utili, 0.1), 2), "intervallo_mediano_s": round(float(np.median(inter)), 3),
           "chiari": sum(l[2] > 0 for l in lampeggi), "scuri": sum(l[2] < 0 for l in lampeggi),
           "luma_mediana": round(float(np.median(amp)), 2), "luma_p90": round(float(np.percentile(amp, 90)), 2),
           "percento_mediano": round(float(np.median(amp / np.maximum(rif[[l[0] for l in lampeggi]], 1))) * 100, 2) if lampeggi else 0,
           "durata_fotogrammi_1_2_3_4": list(map(int, durate)), "luma_media_zona": round(float(y.mean()), 1)}
    if stampa:
        print("scarti:", " ".join(f"{x:+.1f}" for x in d[:120]))
    return out


if __name__ == "__main__":
    for v in [x for x in sys.argv[1:] if not x.startswith("--")]:
        print(v.rsplit("/", 1)[-1], misura(v, "--serie" in sys.argv), flush=True)
