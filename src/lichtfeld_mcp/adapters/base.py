"""Adapter contract.

The MCP layer must not know whether it is talking to a real Lichtfeld Studio API,
a command line executable, a local SDK, or a simulator. This interface isolates
that decision.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lichtfeld_mcp.schemas.common import (
    Box3D,
    ExportResult,
    HistoryEntry,
    MeasurementResult,
    OptimizationResult,
    ProjectInfo,
    SceneStats,
    SelectionResult,
    ToolResult,
    Vec3,
)

if TYPE_CHECKING:
    from lichtfeld_mcp.core.scene_analysis import CleanupCandidateSummary, SceneAnalysisReport


class LichtfeldAdapter(ABC):
    """Abstract API expected by the MCP tools."""

    @abstractmethod
    def open_project(self, path: str) -> ProjectInfo: ...

    @abstractmethod
    def save_project(self) -> ToolResult: ...

    @abstractmethod
    def close_project(self) -> ToolResult: ...

    @abstractmethod
    def get_scene_stats(self) -> SceneStats: ...

    @abstractmethod
    def analyze_scene(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> SceneAnalysisReport: ...

    @abstractmethod
    def preview_cleanup_candidates(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> CleanupCandidateSummary: ...

    @abstractmethod
    def soft_delete_cleanup_candidates(self) -> ToolResult: ...

    @abstractmethod
    def select_by_box(self, box: Box3D, mode: str = "replace") -> SelectionResult: ...

    @abstractmethod
    def select_by_height(self, z_min: float | None, z_max: float | None, mode: str = "replace") -> SelectionResult: ...

    @abstractmethod
    def select_by_color(self, r: int, g: int, b: int, tolerance: int = 20, mode: str = "replace") -> SelectionResult: ...

    @abstractmethod
    def delete_selection(self) -> ToolResult: ...

    @abstractmethod
    def crop_by_box(self, box: Box3D, keep_inside: bool = True) -> ToolResult: ...

    @abstractmethod
    def crop_by_height(self, z_min: float | None, z_max: float | None, keep_inside: bool = True) -> ToolResult: ...

    @abstractmethod
    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult: ...

    @abstractmethod
    def export_scene(self, output_path: str, fmt: str, target: str | None = None) -> ExportResult: ...

    @abstractmethod
    def measure_distance(self, a: Vec3, b: Vec3, unit: str = "m") -> MeasurementResult: ...

    @abstractmethod
    def undo(self) -> ToolResult: ...

    @abstractmethod
    def list_history(self) -> list[HistoryEntry]: ...
