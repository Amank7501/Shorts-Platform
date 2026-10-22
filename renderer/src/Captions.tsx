import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import type { CaptionStyle, Word } from './types';

function chunk(words: Word[], perLine: number): Word[][] {
  const lines: Word[][] = [];
  for (let i = 0; i < words.length; i += perLine) lines.push(words.slice(i, i + perLine));
  return lines;
}

export const Captions: React.FC<{ words: Word[]; style: CaptionStyle }> = ({
  words,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  if (words.length === 0) return null;

  const lines = chunk(words, style.max_words_per_line);
  // The visible line is the last one that has started; it stays until the next begins.
  let lineIdx = -1;
  for (let i = 0; i < lines.length; i++) if (t >= lines[i][0].start - 0.05) lineIdx = i;
  if (lineIdx < 0) return null;
  const line = lines[lineIdx];

  // Highlight the word being spoken; it stays lit through the gap before the next word.
  let activeIdx = -1;
  line.forEach((w, i) => {
    if (t >= w.start) activeIdx = i;
  });

  const stroke = Math.max(2, Math.round(style.font_size / 12));
  return (
    <div
      style={{
        position: 'absolute',
        left: '5%',
        width: '90%',
        top: `${style.position_y * 100}%`,
        transform: 'translateY(-50%)',
        textAlign: 'center',
        fontFamily: `${style.font_family}, Arial, Helvetica, sans-serif`,
        fontSize: style.font_size,
        fontWeight: 800,
        lineHeight: 1.15,
        color: style.color,
        WebkitTextStroke: `${stroke}px ${style.outline_color}`,
        paintOrder: 'stroke fill',
        textShadow: '0 4px 12px rgba(0,0,0,0.45)',
      }}
    >
      {line.map((w, i) => {
        const active = style.mode === 'karaoke' && i === activeIdx;
        return (
          <span
            key={`${lineIdx}-${i}`}
            style={{
              display: 'inline-block',
              marginRight: '0.28em',
              color: active ? style.highlight_color : style.color,
              transform: active ? 'scale(1.08)' : 'none',
            }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
