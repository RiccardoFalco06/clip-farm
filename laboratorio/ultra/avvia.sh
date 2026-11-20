#!/bin/zsh
# Ciclo speedy-ultra: prepara le 30 live (se manca qualcosa), poi i giri. Lanciato da launchd (com.riccardo.clipfarm.ultra), riprende da solo.
cd ~/Projects/clip-farm/laboratorio
export SSL_CERT_FILE=/etc/ssl/cert.pem
export TMPDIR=$(getconf DARWIN_USER_TEMP_DIR)  # senza, claude -p sotto launchd non funziona (visto l11 nov)
# la ricerca delle live (ultra/prepara.py) gira a parte, in parallelo: dal 18/11 il ciclo parte con le live già trovate
exec caffeinate -i nice -n 10 python3 -I ultra/ciclo.py >> ultra/ciclo.log 2>&1  # nice: la CPU va prima a clip farm
