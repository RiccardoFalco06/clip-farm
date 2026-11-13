#!/bin/zsh
# Monta una scheda con la copia di laboratorio di monta.py tenendo il blocco condiviso (Demucs, Whisper, allineamento e render sono pesanti).
# uso: monta.sh scheda.json
LOCK=~/Projects/clip-farm/state/catena.lock
[[ $(df -g ~ | tail -1 | awk '{print $4}') -lt 3 ]] && echo "meno di 3 GB liberi: mi fermo" && exit 1
until mkdir $LOCK 2>/dev/null; do perl -e 'select(undef,undef,undef,5)'; done
trap 'rmdir $LOCK 2>/dev/null' EXIT INT TERM
cd ~/Projects/clip-farm/laboratorio && python3 -I monta.py "$1"
