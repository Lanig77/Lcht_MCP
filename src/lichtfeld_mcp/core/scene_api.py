"""Scene-level orchestration between MCP tools and engine adapters."""

from __future__ import annotations

from lichtfeld_mcp.adapters.base import LichtfeldAdapter
from lichtfeld_mcp.core.constraints import validate_selection_mode
from lichtfeld_mcp.core.scene_analysis import SceneAnalysisReport
from lichtfeld_mcp.core.requests import (
    BoxSelectionRequest,
    ColorSelectionRequest,
    ExportRequest,
    HeightRange,
    OptimizationRequest,
)
from lichtfeld_mcp.core.validation import normalize_measurement_unit, normalize_scene_path
from lichtfeld_mcp.errors import InvalidParameterError, InvalidSelectionError
from lichtfeld_mcp.schemas.common import (
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


class SceneAPI:
    """Small domain facade used by MCP tools."""

    VALID_SELECTION_MODES = {"replace", "add", "subtract"}

    def __init__(self, adapter: LichtfeldAdapter) -> None:
        self._adapter = adapter

    def open_project(self, path: str) -> ProjectInfo:
        return self._adapter.open_project(normalize_scene_path(path, label="project path"))

    def save_project(self) -> ToolResult:
        return self._adapter.save_project()

    def close_project(self) -> ToolResult:
        return self._adapter.close_project()

    def get_scene_stats(self) -> SceneStats:
        return self._adapter.get_scene_stats()

    def analyze_scene(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> SceneAnalysisReport:
        return self._adapter.analyze_scene(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            max_splats=max_splats,
            abort_if_above_limit=abort_if_above_limit,
        )

    def list_history(self) -> list[HistoryEntry]:
        return self._adapter.list_history()

    def undo(self) -> ToolResult:
        return self._adapter.undo()

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
        return self._select_by_box_request(
            BoxSelectionRequest.from_bounds(
                min_x=min_x,
                min_y=min_y,
                min_z=min_z,
                max_x=max_x,
                max_y=max_y,
                max_z=max_z,
                mode=self._validate_selection_mode(mode),
            )
        )

    def select_by_height(
        self,
        z_min: float | None = None,
        z_max: float | None = None,
        mode: str = "replace",
    ) -> SelectionResult:
        return self._select_by_height_range(
            HeightRange(z_min=z_min, z_max=z_max),
            mode=self._validate_selection_mode(mode),
        )

    def select_by_color(
        self,
        r: int,
        g: int,
        b: int,
        tolerance: int = 20,
        mode: str = "replace",
    ) -> SelectionResult:
        return self._select_by_color_request(
            ColorSelectionRequest.from_rgb(
                r=r,
                g=g,
                b=b,
                tolerance=tolerance,
                mode=self._validate_selection_mode(mode),
            )
        )

    def delete_selection(self) -> ToolResult:
        return self._adapter.delete_selection()

    def crop_by_box(
        self,
        min_x: float,
        min_y: float,
        min_z: float,
        max_x: float,
        max_y: float,
        max_z: float,
        keep_inside: bool = True,
    ) -> ToolResult:
        return self._adapter.crop_by_box(
            BoxSelectionRequest.from_bounds(
                min_x=min_x,
                min_y=min_y,
                min_z=min_z,
                max_x=max_x,
                max_y=max_y,
                max_z=max_z,
            ).box,
            keep_inside=keep_inside,
        )

    def crop_by_height(
        self,
        z_min: float | None = None,
        z_max: float | None = None,
        keep_inside: bool = True,
    ) -> ToolResult:
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        return self._adapter.crop_by_height(
            z_min=height_range.z_min,
            z_max=height_range.z_max,
            keep_inside=keep_inside,
        )

    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult:
        return self._optimize(OptimizationRequest(target=target, max_splats=max_splats))

    def export_scene(self, output_path: str, fmt: str = "ply", target: str | None = None) -> ExportResult:
        return self._export(ExportRequest(output_path=output_path, fmt=fmt, target=target))

    def measure_distance(
        self,
        ax: float,
        ay: float,
        az: float,
        bx: float,
        by: float,
        bz: float,
        unit: str = "m",
    ) -> MeasurementResult:
        return self._adapter.measure_distance(
            self._build_vec3(ax, ay, az),
            self._build_vec3(bx, by, bz),
            unit=normalize_measurement_unit(unit),
        )

    def _select_by_box_request(self, request: BoxSelectionRequest) -> SelectionResult:
        return self._adapter.select_by_box(request.box, mode=request.mode)

    def _select_by_height_range(self, height_range: HeightRange, mode: str = "replace") -> SelectionResult:
        return self._adapter.select_by_height(
            z_min=height_range.z_min,
            z_max=height_range.z_max,
            mode=mode,
        )

    def _select_by_color_request(self, request: ColorSelectionRequest) -> SelectionResult:
        return self._adapter.select_by_color(
            r=request.color.r,
            g=request.color.g,
            b=request.color.b,
            tolerance=request.tolerance,
            mode=request.mode,
        )

    def _optimize(self, request: OptimizationRequest) -> OptimizationResult:
        return self._adapter.optimize_for_target(
            target=request.target,
            max_splats=request.max_splats,
        )

    def _export(self, request: ExportRequest) -> ExportResult:
        return self._adapter.export_scene(
            output_path=request.output_path,
            fmt=request.fmt,
            target=request.target,
        )

    @staticmethod
    def _validate_selection_mode(mode: str) -> str:
        try:
            return validate_selection_mode(mode)
        except InvalidParameterError as exc:
            raise InvalidSelectionError(
                f"Unsupported selection mode '{mode}'. Supported modes: add, replace, subtract."
            ) from exc

    @staticmethod
    def _build_vec3(x: float, y: float, z: float) -> Vec3:
        return Vec3(x=x, y=y, z=z)
