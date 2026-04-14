"""ffmpeg 合成每日延时视频"""
from __future__ import annotations
from dataclasses import dataclass
import logging
import subprocess
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

from PIL import Image

from app.config import CameraConfig, WatermarkConfig
from app.watermark import apply_watermark

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComposeOptions:
    video_fps: int | None = None
    watermark: WatermarkConfig | None = None


def _frame_timestamp(target_date: date, frame: Path) -> datetime:
    try:
        return datetime.strptime(f"{target_date.isoformat()} {frame.stem}", "%Y-%m-%d %H-%M-%S")
    except ValueError:
        return datetime.combine(target_date, time.min)


def _prepare_frames(
    frames: list[Path],
    target_date: date,
    watermark: WatermarkConfig | None,
    temp_dir: Path,
) -> list[Path]:
    if watermark is None or not watermark.enabled:
        return frames

    prepared: list[Path] = []
    for idx, frame in enumerate(frames):
        with Image.open(frame) as source:
            img = apply_watermark(source, watermark, _frame_timestamp(target_date, frame))
        out = temp_dir / f"{idx:08d}.jpg"
        img.save(out, "JPEG", quality=90)
        prepared.append(out)
    return prepared


def compose_video(
    cam: CameraConfig,
    target_date: date | None = None,
    options: ComposeOptions | None = None,
) -> Path | None:
    """将指定日期的快照合成为 MP4，默认合成昨天"""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    if options is None:
        options = ComposeOptions()

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
    video_fps = options.video_fps or cam.video_fps
    watermark = options.watermark if options.watermark is not None else cam.watermark

    list_path = ""

    try:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            video_frames = _prepare_frames(frames, target_date, watermark, temp_dir)

            # 写帧列表文件
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
                list_path = f.name
                for frame in video_frames:
                    f.write(f"file '{frame.resolve()}'\n")
                    f.write(f"duration {1 / video_fps}\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", list_path,
                "-vf", f"fps={video_fps}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(output),
            ]

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
        if list_path:
            Path(list_path).unlink(missing_ok=True)
