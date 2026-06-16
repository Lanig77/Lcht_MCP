"""Service facade sitting between MCP tools and the core scene API."""

from __future__ import annotations

from lichtfeld_mcp.core.scene_api import SceneAPI
from lichtfeld_mcp.schemas.common import (
    ExportResult,
    HistoryEntry,
    OptimizationResult,
    ProjectInfo,
    SceneStats,
    SelectionResult,
    ToolResult,
)


class SceneService:
    """Thin application-service facade over SceneAPI."""

    def __init__(self, scene_api: SceneAPI) -> None:
        self._scene_api = scene_api

    def open_project(self, path: str) -> ProjectInfo:
        return self._scene_api.open_project(path)

    def get_stats(self) -> SceneStats:
        return self._scene_api.get_scene_stats()

    def select_by_box(
        self,
        min_x: float,
        min_y: float,
        min_z: float,
        max_x: float,
        max_y: float,
        max_z: float,
        mode: str = "replace",
    ) -> SelectionResult:
        return self._scene_api.select_by_box(
            min_x=min_x,
            min_y=min_y,
            min_z=min_z,
            max_x=max_x,
            max_y=max_y,
            max_z=max_z,
            mode=mode,
        )

    def select_by_height(
        self,
        z_min: float | None = None,
        z_max: float | None = None,
        mode: str = "replace",
    ) -> SelectionResult:
        return self._scene_api.select_by_height(z_min=z_min, z_max=z_max, mode=mode)

    def select_by_color(
        self,
        r: int,
        g: int,
        b: int,
        tolerance: int = 20,
        mode: str = "replace",
    ) -> SelectionResult:
        return self._scene_api.select_by_color(
            r=r,
            g=g,
            b=b,
            tolerance=tolerance,
            mode=mode,
        )

    def crop_by_height(
        self,
        z_min: float | None = None,
        z_max: float | None = None,
        keep_inside: bool = True,
    ) -> ToolResult:
        return self._scene_api.crop_by_height(
            z_min=z_min,
            z_max=z_max,
            keep_inside=keep_inside,
        )

    def delete_selection(self) -> ToolResult:
        return self._scene_api.delete_selection()

    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult:
        return self._scene_api.optimize_for_target(target=target, max_splats=max_splats)

    def export_scene(self, output_path: str, fmt: str = "ply", target: str | None = None) -> ExportResult:
        return self._scene_api.export_scene(output_path=output_path, fmt=fmt, target=target)

    def undo(self) -> ToolResult:
        return self._scene_api.undo()

    def list_history(self) -> list[HistoryEntry]:
        return self._scene_api.list_history()
