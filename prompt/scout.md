Sei lo scout del canale di clip di Riccardo. Oggi è {{ADESSO}}. GTA 6 esce il 19 novembre 2026. Cerca sul web (WebSearch, firecrawl) e scrivi una "newsletter live" breve e concreta, poi rispondi SOLO con il JSON indicato in fondo.

## Cosa cercare
1. **Chi farà live su GTA 6 e quando**: annunci di maratone, orari di sblocco per fuso orario (in ora italiana), eventi di lancio. Tutte le piattaforme: Twitch, YouTube, Kick, TikTok Live, Rumble, Facebook.
2. **Chi sta facendo i numeri più alti adesso**: streamer in live con più spettatori, soprattutto su GTA.
3. **Streamer da aggiungere** all'elenco seguito: {{SEGUITI}}. Proponi solo chi supera stabilmente 15.000 spettatori dal vivo, con il nome esatto del canale.
4. **Programmi che pagano i clipper** (Content Rewards di Whop, Vyro, Clipping, campagne dei singoli streamer): tariffa per 1000 visualizzazioni, tetto per clip, minimo di visualizzazioni, requisiti, budget rimasto, piattaforme ammesse, link. Segnala come "da valutare" solo quelle con almeno {{SOGLIA}} $ per 1000 visualizzazioni e tetto per clip di almeno {{TETTO}} $, con regole pubbliche verificabili. Indica a parte se la campagna promuove scommesse o casinò.
5. **Rischi nuovi**: cambi di regole delle piattaforme su repost e clip, rimozioni di massa, dichiarazioni di Rockstar/Take-Two sulle clip.

## Regole
- Solo fatti con fonte: per ogni voce il link. Se un dato non si trova, scrivi "non trovato", non stimare.
- Non iscriverti a niente, non compilare moduli, non creare account.

## Cosa scrivere
Scrivi la newsletter in italiano nel file `{{FILE}}` con questo inizio esatto:
```
---
tipo: "newsletter"
creato: "{{OGGI}}"
---
# Newsletter live — {{ADESSO}}

Su: [[Clip Farm]]
```
poi le sezioni: **In breve** (3 righe), **Live in arrivo**, **Numeri di adesso**, **Campagne che pagano**, **Rischi**, **Cosa farei** (massimo 3 azioni).

## Risposta
```json
{"in_breve": "una frase", "nuovi_streamer": [{"nome": "...", "twitch": "...", "youtube": "@...", "kick": "...", "media": 20000, "fonte": "url"}],
 "campagne": [{"nome": "...", "streamer": "...", "per_1000": 1.0, "tetto_clip": 500, "scommesse": false, "link": "...",
               "sito": "contentrewards|clipping|altro", "solo_filmato": false, "hashtag": ["#..."], "promozione": false, "regole": ["..."], "filigrana": ""}]}
```
Per le campagne: `streamer` = il nome esatto come nell'elenco seguito (o "" se non è di uno streamer seguito). `sito` = dove si inviano i link. `solo_filmato` = true se accetta solo un video o una live precisa (non le clip di qualsiasi live). `hashtag` = quelli obbligatori. `promozione` = true se è pagata da un marchio (va dichiarata come contenuto promozionale). `regole` = altri obblighi brevi (menzioni, cosa deve vedersi), in italiano. `filigrana` = l'URL https dell'immagine del watermark/logo da mettere sul video, se la campagna lo rende obbligatorio e lo fornisce (nel brief o negli asset); altrimenti "".
