"""配置加载与层级合并"""
from __future__ import annotations
import re
from typing import Optional
import yaml
from pydantic import BaseModel, field_validator, model_validator

SUPPORTED_VIDEO_ENCODERS = {
    "libx264",
    "h264_vaapi",
    "hevc_vaapi",
    "h264_nvenc",
}


class WatermarkConfig(BaseModel):
    enabled: bool = True
    position: str = "bottom-right"
    font: str = "fonts/NotoSansMono-Regular.ttf"
    size: int = 24
    color: str = "white"
    bg_color: str = "rgba(0,0,0,128)"
    format: str = "%Y-%m-%d %H:%M:%S"


class DaylightConfig(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = "Asia/Shanghai"
    torch_on_url: Optional[str] = None
    torch_off_url: Optional[str] = None
    disable_night_snapshots: bool = False

    @model_validator(mode="after")
    def validate_daylight(self) -> "DaylightConfig":
        needs_location = self.disable_night_snapshots or self.torch_on_url or self.torch_off_url
        if needs_location and (self.latitude is None or self.longitude is None):
            raise ValueError("daylight.latitude and daylight.longitude are required when daylight rules are enabled")
        if (self.torch_on_url is None) != (self.torch_off_url is None):
            raise ValueError("daylight.torch_on_url and daylight.torch_off_url must be configured together")
        return self


class CameraConfig(BaseModel):
    name: str
    snapshot_url: str
    stream_url: Optional[str] = None
    output_dir: str
    active: bool = True
    interval: int = 30
    retention_days: int = 30
    video_fps: int = 60
    video_speed_factor: float = 1.0
    video_encoder: str = "libx264"
    video_quality: int = 23
    vaapi_device: str = "/dev/dri/renderD128"
    video_time: str = "00:05"
    watermark: WatermarkConfig = WatermarkConfig()
    daylight: DaylightConfig = DaylightConfig()

    @field_validator("video_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("video_time must be HH:MM format")
        return v

    @field_validator("video_encoder")
    @classmethod
    def validate_video_encoder(cls, v: str) -> str:
        if v not in SUPPORTED_VIDEO_ENCODERS:
            raise ValueError(f"video_encoder must be one of: {', '.join(sorted(SUPPORTED_VIDEO_ENCODERS))}")
        return v

    @field_validator("video_quality")
    @classmethod
    def validate_video_quality(cls, v: int) -> int:
        if not 0 <= v <= 51:
            raise ValueError("video_quality must be between 0 and 51")
        return v


class GlobalConfig(BaseModel):
    active: bool = True
    interval: int = 30
    retention_days: int = 30
    video_fps: int = 60
    video_speed_factor: float = 1.0
    video_encoder: str = "libx264"
    video_quality: int = 23
    vaapi_device: str = "/dev/dri/renderD128"
    video_time: str = "00:05"
    watermark: WatermarkConfig = WatermarkConfig()
    daylight: DaylightConfig = DaylightConfig()

    @field_validator("video_encoder")
    @classmethod
    def validate_video_encoder(cls, v: str) -> str:
        if v not in SUPPORTED_VIDEO_ENCODERS:
            raise ValueError(f"video_encoder must be one of: {', '.join(sorted(SUPPORTED_VIDEO_ENCODERS))}")
        return v

    @field_validator("video_quality")
    @classmethod
    def validate_video_quality(cls, v: int) -> int:
        if not 0 <= v <= 51:
            raise ValueError("video_quality must be between 0 and 51")
        return v


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
