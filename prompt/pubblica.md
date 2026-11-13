Pubblichi UNA clip sugli account social di Riccardo usando Claude in Chrome. Riccardo ha autorizzato la pubblicazione automatica di queste clip (config.json, `pubblicazione_automatica`). Lavora con calma, un passo alla volta, e alla fine rispondi SOLO con il JSON indicato in fondo.

## La clip
- File: `{{FILE}}`
- Titolo: {{TITOLO}}
- Didascalia: {{DIDASCALIA}}

## Dove pubblicare
{{DESTINAZIONI}}

Se una destinazione indica un profilo Chrome, scegli prima quel browser con `list_connected_browsers` / `select_browser`. Apri sempre una scheda nuova e chiudila alla fine.

### YouTube (Shorts)
1. Vai su https://studio.youtube.com, pulsante Crea → Carica video, carica il file con `file_upload`.
2. Titolo = il titolo sopra (aggiungi ` #shorts` se ci sta in 100 caratteri). Descrizione = la didascalia.
3. "No, non è destinato ai bambini". Visibilità: **{{VISIBILITA}}**. Non toccare altre impostazioni.
4. Pubblica e copia il link del video.

### Instagram (Reel)
1. Vai su https://www.instagram.com, Crea → Post, carica il file con `file_upload`, formato originale 9:16.
2. Didascalia = la didascalia sopra. Condividi. Poi apri il profilo e copia il link del reel appena pubblicato.

### TikTok
Solo se è tra le destinazioni: https://www.tiktok.com/tiktokstudio/upload, carica il file, didascalia, Pubblica, copia il link. Se la navigazione è bloccata o uno strumento risponde "Permission denied", chiudi la scheda, aprine una nuova e riprova una volta; se succede ancora segnala `"errore": "dominio bloccato"` e passa oltre.

{{CAMPAGNA}}

## Limiti (non si discutono)
- Non inserire mai password, codici o dati personali. Se un sito chiede l'accesso: per quella piattaforma rispondi `"serve_login": true` e passa alla successiva.
- Se compare una verifica anti-robot, un avviso di violazione, un blocco dell'account o una richiesta di accettare nuovi termini: fermati su quella piattaforma e riporta in `errore` il testo esatto letto a schermo.
- Non cambiare impostazioni dell'account, non cancellare niente, non rispondere a commenti o messaggi.
- Massimo 2 tentativi per piattaforma.
- Se uno strumento di Chrome fallisce, prima di arrenderti chiama `mcp__claude-in-chrome__list_connected_browsers`, scegli il primo browser con `mcp__claude-in-chrome__select_browser` e riprova una volta. Se gli strumenti di Chrome (`mcp__claude-in-chrome__*`) ancora non ci sono o non rispondono, non è un accesso scaduto: rispondi solo `{"errore": "chrome non disponibile", "dettaglio": "<testo esatto dell'errore ricevuto>"}`.

## Risposta
```json
{"youtube": {"url": "...", "account": "..."}, "instagram": {"url": "...", "account": "..."}, "tiktok": {"errore": "..."}}
```
Per ogni piattaforma una sola tra: `url` (+ `account` usato), `serve_login: true`, `errore: "testo"`.
