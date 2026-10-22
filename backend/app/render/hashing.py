"""Cache keys for scene segments.

A segment is re-rendered only when something that affects its pixels or sound
changes. Text that never reaches the screen (the script line, the visual prompt,
unchosen candidates, attribution) is left out, so editing it costs nothing.
"""

import hashlib
import json

from ..schemas.video import Scene, Video
from ..storage import LocalStorage

# Bump when the composition or encoder settings change in a way that alters output.
RENDERER_VERSION = 1

_IGNORED = {
    "script_line": True,
    "visual_prompt": True,
    "media": {"candidates", "attribution"},
    "captions": {"style"},  # the effective style is hashed separately below
}


def _file_signature(storage: LocalStorage, key: str) -> str:
    stat = storage.get(key).stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def effective_caption_style(video: Video, scene: Scene):
    return (scene.captions.style if scene.captions and scene.captions.style else None) or video.caption_style


def scene_hash(video: Video, scene: Scene, mode: str, storage: LocalStorage) -> str:
    files = {}
    for ref in (scene.audio, scene.media):
        if ref is not None:
            files[ref.key] = _file_signature(storage, ref.key)
    payload = {
        "renderer": RENDERER_VERSION,
        "mode": mode,
        "output": video.output.model_dump(mode="json"),
        "caption_style": effective_caption_style(video, scene).model_dump(mode="json"),
        "scene": scene.model_dump(mode="json", exclude=_IGNORED),
        "files": files,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()
