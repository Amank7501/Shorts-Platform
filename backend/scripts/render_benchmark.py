"""Time the renderer on the dummy project.

    python scripts/render_benchmark.py [project_id]

Runs: a full final render from an empty cache, the same render again (all cached),
the same render after editing ONE scene, a full draft render, and a plain
FFmpeg-only render of one scene as a baseline for the Remotion-versus-FFmpeg decision.
"""

import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.render.pipeline import render_video  # noqa: E402
from app.render.tools import probe, run_ffmpeg  # noqa: E402
from app.schemas.video import MotionPreset, parse_video  # noqa: E402
from app.storage import storage  # noqa: E402

project_id = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
video = parse_video((storage.root / "projects" / str(project_id) / "video.json").read_text(encoding="utf-8"))

seg_dir = storage.root / "projects" / str(project_id) / "renders" / "segments"
shutil.rmtree(seg_dir, ignore_errors=True)

rows = []


def run(label, vid, mode):
    r = render_video(project_id, vid, mode, store=storage)
    out = probe(storage.get(r.key))
    rows.append((label, mode, len(r.rendered), len(r.cached), r.segment_seconds, r.join_seconds, r.total_seconds))
    print(f"{label}: {r.total_seconds:.1f}s total (segments {r.segment_seconds:.1f}s, join {r.join_seconds:.1f}s), "
          f"rendered {len(r.rendered)}, cached {len(r.cached)}, output {out['width']}x{out['height']} "
          f"{out['duration']:.1f}s", flush=True)
    return r


run("1. full final, empty cache", video, "final")
run("2. same again", video, "final")

scenes = list(video.scenes)
new_motion = scenes[3].motion.model_copy(update={"preset": MotionPreset.pan_left})
scenes[3] = scenes[3].model_copy(update={"motion": new_motion})
edited = video.model_copy(update={"scenes": scenes})
run("3. edit scene 4 only", edited, "final")

run("4. full draft, empty draft cache", video, "draft")

# FFmpeg-only baseline: one image scene with a zoom, audio and no captions.
scene = next(s for s in video.scenes if s.media.kind.value == "image")
out = Path(storage.root) / "projects" / str(project_id) / "renders" / "ffmpeg_only_baseline.mp4"
frames = round(scene.duration_s * 30)
t0 = time.monotonic()
run_ffmpeg([
    "-i", str(storage.get(scene.media.key)), "-i", str(storage.get(scene.audio.key)),
    "-vf", f"zoompan=z='min(zoom+0.0006,1.18)':d={frames}:s=1080x1920:fps=30,format=yuv420p",
    "-t", f"{scene.duration_s:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out),
])
baseline = time.monotonic() - t0
print(f"5. FFmpeg-only, one {scene.duration_s:.1f}s image scene, no captions: {baseline:.1f}s", flush=True)

full = rows[0]
per_scene = full[4] / full[2]
total_video = video.total_duration_s
print()
print(f"video length: {total_video:.1f}s, {len(video.scenes)} scenes")
print(f"{'run':36}{'mode':7}{'rendered':>9}{'cached':>7}{'segments':>10}{'join':>7}{'total':>8}")
for label, mode, nr, nc, seg, join, total in rows:
    print(f"{label:36}{mode:7}{nr:>9}{nc:>7}{seg:>9.1f}s{join:>6.1f}s{total:>7.1f}s")
print(f"\nRemotion per scene (final, cold): {per_scene:.1f}s avg")
print(f"FFmpeg-only per scene (image, no captions): {baseline:.1f}s")
