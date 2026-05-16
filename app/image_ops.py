"""图片处理工具。"""
from __future__ import annotations

from PIL import Image

SUPPORTED_IMAGE_ROTATIONS = {-180, -90, 0, 90, 180}


try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    RESAMPLE_LANCZOS = Image.LANCZOS


def validate_image_rotation(rotation: int) -> int:
    if rotation not in SUPPORTED_IMAGE_ROTATIONS:
        raise ValueError("image rotation must be one of: -180, -90, 0, 90, 180")
    return rotation


def rotate_image(img: Image.Image, rotation: int) -> Image.Image:
    validate_image_rotation(rotation)
    if rotation == 0:
        return img
    return img.rotate(-rotation, expand=True)
