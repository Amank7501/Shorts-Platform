import json
from pathlib import Path

import pytest

from app import projects
from app.config import settings
from app.db import init_db
from app.schemas.scenes import ScenesInput
from app.schemas.video import parse_video

FIXTURE = Path(__file__).parent / "fixtures" / "sample_video.json"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "test.db")
    init_db()


def test_create_and_read():
    p = projects.create_project("Honey facts")
    assert p["title"] == "Honey facts"
    assert p["status"] == "draft"
    assert projects.get_project(p["id"])["title"] == "Honey facts"


def test_get_missing_returns_none():
    assert projects.get_project(999) is None


def test_list_newest_first():
    a = projects.create_project("a")
    b = projects.create_project("b")
    assert [p["id"] for p in projects.list_projects()] == [b["id"], a["id"]]


def test_scenes_roundtrip():
    p = projects.create_project("x")
    scenes = ScenesInput.model_validate(
        {"scenes": [{"script_line": "Hi", "visual_prompt": "a wave"}]}
    )
    projects.save_scenes(p["id"], scenes)
    assert projects.get_scenes(p["id"]) == scenes


def test_scenes_need_a_visual_prompt():
    with pytest.raises(ValueError):
        ScenesInput.model_validate({"scenes": [{"script_line": "Hi", "visual_prompt": ""}]})


def test_video_roundtrip():
    p = projects.create_project("x")
    video = parse_video(json.loads(FIXTURE.read_text()))
    assert projects.get_video(p["id"]) is None
    projects.save_video(p["id"], video)
    assert projects.get_video(p["id"]) == video


def test_status_update():
    p = projects.create_project("x")
    projects.set_status(p["id"], "review")
    assert projects.get_project(p["id"])["status"] == "review"


def test_unknown_status_rejected():
    p = projects.create_project("x")
    with pytest.raises(ValueError):
        projects.set_status(p["id"], "banana")


def test_updating_missing_project_raises():
    with pytest.raises(KeyError):
        projects.set_status(999, "done")
