#!/bin/zsh
# 18/11 22:00 (Riccardo): clip farm riparte da sola per il lancio di GTA 6; la sentinella rileva il lancio vero
for j in sentinella catena agenti; do launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.riccardo.clipfarm.$j.plist 2>/dev/null; done
