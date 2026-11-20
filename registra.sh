#!/bin/zsh
# Registra una live a blocchi da 10 minuti, più la chat (solo Twitch).
# uso: registra.sh CARTELLA URL [canale_twitch] [primo_blocco]      lanciato dalla sentinella, si ferma con SIGTERM o a fine live
# I blocchi hanno tempi continui (niente -reset_timestamps): "concat:b_00003.ts|b_00004.ts" è un filmato unico,
# così una clip a cavallo di due blocchi si taglia senza perdere niente (vedi analizza.py).
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
QUI="${0:A:h}"
OUT="$1"; URL="$2"; CANALE="${3:-}"; PRIMO="${4:-0}"  # numero del primo blocco: una live ripresa continua la numerazione invece di sovrascrivere
SECONDI=$(python3 -I -c "import json; print(json.load(open('$QUI/config.json'))['blocco_secondi'])")
[[ -n "$CANALE" ]] && { python3 -I "$QUI/chat.py" "$CANALE" "$OUT/chat.jsonl" & CHAT=$!; }
trap '[[ -n "${CHAT:-}" ]] && kill $CHAT 2>/dev/null; kill 0' TERM INT
streamlink -O "$URL" best 2>>"$OUT/streamlink.log" |
  ffmpeg -nostdin -v error -i pipe:0 -map 0:v:0 -map 0:a:0 -c copy -f segment -segment_time "$SECONDI" -segment_start_number "$PRIMO" "$OUT/b_%05d.ts"
[[ -n "${CHAT:-}" ]] && kill $CHAT 2>/dev/null
touch "$OUT/FINE"
