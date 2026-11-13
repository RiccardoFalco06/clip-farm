import React from 'react';
import {AbsoluteFill} from 'remotion';
import {loadFont as bebas} from '@remotion/google-fonts/BebasNeue';
import {loadFont as figtree} from '@remotion/google-fonts/Figtree';

const FONTS = {
  outline: bebas('normal', {weights: ['400'], subsets: ['latin']}).fontFamily,
  glow: figtree('normal', {weights: ['900'], subsets: ['latin']}).fontFamily,
};

export type Word = {text: string; fill?: string; fill2?: string; glow?: string; edge?: string; edgeW?: number};
export type Line = {
  style: 'outline' | 'glow';
  words: Word[];
  cx: number; // centro orizzontale in px
  baseline: number; // linea di base in px
  size: number;
  tracking?: number; // em
  scaleX?: number;
  stroke?: number; // px, spessore del contorno (stile outline)
  join?: 'round' | 'miter' | 'bevel';
  glowBlur?: number;
  glowAlpha?: number;
  shadow?: [number, number, number, number]; // dx, dy, blur, alpha
  wordGap?: number; // em
};
export type CaptionProps = {bg: string; lines: Line[]};

export const LineSvg: React.FC<{l: Line; i: number}> = ({l, i}) => {
  const ls = (l.tracking ?? 0) * l.size;
  const sx = l.scaleX ?? 1;
  const common = {
    fontFamily: FONTS[l.style],
    fontSize: l.size,
    letterSpacing: ls,
    textAnchor: 'middle' as const,
    x: l.cx / sx + ls / 2,
    y: l.baseline,
    style: {wordSpacing: (l.wordGap ?? 0) * l.size},
  };
  const spans = (mode: 'fill' | 'flat', flat?: string) =>
    l.words.map((w, k) => (
      <tspan
        key={k}
        fill={mode === 'flat' ? flat ?? w.glow ?? w.fill ?? '#fff' : w.fill2 ? `url(#g${i}_${k})` : w.fill ?? '#fff'}
        // bordino colorato sottile attorno alla parola (es. bianco con bordo rosso)
        {...(mode === 'fill' && w.edge ? {stroke: w.edge, strokeWidth: (w.edgeW ?? 2) * 2, paintOrder: 'stroke'} : {})}
      >
        {(k ? ' ' : '') + w.text}
      </tspan>
    ));
  return (
    <g transform={`scale(${sx},1)`}>
      <defs>
        {l.words.map((w, k) =>
          w.fill2 ? (
            <linearGradient key={k} id={`g${i}_${k}`} x1="0" y1={l.baseline - l.size * 0.7} x2="0" y2={l.baseline} gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor={w.fill} />
              <stop offset="1" stopColor={w.fill2} />
            </linearGradient>
          ) : null,
        )}
        <filter id={`sh${i}`} x="-20%" y="-60%" width="140%" height="220%">
          <feGaussianBlur stdDeviation={l.shadow?.[2] ?? 0} />
        </filter>
        <filter id={`gl${i}`} x="-20%" y="-80%" width="140%" height="260%">
          <feGaussianBlur stdDeviation={l.glowBlur ?? 0} />
        </filter>
      </defs>
      {l.shadow ? (
        <text {...common} x={common.x + l.shadow[0]} y={common.y + l.shadow[1]} filter={`url(#sh${i})`} opacity={l.shadow[3]}>
          {spans('flat', '#000')}
        </text>
      ) : null}
      {l.glowBlur ? (
        <text {...common} filter={`url(#gl${i})`} opacity={l.glowAlpha ?? 1}>
          {spans('flat')}
        </text>
      ) : null}
      {l.stroke ? (
        <text {...common} stroke="#000" strokeWidth={l.stroke * 2} strokeLinejoin={l.join ?? 'round'} fill="#000">
          {l.words.map((w) => w.text).join(' ')}
        </text>
      ) : null}
      <text {...common}>{spans('fill')}</text>
    </g>
  );
};

export const Caption: React.FC<CaptionProps> = ({bg, lines}) => (
  <AbsoluteFill style={{backgroundColor: bg}}>
    <svg width="100%" height="100%" style={{position: 'absolute', inset: 0}}>
      {lines.map((l, i) => (
        <LineSvg key={i} l={l} i={i} />
      ))}
    </svg>
  </AbsoluteFill>
);
