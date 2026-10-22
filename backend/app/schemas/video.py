"""The video JSON: the contract between the pipeline, the editor and the renderer.

Files are referenced by storage key (for example ``projects/42/clips/scene_03.mp4``),
never by absolute path.
"""

from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Words may overlap by a hair because Whisper timestamps are not exact.
WORD_OVERLAP_TOLERANCE_S = 0.05


def _check_key(key: str) -> str:
    if not key or key.startswith("/") or "\\" in key or ":" in key:
        raise ValueError("storage key must be a relative path with forward slashes")
    if any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError("storage key must not contain empty, '.' or '..' parts")
    return key


StorageKey = Annotated[str, AfterValidator(_check_key)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MediaSource(str, Enum):
    stock = "stock"
    generated = "generated"
    uploaded = "uploaded"


class MediaKind(str, Enum):
    image = "image"
    video = "video"


class MotionPreset(str, Enum):
    zoom_in = "zoom_in"
    zoom_out = "zoom_out"
    pan_left = "pan_left"
    pan_right = "pan_right"
    pan_up = "pan_up"
    pan_down = "pan_down"
    none = "none"


class CaptionMode(str, Enum):
    karaoke = "karaoke"  # the current word is highlighted
    plain = "plain"


class OutputSettings(_Model):
    width: int = Field(1080, gt=0)
    height: int = Field(1920, gt=0)
    fps: int = Field(30, gt=0)

    @model_validator(mode="after")
    def _portrait(self):
        if self.height <= self.width:
            raise ValueError("output must be portrait (height greater than width)")
        return self


class CaptionStyle(_Model):
    mode: CaptionMode = CaptionMode.karaoke
    font_family: str = "Inter"
    font_size: int = Field(72, gt=0)
    color: str = Field("#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    highlight_color: str = Field("#FFD400", pattern=r"^#[0-9A-Fa-f]{6}$")
    outline_color: str = Field("#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    # Vertical position of the caption block, 0 = top and 1 = bottom of the frame.
    # Kept above the bottom edge, which the Shorts interface covers.
    position_y: float = Field(0.68, ge=0, le=1)
    max_words_per_line: int = Field(4, gt=0)


class Music(_Model):
    key: StorageKey
    volume: float = Field(0.15, ge=0, le=1)
    duck_under_voice: bool = True


class Audio(_Model):
    key: StorageKey
    duration_s: float = Field(gt=0)


class Word(_Model):
    text: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end <= self.start:
            raise ValueError("word end must be after its start")
        return self


class Captions(_Model):
    text: str
    words: list[Word] = []
    style: CaptionStyle | None = None  # per-scene override of the video style

    @field_validator("words")
    @classmethod
    def _sorted(cls, words: list[Word]) -> list[Word]:
        for prev, cur in zip(words, words[1:]):
            if cur.start < prev.end - WORD_OVERLAP_TOLERANCE_S:
                raise ValueError(
                    f"words overlap or are out of order ('{prev.text}' then '{cur.text}')"
                )
        return words


class Candidate(_Model):
    key: StorageKey
    source: MediaSource
    kind: MediaKind
    score: float | None = None  # CLIP similarity for stock candidates


class Media(_Model):
    source: MediaSource
    kind: MediaKind
    key: StorageKey
    attribution: str | None = None
    # Trim applies to video clips only; a still image has no length of its own.
    trim_start_s: float = Field(0, ge=0)
    trim_end_s: float | None = Field(None, gt=0)
    candidates: list[Candidate] = []

    @model_validator(mode="after")
    def _trim(self):
        if self.kind == MediaKind.image and (self.trim_start_s or self.trim_end_s):
            raise ValueError("a still image cannot be trimmed")
        if self.trim_end_s is not None and self.trim_end_s <= self.trim_start_s:
            raise ValueError("trim_end_s must be greater than trim_start_s")
        return self


class FocalPoint(_Model):
    # Fractions of the frame. The default sits in the upper-middle, clear of captions.
    x: float = Field(0.5, ge=0, le=1)
    y: float = Field(0.4, ge=0, le=1)


class Motion(_Model):
    preset: MotionPreset = MotionPreset.zoom_in
    focal_point: FocalPoint = FocalPoint()


class Scene(_Model):
    id: str = Field(min_length=1)
    script_line: str = Field(min_length=1)
    visual_prompt: str = ""
    # Audio, media and captions are empty until the pipeline fills them in.
    audio: Audio | None = None
    pad_s: float = Field(0.3, ge=0)  # silence added after the voiceover
    media: Media | None = None
    motion: Motion = Motion()
    captions: Captions | None = None

    @property
    def duration_s(self) -> float | None:
        """Scene length: the voiceover plus a short pad. None until audio exists."""
        if self.audio is None:
            return None
        return self.audio.duration_s + self.pad_s

    @model_validator(mode="after")
    def _words_inside_audio(self):
        if self.audio and self.captions:
            for word in self.captions.words:
                if word.end > self.audio.duration_s + WORD_OVERLAP_TOLERANCE_S:
                    raise ValueError(
                        f"caption word '{word.text}' ends after the audio does"
                    )
        return self


class Video(_Model):
    version: Literal[1] = 1
    output: OutputSettings = OutputSettings()
    image_style_prefix: str = ""  # prepended to every image generation prompt
    caption_style: CaptionStyle = CaptionStyle()
    music: Music | None = None
    scenes: list[Scene] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [s.id for s in self.scenes]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate scene ids: {', '.join(dupes)}")
        return self

    @property
    def total_duration_s(self) -> float | None:
        durations = [s.duration_s for s in self.scenes]
        if any(d is None for d in durations):
            return None
        return sum(durations)


class VideoValidationError(ValueError):
    """Raised with a readable, line-per-problem message."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


def format_errors(exc: ValidationError) -> list[str]:
    problems = []
    for err in exc.errors():
        where = "".join(
            f"[{p}]" if isinstance(p, int) else f".{p}" for p in err["loc"]
        ).lstrip(".") or "video"
        msg = err["msg"].removeprefix("Value error, ")
        problems.append(f"{where}: {msg}")
    return problems


def parse_video(data: dict | str | bytes) -> Video:
    """Validate raw JSON (or a dict) into a Video, or raise VideoValidationError."""
    try:
        if isinstance(data, dict):
            return Video.model_validate(data)
        return Video.model_validate_json(data)
    except ValidationError as exc:
        raise VideoValidationError(format_errors(exc)) from exc


def validate_for_render(video: Video, file_exists) -> None:
    """Stricter check run before rendering: every scene is complete and its files exist.

    ``file_exists`` is a callable taking a storage key and returning a bool.
    """
    problems = []
    for i, scene in enumerate(video.scenes):
        at = f"scenes[{i}] ({scene.id})"
        if scene.audio is None:
            problems.append(f"{at}: no voiceover audio")
        elif not file_exists(scene.audio.key):
            problems.append(f"{at}: audio file missing ({scene.audio.key})")
        if scene.media is None:
            problems.append(f"{at}: no media chosen")
        elif not file_exists(scene.media.key):
            problems.append(f"{at}: media file missing ({scene.media.key})")
        if scene.captions is None:
            problems.append(f"{at}: no captions")
    if video.music and not file_exists(video.music.key):
        problems.append(f"music: file missing ({video.music.key})")
    if problems:
        raise VideoValidationError(problems)
