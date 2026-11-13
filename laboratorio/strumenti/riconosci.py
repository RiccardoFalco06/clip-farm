"""Riconoscimento automatico del brano (Shazam) su più tratti di ogni Short. Manda a Shazam solo l'impronta audio.
uso: .venv-audio/bin/python riconosci.py riferimenti/audio/*.wav  -> riferimenti/musica.json (riprende da dove era arrivato)"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile

from shazamio import Shazam

OUT = "riferimenti/musica.json"


async def main():
    ris = json.load(open(OUT)) if os.path.exists(OUT) else {}
    sh = Shazam()
    for wav in sys.argv[1:]:
        vid = os.path.basename(wav)[:-4]
        if vid in ris:
            continue
        dur = float(subprocess.run(["ffprobe", "-v", "0", "-show_entries", "format=duration", "-of", "csv=p=0", wav], capture_output=True, text=True).stdout)
        trovati = {}
        for t0 in [x for x in (0, 8, 16, 24, 32, 40, 48) if x < max(1, dur - 6)]:
            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(t0), "-t", "12", "-i", wav, tmp.name], check=True)
                try:
                    r = await asyncio.wait_for(sh.recognize(tmp.name), 30)  # senza tetto una richiesta può restare appesa per sempre
                except Exception as e:
                    print(vid, t0, "errore", e, file=sys.stderr)
                    await asyncio.sleep(5)
                    continue
            tr = r.get("track")
            if tr:
                k = f"{tr.get('title')} — {tr.get('subtitle')}"
                trovati.setdefault(k, {"titolo": tr.get("title"), "artista": tr.get("subtitle"), "genere": (tr.get("genres") or {}).get("primary"), "tratti": []})["tratti"].append(t0)
            await asyncio.sleep(1.5)
        ris[vid] = list(trovati.values())
        json.dump(ris, open(OUT, "w"), ensure_ascii=False, indent=1)
        print(vid, [(x["titolo"], x["artista"], x["tratti"]) for x in ris[vid]], flush=True)


asyncio.run(main())
