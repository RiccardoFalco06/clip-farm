"""Stato condiviso: configurazione e database (unica fonte di verità, le note di Obsidian si generano da qui)."""
import contextlib
import json
import sqlite3
import sys
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
CONFIG = json.loads((QUI / "config.json").read_text())
REG = Path(CONFIG["registrazioni"]).expanduser()

SCHEMA = """
create table if not exists live (id integer primary key, streamer text, piattaforma text, url text, titolo text, gioco text,
  inizio real, fine real, spettatori integer, picco integer, gta6 integer default 0, registrata integer default 0, pid integer);
create table if not exists blocco (live integer, n integer, stato text default 'nuovo', primary key (live, n));
create table if not exists clip (id integer primary key, live integer, titolo text, didascalia text, inizio real, fine real,
  file text, stato text default 'montata', creato real, perche text);
create table if not exists pubblicazione (clip integer, piattaforma text, account text, url text, quando real,
  visualizzazioni integer, aggiornato real, primary key (clip, piattaforma));
create table if not exists entrata (id integer primary key, data text, fonte text, importo real, stato text);
create table if not exists evento (id integer primary key, quando real, tipo text, testo text, email integer default 0, inviata integer default 0);
create table if not exists kv (k text primary key, v text);
"""


def db():
    (QUI / "state").mkdir(exist_ok=True)
    # più processi scrivono: ogni scrittura si chiude subito (la catena lavora un blocco per minuti e bloccava la sentinella) e chi trova occupato aspetta
    c = sqlite3.connect(QUI / "state/clipfarm.db", timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def evento(c, tipo, testo, email=False):
    """Ogni fatto notevole passa di qui: finisce in Obsidian e, se email=True, nella posta."""
    c.execute("insert into evento (quando, tipo, testo, email) values (?,?,?,?)", (time.time(), tipo, testo, int(email)))


def kv(c, k, v=None):
    if v is None:
        r = c.execute("select v from kv where k=?", (k,)).fetchone()
        return json.loads(r["v"]) if r else None
    c.execute("insert or replace into kv values (?,?)", (k, json.dumps(v)))


@contextlib.contextmanager
def uno_alla_volta(nome, scade=3600):
    """Un solo giro per volta di questo lavoro; se un altro è in corso si esce. Un blocco più vecchio di `scade` è un giro morto male."""
    blocca = QUI / "state" / f"{nome}.lock"
    (QUI / "state").mkdir(exist_ok=True)
    if blocca.exists() and time.time() - blocca.stat().st_mtime > scade:
        blocca.rmdir()
    try:
        blocca.mkdir()
    except FileExistsError:
        sys.exit(0)
    try:
        yield
    finally:
        blocca.rmdir()
