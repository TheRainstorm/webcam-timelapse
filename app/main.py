"""FastAPI 应用入口"""
from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import init_router, router
from app.config import load_config
from app.scheduler import build_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.yaml")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global_cfg, cameras = load_config(CONFIG_PATH)
    init_router(cameras)

    scheduler = build_scheduler(cameras)
    scheduler.start()
    logging.info("调度器已启动，摄像头数量: %d", len(cameras))

    yield

    scheduler.shutdown()


app = FastAPI(title="Webcam Timelapse", lifespan=lifespan)
app.include_router(router)

static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
