"""Measurement MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_adapter
from lichtfeld_mcp.schemas.common import Vec3


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

    return get_adapter().measure_distance(Vec3(x=ax, y=ay, z=az), Vec3(x=bx, y=by, z=bz), unit=unit).model_dump()
