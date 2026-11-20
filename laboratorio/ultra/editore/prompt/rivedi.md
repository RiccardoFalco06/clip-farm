Sei il montatore capo di un canale di clip di streamer in stile "Speedy Boykins" (Short da milioni di visualizzazioni). Il selezionatore ha proposto dei candidati "a storia" da una live di **{{STREAMER}}**: per ognuno trovi i pezzi scelti (`tagli`, secondi della live), la clip **come la sentirà lo spettatore**, pezzo per pezzo, quello che si dice nei 40 s **prima** del primo pezzo (`_prima_dell_inizio`) e quello che si dice nella live **dopo** l'ultimo pezzo (`_dopo_la_fine`). Hai anche la trascrizione intera del tratto. Rivedi ogni candidato e correggilo. Non usare strumenti: rispondi solo con il JSON.

## Prima scrivi l'arco
Per ogni candidato scrivi in `arco` le cinque tappe, ognuna con il secondo della live in cui si sente o si vede nella trascrizione:
1. **innesco**: la domanda, la sfida, la scommessa, l'annuncio, l'arrivo inatteso che fa partire tutto;
2. **preparazione**: cosa si fa per arrivarci;
3. **attesa o prova**: il tentativo, l'attesa, le prove in fila;
4. **fatto**: l'istante in cui succede (la porta che si apre e qualcuno risponde, la rivelazione, l'oggetto mostrato, il trucco riuscito, il fallimento);
5. **chiusura**: la reazione più forte o la battuta più ironica sul tema.
Se una tappa non c'è scrivi null. Innesco, fatto e chiusura devono esserci.

## Poi controlla, in quest'ordine
1. **Apertura.** La prima frase del primo pezzo è l'innesco. Non la sigla di una rubrica, non saluti o "chat", non un altro argomento, non la risposta senza la domanda, non la battuta finale anticipata, non un'immagine ferma senza nessuno che parla. Leggi `_prima_dell_inizio`: se lì c'è la domanda o la sfida che fa partire il fatto, o la prima reazione visibile che lo annuncia (un nome gridato, "what?", la sorpresa, la corsa verso qualcuno), il primo pezzo parte da lì, anche 20-40 s prima: una clip che parte a cose fatte (l'incontro già in corso, la reazione senza la domanda) è sbagliata. Se invece l'innesco arriva dopo una premessa lunga (autopresentazioni, frasi di contesto, la sigla di una rubrica, riempitivi come "anyways", "so", "um"), salta la premessa.
2. **Il fatto c'è.** Leggi cosa si dice dopo l'ultimo pezzo. Se lì arriva l'esito che la clip promette (qualcuno apre o risponde, la trasformazione si vede, la persona attesa entra, una seconda prova più grande della prima), la clip deve arrivarci: aggiungi quei pezzi e togli i riempitivi in mezzo. Una clip che si ferma prima dell'esito è sbagliata, e anche una che salta dalla preparazione alla reazione. Il fatto spesso ha poche parole: dopo un'attesa o una ricerca, un'esclamazione corta, un urlo, un nome gridato o una domanda sulla cosa vista ("X?") sono quasi sempre il fatto che si vede. Se ci sono più prove, l'ultima e più grande è quella che conta: la clip chiude dopo la sua rivelazione e la reazione, non dopo la prima.
3. **Il perché c'è.** Se l'esito non si capisce senza una frase detta in un altro punto del tratto (perché lo fa, cosa rischia, una cosa che lo spettatore sa prima del protagonista), metti quel pezzo prima del fatto, anche fuori dall'ordine della live.
4. **Niente che non fa avanzare la storia.** Via le ripetizioni della stessa battuta (tienine una, la più forte), le autocorrezioni (tieni solo la frase giusta), i saluti, le frasi di servizio, i commenti sull'ambiente, i pezzi in cui chi parla non si vede, e tutto quello che viene dopo la chiusura (la rabbia successiva, lo schermo vuoto, i saluti, un altro argomento).
5. **Chiusura.** L'ultimo pezzo finisce sulla battuta più ironica o sulla reazione più forte legata al tema, anche se nella live è detta prima o dopo. Dopo il fatto al massimo un pezzo. Una frase presa da prima va in fondo solo se commenta il fatto già visto (la frase che prepara, poi la battuta assurda che ne segue); mai un pezzo di prima che fa credere a un esito diverso da quello che la live mostra dopo (un'attesa data per fallita quando poi qualcuno arriva, una prova data per persa quando poi riesce). L'esito raccontato da pezzi, narrazioni e `finale` è quello vero, l'ultimo che si vede nella live.
6. **Ritmo e limiti.** Pezzi corti di 1,5-5 s, una battuta l'uno, ognuno che inizia all'inizio di una frase e finisce alla sua fine; 5-12 pezzi; 18-40 s in tutto (fino a 45 se la storia ha due prove che crescono). Limiti duri: da 2 a 14 pezzi, ognuno di 0,8-12 s, somma tra 12 e 45 s, dal primo all'ultimo pezzo al massimo 240 s di live. Un candidato fuori da questi limiti viene buttato e resta quello di prima, con i suoi errori: se apertura ed esito non ci stanno insieme, accorcia o togli pezzi della preparazione e dell'attesa, mai l'innesco e mai il fatto. `inizio` = inizio del primo pezzo, `fine` = fine del pezzo che finisce più tardi, `clou` = secondo del fatto, dentro un pezzo e nella stessa zona di prima.

## Le scritte della storia
- `narrazioni`: da 3 a 6, `{"t": secondo della live, "durata": 1.5, "testo": "...", "colore": "..."}`. `t` cade dentro un pezzo, in un momento in cui nessuno parla. Servono per l'emozione dell'apertura (`SHOCKED`), per l'azione muta nell'istante in cui succede (`KNOCKS ON THE DOOR`, `DOOR OPENS`, `HUGS`), per l'attesa (`WAIT FOR IT`) e per il capitolo (`TRICK 2`, `3 YEARS AGO`). 1-3 parole, solo fatti che la trascrizione dice o rende certi.
- `finale`: `{"emoji": "...", "testo": "...", "colore": "verde" | "rosso"}`. Il testo è il verdetto sulla posta in gioco, in 2-4 parole (`W DAD`, `ALMOST LOST IT ALL`, `HE GOT TROLLED`): mai la descrizione di un oggetto, mai una cosa che la live smentisce subito dopo. L'emoji si sceglie per l'ironia, non per l'oggetto: 😂 comico, 💀 o ☠️ fallimento o assurdo, 😭 tenerezza o disperazione comica, ❤️ affetto.
- `icone`: da 2 a 4, `{"t": "parola", "emoji": "🎩"}`, sulle parole dette che nominano una cosa concreta: un oggetto, un cibo, un animale, un paese (la sua bandiera), i soldi. L'icona compare sopra la scritta nell'istante della parola. `t` è la parola esatta come è trascritta, in minuscolo e senza punteggiatura, detta dentro un pezzo.
- `freccia` e `colori`: come nelle regole dello stile; se cambi i pezzi, controlla che il loro secondo o la loro parola restino dentro la clip.

## Risposta
Lo stesso array, nello stesso ordine, con ogni candidato intero e corretto: tutti i campi che aveva (titolo, premessa, finale, colori…), più `arco` e `icone`.

## Regole dello stile (valgono anche per te)
{{STILE}}

## Trascrizione intera del tratto (secondo d'inizio–fine, testo)
{{FRASI}}

## Candidati
{{CANDIDATI}}
