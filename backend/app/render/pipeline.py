"""Render a whole video: validate, render only the changed scenes, join."""

import time
from dataclasses import dataclass, field
from typing import Callable, Literal

from ..schemas.video import Video, VideoValidationError, validate_for_render
from ..storage import LocalStorage, project_key, storage as default_storage
from .hashing import scene_hash
from .join import join_segments
from .segments import render_segments, scene_props
from .tools import RenderError

Mode = Literal["draft", "final"]


@dataclass
class RenderResult:
    key: str
    mode: str
    scenes: int
    rendered: list[str] = field(default_factory=list)  # scene ids rendered this time
    cached: list[str] = field(default_factory=list)  # scene ids reused from the cache
    segment_seconds: float = 0.0
    join_seconds: float = 0.0
    total_seconds: float = 0.0


def segment_key(project_id: int, mode: str, digest: str) -> str:
    return project_key(project_id, "renders", f"segments/{mode}_{digest[:16]}.mp4")


def render_video(
    project_id: int,
    video: Video,
    mode: Mode = "final",
    *,
    scene_range: tuple[int, int] | None = None,
    store: LocalStorage = default_storage,
    on_progress: Callable[[dict], None] | None = None,
) -> RenderResult:
    """Render ``video`` and return where the MP4 is.

    ``scene_range`` is (first, last) scene index, inclusive, for a quick spot check
    of part of the video; the output is then named ``..._range``.
    """
    started = time.monotonic()
    if mode not in ("draft", "final"):
        raise ValueError(f"unknown render mode {mode!r}")

    scenes = list(video.scenes)
    if scene_range is not None:
        first, last = scene_range
        if not (0 <= first <= last < len(scenes)):
            raise ValueError(f"scene_range {scene_range} is outside 0..{len(scenes) - 1}")
        scenes = scenes[first : last + 1]

    # Fail before the slow step if anything is missing or incomplete.
    checked = video.model_copy(update={"scenes": scenes})
    validate_for_render(checked, store.exists)

    result = RenderResult(key="", mode=mode, scenes=len(scenes))
    jobs, segment_keys = [], []
    for scene in scenes:
        digest = scene_hash(video, scene, mode, store)
        key = segment_key(project_id, mode, digest)
        segment_keys.append(key)
        if store.exists(key):
            result.cached.append(scene.id)
        else:
            result.rendered.append(scene.id)
            jobs.append({"id": scene.id, "outKey": key, "props": scene_props(video, scene)})

    log_path = store.root / "projects" / str(project_id) / "renders" / "render.log"
    t0 = time.monotonic()
    render_segments(jobs, mode, log_path, on_progress)
    result.segment_seconds = time.monotonic() - t0

    missing = [k for k in segment_keys if not store.exists(k)]
    if missing:
        raise RenderError(f"renderer finished but segments are missing: {missing}")

    suffix = "" if scene_range is None else f"_range{scene_range[0]}-{scene_range[1]}"
    out_key = project_key(project_id, "renders", f"final_{mode}{suffix}.mp4")
    music_path = store.get(video.music.key) if video.music else None
    total = sum(s.duration_s for s in scenes)

    t0 = time.monotonic()
    join_segments(
        [store.get(k) for k in segment_keys],
        store.root / out_key,
        music=video.music,
        music_path=music_path,
        total_duration_s=total,
    )
    result.join_seconds = time.monotonic() - t0
    result.key = out_key
    result.total_seconds = time.monotonic() - started
    return result
