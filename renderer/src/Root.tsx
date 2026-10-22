import React from 'react';
import { Composition } from 'remotion';
import { Scene } from './Scene';
import type { SceneProps } from './types';

const defaultProps: SceneProps = {
  baseUrl: '',
  width: 1080,
  height: 1920,
  fps: 30,
  durationInFrames: 90,
  audioKey: null,
  media: null,
  motion: { preset: 'zoom_in', focal_point: { x: 0.5, y: 0.4 } },
  words: [
    { text: 'Sample', start: 0.2, end: 0.8 },
    { text: 'caption', start: 0.9, end: 1.6 },
  ],
  captionStyle: {
    mode: 'karaoke',
    font_family: 'Inter',
    font_size: 72,
    color: '#FFFFFF',
    highlight_color: '#FFD400',
    outline_color: '#000000',
    position_y: 0.68,
    max_words_per_line: 4,
  },
};

export const Root: React.FC = () => (
  <Composition
    id="Scene"
    component={Scene}
    defaultProps={defaultProps}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={90}
    calculateMetadata={({ props }) => ({
      width: props.width,
      height: props.height,
      fps: props.fps,
      durationInFrames: props.durationInFrames,
    })}
  />
);
