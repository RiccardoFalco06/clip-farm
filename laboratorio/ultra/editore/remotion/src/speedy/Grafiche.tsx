// Grafiche dello stile "speedy": freccia curva con etichetta, cerchio rosso, emoji con alone, particelle, firma.
import React from 'react';
import {AbsoluteFill, Img, random} from 'remotion';
import {FONT_GLOW, Segui, spostamento} from './Testo';

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const EMOJI = '"Apple Color Emoji", "Noto Color Emoji", sans-serif';

export type Grafica =
  | {tipo: 'freccia'; t: number; durata: number; x: number; y: number; versoX?: 1 | -1; colore?: string; size?: number; segui?: Segui} // (x, y) = punta; segui = la punta va dietro alla faccia
  | {tipo: 'cerchio'; t: number; durata: number; x: number; y: number; r: number; colore?: string}
  | {tipo: 'emoji'; t: number; durata: number; x: number; y: number; emoji?: string; src?: string; size?: number; alone?: string} // (x, y) = centro; src = immagine (icona) al posto dell'emoji, alta size
  | {tipo: 'particelle'; t: number; durata: number};

// Freccia curva piena: parte in basso, sale e piega verso la punta in alto a destra (versoX=-1 la specchia). Bordo bianco e alone.
const Freccia: React.FC<{g: Extract<Grafica, {tipo: 'freccia'}>; k: number; i: number; t: number}> = ({g, k, i, t}) => {
  const s = (g.size ?? 150) / 150;
  const [dx, dy] = spostamento(g.segui, t);
  const c = g.colore ?? '#ff2e9a';
  return (
    <g transform={`translate(${g.x + dx} ${g.y + dy}) scale(${(g.versoX ?? 1) * s * (0.6 + 0.4 * k)} ${s * (0.6 + 0.4 * k)})`} opacity={k}>
      <defs>
        <filter id={`fr${i}`} x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="9" /></filter>
      </defs>
      {/* punta in (0,0): corpo spesso che sale da in basso a sinistra e piega verso destra; sotto l'alone, poi il bordo bianco, poi il colore */}
      {(['alone', 'bordo', 'colore'] as const).map((strato) => {
        const col = strato === 'bordo' ? '#fff' : c;
        const piu = strato === 'colore' ? 0 : strato === 'bordo' ? 12 : 16;
        return (
          <g key={strato} {...(strato === 'alone' ? {filter: `url(#fr${i})`, opacity: 0.85} : {})}>
            <path d="M -137.5 213 C -147.5 103 -107.5 43 -57.5 23" fill="none" stroke={col} strokeWidth={44 + piu} strokeLinecap="round" />
            <polygon points="0,0 -41.2,63.8 -73.8,-17.8" fill={col} stroke={col} strokeWidth={piu} strokeLinejoin="round" />
          </g>
        );
      })}
    </g>
  );
};

const Cerchio: React.FC<{g: Extract<Grafica, {tipo: 'cerchio'}>; k: number; i: number}> = ({g, k, i}) => {
  const c = g.colore ?? '#ff1414';
  const giro = 2 * Math.PI * g.r;
  return (
    <g opacity={Math.min(1, k * 3)}>
      <defs>
        <filter id={`ce${i}`} x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8" /></filter>
      </defs>
      {[true, false].map((alone) => (
        <circle key={String(alone)} cx={g.x} cy={g.y} r={g.r} fill="none" stroke={c} strokeWidth={alone ? 14 : 9} strokeLinecap="round"
          strokeDasharray={giro} strokeDashoffset={giro * (1 - k)} transform={`rotate(-90 ${g.x} ${g.y})`} {...(alone ? {filter: `url(#ce${i})`, opacity: 0.9} : {})} />
      ))}
    </g>
  );
};

export const Grafiche: React.FC<{grafiche: Grafica[]; t: number; width: number; height: number}> = ({grafiche, t, width, height}) => {
  const vive = grafiche.map((g, i) => ({g, i})).filter(({g}) => t >= g.t && t < g.t + g.durata);
  if (!vive.length) return null;
  return (
    <AbsoluteFill>
      {vive.map(({g, i}) => {
        if (g.tipo !== 'particelle') return null;
        // trattini bianchi che cadono in diagonale, come neve mossa: il fondo dei finali (C4i 30.0-31.9, 5Jw 12.6-13.9, FUI, IUm)
        return (
          <AbsoluteFill key={i}>
            {Array.from({length: 40}, (_, n) => {
              const v = 250 + 350 * random(`pv${n}`); // px al secondo
              const y = (random(`py${n}`) * height + v * (t - g.t)) % height;
              const x = (random(`px${n}`) * width - 0.35 * v * (t - g.t) + width * 4) % width;
              const l = 6 + 16 * random(`pr${n}`);
              return <div key={n} style={{position: 'absolute', left: x, top: y, width: 3, height: l, borderRadius: 2, background: '#fff', rotate: '19deg', opacity: 0.3 + 0.5 * random(`po${n}`), filter: 'blur(0.7px)'}} />;
            })}
          </AbsoluteFill>
        );
      })}
      <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
        {vive.map(({g, i}) => {
          const entra = clamp01((t - g.t) / 0.15);
          const k = Math.min(1 - (1 - entra) ** 3, clamp01((g.t + g.durata - t) / 0.28));
          if (g.tipo === 'freccia') return <Freccia key={i} g={g} k={k} i={i} t={t} />;
          if (g.tipo === 'cerchio') return <Cerchio key={i} g={g} k={clamp01((t - g.t) / 0.25)} i={i} />;
          return null;
        })}
      </svg>
      {vive.map(({g, i}) => {
        if (g.tipo !== 'emoji') return null;
        const size = g.size ?? 110;
        const entra = clamp01((t - g.t) / 0.18);
        const k = Math.min(1 - (1 - entra) ** 3, clamp01((g.t + g.durata - t) / 0.28));
        const base: React.CSSProperties = {position: 'absolute', left: g.x, top: g.y, translate: '-50% -50%', fontFamily: EMOJI, fontSize: size, lineHeight: 1};
        // icona da immagine: stessa entrata, alone fatto con la stessa immagine sfocata
        const segno = (sz: number) => (g.src ? <Img src={g.src} style={{height: sz, display: 'block'}} /> : g.emoji);
        return (
          <React.Fragment key={i}>
            {/* fantasma: copia trasparente circa 3 volte più grande che si restringe sull'emoji e svanisce in 0,6 s (FUI 31.13, C4i 29.83, 5Jw 12.56, C1t 41.13) */}
            {t - g.t < 0.6 ? <div style={{...base, scale: String(1 + 2.2 * (1 - clamp01((t - g.t) / 0.6)) ** 2), filter: `blur(${size * 0.04}px)`, opacity: 0.45 * (1 - clamp01((t - g.t) / 0.6))}}>{segno(size)}</div> : null}
            {/* alone morbido fisso attorno all'emoji */}
            <div style={{...base, fontSize: size * 1.7, filter: `blur(${size * 0.22}px)`, opacity: 0.55 * k}}>{segno(size * 1.7)}</div>
            {g.alone ? <div style={{...base, width: size * 1.5, height: size * 1.5, borderRadius: '50%', background: g.alone, filter: `blur(${size * 0.35}px)`, opacity: 0.55 * k}} /> : null}
            <div style={{...base, scale: String(0.5 + 0.5 * k), opacity: k}}>{segno(size)}</div>
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

// Firma piccola in basso al centro, bianca con ombra: resta sopra a tutto, anche alla dissolvenza finale.
export const FirmaSpeedy: React.FC<{testo: string; height: number}> = ({testo, height}) => (
  <div style={{position: 'absolute', left: 0, right: 0, top: height * 0.9, textAlign: 'center', fontFamily: FONT_GLOW, fontWeight: 900, fontSize: 20, letterSpacing: 1.2, color: '#fff', opacity: 0.85, textShadow: '0 2px 4px rgba(0,0,0,0.9)'}}>
    {testo.toUpperCase()}
  </div>
);
