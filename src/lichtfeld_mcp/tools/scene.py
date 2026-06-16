"""Scene-level MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_scene_service


def open_project(path: str) -> dict:
    """Open a Lichtfeld project or Gaussian scene file.

    Args:
        path: Project path, for example C:\\scans\\castle.lfp or scene.ply.
    """

    return get_scene_service().open_project(path).model_dump()


def save_project() -> dict:
    """Save the currently open project."""

    return get_scene_service().save_project().model_dump()


def close_project() -> dict:
    """Close the currently open project."""

    return get_scene_service().close_project().model_dump()


def get_scene_stats() -> dict:
    """Return scene statistics: splat count, selection count, bounds, VRAM estimate."""

    return get_scene_service().get_stats().model_dump()


def list_history() -> list[dict]:
    """Return the editor operation history."""

    return [entry.model_dump() for entry in get_scene_service().list_history()]


def undo() -> dict:
    """Undo the last scene operation when possible."""

    return get_scene_service().undo().model_dump()
