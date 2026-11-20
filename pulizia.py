"""Cancella i video GENERATI da noi che Riccardo non apre da `GIORNI` giorni (richiesta del 2026-11-14: liberare spazio).
Mai i suoi originali: si guarda solo nelle cartelle di uscita qui sotto. Si tengono le clip in coda e quelle pubblicate di recente
o esplose (servono per ripubblicarle sugli altri social).
uso: python3 -I pulizia.py [--prova]   (launchd, ogni 10 minuti)"""
import sqlite3, subprocess, sys, time
from pathlib import Path

GIORNI = 14
SPAZIO = 8e9  # sotto 8 GB liberi parte il ricambio: la sentinella registra 2 live solo sopra 6 GB
H = Path.home()
QUI = H / "Projects/clip-farm"
CARTELLE = [QUI / "clip", QUI / "lavoro", QUI / "laboratorio/lavoro", H / "Desktop/Clip Farm",
            H / "Projects/video-editor/out"]  # non video-editor/work: lì ci sono proxy e sorgenti dei progetti di Studio
VIDEO = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def ultimo_uso(f):
    """Ultima apertura (Spotlight, la aggiorna Finder/QuickTime); se mai aperto, quando è stato creato o modificato."""
    st = f.stat()
    t = max(st.st_birthtime, st.st_mtime)
    out = subprocess.run(["mdls", "-raw", "-name", "kMDItemLastUsedDate", str(f)], capture_output=True, text=True).stdout.strip()
    if out and out != "(null)":
        try:
            t = max(t, time.mktime(time.strptime(out[:19], "%Y-%m-%d %H:%M:%S")) - time.timezone)
        except ValueError:
            pass
    return t


def da_tenere(c, ora, esplosa):
    """File delle clip ancora utili: in coda, pubblicate da meno di GIORNI giorni, o esplose."""
    righe = c.execute("""select clip.file from clip where clip.stato = 'montata' or exists (select 1 from pubblicazione p where p.clip = clip.id
                         and (p.quando > ? or coalesce(p.visualizzazioni, 0) >= ?))""", (ora - GIORNI * 86400, esplosa)).fetchall()
    tieni = set()
    for (f,) in righe:
        if f:
            tieni |= {Path(f), Path(f).with_name(Path(f).stem + "_web.mp4")}
            tieni |= set(Path(f).parent.glob(Path(f).stem + "_*.mp4"))  # copie con filigrana delle campagne
    return tieni


def candidati(ora, tieni, giorni=GIORNI):
    for d in CARTELLE:
        for f in d.rglob("*") if d.exists() else []:
            if f.is_file() and f.suffix.lower() in VIDEO and f not in tieni and ora - ultimo_uso(f) > giorni * 86400:
                yield f


def ricambio(c, ora, tieni, esplosa):
    """Riccardo, 19 nov: "man mano che si occupa spazio, cancella le cose di clip farm meno recenti". In ordine, dal più vecchio:
    video nostri non più utili (anche sotto i GIORNI), registrazioni di live finite da 2 ore, clip pubblicate non esplose.
    Mai le clip in coda né quelle esplose."""
    video = sorted((f for f in candidati(ora, tieni, 2 / 24) if "Desktop" not in f.parts), key=ultimo_uso)  # le copie sul Desktop sono per Riccardo: solo la regola dei GIORNI; 2 ore: una clip appena montata non è ancora nel database
    reg = [QUI / "registrazioni" / str(i) for (i,) in c.execute("select id from live where fine is not null and fine < ? order by fine", (ora - 7200,))]
    reg += sorted((d for d in (QUI / "registrazioni").glob("ripasso*") if d.is_dir() and ora - d.stat().st_mtime > 7200), key=lambda d: d.stat().st_mtime)
    # solo dopo 3 giorni dalla prima uscita: prima non si sa ancora se esplode (e allora va ripubblicata sugli altri social)
    pubblicate = [Path(f) for (f,) in c.execute("""select file from clip where stato = 'pubblicata' and file is not null and coalesce((select max(visualizzazioni)
                  from pubblicazione p where p.clip = clip.id), 0) < ? and (select min(quando) from pubblicazione p where p.clip = clip.id) < ? order by creato""", (esplosa, ora - 3 * 86400))]
    # cartelle di lavoro rimaste del laboratorio (prove, montaggi interrotti): ferme da 2 giorni
    lab = sorted((d for x in ("laboratorio/lavoro", "laboratorio/tmp") for d in (QUI / x).glob("*") if ora - d.stat().st_mtime > 2 * 86400), key=lambda d: d.stat().st_mtime)
    return [f for f in lab + video + reg + pubblicate if f.exists()]


if __name__ == "__main__":
    import json
    ora = time.time()
    esplosa = json.loads((QUI / "config.json").read_text()).get("esplosa_viste", 10000)
    c = sqlite3.connect(QUI / "state/clipfarm.db")
    tieni = da_tenere(c, ora, esplosa)
    prova = "--prova" in sys.argv
    tot = 0
    for f in candidati(ora, tieni):
        tot += f.stat().st_size
        print(("da cancellare " if prova else "cancellato ") + str(f))
        if not prova:
            f.unlink()
    import shutil, tempfile  # ogni render di Remotion lascia ~27 MB in T: in una notte di catena sono GB
    for d in [Path(tempfile.gettempdir()), Path("/private/tmp")]:
        for f in d.glob("*"):
            if f.name.startswith(("remotion-webpack-bundle-", "remotion-v4", "_MEI")) and ora - f.stat().st_mtime > 7200:
                tot += sum(x.stat().st_size for x in f.rglob("*") if x.is_file()) if f.is_dir() else f.stat().st_size
                print(("da cancellare " if prova else "cancellato ") + str(f))
                if not prova:
                    shutil.rmtree(f, ignore_errors=True)
    for f in ricambio(c, ora, tieni, esplosa) if shutil.disk_usage(QUI).free < SPAZIO else []:
        if shutil.disk_usage(QUI).free >= SPAZIO:
            break
        tot += sum(x.stat().st_size for x in f.rglob("*") if x.is_file()) if f.is_dir() else f.stat().st_size
        print(("da cancellare (ricambio) " if prova else "cancellato (ricambio) ") + str(f))
        if prova:
            continue  # shortcut: in prova lo spazio non cambia, quindi elenca tutto il ricambio possibile
        shutil.rmtree(f, ignore_errors=True) if f.is_dir() else f.unlink()
    print(f"{time.strftime('%F %T')} {'si libererebbero' if prova else 'liberati'} {tot / 1e9:.2f} GB")
