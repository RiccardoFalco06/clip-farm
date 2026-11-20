Sei l'ultimo controllo prima di montare una clip per un canale in stile "Speedy Boykins" (clip di streamer da milioni di visualizzazioni). Giudichi UN momento candidato di una live di **{{STREAMER}}** ({{GIOCO}}). Leggi l'immagine `{{IMMAGINE}}` con lo strumento Read: sono 24 fotogrammi in ordine, da sinistra a destra e dall'alto in basso (6 per riga), ognuno con il suo secondo scritto in giallo. Poi rispondi SOLO con il JSON.

## Il candidato
Da {{INIZIO}} a {{FINE}} secondi, momento clou a {{CLOU}}. Il selezionatore (che ha letto solo il testo) dice — premessa: {{PREMESSA}} · finale: {{FINALE}}

{{STORIA}}Picchi misurati di volume e chat nella zona (secondo, forza; sopra 3 = urlo o chat che esplode): {{PICCHI}}

Trascrizione della zona (secondo, testo; mescola lo streamer e le voci del gioco):
{{FRASI}}

## Giudica da sconosciuto
Fai finta di non conoscere lo streamer, la trama del gioco, né cosa è successo prima. Tieni conto che tu vedi solo 24 fotogrammi e un testo imperfetto, mentre lo spettatore vede il video e **sente la voce**: urla, risate e tono fanno metà del lavoro. Le parole ripetute o tutte maiuscole e i picchi sono segni di emozione forte.

1. Scrivi in `cosa_succede` una frase semplice su cosa vede e sente lo spettatore.
2. Dai tre voti da 1 a 10 usando questo metro, preso da clip vere con milioni di visualizzazioni:
   - **9–10** — la premessa è detta o mostrata in modo esplicito e il finale è una rivelazione o una reazione enorme.
   - **7–8** — si capisce *che tipo* di situazione è anche senza i dettagli, e lo streamer ha una reazione grossa e genuina a qualcosa che sta succedendo in quel momento. Esempi: l'avversario fa una giocata fortunata e lui urla "How did you do that? You gotta be the luckiest motherf***er ever!" (9 milioni di visualizzazioni: non si vede bene la giocata, ma si capisce che è stato battuto in modo assurdo); uno parla a raffica senza senso e l'altro risponde "I have no idea what the f*** you're saying right now"; lo streamer vede il suo idolo e urla il suo nome.
   - **5–6** — reazione vera ma tiepida, oppure situazione chiara ma senza finale.
   - **1–4** — filmato della trama del gioco con dialoghi tra personaggi e lo streamer che dice due parole; reazione a qualcosa che non si vede e non viene detto in nessun punto della clip; conversazione già iniziata su persone o fatti che lo spettatore non conosce; parlato a bassa energia.
   I tre voti: `capibile` (si capisce la situazione, almeno nel tipo?), `divertente` (fa ridere, sorprende o soddisfa chi non segue lo streamer?), `finale` (finisce su una reazione, una battuta o un risultato netto?).
   Se la premessa dice che il momento è una clip fatta dagli spettatori, sappi che loro l'hanno già scelto e guardato: un gesto rapido (uno schiaffo, una caduta) può cadere tra un fotogramma e l'altro, quindi fidati del loro titolo per capire cosa succede e giudica se un estraneo se lo godrebbe. Nei titoli degli spettatori "broke", "crashout", "descends into madness" vogliono dire che lo streamer perde la testa dalla rabbia, non che il gioco ha un difetto. Quando in una clip così lo streamer rompe o stacca qualcosa e l'immagine resta ferma, in pausa o nera, o lui sparisce dall'inquadratura, non è un difetto tecnico: è la conseguenza di quello che ha fatto ed è il finale della clip. Tienila dentro al taglio (2–3 secondi bastano) e non abbassare i voti per questo.
   Nel montaggio finale la webcam dello streamer viene ingrandita e occupa il terzo alto dello schermo, con il gioco sotto: non penalizzare la webcam piccola. Ignora scritte, sottotitoli o marchi già presenti nel filmato.
   Giochi horror (gusto di Riccardo, 12 nov): una cosa strana che appare all'inizio (un fungo con la faccia, una paperella enorme) è una premessa che incuriosisce anche senza spiegazioni; un jumpscare (qualcosa che salta addosso, schermo che si sfoca o trema di colpo, il mostro che ricompare deformato) è un finale valido anche se lo streamer resta zitto. Nei fotogrammi un jumpscare sembra spesso un'immagine sfocata o mossa: non scambiarlo per un difetto. Resta invece da 1–4 la scena buia dove non si vede cosa spaventa.
3. Puoi correggere il taglio: sposta `inizio` indietro se la premessa (la domanda, la scommessa, la frase che dice cosa sta per fare, lo schermo che lo mostra) sta prima; accorcia la `fine` a 1–2 secondi dopo il finale. Durata 12–55 secondi, `clou` tra {{ZONA0}} e {{ZONA1}}, tutto tra 0 e {{DURATA}}.

## Se i voti sono alti, prepara il montaggio
(compila comunque tutti i campi)
I sottotitoli parola per parola li mette il codice. Tu aggiungi, con parsimonia:
- `enfasi`: 2–4 parole chiave da colorare, `"parola": "magenta"` oppure `"ciano"`, minuscole e senza punteggiatura, prese dalla trascrizione.
- `zoom`: al massimo uno, sulla reazione: `{"t": "parola@secondo", "durata": 1.5–2.5, "scala": 1.15}`.
- `lampi`: il montaggio ne mette già uno, con il suo suono, su ogni parola di `enfasi`, più una pausa in bianco e nero sui salti tra pezzi. Qui metti solo un fatto senza parole (un colpo, una caduta, la porta che si apre), al massimo 2: verde `#00ff3c` su una cosa riuscita, rosso `#ff2a1a` su un fallimento o uno shock, bianco `#ffffff` su una rivelazione.
- `suoni`: al massimo 3, solo per cose che i lampi non coprono (un riser prima del clou, un vine boom dopo una frase assurda), mai più di uno ogni 2–3 secondi.
- `musica`: una base, sempre, per tutta la clip (il volume lo regola il codice). Negli Short di riferimento è sempre un brano **slowed di tendenza, riconoscibile**, anche nei momenti comici: `phonk_Untitled-Super-Slowed.m4a` per comico, assurdo, imbarazzo, troll e tensione (la scelta normale); `funk_MONTAGEM-ALQUIMIA.m4a` o `funk_MONTAGEM-PERIGOSA.m4a` per azione, esaltazione e vittoria. Le altre basi non si usano: **mai `meme_*`** (pianoforte allegro, musica classica: suona da cartone animato) e niente phonk generiche senza titolo.
- I tempi `t` sono secondi **dall'inizio della clip corretta** oppure, meglio, una parola con il secondo vicino a cui cade, sempre dall'inizio della clip: `"shit@20"`.

Suoni disponibili (file | tipo | quando usarlo):
{{SUONI}}

Musiche disponibili: {{MUSICA}}

Testi (in inglese, pubblico internazionale):
- `titolo`: la premessa in massimo 60 caratteri, con il nome dello streamer, al massimo un'emoji, senza svelare il finale. Deve bastare da solo a capire cosa si sta per vedere.
- `didascalia`: una riga più 4–6 hashtag pertinenti (streamer, gioco, `#shorts`).

## Risposta
```json
{"cosa_succede": "...", "capibile": 0, "divertente": 0, "finale": 0, "motivo": "perché questi voti, in italiano",
 "inizio": 0.0, "fine": 0.0, "clou": 0.0, "titolo": "...", "didascalia": "...",
 "enfasi": {"parola": "magenta"}, "zoom": [], "lampi": [], "suoni": [], "musica": "file.m4a"}
```
