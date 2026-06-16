"""Selection and deletion MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_scene_api


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

    return get_scene_api().select_by_box(
        min_x=min_x,
        min_y=min_y,
        min_z=min_z,
        max_x=max_x,
        max_y=max_y,
        max_z=max_z,
        mode=mode,
    ).model_dump()


def select_by_height(z_min: float | None = None, z_max: float | None = None, mode: str = "replace") -> dict:
    """Select splats by vertical range.

    Useful for commands such as 'select the ceiling', 'select everything above 2m',
    or 'remove the floor'.
    """

    return get_scene_api().select_by_height(z_min=z_min, z_max=z_max, mode=mode).model_dump()


def select_by_color(r: int, g: int, b: int, tolerance: int = 20, mode: str = "replace") -> dict:
    """Select splats close to an RGB color.

    This is a simple pre-AI primitive useful for selecting sky, green vegetation,
    white studio backgrounds, or dark noisy regions.
    """

    return get_scene_api().select_by_color(
        r=r,
        g=g,
        b=b,
        tolerance=tolerance,
        mode=mode,
    ).model_dump()


def delete_selection() -> dict:
    """Delete the currently selected splats."""

    return get_scene_api().delete_selection().model_dump()
