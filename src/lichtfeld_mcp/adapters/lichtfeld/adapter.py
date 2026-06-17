"""Public adapter facade for the LichtFeld plugin integration."""

from __future__ import annotations

from lichtfeld_mcp.adapters.base import LichtfeldAdapter as AdapterContract
from lichtfeld_mcp.core.constraints import (
    validate_color_tolerance,
    validate_rgb_color,
    validate_selection_mode,
)
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

from .cameras import CameraOperations
from .export import ExportOperations
from .gaussian import extract_color_rows, extract_opacity_values, extract_position_rows
from .scene import build_scene_stats, notify_scene_changed
from .selection import SelectionState
from .training import TrainingOperations
from .utils import load_lichtfeld, not_implemented, require_active_scene, require_combined_model


class LichtfeldAdapter(AdapterContract):
    """Facade preserving the existing adapter API while delegating feature logic."""

    def __init__(self) -> None:
        self._selection = SelectionState()
        self._training = TrainingOperations()
        self._export = ExportOperations()
        self._cameras = CameraOperations()

    @property
    def _cached_selection_mask(self) -> list[bool] | None:
        return self._selection.cached_mask(expected_length=len(self._selection._cached_mask or []))

    def open_project(self, path: str) -> ProjectInfo:
        normalized_path = normalize_scene_path(path, label="project path")
        load_lichtfeld()
        not_implemented("open_project", normalized_path=normalized_path)

    def save_project(self) -> ToolResult:
        load_lichtfeld()
        not_implemented("save_project")

    def close_project(self) -> ToolResult:
        load_lichtfeld()
        not_implemented("close_project")

    def get_stats(self) -> SceneStats:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        position_rows = extract_position_rows(model)
        return build_scene_stats(
            scene,
            model,
            position_rows,
            selected_count=self._selection.get_selected_count(scene, len(position_rows)),
        )

    def get_scene_stats(self) -> SceneStats:
        return self.get_stats()

    def select_by_box(self, box: Box3D, mode: str = "replace") -> SelectionResult:
        load_lichtfeld()
        not_implemented("select_by_box", box=box, mode=mode)

    def select_by_height(
        self,
        z_min: float | None,
        z_max: float | None,
        mode: str = "replace",
    ) -> SelectionResult:
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        normalized_mode = validate_selection_mode(mode)
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        position_rows = extract_position_rows(model)
        height_mask = self._selection.build_height_mask(position_rows, height_range)
        selection_mask = self._selection.merge_height_mask(
            scene,
            height_mask,
            normalized_mode,
        )
        selected_indices = self._selection.selected_indices(selection_mask)
        try:
            self._selection.apply_native_selection(
                scene,
                selected_indices,
                lichtfeld_module,
            )
        except AdapterUnavailableError as exc:
            try:
                self._selection.apply_scene_selection_mask(
                    scene,
                    selection_mask,
                    lichtfeld_module,
                    model=model,
                )
            except AdapterUnavailableError as tensor_exc:
                raise AdapterUnavailableError(
                    f"{exc} Tensor fallback also failed: {tensor_exc}"
                ) from tensor_exc
        self._selection.cache_mask(selection_mask)
        notify_scene_changed(scene)
        return SelectionResult(
            selected_count=sum(selection_mask),
            selection_mode=normalized_mode,
            message="Height selection applied.",
        )

    def select_by_opacity(
        self,
        min_opacity: float | None = None,
        max_opacity: float | None = None,
    ) -> SelectionResult:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        opacities = extract_opacity_values(model)
        selection_mask = self._selection.build_opacity_mask(
            opacities,
            min_opacity=min_opacity,
            max_opacity=max_opacity,
        )
        self._selection.apply_scene_selection_mask(
            scene,
            selection_mask,
            lichtfeld_module,
            model=model,
        )
        self._selection.cache_mask(selection_mask)
        notify_scene_changed(scene)
        return SelectionResult(
            selected_count=sum(selection_mask),
            selection_mode="replace",
            message="Opacity selection applied.",
        )

    def select_by_color(
        self,
        r: int,
        g: int,
        b: int,
        tolerance: int = 20,
        mode: str = "replace",
    ) -> SelectionResult:
        target_rgb = validate_rgb_color(r, g, b)
        normalized_tolerance = validate_color_tolerance(tolerance)
        normalized_mode = validate_selection_mode(mode)
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        colors = extract_color_rows(model)
        color_mask = self._selection.build_color_mask(
            colors,
            rgb=target_rgb,
            tolerance=normalized_tolerance,
        )
        selection_mask = self._selection.merge_selection_mask(
            scene,
            color_mask,
            normalized_mode,
        )
        self._selection.apply_scene_selection_mask(
            scene,
            selection_mask,
            lichtfeld_module,
            model=model,
        )
        self._selection.cache_mask(selection_mask)
        notify_scene_changed(scene)
        return SelectionResult(
            selected_count=sum(selection_mask),
            selection_mode=normalized_mode,
            message="Color selection applied.",
        )

    def delete_selection(self) -> ToolResult:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        splat_count = len(extract_position_rows(model))
        selection_mask = self._selection.current_selection_mask(scene, splat_count)
        if selection_mask is None or not any(selection_mask):
            self._selection.clear_cache()
            return ToolResult(ok=False, message="No active selection available to delete.")
        native_selection_mask = self._selection.read_native_selection_mask(scene)
        if native_selection_mask is None:
            raise AdapterUnavailableError(
                "Active LichtFeld selection exists, but no native scene.selection_mask Tensor "
                "is available for deletion."
            )

        soft_delete = getattr(model, "soft_delete", None)
        if not callable(soft_delete):
            raise AdapterUnavailableError(
                "Active LichtFeld combined model does not expose soft_delete for deletion."
            )

        # Current LichtFeld mapping:
        # - model.soft_delete(mask)
        # - model.apply_deleted() when available to commit pending deletions
        soft_delete(native_selection_mask)
        apply_deleted = getattr(model, "apply_deleted", None)
        if callable(apply_deleted):
            apply_deleted()

        remaining_count = len(extract_position_rows(model))
        self._selection.clear_scene_selection_mask(
            scene,
            remaining_count,
            lichtfeld_module,
            model=model,
        )
        self._selection.clear_cache()
        notify_scene_changed(scene)
        return ToolResult(message=f"Deleted {sum(selection_mask)} selected splats.")

    def crop_by_box(self, box: Box3D, keep_inside: bool = True) -> ToolResult:
        load_lichtfeld()
        not_implemented("crop_by_box", box=box, keep_inside=keep_inside)

    def crop_by_height(
        self,
        z_min: float | None,
        z_max: float | None,
        keep_inside: bool = True,
    ) -> ToolResult:
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        load_lichtfeld()
        not_implemented(
            "crop_by_height",
            z_min=height_range.z_min,
            z_max=height_range.z_max,
            keep_inside=keep_inside,
        )

    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult:
        load_lichtfeld()
        not_implemented("optimize_for_target", target=target, max_splats=max_splats)

    def export_scene(self, output_path: str, fmt: str, target: str | None = None) -> ExportResult:
        load_lichtfeld()
        not_implemented("export_scene", output_path=output_path, fmt=fmt, target=target)

    def measure_distance(self, a: Vec3, b: Vec3, unit: str = "m") -> MeasurementResult:
        load_lichtfeld()
        not_implemented("measure_distance", a=a, b=b, unit=unit)

    def undo(self) -> ToolResult:
        load_lichtfeld()
        # Future LichtFeld mapping:
        # - scene.combined_model()
        # - model.undelete(mask)
        # - scene.notify_changed()
        not_implemented("undo")

    def list_history(self) -> list[HistoryEntry]:
        load_lichtfeld()
        not_implemented("list_history")


LichtfeldPluginAdapter = LichtfeldAdapter

__all__ = ["LichtfeldAdapter", "LichtfeldPluginAdapter"]
