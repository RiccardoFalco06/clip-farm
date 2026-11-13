"""Sentinella: un giro al minuto (launchd). Solo codice, nessun modello.

uso: python3 -I sentinella.py            un giro vero
     python3 -I sentinella.py --guarda   stampa la classifica e non tocca niente
Guarda chi è in live (Twitch, YouTube, Kick), sceglie le live da registrare ("chi ha i numeri più alti vince"),
avvia e ferma i registratori, rileva il lancio di GTA 6.
"""
import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con -I la cartella dello script non è nel percorso
from obsidian import VAULT, campo, genera, nome  # noqa: E402
from stato import CONFIG, QUI, REG, db, evento, kv  # noqa: E402

BIN = Path.home() / ".local/bin"
GTA6 = re.compile(CONFIG["gta6"], re.I)
SEGRETI = json.loads((QUI / "segreti.json").read_text()) if (QUI / "segreti.json").exists() else {}


def scarica(url, intestazioni=None, dati=None):
    req = urllib.request.Request(url, data=dati, headers={"User-Agent": "Mozilla/5.0", **(intestazioni or {})})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def helix(percorso):
    """API ufficiale di Twitch: l'unico modo lecito per avere gli spettatori dal vivo. Serve la chiave in segreti.json."""
    if "gettone" not in SEGRETI:  # uno per giro
        SEGRETI["gettone"] = scarica("https://id.twitch.tv/oauth2/token", dati=urllib.parse.urlencode(
            {"client_id": SEGRETI["twitch_client_id"], "client_secret": SEGRETI["twitch_client_secret"], "grant_type": "client_credentials"}).encode())["access_token"]
    return scarica("https://api.twitch.tv/helix/" + percorso, {"Client-Id": SEGRETI["twitch_client_id"], "Authorization": "Bearer " + SEGRETI["gettone"]})["data"]


def twitch(canale):
    r = json.loads(subprocess.run([BIN / "streamlink", "--json", f"twitch.tv/{canale}"], capture_output=True, text=True, timeout=40).stdout)
    m = r.get("metadata")
    return m and {"url": f"https://twitch.tv/{canale}", "titolo": m.get("title") or "", "gioco": m.get("category") or "", "spettatori": None}


def kick(canale):
    l = scarica(f"https://kick.com/api/v2/channels/{canale}").get("livestream")
    return l and {"url": f"https://kick.com/{canale}", "titolo": l.get("session_title") or "",
                  "gioco": ", ".join(c["name"] for c in l.get("categories", [])), "spettatori": l.get("viewer_count")}


def youtube(canale):
    # 12/11: yt-dlp su un canale offline impiegava ~28 s e spesso superava il limite di 30 (279 controlli saltati). Prima la pagina /live
    # (7-9 s): se non è in live si chiude lì; se lo è, la pagina dà il link del video e yt-dlp legge titolo e spettatori con più margine.
    req = urllib.request.Request(f"https://www.youtube.com/{canale}/live", headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en", "Cookie": "SOCS=CAI"})
    pagina = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
    video = in_live(pagina)
    if not video:
        return None
    r = subprocess.run([BIN / "yt-dlp", "--dump-json", "--no-download", video], capture_output=True, text=True, timeout=90).stdout
    d = json.loads(r) if r.strip() else {}
    titolo = re.search(r'<meta property="og:title" content="([^"]*)"', pagina)
    return {"url": d.get("webpage_url", video), "titolo": d.get("title") or (html.unescape(titolo.group(1)) if titolo else ""), "gioco": "", "spettatori": d.get("concurrent_view_count")}


def in_live(pagina):
    """Il link del video se la pagina /live di un canale mostra una diretta in corso, altrimenti None."""
    link = re.search(r'<link rel="canonical" href="(https://www\.youtube\.com/watch\?v=[\w-]+)"', pagina)
    return link.group(1) if link and '"isLiveNow":true' in pagina else None


PIATTAFORME = {"twitch": twitch, "youtube": youtube, "kick": kick}


def nuove(trovate, noti, minimo, gta=GTA6):
    """Tra le live trovate tiene quelle di GTA 6, sopra il minimo di spettatori, di canali non già in elenco."""
    return [(s, p, l) for s, p, l in trovate if (p, s[p].lower()) not in noti and l["spettatori"] >= minimo and gta.search(l["titolo"] + " " + l["gioco"])]


def scopri():
    """Live in inglese di canali non in elenco: categoria GTA VI su Twitch (API ufficiale), le 50 più viste su Kick.
    shortcut: YouTube non ha un elenco gratuito delle live più viste; lì i canali nuovi li porta lo scout."""
    trovate = []
    try:
        if SEGRETI.get("twitch_client_secret"):
            for g in helix("games?name=" + urllib.parse.quote("Grand Theft Auto VI")):
                trovate += [({"nome": x["user_name"], "twitch": x["user_login"]}, "twitch",
                             {"url": f"https://twitch.tv/{x['user_login']}", "titolo": x["title"], "gioco": x["game_name"], "spettatori": x["viewer_count"]})
                            for x in helix(f"streams?first=20&language=en&game_id={g['id']}")]
    except Exception as e:
        print(f"[scopri/twitch] {type(e).__name__}: {e}", file=sys.stderr)
    try:
        trovate += [({"nome": x["channel"]["user"]["username"], "kick": x["channel"]["slug"]}, "kick",
                     {"url": f"https://kick.com/{x['channel']['slug']}", "titolo": x.get("session_title") or "",
                      "gioco": ", ".join(c["name"] for c in x.get("categories", [])), "spettatori": x["viewer_count"]})
                    for x in scarica("https://kick.com/stream/livestreams/en?sort=desc&limit=50")["data"] if x.get("language") == "English"]
    except Exception as e:
        print(f"[scopri/kick] {type(e).__name__}: {e}", file=sys.stderr)
    return nuove(trovate, {(p, s[p].lower()) for s in CONFIG["streamer"] for p in PIATTAFORME if s.get(p)}, CONFIG["scoperta_minimo"])


def guarda():
    """Una riga per streamer in live: la piattaforma con più spettatori, punteggio sulla somma."""
    # "stato: escluso" nella scheda Obsidian dello streamer = non seguirlo
    escluso = lambda s: (f := VAULT / "Streamer" / f"{nome(s['nome'])}.md").exists() and campo(f.read_text(), "stato") == "escluso"
    lavori = [(s, p, s[p]) for s in CONFIG["streamer"] if not escluso(s) for p in PIATTAFORME if s.get(p)]

    def uno(l):
        s, p, canale = l
        try:
            return s, p, PIATTAFORME[p](canale)
        except Exception as e:  # una piattaforma che non risponde non deve fermare il giro
            print(f"[{p}/{canale}] {type(e).__name__}: {e}", file=sys.stderr)
            return s, p, None

    with ThreadPoolExecutor(8) as ex:
        esiti = [e for e in ex.map(uno, lavori) if e[2]]
    vivi = {}
    if SEGRETI.get("twitch_client_id"):
        canali = [s["twitch"] for s, p, _ in esiti if p == "twitch"]
        try:
            vivi = {x["user_login"]: x["viewer_count"] for x in helix("streams?" + "&".join("user_login=" + c for c in canali))} if canali else {}
        except Exception as e:
            print(f"[helix] {type(e).__name__}: {e}", file=sys.stderr)
    righe = {}
    for s, p, l in esiti:
        if p == "twitch":
            l["spettatori"] = vivi.get(s["twitch"])
    for s, p, l in esiti + scopri():
        n = l["spettatori"] if l["spettatori"] is not None else s.get("media", 0)
        r = righe.setdefault(s["nome"], {"streamer": s["nome"], "tot": 0, "max": -1, "gta6": False})
        r["tot"] += n
        if s not in CONFIG["streamer"]:
            r.setdefault("nuovo", {}).update(s)  # scoperto adesso: giro() lo aggiunge all'elenco
        r["gta6"] |= bool(GTA6.search(l["titolo"] + " " + l["gioco"]))
        if n > r["max"]:
            r.update(max=n, piattaforma=p, stimati=l["spettatori"] is None, **l)
    for r in righe.values():
        r["spettatori"] = r["tot"]
        r["punteggio"] = r["tot"] * (2 if r["gta6"] else 1) * next((s.get("campagna", 1) for s in CONFIG["streamer"] if s["nome"] == r["streamer"]), 1)
    return sorted(righe.values(), key=lambda r: -r["punteggio"])


def scegli(classifica, attuali, sfide, ora, capienza=CONFIG["capienza"], margine=CONFIG["isteresi"]["margine"], attesa=CONFIG["isteresi"]["minuti"] * 60):
    """Chi registrare. Una sfidante scalza una live in corso solo se resta sopra del margine per tutta l'attesa:
    così non si salta avanti e indietro tra due live vicine. `sfide` (streamer -> da quando è sopra) viene aggiornato."""
    punti = {r["streamer"]: r["punteggio"] for r in classifica}
    tenute = sorted((s for s in attuali if s in punti), key=punti.get, reverse=True)[:capienza]  # chi ha chiuso la live esce subito; se la capienza è scesa restano le più forti
    for r in classifica:
        s = r["streamer"]
        if s in tenute:
            continue
        if len(tenute) < capienza:
            tenute.append(s)
            continue
        debole = min(tenute, key=punti.get)
        if punti[s] > punti[debole] * margine:
            sfide.setdefault(s, ora)
            if ora - sfide[s] >= attesa:
                tenute[tenute.index(debole)] = s
                del sfide[s]
        else:
            sfide.pop(s, None)
    for s in [s for s in sfide if s not in punti or s in tenute]:
        del sfide[s]
    return tenute


def vivo(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def mancanti(registrate, viste, visti, ora, vivo, grazia=300):
    """Live registrate sparite da questo controllo ma col registratore ancora acceso e viste meno di `grazia` secondi fa."""
    return [l for l in registrate if l["streamer"] not in viste and vivo(l["pid"]) and ora - visti.get(l["streamer"], l["inizio"]) < grazia]


def tenute_in_vita(c, classifica, ora):
    # visto il 12 nov (Streamer Awards): con la rete che va e viene il controllo di Twitch scade (40 s), la live spariva dalla
    # classifica e la registrazione veniva chiusa e riaperta ogni pochi minuti. Se il registratore gira ancora, la si tiene 5 minuti.
    visti = {**(kv(c, "visti") or {}), **{r["streamer"]: ora for r in classifica}}
    kv(c, "visti", visti)
    registrate = c.execute("select * from live where fine is null and registrata=1").fetchall()
    return [{"streamer": l["streamer"], "piattaforma": l["piattaforma"], "url": l["url"], "titolo": l["titolo"], "gioco": l["gioco"],
             "spettatori": l["spettatori"], "punteggio": l["spettatori"] or 0, "gta6": bool(l["gta6"]), "stimati": True}
            for l in mancanti(registrate, {r["streamer"] for r in classifica}, visti, ora, vivo)]


def giro():
    c = db()
    ora = time.time()
    classifica = guarda()
    classifica += tenute_in_vita(c, classifica, ora)
    righe = {r["streamer"]: r for r in classifica}
    aperte = {l["streamer"]: l for l in c.execute("select * from live where fine is null")}
    if scoperti := [r["nuovo"] for r in classifica if r.get("nuovo")]:
        # entrano tra i seguiti come quelli dello scout: per toglierne uno, "stato: escluso" nella sua scheda
        cfg = json.loads((QUI / "config.json").read_text())
        cfg["streamer"] += scoperti
        (QUI / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        evento(c, "streamer scoperto", ", ".join(f"{r['streamer']} ({r['spettatori']:,} su {r['piattaforma']})" for r in classifica if r.get("nuovo")))

    for s, l in aperte.items():  # live finite, o registratore caduto (lo si rilancia più sotto come live nuova)
        if s not in righe or (l["registrata"] and not vivo(l["pid"])):
            c.execute("update live set fine=? where id=?", (ora, l["id"]))
            if l["registrata"]:
                if vivo(l["pid"]):  # sparita dalla classifica (rete giù) ma il registratore gira ancora: senza questo resta orfano e riempie il disco
                    os.killpg(l["pid"], signal.SIGTERM)
                (REG / str(l["id"]) / "FINE").touch()
                evento(c, "live finita", f"{s}: registrazione chiusa" + ("" if s not in righe else " (registratore caduto, riparte)"))
    aperte = {s: l for s, l in aperte.items() if s in righe and not (l["registrata"] and not vivo(l["pid"]))}

    for s, r in righe.items():
        if s in aperte:
            c.execute("update live set spettatori=?, picco=max(picco, ?), titolo=?, gioco=?, gta6=max(gta6, ?) where id=?",
                      (r["spettatori"], r["spettatori"], r["titolo"], r["gioco"], int(r["gta6"]), aperte[s]["id"]))
        else:
            c.execute("insert into live (streamer, piattaforma, url, titolo, gioco, inizio, spettatori, picco, gta6) values (?,?,?,?,?,?,?,?,?)",
                      (s, r["piattaforma"], r["url"], r["titolo"], r["gioco"], ora, r["spettatori"], r["spettatori"], int(r["gta6"])))
    aperte = {l["streamer"]: l for l in c.execute("select * from live where fine is null")}

    if any(r["gta6"] for r in classifica) and not kv(c, "lancio"):
        kv(c, "lancio", ora)
        evento(c, "LANCIO GTA 6", "GTA 6 è partito: " + ", ".join(r["streamer"] for r in classifica if r["gta6"]), email=True)

    sfide = kv(c, "sfide") or {}
    scelte = scegli(classifica, [s for s, l in aperte.items() if l["registrata"]], sfide, ora)
    kv(c, "sfide", sfide)
    REG.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(REG).free < 6e9:  # sotto 6 GB non si aprono registrazioni nuove (una live sono circa 3,5 GB l'ora)
        scelte = [s for s in scelte if aperte[s]["registrata"]]
        if ora - (kv(c, "disco") or 0) > 3600:
            kv(c, "disco", ora)
            evento(c, "disco pieno", f"restano {shutil.disk_usage(REG).free / 1e9:.1f} GB: nessuna registrazione nuova finché non si libera spazio", email=True)
    for s, l in aperte.items():
        if l["registrata"] and s not in scelte:  # scalzata da una live più forte
            os.killpg(l["pid"], signal.SIGTERM)
            c.execute("update live set registrata=0, pid=null where id=?", (l["id"],))
            (REG / str(l["id"]) / "FINE").touch()
            evento(c, "registrazione fermata", f"{s}: scalzata da una live con più spettatori")
        elif not l["registrata"] and s in scelte:
            d = REG / str(l["id"])
            d.mkdir(parents=True, exist_ok=True)
            p = subprocess.Popen(["/bin/zsh", str(QUI / "registra.sh"), str(d), l["url"], l["url"].rsplit("/", 1)[-1] if l["piattaforma"] == "twitch" else ""],
                                 start_new_session=True, stdout=open(d / "registra.log", "a"), stderr=subprocess.STDOUT)
            c.execute("update live set registrata=1, pid=? where id=?", (p.pid, l["id"]))
            r = righe[s]
            evento(c, "live registrata", f"{s} su {l['piattaforma']}: {r['spettatori']:,} spettatori{' (stima)' if r['stimati'] else ''} — {r['titolo']}", email=True)
    # riepilogo ogni ora mentre si registra: le clip dell'ultima ora
    if scelte and ora - (kv(c, "riepilogo") or 0) > 3600:
        fatte = c.execute("select clip.titolo, clip.stato, live.streamer, (select group_concat(url, ' ') from pubblicazione where clip = clip.id) as link "
                          "from clip join live on live.id = clip.live where clip.creato > ? and clip.stato != 'scartata'", (ora - 3600,)).fetchall()
        if kv(c, "riepilogo") and fatte:
            evento(c, "riepilogo dell'ora", f"{len(fatte)} clip: " + "; ".join(f"{k['streamer']} — {k['titolo']} ({k['link'] or k['stato']})" for k in fatte), email=True)
        kv(c, "riepilogo", ora)
    c.commit()
    genera()
    if c.execute("select 1 from evento where email=1 and inviata=0").fetchone():
        subprocess.Popen([sys.executable, "-I", str(QUI / "notifica.py")], start_new_session=True, stdout=open(QUI / "state/notifica.log", "a"), stderr=subprocess.STDOUT)


if __name__ == "__main__":
    assert in_live('<link rel="canonical" href="https://www.youtube.com/watch?v=4t4AQ15yj1M">..."isLiveNow":true') == "https://www.youtube.com/watch?v=4t4AQ15yj1M"
    _l = [{"streamer": "A", "pid": 1, "inizio": 0}, {"streamer": "B", "pid": 2, "inizio": 0}, {"streamer": "C", "pid": 3, "inizio": 0}]
    assert [x["streamer"] for x in mancanti(_l, {"A"}, {"B": 900, "C": 100}, 1000, lambda p: p != 3)] == ["B"]  # A visto, C registratore spento
    assert mancanti(_l[1:2], set(), {"B": 600}, 1000, lambda p: True) == []  # sparito da più di 5 minuti: si chiude
    assert in_live('<link rel="canonical" href="https://www.youtube.com/channel/UCx">') is None and in_live('<link rel="canonical" href="https://www.youtube.com/watch?v=abc">"isLiveNow":false') is None
    # autocontrollo della scelta: capienza, isteresi di 10 minuti, uscita di chi chiude
    cl = lambda **p: [{"streamer": s, "punteggio": v} for s, v in sorted(p.items(), key=lambda x: -x[1])]
    sf = {}
    assert scegli(cl(a=100, b=50, c=10), [], sf, 0, 2, 1.3, 600) == ["a", "b"]
    assert scegli(cl(a=100, b=50, c=60), ["a", "b"], sf, 0, 2, 1.3, 600) == ["a", "b"] and not sf  # sopra, ma meno del 30%
    assert scegli(cl(a=100, b=50, c=90), ["a", "b"], sf, 0, 2, 1.3, 600) == ["a", "b"] and sf == {"c": 0}
    assert scegli(cl(a=100, b=50, c=90), ["a", "b"], sf, 601, 2, 1.3, 600) == ["a", "c"] and not sf  # ha retto 10 minuti
    assert scegli(cl(b=50), ["a", "b"], sf, 0, 2, 1.3, 600) == ["b"]
    assert scegli(cl(a=100, b=50, c=10), ["b", "a"], sf, 0, 1, 1.3, 600) == ["a"]  # capienza scesa a 1: resta la più vista
    tr = [({"nome": "A", "kick": "a"}, "kick", {"titolo": "GTA 6 day one", "gioco": "", "spettatori": 20000}),
          ({"nome": "B", "kick": "b"}, "kick", {"titolo": "chill", "gioco": "Grand Theft Auto V (GTA)", "spettatori": 90000}),  # GTA 5 non è GTA 6
          ({"nome": "C", "twitch": "c"}, "twitch", {"titolo": "giveaway", "gioco": "Grand Theft Auto VI", "spettatori": 23}),
          ({"nome": "D", "twitch": "D"}, "twitch", {"titolo": "", "gioco": "Grand Theft Auto VI", "spettatori": 50000})]
    assert [s["nome"] for s, _, _ in nuove(tr, {("twitch", "d")}, 10000)] == ["A"]
    if "--guarda" in sys.argv:
        for r in guarda():
            print(f"{r['punteggio']:>9,.0f}  {r['streamer']:<16} {r['piattaforma']:<8} {r['spettatori']:>7,}{'~' if r['stimati'] else ' '} {'GTA6 ' if r['gta6'] else ''}{r['gioco'][:24]:<24} {r['titolo'][:50]}")
    elif "--prova" not in sys.argv:
        giro()
