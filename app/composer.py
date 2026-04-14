"""ffmpeg 合成每日延时视频"""
from __future__ import annotations
from dataclasses import dataclass
import logging
import shutil
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
    speed_multiplier: float | None = None
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
    prepared: list[Path] = []
    for idx, frame in enumerate(frames):
        out = temp_dir / f"{idx:08d}.jpg"
        if watermark is not None and watermark.enabled:
            with Image.open(frame) as source:
                img = apply_watermark(source, watermark, _frame_timestamp(target_date, frame))
            img.save(out, "JPEG", quality=90)
        else:
            try:
                out.symlink_to(frame.resolve())
            except OSError:
                shutil.copy2(frame, out)
        prepared.append(out)
    return prepared


def _select_frames(
    frames: list[Path],
    snapshot_interval: int,
    video_fps: int,
    speed_multiplier: float,
) -> list[Path]:
    output_count = round(len(frames) * snapshot_interval * video_fps / speed_multiplier)
    output_count = max(1, output_count)
    if output_count == 1:
        return [frames[0]]
    if len(frames) == 1:
        return [frames[0]] * output_count

    last_idx = len(frames) - 1
    return [frames[round(i * last_idx / (output_count - 1))] for i in range(output_count)]


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
    speed_multiplier = options.speed_multiplier or cam.interval * video_fps * cam.video_speed_factor
    watermark = options.watermark if options.watermark is not None else cam.watermark

    try:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            sampled_frames = _select_frames(frames, cam.interval, video_fps, speed_multiplier)
            _prepare_frames(sampled_frames, target_date, watermark, temp_dir)

            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(video_fps),
                "-i", str(temp_dir / "%08d.jpg"),
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
