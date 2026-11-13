"""Manda a Riccardo UN solo riepilogo al giorno (dalle 8, con gli eventi delle 24 ore prima: lancio, live registrate, serve il login, newsletter...).

uso: python3 -I notifica.py      lanciato dalla sentinella quando ci sono eventi in attesa
L'email parte dal connettore Gmail di Claude, come nella routine Lead Medici: arriva sul telefono con l'app Gmail.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # con -I la cartella dello script non è nel percorso
from stato import CONFIG, QUI, db, kv, uno_alla_volta  # noqa: E402


def email(eventi):
    oggetto = "Clip Farm — riepilogo del giorno: " + (eventi[0]["tipo"] if len(eventi) == 1 else f"{eventi[0]['tipo']} e altre {len(eventi) - 1} novità")
    return oggetto, "\n".join(f"{time.strftime('%d/%m %H:%M', time.localtime(e['quando']))}  {e['tipo'].upper()}: {e['testo']}" for e in eventi)


if __name__ == "__main__":
    o, t = email([{"tipo": "live registrata", "testo": "Kai", "quando": 0}, {"tipo": "errore", "testo": "x", "quando": 0}])
    assert o == "Clip Farm — riepilogo del giorno: live registrata e altre 1 novità" and "ERRORE: x" in t
    if "--prova" not in sys.argv:
        with uno_alla_volta("notifica", scade=900):
            c = db()
            oggi = time.strftime("%Y-%m-%d")
            if time.localtime().tm_hour < 8 or kv(c, "email_giorno") == oggi:  # richiesta di Riccardo (13 nov): troppe email, una al giorno
                sys.exit(0)
            eventi = c.execute("select * from evento where email=1 and inviata=0 order by quando").fetchall()
            if eventi:
                oggetto, corpo = email(eventi)
                prompt = (f"Invia un'email con mcp__claude_ai_Gmail__send_message: to [\"{CONFIG['email']}\"], subject e body copiati IDENTICI da sotto "
                          "(testo semplice, niente Markdown). Non fare altro. Alla fine rispondi solo INVIATA, oppure ERRORE: motivo.\n\n"
                          f"SUBJECT: {oggetto}\n\nBODY:\n{corpo}\n\nDashboard: Obsidian → 10 Progetti → Clip Farm")
                r = subprocess.run([Path.home() / ".local/bin/claude", "-p", prompt, "--model", "claude-sonnet-5-5", "--max-turns", "4",
                                    "--allowedTools", "mcp__claude_ai_Gmail__send_message"], capture_output=True, text=True, timeout=300,
                                   env={**os.environ, "OBSIDIAN_SYNC_CHILD": "1"}, cwd=QUI)
                if "INVIATA" in r.stdout:
                    c.executemany("update evento set inviata=1 where id=?", [(e["id"],) for e in eventi])
                    kv(c, "email_giorno", oggi)
                    c.commit()
                else:  # resta in attesa: riprova al prossimo giro della sentinella
                    print(f"email non inviata (exit {r.returncode}): {(r.stdout or r.stderr)[-300:]}", file=sys.stderr)
