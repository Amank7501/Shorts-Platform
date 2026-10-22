"""Join scene segments into one MP4 with FFmpeg.

Every segment comes out of the same encoder settings, so the join is a stream copy:
no re-encode, hard cuts only. Background music, when present, is mixed in a second
pass that copies the video and re-encodes just the audio.
"""

import tempfile
from pathlib import Path

from ..schemas.video import Music
from .tools import run_ffmpeg


def _concat_list(paths: list[Path]) -> Path:
    lines = []
    for p in paths:
        escaped = p.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    f.write("\n".join(lines))
    f.close()
    return Path(f.name)


def join_segments(
    segments: list[Path],
    dst: Path,
    *,
    music: Music | None = None,
    music_path: Path | None = None,
    total_duration_s: float | None = None,
) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part.mp4")
    listing = _concat_list(segments)
    try:
        if music is None:
            run_ffmpeg([
                "-f", "concat", "-safe", "0", "-i", str(listing),
                "-c", "copy", "-movflags", "+faststart", str(tmp),
            ])
        else:
            if music_path is None:
                raise ValueError("music_path is required when music is set")
            vol = f"volume={music.volume}"
            if music.duck_under_voice:
                # The voice sidechains a compressor on the music, so music dips while
                # someone is speaking and returns in the gaps.
                graph = (
                    f"[1:a]{vol}[m];[0:a]asplit=2[voice][sc];"
                    "[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[ducked];"
                    "[voice][ducked]amix=inputs=2:duration=first:normalize=0[a]"
                )
            else:
                graph = f"[1:a]{vol}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]"
            args = [
                "-f", "concat", "-safe", "0", "-i", str(listing),
                "-stream_loop", "-1", "-i", str(music_path),
                "-filter_complex", graph,
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            ]
            if total_duration_s:
                args += ["-t", f"{total_duration_s:.3f}"]
            run_ffmpeg([*args, "-movflags", "+faststart", str(tmp)])
        tmp.replace(dst)
    finally:
        listing.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
