import React from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Line, LineSvg, Word} from './Caption';

export type Gruppo = {start: number; end: number; words: Word[]};
export type ClipProps = {
  video: string; // URL del video già ritagliato nel layout finale
  width: number;
  height: number;
  durata: number; // secondi
  riga: Omit<Line, 'words'>; // stile e posizione dei sottotitoli (da presets.json)
  gruppi: Gruppo[];
  lampi: {t: number; colore: string}[];
  zoom: {t: number; durata: number; scala: number}[];
  suoni: {t: number; file: string; volume: number}[];
  musica?: {file: string; volume: number};
  firma?: string;
};

const POP = 3; // fotogrammi: la parola entra ingrandendosi, come nelle clip di riferimento
const LAMPO = 12; // fotogrammi di dissolvenza del lampo colorato (circa 0,4 s)

export const Clip: React.FC<ClipProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const g = p.gruppi.find((x) => t >= x.start && t < x.end);
  const pop = g ? interpolate(frame - g.start * fps, [0, POP], [0.82, 1], {extrapolateRight: 'clamp', extrapolateLeft: 'clamp'}) : 1;
  const z = p.zoom.find((x) => t >= x.t && t < x.t + x.durata);
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <AbsoluteFill style={{transform: `scale(${z ? z.scala : 1})`}}>
        <OffthreadVideo src={p.video} />
      </AbsoluteFill>
      {p.lampi.map((l, i) => {
        const o = interpolate(frame - l.t * fps, [0, LAMPO], [0.6, 0], {extrapolateRight: 'clamp', extrapolateLeft: 'clamp'});
        return frame >= l.t * fps && o > 0 ? <AbsoluteFill key={i} style={{backgroundColor: l.colore, opacity: o}} /> : null;
      })}
      {g ? (
        <svg width="100%" height="100%" style={{position: 'absolute', inset: 0}}>
          <g transform={`translate(${p.riga.cx} ${p.riga.baseline}) scale(${pop}) translate(${-p.riga.cx} ${-p.riga.baseline})`}>
            <LineSvg l={{...p.riga, words: g.words}} i={0} />
          </g>
        </svg>
      ) : null}
      {p.firma ? (
        <div style={{position: 'absolute', left: 0, right: 0, top: p.height * 0.83, textAlign: 'center', fontFamily: 'Figtree', fontWeight: 900, fontSize: 26, letterSpacing: 3, color: '#fff', opacity: 0.5}}>
          {p.firma.toUpperCase()}
        </div>
      ) : null}
      {p.suoni.map((s, i) => (
        <Sequence key={i} from={Math.round(s.t * fps)}>
          <Audio src={s.file} volume={s.volume} />
        </Sequence>
      ))}
      {p.musica ? <Audio src={p.musica.file} volume={p.musica.volume} loop /> : null}
    </AbsoluteFill>
  );
};
