import React from 'react';
import {Composition} from 'remotion';
import {Caption, CaptionProps} from './Caption';
import {Clip, ClipProps} from './Clip';

const base: CaptionProps = {bg: 'transparent', lines: []};
const clip: ClipProps = {video: '', width: 1080, height: 1920, durata: 1, riga: {style: 'outline', cx: 540, baseline: 1058, size: 200}, gruppi: [], lampi: [], zoom: [], suoni: []};
export const Root: React.FC = () => (
  <>
    <Composition id="Cap916" component={Caption} width={1080} height={1920} fps={30} durationInFrames={1} defaultProps={base} />
    <Composition id="Cap34" component={Caption} width={1080} height={1440} fps={30} durationInFrames={1} defaultProps={base} />
    <Composition
      id="Clip"
      component={Clip}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={30}
      defaultProps={clip}
      calculateMetadata={({props}) => ({width: props.width, height: props.height, durationInFrames: Math.max(1, Math.round(props.durata * 30))})}
    />
  </>
);
