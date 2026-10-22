"""Build a 10-scene dummy project in storage for testing the renderer.

    python scripts/make_dummy_project.py [project_id]

Generated with FFmpeg only: labelled test images, odd-format clips that go through
the real ingest step, sine-tone "voiceovers", and fake word timings. Swap in your own
files under storage/projects/<id>/ to try real material.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.render.ingest import normalize_video  # noqa: E402
from app.render.tools import probe, run_ffmpeg  # noqa: E402
from app.schemas.video import parse_video  # noqa: E402
from app.storage import project_key, storage  # noqa: E402

PROJECT_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 9999

LINES = [
    "Honey never spoils and that is a fact",
    "Archaeologists found edible honey in ancient tombs",
    "Bees make it by repeatedly drying nectar",
    "Its low water content keeps bacteria away",
    "A single bee makes only a tiny spoonful",
    "A hive can visit millions of flowers a day",
    "The colour changes with the flowers they visit",
    "Dark honey is often stronger in flavour",
    "People have used it as medicine for ages",
    "So keep your jar and never throw it away",
]
AUDIO_SECONDS = [3.2, 4.5, 2.8, 5.0, 3.6, 4.1, 2.5, 4.8, 3.3, 4.0]
PRESETS = ["zoom_in", "pan_left", "zoom_out", "pan_right", "pan_up", "zoom_in",
           "pan_down", "zoom_out", "pan_left", "pan_right"]
SOURCES = ["testsrc2", "mandelbrot", "gradients", "rgbtestsrc", "smptebars"]
FONT = "C\\:/Windows/Fonts/arial.ttf"


def label(n: int) -> str:
    return (
        f"drawtext=fontfile='{FONT}':text='SCENE {n}':fontsize=120:fontcolor=white:"
        "box=1:boxcolor=black@0.55:boxborderw=24:x=(w-text_w)/2:y=h*0.18"
    )


def make_image(n: int, out: Path) -> None:
    # Bigger than the frame (1.2x), as generated images will be, to leave room for motion.
    src = SOURCES[n % len(SOURCES)]
    run_ffmpeg([
        "-f", "lavfi", "-i", f"{src}=s=1296x2304", "-frames:v", "1",
        "-vf", label(n), "-q:v", "3", str(out),
    ])


def make_raw_clip(n: int, out: Path) -> None:
    src = SOURCES[n % len(SOURCES)]
    run_ffmpeg([
        "-f", "lavfi", "-i", f"{src}=s=1280x720:r=25", "-t", "4",
        "-vf", label(n).replace("fontsize=120", "fontsize=80"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
    ])


def make_voice(n: int, seconds: float, out: Path) -> None:
    run_ffmpeg([
        "-f", "lavfi", "-i", f"sine=frequency={180 + 35 * n}:duration={seconds}",
        "-af", "volume=0.25", "-c:a", "libmp3lame", "-q:a", "4", str(out),
    ])


def make_music(out: Path) -> None:
    run_ffmpeg([
        "-f", "lavfi", "-i", "sine=frequency=110:duration=20",
        "-af", "tremolo=f=2:d=0.6,volume=0.6", "-c:a", "libmp3lame", "-q:a", "4", str(out),
    ])


def words_for(line: str, duration: float) -> list[dict]:
    words = line.split()
    start, end = 0.15, duration - 0.25
    step = (end - start) / len(words)
    return [
        {"text": w, "start": round(start + i * step, 3), "end": round(start + (i + 1) * step - 0.04, 3)}
        for i, w in enumerate(words)
    ]


def main() -> None:
    scenes = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        for i, line in enumerate(LINES):
            n = i + 1
            name = f"scene_{n:02d}"

            voice_tmp = tmp / f"{name}.mp3"
            make_voice(i, AUDIO_SECONDS[i], voice_tmp)
            audio_key = storage.save(project_key(PROJECT_ID, "audio", f"{name}.mp3"), voice_tmp)
            duration = probe(storage.get(audio_key))["duration"]

            if i % 2 == 0:
                img_tmp = tmp / f"{name}.jpg"
                make_image(n, img_tmp)
                media_key = storage.save(project_key(PROJECT_ID, "clips", f"{name}.jpg"), img_tmp)
                media = {"source": "generated", "kind": "image", "key": media_key}
            else:
                raw = tmp / f"{name}_raw.mp4"
                make_raw_clip(n, raw)
                norm = tmp / f"{name}.mp4"
                info = normalize_video(raw, norm)
                media_key = storage.save(project_key(PROJECT_ID, "clips", f"{name}.mp4"), norm)
                media = {"source": "stock", "kind": "video", "key": media_key,
                         "duration_s": round(info["duration"], 3)}

            scenes.append({
                "id": f"s{n}",
                "script_line": line,
                "visual_prompt": f"dummy visual {n}",
                "audio": {"key": audio_key, "duration_s": round(duration, 3)},
                "media": media,
                "motion": {"preset": PRESETS[i]},
                "captions": {"text": line, "words": words_for(line, duration)},
            })

        music_tmp = tmp / "music.mp3"
        make_music(music_tmp)
        music_key = storage.save(project_key(PROJECT_ID, "audio", "music.mp3"), music_tmp)

    video = parse_video({
        "scenes": scenes,
        "music": {"key": music_key, "volume": 0.15, "duck_under_voice": True},
    })
    out = storage.root / "projects" / str(PROJECT_ID) / "video.json"
    out.write_text(json.dumps(json.loads(video.model_dump_json()), indent=2), encoding="utf-8")
    print(f"project {PROJECT_ID}: {len(scenes)} scenes, {video.total_duration_s:.1f}s total")
    print(f"video JSON: {out}")


if __name__ == "__main__":
    main()
