// Props for one scene segment. Keys are storage keys; they are resolved against
// `baseUrl`, which is the render-time file server (or `/files` in the browser).
// Field names follow the video JSON (snake_case) so values pass straight through.

export type MotionPreset =
  | 'zoom_in'
  | 'zoom_out'
  | 'pan_left'
  | 'pan_right'
  | 'pan_up'
  | 'pan_down'
  | 'none';

export type Word = { text: string; start: number; end: number };

export type CaptionStyle = {
  mode: 'karaoke' | 'plain';
  font_family: string;
  font_size: number;
  color: string;
  highlight_color: string;
  outline_color: string;
  position_y: number;
  max_words_per_line: number;
};

export type SceneMedia = {
  kind: 'image' | 'video';
  key: string;
  trim_start_s: number;
  // Playable length of the clip after trimming, when known. Used to loop short clips.
  clip_length_s: number | null;
};

export type SceneProps = {
  baseUrl: string;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
  audioKey: string | null;
  media: SceneMedia | null;
  motion: { preset: MotionPreset; focal_point: { x: number; y: number } };
  words: Word[];
  captionStyle: CaptionStyle;
};

export const fileUrl = (baseUrl: string, key: string) =>
  `${baseUrl.replace(/\/$/, '')}/${key.split('/').map(encodeURIComponent).join('/')}`;
