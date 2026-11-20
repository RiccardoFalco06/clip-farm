// Stile "speedy": stesse proprietà di Clip (stile classico) più quelle sue, tutte facoltative.
// La stessa scheda si monta in uno stile o nell'altro: monta.py sceglie la composizione dal campo "stile".
import React from 'react';
import {AbsoluteFill, Audio, Freeze, OffthreadVideo, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {LineSvg} from '../Caption';
import {ClipProps} from '../Clip';
import {Effetto, Lampi, Veli, VeloNero, filtroVideo, luceVideo, scalaZoom, stiraMosso} from './Effetti';
import {FirmaSpeedy, Grafica, Grafiche} from './Grafiche';
import {FUMETTO_916, FraseGlow, FraseS, GLOW_34, RigaFumetto, StileFumetto, StileGlow} from './Testo';

export type ClipSpeedyProps = ClipProps & {
  testo?: 'glow' | 'fumetto' | 'outline'; // stile dei sottotitoli (predefinito glow)
  frasi?: FraseS[]; // per glow: frasi che si costruiscono; se manca si usano i gruppi così come sono
  glow?: Partial<StileGlow>;
  fumetto?: Partial<StileFumetto>;
  effetti?: Effetto[];
  grafiche?: Grafica[];
  fps?: number; // 30 se manca (60 solo per i confronti con gli originali)
  sfondo?: string; // colore di fondo quando non c'è video (fermi di prova)
  luce?: {forza: number}; // luce che lampeggia sopra il video (assente = spenta)
  saturazione?: number; // 1 = colori pieni; la vibe seria la abbassa
  fermo?: number; // secondo da cui il video resta fermo (fondo del finale, ocTX 31,4-33,2)
  contrasto?: number; // correzione colore costante (1 = live grezza)
};

const POP = [0.6, 1.12, 0.97, 1]; // scala della parola a fumetto nei primi 4 fotogrammi a 30 fps

export const ClipSpeedy: React.FC<ClipSpeedyProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const testo = p.testo ?? 'glow';
  const effetti = p.effetti ?? [];
  const sg = {...GLOW_34, ...(p.glow ?? {})};
  const sf = {...FUMETTO_916, ...(p.fumetto ?? {})};
  const frasi: FraseS[] = p.frasi ?? p.gruppi.map((g) => ({start: g.start, end: g.end, righe: [g.words]}));
  const g = p.gruppi.find((x) => t >= x.start && t < x.end);
  const mosso = stiraMosso(effetti, t);
  const filtri = [
    filtroVideo(effetti, t),
    mosso ? `blur(${mosso.blur}px)` : '',
    p.luce ? `brightness(${luceVideo(p.luce.forza, Math.round(t * 30))})` : '',
    p.saturazione != null && p.saturazione !== 1 ? `saturate(${p.saturazione})` : '',
    p.contrasto != null && p.contrasto !== 1 ? `contrast(${p.contrasto})` : '',
  ];
  const fermoDa = p.fermo != null ? Math.round(p.fermo * fps) : null;
  const video = p.video ? <OffthreadVideo src={p.video} /> : null;
  return (
    <AbsoluteFill style={{backgroundColor: p.sfondo ?? '#000'}}>
      <AbsoluteFill style={{scale: String(scalaZoom(p.zoom, t)), filter: filtri.filter(Boolean).join(' ') || undefined, transform: mosso ? `scaleY(${mosso.scaleY})` : undefined}}>
        {fermoDa != null && frame >= fermoDa ? <Freeze frame={fermoDa}>{video}</Freeze> : video}
      </AbsoluteFill>
      <Veli effetti={effetti} t={t} />
      <Lampi lampi={p.lampi} t={t} />
      <Grafiche grafiche={p.grafiche ?? []} t={t} width={p.width} height={p.height} />
      <svg width={p.width} height={p.height} style={{position: 'absolute', inset: 0}}>
        {testo === 'glow' ? frasi.map((f, i) => (frasi.some((n) => n.start > f.start && t >= n.start && ((n.cx === f.cx && n.baseline === f.baseline) || (!n.corsivo && !f.corsivo))) ? null : <FraseGlow key={i} f={f} s={sg} t={t} id={`f${i}`} />)) : null}
        {testo === 'fumetto' && g ? <RigaFumetto parole={g.words} s={sf} scala={POP[Math.min(3, Math.floor((t - g.start) * 30))]} id="fu" /> : null}
        {testo === 'outline' && g ? <LineSvg l={{...p.riga, words: g.words}} i={0} /> : null}
      </svg>
      <VeloNero effetti={effetti} t={t} />
      {p.firma ? <FirmaSpeedy testo={p.firma} height={p.height} /> : null}
      {p.suoni.map((s, i) => (
        <Sequence key={i} from={Math.round(s.t * fps)}>
          <Audio src={s.file} volume={s.volume} />
        </Sequence>
      ))}
      {p.musica ? <Audio src={p.musica.file} volume={p.musica.volume} loop /> : null}
    </AbsoluteFill>
  );
};
