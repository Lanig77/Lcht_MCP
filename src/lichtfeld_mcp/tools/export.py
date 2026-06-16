"""Export MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_scene_api


def export_scene(output_path: str, fmt: str = "ply", target: str | None = None) -> dict:
    """Export the current scene.

    Supported mock formats: ply, spz, splat, json.
    """

    return get_scene_api().export_scene(output_path=output_path, fmt=fmt, target=target).model_dump()
