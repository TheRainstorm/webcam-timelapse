"""RESTful API 路由"""
from __future__ import annotations
import asyncio
import os
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.capture import capture_snapshot
from app.composer import ComposeOptions, compose_video
from app.config import CameraConfig

router = APIRouter(prefix="/api")

# 由 main.py 注入
_cameras: list[CameraConfig] = []


def init_router(cameras: list[CameraConfig]) -> None:
    _cameras.clear()
    _cameras.extend(cameras)


def _get_cam(name: str) -> CameraConfig:
    for c in _cameras:
        if c.name == name:
            return c
    raise HTTPException(404, f"Camera '{name}' not found")


@router.get("/cameras")
async def list_cameras() -> list[dict[str, Any]]:
    result = []
    for cam in _cameras:
        snap_root = Path(cam.output_dir) / "snapshots"
        today_str = date.today().isoformat()
        today_dir = snap_root / today_str
        today_count = len(list(today_dir.glob("*.jpg"))) if today_dir.exists() else 0

        # 最新快照
        latest = None
        if snap_root.exists():
            all_snaps = sorted(snap_root.rglob("*.jpg"))
            if all_snaps:
                latest = str(all_snaps[-1].relative_to(Path(cam.output_dir)))

        result.append({
            "name": cam.name,
            "snapshot_url": cam.snapshot_url,
            "stream_url": cam.stream_url,
            "today_count": today_count,
            "latest_snapshot": latest,
            "video_fps": cam.video_fps,
            "watermark": cam.watermark.model_dump(),
        })
    return result


@router.get("/cameras/{name}/snapshots")
async def list_snapshots(name: str) -> dict[str, Any]:
    cam = _get_cam(name)
    snap_root = Path(cam.output_dir) / "snapshots"
    dates: dict[str, list[str]] = {}
    if snap_root.exists():
        for d in sorted(snap_root.iterdir()):
            if d.is_dir():
                frames = sorted(f.name for f in d.glob("*.jpg"))
                if frames:
                    dates[d.name] = frames
    return {"camera": name, "dates": dates}


@router.get("/cameras/{name}/videos")
async def list_videos(name: str) -> dict[str, Any]:
    cam = _get_cam(name)
    video_dir = Path(cam.output_dir) / "videos"
    videos = []
    if video_dir.exists():
        for v in sorted(video_dir.glob("*.mp4")):
            videos.append({
                "date": v.stem,
                "filename": v.name,
                "size": v.stat().st_size,
            })
    return {"camera": name, "videos": videos}


@router.delete("/cameras/{name}/videos/{video_date}")
async def delete_video(name: str, video_date: str) -> dict[str, str]:
    cam = _get_cam(name)
    video_path = Path(cam.output_dir) / "videos" / f"{video_date}.mp4"
    if not video_path.exists():
        raise HTTPException(404, "Video not found")
    video_path.unlink()
    return {"status": "deleted", "date": video_date}


@router.post("/cameras/{name}/trigger")
async def trigger_capture(name: str) -> dict[str, Any]:
    cam = _get_cam(name)
    path = await capture_snapshot(cam)
    if path is None:
        raise HTTPException(502, "Capture failed")
    return {"status": "ok", "path": str(path)}


@router.post("/cameras/{name}/compose")
async def trigger_compose(
    name: str,
    target_date: str | None = None,
    video_fps: int | None = None,
    watermark_enabled: bool | None = None,
    watermark_position: str | None = None,
    watermark_size: int | None = None,
) -> dict[str, Any]:
    cam = _get_cam(name)
    d = date.fromisoformat(target_date) if target_date else None
    if video_fps is not None and not 1 <= video_fps <= 120:
        raise HTTPException(400, "video_fps must be between 1 and 120")
    if watermark_position is not None and watermark_position not in {
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
    }:
        raise HTTPException(400, "Invalid watermark_position")
    if watermark_size is not None and not 8 <= watermark_size <= 96:
        raise HTTPException(400, "watermark_size must be between 8 and 96")

    watermark = cam.watermark
    watermark_updates: dict[str, Any] = {}
    if watermark_enabled is not None:
        watermark_updates["enabled"] = watermark_enabled
    if watermark_position is not None:
        watermark_updates["position"] = watermark_position
    if watermark_size is not None:
        watermark_updates["size"] = watermark_size
    if watermark_updates:
        watermark = watermark.model_copy(update=watermark_updates)

    options = ComposeOptions(video_fps=video_fps, watermark=watermark)
    loop = asyncio.get_event_loop()
    path = await loop.run_in_executor(None, partial(compose_video, cam, d, options))
    if path is None:
        raise HTTPException(500, "Compose failed")
    return {"status": "ok", "path": str(path)}


@router.get("/cameras/{name}/snapshots/{snap_date}/{filename}")
async def get_snapshot_file(name: str, snap_date: str, filename: str) -> FileResponse:
    cam = _get_cam(name)
    path = Path(cam.output_dir) / "snapshots" / snap_date / filename
    if not path.exists() or path.suffix != ".jpg":
        raise HTTPException(404, "Not found")
    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/cameras/{name}/videos/{filename}")
async def get_video_file(name: str, filename: str) -> FileResponse:
    cam = _get_cam(name)
    path = Path(cam.output_dir) / "videos" / filename
    if not path.exists() or path.suffix != ".mp4":
        raise HTTPException(404, "Not found")
    return FileResponse(str(path), media_type="video/mp4")
