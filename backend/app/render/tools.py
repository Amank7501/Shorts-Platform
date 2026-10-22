"""Running FFmpeg and ffprobe, with errors that say what failed."""

import json
import subprocess
from pathlib import Path

from ..config import settings


class RenderError(RuntimeError):
    pass


def _tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def run_ffmpeg(args: list[str]) -> None:
    cmd = [settings.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RenderError(
            f"ffmpeg not found ({settings.ffmpeg_bin!r}). Install FFmpeg and put it on PATH."
        ) from exc
    if proc.returncode != 0:
        raise RenderError(f"ffmpeg failed:\n{_tail(proc.stderr)}\ncommand: {' '.join(cmd)}")


def probe(path: Path) -> dict:
    """Return duration (s), width, height and fps of the first video stream, if any."""
    cmd = [
        settings.ffprobe_bin, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RenderError(
            f"ffprobe not found ({settings.ffprobe_bin!r}). Install FFmpeg and put it on PATH."
        ) from exc
    if proc.returncode != 0:
        raise RenderError(f"ffprobe failed on {path}:\n{_tail(proc.stderr)}")
    data = json.loads(proc.stdout)
    info = {"duration": float(data.get("format", {}).get("duration") or 0)}
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            num, _, den = stream.get("r_frame_rate", "0/1").partition("/")
            info.update(
                width=stream["width"],
                height=stream["height"],
                fps=float(num) / float(den or 1) if float(den or 1) else 0.0,
                video_codec=stream.get("codec_name"),
            )
        elif stream.get("codec_type") == "audio":
            info.update(
                audio_codec=stream.get("codec_name"),
                sample_rate=int(stream.get("sample_rate", 0)),
            )
    return info
