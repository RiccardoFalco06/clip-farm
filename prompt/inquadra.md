Leggi le sei immagini {{IMMAGINI}} (1280×720): sono sei fotogrammi in ordine di tempo dello stesso tratto di una live di {{STREAMER}}. Servono per ritagliare la clip in verticale. La scena può cambiare da un'immagine all'altra (webcam piccola sul gioco, poi webcam a schermo intero): descrivi ogni immagine per conto suo.

Rispondi SOLO con un array JSON di sei elementi, uno per immagine, nello stesso ordine:
```json
[{"facecam": [x, y, larghezza, altezza], "soggetto_cx": 640, "sottotitoli_y": null}, {"facecam": null, "soggetto_cx": 640, "sottotitoli_y": 655}]
```
- `facecam`: il riquadro della webcam dello streamer sovrapposto al gioco in quell'immagine, in pixel, **appena dentro** i suoi bordi (meglio 3–4 pixel in meno che un filo di gioco in più). Se la webcam è nello stesso punto in più immagini, usa gli stessi numeri. Metti `null` se in quell'immagine la webcam non c'è o se tutta l'immagine è la ripresa (live dal vivo, "just chatting", webcam a schermo intero).
- `soggetto_cx`: la coordinata x del centro della cosa più importante da tenere al centro del ritaglio verticale: il personaggio o l'azione del gioco se c'è la webcam, altrimenti la faccia dello streamer.
- `sottotitoli_y`: se nell'immagine ci sono sottotitoli già messi dallo streamer nella sua live (una riga di testo che trascrive quello che dice, di solito piccola, in basso al centro), la coordinata y del loro bordo SUPERIORE; altrimenti `null`. Le scritte del gioco (menu, missioni) e la chat non contano.
