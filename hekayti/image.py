"""Technical image metadata validation without decoding or calling providers."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ImageMetadata:
    width: int
    height: int
    format: str
    color_mode: str = "RGB"
    has_alpha: bool = False
    byte_size: int | None = None


@dataclass(frozen=True)
class ImageValidation:
    valid: bool
    errors: tuple[str, ...] = ()


def validate_image_metadata(metadata: ImageMetadata, *, min_width: int = 256,
                            min_height: int = 256, max_bytes: int | None = None,
                            allowed_formats: Iterable[str] = ("PNG", "JPEG", "WEBP"),
                            allowed_modes: Iterable[str] = ("RGB", "RGBA")) -> ImageValidation:
    errors: list[str] = []
    formats = {item.upper() for item in allowed_formats}
    modes = {item.upper() for item in allowed_modes}
    if metadata.width < min_width or metadata.height < min_height:
        errors.append("dimensions below minimum")
    if metadata.format.upper() not in formats:
        errors.append("unsupported format")
    if metadata.color_mode.upper() not in modes:
        errors.append("unsupported color mode")
    if max_bytes is not None and metadata.byte_size is not None and metadata.byte_size > max_bytes:
        errors.append("file size exceeds maximum")
    if metadata.width <= 0 or metadata.height <= 0:
        errors.append("dimensions must be positive")
    return ImageValidation(not errors, tuple(errors))

