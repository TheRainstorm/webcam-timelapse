"""水印叠加：在图片四角打时间戳"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from app.config import WatermarkConfig


def _parse_rgba(color_str: str) -> tuple[int, int, int, int]:
    """解析 rgba(r,g,b,a) 或颜色名"""
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", color_str)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    # 颜色名直接返回不透明
    return color_str  # type: ignore[return-value]


def apply_watermark(img: Image.Image, cfg: WatermarkConfig, ts: datetime) -> Image.Image:
    if not cfg.enabled:
        return img

    img = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text = ts.strftime(cfg.format)

    font_path = Path(cfg.font)
    try:
        font = ImageFont.truetype(str(font_path), cfg.size)
    except (IOError, OSError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    padding = 6
    W, H = img.size

    positions = {
        "top-left":     (padding, padding),
        "top-right":    (W - tw - padding * 2, padding),
        "bottom-left":  (padding, H - th - padding * 2),
        "bottom-right": (W - tw - padding * 2, H - th - padding * 2),
    }
    x, y = positions.get(cfg.position, positions["bottom-right"])

    # 背景矩形
    bg = _parse_rgba(cfg.bg_color)
    if isinstance(bg, tuple):
        draw.rectangle([x - padding, y - padding, x + tw + padding, y + th + padding], fill=bg)

    draw.text((x, y), text, font=font, fill=cfg.color)

    result = Image.alpha_composite(img, overlay)
    return result.convert("RGB")
