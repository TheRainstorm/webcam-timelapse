"""过期快照清理"""
from __future__ import annotations
import logging
import shutil
from datetime import date, timedelta
from pathlib import Path

from app.config import CameraConfig

logger = logging.getLogger(__name__)


def clean_snapshots(cam: CameraConfig) -> int:
    """删除超过 retention_days 的快照目录，返回删除数量"""
    snap_root = Path(cam.output_dir) / "snapshots"
    if not snap_root.exists():
        return 0

    cutoff = date.today() - timedelta(days=cam.retention_days)
    removed = 0
    for d in snap_root.iterdir():
        if not d.is_dir():
            continue
        try:
            dir_date = date.fromisoformat(d.name)
        except ValueError:
            continue
        if dir_date < cutoff:
            shutil.rmtree(d)
            logger.info("[%s] 删除过期快照: %s", cam.name, d)
            removed += 1
    return removed
