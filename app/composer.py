"""ffmpeg 合成按日/周/月的延时视频"""
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
    frames: list[tuple[date, Path]],
    watermark: WatermarkConfig | None,
    temp_dir: Path,
) -> list[Path]:
    prepared: list[Path] = []
    for idx, (frame_date, frame) in enumerate(frames):
        out = temp_dir / f"{idx:08d}.jpg"
        if watermark is not None and watermark.enabled:
            with Image.open(frame) as source:
                img = apply_watermark(source, watermark, _frame_timestamp(frame_date, frame))
            img.save(out, "JPEG", quality=90)
        else:
            try:
                out.symlink_to(frame.resolve())
            except OSError:
                shutil.copy2(frame, out)
        prepared.append(out)
    return prepared


def _select_frames(
    frames: list[tuple[date, Path]],
    snapshot_interval: int,
    video_fps: int,
    speed_multiplier: float,
) -> list[tuple[date, Path]]:
    output_count = round(len(frames) * snapshot_interval * video_fps / speed_multiplier)
    output_count = max(1, output_count)
    if output_count == 1:
        return [frames[0]]
    if len(frames) == 1:
        return [frames[0]] * output_count

    last_idx = len(frames) - 1
    return [frames[round(i * last_idx / (output_count - 1))] for i in range(output_count)]


def _week_range(anchor_date: date) -> tuple[date, date]:
    start = anchor_date - timedelta(days=anchor_date.weekday())
    end = start + timedelta(days=6)
    return start, end


def _month_range(anchor_date: date) -> tuple[date, date]:
    start = anchor_date.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    end = next_month - timedelta(days=1)
    return start, end


def _range_dates(start_date: date, end_date: date) -> list[date]:
    total_days = (end_date - start_date).days + 1
    return [start_date + timedelta(days=offset) for offset in range(total_days)]


def _collect_frames(cam: CameraConfig, target_dates: list[date]) -> list[tuple[date, Path]]:
    root = Path(cam.output_dir) / "snapshots"
    frames: list[tuple[date, Path]] = []
    for target_date in target_dates:
        snap_dir = root / target_date.isoformat()
        if not snap_dir.exists():
            continue
        for frame in sorted(snap_dir.glob("*.jpg")):
            frames.append((target_date, frame))
    return frames


def period_bounds(anchor_date: date, period: str) -> tuple[date, date]:
    if period == "day":
        return anchor_date, anchor_date
    if period == "week":
        return _week_range(anchor_date)
    if period == "month":
        return _month_range(anchor_date)
    raise ValueError(f"Unsupported compose period: {period}")


def period_video_stem(anchor_date: date, period: str, start_date: date | None = None, end_date: date | None = None) -> str:
    if period == "day":
        return anchor_date.isoformat()
    if period == "week":
        iso_year, iso_week, _ = anchor_date.isocalendar()
        return f"week-{iso_year}-W{iso_week:02d}"
    if period == "month":
        return f"month-{anchor_date.strftime('%Y-%m')}"
    if period == "range" and start_date is not None and end_date is not None:
        return f"range-{start_date.isoformat()}_{end_date.isoformat()}"
    raise ValueError(f"Unsupported compose period: {period}")


def compose_video(
    cam: CameraConfig,
    target_date: date | None = None,
    options: ComposeOptions | None = None,
    period: str = "day",
    range_start: date | None = None,
    range_end: date | None = None,
) -> Path | None:
    """将指定日期所属的日/周/月或自定义区间快照合成为 MP4。"""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    if options is None:
        options = ComposeOptions()

    if period == "range":
        if range_start is None or range_end is None:
            raise ValueError("range_start and range_end are required when period='range'")
        start_date, end_date = sorted((range_start, range_end))
    else:
        start_date, end_date = period_bounds(target_date, period)
    frames = _collect_frames(cam, _range_dates(start_date, end_date))
    if not frames:
        logger.warning(
            "[%s] 无快照帧: period=%s, range=%s..%s",
            cam.name,
            period,
            start_date,
            end_date,
        )
        return None

    video_dir = Path(cam.output_dir) / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    output = video_dir / f"{period_video_stem(target_date, period, start_date, end_date)}.mp4"
    video_fps = options.video_fps or cam.video_fps
    speed_multiplier = options.speed_multiplier or cam.interval * video_fps * cam.video_speed_factor
    watermark = options.watermark if options.watermark is not None else cam.watermark

    try:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            sampled_frames = _select_frames(frames, cam.interval, video_fps, speed_multiplier)
            _prepare_frames(sampled_frames, watermark, temp_dir)

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
        logger.info("[%s] 视频合成完成: %s (%s %s..%s)", cam.name, output, period, start_date, end_date)
        return output
    except Exception as e:
        logger.error("[%s] 合成异常: %s", cam.name, e)
        return None
