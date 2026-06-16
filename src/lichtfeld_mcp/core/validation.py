"""Validation helpers shared by scene-facing surfaces and adapters."""

from __future__ import annotations

from pathlib import Path

from lichtfeld_mcp.errors import InvalidPathError, UnsupportedUnitError


SUPPORTED_MEASUREMENT_UNITS = frozenset({"m", "cm", "mm"})


def normalize_scene_path(path: str | Path, *, label: str = "path") -> str:
    """Normalize a scene-related path and reject empty input."""

    raw_path = str(path).strip()
    if not raw_path:
        raise InvalidPathError(f"{label.capitalize()} must not be empty.")
    return str(Path(raw_path).expanduser())


def normalize_measurement_unit(unit: str) -> str:
    """Normalize and validate a measurement unit."""

    normalized = unit.lower().strip()
    if normalized not in SUPPORTED_MEASUREMENT_UNITS:
        raise UnsupportedUnitError(
            f"Unsupported measurement unit '{unit}'. Supported: {sorted(SUPPORTED_MEASUREMENT_UNITS)}"
        )
    return normalized
