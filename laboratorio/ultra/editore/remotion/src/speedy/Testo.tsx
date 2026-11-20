// Sottotitoli dello stile "speedy". Tre stili di testo:
//  - glow:    frase che si costruisce parola per parola, alone colorato, spaziatura che si allarga piano (Shorts 2026)
//  - fumetto: una parola (o poche) alla volta, font da fumetto con contorno nero e ombra (Shorts 2024 con riempitivo)
//  - outline: è lo stile classico (Bebas con contorno): lo disegna LineSvg di ../Caption, qui non si tocca
import React from 'react';
import {loadFont as figtree} from '@remotion/google-fonts/Figtree';
import {loadFont as luckiest} from '@remotion/google-fonts/LuckiestGuy';

export const FONT_GLOW = figtree('normal', {weights: ['900'], subsets: ['latin']}).fontFamily;
figtree('italic', {weights: ['900'], subsets: ['latin']});
export const FONT_FUMETTO = luckiest('normal', {weights: ['400'], subsets: ['latin']}).fontFamily;

export type ParolaS = {
  text: string;
  start?: number; // secondo in cui la parola comincia ad accendersi (assente = subito con la frase)
  fill?: string;
  fill2?: string; // sfumatura verticale fill -> fill2
  glow?: string;
  edge?: string; // bordino colorato sottile (bianco con bordo rosso)
  edgeW?: number;
};
export type FraseS = {
  start: number;
  end: number;
  righe: ParolaS[][]; // 1 o 2 righe
  corsivo?: boolean; // narrazione tra asterischi: *LAUGHING*
  cx?: number; // posizione propria (etichette, narrazione in alto); assente = quella dello stile
  baseline?: number;
  size?: number;
  scrivi?: number; // lettere al secondo: la scritta si scrive lettera per lettera (5Jw 11,1-11,9: circa 20 al secondo)
  segui?: Segui; // etichetta della freccia: si sposta con la faccia indicata
};
// [secondo, dx, dy]: spostamento della faccia seguita rispetto al primo fotogramma (monta.py, piazza_freccia), lineare fra i punti
export type Segui = [number, number, number][];
export const spostamento = (segui: Segui | undefined, t: number): [number, number] => {
  if (!segui?.length) return [0, 0];
  const j = segui.findIndex((p) => p[0] > t);
  if (j <= 0) return j === 0 ? [segui[0][1], segui[0][2]] : [segui[segui.length - 1][1], segui[segui.length - 1][2]];
  const [a, b] = [segui[j - 1], segui[j]];
  const u = (t - a[0]) / (b[0] - a[0]);
  return [a[1] + u * (b[1] - a[1]), a[2] + u * (b[2] - a[2])];
};
export type StileGlow = {
  font?: string; // famiglia (predefinita FONT_GLOW)
  cx: number;
  baseline: number; // linea di base della prima riga
  size: number;
  tracking: number; // em, all'inizio della frase
  trackingVel: number; // em al secondo: la spaziatura si allarga finché la frase resta a schermo
  scaleX: number;
  interlinea: number;
  glowBlur: number;
  glowAlpha: number;
  glow2Blur: number; // alone largo e tenue
  glow2Alpha: number;
  shadow: [number, number, number, number]; // dx, dy, blur, alpha
  fadeParola: number; // secondi: accensione lineare di ogni parola
  fadeUscita: number; // secondi: la frase vecchia sfuma mentre entra la nuova
};

// Misure prese su Shorts 1080x1440 (vedi laboratorio/libreria.json per i confronti)
export const GLOW_34: StileGlow = {
  cx: 540, baseline: 711, size: 68, tracking: 0.14, trackingVel: 0.0218, scaleX: 0.92, interlinea: 67,
  glowBlur: 4, glowAlpha: 0.5, glow2Blur: 26, glow2Alpha: 0.7, shadow: [3, 5, 3, 0.9], fadeParola: 0.2, fadeUscita: 0.28,
};

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

export const FraseGlow: React.FC<{f: FraseS; s: StileGlow; t: number; id: string}> = ({f, s, t, id}) => {
  const size = f.size ?? s.size;
  const k = size / s.size;
  const esce = 1 - clamp01((t - f.end) / s.fadeUscita);
  if (t < f.start || esce <= 0) return null;
  // le righe lunghe partono più strette (misurato: 0,14 em fino a 14 caratteri, 0,093 em a 19)
  const lunga = Math.max(...f.righe.map((r) => r.map((w) => w.text).join(' ').length));
  const ls = (Math.max(0.07, s.tracking - 0.0094 * Math.max(0, lunga - 14)) + s.trackingVel * (t - f.start)) * size;
  const cx = f.cx ?? s.cx;
  return (
    <g opacity={esce} transform={`translate(${spostamento(f.segui, t).join(' ')}) scale(${s.scaleX},1)`}>
      {f.righe.map((riga, r) => {
        const y = (f.baseline ?? s.baseline) + r * s.interlinea * k;
        const common = {
          fontFamily: s.font ?? FONT_GLOW, fontSize: size, fontWeight: 900, fontStyle: f.corsivo ? ('italic' as const) : ('normal' as const),
          letterSpacing: ls, textAnchor: 'middle' as const, x: cx / s.scaleX + ls / 2, y,
        };
        const op = (w: ParolaS) => clamp01((t - (w.start ?? f.start)) / s.fadeParola);
        const visibili = f.scrivi ? Math.floor((t - f.start) * f.scrivi) + 1 : Infinity;
        const spans = (colore: (w: ParolaS, i: number) => string, extra?: (w: ParolaS) => object) => {
          let usati = 0;
          return riga.map((w, i) => {
            const pieno = (i ? ' ' : '') + w.text;
            const pezzo = pieno.slice(0, Math.max(0, visibili - usati));
            usati += pieno.length;
            return (
              <tspan key={i} fill={colore(w, i)} fillOpacity={op(w)} strokeOpacity={op(w)} {...(extra ? extra(w) : {})}>
                {pezzo}
              </tspan>
            );
          });
        };
        const gid = `${id}_${r}`;
        return (
          <g key={r}>
            <defs>
              {riga.map((w, i) =>
                w.fill2 ? (
                  <linearGradient key={i} id={`gr${gid}_${i}`} x1="0" y1={y - size * 0.7} x2="0" y2={y} gradientUnits="userSpaceOnUse">
                    <stop offset="0" stopColor={w.fill} />
                    <stop offset="1" stopColor={w.fill2} />
                  </linearGradient>
                ) : null,
              )}
              <filter id={`sh${gid}`} x="-20%" y="-80%" width="140%" height="260%"><feGaussianBlur stdDeviation={s.shadow[2] * k} /></filter>
              <filter id={`g1${gid}`} x="-20%" y="-100%" width="140%" height="300%"><feGaussianBlur stdDeviation={s.glowBlur * k} /></filter>
              <filter id={`g2${gid}`} x="-30%" y="-200%" width="160%" height="500%"><feGaussianBlur stdDeviation={s.glow2Blur * k} /></filter>
            </defs>
            <text {...common} x={common.x + s.shadow[0] * k} y={y + s.shadow[1] * k} filter={`url(#sh${gid})`} opacity={s.shadow[3]}>{spans(() => '#000')}</text>
            <text {...common} filter={`url(#g2${gid})`} opacity={s.glow2Alpha}>{spans((w) => w.glow ?? w.fill ?? '#fff')}</text>
            <text {...common} filter={`url(#g1${gid})`} opacity={s.glowAlpha}>{spans((w) => w.glow ?? w.fill ?? '#fff')}</text>
            <text {...common}>
              {spans(
                (w, i) => (w.fill2 ? `url(#gr${gid}_${i})` : w.fill ?? '#fff'),
                // 12/11, agente sottotitoli: bianco su felpa o muro chiari illeggibile; un contorno scuro sottile sotto il riempimento
                (w) => (w.edge ? {stroke: w.edge, strokeWidth: (w.edgeW ?? 2) * 2, paintOrder: 'stroke'} : {stroke: 'rgba(0,0,0,0.6)', strokeWidth: 5 * k, strokeLinejoin: 'round', paintOrder: 'stroke'}),
              )}
            </text>
          </g>
        );
      })}
    </g>
  );
};

// Fumetto: contorno nero spesso, ombra morbida in basso, entrata a scatto (scala che supera e torna)
export type StileFumetto = {cx: number; baseline: number; size: number; stroke: number; shadow: [number, number, number, number]; tracking: number};
export const FUMETTO_916: StileFumetto = {cx: 540, baseline: 1090, size: 96, stroke: 9, shadow: [0, 8, 6, 0.6], tracking: 0};

export const RigaFumetto: React.FC<{parole: ParolaS[]; s: StileFumetto; scala: number; id: string}> = ({parole, s, scala, id}) => {
  const common = {fontFamily: FONT_FUMETTO, fontSize: s.size, letterSpacing: s.tracking * s.size, textAnchor: 'middle' as const, x: s.cx, y: s.baseline};
  const testo = parole.map((w) => w.text).join(' ');
  return (
    <g transform={`translate(${s.cx} ${s.baseline - s.size * 0.35}) scale(${scala}) translate(${-s.cx} ${-(s.baseline - s.size * 0.35)})`}>
      <defs>
        <filter id={`fs${id}`} x="-20%" y="-60%" width="140%" height="240%"><feGaussianBlur stdDeviation={s.shadow[2]} /></filter>
      </defs>
      <text {...common} x={s.cx + s.shadow[0]} y={s.baseline + s.shadow[1]} stroke="#000" strokeWidth={s.stroke * 2} strokeLinejoin="round" fill="#000" filter={`url(#fs${id})`} opacity={s.shadow[3]}>{testo}</text>
      <text {...common} stroke="#000" strokeWidth={s.stroke * 2} strokeLinejoin="round" fill="#000">{testo}</text>
      <text {...common}>
        {parole.map((w, i) => (
          <tspan key={i} fill={w.fill ?? '#fff'}>{(i ? ' ' : '') + w.text}</tspan>
        ))}
      </text>
    </g>
  );
};
