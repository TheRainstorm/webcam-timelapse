"""摄像头运行状态：控制是否允许抓帧与合成。"""
from __future__ import annotations

from app.config import CameraConfig

_camera_active: dict[str, bool] = {}


def init_camera_state(cameras: list[CameraConfig]) -> None:
    _camera_active.clear()
    for cam in cameras:
        _camera_active[cam.name] = cam.active


def is_camera_active(cam_or_name: CameraConfig | str) -> bool:
    name = cam_or_name.name if isinstance(cam_or_name, CameraConfig) else cam_or_name
    return _camera_active.get(name, True)


def set_camera_active(name: str, active: bool) -> bool:
    _camera_active[name] = active
    return active
