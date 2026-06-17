"""Public adapter facade for the LichtFeld plugin integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from lichtfeld_mcp.adapters.base import LichtfeldAdapter as AdapterContract
from lichtfeld_mcp.core.cluster_analysis import (
    analyze_clusters,
    clusters_outside_largest,
    clusters_smaller_than,
    largest_cluster,
)
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
from .gaussian import (
    build_gaussian_cloud_snapshot,
    extract_color_rows,
    extract_opacity_values,
    extract_position_rows,
)
from .scene import build_scene_stats, notify_scene_changed
from .selection import SelectionState
from .training import TrainingOperations
from .utils import load_lichtfeld, not_implemented, require_active_scene, require_combined_model


logger = logging.getLogger(__name__)


def _safe_length(value: object) -> str:
    try:
        return str(len(value))  # type: ignore[arg-type]
    except Exception:
        return "unknown"


@dataclass(frozen=True, slots=True)
class ClusterAnalysisSummary:
    distance_threshold: float
    min_cluster_size: int
    total_splats: int
    total_clusters: int
    largest_cluster_size: int
    small_cluster_count: int
    candidate_floating_cluster_count: int
    candidate_floating_splat_count: int


class LichtfeldAdapter(AdapterContract):
    """Facade preserving the existing adapter API while delegating feature logic."""

    def __init__(self) -> None:
        self._selection = SelectionState()
        self._training = TrainingOperations()
        self._export = ExportOperations()
        self._cameras = CameraOperations()
        self._last_delete_mask: object | None = None
        self._last_delete_count = 0
        self._last_finalized_delete_count = 0

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

    def analyze_clusters_preview(
        self,
        distance_threshold: float,
        min_cluster_size: int = 1,
    ) -> ClusterAnalysisSummary:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        cloud = build_gaussian_cloud_snapshot(model)
        clusters = analyze_clusters(
            cloud,
            distance_threshold=distance_threshold,
            min_cluster_size=1,
        )
        largest = largest_cluster(clusters)
        small_clusters = clusters_smaller_than(clusters, min_cluster_size)
        candidate_floating_clusters = [
            cluster
            for cluster in clusters_outside_largest(clusters)
            if cluster.count < min_cluster_size
        ]
        return ClusterAnalysisSummary(
            distance_threshold=distance_threshold,
            min_cluster_size=min_cluster_size,
            total_splats=cloud.count(),
            total_clusters=len(clusters),
            largest_cluster_size=0 if largest is None else largest.count,
            small_cluster_count=len(small_clusters),
            candidate_floating_cluster_count=len(candidate_floating_clusters),
            candidate_floating_splat_count=sum(
                cluster.count for cluster in candidate_floating_clusters
            ),
        )

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

    def soft_delete_selection(self) -> ToolResult:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        initial_count = len(extract_position_rows(model))
        selection_mask = self._selection.current_selection_mask(scene, initial_count)
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

        selected_count = sum(selection_mask)
        logger.info(
            "LichtFeld soft_delete_selection: initial_count=%s selected_count=%s native_mask_type=%s native_mask_len=%s",
            initial_count,
            selected_count,
            type(native_selection_mask).__name__,
            _safe_length(native_selection_mask),
        )
        logger.info("LichtFeld soft_delete_selection: before model.soft_delete()")
        self._store_last_delete(native_selection_mask, selected_count)
        try:
            soft_delete(native_selection_mask)
        except Exception:
            self._clear_last_delete()
            raise
        logger.info("LichtFeld soft_delete_selection: after model.soft_delete()")

        self._log_delete_cleanup_step(
            "scene.clear_selection()",
            lambda: self._selection.clear_selection_via_scene(scene),
        )
        self._log_delete_cleanup_step(
            "lichtfeld.deselect_all()",
            lambda: self._selection.deselect_all(lichtfeld_module),
        )

        self._log_delete_cleanup_step(
            "scene.reset_selection_state() post-soft-delete",
            lambda: self._selection.reset_selection_state(scene),
        )
        self._log_delete_cleanup_step(
            "scene.clear_selection() post-soft-delete",
            lambda: self._selection.clear_selection_via_scene(scene),
        )
        self._log_delete_cleanup_step(
            "lichtfeld.deselect_all() post-soft-delete",
            lambda: self._selection.deselect_all(lichtfeld_module),
        )
        self._selection.clear_cache()
        self._log_delete_cleanup_step(
            "scene.notify_changed()",
            lambda: self._notify_scene_changed(scene),
        )
        return ToolResult(
            message=(
                f"Soft-deleted {selected_count} selected splats. "
                "Reversible until apply_deleted() is called."
            )
        )

    def apply_pending_delete(self) -> ToolResult:
        if self._last_delete_mask is None or self._last_delete_count <= 0:
            raise AdapterUnavailableError("No pending LichtFeld soft delete is available to finalize.")

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        pending_count = self._last_delete_count

        apply_deleted = getattr(model, "apply_deleted", None)
        if callable(apply_deleted):
            logger.info("LichtFeld apply_pending_delete: before model.apply_deleted()")
            apply_deleted()
            logger.info(
                "LichtFeld apply_pending_delete: after model.apply_deleted() remaining_count=%s",
                len(extract_position_rows(model)),
            )
            self._last_finalized_delete_count = pending_count
            self._clear_last_delete()
        else:
            logger.info(
                "LichtFeld apply_pending_delete: model.apply_deleted() skipped; "
                "soft delete remains reversible"
            )

        self._log_delete_cleanup_step(
            "scene.reset_selection_state()",
            lambda: self._selection.reset_selection_state(scene),
        )
        self._log_delete_cleanup_step(
            "scene.clear_selection() post-apply",
            lambda: self._selection.clear_selection_via_scene(scene),
        )
        self._log_delete_cleanup_step(
            "lichtfeld.deselect_all() post-apply",
            lambda: self._selection.deselect_all(lichtfeld_module),
        )
        self._selection.clear_cache()
        self._log_delete_cleanup_step(
            "scene.notify_changed()",
            lambda: self._notify_scene_changed(scene),
        )

        if callable(apply_deleted):
            return ToolResult(message=f"Finalized deletion of {pending_count} soft-deleted splats.")
        return ToolResult(
            message=(
                f"apply_deleted() is unavailable; {pending_count} soft-deleted splats remain reversible."
            )
        )

    def delete_selection(self) -> ToolResult:
        soft_delete_result = self.soft_delete_selection()
        if not soft_delete_result.ok:
            return soft_delete_result
        pending_count = self._last_delete_count
        apply_result = self.apply_pending_delete()
        if self._last_finalized_delete_count == pending_count:
            return ToolResult(message=f"Deleted {pending_count} selected splats.")
        return apply_result

    def restore_last_delete(self) -> ToolResult:
        if self._last_delete_mask is None or self._last_delete_count <= 0:
            if self._last_finalized_delete_count > 0:
                raise AdapterUnavailableError(
                    "The last LichtFeld delete was already finalized with apply_deleted(); "
                    "undelete(mask) only works before apply_deleted()."
                )
            raise AdapterUnavailableError("No previous LichtFeld soft delete is available to restore.")

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        undelete = getattr(model, "undelete", None)
        if not callable(undelete):
            raise AdapterUnavailableError(
                "Active LichtFeld combined model does not expose undelete(mask) for restore."
            )

        logger.info(
            "LichtFeld restore_last_delete: deleted_count=%s native_mask_type=%s native_mask_len=%s",
            self._last_delete_count,
            type(self._last_delete_mask).__name__,
            _safe_length(self._last_delete_mask),
        )
        logger.info("LichtFeld restore_last_delete: before model.undelete()")
        undelete(self._last_delete_mask)
        logger.info("LichtFeld restore_last_delete: after model.undelete()")

        apply_deleted = getattr(model, "apply_deleted", None)
        if callable(apply_deleted):
            logger.info("LichtFeld restore_last_delete: before model.apply_deleted()")
            apply_deleted()
            logger.info(
                "LichtFeld restore_last_delete: after model.apply_deleted() splat_count=%s",
                len(extract_position_rows(model)),
            )
        else:
            logger.info("LichtFeld restore_last_delete: model.apply_deleted() skipped")

        self._log_delete_cleanup_step(
            "scene.reset_selection_state()",
            lambda: self._selection.reset_selection_state(scene),
        )
        self._log_delete_cleanup_step(
            "scene.clear_selection() post-undelete",
            lambda: self._selection.clear_selection_via_scene(scene),
        )
        self._log_delete_cleanup_step(
            "lichtfeld.deselect_all() post-undelete",
            lambda: self._selection.deselect_all(lichtfeld_module),
        )
        self._selection.clear_cache()
        self._log_delete_cleanup_step(
            "scene.notify_changed()",
            lambda: self._notify_scene_changed(scene),
        )
        restored_count = self._last_delete_count
        self._clear_last_delete()
        self._last_finalized_delete_count = 0
        return ToolResult(message=f"Restored {restored_count} deleted splats.")

    def _store_last_delete(self, native_mask: object, deleted_count: int) -> None:
        self._last_delete_mask = native_mask
        self._last_delete_count = deleted_count
        self._last_finalized_delete_count = 0

    def _clear_last_delete(self) -> None:
        self._last_delete_mask = None
        self._last_delete_count = 0

    @staticmethod
    def _notify_scene_changed(scene: object) -> bool:
        notify_changed = getattr(scene, "notify_changed", None)
        if not callable(notify_changed):
            return False
        notify_changed()
        return True

    @staticmethod
    def _log_delete_cleanup_step(label: str, action) -> None:
        logger.info("LichtFeld delete_selection: before %s", label)
        try:
            invoked = action()
        except Exception as exc:
            logger.warning("LichtFeld delete_selection: %s failed: %s", label, exc)
            return
        if invoked:
            logger.info("LichtFeld delete_selection: after %s", label)
            return
        logger.info("LichtFeld delete_selection: %s skipped", label)

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
