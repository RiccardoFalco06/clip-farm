Fai i conti del canale di clip di Riccardo usando Claude in Chrome: sola lettura, non pubblicare e non modificare niente. Alla fine rispondi SOLO con il JSON indicato in fondo.

## Cosa leggere
1. **Sessioni**: per ogni piattaforma con un account ({{PIATTAFORME}}) apri il sito e controlla che l'accesso sia ancora fatto (YouTube: https://studio.youtube.com · Instagram: https://www.instagram.com · TikTok: https://www.tiktok.com/tiktokstudio). Se chiede l'accesso: `"sessione": "login"`. Non inserire mai password o codici.
2. **Visualizzazioni** delle clip qui sotto (id, piattaforma, link). YouTube: Studio → Contenuti → Shorts, colonna Visualizzazioni. Instagram: profilo → Reel, numero sotto ogni reel (o Insights). Leggi il numero esatto; se è abbreviato ("12,3 K") convertilo.
3. **Entrate**: YouTube Studio → Guadagna/Analytics → Entrate (solo se il canale è monetizzato): entrate stimate degli ultimi 28 giorni. Se non è monetizzato, niente.
4. **Avvisi**: avvertimenti sul copyright, limitazioni o violazioni mostrati dalle piattaforme: riporta il testo esatto.

Apri sempre una scheda nuova e chiudila alla fine con `mcp__claude-in-chrome__tabs_close_mcp`, anche se qualcosa va storto: ogni scheda lasciata aperta resta in Chrome come un gruppo "Claude" in più.
Se uno strumento di Chrome fallisce, prima di arrenderti chiama `mcp__claude-in-chrome__list_connected_browsers`, scegli il primo browser con `mcp__claude-in-chrome__select_browser` e riprova una volta. Se gli strumenti di Chrome (`mcp__claude-in-chrome__*`) ancora non ci sono o non rispondono, non è un accesso scaduto: rispondi solo `{"errore": "chrome non disponibile", "dettaglio": "<testo esatto dell'errore ricevuto>"}`.

## Clip da controllare
{{CLIP}}

## Risposta
```json
{"sessioni": {"youtube": "ok", "instagram": "login"},
 "visualizzazioni": [{"clip": 12, "piattaforma": "youtube", "n": 15300}],
 "entrate": [{"fonte": "YouTube ultimi 28 giorni", "importo": 0.0, "valuta": "EUR", "stato": "stimato"}],
 "avvisi": [{"piattaforma": "youtube", "testo": "..."}]}
```
