Leggi l'immagine `{{IMMAGINE}}`: è un mosaico di fotogrammi presi da una live di {{STREAMER}}, uno per ogni pezzo di una clip (etichetta P1, P2, … in alto a sinistra). In ogni fotogramma le facce trovate sono dentro un riquadro giallo con un numero.

La clip verrà ritagliata in verticale e in ogni pezzo deve stare al centro **la persona che sta parlando**. Ecco cosa si dice in ogni pezzo (trascrizione automatica, può mescolare due voci):

{{PEZZI}}

Per ogni pezzo decidi chi dice quelle parole, usando il senso del dialogo (chi fa la domanda e chi risponde, chi tiene il microfono per intervistare, a chi si rivolgono gli altri, chi ha la bocca aperta) oltre all'immagine. Se nel pezzo parlano in due, scegli chi dice la parte più importante (la risposta, la battuta). Metti `null` se chi parla non è tra le facce numerate (fuori campo, streamer in webcam non inquadrato) o se non riesci a capirlo.

Rispondi SOLO con un array JSON di {{N}} elementi, uno per pezzo nello stesso ordine, col numero della faccia o null. Esempio: `[2, 2, 1, null]`
