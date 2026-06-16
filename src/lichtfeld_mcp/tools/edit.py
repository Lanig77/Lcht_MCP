"""Crop and edit MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_adapter
from lichtfeld_mcp.schemas.common import Box3D, Vec3


def crop_by_box(
    min_x: float,
    min_y: float,
    min_z: float,
    max_x: float,
    max_y: float,
    max_z: float,
    keep_inside: bool = True,
) -> dict:
    """Crop the scene by an axis-aligned 3D box."""

    box = Box3D(min=Vec3(x=min_x, y=min_y, z=min_z), max=Vec3(x=max_x, y=max_y, z=max_z))
    return get_adapter().crop_by_box(box, keep_inside=keep_inside).model_dump()


def crop_by_height(z_min: float | None = None, z_max: float | None = None, keep_inside: bool = True) -> dict:
    """Crop splats using a vertical range."""

    return get_adapter().crop_by_height(z_min=z_min, z_max=z_max, keep_inside=keep_inside).model_dump()
