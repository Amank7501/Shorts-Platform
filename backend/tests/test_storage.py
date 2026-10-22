import pytest

from app.storage import LocalStorage, project_key


@pytest.fixture
def store(tmp_path):
    return LocalStorage(tmp_path / "storage")


def test_save_and_get_bytes(store):
    key = project_key(42, "clips", "scene_03.mp4")
    assert key == "projects/42/clips/scene_03.mp4"
    assert store.save(key, b"data") == key
    assert store.get(key).read_bytes() == b"data"
    assert store.exists(key)


def test_save_copies_a_file(store, tmp_path):
    src = tmp_path / "in.mp3"
    src.write_bytes(b"audio")
    store.save("projects/1/audio/a.mp3", src)
    assert store.get("projects/1/audio/a.mp3").read_bytes() == b"audio"
    assert src.exists()  # the source is left alone


def test_save_overwrites(store):
    store.save("a/b.txt", b"one")
    store.save("a/b.txt", b"two")
    assert store.get("a/b.txt").read_bytes() == b"two"


def test_get_missing_raises(store):
    with pytest.raises(FileNotFoundError):
        store.get("projects/1/audio/none.mp3")


def test_delete(store):
    store.save("a/b.txt", b"x")
    store.delete("a/b.txt")
    assert not store.exists("a/b.txt")


def test_delete_missing_is_fine(store):
    store.delete("a/never.txt")


@pytest.mark.parametrize(
    "key", ["../escape.txt", "a/../../escape.txt", "/abs.txt", "C:\\x.txt", "a\\b.txt", ""]
)
def test_bad_keys_rejected(store, key):
    with pytest.raises(ValueError):
        store.save(key, b"x")
    with pytest.raises(ValueError):
        store.get(key)
