"""Genera le note di Obsidian dal database (senso unico: database -> note).

uso: python3 -I obsidian.py
Unica eccezione al senso unico: `priorita` e `stato` nelle schede Streamer li cambia Riccardo e restano com'erano
(stato: escluso = la sentinella non lo registra). Sotto "## Note personali" si scrive a mano e non viene toccato.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con -I la cartella dello script non è nel percorso
from stato import CONFIG, db  # noqa: E402

VAULT = Path.home() / "Desktop/Obsidian Vault/10 Progetti/Clip Farm"
PERSONALI = "## Note personali"
PIATTAFORME = ("youtube", "instagram", "tiktok")


def nome(testo):
    """Nome file leggibile: senza i caratteri che Obsidian non vuole."""
    return re.sub(r"\s+", " ", re.sub(r'[#^\[\]|:/\\?*"<>]', "", testo)).strip()[:90]


def giorno(t):
    return time.strftime("%Y-%m-%d", time.localtime(t))


def ora(t):
    return time.strftime("%d/%m %H:%M", time.localtime(t)) if t else ""


def campo(testo, chiave):
    m = re.search(rf'^{chiave}: "?([^"\n]*)"?$', testo, re.M)
    return m.group(1) if m else None


def scrivi(rel, front, corpo):
    """Scrive solo se cambia qualcosa, e conserva le note personali."""
    f = VAULT / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    vecchia = f.read_text() if f.exists() else ""
    coda = vecchia[vecchia.index(PERSONALI):] if PERSONALI in vecchia else PERSONALI + "\n"
    testa = "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in front.items()) + "---\n"
    nuova = testa + corpo.rstrip() + "\n\n" + coda
    if nuova != vecchia:
        f.write_text(nuova)


def tabella(intestazioni, righe):
    if not righe:
        return "_Ancora niente._\n"
    return "| " + " | ".join(intestazioni) + " |\n|" + "---|" * len(intestazioni) + "\n" + "".join("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |\n" for r in righe)


def genera():
    c = db()
    oggi = giorno(time.time())
    lives = c.execute("select * from live order by inizio desc").fetchall()
    clips = c.execute("select clip.*, live.streamer from clip join live on live.id = clip.live order by creato desc").fetchall()
    pubb = {}
    for p in c.execute("select * from pubblicazione"):
        pubb.setdefault(p["clip"], {})[p["piattaforma"]] = p
    nota_live = {l["id"]: nome(f"{giorno(l['inizio'])} {l['streamer']} {l['id']}") for l in lives}
    nota_clip = {k["id"]: nome(f"{giorno(k['creato'])} {k['titolo']} {k['id']}") for k in clips}
    viste = lambda k: sum((p["visualizzazioni"] or 0) for p in pubb.get(k, {}).values())

    for s in CONFIG["streamer"]:
        f = VAULT / "Streamer" / f"{nome(s['nome'])}.md"
        vecchia = f.read_text() if f.exists() else ""
        sue = [l for l in lives if l["streamer"] == s["nome"]]
        sue_clip = [k for k in clips if k["streamer"] == s["nome"]]
        scrivi(f"Streamer/{nome(s['nome'])}.md", {
            "tipo": "streamer", "creato": campo(vecchia, "creato") or oggi,
            "piattaforme": [p for p in ("twitch", "youtube", "kick") if s.get(p)],
            "spettatori_medi": s.get("media", 0), "picco": max([l["picco"] or 0 for l in sue], default=0),
            "campagna": s.get("campagna_nome", ""), "paga_per_1000": s.get("paga_per_1000", 0),
            "clip": len(sue_clip), "visualizzazioni": sum(viste(k["id"]) for k in sue_clip),
            "priorita": campo(vecchia, "priorita") or "normale", "stato": campo(vecchia, "stato") or "seguito",
        }, f"# {s['nome']}\n\nSu: [[Clip Farm]]\n\n> `stato: escluso` = la sentinella non lo registra. `priorita` è un tuo appunto.\n\n"
           + "Canali: " + " · ".join(f"{p}: `{s[p]}`" for p in ("twitch", "youtube", "kick") if s.get(p)) + "\n\n## Live\n"
           + "".join(f"- [[{nota_live[l['id']]}]]\n" for l in sue[:20]))

    for l in lives:
        sue = [k for k in clips if k["live"] == l["id"]]
        scrivi(f"Live/{nota_live[l['id']]}.md", {
            "tipo": "live", "creato": giorno(l["inizio"]), "streamer": l["streamer"], "piattaforma": l["piattaforma"], "gioco": l["gioco"] or "",
            "inizio": ora(l["inizio"]), "fine": ora(l["fine"]), "picco": l["picco"] or 0, "gta6": bool(l["gta6"]),
            "registrata": bool(c.execute("select 1 from blocco where live=?", (l["id"],)).fetchone()) or bool(l["registrata"]),
            "clip_prodotte": len(sue), "clip_pubblicate": sum(1 for k in sue if pubb.get(k["id"])),
        }, f"# {l['streamer']} — {ora(l['inizio'])}\n\nSu: [[Clip Farm]] · Streamer: [[{nome(l['streamer'])}]]\n\n{l['titolo']}\n\n[Apri il canale]({l['url']})\n\n## Clip\n"
           + "".join(f"- [[{nota_clip[k['id']]}]]\n" for k in sue))

    for k in clips:
        p = pubb.get(k["id"], {})
        scrivi(f"Clip/{nota_clip[k['id']]}.md", {
            "tipo": "clip", "creato": giorno(k["creato"]), "streamer": k["streamer"], "stato": k["stato"], "durata_s": round(k["fine"] - k["inizio"]),
            **{f"visualizzazioni_{x}": (p[x]["visualizzazioni"] or 0) if x in p else 0 for x in PIATTAFORME},
            "visualizzazioni": viste(k["id"]),
        }, f"# {k['titolo']}\n\nSu: [[Clip Farm]] · Live: [[{nota_live[k['live']]}]] · Streamer: [[{nome(k['streamer'])}]]\n\n"
           f"**Perché:** {k['perche']}\n\n**Didascalia:** {k['didascalia']}\n\n**Momento della live:** da {int(k['inizio'] // 60)}:{int(k['inizio'] % 60):02d} a {int(k['fine'] // 60)}:{int(k['fine'] % 60):02d}\n\n"
           f"**File:** [{Path(k['file']).name}](file://{k['file'].replace(' ', '%20')})\n\n## Pubblicazioni\n"
           + tabella(["Piattaforma", "Account", "Link", "Visualizzazioni", "Aggiornato"], [(x, p[x]["account"] or "", p[x]["url"] or "", p[x]["visualizzazioni"] or 0, ora(p[x]["aggiornato"])) for x in PIATTAFORME if x in p]))

    for x in PIATTAFORME:
        sue = [p[x] for p in pubb.values() if x in p]
        avvisi = c.execute("select * from evento where tipo='account' and testo like ? order by quando desc limit 10", (f"%{x}%",)).fetchall()
        scrivi(f"Account/{x.capitalize()}.md", {"tipo": "account", "creato": oggi, "piattaforma": x, "account": CONFIG["account"].get(x, []),
                                                 "clip_pubblicate": len(sue), "visualizzazioni": sum(p["visualizzazioni"] or 0 for p in sue)},
               f"# Account {x.capitalize()}\n\nSu: [[Clip Farm]]\n\nPrincipale e riserve in `~/Projects/clip-farm/config.json` (`account.{x}`), nell'ordine in cui si usano.\n\n## Avvisi\n"
               + ("".join(f"- {ora(e['quando'])} — {e['testo']}\n" for e in avvisi) or "_Nessun avviso._\n"))

    entrate = c.execute("select * from entrata order by data desc").fetchall()
    scrivi("Entrate.md", {"tipo": "registro", "creato": oggi, "totale": round(sum(e["importo"] for e in entrate), 2)},
           "# Entrate\n\nSu: [[Clip Farm]]\n\n" + tabella(["Data", "Fonte", "Importo", "Stato"], [(e["data"], e["fonte"], f"{e['importo']:.2f}", e["stato"]) for e in entrate]))

    for cartella, colonne in {"Streamer": ["file.name", "stato", "priorita", "piattaforme", "spettatori_medi", "picco", "clip", "visualizzazioni", "campagna", "paga_per_1000"],
                              "Live": ["file.name", "streamer", "piattaforma", "gioco", "inizio", "fine", "picco", "gta6", "clip_prodotte", "clip_pubblicate"],
                              "Clip": ["file.name", "streamer", "stato", "visualizzazioni", "visualizzazioni_youtube", "visualizzazioni_instagram", "visualizzazioni_tiktok", "creato"]}.items():
        base = VAULT / f"{cartella}.base"
        testo = f'filters:\n  and:\n    - file.inFolder("10 Progetti/Clip Farm/{cartella}")\nviews:\n  - type: table\n    name: Tutte\n    order:\n' + "".join(f"      - {x}\n" for x in colonne)
        if not base.exists() or base.read_text() != testo:
            base.write_text(testo)

    in_corso = [l for l in lives if l["fine"] is None]
    coda = [k for k in clips if k["stato"] == "montata"]
    eventi = c.execute("select * from evento order by quando desc limit 25").fetchall()
    lettere = sorted((VAULT / "Newsletter live").glob("*.md"), reverse=True)[:5] if (VAULT / "Newsletter live").exists() else []
    scrivi("Clip Farm.md", {"tipo": "progetto", "creato": campo((VAULT / "Clip Farm.md").read_text() if (VAULT / "Clip Farm.md").exists() else "", "creato") or oggi,
                            "stato": "attivo", "aggiornato": time.strftime("%Y-%m-%d %H:%M")},
           "# Clip Farm\n\nSu: [[Progetti]]\n\n> Generata da `~/Projects/clip-farm/obsidian.py` a ogni giro. Scrivi a mano solo sotto **Note personali**.\n\n"
           f"## Adesso\n- Lancio di GTA 6: {'**rilevato**' if c.execute('select 1 from kv where k=?', ('lancio',)).fetchone() else 'non ancora'}\n"
           f"- Clip in coda di pubblicazione: **{len(coda)}** · pubblicate: **{sum(1 for k in clips if pubb.get(k['id']))}** · montate in tutto: **{len(clips)}**\n"
           f"- Visualizzazioni totali: **{sum(viste(k['id']) for k in clips):,}** · Entrate: **{sum(e['importo'] for e in entrate):.2f}** → [[Entrate]]\n\n"
           "### Live in corso\n" + tabella(["Streamer", "Piattaforma", "Spettatori", "GTA 6", "Registrata", "Titolo"], [(f"[[{nome(l['streamer'])}]]", l["piattaforma"], f"{l['spettatori'] or 0:,}", "sì" if l["gta6"] else "", "● sì" if l["registrata"] else "no", (l["titolo"] or "")[:60]) for l in in_corso])
           + "\n### Ultime clip\n" + tabella(["Clip", "Streamer", "Stato", "Visualizzazioni"], [(f"[[{nota_clip[k['id']]}]]", k["streamer"], k["stato"], f"{viste(k['id']):,}") for k in clips[:15]])
           + "\n## Viste\n- Tabelle: [[Streamer.base]] · [[Live.base]] · [[Clip.base]]\n- Account: " + " · ".join(f"[[{x.capitalize()}]]" for x in PIATTAFORME)
           + "\n- Newsletter live: " + (" · ".join(f"[[{f.stem}]]" for f in lettere) or "_ancora nessuna_")
           + "\n\n## Ultimi fatti\n" + "".join(f"- {ora(e['quando'])} — **{e['tipo']}**: {e['testo']}\n" for e in eventi))


if __name__ == "__main__":
    assert nome("Kai: [WOW] #1 | a/b?") == "Kai WOW 1 ab" and campo('stato: "escluso"\npriorita: alta\n', "stato") == "escluso"
    if "--prova" not in sys.argv:
        genera()
