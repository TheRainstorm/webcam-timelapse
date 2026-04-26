"""日出日落计算与补光灯控制"""
from __future__ import annotations

from datetime import date, datetime, time
import logging
from zoneinfo import ZoneInfo

import httpx
from astral import Observer
from astral.sun import sun

from app.config import CameraConfig

logger = logging.getLogger(__name__)

_sun_cache: dict[tuple[str, date], tuple[datetime, datetime]] = {}
_torch_state: dict[str, bool] = {}


def has_daylight_rules(cam: CameraConfig) -> bool:
    return (
        cam.daylight.enabled
        or cam.daylight.disable_night_snapshots
        or bool(cam.daylight.torch_on_url and cam.daylight.torch_off_url)
    )


def _local_now(cam: CameraConfig, now: datetime | None = None) -> datetime:
    tz = ZoneInfo(cam.daylight.timezone)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def sun_window(cam: CameraConfig, target_date: date) -> tuple[datetime, datetime]:
    key = (cam.name, target_date)
    cached = _sun_cache.get(key)
    if cached is not None:
        return cached

    values = sun(
        Observer(latitude=cam.daylight.latitude, longitude=cam.daylight.longitude),
        date=target_date,
        tzinfo=ZoneInfo(cam.daylight.timezone),
    )
    sunrise = values["sunrise"]
    sunset = values["sunset"]
    _sun_cache[key] = (sunrise, sunset)
    logger.info(
        "[%s] %s 日出 %s，日落 %s",
        cam.name,
        target_date.isoformat(),
        sunrise.strftime("%H:%M:%S"),
        sunset.strftime("%H:%M:%S"),
    )
    return sunrise, sunset


def frame_in_daylight(cam: CameraConfig, target_date: date, frame_name: str) -> bool:
    sunrise, sunset = sun_window(cam, target_date)
    base = str(frame_name).rsplit(".", 1)[0]
    try:
        frame_time = datetime.strptime(f"{target_date.isoformat()} {base}", "%Y-%m-%d %H-%M-%S")
        frame_dt = frame_time.replace(tzinfo=ZoneInfo(cam.daylight.timezone))
    except ValueError:
        frame_dt = datetime.combine(target_date, time.min, tzinfo=ZoneInfo(cam.daylight.timezone))
    return sunrise <= frame_dt < sunset


def is_daylight(cam: CameraConfig, now: datetime | None = None) -> bool:
    current = _local_now(cam, now)
    sunrise, sunset = sun_window(cam, current.date())
    return sunrise <= current < sunset


async def reconcile_torch(cam: CameraConfig) -> None:
    if not has_daylight_rules(cam):
        return
    if not cam.daylight.torch_on_url or not cam.daylight.torch_off_url:
        return

    should_on = not is_daylight(cam)
    previous = _torch_state.get(cam.name)
    if previous is should_on:
        return

    await set_torch(cam, should_on)


async def set_torch(cam: CameraConfig, enabled: bool) -> None:
    if not cam.daylight.torch_on_url or not cam.daylight.torch_off_url:
        raise ValueError("Torch URLs are not configured")

    url = cam.daylight.torch_on_url if enabled else cam.daylight.torch_off_url
    action = "开启" if enabled else "关闭"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url)
            resp.raise_for_status()
        _torch_state[cam.name] = enabled
        logger.info("[%s] 已%s补光灯", cam.name, action)
    except Exception as exc:
        logger.warning("[%s] %s补光灯失败: %s", cam.name, action, exc)
        raise
