"""配置加载与层级合并"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, field_validator


class WatermarkConfig(BaseModel):
    enabled: bool = True
    position: str = "bottom-right"
    font: str = "fonts/NotoSansMono-Regular.ttf"
    size: int = 24
    color: str = "white"
    bg_color: str = "rgba(0,0,0,128)"
    format: str = "%Y-%m-%d %H:%M:%S"


class CameraConfig(BaseModel):
    name: str
    snapshot_url: str
    stream_url: Optional[str] = None
    output_dir: str
    interval: int = 30
    retention_days: int = 30
    video_fps: int = 60
    video_speed_factor: float = 1.0
    video_time: str = "00:05"
    watermark: WatermarkConfig = WatermarkConfig()

    @field_validator("video_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("video_time must be HH:MM format")
        return v


class GlobalConfig(BaseModel):
    interval: int = 30
    retention_days: int = 30
    video_fps: int = 60
    video_speed_factor: float = 1.0
    video_time: str = "00:05"
    watermark: WatermarkConfig = WatermarkConfig()


class AppConfig(BaseModel):
    global_: GlobalConfig
    cameras: list[CameraConfig]


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典，override 优先"""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(path: str = "config.yaml") -> tuple[GlobalConfig, list[CameraConfig]]:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    global_raw = raw.get("global", {})
    global_cfg = GlobalConfig(**global_raw)
    global_dict = global_cfg.model_dump()

    cameras: list[CameraConfig] = []
    for cam_raw in raw.get("cameras", []):
        merged = _deep_merge(global_dict, cam_raw)
        # watermark 单独合并
        if "watermark" in cam_raw:
            merged["watermark"] = _deep_merge(
                global_dict.get("watermark", {}), cam_raw["watermark"]
            )
        cameras.append(CameraConfig(**merged))

    return global_cfg, cameras
