// Effetti dello stile "speedy". Ogni funzione prende il tempo in secondi e restituisce stile o elementi: niente stato.
import React from 'react';
import {AbsoluteFill, random} from 'remotion';

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const coseno = (x: number) => (1 + Math.cos(Math.PI * clamp01(x))) / 2; // 1 -> 0 morbido

export type Lampo = {t: number; colore: string; durata?: number; forza?: number};
// Lampo colorato: parte al massimo in un fotogramma, cala con curva a coseno; fusione "scolora" (i neri prendono il colore, i bianchi restano).
export const LAMPO = {durata: 0.45, forza: 0.77}; // misurati: 161 lampi in 27 Shorts, durata mediana 0,40-0,43 s
export const Lampi: React.FC<{lampi: Lampo[]; t: number}> = ({lampi, t}) => (
  <>
    {lampi.map((l, i) => {
      const o = t >= l.t ? (l.forza ?? LAMPO.forza) * coseno((t - l.t) / (l.durata ?? LAMPO.durata)) : 0;
      return o > 0.003 ? <AbsoluteFill key={i} style={{backgroundColor: l.colore, opacity: o, mixBlendMode: 'screen'}} /> : null;
    })}
  </>
);

export type Zoom = {t: number; durata: number; scala: number; cx?: number; cy?: number};
// Zoom sulla reazione: entra in 0,12 s (ease-out), resta, esce in 0,2 s.
export const scalaZoom = (zoom: Zoom[], t: number) => {
  let s = 1;
  for (const z of zoom) {
    const dentro = clamp01((t - z.t) / 0.12);
    const fuori = clamp01((z.t + z.durata - t) / 0.2);
    const k = Math.min(1 - (1 - dentro) ** 3, fuori);
    if (t >= z.t && t < z.t + z.durata) s = Math.max(s, 1 + (z.scala - 1) * k);
  }
  return s;
};

export type Effetto =
  | {tipo: 'bn'; t: number; durata: number; scuro?: number; sfoca?: number} // momento in bianco e nero (fermo, sottolineatura, finale)
  | {tipo: 'scuro'; t: number; durata: number; forza?: number} // sfondo abbassato dietro una scritta importante
  | {tipo: 'mosso'; t: number; durata?: number} // stacco con lampo bianco e mosso verticale
  | {tipo: 'nero'; t: number; durata?: number} // dissolvenza a nero finale (la firma resta sopra)
  | {tipo: 'stacco'; t: number; durata?: number}; // righe bianche orizzontali per 0,1 s, poi B/N sfocato che torna a colori (IUm 2.63, C4i 2.80)

// filtro CSS da mettere sul video per gli effetti attivi al tempo t
export const filtroVideo = (effetti: Effetto[], t: number) => {
  const f: string[] = [];
  for (const e of effetti) {
    if (e.tipo === 'bn' && t >= e.t && t < e.t + e.durata) {
      const k = clamp01((t - e.t) / 0.1);
      f.push(`grayscale(${k}) brightness(${1 - (e.scuro ?? 0.25) * k}) contrast(1.15)` + (e.sfoca ? ` blur(${e.sfoca * k}px)` : ''));
    }
    if (e.tipo === 'stacco' && t >= e.t && t < e.t + (e.durata ?? 0.45)) {
      const r = 1 - clamp01((t - e.t - 0.07) / ((e.durata ?? 0.45) - 0.07)); // 1 = B/N pieno, 0 = colore
      f.push(`grayscale(${r}) blur(${10 * r}px) brightness(${1 + 0.25 * r})`);
    }
    if (e.tipo === 'mosso') {
      const d = e.durata ?? 0.25;
      const k = t >= e.t ? 1 - clamp01((t - e.t) / d) : 0;
      if (k > 0) f.push(`brightness(${1 + 2.5 * k * k})`);
    }
  }
  return f.join(' ') || undefined;
};

// Luce che lampeggia sopra la clip: guadagno di luminosità di tutto il video che cambia a caso ogni 1-4 fotogrammi (a 30 fps).
// Misurata fotogramma per fotogramma su 10 Shorts 2025-2026 (strumenti/luce3.py): 10-14 lampeggi al secondo, chiari e scuri
// in pari numero, durata 1/2/3/4 fotogrammi nel 40/33/18/9 per cento dei casi, 3-7% di luminosità. Velatura, non particelle.
// Sta solo sul video: sottotitoli, grafiche e firma restano fermi.
const DURATE_LUCE = [0.4, 0.73, 0.91, 1]; // probabilità cumulata di durare 1, 2, 3, 4 fotogrammi
export const luceVideo = (forza: number, frame: number) => {
  let f = 0;
  for (let k = 0; ; k++) {
    const u = random(`lu-l-${k}`);
    const lungo = 1 + DURATE_LUCE.findIndex((p) => u < p);
    if (frame < f + lungo) return 1 + forza * (2 * random(`lu-v-${k}`) - 1);
    f += lungo;
  }
};

// stiramento verticale del video durante il "mosso" (il vero mosso direzionale non esiste in CSS: si allunga e si sfoca)
export const stiraMosso = (effetti: Effetto[], t: number) => {
  for (const e of effetti) {
    if (e.tipo !== 'mosso') continue;
    const k = t >= e.t ? 1 - clamp01((t - e.t) / (e.durata ?? 0.25)) : 0;
    if (k > 0) return {scaleY: 1 + 5 * k * k, blur: 14 * k};
  }
  return null;
};

export const Veli: React.FC<{effetti: Effetto[]; t: number}> = ({effetti, t}) => (
  <>
    {effetti.map((e, i) => {
      if (e.tipo === 'scuro' && t >= e.t && t < e.t + e.durata) {
        const k = Math.min(clamp01((t - e.t) / 0.15), clamp01((e.t + e.durata - t) / 0.15));
        return <AbsoluteFill key={i} style={{backgroundColor: '#000', opacity: (e.forza ?? 0.45) * k}} />;
      }
      if (e.tipo === 'stacco' && t >= e.t && t < e.t + 0.1) {
        // righe bianche sottili a caso, diverse a ogni fotogramma
        const f = Math.floor(t * 30);
        return (
          <AbsoluteFill key={i}>
            {Array.from({length: 7}, (_, n) => (
              <div key={n} style={{position: 'absolute', left: 0, right: 0, top: `${random(`sy${f}-${n}`) * 100}%`, height: 2 + 10 * random(`sh${f}-${n}`), background: '#fff', opacity: 0.6 + 0.4 * random(`so${f}-${n}`)}} />
            ))}
          </AbsoluteFill>
        );
      }
      return null;
    })}
  </>
);

export const VeloNero: React.FC<{effetti: Effetto[]; t: number}> = ({effetti, t}) => (
  <>
    {effetti.map((e, i) => (e.tipo === 'nero' && t >= e.t ? <AbsoluteFill key={i} style={{backgroundColor: '#000', opacity: clamp01((t - e.t) / (e.durata ?? 0.5))}} /> : null))}
  </>
);
