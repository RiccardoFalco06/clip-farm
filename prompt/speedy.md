

## Stile "speedy": campi in più (tutti facoltativi)
La clip verrà montata nello stile speedy. Oltre ai campi di sopra puoi aggiungere questi, solo dove servono davvero: sono eccezioni di stile, non regole. Se non sei sicuro, non metterli.

- `"colori"`: come `enfasi`, ma con più colori e per emozione o significato, non per chi parla. `{"parola": "colore"}` con colore tra `verde` (positivo, vittoria), `rosso` (fallimento, pericolo, rabbia), `giallo` (sorpresa, soldi), `ciano` (nomi, cose da notare), `magenta` (assurdo, esagerato), `rosa` (affetto, famiglia), `viola`, `corallo`, `oro`, `lime`. Da 3 a 8 parole chiave in una clip di 20-30 secondi.
- `"finale"`: `{"emoji": "😂", "testo": "HE LOST IT", "colore": "verde"}`. Chiusura con emoji al centro e scritta breve (2-4 parole, maiuscole, in inglese). Solo se la clip si chiude su una reazione forte che la scritta rende più divertente: circa 3 clip su 5, mai per abitudine. 😂 comico, 💀 fallimento o assurdo, 🥶 epico. Colore `rosso` per i fallimenti, altrimenti `verde`.
- `"narrazioni"`: `[{"t": 12.0, "durata": 2.0, "testo": "CAN'T STOP LAUGHING"}]`. Scritta tra asterischi che dice cosa sta facendo lo streamer quando NON parla: ride, urla, canta, resta in silenzio a fissare lo schermo. Solo se si capisce chiaramente dalla trascrizione e dai picchi (per esempio un urlo senza parole). Al massimo 2, di 2-4 parole. Mai per ripetere ciò che viene detto.
- `"freccia"`: `{"t": 0.3, "durata": 2.3, "chi": "sinistra" | "destra" | "unica", "testo": "BIG SMOKE"}`. Presenta una persona nei primi 3 secondi con una freccia e il suo nome. Solo se nella clip compare una persona diversa dallo streamer che lo spettatore deve riconoscere, o se lo streamer va presentato; `chi` dice quale faccia nel quadro. La posizione la calcola il montaggio; se non trova la faccia non la mette.
- `"vibe": "serio"`: solo se il momento è davvero serio (emergenza, notizia triste, discorso sentito). Toglie la giocosità: sottotitoli bianchi, niente colori, niente finale scherzoso. È raro.

Regole fisse di Riccardo per questo stile: mai scritte che ripetono o inventano parole non dette; il finale è un'eccezione; ogni elemento solo dove ci sta. Meglio una clip pulita che una carica.

## Montaggio a storia (sempre, da questo stile in poi)
Riccardo ha approvato il 12/11 le clip "a storia": da 1-3 minuti di live si tengono i momenti che raccontano un fatto e si uniscono con stacchi secchi. Per ogni candidato aggiungi `"tagli"`: i pezzi da tenere, in ordine, in secondi del tratto (come `t`/`fine` delle frasi).

- Totale 20-40 secondi, da 4 a 12 pezzi, ognuno di 1,5-8 secondi. `inizio` = inizio del primo pezzo, `fine` = fine dell'ultimo; `clou` dentro un pezzo.
- Ogni pezzo inizia all'inizio di una frase e finisce alla sua fine (usa `t` e `fine` delle frasi): mai una frase spezzata, mai un pezzo che finisce su "and", "to", "the", "if", "you" o su un numero a metà ("ten" senza "thousand"). Se la frase continua subito dopo, tienila intera.
- Il primo pezzo è già la posta in gioco o la frase più forte (mai saluti, "hello", "he just called me"). Poi 2-4 battute che fanno salire la storia, l'esito verso il 75-85% e l'ultimo pezzo che finisce subito dopo la battuta finale: lampo, emoji e scritta del finale li aggiunge il montaggio, dopo l'ultima parola.
- Togli i tempi morti, i riempitivi e le ripetizioni ("you know the rules" detto 4 volte: tienilo una volta), ma mai il passaggio che lega causa ed effetto (domanda → risposta, notizia → reazione).
- Niente pezzi in cui lo streamer non si vede per più di un secondo (va via, inquadra il pavimento), salvo che sia proprio il fatto (la telecamera caduta: 1 secondo basta).
- Preferisci momenti in cui si parla a un ritmo normale: un tratto parlato a raffica diventa sottotitoli illeggibili.
- `lampi` e `suoni` (2-3 in tutto, a 5 secondi l'uno dall'altro, solo su fatti veri): come `t` scrivi la parola esatta detta in quel momento ("thousand", "quit"), non un secondo. Niente `narrazioni` e niente `freccia` nelle storie.
- Titolo 25-40 caratteri: nome dello streamer, curiosità senza svelare l'esito (no "Banned", "Quit" se è il finale), 2 emoji uguali alla fine, almeno 2 tra chi/cosa/numero/tempo/contrasto/curiosità/beneficio. L'emoji del `finale` è la stessa del titolo e la scritta del finale non ripete il titolo.

Esempio (Kai e il cameraman che se ne va): `"tagli": [[76.2, 80.1], [80.55, 82.2], [110.5, 115.2], [116.5, 119.3], [127.0, 127.8], [186.5, 192.05], [211.3, 212.4], [214.5, 215.4], [249.7, 252.6]]`, titolo "Kai Cenat Yelled At His Cameraman 💀💀", finale `{"emoji": "💀", "testo": "HE REALLY QUIT", "colore": "rosso"}`.
