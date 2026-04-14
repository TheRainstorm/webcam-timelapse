"""异步抓帧：从 snapshot_url 拉取 JPEG 并保存"""
from __future__ import annotations
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from app.config import CameraConfig

logger = logging.getLogger(__name__)


async def capture_snapshot(cam: CameraConfig) -> Path | None:
    """抓取一帧原始快照，保存到 output_dir/snapshots/YYYY-MM-DD/HH-MM-SS.jpg"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M-%S")

    save_dir = Path(cam.output_dir) / "snapshots" / date_str
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{time_str}.jpg"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(cam.snapshot_url)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
    except Exception as e:
        logger.warning("[%s] 抓帧失败: %s", cam.name, e)
        return None

    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(save_path, "JPEG", quality=90)
    logger.debug("[%s] 保存快照: %s", cam.name, save_path)
    return save_path
