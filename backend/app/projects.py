"""Project records in SQLite. The video JSON is stored as validated text."""

from .db import connect
from .schemas.scenes import ScenesInput
from .schemas.video import Video, parse_video

STATUSES = ("draft", "running", "review", "rendering", "done", "failed")


def _row(row) -> dict:
    return dict(row) if row else None


def create_project(title: str) -> dict:
    with connect() as conn:
        cur = conn.execute("INSERT INTO projects (title) VALUES (?)", (title,))
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row(row)


def list_projects() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_project(project_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row(row)


def _update(project_id: int, column: str, value: str) -> None:
    with connect() as conn:
        cur = conn.execute(
            f"UPDATE projects SET {column} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (value, project_id),
        )
        if cur.rowcount == 0:
            raise KeyError(f"project {project_id} not found")


def save_scenes(project_id: int, scenes: ScenesInput) -> None:
    _update(project_id, "scenes_json", scenes.model_dump_json())


def get_scenes(project_id: int) -> ScenesInput | None:
    project = get_project(project_id)
    if not project or not project["scenes_json"]:
        return None
    return ScenesInput.model_validate_json(project["scenes_json"])


def save_video(project_id: int, video: Video) -> None:
    _update(project_id, "video_json", video.model_dump_json())


def get_video(project_id: int) -> Video | None:
    project = get_project(project_id)
    if not project or not project["video_json"]:
        return None
    return parse_video(project["video_json"])


def set_status(project_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    _update(project_id, "status", status)
