import { Easing, interpolate } from 'remotion';
import type { MotionPreset } from './types';

// Ken Burns: a slow transform over the scene. No AI involved.
const ZOOM = 0.18; // pans and zooms run on a 1.18x image, so edges never show
const PAN = 0.05; // fraction of the frame travelled by a pan

const ease = Easing.inOut(Easing.ease);

export function motionStyle(
  preset: MotionPreset,
  progress: number,
  focal: { x: number; y: number },
  width: number,
  height: number,
): { transform: string; transformOrigin: string } {
  const p = Math.min(1, Math.max(0, progress));
  const at = (from: number, to: number) =>
    interpolate(p, [0, 1], [from, to], { easing: ease });
  let scale = 1;
  let tx = 0;
  let ty = 0;
  let origin = `${focal.x * 100}% ${focal.y * 100}%`;
  switch (preset) {
    case 'zoom_in':
      scale = at(1, 1 + ZOOM);
      break;
    case 'zoom_out':
      scale = at(1 + ZOOM, 1);
      break;
    case 'pan_left':
      scale = 1 + ZOOM;
      tx = at(PAN * width, -PAN * width);
      origin = '50% 50%';
      break;
    case 'pan_right':
      scale = 1 + ZOOM;
      tx = at(-PAN * width, PAN * width);
      origin = '50% 50%';
      break;
    case 'pan_up':
      scale = 1 + ZOOM;
      ty = at(PAN * height, -PAN * height);
      origin = '50% 50%';
      break;
    case 'pan_down':
      scale = 1 + ZOOM;
      ty = at(-PAN * height, PAN * height);
      origin = '50% 50%';
      break;
    case 'none':
      break;
  }
  return {
    transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
    transformOrigin: origin,
  };
}
