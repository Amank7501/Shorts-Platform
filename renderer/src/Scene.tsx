import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Loop,
  OffthreadVideo,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { Captions } from './Captions';
import { motionStyle } from './motion';
import { fileUrl, type SceneProps } from './types';

const Media: React.FC<{ props: SceneProps }> = ({ props }) => {
  const { media, baseUrl, fps, durationInFrames } = props;
  if (!media) return null;
  const src = fileUrl(baseUrl, media.key);
  const fill: React.CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  };
  if (media.kind === 'image') return <Img src={src} style={fill} />;

  const trimBefore = Math.round(media.trim_start_s * fps);
  const video = <OffthreadVideo src={src} muted trimBefore={trimBefore} style={fill} />;
  // A clip shorter than the scene loops. A longer one simply plays from its start point.
  if (media.clip_length_s) {
    const loopFrames = Math.max(1, Math.round(media.clip_length_s * fps));
    if (loopFrames < durationInFrames) {
      return <Loop durationInFrames={loopFrames}>{video}</Loop>;
    }
  }
  return video;
};

export const Scene: React.FC<SceneProps> = (props) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const progress = durationInFrames > 1 ? frame / (durationInFrames - 1) : 0;
  const motion = motionStyle(
    props.motion.preset,
    progress,
    props.motion.focal_point,
    width,
    height,
  );
  return (
    <AbsoluteFill style={{ backgroundColor: '#000', overflow: 'hidden' }}>
      <AbsoluteFill style={motion}>
        <Media props={props} />
      </AbsoluteFill>
      <Captions words={props.words} style={props.captionStyle} />
      {props.audioKey ? <Audio src={fileUrl(props.baseUrl, props.audioKey)} /> : null}
    </AbsoluteFill>
  );
};
