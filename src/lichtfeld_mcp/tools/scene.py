"""Scene-level MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_adapter


def open_project(path: str) -> dict:
    """Open a Lichtfeld project or Gaussian scene file.

    Args:
        path: Project path, for example C:\\scans\\castle.lfp or scene.ply.
    """

    return get_adapter().open_project(path).model_dump()


def save_project() -> dict:
    """Save the currently open project."""

    return get_adapter().save_project().model_dump()


def close_project() -> dict:
    """Close the currently open project."""

    return get_adapter().close_project().model_dump()


def get_scene_stats() -> dict:
    """Return scene statistics: splat count, selection count, bounds, VRAM estimate."""

    return get_adapter().get_scene_stats().model_dump()


def list_history() -> list[dict]:
    """Return the editor operation history."""

    return [entry.model_dump() for entry in get_adapter().list_history()]


def undo() -> dict:
    """Undo the last scene operation when possible."""

    return get_adapter().undo().model_dump()
