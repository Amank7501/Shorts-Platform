import shutil
from pathlib import Path

import pytest

from app.render import pipeline
from app.render.hashing import scene_hash
from app.render.ingest import normalize_video
from app.render.join import join_segments
from app.render.segments import scene_props
from app.render.tools import probe, run_ffmpeg
from app.schemas.video import Captions, MotionPreset, VideoValidationError, Word, parse_video
from app.storage import LocalStorage

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


@pytest.fixture
def store(tmp_path):
    return LocalStorage(tmp_path / "storage")


def make_audio(path: Path, seconds: float = 1.0):
    run_ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}", str(path)])


def make_image(path: Path):
    run_ffmpeg(["-f", "lavfi", "-i", "color=c=red:s=200x300", "-frames:v", "1", str(path)])


@pytest.fixture
def video(store, tmp_path):
    scenes = []
    for n in (1, 2, 3):
        a, i = tmp_path / f"a{n}.mp3", tmp_path / f"i{n}.jpg"
        make_audio(a, 1.0 + n / 10)
        make_image(i)
        store.save(f"projects/1/audio/s{n}.mp3", a)
        store.save(f"projects/1/clips/s{n}.jpg", i)
        scenes.append({
            "id": f"s{n}",
            "script_line": f"line {n}",
            "visual_prompt": "x",
            "audio": {"key": f"projects/1/audio/s{n}.mp3", "duration_s": 1.0 + n / 10},
            "media": {"source": "generated", "kind": "image", "key": f"projects/1/clips/s{n}.jpg"},
            "captions": {"text": f"line {n}", "words": [{"text": "line", "start": 0.0, "end": 0.4}]},
        })
    return parse_video({"scenes": scenes})


def change(video, index, **fields):
    scenes = list(video.scenes)
    scenes[index] = scenes[index].model_copy(update=fields)
    return video.model_copy(update={"scenes": scenes})


# --- hashing -----------------------------------------------------------------


def test_hash_is_stable(video, store):
    s = video.scenes[0]
    assert scene_hash(video, s, "final", store) == scene_hash(video, s, "final", store)


def test_hash_ignores_text_that_is_not_rendered(video, store):
    base = scene_hash(video, video.scenes[0], "final", store)
    edited = change(video, 0, script_line="something else", visual_prompt="other")
    assert scene_hash(edited, edited.scenes[0], "final", store) == base


def test_hash_ignores_candidates(video, store):
    base = scene_hash(video, video.scenes[0], "final", store)
    media = video.scenes[0].media.model_copy(update={
        "candidates": [{"key": "projects/1/clips/other.jpg", "source": "stock", "kind": "image"}]
    })
    edited = change(video, 0, media=media)
    assert scene_hash(edited, edited.scenes[0], "final", store) == base


def test_hash_changes_with_motion(video, store):
    base = scene_hash(video, video.scenes[0], "final", store)
    motion = video.scenes[0].motion.model_copy(update={"preset": MotionPreset.pan_up})
    edited = change(video, 0, motion=motion)
    assert scene_hash(edited, edited.scenes[0], "final", store) != base


def test_hash_changes_with_caption_words(video, store):
    base = scene_hash(video, video.scenes[0], "final", store)
    caps = Captions(text="line 1", words=[Word(text="changed", start=0.0, end=0.4)])
    edited = change(video, 0, captions=caps)
    assert scene_hash(edited, edited.scenes[0], "final", store) != base


def test_hash_changes_with_video_caption_style(video, store):
    base = scene_hash(video, video.scenes[0], "final", store)
    style = video.caption_style.model_copy(update={"font_size": 90})
    edited = video.model_copy(update={"caption_style": style})
    assert scene_hash(edited, edited.scenes[0], "final", store) != base


def test_hash_changes_with_mode(video, store):
    s = video.scenes[0]
    assert scene_hash(video, s, "draft", store) != scene_hash(video, s, "final", store)


def test_hash_changes_when_file_is_replaced(video, store, tmp_path):
    base = scene_hash(video, video.scenes[0], "final", store)
    new = tmp_path / "new.mp3"
    make_audio(new, 2.5)
    store.save("projects/1/audio/s1.mp3", new)
    assert scene_hash(video, video.scenes[0], "final", store) != base


# --- props -------------------------------------------------------------------


def test_props_duration_and_style(video):
    props = scene_props(video, video.scenes[0])
    assert props["durationInFrames"] == round((1.1 + 0.3) * 30)
    assert props["audioKey"] == "projects/1/audio/s1.mp3"
    assert props["captionStyle"]["mode"] == "karaoke"
    assert props["media"]["kind"] == "image"


def test_props_clip_length_from_trim_and_duration():
    v = parse_video({"scenes": [{
        "id": "a", "script_line": "x",
        "audio": {"key": "a.mp3", "duration_s": 5},
        "media": {"source": "stock", "kind": "video", "key": "c.mp4",
                  "duration_s": 6, "trim_start_s": 1},
    }]})
    assert scene_props(v, v.scenes[0])["media"]["clip_length_s"] == 5
    v2 = parse_video({"scenes": [{
        "id": "a", "script_line": "x",
        "audio": {"key": "a.mp3", "duration_s": 5},
        "media": {"source": "stock", "kind": "video", "key": "c.mp4",
                  "duration_s": 6, "trim_start_s": 1, "trim_end_s": 3},
    }]})
    assert scene_props(v2, v2.scenes[0])["media"]["clip_length_s"] == 2


# --- ingest ------------------------------------------------------------------


def test_normalize_video_outputs_standard_format(tmp_path):
    raw = tmp_path / "raw.mp4"
    run_ffmpeg([
        "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=25", "-f", "lavfi",
        "-i", "sine=frequency=440", "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(raw),
    ])
    out = tmp_path / "norm.mp4"
    info = normalize_video(raw, out, max_seconds=2)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert info["fps"] == pytest.approx(30)
    assert "audio_codec" not in info  # audio stripped
    assert info["duration"] <= 2.1


# --- join --------------------------------------------------------------------


def make_segment(path: Path, seconds: float, tone: int = 300):
    run_ffmpeg([
        "-f", "lavfi", "-i", f"color=c=blue:s=108x192:r=30:d={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency={tone}:duration={seconds}:sample_rate=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-shortest", str(path),
    ])


def test_join_concatenates(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    make_segment(a, 1.0)
    make_segment(b, 1.5)
    out = tmp_path / "out.mp4"
    join_segments([a, b], out)
    assert probe(out)["duration"] == pytest.approx(2.5, abs=0.15)


def test_join_mixes_music(tmp_path):
    from app.schemas.video import Music

    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    make_segment(a, 1.0)
    make_segment(b, 1.0)
    music = tmp_path / "m.mp3"
    make_audio(music, 0.5)  # shorter than the video: it must loop, not cut the video short
    out = tmp_path / "out.mp4"
    join_segments(
        [a, b], out,
        music=Music(key="m.mp3", volume=0.2), music_path=music, total_duration_s=2.0,
    )
    info = probe(out)
    assert info["duration"] == pytest.approx(2.0, abs=0.15)
    assert info["audio_codec"] == "aac"


# --- pipeline (the Remotion step is stubbed) ----------------------------------


@pytest.fixture
def stub_renderer(monkeypatch, store, tmp_path):
    template = tmp_path / "template.mp4"
    make_segment(template, 1.0)
    calls = []

    def fake(jobs, mode, log_path, on_progress=None):
        calls.append([j["id"] for j in jobs])
        for j in jobs:
            store.save(j["outKey"], template)
        return {j["id"]: 0.0 for j in jobs}

    monkeypatch.setattr(pipeline, "render_segments", fake)
    return calls


def test_first_render_renders_everything(video, store, stub_renderer):
    result = pipeline.render_video(1, video, "draft", store=store)
    assert result.rendered == ["s1", "s2", "s3"] and result.cached == []
    assert store.exists(result.key)


def test_second_render_uses_cache(video, store, stub_renderer):
    pipeline.render_video(1, video, "draft", store=store)
    result = pipeline.render_video(1, video, "draft", store=store)
    assert result.rendered == [] and result.cached == ["s1", "s2", "s3"]


def test_editing_one_scene_rerenders_only_that_scene(video, store, stub_renderer):
    pipeline.render_video(1, video, "final", store=store)
    motion = video.scenes[1].motion.model_copy(update={"preset": MotionPreset.pan_down})
    edited = change(video, 1, motion=motion)
    result = pipeline.render_video(1, edited, "final", store=store)
    assert result.rendered == ["s2"]
    assert result.cached == ["s1", "s3"]
    assert stub_renderer[-1] == ["s2"]


def test_script_line_edit_rerenders_nothing(video, store, stub_renderer):
    pipeline.render_video(1, video, "final", store=store)
    edited = change(video, 0, script_line="reworded")
    result = pipeline.render_video(1, edited, "final", store=store)
    assert result.rendered == []


def test_draft_and_final_are_cached_separately(video, store, stub_renderer):
    pipeline.render_video(1, video, "draft", store=store)
    result = pipeline.render_video(1, video, "final", store=store)
    assert len(result.rendered) == 3


def test_scene_range_renders_a_subset(video, store, stub_renderer):
    result = pipeline.render_video(1, video, "draft", scene_range=(1, 2), store=store)
    assert result.rendered == ["s2", "s3"]
    assert result.key.endswith("_range1-2.mp4")


def test_bad_scene_range_rejected(video, store, stub_renderer):
    with pytest.raises(ValueError):
        pipeline.render_video(1, video, "draft", scene_range=(2, 9), store=store)


def test_validation_runs_before_any_rendering(video, store, stub_renderer):
    store.delete("projects/1/clips/s2.jpg")
    with pytest.raises(VideoValidationError) as exc:
        pipeline.render_video(1, video, "final", store=store)
    assert any("media file missing" in p for p in exc.value.problems)
    assert stub_renderer == []  # the slow step never started
