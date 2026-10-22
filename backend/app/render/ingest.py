"""Normalize media once, when it is downloaded, so rendering never meets odd inputs.

Clips become 1080x1920, 30 fps, H.264, no audio, with their length capped. A small
low-resolution proxy is made alongside for smooth scrubbing in the editor.
"""

from pathlib import Path

from .tools import probe, run_ffmpeg

WIDTH, HEIGHT, FPS = 1080, 1920, 30
MAX_CLIP_SECONDS = 15.0

PROXY_WIDTH, PROXY_HEIGHT = 360, 640


def _cover(width: int, height: int) -> str:
    # Fill the frame, cropping the overflow, rather than letterboxing.
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )


def normalize_video(src: Path, dst: Path, max_seconds: float = MAX_CLIP_SECONDS) -> dict:
    """Transcode ``src`` to the standard format at ``dst``. Returns its probe info."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", str(src), "-t", f"{max_seconds}", "-an",
        "-vf", f"{_cover(WIDTH, HEIGHT)},fps={FPS},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-movflags", "+faststart", str(dst),
    ])
    return probe(dst)


def make_video_proxy(src: Path, dst: Path) -> None:
    """A small, cheap-to-decode copy of a clip for editor scrubbing."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", str(src), "-an",
        "-vf", f"{_cover(PROXY_WIDTH, PROXY_HEIGHT)},fps={FPS},format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
        "-g", "15", "-movflags", "+faststart", str(dst),
    ])
