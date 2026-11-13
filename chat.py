"""Conta i messaggi della chat di Twitch mentre si registra.

uso: python3 -I chat.py CANALE chat.jsonl     (una riga per messaggio: {"t": secondi dall'avvio, "m": testo})
Lettura anonima dall'interfaccia IRC pubblica di Twitch (accesso in sola lettura previsto da Twitch).
shortcut: solo Twitch; per Kick e YouTube l'analisi usa solo il volume. Aggiungerle se i picchi di volume non bastano.
"""
import json
import socket
import sys
import time


def messaggio(riga):
    """Testo di un messaggio di chat, o None per le righe di servizio."""
    parti = riga.split(" PRIVMSG ", 1)
    return parti[1].split(" :", 1)[1] if len(parti) == 2 and " :" in parti[1] else None


if __name__ == "__main__":
    assert messaggio(":pippo!pippo@pippo.tmi.twitch.tv PRIVMSG #kaicenat :W stream") == "W stream"
    assert messaggio(":tmi.twitch.tv 001 justinfan1 :Welcome") is None
    if len(sys.argv) > 2:
        canale, uscita, t0 = sys.argv[1].lower(), sys.argv[2], time.time()
        while True:  # se cade la connessione si ricollega: i tempi restano riferiti all'avvio
            try:
                s = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=300)
                s.sendall(f"NICK justinfan{int(t0) % 100000}\r\nJOIN #{canale}\r\n".encode())
                resto = b""
                with open(uscita, "a") as f:
                    while True:
                        dati = s.recv(65536)
                        if not dati:
                            break
                        *righe, resto = (resto + dati).split(b"\r\n")
                        for r in righe:
                            r = r.decode("utf-8", "replace")
                            if r.startswith("PING"):
                                s.sendall(b"PONG :tmi.twitch.tv\r\n")
                            elif (m := messaggio(r)) is not None:
                                f.write(json.dumps({"t": round(time.time() - t0, 1), "m": m}, ensure_ascii=False) + "\n")
                        f.flush()
            except OSError:
                pass
            time.sleep(5)
