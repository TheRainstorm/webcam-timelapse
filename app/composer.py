"""ffmpeg 合成每日延时视频"""
from __future__ import annotations
import logging
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

from app.config import CameraConfig

logger = logging.getLogger(__name__)


def compose_video(cam: CameraConfig, target_date: date | None = None) -> Path | None:
    """将指定日期的快照合成为 MP4，默认合成昨天"""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    date_str = target_date.strftime("%Y-%m-%d")
    snap_dir = Path(cam.output_dir) / "snapshots" / date_str
    if not snap_dir.exists():
        logger.warning("[%s] 快照目录不存在: %s", cam.name, snap_dir)
        return None

    frames = sorted(snap_dir.glob("*.jpg"))
    if not frames:
        logger.warning("[%s] 无快照帧: %s", cam.name, snap_dir)
        return None

    video_dir = Path(cam.output_dir) / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    output = video_dir / f"{date_str}.mp4"

    # 写帧列表文件
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        list_path = f.name
        for frame in frames:
            f.write(f"file '{frame.resolve()}'\n")
            f.write(f"duration {1 / cam.video_fps}\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-vf", f"fps={cam.video_fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error("[%s] ffmpeg 失败: %s", cam.name, result.stderr[-500:])
            return None
        logger.info("[%s] 视频合成完成: %s", cam.name, output)
        return output
    except Exception as e:
        logger.error("[%s] 合成异常: %s", cam.name, e)
        return None
    finally:
        Path(list_path).unlink(missing_ok=True)
