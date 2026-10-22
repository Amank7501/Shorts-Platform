"""Render the dummy project.

    python scripts/render_dummy.py [draft|final] [first-last] [project_id]

Examples:  render_dummy.py draft 0-1      render_dummy.py final
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.render.pipeline import render_video  # noqa: E402
from app.schemas.video import parse_video  # noqa: E402
from app.storage import storage  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "final"
scene_range = None
if len(sys.argv) > 2 and "-" in sys.argv[2]:
    a, b = sys.argv[2].split("-")
    scene_range = (int(a), int(b))
project_id = int(sys.argv[3]) if len(sys.argv) > 3 else 9999

video = parse_video((storage.root / "projects" / str(project_id) / "video.json").read_text(encoding="utf-8"))


def progress(event: dict) -> None:
    if event.get("event") in ("start", "done", "error"):
        print(" ", event, flush=True)


result = render_video(project_id, video, mode, scene_range=scene_range, on_progress=progress)
print(result)
print("output:", storage.get(result.key))
