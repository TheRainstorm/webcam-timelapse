"""APScheduler 定时任务：抓帧 + 每日合成 + 清理"""
from __future__ import annotations
import asyncio
from datetime import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.camera_state import is_camera_active
from app.capture import capture_snapshot
from app.cleaner import clean_snapshots
from app.composer import compose_video
from app.config import CameraConfig
from app.daylight import has_daylight_rules, is_daylight, reconcile_torch

logger = logging.getLogger(__name__)


def build_scheduler(cameras: list[CameraConfig]) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    for cam in cameras:
        # 定时抓帧
        scheduler.add_job(
            _capture_job,
            "interval",
            seconds=cam.interval,
            args=[cam],
            id=f"capture_{cam.name}",
            max_instances=1,
        )

        # 每日视频合成
        h, m = cam.video_time.split(":")
        scheduler.add_job(
            _compose_job,
            "cron",
            hour=int(h),
            minute=int(m),
            args=[cam],
            id=f"compose_{cam.name}",
        )

        # 每日清理（凌晨 01:00）
        scheduler.add_job(
            _clean_job,
            "cron",
            hour=1,
            minute=0,
            args=[cam],
            id=f"clean_{cam.name}",
        )

        if has_daylight_rules(cam):
            scheduler.add_job(
                _daylight_job,
                "interval",
                minutes=1,
                args=[cam],
                id=f"daylight_{cam.name}",
                max_instances=1,
                next_run_time=datetime.now(),
            )

    return scheduler


async def _capture_job(cam: CameraConfig) -> None:
    if not is_camera_active(cam):
        logger.info("[%s] 已关闭，跳过抓帧", cam.name)
        return
    if has_daylight_rules(cam) and cam.daylight.disable_night_snapshots and not is_daylight(cam):
        logger.info("[%s] 夜间跳过抓帧", cam.name)
        return
    await capture_snapshot(cam)


async def _compose_job(cam: CameraConfig) -> None:
    if not is_camera_active(cam):
        logger.info("[%s] 已关闭，跳过视频合成", cam.name)
        return
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, compose_video, cam, None)


async def _clean_job(cam: CameraConfig) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, clean_snapshots, cam)


async def _daylight_job(cam: CameraConfig) -> None:
    await reconcile_torch(cam)
