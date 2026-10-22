"""Local file storage behind a small interface.

Nothing else in the app touches file paths: it passes keys such as
``projects/42/clips/scene_03.mp4``. Swapping this class for S3 later should not
change any caller.
"""

import shutil
from pathlib import Path
from typing import Literal

from .config import settings

Kind = Literal["audio", "clips", "renders"]


def project_key(project_id: int, kind: Kind, filename: str) -> str:
    return f"projects/{project_id}/{kind}/{filename}"


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        if not key or key.startswith("/") or "\\" in key or ":" in key:
            raise ValueError(f"invalid storage key: {key!r}")
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError(f"invalid storage key: {key!r}")
        return path

    def save(self, key: str, data: bytes | Path) -> str:
        """Store bytes, or copy the file at the given path, under ``key``."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, Path):
            shutil.copyfile(data, path)
        else:
            path.write_bytes(data)
        return key

    def get(self, key: str) -> Path:
        """Return the local path for ``key``. Raises FileNotFoundError if absent."""
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        """Delete the file. Deleting a missing key is not an error."""
        self._path(key).unlink(missing_ok=True)


storage = LocalStorage(settings.storage_dir)
