#!/bin/zsh
# Spegne Clip Farm e chiude le registrazioni in corso (i blocchi già scritti restano e la catena non riparte).
QUI="${0:A:h}"
for f in "$QUI"/launchd/*.plist; do
  launchctl bootout "gui/$UID/${f:t:r}" 2>/dev/null && echo "spento: ${f:t:r}"
  rm -f ~/Library/LaunchAgents/"${f:t}"
done
sqlite3 "$QUI/state/clipfarm.db" "select pid from live where fine is null and registrata=1 and pid is not null" | while read p; do kill -TERM -- "-$p" 2>/dev/null && echo "registrazione fermata (pid $p)"; done
sqlite3 "$QUI/state/clipfarm.db" "update live set fine=strftime('%s','now'), registrata=0, pid=null where fine is null"
[ -d /Applications/Amphetamine.app ] && osascript -e 'tell application "Amphetamine" to end session' >/dev/null 2>&1 && echo "spento: Amphetamine"
