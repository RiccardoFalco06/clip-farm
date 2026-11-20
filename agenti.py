"""Gli agenti che usano un modello (Sonnet): pubblicazione, conti, scout. Uno alla volta: Chrome è uno solo.

uso: python3 -I agenti.py                 giro di launchd: fa ciò che è in scadenza
     python3 -I agenti.py pubblica        una clip adesso, anche senza via libera automatico (primo giro, con Riccardo che guarda)
     python3 -I agenti.py conti | scout   subito
Il modello risponde con un JSON; quello che entra nel database lo decide questo codice.
"""
import json
import os
import random
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con -I la cartella dello script non è nel percorso
from obsidian import VAULT, genera  # noqa: E402
from stato import CONFIG, QUI, db, evento, kv, uno_alla_volta  # noqa: E402
import monta  # noqa: E402

CHROME = ["mcp__claude-in-chrome__" + x for x in ("tabs_context_mcp", "tabs_create_mcp", "tabs_close_mcp", "navigate", "computer", "read_page", "find",
                                                   "get_page_text", "form_input", "file_upload", "list_connected_browsers", "select_browser")]
PIATTAFORME = ("youtube", "instagram", "tiktok")
# account chiuso o sospeso; "dominio bloccato" è Chrome che non apre il sito, non l'account (visto con TikTok: aveva sospeso tutta la coda)
RIFIUTO = re.compile(r"dominio bloccato|permission denied|not allowed|chrome non disponibile", re.I)
BLOCCO = re.compile(r"^(?!.*dominio bloccato).*(sospes|bloccat|terminat|disabilitat|suspend|terminated|disabled|banned)", re.I | re.S)


def in_rete():
    """Senza internet l'estensione di Chrome si scollega (Riccardo, 13 nov): inutile lanciare l'agente."""
    try:
        socket.create_connection(("claude.ai", 443), 5).close()
        return True
    except OSError:
        return False


def chiedi(nome, valori, strumenti, giri):
    """Lancia `claude -p` col prompt compilato e restituisce il JSON della risposta (dict)."""
    if strumenti is CHROME and not in_rete():
        return {"errore": "chrome non disponibile", "dettaglio": "il Mac è senza internet"}
    prompt = (QUI / f"prompt/{nome}.md").read_text()
    for k, v in valori.items():
        prompt = prompt.replace("{{" + k + "}}", str(v))
    for prova in range(3):
        r = subprocess.run([Path.home() / ".local/bin/claude", "-p", prompt, "--model", "claude-sonnet-5-5", "--max-turns", str(giri),
                            *(["--chrome"] if strumenti is CHROME else []), "--allowedTools", *strumenti],  # senza --chrome gli strumenti del browser non esistono
                           capture_output=True, text=True, timeout=1500, env={**os.environ, "OBSIDIAN_SYNC_CHILD": "1", "TMPDIR": os.environ.get("TMPDIR") or os.confstr(65537)}, cwd=QUI)
        try:
            out = estrai(r.stdout)
        except ValueError:
            raise RuntimeError(f"{nome}: risposta senza JSON (exit {r.returncode}): {(r.stdout or r.stderr)[-300:]}")
        if strumenti is not CHROME or out.get("errore") != "chrome non disponibile":
            return out
        # visto il 12 nov alle 6:26 e alle 12:29: l'estensione a tratti non risponde e un minuto dopo va; si riprova in una sessione nuova
        with open(QUI / "logs/pubblica.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {nome}: chrome non disponibile (prova {prova + 1}/3) — {json.dumps(out, ensure_ascii=False)[:400]} {r.stderr[-300:]}\n")
        time.sleep(45)
    return out


def estrai(testo):
    m = re.search(r"\{.*\}", testo, re.S)
    if not m:
        raise ValueError("nessun JSON")
    return json.loads(m.group(0))


def account(c, piattaforma):
    """Primo account non segnato come bloccato: l'ordine in config.json è principale, poi le riserve."""
    bloccati = kv(c, "bloccati") or []
    return next((a for a in CONFIG["account"].get(piattaforma, []) if a["nome"] not in bloccati), None)


def marchia(file, fil):
    """Riccardo, 14 nov: nelle campagne "ti adatti tu ogni volta in base alla richiesta specifica della campagna, senza compromettere lo stile".
    La filigrana richiesta va SOPRA la clip già montata (il montaggio non cambia): centrata, larga `larghezza` del quadro, centro a `y`
    (frazione dell'altezza). Mai sui bordi: le campagne scartano le filigrane nascoste ai lati o troppo piccole."""
    f, img = Path(file), QUI / fil["file"]
    out = f.with_name(f"{f.stem}_{img.parent.name}.mp4")
    if not out.exists():
        w, y = float(fil.get("larghezza", 0.45)), float(fil.get("y", 0.63))
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", f, "-i", img, "-filter_complex",
                        f"[1][0]scale2ref=w=main_w*{w}:h=ow/mdar[m][v];[v][m]overlay=x=(main_w-overlay_w)/2:y=main_h*{y}-overlay_h/2",
                        "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out],
                       check=True, timeout=1200)
    return out


def leggero(file, tetto=9.4e6):
    """Il file da caricare: `file_upload` di Chrome passa al massimo 10 MB, sopra si fa una copia HEVC a due passate che ci sta.
    shortcut: sotto 1800 kb/s (clip oltre ~40 s) la copia scende a 720p; per caricare l'originale serve un'altra strada (API ufficiali)."""
    f = Path(file)
    if f.stat().st_size <= tetto:
        return f
    durata = float(subprocess.run(["ffprobe", "-v", "0", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True, check=True).stdout)
    kb = int(tetto * 8 / durata / 1000) - 128  # 128 kb/s vanno all'audio
    copia, stat = f.with_name(f.stem + "_web.mp4"), str(f.with_suffix(".x265"))
    video = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", f, *(["-vf", "scale=720:-2"] if kb < 1800 else []), "-c:v", "libx265", "-preset", "medium", "-b:v", f"{kb}k", "-tag:v", "hvc1"]
    subprocess.run([*video, "-x265-params", f"pass=1:stats={stat}:log-level=error", "-an", "-f", "null", "/dev/null"], check=True, timeout=1200)
    subprocess.run([*video, "-x265-params", f"pass=2:stats={stat}:log-level=error", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", copia], check=True, timeout=1200)
    for x in f.parent.glob(f.stem + ".x265*"):
        x.unlink()
    assert copia.stat().st_size < 10e6, f"copia ancora troppo grande: {copia.stat().st_size}"
    return copia


def muta(r, dest):
    """La risposta non parla di nessuna delle piattaforme chieste (Chrome non raggiungibile, agente che si arrende)."""
    return not any(isinstance(r.get(p), dict) for p in dest)


VERIFICA = re.compile(r"confirm you.re human|captcha|verify (that )?you|are you a robot|conferma di essere|verifica di sicurezza", re.I)
LIMITE = re.compile(r"daily upload limit|wait 24 hours|limite (giornaliero|di caricament)", re.I)  # il tetto giornaliero della piattaforma: non è un errore della clip


def interesse(k):
    """Quanto può interessare una clip: la somma dei tre voti del giudice (capibile/divertente/finale) scritta in `perche`."""
    m = re.search(r"voti (\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", k["perche"] or "")  # k: riga del database o dict
    return sum(map(float, m.groups())) if m else 0


def prossima(clips, uscite, attive, tentativi, oggi, viste, tetto=3, soglia=10**9):
    """Clip e piattaforma da pubblicare adesso. Riccardo, 13 nov: "3 video al giorno a social (in tutto 9) tutti diversi. poi i video
    che vediamo che esplodono su un social li possiamo pubblicare anche sugli altri". Una piattaforma alla volta, la più indietro oggi;
    prima una clip esplosa altrove (>= soglia visualizzazioni, conta nei 3), poi una clip mai uscita. Al massimo 3 tentativi per clip e piattaforma."""
    libere = sorted((q for q in attive if oggi.get(q, 0) < tetto), key=lambda q: oggi.get(q, 0))
    for q in libere:
        prova = lambda k: (k["id"], q) not in uscite and tentativi.get(f"{k['id']}:{q}", 0) < 3
        esplose = sorted((k for k in clips if k["stato"] == "pubblicata" and viste.get(k["id"], 0) >= soglia and prova(k)), key=lambda k: -viste[k["id"]])
        # Riccardo, 14 nov: "massimo 3 video al giorno in ordine di quale video può poter generare più interesse"
        nuove = sorted((k for k in clips if k["stato"] == "montata" and not any(u[0] == k["id"] for u in uscite) and prova(k)), key=lambda k: -interesse(k))
        if esplose or nuove:
            return (esplose or nuove)[0], [q]
    return None, []


def campagna(k):
    """Prima campagna attiva (config.json, "campagne_attive") che accetta questa clip: stesso streamer e, se la campagna le chiede, le parole nel titolo."""
    for camp in CONFIG.get("campagne_attive", []):
        if k["streamer"] in camp.get("streamer", []) and all(p.lower() in (k["titolo"] or "").lower() for p in camp.get("parole", [])):
            return camp
    return None


def regole(camp):
    """Istruzioni in più per l'agente che pubblica: vuote se la clip non va in nessuna campagna."""
    if not camp:
        return ""
    r = [f"## Campagna: {camp['nome']}", "Questa clip partecipa a una campagna di clipping pagata. Oltre ai passi sopra:"]
    if camp.get("promozione"):
        r += ["- TikTok: in \"Show more\" attiva \"Disclose post content\" e spunta \"Branded content\".",
              "- Instagram e YouTube: la didascalia deve contenere #ad (aggiungilo se manca)."]
    r += [f"- {x}" for x in camp.get("regole", [])]
    return "\n".join(r)


INVIO_ATTESA, INVIO_SCADENZA = 6 * 60, 29 * 60  # le campagne accettano i link entro 30 min; i post nuovi compaiono sul sito dopo qualche minuto


def pronte(coda, ora):
    return [x for x in coda if INVIO_ATTESA <= ora - x["quando"] < INVIO_SCADENZA and ora - x["provato"] >= 5 * 60]


def da_inviare(c, ora):
    return pronte(kv(c, "da_inviare") or [], ora)


def invia(c):
    """Manda alla campagna i link delle clip appena pubblicate. Si riprova ogni 5 minuti finché la finestra di 30 minuti è aperta."""
    ora = time.time()
    coda = kv(c, "da_inviare") or []
    for x in pronte(coda, ora):
        camp = next((k for k in CONFIG.get("campagne_attive", []) if k["nome"] == x["campagna"]), None)
        link = {r["piattaforma"]: r["url"] for r in c.execute("select piattaforma, url from pubblicazione where clip=?", (x["clip"],)) if r["piattaforma"] in x["piattaforme"]}
        if camp and link:
            x["provato"] = ora
            try:
                r = chiedi("invia", {"CAMPAGNA": camp["nome"], "LINK_CAMPAGNA": camp["link_invio"], "TITOLO": x["titolo"],
                                     "LINK": "\n".join(f"- {q}: {u}" for q, u in link.items())}, CHROME, 60)
            except RuntimeError:
                r = {}  # si riprova tra 5 minuti
            fatte = [q for q in r.get("inviate") or [] if q in x["piattaforme"]]
            x["piattaforme"] = [q for q in x["piattaforme"] if q not in fatte]
            if fatte:
                evento(c, "campagna", f"{camp['nome']}: inviata «{x['titolo']}» ({', '.join(fatte)})")
        if not camp or not link or not x["piattaforme"]:
            coda.remove(x)
    for x in [x for x in coda if ora - x["quando"] >= INVIO_SCADENZA]:  # finestra chiusa: si avvisa una volta e si toglie
        evento(c, "campagna", f"{x['campagna']}: «{x['titolo']}» non inviata in tempo su {', '.join(x['piattaforme'])}", email=True)
        coda.remove(x)
    kv(c, "da_inviare", coda)


def pubblica(c):
    ora = time.time()
    pausa = {q: fino for q, fino in (kv(c, "pausa") or {}).items() if fino > ora}
    attive = {q: a for q in PIATTAFORME if (a := account(c, q)) and q not in (kv(c, "in_attesa") or {}) and q not in pausa}
    clips = c.execute("select clip.*, live.streamer from clip join live on live.id = clip.live where clip.stato in ('montata', 'pubblicata') order by creato").fetchall()
    uscite = {(r["clip"], r["piattaforma"]) for r in c.execute("select clip, piattaforma from pubblicazione")}
    tentativi = kv(c, "tentativi") or {}
    mezzanotte = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
    oggi = dict(c.execute("select piattaforma, count(*) from pubblicazione where quando >= ? group by piattaforma", (mezzanotte,)).fetchall())
    viste = dict(c.execute("select clip, max(visualizzazioni) from pubblicazione group by clip").fetchall())
    k, dove = prossima(clips, uscite, attive, tentativi, oggi, viste, CONFIG.get("clip_al_giorno_per_social", 3), CONFIG.get("esplosa_viste", 10**9))
    if not k:
        return
    dest = {q: attive[q] for q in dove}
    rinuncia = lambda: kv(c, "tentativi", {**tentativi, **{f"{k['id']}:{q}": 3 for q in dest}})
    originale = Path(k["file"]).expanduser()
    if not originale.exists():  # clip vecchia, file già cancellato: non si può più recuperare
        return rinuncia()
    if fermo := monta.avvio_fermo(originale):  # Riccardo: "rendere impossibile che le clip ferme passino"
        if k["stato"] == "montata":
            c.execute("update clip set stato='scartata', perche=? where id=?", (f"BOCCIATA PRIMA DELLA PUBBLICAZIONE: inizio fermo ({fermo}). " + (k["perche"] or ""), k["id"]))
            evento(c, "clip bocciata", f"{k['streamer']}: {k['titolo']} — inizio fermo ({fermo}), fermata prima della pubblicazione")
        return rinuncia()  # una clip già uscita altrove con l'inizio fermo non si porta sulle altre piattaforme
    # distanza dalla prossima estratta a caso ogni volta (richiesta di Riccardo): un intervallo fisso si riconosce subito come automatico
    kv(c, "prossima_pubblica", time.time() + random.uniform(*CONFIG["pubblica_ogni_minuti"]) * 60)
    camp = campagna(k)
    file = leggero(marchia(k["file"], camp["filigrana"]) if camp and camp.get("filigrana") else k["file"])
    didascalia = " ".join([k["didascalia"] or "", *[h for h in camp.get("hashtag", []) if h.lower() not in (k["didascalia"] or "").lower()]]).strip() if camp else k["didascalia"]
    domanda = lambda d: chiedi("pubblica", {"FILE": file, "TITOLO": k["titolo"], "DIDASCALIA": didascalia, "VISIBILITA": CONFIG.get("visibilita_youtube", "Pubblico"), "CAMPAGNA": regole(camp),
                                            "DESTINAZIONI": "\n".join(f"- {q}: account {a['nome']}" + (f", profilo Chrome \"{a['profilo']}\"" if a.get("profilo") else "") for q, a in d.items())},
                               CHROME, 120)
    r = domanda(dest)
    if muta(r, dest):
        # visto la notte dell'11 nov: 4 clip segnate "non pubblicata" e perse perché l'agente non aveva risposto per nessuna piattaforma.
        # La clip resta in coda e si riprova al prossimo giro; un solo avviso ogni 6 ore per non riempire la posta.
        testo = f"pubblicazione rimandata, la clip resta in coda. Risposta dell'agente: {json.dumps(r, ensure_ascii=False)[:300]}"
        if not c.execute("select 1 from evento where tipo='account' and testo=? and quando>?", (testo, time.time() - 6 * 3600)).fetchone():
            evento(c, "account", testo, email=True)
        if r.get("errore") == "chrome non disponibile":  # Chrome o internet tornano da soli: si riprova tra 10 minuti, non tra 45-120
            kv(c, "prossima_pubblica", time.time() + 600)
        return
    # Chrome a volte rifiuta un sito in una sessione e lo accetta nella successiva (visto con TikTok): si riprova una volta in una sessione nuova
    if rifiutate := {q: a for q, a in dest.items() if RIFIUTO.search(str((r.get(q) or {}).get("errore", "")) if isinstance(r.get(q), dict) else "")}:
        try:
            r.update(domanda(rifiutate))
        except RuntimeError:
            pass
    for q, a in dest.items():
        e = r.get(q) if isinstance(r.get(q), dict) else {"errore": "nessuna risposta per questa piattaforma"}
        if str(e.get("url", "")).startswith("https://"):
            c.execute("insert or replace into pubblicazione (clip, piattaforma, account, url, quando, visualizzazioni, aggiornato) values (?,?,?,?,?,0,?)",
                      (k["id"], q, a["nome"], e["url"], time.time(), time.time()))
            uscite.add((k["id"], q))
        elif e.get("serve_login"):
            # quella coda resta ferma finché i conti non vedono di nuovo l'accesso fatto
            kv(c, "in_attesa", {**(kv(c, "in_attesa") or {}), q: "login"})
            evento(c, "account", f"serve il login: {q} ({a['nome']}). Rifai l'accesso in Chrome; la coda di {q} riparte da sola.", email=True)
        else:
            testo = str(e.get("errore", "errore senza testo"))[:300]
            if VERIFICA.search(testo):
                # verifica anti-robot: la fa Riccardo; nel frattempo quella piattaforma si ferma (insistere peggiora il sospetto) e la clip non perde tentativi
                kv(c, "pausa", {**pausa, q: time.time() + 24 * 3600})
                evento(c, "account", f"{q}: la piattaforma chiede di confermare che sei umano («{testo[:120]}»). Fallo tu in Chrome; {q} è in pausa finché non mi dici che è fatto.", email=True)
                continue
            if LIMITE.search(testo):
                # tetto giornaliero (YouTube: 10 Shorts sul canale nuovo): quella piattaforma riposa 6 ore, le clip saltate si recuperano dopo
                kv(c, "pausa", {**pausa, q: time.time() + 6 * 3600})
                if not c.execute("select 1 from evento where tipo='account' and testo like ? and quando>?", (f"{q}: limite giornaliero%", time.time() - 6 * 3600)).fetchone():
                    evento(c, "account", f"{q}: limite giornaliero raggiunto («{testo[:120]}»). Riprovo tra 6 ore e recupero le clip saltate.", email=True)
                continue
            volte = tentativi[f"{k['id']}:{q}"] = tentativi.get(f"{k['id']}:{q}", 0) + 1
            if BLOCCO.search(testo):
                kv(c, "bloccati", (kv(c, "bloccati") or []) + [a["nome"]])
                riserva = account(c, q)
                # le altre clip dello stesso streamer escono dalla coda: sono il sospetto più probabile
                c.execute("update clip set stato='sospesa' where stato='montata' and live in (select id from live where streamer=?)", (k["streamer"],))
                evento(c, "account", f"{q}: account {a['nome']} bloccato («{testo}»). " + (f"Passo alla riserva {riserva['nome']}." if riserva else "Nessuna riserva configurata.")
                       + f" Sospese le clip di {k['streamer']} in coda.", email=True)
            else:
                evento(c, "account", f"{q}: pubblicazione non riuscita per «{k['titolo']}» (tentativo {volte} di 3): {testo}", email=True)
    kv(c, "tentativi", tentativi)
    if camp and (nuove := [q for q in dest if (k["id"], q) in uscite]):
        # Riccardo, 11 nov: "in futuro devi farlo in automatico non aspettare il mio sì" → l'invio dei link alla campagna lo fa il lavoro "invia"
        kv(c, "da_inviare", (kv(c, "da_inviare") or []) + [{"clip": k["id"], "titolo": k["titolo"], "campagna": camp["nome"], "piattaforme": nuove, "quando": time.time(), "provato": 0}])
    if any(u[0] == k["id"] for u in uscite):
        c.execute("update clip set stato='pubblicata' where id=?", (k["id"],))
    elif all(tentativi.get(f"{k['id']}:{q}", 0) >= 3 for q in dest):  # tre tentativi falliti su tutte: esce dalla coda
        c.execute("update clip set stato='non pubblicata' where id=?", (k["id"],))


def conti(c):
    righe = c.execute("select clip, piattaforma, url from pubblicazione order by quando desc limit 60").fetchall()
    attive = [p for p in PIATTAFORME if CONFIG["account"].get(p)]
    if not attive:
        return
    r = chiedi("conti", {"PIATTAFORME": ", ".join(attive), "CLIP": "\n".join(f"- clip {x['clip']} · {x['piattaforma']} · {x['url']}" for x in righe) or "(nessuna clip pubblicata)"}, CHROME, 150)
    attesa = kv(c, "in_attesa") or {}
    for p, s in (r.get("sessioni") or {}).items():
        if p in PIATTAFORME and s == "login" and p not in attesa:
            attesa[p] = "login"
            evento(c, "account", f"serve il login: {p}. Rifai l'accesso in Chrome; la coda riparte da sola.", email=True)
        elif s == "ok":
            attesa.pop(p, None)
    kv(c, "in_attesa", attesa)
    for v in r.get("visualizzazioni") or []:
        if isinstance(v.get("n"), (int, float)) and v["n"] >= 0:
            c.execute("update pubblicazione set visualizzazioni=?, aggiornato=? where clip=? and piattaforma=?", (int(v["n"]), time.time(), v.get("clip"), v.get("piattaforma")))
    for e in r.get("entrate") or []:
        if isinstance(e.get("importo"), (int, float)):
            # una riga per fonte e giorno: i conti di oggi sostituiscono quelli di stamattina
            c.execute("delete from entrata where data=? and fonte=?", (time.strftime("%Y-%m-%d"), str(e.get("fonte"))))
            c.execute("insert into entrata (data, fonte, importo, stato) values (?,?,?,?)", (time.strftime("%Y-%m-%d"), str(e.get("fonte")), float(e["importo"]), f"{e.get('stato', '')} {e.get('valuta', '')}".strip()))
    for a in r.get("avvisi") or []:
        if not c.execute("select 1 from evento where tipo='account' and testo=?", (f"{a.get('piattaforma')}: {a.get('testo')}",)).fetchone():
            evento(c, "account", f"{a.get('piattaforma')}: {a.get('testo')}", email=True)


def attivabile(k, noti):
    """Voce per "campagne_attive" se lo scout ha trovato una campagna usabile da sola: streamer seguito, sito dove abbiamo l'account, clip di qualsiasi live."""
    if not (isinstance(k.get("streamer"), str) and k["streamer"].lower() in noti and k.get("sito") in ("contentrewards", "clipping")
            and not k.get("solo_filmato") and str(k.get("link", "")).startswith("https://")):
        return None
    nome = next(s["nome"] for s in CONFIG["streamer"] if s["nome"].lower() == k["streamer"].lower())
    fil = {}
    if str(k.get("filigrana", "")).startswith("https://"):  # watermark obbligatorio della campagna: si scarica e si mette sopra ogni clip
        cartella = QUI / "campagne" / re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
        cartella.mkdir(parents=True, exist_ok=True)
        grezza = cartella / "filigrana_scaricata"
        subprocess.run(["curl", "-sL", "-m", "60", "-o", grezza, k["filigrana"]], check=True)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", grezza, cartella / "filigrana.png"], check=True)
        fil = {"filigrana": {"file": str((cartella / "filigrana.png").relative_to(QUI)), "larghezza": 0.45, "y": 0.63}}
    return {**fil, "nome": str(k.get("nome") or nome)[:80], "streamer": [nome], "link_invio": k["link"], "hashtag": [h for h in k.get("hashtag") or [] if isinstance(h, str) and h.startswith("#")][:5],
            "promozione": bool(k.get("promozione")), "regole": [str(x)[:200] for x in k.get("regole") or []][:5]}


def scout(c):
    adesso = time.strftime("%Y-%m-%d %H.%M")
    file = VAULT / "Newsletter live" / f"{adesso}.md"
    file.parent.mkdir(parents=True, exist_ok=True)
    r = chiedi("scout", {"ADESSO": adesso, "OGGI": adesso[:10], "FILE": file, "SOGLIA": CONFIG["campagne"]["soglia_per_1000"], "TETTO": CONFIG["campagne"]["tetto_minimo_clip"],
                         "SEGUITI": ", ".join(s["nome"] for s in CONFIG["streamer"])},
               ["WebSearch", "WebFetch", "mcp__firecrawl__firecrawl_search", "mcp__firecrawl__firecrawl_scrape", f"Edit(/{file.parent}/**)"], 60)
    noti = {s["nome"].lower() for s in CONFIG["streamer"]}
    nuovi = [{k: s[k] for k in ("nome", "twitch", "youtube", "kick", "media") if s.get(k)} for s in r.get("nuovi_streamer") or []
             if isinstance(s.get("nome"), str) and s["nome"].lower() not in noti and any(s.get(p) for p in ("twitch", "youtube", "kick"))]
    if nuovi:  # entrano subito tra i seguiti: per toglierne uno, "stato: escluso" nella sua scheda
        cfg = json.loads((QUI / "config.json").read_text())
        cfg["streamer"] += nuovi
        (QUI / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    buone = [k for k in r.get("campagne") or [] if isinstance(k.get("per_1000"), (int, float)) and k["per_1000"] >= CONFIG["campagne"]["soglia_per_1000"]
             and (k.get("tetto_clip") or 0) >= CONFIG["campagne"]["tetto_minimo_clip"] and not k.get("scommesse")]
    viste = kv(c, "campagne_viste") or []
    for k in buone:
        if k.get("link") not in viste:
            viste.append(k.get("link"))
            if voce := attivabile(k, noti):  # Riccardo, 11 nov: "rendiamo tutto automatico"
                cfg = json.loads((QUI / "config.json").read_text())
                cfg["campagne_attive"] = cfg.get("campagne_attive", []) + [voce]
                (QUI / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
                evento(c, "campagna", f"attivata {voce['nome']} ({k['streamer']}): {k['per_1000']} $ per 1000, tetto {k.get('tetto_clip')} $ a clip — {k['link']}. Le clip di {k['streamer']} la useranno da sole.", email=True)
            else:
                evento(c, "campagna da valutare", f"{k.get('nome')} ({k.get('streamer', '?')}): {k['per_1000']} $ per 1000, tetto {k.get('tetto_clip')} $ a clip — {k.get('link')}. Non la attivo da solo (solo un filmato preciso, sito senza nostro account o streamer non seguito).", email=True)
    kv(c, "campagne_viste", viste)
    evento(c, "newsletter", f"[[{adesso}]] — {str(r.get('in_breve', ''))[:200]}" + (f" · nuovi seguiti: {', '.join(s['nome'] for s in nuovi)}" if nuovi else ""),
           email=time.localtime().tm_hour >= 20 and (kv(c, "sera") != adesso[:10]))
    if time.localtime().tm_hour >= 20:
        kv(c, "sera", adesso[:10])


LAVORI = {"invia": invia, "pubblica": pubblica, "conti": conti, "scout": scout}


def in_scadenza(c, ora):
    """Nei giorni del lancio (dal 17 novembre) conti e scout girano ogni ora."""
    lancio = time.strftime("%Y-%m-%d", time.localtime(ora)) >= "2026-11-17"
    ogni = {"conti": 3600 if lancio else 6 * 3600, "scout": 3600 if lancio else 8 * 3600}
    # la prossima pubblicazione ha un'ora sua, estratta a caso dopo ogni caricamento (vedi pubblica): mai a intervalli regolari
    return (["invia"] if da_inviare(c, ora) or any(ora - x["quando"] >= INVIO_SCADENZA for x in kv(c, "da_inviare") or []) else []) + (["pubblica"] if CONFIG["pubblicazione_automatica"] and ora >= (kv(c, "prossima_pubblica") or 0) else []) + [n for n, s in ogni.items() if ora - (kv(c, "ultimo_" + n) or 0) >= s]


if __name__ == "__main__":
    assert BLOCCO.search("Il tuo account è stato sospeso") and BLOCCO.search("This account has been terminated") and not BLOCCO.search("dominio bloccato") and not BLOCCO.search("upload fallito")
    assert muta({"errore": "chrome non disponibile"}, {"youtube": 1}) and not muta({"youtube": {"url": "u"}}, {"youtube": 1, "tiktok": 1})
    _c = [{"id": 1, "stato": "pubblicata", "perche": ""}, {"id": 2, "stato": "montata", "perche": ""}, {"id": 3, "stato": "montata", "perche": ""}]
    _y = ["youtube", "instagram", "tiktok"]
    _v = [{"id": 7, "stato": "montata", "perche": "x (voti 5/5/5)"}, {"id": 8, "stato": "montata", "perche": "y (voti 8/7/9) z"}, {"id": 9, "stato": "montata", "perche": ""}]
    assert interesse(_v[1]) == 24 and interesse(_v[2]) == 0 and prossima(_v, set(), _y, {}, {}, {}, 3, 5000) == (_v[1], ["youtube"])  # prima la più interessante
    assert prossima(_c, {(1, "youtube")}, _y, {}, {}, {1: 50}, 3, 5000) == (_c[1], ["youtube"])  # clip nuova, una piattaforma sola
    assert prossima(_c, {(1, "youtube")}, _y, {}, {"youtube": 1}, {1: 50}, 3, 5000) == (_c[1], ["instagram"])  # la più indietro oggi
    assert prossima(_c, {(1, "youtube"), (2, "instagram")}, _y, {}, {"youtube": 1, "instagram": 1}, {1: 50}, 3, 5000) == (_c[2], ["tiktok"])  # tutte diverse
    assert prossima(_c, {(1, "youtube")}, _y, {}, {"youtube": 1}, {1: 9000}, 3, 5000) == (_c[0], ["instagram"])  # esplosa: va anche sugli altri
    assert prossima(_c, set(), _y, {}, {"youtube": 3, "instagram": 3, "tiktok": 3}, {}, 3, 5000) == (None, [])  # 3 al giorno per social
    assert prossima(_c[:1], {(1, "youtube")}, _y, {}, {}, {1: 50}, 3, 5000) == (None, [])  # non esplosa: resta dov'è
    assert prossima(_c, set(), _y, {"2:youtube": 3}, {}, {}, 3, 5000) == (_c[2], ["youtube"])
    assert VERIFICA.search("Confirm you're human to use your account, iamclipfarmer67") and not VERIFICA.search("Post couldn't be shared")
    assert RIFIUTO.search("dominio bloccato") and RIFIUTO.search("Permission denied for this action on this domain") and not RIFIUTO.search("account sospeso")
    assert 0 < CONFIG["pubblica_ogni_minuti"][0] < CONFIG["pubblica_ogni_minuti"][1]
    assert estrai('ecco:\n```json\n{"youtube": {"url": "https://x"}}\n```') == {"youtube": {"url": "https://x"}}
    _k = {"streamer": "Kai Cenat", "titolo": "Kai Cenat GTA 6 chaos"}
    _camp = {"nome": "Kai", "streamer": ["Kai Cenat"], "hashtag": ["#KaiCenat"], "promozione": True, "regole": ["mostra Kai"], "link_invio": "https://x"}
    CONFIG["campagne_attive"], _salva = [_camp], CONFIG.get("campagne_attive", [])
    assert campagna(_k) is _camp and campagna({**_k, "streamer": "xQc"}) is None and campagna(_k | {"titolo": "x"}) is _camp
    assert campagna(_k) and not campagna({**_k}) is None and "Branded content" in regole(_camp) and regole(None) == ""
    CONFIG["campagne_attive"] = [{**_camp, "parole": ["gta"]}]
    assert campagna(_k) and campagna({**_k, "titolo": "Kai eats"}) is None
    CONFIG["campagne_attive"] = _salva
    _q = [{"quando": 0, "provato": 0}, {"quando": 500, "provato": 0}, {"quando": 0, "provato": 1700}]
    assert pronte(_q, 600) == [_q[0]] and pronte(_q, 1800) == [_q[1]] and pronte(_q, 2300) == [] and pronte(_q, 1000) == _q[:2]
    _noti = {"kai cenat"}
    assert attivabile({"streamer": "kai cenat", "sito": "contentrewards", "link": "https://c", "hashtag": ["#kai", "x"]}, _noti)["hashtag"] == ["#kai"]
    assert attivabile({"streamer": "Kai Cenat", "sito": "contentrewards", "link": "https://c", "solo_filmato": True}, _noti) is None and attivabile({"streamer": "Speed", "sito": "clipping", "link": "https://c"}, _noti) is None
    if "--prova" not in sys.argv:
        with uno_alla_volta("agenti", scade=2400):
            c = db()
            for n in ([sys.argv[1]] if len(sys.argv) > 1 else in_scadenza(c, time.time())):
                try:
                    kv(c, "ultimo_" + n, time.time())
                    c.commit()
                    LAVORI[n](c)
                except Exception as e:  # un agente andato male non ferma gli altri
                    evento(c, "errore", f"agente {n}: {type(e).__name__}: {str(e)[-300:]}")
                c.commit()
            genera()
