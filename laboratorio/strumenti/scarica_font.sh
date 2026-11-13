#!/bin/zsh
# uso: scarica_font.sh "Famiglia:peso[i]" ...   -> font/Famiglia-peso[i].ttf (Google Fonts, licenze aperte)
export SSL_CERT_FILE=/etc/ssl/cert.pem
for spec in "$@"; do
  fam=${spec%%:*}; w=${spec##*:}; it=0; [[ $w == *i ]] && it=1 && w=${w%i}
  out="font/${fam// /}-$w$([[ $it == 1 ]] && echo i).ttf"
  [[ -s $out ]] && continue
  url=$(curl -s -A "curl/8" "https://fonts.googleapis.com/css2?family=${fam// /+}:ital,wght@$it,$w" | grep -o 'https://[^)]*\.ttf' | head -1)
  [[ -z $url ]] && url=$(curl -s -A "curl/8" "https://fonts.googleapis.com/css2?family=${fam// /+}" | grep -o 'https://[^)]*\.ttf' | head -1)
  [[ -n $url ]] && curl -s -o "$out" "$url" && echo "ok $out" || echo "MANCA $spec"
done
