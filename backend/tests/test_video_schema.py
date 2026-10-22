import copy
import json
from pathlib import Path

import pytest

from app.schemas.video import VideoValidationError, parse_video, validate_for_render

FIXTURE = Path(__file__).parent / "fixtures" / "sample_video.json"


@pytest.fixture
def sample() -> dict:
    return json.loads(FIXTURE.read_text())


def problems(data: dict) -> list[str]:
    with pytest.raises(VideoValidationError) as exc:
        parse_video(data)
    return exc.value.problems


def test_sample_validates(sample):
    video = parse_video(sample)
    assert len(video.scenes) == 3
    assert video.output.width == 1080 and video.output.height == 1920


def test_validates_from_json_text():
    assert parse_video(FIXTURE.read_text()).scenes[0].id == "s1"


def test_duration_is_audio_plus_pad(sample):
    video = parse_video(sample)
    assert video.scenes[0].duration_s == pytest.approx(1.8 + 0.3)
    assert video.scenes[1].duration_s == pytest.approx(3.6 + 0.4)
    assert video.scenes[2].duration_s is None  # no audio yet
    assert video.total_duration_s is None


def test_total_duration_when_all_scenes_have_audio(sample):
    sample["scenes"] = sample["scenes"][:2]
    assert parse_video(sample).total_duration_s == pytest.approx(2.1 + 4.0)


def test_defaults_fill_in():
    video = parse_video({"scenes": [{"id": "a", "script_line": "Hi"}]})
    scene = video.scenes[0]
    assert video.output.fps == 30
    assert scene.motion.focal_point.y == 0.4
    assert scene.media is None


def test_absolute_path_rejected(sample):
    sample["scenes"][0]["audio"]["key"] = "/home/me/a.mp3"
    assert any("relative path" in p for p in problems(sample))


def test_windows_path_rejected(sample):
    sample["scenes"][0]["audio"]["key"] = "C:\\audio\\a.mp3"
    assert any("relative path" in p for p in problems(sample))


def test_parent_traversal_rejected(sample):
    sample["scenes"][0]["media"]["key"] = "projects/1/../../secret.mp4"
    assert any("'..'" in p for p in problems(sample))


def test_error_message_points_at_the_field(sample):
    sample["scenes"][1]["audio"]["duration_s"] = 0
    msgs = problems(sample)
    assert any(m.startswith("scenes[1].audio.duration_s") for m in msgs)


def test_duplicate_scene_ids_rejected(sample):
    sample["scenes"][1]["id"] = "s1"
    assert any("duplicate scene ids: s1" in p for p in problems(sample))


def test_no_scenes_rejected():
    assert problems({"scenes": []})


def test_unknown_field_rejected(sample):
    sample["scenes"][0]["colour"] = "red"
    assert any("colour" in p for p in problems(sample))


def test_unknown_motion_preset_rejected(sample):
    sample["scenes"][0]["motion"]["preset"] = "spin"
    assert any("motion.preset" in p for p in problems(sample))


def test_focal_point_must_be_in_frame(sample):
    sample["scenes"][0]["motion"]["focal_point"]["x"] = 1.5
    assert any("focal_point.x" in p for p in problems(sample))


def test_landscape_output_rejected(sample):
    sample["output"] = {"width": 1920, "height": 1080, "fps": 30}
    assert any("portrait" in p for p in problems(sample))


def test_trim_end_before_start_rejected(sample):
    sample["scenes"][0]["media"]["trim_start_s"] = 2.0
    sample["scenes"][0]["media"]["trim_end_s"] = 1.0
    assert any("trim_end_s" in p for p in problems(sample))


def test_image_cannot_be_trimmed(sample):
    sample["scenes"][1]["media"]["trim_start_s"] = 1.0
    assert any("cannot be trimmed" in p for p in problems(sample))


def test_word_must_end_after_start(sample):
    sample["scenes"][0]["captions"]["words"][0]["end"] = 0.0
    assert any("end must be after" in p for p in problems(sample))


def test_overlapping_words_rejected(sample):
    words = sample["scenes"][0]["captions"]["words"]
    words[1]["start"] = 0.1
    assert any("overlap" in p for p in problems(sample))


def test_word_past_end_of_audio_rejected(sample):
    sample["scenes"][0]["captions"]["words"][2]["end"] = 5.0
    assert any("ends after the audio" in p for p in problems(sample))


def test_bad_caption_color_rejected(sample):
    sample["caption_style"]["color"] = "white"
    assert any("caption_style.color" in p for p in problems(sample))


def test_several_problems_reported_together(sample):
    sample["scenes"][0]["audio"]["key"] = "/abs.mp3"
    sample["scenes"][1]["audio"]["duration_s"] = 0
    assert len(problems(sample)) >= 2


def test_roundtrip(sample):
    video = parse_video(sample)
    again = parse_video(video.model_dump_json())
    assert again == video


# --- validate_for_render -----------------------------------------------------


def complete_video(sample):
    data = copy.deepcopy(sample)
    data["scenes"] = data["scenes"][:2]
    return parse_video(data)


def test_render_check_passes_when_complete_and_files_exist(sample):
    validate_for_render(complete_video(sample), lambda key: True)


def test_render_check_flags_missing_files(sample):
    with pytest.raises(VideoValidationError) as exc:
        validate_for_render(complete_video(sample), lambda key: False)
    msgs = exc.value.problems
    assert any("audio file missing" in m for m in msgs)
    assert any("media file missing" in m for m in msgs)
    assert any("music" in m for m in msgs)


def test_render_check_flags_incomplete_scene(sample):
    with pytest.raises(VideoValidationError) as exc:
        validate_for_render(parse_video(sample), lambda key: True)
    msgs = exc.value.problems
    assert any("scenes[2]" in m and "no voiceover" in m for m in msgs)
    assert any("scenes[2]" in m and "no media" in m for m in msgs)
