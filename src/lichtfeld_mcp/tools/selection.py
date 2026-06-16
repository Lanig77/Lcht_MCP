"""Selection and deletion MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_adapter
from lichtfeld_mcp.schemas.common import Box3D, Vec3


def select_by_box(
    min_x: float,
    min_y: float,
    min_z: float,
    max_x: float,
    max_y: float,
    max_z: float,
    mode: str = "replace",
) -> dict:
    """Select splats inside an axis-aligned 3D box.

    Modes: replace, add, subtract.
    """

    box = Box3D(min=Vec3(x=min_x, y=min_y, z=min_z), max=Vec3(x=max_x, y=max_y, z=max_z))
    return get_adapter().select_by_box(box, mode=mode).model_dump()


def select_by_height(z_min: float | None = None, z_max: float | None = None, mode: str = "replace") -> dict:
    """Select splats by vertical range.

    Useful for commands such as 'select the ceiling', 'select everything above 2m',
    or 'remove the floor'.
    """

    return get_adapter().select_by_height(z_min=z_min, z_max=z_max, mode=mode).model_dump()


def select_by_color(r: int, g: int, b: int, tolerance: int = 20, mode: str = "replace") -> dict:
    """Select splats close to an RGB color.

    This is a simple pre-AI primitive useful for selecting sky, green vegetation,
    white studio backgrounds, or dark noisy regions.
    """

    return get_adapter().select_by_color(r=r, g=g, b=b, tolerance=tolerance, mode=mode).model_dump()


def delete_selection() -> dict:
    """Delete the currently selected splats."""

    return get_adapter().delete_selection().model_dump()
