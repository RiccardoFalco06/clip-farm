"""Testo di una clip, robusto.

uso: ~/Projects/video-editor/.venv/bin/python -I trascrivi.py CARTELLA   (legge vocals.wav, scrive whisper.json)
Con due voci insieme (streamer + personaggi del gioco) Whisper spesso ne segue una sola e salta l'altra, oppure
entra in un ciclo di ripetizioni; quale delle due dipende da modello e punto di partenza (misurato sulle clip di
prova: stessa clip, 4 parole oppure 76). Si fanno fino a quattro prove (due modelli, con e senza 3 s di silenzio davanti)
e si tiene quella con più parole sicure, scartando i cicli. I tempi li decide poi l'allineatore della skill.
"""
import json
import re
import subprocess
import sys
import zlib

import numpy as np

SR = 16000
# prima le due veloci: se concordano e il parlato è fitto, le due lente non servono (quasi sempre, con una voce sola)
PROVE = [(m, pausa) for m in ("whisper-large-v3-turbo", "whisper-large-v3-mlx") for pausa in (0, 3)]


def basta(voti, secondi):
    a, b = sorted(voti)[-2:]
    return b >= secondi and a >= 0.9 * b  # almeno una parola al secondo, e le due migliori a meno del 10% l'una dall'altra


def scelta(voti):
    """Quale prova tenere: quella con più parole sicure tra le prove confermate da un'altra (entro il 30%); se nessuna è confermata, la più ricca.
    Una prova molto più lunga di tutte le altre è parlato inventato sul rumore del gioco (visto: 3, 16, 3, 2 parole → "GOT GLOUTS", "FACE THANK")."""
    confermate = [i for i, v in enumerate(voti) if v and any(j != i and u >= 0.7 * v and v >= 0.7 * u for j, u in enumerate(voti))]
    return max(confermate or range(len(voti)), key=lambda i: voti[i])


def voto(words):
    testo = " ".join(w["text"] for w in words).encode()
    if testo and len(testo) / len(zlib.compress(testo)) > 2.4:  # ciclo di ripetizioni (stessa soglia che usa Whisper)
        return 0
    return sum(w["p"] > 0.3 for w in words)  # spazzatura = probabilità quasi zero; frasi saltate = meno parole


def dette(words, altre, sicura=0.85, vicino=1.0):
    """Solo le parole dette davvero (Riccardo, 11 nov: "cerca di non mettere mai cose che non vengono dette"): quelle che un'altra
    prova ha sentito uguali nello stesso momento, oppure quelle di cui Whisper è quasi certo. Su versi, risate e rumore del gioco
    ogni prova inventa parole diverse, mentre il parlato vero lo sentono tutte uguale. Meglio una parola in meno che una inventata."""
    pulita = lambda x: re.sub(r"[^\w']", "", x).lower()
    sentita = lambda w: any(pulita(x["text"]) == pulita(w["text"]) and abs(x["start"] - w["start"]) <= vicino for a in altre for x in a)
    ok = [bool(pulita(w["text"])) and sentita(w) for w in words]
    # una parola non confermata passa solo se Whisper ne è quasi certo E sta in mezzo a parlato confermato (entro 1,5 s):
    # da sola sul rumore è il classico "Thank you." inventato (visto: clip senza parlato, restava "you.")
    accanto = lambda w: any(c and abs(x["start"] - w["start"]) <= 1.5 for c, x in zip(ok, words))
    return [w for c, w in zip(ok, words) if c or (pulita(w["text"]) and w["p"] >= sicura and accanto(w))]


def senza(words, risposta):
    """Applica la risposta del controllo di coerenza: toglie solo le parole indicate. Se la risposta non è quella attesa non tocca niente."""
    togli = risposta.get("togli") if isinstance(risposta, dict) else None
    if not isinstance(togli, list) or not all(isinstance(i, int) and 0 <= i < len(words) for i in togli):
        return words
    return [w for i, w in enumerate(words) if i not in set(togli)]


def coerenti(words):
    """Controllo di coerenza sull'intera trascrizione (Riccardo, 11 nov): Sonnet legge tutte le parole in fila e indica quelle che
    non hanno senso una accanto all'altra (frammenti isolati, versi scritti come parole, frasi inventate sul rumore). Può solo togliere.
    Se la chiamata non riesce la trascrizione resta com'è: dopo c'è ancora la casella "il testo dei sottotitoli ha senso" del controllo qualità."""
    if not words:
        return words
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import catena
    try:
        r = catena.primo_json(catena.chiedi((Path(__file__).resolve().parent / "prompt/coerenza.md").read_text(),
                                            {"PAROLE": "\n".join(f"{i} | {w['start']:.1f} | {w['text']}" for i, w in enumerate(words))}), "{")
    except Exception as e:  # limite d'uso, rete, risposta senza JSON
        print(f"controllo di coerenza non riuscito ({type(e).__name__}): trascrizione lasciata com'è", file=sys.stderr)
        return words
    tenute = senza(words, r)
    if len(tenute) < len(words):
        print(f"controllo di coerenza: tolte {len(words) - len(tenute)} parole su {len(words)} ({' '.join(w['text'] for w in words if w not in tenute)[:200]}) — {str(r.get('motivo', ''))[:200]}", file=sys.stderr)
    return tenute


def prova(audio, modello, pausa):
    import mlx_whisper

    x = np.concatenate([np.zeros(pausa * SR, dtype=np.float32), audio])
    r = mlx_whisper.transcribe(x, path_or_hf_repo=f"mlx-community/{modello}", language="en", word_timestamps=True, condition_on_previous_text=False)
    return [{"text": w["word"].strip(), "start": max(0, w["start"] - pausa), "end": max(0, w["end"] - pausa), "p": w["probability"]}
            for s in r["segments"] for w in s["words"] if w["word"].strip()]


if __name__ == "__main__":
    assert voto([{"text": "ciao", "p": 0.9}, {"text": "x", "p": 0.0003}]) == 1
    assert voto([{"text": "P .C .O .E .G .E.", "p": 0.9}] * 20) == 0
    assert basta([93, 93], 23) and not basta([4, 4], 31) and not basta([4, 10, 2], 31) and basta([59, 61, 64], 23)
    assert scelta([3, 16, 3, 2]) == 0 and scelta([4, 76, 70, 5]) == 1 and scelta([5, 0, 5, 0]) == 0 and scelta([4, 76]) == 1 and scelta([26, 45, 47]) == 2 and scelta([0, 0]) == 0
    W = lambda x, s, p: {"text": x, "start": s, "end": s + 0.2, "p": p}
    vera, altra = [W("Oh", 1, 0.5), W("my", 1.3, 0.4), W("God!", 1.6, 0.95), W("Thank", 9, 0.6), W("you.", 9.3, 0.7), W("...", 12, 0.9)], [W("oh", 1.2, 0.6), W("my", 1.5, 0.5), W("Bye", 9, 0.6)]
    assert [w["text"] for w in dette(vera, [altra])] == ["Oh", "my", "God!"]  # confermate o quasi certe; "Thank you" inventato sul rumore sparisce
    assert senza(vera, {"togli": [3, 4]}) == vera[:3] + vera[5:] and senza(vera, {"togli": [99]}) == vera and senza(vera, "boh") == vera and senza(vera, {"togli": []}) == vera
    assert dette(vera, []) == [] and dette([], [altra]) == [] and dette([W("you.", 5, 0.99)], [[W("Bye", 5, 0.9)]]) == []
    if len(sys.argv) > 1:
        d = sys.argv[1]
        pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", f"{d}/vocals.wav", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, check=True).stdout
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        esiti = []
        for p in PROVE:
            esiti.append(prova(audio, *p))
            if len(esiti) >= 2 and basta([voto(e) for e in esiti], len(audio) / SR):
                break
        print("parole sicure per prova:", [voto(e) for e in esiti], file=sys.stderr)
        k = scelta([voto(e) for e in esiti])
        words = dette(esiti[k], esiti[:k] + esiti[k + 1:])
        if tolte := [w["text"] for w in esiti[k] if w not in words]:
            print(f"parole tolte perché non confermate ({len(tolte)} su {len(esiti[k])}):", " ".join(tolte), file=sys.stderr)
        if "--senza-coerenza" not in sys.argv:  # storie: il tratto è fatto di frammenti e le ripetizioni sono dette davvero (12/11: tolto "Who are you today?", la premessa)
            words = coerenti(words)
        json.dump({"text": " ".join(w["text"] for w in words), "words": words}, open(f"{d}/whisper.json", "w"), ensure_ascii=False, indent=1)
