"""Optimization MCP tools."""

from __future__ import annotations

from lichtfeld_mcp.app_state import get_scene_api


def optimize_for_target(target: str, max_splats: int | None = None) -> dict:
    """Optimize the currently open Gaussian scene for a target platform.

    Supported mock targets: quest3, web, mobile, unity, unreal, archive.
    """

    return get_scene_api().optimize_for_target(target=target, max_splats=max_splats).model_dump()
