"""Il ciclo di speedy-ultra (richiesta di Riccardo del 17 nov): agente 1 monta, agente 2 confronta con Speedy, un correttore
cambia l'agente 1, e si ripete sulle clip di allenamento finché il voto non arriva a 9,5 o smette di salire per 3 giri.
Poi la prova su 10 clip mai viste: con media >= 8,5 il modulo si salva in ~/Projects/clip-farm/stili/speedy-ultra/.

uso: python3 -I ultra/ciclo.py            (launchd com.riccardo.clipfarm.ultra: riprende da dove era arrivato)
     python3 -I ultra/ciclo.py --stato    (riassunto dei giri)
Stato in ultra/stato.json, tutto il resto in ultra/giri/gNN/. Pausa automatica negli intervalli di ultra/regole.json
(lancio di GTA 6: il ciclo consuma il limite d'uso che serve alla catena).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

QUI = Path(__file__).resolve().parent
FARM = next(p for p in QUI.parents if (p / "config.json").exists())
ED = QUI / "editore"
GIRI = QUI / "giri"
DATI = QUI / "dati"
PY = str(Path.home() / "Projects/video-editor/.venv/bin/python")
CLAUDE = str(Path.home() / ".local/bin/claude")
REGOLE = json.loads((QUI / "regole.json").read_text())


def scrivi(*a):
    riga = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(riga, flush=True)  # avvia.sh manda già lo stdout in ciclo.log


def stato():
    f = QUI / "stato.json"
    return json.loads(f.read_text()) if f.exists() else {"fase": "allenamento", "giro": 1, "storia": [], "migliore": None}


def salva_stato(s):
    (QUI / "stato.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))


def online():
    """Claude raggiungibile? (agente 1, giudice e correttore lo usano tutti)"""
    r = subprocess.run(["curl", "-s", "-m", "10", "-o", "/dev/null", "-w", "%{http_code}", "https://api.anthropic.com"], capture_output=True, text=True)
    return r.stdout.strip() not in ("", "000")


def libera(forza=False):
    """Disco pieno: cancella i video vecchi (Riccardo, 18/11: "cancella i video vecchi per liberare spazio in automatico"),
    dal meno utile, finché non ci sono 4 GB sopra la soglia. Si chiama tra una clip e l'altra, quando niente è in lavorazione."""
    voglio = (REGOLE.get("disco_minimo_gb", 8) + (8 if forza else 4)) * 2 ** 30  # dopo un "disco pieno" vero si libera di più
    pieno = lambda: shutil.disk_usage(Path.home()).free < voglio
    video = {".mp4", ".mkv", ".wav", ".mov", ".webm", ".ts"}
    # cartelle di lavoro dell'agente 1, intere: tenerne solo una parte rompeva le cache (S9m, 18/11: parole/ senza vocals.wav)
    gruppi = [sorted((ED / "lavoro").glob("*"), key=lambda d: d.stat().st_mtime),
              [GIRI / "scartati_rete"],
              [f for c in (FARM / "lavoro", FARM / "laboratorio/lavoro") for f in c.rglob("*")  # lavori vecchi della catena e del laboratorio
               if f.suffix in video and time.time() - f.stat().st_mtime > 7200]]
    giri = sorted(GIRI.glob("g[0-9][0-9]"))
    gruppi.append([f for g in giri[:-2] for f in g.glob("*.mp4")] + [f for g in giri[:-2] for f in g.glob("*_misure/fotogrammi")])  # clip dei giri vecchi
    gruppi.append(["pulizia"])  # clip vecchie di clip farm: pulizia.py tiene quelle in coda, pubblicate da poco o esplose
    rec = FARM / "registrazioni"  # live registrate dal sistema vivo, dalla più vecchia; non quelle toccate nelle ultime 2 ore
    gruppi.append(sorted((d for d in rec.glob("*") if time.time() - d.stat().st_mtime > 7200), key=lambda d: d.stat().st_mtime) if rec.exists() else [])
    for gruppo in gruppi:
        for f in gruppo:
            if not pieno():
                return
            if f == "pulizia":
                subprocess.run(["python3", "-I", str(FARM / "pulizia.py")], capture_output=True, timeout=1800)
                scrivi("disco pieno: pulizia.py delle clip vecchie di clip farm")
            elif f.exists():
                shutil.rmtree(f, ignore_errors=True) if f.is_dir() else f.unlink()
                scrivi(f"disco pieno: cancellato {f.relative_to(FARM)}")


def claude_ok():
    """Claude risponde? Col limite d'uso finito claude -p restituisce un avviso invece del JSON e ogni clip prendeva 0."""
    try:
        r = subprocess.run([CLAUDE, "-p", "rispondi solo: ok", "--model", "claude-haiku-5-5"], capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False
    return "ok" in r.stdout.lower() and "limit" not in r.stdout.lower()


def clipfarm_sotto_stress():
    """Riccardo, 18/11: con la RAM sotto stress ha la priorità clip farm (catena viva): il ciclo aspetta tra una clip e l'altra."""
    viva = subprocess.run(["/usr/bin/pgrep", "-f", "clip-farm/(catena|registra|sentinella)"], capture_output=True).returncode == 0
    livello = subprocess.run(["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"], capture_output=True, text=True).stdout.strip()
    return viva and livello not in ("", "1")  # 1 = normale, 2 = attenzione, 4 = critico


def in_pausa(ora=None):
    ora = ora or datetime.now()
    if clipfarm_sotto_stress():
        return True
    if not online():
        return True
    # disco: sotto 8 GB liberi il ciclo aspetta, le registrazioni delle live del sistema vivo vengono prima
    if shutil.disk_usage(Path.home()).free < REGOLE.get("disco_minimo_gb", 8) * 2 ** 30:
        libera()
    if shutil.disk_usage(Path.home()).free < REGOLE.get("disco_minimo_gb", 8) * 2 ** 30:
        return True
    return any(datetime.fromisoformat(a) <= ora < datetime.fromisoformat(b) for a, b in REGOLE["pause"])


def fotografia(dest):
    """Copia dell'agente 1 (senza file di lavoro): serve per tornare alla versione migliore."""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(ED, dest, symlinks=True, ignore=shutil.ignore_patterns("lavoro", "_ombra", "__pycache__", "out", ".cache", ".remotion"))


def ripristina(da):
    for p in ED.iterdir():
        if p.name not in ("lavoro", "_ombra"):
            shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
    for p in Path(da).iterdir():
        (shutil.copytree(p, ED / p.name, symlinks=True) if p.is_dir() and not p.is_symlink() else shutil.copy2(p, ED / p.name, follow_symlinks=False))


def una_clip(ident, cart):
    """Agente 1 -> misura -> agente 2 per una clip. Ogni passo si salta se il suo file esiste già (ripresa dopo un arresto)."""
    cart.mkdir(parents=True, exist_ok=True)
    src, voto = DATI / ident / "sorgente.mp4", cart / f"{ident}.voto.json"
    if voto.exists():
        return json.loads(voto.read_text())
    clip = cart / f"{ident}.mp4"
    if not clip.exists():
        # render a metà risoluzione solo nell'allenamento (più veloce); il modulo salvato rende a 1080x1440
        r = subprocess.run(["python3", "-I", str(ED / "edita.py"), str(src), str(clip), "IShowSpeed"], capture_output=True, text=True, timeout=7200,
                           env={**os.environ, "ULTRA_SCALA": str(REGOLE.get("scala_render_allenamento", 1))})
        (cart / f"{ident}.agente1.log").write_text(r.stdout + r.stderr)
        if r.returncode or not clip.exists():
            g = {"totale": 0.0, "errore": "agente 1: " + r.stderr[-600:]}
            voto.write_text(json.dumps(g, ensure_ascii=False, indent=1))
            return g
    mis = cart / f"{ident}_misure"
    if not (mis / "misure.json").exists():
        subprocess.run([PY, "-I", str(QUI / "misura.py"), str(clip), str(mis), "--sorgente", str(src)], check=True, capture_output=True, timeout=3600)
    subprocess.run(["python3", "-I", str(QUI / "giudice/giudica.py"), str(DATI / ident / "misure_originale"), str(mis), str(voto), str(DATI / ident / "fonte.json")],
                   check=True, capture_output=True, timeout=3600)
    shutil.rmtree(mis / "fotogrammi", ignore_errors=True)  # 40 MB a clip: per i giri dopo bastano fogli e misure
    return json.loads(voto.read_text())


def giro(ids, cart):
    voti = {}
    for ident in ids:
        while in_pausa():
            time.sleep(600)
        for prova in range(3):
            try:
                voti[ident] = una_clip(ident, cart)
            except Exception as e:  # una clip andata male non ferma il giro
                voti[ident] = {"totale": 0.0, "errore": f"{type(e).__name__}: {str(e)[-400:]}"}
            senza_spazio = "No space left" in json.dumps(voti[ident]) or "Errno 28" in json.dumps(voti[ident])
            if voti[ident].get("totale") or (online() and claude_ok() and not senza_spazio):
                break
            # 18/11: senza rete (11:45-12:44) o col disco pieno ogni clip prendeva 0 e falsava i giri; si aspetta e si rifà la clip
            scrivi(f"  {cart.name} {ident}: {'disco pieno' if senza_spazio else 'niente rete'}, aspetto e rifaccio")
            while not (online() and claude_ok()):
                time.sleep(600)
            libera(forza=senza_spazio)
            for f in cart.glob(f"{ident}*"):
                shutil.rmtree(f) if f.is_dir() else f.unlink()
        scrivi(f"  {cart.name} {ident}: {voti[ident].get('totale')}", voti[ident].get("errore", "")[:200])
    sezioni = {}
    for g in voti.values():
        for k, v in (g.get("voti") or {}).items():
            sezioni.setdefault(k, []).append(v)
    r = {"media": round(sum(g.get("totale", 0) for g in voti.values()) / len(voti), 2),
         "sezioni": {k: round(sum(v) / len(v), 2) for k, v in sorted(sezioni.items(), key=lambda x: sum(x[1]) / len(x[1]))},
         "per_clip": {k: g.get("totale") for k, g in voti.items()}, "errori": {k: g["errore"] for k, g in voti.items() if g.get("errore")}}
    (cart / "riassunto.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


def controlli():
    """L'agente 1 deve restare eseguibile: autocontrollo del montatore e tipi del progetto Remotion."""
    a = subprocess.run(["python3", "-I", str(ED / "monta.py")], capture_output=True, text=True, timeout=600)
    b = subprocess.run(["npx", "tsc", "--noEmit", "-p", "."], capture_output=True, text=True, timeout=600, cwd=ED / "remotion")
    c = subprocess.run(["python3", "-c", f"import ast;ast.parse(open('{ED / 'edita.py'}').read())"], capture_output=True, text=True)
    return [x for x, r in (("monta.py", a), ("remotion tsc", b), ("edita.py", c)) if r.returncode], (a.stderr + b.stdout + c.stderr)[-1500:]


def migliora(s, cart):
    prompt = (QUI / "prompt/migliora.md").read_text()
    storia = "\n".join(f"- giro {x['giro']}: media {x['media']} — sezioni più basse: {list(x['sezioni'].items())[:5]}" for x in s["storia"])
    for k, v in {"GIRO": s["giro"], "CARTELLA": cart, "STORIA": storia, "GIRI": GIRI, "DATI": DATI, "EDITORE": ED, "FARM": FARM}.items():
        prompt = prompt.replace("{{" + k + "}}", str(v))
    r = subprocess.run([CLAUDE, "-p", prompt, "--model", REGOLE["modello_correttore"], "--max-turns", "200",
                        "--allowedTools", "Read", "Edit", "Write", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"],
                       capture_output=True, text=True, timeout=3 * 3600, cwd=ED)
    (cart / "correttore.log").write_text(r.stdout[-20000:] + "\n---\n" + r.stderr[-5000:])


def salva_modulo(s):
    dest = FARM / "stili/speedy-ultra"
    fotografia(dest)
    (dest / "LEGGIMI.md").write_text(
        f"# Stile speedy-ultra\n\nSalvato il {time.strftime('%Y-%m-%d %H:%M')} dal ciclo di ultra/ciclo.py.\n"
        f"Media sulle clip di allenamento: {s['migliore']['media']} (giro {s['migliore']['giro']}). "
        f"Media sulle clip mai viste: {s['verifica']['media']}.\n"
        "Agente 1: edita.py (sorgente -> clip), prompt/, monta.py, remotion/. Si attiva con \"stile\": \"speedy-ultra\" in config.json.\n")


def main():
    s = stato()
    el = json.loads((DATI / "elenco.json").read_text())
    tutti = el["allenamento"] + el["verifica"]
    if len(tutti) < 3:
        scrivi(f"solo {len(tutti)} Short con la live trovata: il ciclo non parte")
        return
    if s.get("allenamento"):  # l'allenamento resta quello del primo giro; la verifica prende anche gli Short trovati dopo
        el = {"allenamento": s["allenamento"], "verifica": [x for x in tutti if x not in s["allenamento"]]}
    elif len(el["verifica"]) < 3:  # live trovate per meno Short del previsto: un terzo resta per la prova finale, mai visto in allenamento
        el = {"allenamento": tutti[: len(tutti) * 2 // 3], "verifica": tutti[len(tutti) * 2 // 3:]}
        scrivi(f"live trovate solo per {len(tutti)} Short: {len(el['allenamento'])} in allenamento, {len(el['verifica'])} in verifica")
    s["allenamento"] = el["allenamento"]
    while s["fase"] in ("allenamento", "verifica"):
        while in_pausa():
            time.sleep(600)
        if s["fase"] == "allenamento":
            cart = GIRI / f"g{s['giro']:02d}"
            if not (cart / "editore_prima").exists():
                fotografia(cart / "editore_prima")
            scrivi(f"giro {s['giro']}: {len(el['allenamento'])} clip")
            r = giro(el["allenamento"], cart)
            s["storia"].append({"giro": s["giro"], "media": r["media"], "sezioni": r["sezioni"]})
            if not s["migliore"] or r["media"] > s["migliore"]["media"]:
                s["migliore"] = {"giro": s["giro"], "media": r["media"], "editore": str(cart / "editore_prima")}
            scrivi(f"giro {s['giro']}: media {r['media']} (migliore {s['migliore']['media']} al giro {s['migliore']['giro']})")
            fermo = len(s["storia"]) - [x["giro"] for x in s["storia"]].index(s["migliore"]["giro"]) - 1  # giri senza migliorare
            if r["media"] >= REGOLE["obiettivo_allenamento"] or fermo >= REGOLE["giri_senza_migliorare"] or s["giro"] >= REGOLE["giri_massimi"]:
                ripristina(s["migliore"]["editore"])
                s["fase"], s["motivo_fine_allenamento"] = "verifica", ("obiettivo" if r["media"] >= REGOLE["obiettivo_allenamento"] else f"fermo da {fermo} giri" if fermo else "giri finiti")
                salva_stato(s)
                continue
            if r["media"] < s["migliore"]["media"] - 0.3:  # peggiorato: si riparte dalla versione migliore, il correttore vede tutto lo storico
                ripristina(s["migliore"]["editore"])
            prima = list(ED.glob("**/*"))
            migliora(s, cart)
            rotti, perche = controlli()
            if rotti:  # il correttore ha rotto qualcosa: si torna a com'era prima di lui
                scrivi(f"giro {s['giro']}: correzioni annullate, non passano {rotti}: {perche[-300:]}")
                ripristina(cart / "editore_prima")
            scrivi(f"giro {s['giro']}: correttore finito ({len(list(ED.glob('**/*'))) - len(prima):+d} file)")
            s["giro"] += 1
            salva_stato(s)
        else:
            el2 = json.loads((DATI / "elenco.json").read_text())  # la ricerca delle live continua in parallelo: Short nuovi = verifica più ampia
            el["verifica"] = [x for x in el2["allenamento"] + el2["verifica"] if x not in s["allenamento"]]
            r = giro(el["verifica"], GIRI / "verifica")
            s["verifica"] = {"media": r["media"], "sezioni": r["sezioni"]}
            ok = r["media"] >= REGOLE["obiettivo_verifica"]
            scrivi(f"verifica su clip mai viste: media {r['media']} -> {'SALVATO' if ok else 'non basta'}")
            if ok:
                salva_modulo(s)
            s["fase"] = "salvato" if ok else "verifica_fallita"
            salva_stato(s)
    subprocess.run(["launchctl", "bootout", f"gui/{subprocess.run(['id', '-u'], capture_output=True, text=True).stdout.strip()}/com.riccardo.clipfarm.ultra"], capture_output=True)


if __name__ == "__main__":
    if "--stato" in sys.argv:
        s = stato()
        print(json.dumps({k: v for k, v in s.items() if k != "storia"}, ensure_ascii=False), *[f"giro {x['giro']}: {x['media']}" for x in s["storia"]], sep="\n")
    elif "--prova" in sys.argv:
        assert not any(datetime.fromisoformat(a) <= datetime(2026, 11, 18, 12) < datetime.fromisoformat(b) for a, b in REGOLE["pause"])
        print("ok")
    else:
        main()
