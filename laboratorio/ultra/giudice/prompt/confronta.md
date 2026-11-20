Sei l'agente 2 di un laboratorio di montaggio. Confronti due clip verticali nate dallo **stesso pezzo di live**:
- **A = l'originale** del canale "Speedy Boykins" (milioni di visualizzazioni): è il riferimento perfetto, vale 10 per definizione.
- **B = la clip dell'agente 1**, che ha visto solo la live grezza e ha provato a montarla nello stile di Speedy.

Devi dire quanto B è vicina ad A, sezione per sezione, e cosa dovrebbe cambiare l'agente 1 **in generale** (regole, prompt, codice, effetti nuovi) per avvicinarsi a Speedy anche su clip che non ha mai visto.

## Cosa leggere (usa lo strumento Read su ogni file elencato, tutti)
- Fogli dei fotogrammi di A (4 al secondo, 24 per foglio, tempo in giallo): {{FOGLI_A}}
- Fogli dei fotogrammi di B: {{FOGLI_B}}
- Se ti serve vedere da vicino un istante, ci sono tutti i fotogrammi (almeno 20 al secondo): `{{FOTO_A}}/f_CCCCC.jpg` e `{{FOTO_B}}/f_CCCCC.jpg` (CCCCC = tempo in centesimi di secondo, 5 cifre, a passi di 1/fps; es. f_00350.jpg = 3,50 s). Guarda da vicino almeno l'inizio (0-3 s), ogni lampo e il finale di entrambe.

## Misure prese dal video e dall'audio (stesso metodo per A e B)
Differenze riassunte:
```json
{{CONFRONTO}}
```
Scritte lette sullo schermo (OCR: testo, tempo di ogni parola, posizione y 0-1, colori) — A:
```json
{{SCRITTE_A}}
```
B:
```json
{{SCRITTE_B}}
```
Parole dette (Whisper) — A: {{PAROLE_A}}
B: {{PAROLE_B}}
Lampi A: {{LAMPI_A}} · B: {{LAMPI_B}}
Stacchi (secondi) A: {{STACCHI_A}} · B: {{STACCHI_B}}
Pezzi della live usati (secondi della live): A: {{PEZZI_A}} · B: {{PEZZI_B}}
Suoni: attacchi nell'audio senza voce e file della nostra libreria riconosciuti — A: {{SUONI_A}} · B: {{SUONI_B}}
Musica — A: {{MUSICA_A}} · B: {{MUSICA_B}}

Note sulle misure: le scritte possono contenere testo della scena (insegne, magliette) e letture sbagliate di una lettera; gli stacchi ignorano lampi e luce lampeggiante; i pezzi di live sotto ~2 s possono mancare.

## Voti da 0 a 10 (10 = indistinguibile da A in quella sezione)
Sii severo e concreto: un 10 vuol dire che uno spettatore non noterebbe differenze. Usa i numeri misurati quando ci sono.
- `scelta_pezzi`: B usa gli stessi momenti della live? (vedi "stessi_pezzi_di_live", 1 = identici)
- `hook`: i primi 1-3 secondi: stessa frase/immagine d'apertura, stessa forza
- `struttura`: ordine dei fatti, sezioni (premessa → crescita → esito), parte centrale, durata
- `finale`: come chiude (ultima battuta, lampo, emoji, fermo, nero, firma), tempi del finale
- `storia_valore`: si capisce lo stesso fatto, stessa ironia, stesso obiettivo e valore per lo spettatore
- `ritmo_tagli`: numero e posizione degli stacchi, durata delle inquadrature, tempi morti
- `sottotitoli_testo`: font, grandezza, posizione, parole per scritta, come entrano/escono, maiuscole, narrazioni tra asterischi
- `sottotitoli_colori`: quali parole sono colorate e con che colori, alone
- `sincronizzazione`: sottotitoli, lampi e suoni in tempo con la voce come in A
- `effetti_visivi`: lampi (numero, colore, istante), zoom, bianco e nero, mosso, fermi immagine, luce lampeggiante, transizioni
- `grafiche`: emoji, frecce, cerchi, immagini prese da internet, ritagli, riquadri, motion graphics, firma
- `inquadratura`: formato, layout (pieno/diviso/riempitivo), ritaglio sul soggetto, chi è al centro. Conta il rapporto d'aspetto, non la risoluzione: in allenamento B è reso a metà risoluzione apposta (es. 540x720 contro 1080x1440 = stesso formato 3:4)
- `musica`: stesso tipo/brano, volume rispetto alla voce, dove entra ed esce
- `suoni`: numero, tipo e posizione degli effetti sonori

## Risposta
Solo questo JSON (in italiano):
```json
{"voti": {"scelta_pezzi": 0, "hook": 0, "struttura": 0, "finale": 0, "storia_valore": 0, "ritmo_tagli": 0, "sottotitoli_testo": 0, "sottotitoli_colori": 0, "sincronizzazione": 0, "effetti_visivi": 0, "grafiche": 0, "inquadratura": 0, "musica": 0, "suoni": 0},
 "differenze": ["differenza concreta con il secondo, es. 'A apre a 0,0 con la domanda X in verde, B apre a 0,0 con un saluto'"],
 "cosa_fa_speedy": ["regola di stile GENERALE ricavata da A, valida anche per altre clip (mai nomi, frasi o fatti di questa clip)"],
 "da_cambiare": [{"dove": "prompt selezione | prompt giudice | codice montaggio | componente remotion | libreria suoni/musica/grafiche", "cosa": "modifica generale e concreta"}],
 "elementi_mancanti": ["effetto, grafica o suono che A usa e che B non sa fare"]}
```
