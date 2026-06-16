"""Measurement MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_scene_api


def measure_distance(
    ax: float,
    ay: float,
    az: float,
    bx: float,
    by: float,
    bz: float,
    unit: str = "m",
) -> dict:
    """Measure a 3D distance between two points."""

    return get_scene_api().measure_distance(ax=ax, ay=ay, az=az, bx=bx, by=by, bz=bz, unit=unit).model_dump()
