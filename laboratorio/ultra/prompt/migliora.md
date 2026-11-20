Sei il correttore del ciclo "speedy-ultra" (laboratorio di Riccardo, progetto clip-farm). Scopo, parole di Riccardo: lo stile speedy-ultra deve "ricreare perfettamente gli stessi video di speedy" partendo dalla stessa live grezza — audio, musica, lampi, effetti, sottotitoli, sincronizzazione, tagli, storia, struttura, obiettivo, valore, ironia, dettagli, hook, parte centrale, finale, immagini (ha autorizzato a cercare e scaricare immagini dal web), effetti visivi e sonori, motion graphics, video riempitivi per tenere l'attenzione durante i discorsi lunghi, font.

## Come funziona
- **Agente 1** = la cartella in cui sei, `{{EDITORE}}`: `edita.py` (sorgente grezza → analisi → `prompt/seleziona.md` + `prompt/speedy.md` scelgono i pezzi → `prompt/giudica.md` prepara il montaggio → inquadratura → `monta.py` + Remotion `remotion/src/speedy/*.tsx`, composizione `ClipSpeedy`). Non vede MAI lo Short originale.
- **Agente 2** ha confrontato ogni clip dell'agente 1 con lo Short di Speedy nato dallo stesso pezzo di live e ha dato voti per sezione, differenze, regole di Speedy e modifiche consigliate.
- Tu sei al giro {{GIRO}}. Storico dei giri:
{{STORIA}}

## Cosa leggere
1. `{{CARTELLA}}/riassunto.json` (media, sezioni dalla più bassa, voti per clip, errori) e TUTTI i `{{CARTELLA}}/*.voto.json` (campi `differenze`, `cosa_fa_speedy`, `da_cambiare`, `elementi_mancanti`, `misure`).
2. Le modifiche dei giri precedenti: `{{GIRI}}/g*/modifiche.md` (cosa è stato provato e se ha funzionato: confronta le medie per sezione prima e dopo).
3. Se ti serve vedere: i fogli degli originali `{{DATI}}/<id>/misure_originale/fogli/*.jpg` e delle nostre clip `{{CARTELLA}}/<id>_misure/fogli/*.jpg`; i log dell'agente 1 `{{CARTELLA}}/<id>.agente1.log`; la scheda usata `{{EDITORE}}/lavoro/<id>_regia/scheda.json`.
4. Lo stile già studiato: `{{FARM}}/laboratorio/catalogo.md`, `{{FARM}}/laboratorio/libreria.json`, `{{FARM}}/laboratorio/appunti.md`, `{{FARM}}/laboratorio/da-capcut.md`.

## Cosa fare
Scegli le 2-4 modifiche che più alzano la media, partendo dalle sezioni con voto più basso e dalle differenze che si ripetono in più clip, e falle. Puoi cambiare:
- i prompt in `prompt/` (regole di scelta dei pezzi, struttura, hook, finale, colori, effetti, suoni, musica, titolo);
- `edita.py` (passi dell'agente 1: per esempio un passo di regia in più, più candidati, il modello usato per un passo);
- `monta.py` e `remotion/src/` (effetti, grafiche, font, animazioni, motion graphics nuovi: registra i componenti in ClipSpeedy, mantieni compatibili le schede esistenti);
- risorse nuove in `{{EDITORE}}/risorse/` (suoni, immagini, meme, video riempitivi scaricati dal web: Riccardo ha dato il permesso; scrivi da dove vengono in `risorse/FONTI.md`).

## Regole che non puoi violare
1. **Solo regole generali.** Mai nomi, frasi, fatti, tempi o titoli delle clip di allenamento dentro prompt o codice: dopo l'allenamento l'agente 1 verrà provato su 10 clip mai viste e una regola copiata da una clip lì non serve. Scrivi "quando lo streamer fa una domanda e poi reagisce, apri sulla domanda", non "apri su 'who is the best'".
2. Lavora SOLO dentro `{{EDITORE}}`. Non toccare niente fuori (il sistema vivo pubblica clip con `{{FARM}}/catena.py`, `{{FARM}}/monta.py`, `{{FARM}}/laboratorio/`).
3. Regole fisse di Riccardo che restano valide: mai sottotitoli di parole non dette; l'inizio sempre in movimento; icone ed emoji subito sopra o sotto la scritta (l'emoji del finale al centro); freccia sempre sulla faccia e mai sovrapposta all'etichetta; niente voce fuori campo.
4. Alla fine l'agente 1 deve funzionare: `python3 -I monta.py` (autocontrollo) e `cd remotion && npx tsc --noEmit -p .` devono passare. Se cambi monta.py aggiungi un assert per la logica nuova. Se vuoi provare un render, prima prendi il blocco `{{FARM}}/state/catena.lock` (mkdir; rmdir sempre alla fine) e tienilo corto (renderStill).
5. Scrivi `{{CARTELLA}}/modifiche.md`: per ogni modifica, quale sezione deve alzare, perché (le differenze che l'hanno motivata, in quante clip) e cosa hai cambiato (file). Se una modifica di un giro precedente ha abbassato una sezione, annullala e dillo.

Rispondi alla fine con una riga: quante modifiche e su quali sezioni.
