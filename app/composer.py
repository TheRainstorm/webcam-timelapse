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

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    RESAMPLE_LANCZOS = Image.LANCZOS

from app.config import CameraConfig, WatermarkConfig
from app.daylight import frame_in_daylight
from app.watermark import apply_watermark

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComposeOptions:
    video_fps: int | None = None
    speed_multiplier: float | None = None
    video_encoder: str | None = None
    video_quality: int | None = None
    skip_night: bool = False
    watermark: WatermarkConfig | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None


def _frame_timestamp(target_date: date, frame: Path) -> datetime:
    try:
        return datetime.strptime(f"{target_date.isoformat()} {frame.stem}", "%Y-%m-%d %H-%M-%S")
    except ValueError:
        return datetime.combine(target_date, time.min)


def _prepare_frames(
    frames: list[tuple[date, Path]],
    watermark: WatermarkConfig | None,
    temp_dir: Path,
    target_size: tuple[int, int],
) -> list[Path]:
    prepared: list[Path] = []
    for idx, (frame_date, frame) in enumerate(frames):
        out = temp_dir / f"{idx:08d}.jpg"
        with Image.open(frame) as probe:
            frame_size = probe.size
        needs_render = (watermark is not None and watermark.enabled) or frame_size != target_size
        if needs_render:
            with Image.open(frame) as source:
                img = source
                if watermark is not None and watermark.enabled:
                    img = apply_watermark(img, watermark, _frame_timestamp(frame_date, frame))
                if img.size != target_size:
                    img = img.resize(target_size, RESAMPLE_LANCZOS)
                if img.mode != "RGB":
                    img = img.convert("RGB")
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


def _filter_frames_by_datetime(
    frames: list[tuple[date, Path]],
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[tuple[date, Path]]:
    if start_at is None and end_at is None:
        return frames
    filtered: list[tuple[date, Path]] = []
    for frame_date, frame in frames:
        ts = _frame_timestamp(frame_date, frame)
        if start_at is not None and ts < start_at:
            continue
        if end_at is not None and ts > end_at:
            continue
        filtered.append((frame_date, frame))
    return filtered


def _filter_daylight_frames(cam: CameraConfig, frames: list[tuple[date, Path]]) -> list[tuple[date, Path]]:
    if not frames:
        return frames
    filtered = [
        (frame_date, frame)
        for frame_date, frame in frames
        if frame_in_daylight(cam, frame_date, frame.name)
    ]
    return filtered


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


def datetime_range_video_stem(start_at: datetime, end_at: datetime) -> str:
    return f"range-{start_at.strftime('%Y-%m-%dT%H-%M-%S')}_{end_at.strftime('%Y-%m-%dT%H-%M-%S')}"


def _ffmpeg_video_args(cam: CameraConfig, video_encoder: str, video_quality: int, video_fps: int) -> list[str]:
    gop_size = max(30, video_fps * 2)
    if video_encoder == "libx264":
        return [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", str(video_quality),
            "-pix_fmt", "yuv420p",
            "-g", str(gop_size),
        ]
    if video_encoder in {"h264_vaapi", "hevc_vaapi"}:
        return [
            "-vaapi_device", cam.vaapi_device,
            "-vf", "format=nv12,hwupload",
            "-c:v", video_encoder,
            "-qp", str(video_quality),
            "-g", str(gop_size),
        ]
    if video_encoder == "h264_nvenc":
        return [
            "-c:v", "h264_nvenc",
            "-preset", "p5",
            "-rc:v", "vbr",
            "-cq:v", str(video_quality),
            "-b:v", "0",
            "-pix_fmt", "yuv420p",
            "-g", str(gop_size),
        ]
    raise ValueError(f"Unsupported video encoder: {video_encoder}")


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
    frames = _filter_frames_by_datetime(frames, options.start_datetime, options.end_datetime)
    if options.skip_night:
        frames = _filter_daylight_frames(cam, frames)
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
    stem = (
        datetime_range_video_stem(options.start_datetime, options.end_datetime)
        if options.start_datetime is not None and options.end_datetime is not None
        else period_video_stem(target_date, period, start_date, end_date)
    )
    output = video_dir / f"{stem}.mp4"
    video_fps = options.video_fps or cam.video_fps
    speed_multiplier = options.speed_multiplier or cam.interval * video_fps * cam.video_speed_factor
    video_encoder = options.video_encoder or cam.video_encoder
    video_quality = options.video_quality if options.video_quality is not None else cam.video_quality
    watermark = options.watermark if options.watermark is not None else cam.watermark

    try:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            sampled_frames = _select_frames(frames, cam.interval, video_fps, speed_multiplier)
            with Image.open(sampled_frames[0][1]) as first_frame:
                target_size = first_frame.size
            _prepare_frames(sampled_frames, watermark, temp_dir, target_size)

            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(video_fps),
                "-i", str(temp_dir / "%08d.jpg"),
                *_ffmpeg_video_args(cam, video_encoder, video_quality, video_fps),
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
