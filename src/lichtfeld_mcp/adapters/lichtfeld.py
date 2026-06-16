"""LichtFeld Studio plugin adapter skeleton.

This module intentionally avoids importing ``lichtfeld`` at module import time so the
normal test suite can run without LichtFeld Studio installed.
"""

from __future__ import annotations

import importlib

from lichtfeld_mcp.adapters.base import LichtfeldAdapter as AdapterContract
from lichtfeld_mcp.core.requests import HeightRange
from lichtfeld_mcp.core.validation import normalize_scene_path
from lichtfeld_mcp.errors import AdapterUnavailableError
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


class LichtfeldPluginAdapter(AdapterContract):
    """Skeleton adapter for the LichtFeld Studio Python plugin API."""

    def open_project(self, path: str) -> ProjectInfo:
        normalized_path = normalize_scene_path(path, label="project path")
        self._load_lichtfeld()
        self._not_implemented(
            "open_project",
            normalized_path=normalized_path,
        )

    def save_project(self) -> ToolResult:
        self._load_lichtfeld()
        self._not_implemented("save_project")

    def close_project(self) -> ToolResult:
        self._load_lichtfeld()
        self._not_implemented("close_project")

    def get_stats(self) -> SceneStats:
        return self.get_scene_stats()

    def get_scene_stats(self) -> SceneStats:
        self._load_lichtfeld()
        # Future LichtFeld mapping:
        # - scene.combined_model()
        # - model.get_means()
        # - derive bounds, splat count and related scene statistics from tensors
        self._not_implemented("get_scene_stats")

    def select_by_box(self, box: Box3D, mode: str = "replace") -> SelectionResult:
        self._load_lichtfeld()
        self._not_implemented("select_by_box", box=box, mode=mode)

    def select_by_height(
        self,
        z_min: float | None,
        z_max: float | None,
        mode: str = "replace",
    ) -> SelectionResult:
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        self._load_lichtfeld()
        # Future LichtFeld mapping:
        # - scene.combined_model()
        # - model.get_means()
        # - build a boolean height mask from the means tensor
        # - scene.set_selection_mask(mask)
        # - scene.notify_changed()
        self._not_implemented(
            "select_by_height",
            z_min=height_range.z_min,
            z_max=height_range.z_max,
            mode=mode,
        )

    def select_by_color(
        self,
        r: int,
        g: int,
        b: int,
        tolerance: int = 20,
        mode: str = "replace",
    ) -> SelectionResult:
        self._load_lichtfeld()
        self._not_implemented(
            "select_by_color",
            r=r,
            g=g,
            b=b,
            tolerance=tolerance,
            mode=mode,
        )

    def delete_selection(self) -> ToolResult:
        self._load_lichtfeld()
        # Future LichtFeld mapping:
        # - scene.combined_model()
        # - model.soft_delete(mask)
        # - model.apply_deleted()
        # - scene.notify_changed()
        self._not_implemented("delete_selection")

    def crop_by_box(self, box: Box3D, keep_inside: bool = True) -> ToolResult:
        self._load_lichtfeld()
        self._not_implemented("crop_by_box", box=box, keep_inside=keep_inside)

    def crop_by_height(
        self,
        z_min: float | None,
        z_max: float | None,
        keep_inside: bool = True,
    ) -> ToolResult:
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        self._load_lichtfeld()
        self._not_implemented(
            "crop_by_height",
            z_min=height_range.z_min,
            z_max=height_range.z_max,
            keep_inside=keep_inside,
        )

    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult:
        self._load_lichtfeld()
        self._not_implemented("optimize_for_target", target=target, max_splats=max_splats)

    def export_scene(self, output_path: str, fmt: str, target: str | None = None) -> ExportResult:
        self._load_lichtfeld()
        self._not_implemented("export_scene", output_path=output_path, fmt=fmt, target=target)

    def measure_distance(self, a: Vec3, b: Vec3, unit: str = "m") -> MeasurementResult:
        self._load_lichtfeld()
        self._not_implemented("measure_distance", a=a, b=b, unit=unit)

    def undo(self) -> ToolResult:
        self._load_lichtfeld()
        # Future LichtFeld mapping:
        # - scene.combined_model()
        # - model.undelete(mask)
        # - scene.notify_changed()
        self._not_implemented("undo")

    def list_history(self) -> list[HistoryEntry]:
        self._load_lichtfeld()
        self._not_implemented("list_history")

    @staticmethod
    def _load_lichtfeld() -> object:
        try:
            return importlib.import_module("lichtfeld")
        except ModuleNotFoundError as exc:
            if exc.name not in {None, "lichtfeld"}:
                raise
            raise AdapterUnavailableError(
                "LichtFeld Studio Python plugin API is not available. "
                "Install or launch LichtFeld Studio with Python plugin support."
            ) from exc
        except ImportError as exc:
            raise AdapterUnavailableError(
                "LichtFeld Studio Python plugin API could not be imported: "
                f"{exc}."
            ) from exc

    @staticmethod
    def _not_implemented(method_name: str, **_: object) -> None:
        raise NotImplementedError(
            f"LichtFeld plugin adapter skeleton does not implement '{method_name}' yet."
        )


LichtfeldAdapter = LichtfeldPluginAdapter

__all__ = ["LichtfeldAdapter", "LichtfeldPluginAdapter"]
