"""The input to the pipeline: one script line and one visual prompt per scene."""

from pydantic import BaseModel, ConfigDict, Field


class SceneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_line: str = Field(min_length=1)
    visual_prompt: str = Field(min_length=1)


class ScenesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenes: list[SceneInput] = Field(min_length=1)
