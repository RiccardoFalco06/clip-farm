#!/bin/zsh
# Fogli di una fascia orizzontale del video, un fotogramma per cella con il tempo: per studiare le animazioni fotogramma per fotogramma.
# uso: striscia.sh video uscita.jpg da durata y altezza [colonne=4] [righe=15] [fps=sorgente] [larghezza_cella=480]
v=$1; out=$2; da=$3; dur=$4; y=$5; h=$6; c=${7:-4}; r=${8:-15}; fps=${9:-60}; w=${10:-480}
ffmpeg -nostdin -v error -y -ss $da -t $dur -i "$v" -vf "fps=$fps,crop=iw:$h:0:$y,scale=$w:-2,drawtext=text='%{eif\:(t+$da)*1000\:d}':x=2:y=2:fontsize=14:fontcolor=yellow:box=1:boxcolor=black@0.7:fontfile=/System/Library/Fonts/Supplemental/Arial.ttf,tile=${c}x${r}" -frames:v 1 -q:v 3 "$out"
