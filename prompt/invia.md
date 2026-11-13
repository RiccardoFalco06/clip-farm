Invii a una campagna di clipping i link di una clip appena pubblicata sugli account di Riccardo, usando Claude in Chrome. Riccardo ha autorizzato l'invio automatico ("in futuro devi farlo in automatico non aspettare il mio sì"). Alla fine rispondi SOLO con il JSON indicato in fondo.

## Cosa inviare
- Campagna: {{CAMPAGNA}}
- Pagina della campagna: {{LINK_CAMPAGNA}}
- Clip: {{TITOLO}}
- Link pubblicati:
{{LINK}}

## Come
1. Apri una scheda nuova sulla pagina della campagna. Se è un elenco, apri la campagna con quel nome.
2. Se c'è "Join Campaign" ed è gratis, premilo prima (se chiede di pagare o di rispondere a domande, fermati: `"errore": "iscrizione da fare a mano"`). Poi premi "Submit clip" (Content Rewards) oppure "Upload" (clipping.net).
3. Se il modulo mostra i post recenti come riquadri, seleziona solo quelli di questa clip (stesso titolo o didascalia), una volta per piattaforma. Altrimenti incolla un link alla volta nel campo "Paste a link".
4. Spunta la casella "I've read the requirements…" e invia. Aspetta la conferma (per esempio "clips submitted").
5. Se dice che il link non si legge ancora ("couldn't read", "No new clips yet"), non insistere: chiudi e riporta quella piattaforma come non inviata. Si riprova da solo fra 5 minuti.
6. Chiudi la scheda.

## Limiti
- Seleziona e invia solo le clip elencate sopra, mai altri post.
- Non inserire password, codici o dati personali. Non accettare termini nuovi, non cambiare impostazioni. Se serve l'accesso, rispondi con `"errore": "serve il login"`.
- Massimo 2 tentativi.

## Risposta
```json
{"inviate": ["tiktok", "instagram"], "errore": ""}
```
`inviate` = le piattaforme confermate dal sito (lista vuota se nessuna).
