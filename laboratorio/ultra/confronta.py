"""Differenze misurate tra la clip di Speedy e la nostra (due misure.json di misura.py, stessa live di partenza).
Sono numeri, non voti: l'agente 2 li legge insieme ai fogli dei fotogrammi e dà il voto per sezione.
uso: python3 -I ultra/confronta.py SPEEDY/misure.json NOSTRA/misure.json  -> json su stdout
"""
import json
import sys


def intervalli(m):
    return [tuple(p["live"]) for p in m.get("pezzi_live") or []]


def sovrapp(a, b):
    """Secondi di live in comune / secondi di live usati da almeno una delle due (1 = stessi pezzi)."""
    tot = lambda xs: sum(z - y for y, z in unisci(xs))
    comune = sum(max(0, min(z1, z2) - max(y1, y2)) for y1, z1 in unisci(a) for y2, z2 in unisci(b))
    u = tot(a) + tot(b) - comune
    return round(comune / u, 2) if u > 0 else None


def unisci(xs):
    out = []
    for y, z in sorted(xs):
        if out and y <= out[-1][1]:
            out[-1][1] = max(out[-1][1], z)
        else:
            out.append([y, z])
    return out


def ordine_uguale(a, b):
    """I pezzi in comune compaiono nello stesso ordine? (Speedy a volte mette prima il finale come gancio)."""
    # a e b sono in ordine di clip: per ogni pezzo di a, la posizione in b del pezzo con la stessa live; deve crescere
    s = [j for (y, z) in a for j, (p, q) in enumerate(b) if min(z, q) > max(y, p)]
    return s == sorted(s)


COLORI = {"bianco": (240, 240, 240), "giallo": (242, 253, 6), "verde": (37, 251, 6), "lime": (152, 251, 5), "rosso": (247, 1, 5),
          "magenta": (249, 9, 244), "rosa": (240, 110, 170), "ciano": (102, 252, 249), "arancio": (247, 160, 40), "viola": (150, 60, 240),
          "azzurro": (60, 140, 250), "scuro": (40, 40, 40)}  # paletta misurata sugli Shorts (CONSEGNE.md) + i colori di base


def nome_colore(h):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return min(COLORI, key=lambda k: sum((x - y) ** 2 for x, y in zip(COLORI[k], (r, g, b))))


def riassunto(m):
    ev = m["scritte"]["eventi"]
    parole = [len(e["parole"]) for e in ev]
    d = m["durata"]
    return {
        "durata": d, "formato": m["formato"], "layout": m["layout"]["tipo"],
        "stacchi_ogni_10s": round(len(m["stacchi"]) / d * 10, 1),
        "durata_media_inquadratura": round(d / (len(m["stacchi"]) + 1), 2),
        "lampi": len(m["lampi"]), "lampi_colori": [l["tipo"] if l["tipo"] == "bianco" else l["colore_neri"] for l in m["lampi"]],
        "bianco_nero_secondi": round(sum(b - a for a, b in m.get("bianco_nero", [])), 1),
        "scritte": len(ev), "parole_per_scritta": round(sum(parole) / len(parole), 1) if parole else 0,
        "altezza_lettere_mediana": sorted(e["altezza_lettere"] for e in ev)[len(ev) // 2] if ev else None,
        "posizione_y_mediana": sorted(e["y"] for e in ev)[len(ev) // 2] if ev else None,
        "colori_usati": sorted({nome_colore(c) for e in ev for c in e["colori"][:1]}),
        "narrazioni_asterischi": sum("*" in e["testo"] for e in ev),
        "ritardo_sottotitoli_mediano": m["ritardo_sottotitoli"]["mediana"],
        "copertura_sottotitoli": round(sum(e["a"] - e["da"] for e in ev) / d, 2),
        "volume_lufs": m["volume"]["tutto_lufs"], "voce_meno_resto_db": round(m["volume"]["voce_lufs"] - m["volume"]["resto_lufs"], 1)
        if m["volume"]["voce_lufs"] and m["volume"]["resto_lufs"] else None,
        "musica": m.get("musica_titolo"),
        "suoni_attacchi_ogni_10s": round(len(m["suoni"]["attacchi"]) / d * 10, 1),
        "secondi_di_live_usati": round(sum(z - y for y, z in unisci(intervalli(m))), 1),
        "pezzi_live": len(intervalli(m)),
    }


def confronta(sp, no):
    a, b = riassunto(sp), riassunto(no)
    return {"speedy": a, "nostra": b,
            "stessi_pezzi_di_live": sovrapp(intervalli(sp), intervalli(no)),
            "stesso_ordine": ordine_uguale(intervalli(sp), intervalli(no)) if intervalli(sp) and intervalli(no) else None,
            "stessa_musica": a["musica"] == b["musica"] if a["musica"] and b["musica"] else None,
            "inizio_live_speedy_vs_nostra": [round(min((p[0] for p in intervalli(sp)), default=0), 1), round(min((p[0] for p in intervalli(no)), default=0), 1)]}


if __name__ == "__main__":
    if sys.argv[1:] == ["--prova"]:
        assert sovrapp([(10, 20)], [(10, 20)]) == 1.0 and sovrapp([(10, 20)], [(15, 25)]) == 0.33 and sovrapp([(0, 1)], [(5, 6)]) == 0.0
        assert ordine_uguale([(0, 5), (10, 15)], [(0, 5), (10, 15)]) and not ordine_uguale([(10, 15), (0, 5)], [(0, 5), (10, 15)])
        assert nome_colore("#25fb06") == "verde" and nome_colore("#f70105") == "rosso" and nome_colore("#fafa76") == "giallo"
        print("ok")
    else:
        print(json.dumps(confronta(json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))), ensure_ascii=False, indent=1))
