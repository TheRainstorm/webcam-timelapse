"""RESTful API 路由"""
from __future__ import annotations
import asyncio
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.capture import capture_snapshot
from app.composer import ComposeOptions, compose_video, period_bounds
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
            "interval": cam.interval,
            "video_fps": cam.video_fps,
            "video_speed_factor": cam.video_speed_factor,
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
            scope = "day"
            anchor_date: date | None = None
            label = v.stem
            if v.stem.startswith("week-"):
                scope = "week"
                try:
                    _, iso_year, iso_week = v.stem.split("-", 2)
                    anchor_date = date.fromisocalendar(int(iso_year), int(iso_week.removeprefix("W")), 1)
                    label = f"{iso_year} 第 {int(iso_week.removeprefix('W'))} 周"
                except ValueError:
                    anchor_date = None
            elif v.stem.startswith("month-"):
                scope = "month"
                try:
                    anchor_date = date.fromisoformat(f"{v.stem.removeprefix('month-')}-01")
                    label = anchor_date.strftime("%Y-%m")
                except ValueError:
                    anchor_date = None
            elif v.stem.startswith("range-"):
                scope = "range"
                try:
                    start_raw, end_raw = v.stem.removeprefix("range-").split("_", 1)
                    start_date = date.fromisoformat(start_raw)
                    end_date = date.fromisoformat(end_raw)
                    anchor_date = start_date
                    start_date_str = start_date.isoformat()
                    end_date_str = end_date.isoformat()
                    label = f"{start_date_str} ~ {end_date_str}"
                except ValueError:
                    anchor_date = None
            else:
                try:
                    anchor_date = date.fromisoformat(v.stem)
                    label = anchor_date.isoformat()
                except ValueError:
                    anchor_date = None

            if scope == "range" and anchor_date is not None:
                pass
            elif anchor_date is not None:
                start_date, end_date = period_bounds(anchor_date, scope)
                start_date_str = start_date.isoformat()
                end_date_str = end_date.isoformat()
            else:
                start_date_str = v.stem
                end_date_str = v.stem

            videos.append({
                "id": v.stem,
                "date": v.stem,
                "filename": v.name,
                "size": v.stat().st_size,
                "scope": scope,
                "label": label,
                "start_date": start_date_str,
                "end_date": end_date_str,
            })
    return {"camera": name, "videos": videos}


@router.delete("/cameras/{name}/videos/{video_id}")
async def delete_video(name: str, video_id: str) -> dict[str, str]:
    cam = _get_cam(name)
    video_path = Path(cam.output_dir) / "videos" / f"{video_id}.mp4"
    if not video_path.exists():
        raise HTTPException(404, "Video not found")
    video_path.unlink()
    return {"status": "deleted", "id": video_id}


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
    period: str = "day",
    start_date: str | None = None,
    end_date: str | None = None,
    video_fps: int | None = None,
    speed_multiplier: float | None = None,
    watermark_enabled: bool | None = None,
    watermark_position: str | None = None,
    watermark_size: int | None = None,
) -> dict[str, Any]:
    cam = _get_cam(name)
    d = date.fromisoformat(target_date) if target_date else None
    range_start = date.fromisoformat(start_date) if start_date else None
    range_end = date.fromisoformat(end_date) if end_date else None
    if period not in {"day", "week", "month", "range"}:
        raise HTTPException(400, "period must be one of: day, week, month, range")
    if period == "range" and (range_start is None or range_end is None):
        raise HTTPException(400, "start_date and end_date are required for period=range")
    if video_fps is not None and not 1 <= video_fps <= 240:
        raise HTTPException(400, "video_fps must be between 1 and 240")
    if speed_multiplier is not None and not 1 <= speed_multiplier <= 100000:
        raise HTTPException(400, "speed_multiplier must be between 1 and 100000")
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

    options = ComposeOptions(
        video_fps=video_fps,
        speed_multiplier=speed_multiplier,
        watermark=watermark,
    )
    loop = asyncio.get_event_loop()
    path = await loop.run_in_executor(
        None,
        partial(compose_video, cam, d, options, period, range_start, range_end),
    )
    if path is None:
        raise HTTPException(500, "Compose failed")
    return {"status": "ok", "path": str(path), "period": period}


@router.get("/cameras/{name}/snapshots/{snap_date}/{filename}")
async def get_snapshot_file(name: str, snap_date: str, filename: str) -> FileResponse:
    cam = _get_cam(name)
    path = Path(cam.output_dir) / "snapshots" / snap_date / filename
    if not path.exists() or path.suffix != ".jpg":
        raise HTTPException(404, "Not found")
    return FileResponse(str(path), media_type="image/jpeg")


def _iter_file_range(path: Path, start: int, end: int, chunk_size: int = 1024 * 1024):
    with path.open("rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/cameras/{name}/videos/{filename}")
async def get_video_file(name: str, filename: str, request: Request):
    cam = _get_cam(name)
    path = Path(cam.output_dir) / "videos" / filename
    if not path.exists() or path.suffix != ".mp4":
        raise HTTPException(404, "Not found")

    size = path.stat().st_size
    range_header = request.headers.get("range")
    headers = {"Accept-Ranges": "bytes"}
    if not range_header:
        headers["Content-Length"] = str(size)
        return FileResponse(str(path), media_type="video/mp4", headers=headers)

    try:
        unit, range_value = range_header.split("=", 1)
        if unit != "bytes":
            raise ValueError
        start_raw, end_raw = range_value.split("-", 1)
        if start_raw:
            start = int(start_raw)
            end = int(end_raw) if end_raw else size - 1
        else:
            suffix_size = int(end_raw)
            start = max(0, size - suffix_size)
            end = size - 1
        if start < 0 or end >= size or start > end:
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=416,
            detail="Invalid range",
            headers={"Content-Range": f"bytes */{size}"},
        )

    headers.update({
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Content-Length": str(end - start + 1),
    })
    return StreamingResponse(
        _iter_file_range(path, start, end),
        status_code=206,
        media_type="video/mp4",
        headers=headers,
    )
