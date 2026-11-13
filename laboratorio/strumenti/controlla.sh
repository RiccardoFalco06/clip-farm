#!/bin/zsh
# Controllo di un video finito: durate audio/video, volume integrato (LUFS) e picco vero, foglio di fotogrammi.
# uso: controlla.sh video.mp4 uscita_prefisso [fps=3]
v=$1; out=$2; fps=${3:-3}
ffprobe -v error -show_entries stream=codec_type,duration,width,height,r_frame_rate -of compact=p=0:nk=0 "$v"
ffmpeg -nostdin -hide_banner -i "$v" -vn -af ebur128=peak=true -f null - 2>&1 | grep -A20 "^\[Parsed_ebur128.*Summary" | grep -E "I:|Peak:"
~/Projects/clip-farm/laboratorio/strumenti/foglio.sh "$v" "$out" $fps 8 3 0 "" 200
ls "${out}"_*.jpg
