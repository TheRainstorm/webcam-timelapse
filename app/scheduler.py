"""APScheduler 定时任务：抓帧 + 每日合成 + 清理"""
from __future__ import annotations
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.capture import capture_snapshot
from app.cleaner import clean_snapshots
from app.composer import compose_video
from app.config import CameraConfig

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

    return scheduler


async def _capture_job(cam: CameraConfig) -> None:
    await capture_snapshot(cam)


async def _compose_job(cam: CameraConfig) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, compose_video, cam, None)


async def _clean_job(cam: CameraConfig) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, clean_snapshots, cam)
