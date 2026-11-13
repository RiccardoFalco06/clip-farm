#!/bin/zsh
# Foglio di contatto con il tempo scritto sopra ogni fotogramma.
# uso: foglio.sh video.mp4 uscita_prefisso [fps=2] [colonne=10] [righe=4] [da=0] [durata=tutto] [larghezza_fotogramma=192]
# -> uscita_prefisso_001.jpg, _002.jpg ...
v=$1; out=$2; fps=${3:-2}; c=${4:-10}; r=${5:-4}; da=${6:-0}; dur=$7; w=${8:-192}
ffmpeg -nostdin -v error -y -ss $da ${dur:+-t} $dur -i "$v" -vf "fps=$fps,scale=$w:-2,drawtext=text='%{eif\:(t+$da)*100/100\:d}.%{eif\:mod((t+$da)*100\,100)\:d\:2}':x=4:y=4:fontsize=$((w/8)):fontcolor=yellow:box=1:boxcolor=black@0.7:fontfile=/System/Library/Fonts/Supplemental/Arial.ttf,tile=${c}x${r}" -q:v 4 "${out}_%03d.jpg"
