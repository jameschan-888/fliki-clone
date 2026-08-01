"""rev35 阶段 2 P0.5: render request body Pydantic models.

Centralizes 2 endpoint request body types, easy for router modules to import +
main.py to re-export.

Tests access these via main.RenderCreateBody / main.RenderCancelBody (getattr pattern),
so these types must also be visible at main module top-level - satisfied by main.py
re-exporting `from models.render import ...`.
"""
from pydantic import BaseModel, Field


class RenderCreateBody(BaseModel):
    """POST /render.create request body.

    playback_id: required, from workflow_draft / scene_draft.
    resolution: 720p / 1080p, default 720p.
    extension: mp4 / mov, default mp4.
    engine: remotion / ffmpeg, default remotion.
    renderer: local / docker / gke / cloud, default local.
    props_path: optional; when missing, router uses DATA_DIR/props/<playback_id>.json.
    """
    playback_id: str
    resolution: str = "720p"
    extension: str = "mp4"
    engine: str = "remotion"
    renderer: str = "local"
    props_path: str | None = None


class RenderCancelBody(BaseModel):
    """POST /render.cancel request body: jobId alias -> job_id."""
    model_config = {"populate_by_name": True}
    job_id: str = Field(alias="jobId")
