#!/bin/zsh
# Accende Clip Farm: sentinella e catena ogni minuto, Mac sempre sveglio. Resta acceso anche dopo il riavvio.
QUI="${0:A:h}"
for f in "$QUI"/launchd/*.plist; do
  cp "$f" ~/Library/LaunchAgents/
  launchctl bootout "gui/$UID/${f:t:r}" 2>/dev/null
  launchctl bootstrap "gui/$UID" ~/Library/LaunchAgents/"${f:t}" && echo "acceso: ${f:t:r}"
done
# Amphetamine tiene sveglio il Mac anche a coperchio chiuso finché Clip Farm è acceso (caffeinate, sopra, da solo non basta a coperchio chiuso)
if [ -d /Applications/Amphetamine.app ]; then
  osascript -e 'tell application "Amphetamine"' -e 'start new session' -e 'enable closed display mode' -e 'allow display sleep' -e 'end tell' >/dev/null && echo "acceso: Amphetamine (sessione senza scadenza)"
fi
