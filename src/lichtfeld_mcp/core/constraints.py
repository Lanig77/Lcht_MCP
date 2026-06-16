"""Numeric normalization and validation helpers for scene operations."""

from __future__ import annotations

from typing import Literal

from lichtfeld_mcp.errors import InvalidParameterError


MIN_COLOR_VALUE = 0
MAX_COLOR_VALUE = 255
MAX_COLOR_TOLERANCE = 255
VALID_SELECTION_MODES = frozenset({"replace", "add", "subtract"})
SelectionMode = Literal["replace", "add", "subtract"]


def normalize_height_range(
    z_min: float | None,
    z_max: float | None,
) -> tuple[float | None, float | None]:
    """Return a stable lower/upper height range without forcing both bounds."""

    if z_min is None or z_max is None:
        return z_min, z_max
    if z_min <= z_max:
        return z_min, z_max
    return z_max, z_min


def validate_rgb_color(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Validate an RGB triplet."""

    return (
        _validate_color_value("r", r),
        _validate_color_value("g", g),
        _validate_color_value("b", b),
    )


def validate_color_tolerance(tolerance: int) -> int:
    """Validate color-selection tolerance."""

    if not MIN_COLOR_VALUE <= tolerance <= MAX_COLOR_TOLERANCE:
        raise InvalidParameterError(
            f"tolerance must be between {MIN_COLOR_VALUE} and {MAX_COLOR_TOLERANCE}."
        )
    return tolerance


def validate_max_splats(max_splats: int | None) -> int | None:
    """Validate an optional max_splats override."""

    if max_splats is None:
        return None
    if max_splats <= 0:
        raise InvalidParameterError("max_splats must be greater than 0.")
    return max_splats


def _validate_color_value(channel: str, value: int) -> int:
    if not MIN_COLOR_VALUE <= value <= MAX_COLOR_VALUE:
        raise InvalidParameterError(
            f"{channel} must be between {MIN_COLOR_VALUE} and {MAX_COLOR_VALUE}."
        )
    return value


def validate_selection_mode(mode: str) -> str:
    """Normalize and validate a selection mode."""

    normalized = mode.lower().strip()
    if normalized not in VALID_SELECTION_MODES:
        supported = ", ".join(sorted(VALID_SELECTION_MODES))
        raise InvalidParameterError(
            f"selection mode must be one of: {supported}."
        )
    return normalized
