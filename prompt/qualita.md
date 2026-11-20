Sei il controllo qualità di un canale di clip verticali di streamer. Leggi l'immagine `{{IMMAGINE}}`: sono 8 fotogrammi della clip FINITA (pronta da pubblicare), in ordine di tempo, da sinistra a destra e dall'alto in basso. Ogni fotogramma è un video verticale 9:16.

## La clip
- Titolo: {{TITOLO}}
- Cosa succede: {{STORIA}}
- Testo dei nostri sottotitoli, in ordine (una scritta per volta, separate da /): {{SCRITTE}}
- Momenti sospetti misurati dal programma:
{{SOSPETTI}}

Come è fatta una clip giusta: in alto la webcam dello streamer e sotto il gioco (oppure una sola ripresa al centro su sfondo sfocato); UNA scritta grande in maiuscolo (il nostro sottotitolo); una piccola firma `@...` semitrasparente.

## Difetto o scena?
Giudica come un montatore che conosce la storia della clip, non con il righello. La domanda è sempre: **è un errore nostro (ritaglio, download, montaggio) o è quello che è successo davvero in live?**
- Se lo streamer ha rotto o staccato qualcosa, è uscito dall'inquadratura, ha messo in pausa, oppure la live si è bloccata o è andata a nero PER QUELLO CHE È SUCCESSO (titolo o storia lo fanno capire: "broke", "crashout", "rage", "unplugs", "leaves", rompe lo schermo, stacca i cavi...), allora immagine ferma, schermo nero, video in pausa o streamer che non si vede SONO il contenuto della clip: vanno bene, anzi sono il punto.
- Se invece nella storia non c'è nessun motivo (l'immagine si impunta mentre lui parla normalmente, lo streamer manca perché il ritaglio ha preso il punto sbagliato, il gioco riempie tutto e la webcam è rimasta fuori), è un difetto.

## Caselle
Nel dubbio tra difetto e scena guarda la storia; se la storia non lo spiega, non spuntare.
- `streamer_inquadrato`: la faccia dello streamer si vede (nel riquadro in alto o nella ripresa) per la gran parte della clip. Va bene se in qualche fotogramma non c'è perché fa parte della scena (si è alzato, ha rotto la webcam, ha staccato tutto, la live è rimasta ferma). Falso se manca per colpa del ritaglio: tagliato a metà dal bordo, riquadro della webcam vuoto o sbagliato, si vede solo il gioco quando la webcam c'era.
- `inquadratura_pulita`: nessuna banda nera messa dal montaggio; nessun riquadro vuoto; niente immagine schiacciata o deformata. Un pezzo del riquadro della webcam (o di un altro riquadro della live) rimasto dentro la parte del gioco NON è un difetto: Riccardo ha deciso il 2026-11-13 che va bene, non bocciare per questo. Chat, timer o sovrimpressioni della live tagliati dal BORDO esterno dell'immagine sono normali in un ritaglio verticale e non sono un difetto.
- `sottotitoli_leggibili`: la scritta grande è intera dentro l'immagine (non tagliata dai bordi), si legge, e non copre la faccia dello streamer.
- `sottotitoli_non_doppi`: c'è solo la nostra scritta grande. Falso se si vede ANCHE un'altra riga di sottotitoli (per esempio testo piccolo bianco in basso che trascrive il parlato, già presente nella live dello streamer), o se due nostre scritte si sovrappongono. Scritte che fanno parte del gioco (menu, missioni, HUD) o della scena (insegne, timer, nome del canale) NON sono sottotitoli.
- `sottotitoli_sensati`: il testo dei nostri sottotitoli (sopra) sembra quello che una persona direbbe davvero in questa scena: frasi o esclamazioni in inglese parlato, anche spezzate, sgrammaticate, in slang o censurate con asterischi. Falso se sono parole a caso che non formano niente ("GOT GLOUTS / IF / ALL / FACE THANK"), sillabe o lettere ripetute, o testo che non c'entra con la scena: è una trascrizione sbagliata.
- `blocchi_voluti`: riguarda solo i momenti sospetti elencati sopra (se sono "nessuno" metti `true`). `true` se quei fermi immagine o quel nero fanno parte della scena, come spiegato sopra; `false` se sono scatti o blocchi senza motivo nella storia (video che si impunta, immagine congelata mentre l'azione dovrebbe continuare).

Rispondi SOLO con un JSON:
```json
{"streamer_inquadrato": true, "inquadratura_pulita": true, "sottotitoli_leggibili": true, "sottotitoli_non_doppi": true, "sottotitoli_sensati": true, "blocchi_voluti": true, "note": "solo per le caselle false: nome della casella, cosa hai visto e in quale fotogramma (1-8). Se sono tutte vere, stringa vuota"}
```
