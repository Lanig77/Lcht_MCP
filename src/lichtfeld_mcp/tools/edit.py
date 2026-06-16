"""Crop and edit MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_scene_service


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

    return get_scene_service().crop_by_box(
        min_x=min_x,
        min_y=min_y,
        min_z=min_z,
        max_x=max_x,
        max_y=max_y,
        max_z=max_z,
        keep_inside=keep_inside,
    ).model_dump()


def crop_by_height(z_min: float | None = None, z_max: float | None = None, keep_inside: bool = True) -> dict:
    """Crop splats using a vertical range."""

    return get_scene_service().crop_by_height(z_min=z_min, z_max=z_max, keep_inside=keep_inside).model_dump()
