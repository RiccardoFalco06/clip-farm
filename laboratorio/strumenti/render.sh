#!/bin/zsh
# Un solo lavoro pesante alla volta su tutto il Mac: prende il blocco condiviso, rende, lo rilascia SEMPRE (anche se fallisce).
# uso: render.sh lavori.json [script=render-lab.mjs]
LOCK=~/Projects/clip-farm/state/catena.lock
until mkdir $LOCK 2>/dev/null; do perl -e 'select(undef,undef,undef,5)'; done
trap 'rmdir $LOCK 2>/dev/null' EXIT INT TERM
cd ~/Projects/clip-farm/laboratorio/remotion && node ${2:-render-lab.mjs} "$1"
