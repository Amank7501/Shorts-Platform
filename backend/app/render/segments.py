"""Render scene segments by handing a manifest to the Remotion renderer (Node)."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from ..config import settings
from ..schemas.video import Scene, Video
from .hashing import effective_caption_style
from .tools import RenderError

Progress = Callable[[dict], None]


def scene_props(video: Video, scene: Scene) -> dict:
    """Everything the Remotion composition needs for one scene. Keys, never paths."""
    fps = video.output.fps
    media = None
    if scene.media is not None:
        m = scene.media
        clip_length = None
        if m.kind.value == "video":
            end = m.trim_end_s if m.trim_end_s is not None else m.duration_s
            if end is not None:
                clip_length = max(end - m.trim_start_s, 0) or None
        media = {
            "kind": m.kind.value,
            "key": m.key,
            "trim_start_s": m.trim_start_s,
            "clip_length_s": clip_length,
        }
    return {
        "width": video.output.width,
        "height": video.output.height,
        "fps": fps,
        "durationInFrames": max(1, round(scene.duration_s * fps)),
        "audioKey": scene.audio.key if scene.audio else None,
        "media": media,
        "motion": {
            "preset": scene.motion.preset.value,
            "focal_point": scene.motion.focal_point.model_dump(),
        },
        "words": [w.model_dump() for w in scene.captions.words] if scene.captions else [],
        "captionStyle": effective_caption_style(video, scene).model_dump(mode="json"),
    }


def render_segments(
    jobs: list[dict], mode: str, log_path: Path, on_progress: Progress | None = None
) -> dict[str, float]:
    """Render ``jobs`` ([{id, outKey, props}]). Returns seconds taken per job id.

    Renderer stderr is appended to ``log_path``; a failure raises RenderError with
    the renderer's own message.
    """
    if not jobs:
        return {}
    manifest = {"storageRoot": str(settings.storage_dir), "mode": mode, "jobs": jobs}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    seconds: dict[str, float] = {}
    error: str | None = None

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(manifest, f)
        manifest_path = f.name
    try:
        with open(log_path, "a", encoding="utf-8") as log:
            try:
                proc = subprocess.Popen(
                    [settings.node_bin, "render-segments.mjs", manifest_path],
                    cwd=settings.renderer_dir,
                    env={**os.environ, "FFPROBE_BIN": settings.ffprobe_bin},
                    stdout=subprocess.PIPE,
                    stderr=log,
                    text=True,
                    encoding="utf-8",
                )
            except FileNotFoundError as exc:
                raise RenderError(f"node not found ({settings.node_bin!r})") from exc
            for line in proc.stdout:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    log.write(line)
                    continue
                if event.get("event") == "done":
                    seconds[event["id"]] = event["seconds"]
                elif event.get("event") == "error":
                    error = event.get("message")
                if on_progress:
                    on_progress(event)
            code = proc.wait()
    finally:
        Path(manifest_path).unlink(missing_ok=True)

    if error or code != 0:
        raise RenderError(f"segment render failed: {error or f'renderer exited with {code}'}\n(see {log_path})")
    return seconds
