"""Lettura fotogrammi con ffmpeg -> numpy. Regola di memoria: i video si leggono IN FLUSSO (un fotogramma alla volta, già
ridotti o ritagliati da ffmpeg); frames() carica in memoria solo pezzi piccoli e si rifiuta sopra 300 MB."""
import subprocess

import numpy as np

TETTO = 300 * 1024 * 1024


def dims(path):
    w, h = subprocess.run(["ffprobe", "-v", "0", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                          capture_output=True, text=True, check=True).stdout.strip().split(",")[:2]
    return int(w), int(h)


def _uscita(path, crop, larg):
    """Dimensioni dei fotogrammi dopo crop (w,h,x,y: arrotondato ai pari come fa ffmpeg) e riduzione a `larg` px di larghezza."""
    w, h = dims(path)
    vf = []
    if crop:
        cw, ch, cx, cy = crop
        cw, ch = cw // 2 * 2, ch // 2 * 2
        vf.append(f"crop={cw}:{ch}:{cx}:{cy}:exact=1")
        w, h = cw, ch
    if larg:
        h = round(h * larg / w / 2) * 2
        w = larg
        vf.append(f"scale={w}:{h}:flags=area")
    return w, h, vf


def flusso(path, t0=0, dur=None, fps=None, crop=None, larg=None):
    """Genera i fotogrammi (h, w, 3) uint8 uno alla volta: in memoria ce n'è sempre uno solo."""
    w, h, vf = _uscita(path, crop, larg)
    if fps:
        vf.insert(0, f"fps={fps}")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t0)] + (["-t", str(dur)] if dur else []) + ["-i", path] + (["-vf", ",".join(vf)] if vf else []) + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        p.stdout.close()
        p.wait()


def frames(path, t0=0, dur=None, fps=None, crop=None, larg=None):
    """Array (n, h, w, 3) uint8 di un pezzo PICCOLO (ritaglio o pochi fotogrammi). Sopra 300 MB si ferma."""
    out, tot = [], 0
    for f in flusso(path, t0, dur, fps, crop, larg):
        tot += f.nbytes
        assert tot < TETTO, "troppi fotogrammi in memoria: usa flusso(), un ritaglio o larg="
        out.append(f)
    return np.stack(out)


def frame(path, t, crop=None):
    """Un fotogramma (h, w, 3). crop=(w,h,x,y) ritagliato in numpy (preciso anche con misure dispari)."""
    w, h = dims(path)
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(h, w, 3)
    return f[crop[3]:crop[3] + crop[1], crop[2]:crop[2] + crop[0]] if crop else f


def png(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGB"))


def salva(arr, path):
    from PIL import Image
    Image.fromarray(arr.astype(np.uint8)).save(path)
