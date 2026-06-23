"""Public adapter facade for the LichtFeld plugin integration."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
import math
from time import perf_counter

from lichtfeld_mcp.adapters.base import LichtfeldAdapter as AdapterContract
from lichtfeld_mcp.core.cleanup_workspace import (
    CleanupParameters,
    CleanupSession,
    CleanupWorkspace,
    build_scene_profile,
)
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
from lichtfeld_mcp.core.scene_analysis import (
    CleanupCandidateSummary,
    SceneAnalysisContext,
    SceneAnalysisReport,
    build_default_scene_analysis_engine,
)
from lichtfeld_mcp.core.validation import normalize_scene_path
from lichtfeld_mcp.core.voxel_analysis import (
    analyze_voxel_clusters,
    largest_voxel_cluster,
    voxel_clusters_outside_largest,
    voxel_clusters_smaller_than,
)
from lichtfeld_mcp.errors import AdapterUnavailableError, InvalidParameterError
from lichtfeld_mcp.schemas.common import (
    Box3D,
    CleanupApplyDeletedResult,
    CleanupSoftDeleteResult,
    CleanupSelectionPreviewResult,
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
    build_bounds,
    build_gaussian_cloud_from_positions,
    extract_sampled_position_rows,
    extract_color_rows,
    extract_opacity_values,
    extract_position_rows,
    sample_position_rows,
    _coerce_position_rows,
    get_position_source_count,
    resolve_position_source,
)
from .scene import build_scene_stats, get_scene_name, get_scene_path, notify_scene_changed
from .selection import SelectionState
from .training import TrainingOperations
from .utils import (
    load_lichtfeld,
    not_implemented,
    require_active_scene,
    require_combined_model,
)


logger = logging.getLogger(__name__)


def _elapsed_seconds(start_time: float) -> float:
    return perf_counter() - start_time


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
    analyzed_splats: int
    total_clusters: int
    largest_cluster_size: int
    small_cluster_count: int
    candidate_floating_cluster_count: int
    candidate_floating_splat_count: int
    approximate: bool
    refused: bool
    sampling_stride: int
    message: str
    used_native_sampling: bool
    stats_elapsed_seconds: float
    read_means_elapsed_seconds: float
    sampling_elapsed_seconds: float
    cloud_build_elapsed_seconds: float
    clustering_elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class VoxelClusterAnalysisSummary:
    voxel_size: float
    min_voxel_cluster_size: int
    total_splats: int
    analyzed_splats: int
    occupied_voxels: int
    total_voxel_clusters: int
    largest_voxel_cluster_voxel_count: int
    largest_voxel_cluster_estimated_splats: int
    small_voxel_cluster_count: int
    estimated_floating_splats: int
    approximate: bool
    refused: bool
    sampling_stride: int
    message: str
    used_native_sampling: bool
    read_means_elapsed_seconds: float
    sampling_elapsed_seconds: float
    voxel_analysis_elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class AnalysisSceneStats:
    splat_count: int
    bounding_box: Box3D
    deleted_count: int | None = None
    selected_count: int | None = None


@dataclass(slots=True)
class _SceneAnalysisState:
    report: SceneAnalysisReport
    sampled_rows: list[tuple[float, float, float]]
    sampled_indices: list[int]
    project_path: str
    total_splats: int
    approximate: bool
    scene_generation: object | None = None


@dataclass(slots=True)
class _CleanupPreviewState:
    summary: CleanupCandidateSummary
    selection_mask: list[bool]
    selected_indices: list[int]
    selection_sources: tuple[str, ...]
    approximate: bool


@dataclass(slots=True)
class _CleanupCandidateBuild:
    summary: CleanupCandidateSummary
    selection_mask: list[bool]
    selected_indices: list[int]
    selection_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SceneAnalysisReuseDecision:
    analysis_state: _SceneAnalysisState
    analysis_reused: bool
    sample_reused: bool
    reason: str


def _raise_analyze_scene_stage_error(stage: str, exc: Exception) -> None:
    raise AdapterUnavailableError(f"analyze_scene failed at {stage}: {exc}") from exc


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
        self._last_finalized_restore_message: str | None = None
        self._last_delete_workspace_session: CleanupSession | None = None
        self._last_scene_analysis: _SceneAnalysisState | None = None
        self._last_cleanup_preview: _CleanupPreviewState | None = None
        self._cleanup_workspace_session: CleanupSession | None = None
        self._pending_cleanup_apply_project_path: str | None = None

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

    def get_stats(self, *, include_selection: bool = True) -> SceneStats:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        position_rows = extract_position_rows(model)
        if include_selection:
            selected_count = self._selection.get_selected_count(
                scene,
                len(position_rows),
                lf_module=lichtfeld_module,
            )
        else:
            selected_count = 0
        return build_scene_stats(
            scene,
            model,
            position_rows,
            selected_count=selected_count,
        )

    def get_scene_stats(self) -> SceneStats:
        return self.get_stats()

    def analyze_scene(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> SceneAnalysisReport:
        if voxel_size <= 0.0:
            raise InvalidParameterError("voxel_size must be strictly positive.")
        if min_voxel_cluster_size < 1:
            raise InvalidParameterError("min_voxel_cluster_size must be at least 1.")
        if max_splats < 1:
            raise InvalidParameterError("max_splats must be at least 1.")

        try:
            lichtfeld_module = load_lichtfeld()
        except Exception as exc:
            _raise_analyze_scene_stage_error("get_lf_module", exc)

        try:
            scene = require_active_scene(lichtfeld_module)
        except Exception as exc:
            _raise_analyze_scene_stage_error("get_active_scene", exc)

        try:
            model = require_combined_model(scene)
        except Exception as exc:
            _raise_analyze_scene_stage_error("combined_model", exc)

        try:
            project_path = get_scene_path(scene)
            project_name = get_scene_name(scene, project_path)
        except Exception as exc:
            _raise_analyze_scene_stage_error("basic_stats", exc)

        try:
            position_source = resolve_position_source(model)
        except Exception as exc:
            _raise_analyze_scene_stage_error("get_means", exc)

        try:
            total_splats = self._read_splat_count_without_selection(model, position_source)
            materialized_position_rows: list[tuple[float, float, float]] | None = None
            used_native_sampling = False
            sampling_stride = 1
            sampled_rows: list[tuple[float, float, float]] = []
            sampled_indices: list[int] = []

            if total_splats is None:
                materialized_position_rows = _coerce_position_rows(position_source)
                total_splats = len(materialized_position_rows)

            if abort_if_above_limit and total_splats > max_splats:
                analysis_stats = AnalysisSceneStats(
                    splat_count=total_splats,
                    bounding_box=build_bounds([]),
                    deleted_count=None,
                    selected_count=None,
                )
            else:
                if materialized_position_rows is not None:
                    sampled_rows, sampling_stride = sample_position_rows(
                        materialized_position_rows,
                        max_splats,
                    )
                    sampled_indices = list(range(0, len(materialized_position_rows), sampling_stride))[
                        : len(sampled_rows)
                    ]
                else:
                    sampled_rows, sampling_stride, used_native_sampling = extract_sampled_position_rows(
                        position_source,
                        max_splats,
                        total_splats=total_splats,
                    )
                    sampled_indices = list(range(0, total_splats, sampling_stride))[: len(sampled_rows)]
                analysis_stats = AnalysisSceneStats(
                    splat_count=total_splats,
                    bounding_box=build_bounds(sampled_rows),
                    deleted_count=None,
                    selected_count=None,
                )
        except Exception as exc:
            _raise_analyze_scene_stage_error("sampling", exc)

        approximate = len(sampled_rows) != analysis_stats.splat_count
        aborted = abort_if_above_limit and analysis_stats.splat_count > max_splats
        scene_generation = self._read_scene_generation(scene, model)
        logger.info(
            "LichtFeld scene analysis: total_splats=%s analyzed_splats=%s "
            "approximate=%s sampling_stride=%s native_sampling=%s aborted=%s",
            analysis_stats.splat_count,
            len(sampled_rows),
            approximate,
            sampling_stride,
            used_native_sampling,
            aborted,
        )

        context = SceneAnalysisContext(
            scene_name=project_name,
            project_path=project_path,
            positions=sampled_rows,
            total_splats=analysis_stats.splat_count,
            analyzed_splats=len(sampled_rows),
            selected_splats=0,
            deleted_splats=0,
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            approximate=approximate,
            sampling_stride=sampling_stride,
            used_native_sampling=used_native_sampling,
            max_splats=max_splats,
            aborted=aborted,
        )
        try:
            engine = build_default_scene_analysis_engine()
        except Exception as exc:
            _raise_analyze_scene_stage_error("engine_creation", exc)

        try:
            report = engine.analyze(context)
        except Exception as exc:
            _raise_analyze_scene_stage_error("engine_run", exc)
        report = replace(
            report,
            scene_stats={
                **report.scene_stats,
                "scene_generation": scene_generation,
            },
        )
        logger.info(
            "LichtFeld scene analysis complete: quality_score=%s warnings=%s "
            "recommendations=%s analysis_time=%.3fs",
            report.quality_score,
            len(report.warnings),
            len(report.recommendations),
            report.analysis_time,
        )
        self._last_scene_analysis = _SceneAnalysisState(
            report=report,
            sampled_rows=list(sampled_rows),
            sampled_indices=list(sampled_indices),
            project_path=project_path,
            total_splats=analysis_stats.splat_count,
            approximate=approximate,
            scene_generation=scene_generation,
        )
        self._last_cleanup_preview = None
        self._invalidate_cleanup_workspace()
        return report

    def preview_cleanup_candidates(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> CleanupCandidateSummary:
        analysis_state = self._last_scene_analysis
        if analysis_state is None:
            raise AdapterUnavailableError(
                "No previous scene analysis is available. Run Analyze Scene first."
            )
        build = self._build_cleanup_candidate_preview(
            analysis_state,
            CleanupParameters(
                voxel_size=float(voxel_size),
                min_voxel_cluster_size=int(min_voxel_cluster_size),
                cluster_distance_threshold=0.10,
                outlier_distance=2.5,
                cleanup_aggressiveness=0.5,
            ),
            sampled_gaussian_cloud=build_gaussian_cloud_from_positions(list(analysis_state.sampled_rows)),
        )
        self._last_cleanup_preview = _CleanupPreviewState(
            summary=build.summary,
            selection_mask=list(build.selection_mask),
            selected_indices=list(build.selected_indices),
            selection_sources=build.selection_sources,
            approximate=build.summary.approximate,
        )
        logger.info(
            "LichtFeld cleanup preview: candidate_groups=%s estimated_affected_splats=%s "
            "floating_voxel_groups=%s small_voxel_clusters=%s sparse_regions=%s",
            build.summary.candidate_group_count,
            build.summary.estimated_affected_splats,
            build.summary.floating_voxel_groups,
            build.summary.small_voxel_clusters,
            build.summary.sparse_regions,
        )
        logger.info("LichtFeld cleanup preview: cached for native selection preview")
        return build.summary

    def preview_cleanup_selection(self) -> CleanupSelectionPreviewResult:
        analysis_state = self._last_scene_analysis
        if analysis_state is None:
            raise AdapterUnavailableError(
                "No previous scene analysis is available. Run Analyze Scene first."
            )
        preview_state = self._last_cleanup_preview
        if preview_state is None:
            raise AdapterUnavailableError(
                "No cleanup preview is available. Run Preview Cleanup Selection after Analyze Scene."
            )

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        scene_path = get_scene_path(scene)
        if scene_path != analysis_state.project_path:
            raise AdapterUnavailableError(
                "Cleanup selection preview no longer matches the active scene. "
                "Run Analyze Scene again."
            )

        selected_count = len(preview_state.selected_indices)
        selection_mode = "replace"
        selection_source = ", ".join(preview_state.selection_sources) or "no cleanup candidates"
        approximate = preview_state.approximate
        selection_percentage = (
            0.0 if analysis_state.total_splats <= 0 else selected_count / analysis_state.total_splats
        )

        if approximate:
            self._apply_cleanup_candidate_selection_indices_only(
                scene,
                lichtfeld_module,
                preview_state.selected_indices,
            )
        else:
            self._apply_cleanup_candidate_selection(
                scene,
                model,
                lichtfeld_module,
                preview_state.selection_mask,
            )

        message = (
            "Approximate sampled selection preview. "
            "Selected splats represent estimated cleanup regions. "
            "Run Detailed mode for a more precise preview."
            if approximate
            else "Exact cleanup selection preview."
        )
        logger.info(
            "LichtFeld cleanup selection preview: selected_count=%s selection_percentage=%.6f "
            "selection_mode=%s selection_source=%s approximate=%s",
            selected_count,
            selection_percentage,
            selection_mode,
            selection_source,
            approximate,
        )
        return CleanupSelectionPreviewResult(
            selected_count=selected_count,
            selection_percentage=selection_percentage,
            selection_mode="replace",
            selection_source=selection_source,
            approximate=approximate,
            message=message,
        )

    def open_cleanup_workspace(
        self,
        *,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        cluster_distance_threshold: float = 0.10,
        outlier_distance: float = 2.5,
        cleanup_aggressiveness: float = 0.5,
        preset_name: str = "Balanced",
    ) -> CleanupWorkspace:
        params = self._normalize_cleanup_parameters(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            cluster_distance_threshold=cluster_distance_threshold,
            outlier_distance=outlier_distance,
            cleanup_aggressiveness=cleanup_aggressiveness,
            preset_name=preset_name,
        )
        analysis_decision = self._resolve_cleanup_analysis_state_for_workspace(params)
        logger.info(
            "LichtFeld cleanup workspace analysis: analysis_reused=%s sample_reused=%s reason=%s",
            analysis_decision.analysis_reused,
            analysis_decision.sample_reused,
            analysis_decision.reason,
        )
        session = self._build_cleanup_workspace_session(
            analysis_decision.analysis_state,
            params,
            existing_session=(
                self._reusable_cleanup_session_for_scene(
                    analysis_decision.analysis_state.project_path
                )
                if analysis_decision.sample_reused
                else None
            ),
            analysis_reused=analysis_decision.analysis_reused,
            sample_reused=analysis_decision.sample_reused,
        )
        self._last_cleanup_preview = None
        self._cleanup_workspace_session = session
        return session.workspace

    def update_cleanup_workspace(
        self,
        *,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        cluster_distance_threshold: float = 0.10,
        outlier_distance: float = 2.5,
        cleanup_aggressiveness: float = 0.5,
        preset_name: str = "Balanced",
    ) -> CleanupWorkspace:
        session = self._require_cleanup_session()
        self._ensure_workspace_scene_matches(session.workspace)
        params = self._normalize_cleanup_parameters(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            cluster_distance_threshold=cluster_distance_threshold,
            outlier_distance=outlier_distance,
            cleanup_aggressiveness=cleanup_aggressiveness,
            preset_name=preset_name,
        )
        analysis_decision = self._resolve_cleanup_analysis_state_for_workspace(params)
        logger.info(
            "LichtFeld cleanup workspace analysis: analysis_reused=%s sample_reused=%s reason=%s",
            analysis_decision.analysis_reused,
            analysis_decision.sample_reused,
            analysis_decision.reason,
        )
        updated_session = self._build_cleanup_workspace_session(
            analysis_decision.analysis_state,
            params,
            existing_session=session if analysis_decision.sample_reused else None,
            analysis_reused=analysis_decision.analysis_reused,
            sample_reused=analysis_decision.sample_reused,
        )
        self._last_cleanup_preview = None
        self._cleanup_workspace_session = updated_session
        return updated_session.workspace

    def get_cleanup_workspace(self) -> CleanupWorkspace | None:
        session = self._cleanup_workspace_session
        if session is None:
            return None
        try:
            self._ensure_workspace_scene_matches(session.workspace)
        except AdapterUnavailableError:
            return None
        return session.workspace

    def invalidate_cleanup_workspace_preview(self) -> ToolResult:
        session = self._cleanup_workspace_session
        if session is None:
            return ToolResult(message="Cleanup workspace preview was already inactive.")
        workspace = self._ensure_workspace_scene_matches(session.workspace)
        if not workspace.preview_selection_active:
            return ToolResult(message="Cleanup workspace preview was already inactive.")
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        self._clear_native_selection_preview(scene, model, lichtfeld_module)
        self._clear_workspace_preview_state(workspace_state="active")
        logger.info("LichtFeld cleanup workspace preview invalidated")
        return ToolResult(
            message="Cleanup workspace preview invalidated. Run Update Preview to rebuild it."
        )

    def reset_cleanup_workspace(self) -> ToolResult:
        session = self._cleanup_workspace_session
        self._cleanup_workspace_session = None
        self._last_cleanup_preview = None
        if session is None:
            return ToolResult(message="Cleanup workspace was already reset.")
        workspace = session.workspace
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        if get_scene_path(scene) != workspace.scene_profile.project_path:
            return ToolResult(message="Cleanup workspace reset after scene change.")
        self._clear_native_selection_preview(scene, model, lichtfeld_module)
        logger.info("LichtFeld cleanup workspace reset: selection cleared")
        return ToolResult(message="Cleanup workspace reset. Native preview selection cleared.")

    def soft_delete_cleanup_workspace_selection(
        self,
        *,
        max_deletable_splats: int | None = None,
        max_deletable_percentage: float | None = None,
    ) -> CleanupSoftDeleteResult:
        session = self._require_cleanup_session()
        workspace = session.workspace
        if not workspace.preview_selection_active or workspace.workspace_state == "soft_deleted":
            raise AdapterUnavailableError(
                "No cleanup workspace preview selection is available. Update Preview first."
            )

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        self._ensure_workspace_scene_matches(workspace)
        current_splat_count = self._read_current_model_splat_count(model)

        current_scene_generation = self._read_scene_generation(scene, model)
        if self._scene_generation_changed(workspace.scene_generation, current_scene_generation):
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="scene_content_stamp_changed",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_splat_count,
            )
            self._invalidate_cleanup_workspace()
            raise AdapterUnavailableError(
                "Cleanup workspace no longer matches the current scene generation. "
                "Open Cleanup Workspace again."
            )

        if current_splat_count != workspace.scene_profile.total_splats:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="scene_splat_count_changed",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_splat_count,
            )
            self._invalidate_cleanup_workspace()
            raise AdapterUnavailableError(
                "Cleanup workspace no longer matches the current scene splat count. "
                "Open Cleanup Workspace again."
            )

        selected_count = workspace.selected_count
        if selected_count <= 0:
            raise AdapterUnavailableError("Cleanup workspace preview selection is empty.")

        if workspace.native_selection_mask is None:
            raise AdapterUnavailableError(
                "Cleanup workspace preview exists, but no workspace-owned native selection mask "
                "is available for soft delete."
            )

        native_mask_size = workspace.native_selection_mask_size
        if native_mask_size is None:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="workspace_mask_size_unavailable",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_splat_count,
            )
            raise AdapterUnavailableError(
                "Cleanup workspace native selection mask size is unavailable for soft delete."
            )
        if native_mask_size != current_splat_count:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="workspace_mask_size_mismatch",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_splat_count,
            )
            self._invalidate_cleanup_workspace()
            raise AdapterUnavailableError(
                "Cleanup workspace native selection mask size does not match the current scene "
                "splat count."
            )

        selected_percentage = (
            0.0 if current_splat_count <= 0 else selected_count / current_splat_count
        )
        logger.info(
            "LichtFeld cleanup workspace soft delete: initial_splat_count=%s",
            current_splat_count,
        )
        logger.info(
            "LichtFeld cleanup workspace soft delete: workspace_selected_count=%s",
            selected_count,
        )
        logger.info(
            "LichtFeld cleanup workspace soft delete: selected_percentage=%.6f",
            selected_percentage,
        )
        logger.info(
            "LichtFeld cleanup workspace soft delete: max_deletable_splats=%s "
            "max_deletable_percentage=%s",
            max_deletable_splats,
            max_deletable_percentage,
        )
        if max_deletable_splats is not None and selected_count > max_deletable_splats:
            raise AdapterUnavailableError(
                "Cleanup workspace soft delete refused: "
                f"selected_count={selected_count} exceeds max_deletable_splats="
                f"{max_deletable_splats}."
            )
        if (
            max_deletable_percentage is not None
            and selected_percentage > max_deletable_percentage
        ):
            raise AdapterUnavailableError(
                "Cleanup workspace soft delete refused: "
                f"selected_percentage={selected_percentage:.6f} exceeds "
                f"max_deletable_percentage={max_deletable_percentage:.6f}."
            )

        try:
            result = self._soft_delete_native_selection_mask(
                scene,
                model,
                lichtfeld_module,
                workspace.native_selection_mask,
                selected_count,
                initial_count=current_splat_count,
                workspace_session_snapshot=self._snapshot_cleanup_workspace_session(session),
            )
        except Exception:
            logger.info("LichtFeld cleanup workspace soft delete: soft_delete failed")
            raise

        restore_available = self._last_delete_mask is not None and self._last_delete_count > 0
        self._pending_cleanup_apply_project_path = None
        self._clear_workspace_preview_state(workspace_state="soft_deleted")
        workspace_state = (
            self._cleanup_workspace_session.workspace.workspace_state
            if self._cleanup_workspace_session is not None
            else "inactive"
        )
        logger.info(
            "LichtFeld cleanup workspace soft delete: ok=%s restore_available=%s "
            "workspace_state=%s",
            result.ok,
            restore_available,
            workspace_state,
        )
        return CleanupSoftDeleteResult(
            ok=result.ok,
            soft_deleted_count=selected_count,
            total_splats=current_splat_count,
            percentage=selected_percentage,
            restore_available=restore_available,
            message=(
                f"Soft-deleted {selected_count} cleanup workspace splats. "
                "Reversible until apply_deleted() is called."
            ),
        )

    def soft_delete_current_cleanup_selection(self) -> CleanupSoftDeleteResult:
        return self.soft_delete_cleanup_workspace_selection()

    def apply_cleanup_workspace_deleted(self) -> CleanupApplyDeletedResult:
        session = self._require_cleanup_session()
        workspace = session.workspace
        if workspace.workspace_state != "soft_deleted":
            raise AdapterUnavailableError(
                "No cleanup workspace soft delete is available. "
                "Run Soft Delete Cleanup Workspace Selection first."
            )
        if not self._has_reversible_soft_delete():
            raise AdapterUnavailableError(
                "No reversible cleanup workspace soft delete is available to apply."
            )

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        self._ensure_workspace_scene_matches(workspace)
        current_splat_count = self._read_current_model_splat_count(model)

        current_scene_generation = self._read_scene_generation(scene, model)
        if self._scene_generation_changed(workspace.scene_generation, current_scene_generation):
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="scene_content_stamp_changed",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_splat_count,
            )
            self._invalidate_cleanup_workspace()
            raise AdapterUnavailableError(
                "Cleanup workspace no longer matches the current scene generation. "
                "Open Cleanup Workspace again."
            )

        initial_splat_count = current_splat_count
        if initial_splat_count != workspace.scene_profile.total_splats:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="scene_splat_count_changed",
                current_generation=current_scene_generation,
                current_splat_count=initial_splat_count,
                current_model_splat_count=initial_splat_count,
            )
            self._invalidate_cleanup_workspace()
            raise AdapterUnavailableError(
                "Cleanup workspace no longer matches the current scene splat count. "
                "Open Cleanup Workspace again."
            )

        soft_deleted_count = self._last_delete_count
        if soft_deleted_count <= 0:
            raise AdapterUnavailableError(
                "Cleanup workspace soft delete metadata is empty. "
                "Run Soft Delete Cleanup Workspace Selection first."
            )

        delete_mask_size = self._native_mask_size(self._last_delete_mask)
        if delete_mask_size is None:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="delete_mask_size_unavailable",
                current_generation=current_scene_generation,
                current_splat_count=initial_splat_count,
                current_model_splat_count=initial_splat_count,
            )
            raise AdapterUnavailableError(
                "Cleanup workspace soft delete mask size is unavailable for permanent apply."
            )
        if delete_mask_size != initial_splat_count:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="delete_mask_size_mismatch",
                current_generation=current_scene_generation,
                current_splat_count=initial_splat_count,
                current_model_splat_count=initial_splat_count,
                workspace_mask_size=delete_mask_size,
            )
            self._invalidate_cleanup_workspace()
            raise AdapterUnavailableError(
                "Cleanup workspace soft delete mask size does not match the current scene "
                "splat count."
            )

        apply_deleted_entry = self._resolve_apply_deleted_callable(scene, model)
        if apply_deleted_entry is None:
            raise AdapterUnavailableError(
                "Active LichtFeld scene/model does not expose apply_deleted() for permanent cleanup."
            )
        apply_deleted_label, apply_deleted = apply_deleted_entry

        logger.info(
            "LichtFeld cleanup workspace apply: initial_splat_count=%s",
            initial_splat_count,
        )
        logger.info(
            "LichtFeld cleanup workspace apply: soft_deleted_count=%s",
            soft_deleted_count,
        )
        self._log_native_selection_state(
            "cleanup workspace apply: before pre-apply selection clear",
            scene,
            model,
        )
        self._prepare_native_selection_for_apply_deleted(
            scene,
            model,
            lichtfeld_module,
            context_label="cleanup workspace apply",
        )
        self._log_native_selection_state(
            "cleanup workspace apply: after pre-apply selection clear",
            scene,
            model,
        )
        self._log_native_selection_state(
            "cleanup workspace apply: before apply_deleted()",
            scene,
            model,
        )
        logger.info(
            "LichtFeld cleanup workspace apply: before %s",
            apply_deleted_label,
        )
        apply_deleted()
        model = self._refresh_model_after_apply_deleted(
            scene,
            model,
            context_label="cleanup workspace apply",
        )
        self._log_native_selection_state(
            "cleanup workspace apply: after apply_deleted()",
            scene,
            model,
        )
        final_splat_count = self._read_current_model_splat_count(model)
        permanently_deleted_count = initial_splat_count - final_splat_count
        logger.info(
            "LichtFeld cleanup workspace apply: final_splat_count=%s",
            final_splat_count,
        )
        logger.info(
            "LichtFeld cleanup workspace apply: permanently_deleted_count=%s",
            permanently_deleted_count,
        )

        self._last_finalized_delete_count = soft_deleted_count
        self._clear_last_delete()
        self._last_finalized_restore_message = (
            "No reversible soft delete is available. The last cleanup was permanently applied."
        )
        self._pending_cleanup_apply_project_path = None

        self._log_native_selection_state(
            "cleanup workspace apply: before selection reset",
            scene,
            model,
        )
        self._reset_native_selection_after_apply_deleted(
            scene,
            model,
            lichtfeld_module,
            context_label="cleanup workspace apply",
        )
        self._log_native_selection_state(
            "cleanup workspace apply: after selection reset",
            scene,
            model,
        )
        self._log_delete_cleanup_step(
            "scene.notify_changed()",
            lambda: self._notify_scene_changed(scene),
        )
        self._invalidate_cleanup_workspace()
        logger.info(
            "LichtFeld cleanup workspace apply: restore_available=%s workspace_state=%s",
            False,
            "invalidated",
        )
        return CleanupApplyDeletedResult(
            ok=True,
            initial_splat_count=initial_splat_count,
            soft_deleted_count=soft_deleted_count,
            permanently_deleted_count=permanently_deleted_count,
            final_splat_count=final_splat_count,
            restore_available=False,
            workspace_state="invalidated",
            message=(
                f"Permanently applied cleanup of {permanently_deleted_count} soft-deleted splats."
            ),
        )

    def soft_delete_cleanup_candidates(self) -> ToolResult:
        preview_state = self._last_cleanup_preview
        if preview_state is None:
            raise AdapterUnavailableError(
                "No cleanup preview is available. Run Preview Cleanup Selection after Analyze Scene."
            )
        if preview_state.summary.approximate:
            raise AdapterUnavailableError(
                "Cleanup preview is approximate-only; no reliable native selection is available."
            )
        selection_mask = list(preview_state.selection_mask)
        selected_count = sum(selection_mask)
        if selected_count <= 0:
            raise AdapterUnavailableError(
                "Cleanup preview did not identify any reliable cleanup candidates."
            )

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        if preview_state.summary.project_path != get_scene_path(scene):
            raise AdapterUnavailableError(
                "Cleanup preview no longer matches the active scene. "
                "Run Preview Cleanup Selection again."
            )

        try:
            self._apply_cleanup_candidate_selection(
                scene,
                model,
                lichtfeld_module,
                selection_mask,
            )
        except Exception as exc:
            raise AdapterUnavailableError(
                "Cleanup preview could not build a reliable native selection."
            ) from exc

        result = self.soft_delete_selection()
        logger.info(
            "LichtFeld cleanup soft delete: affected_count=%s message=%s",
            selected_count,
            result.message,
        )
        self._pending_cleanup_apply_project_path = preview_state.summary.project_path
        self._last_cleanup_preview = None
        return result

    def apply_cleanup_candidates(self) -> ToolResult:
        if self._pending_cleanup_apply_project_path is None:
            raise AdapterUnavailableError(
                "No confirmed cleanup soft delete is available. "
                "Run Soft Delete Cleanup Preview after Preview Cleanup Selection."
            )
        if self._last_delete_mask is None or self._last_delete_count <= 0:
            self._pending_cleanup_apply_project_path = None
            raise AdapterUnavailableError(
                "No pending cleanup soft delete is available to finalize."
            )

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        scene_path = get_scene_path(scene)
        if scene_path != self._pending_cleanup_apply_project_path:
            raise AdapterUnavailableError(
                "Pending cleanup soft delete no longer matches the active scene. "
                "Run Preview Cleanup Selection again."
            )

        apply_deleted = getattr(model, "apply_deleted", None)
        if not callable(apply_deleted):
            raise AdapterUnavailableError(
                "Active LichtFeld combined model does not expose apply_deleted() for permanent cleanup."
            )

        initial_splat_count = self._read_current_model_splat_count(model)
        soft_deleted_count = self._last_delete_count
        logger.info("LichtFeld cleanup apply: initial_splat_count=%s", initial_splat_count)
        logger.info("LichtFeld cleanup apply: soft_deleted_count=%s", soft_deleted_count)
        result = self.apply_pending_delete()
        final_splat_count = self._read_current_model_splat_count(model)
        permanent_deleted_count = initial_splat_count - final_splat_count
        logger.info("LichtFeld cleanup apply: final_splat_count=%s", final_splat_count)
        logger.info(
            "LichtFeld cleanup apply: permanent_deleted_count=%s",
            permanent_deleted_count,
        )
        self._invalidate_cleanup_workspace()
        return ToolResult(
            ok=result.ok,
            message=(
                f"Permanently applied cleanup of {permanent_deleted_count} soft-deleted splats."
            ),
        )

    def analyze_clusters_preview(
        self,
        distance_threshold: float,
        min_cluster_size: int = 1,
        max_cluster_analysis_splats: int = 25_000,
        abort_if_splat_count_above_limit: bool = False,
    ) -> ClusterAnalysisSummary:
        if max_cluster_analysis_splats < 1:
            raise InvalidParameterError("max_cluster_analysis_splats must be at least 1.")

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)

        logger.info("LichtFeld cluster preview: before reading means")
        read_means_started_at = perf_counter()
        position_source = resolve_position_source(model)
        read_means_elapsed_seconds = _elapsed_seconds(read_means_started_at)
        logger.info(
            "LichtFeld cluster preview: after reading means source_type=%s elapsed=%.3fs",
            type(position_source).__name__,
            read_means_elapsed_seconds,
        )

        logger.info("LichtFeld cluster preview: before get_stats")
        stats_started_at = perf_counter()
        materialized_position_rows: list[tuple[float, float, float]] | None = None
        total_splats = get_position_source_count(position_source)
        if total_splats is None:
            materialized_position_rows = _coerce_position_rows(position_source)
            total_splats = len(materialized_position_rows)
        stats_elapsed_seconds = _elapsed_seconds(stats_started_at)
        logger.info(
            "LichtFeld cluster preview: after get_stats total_splats=%s elapsed=%.3fs",
            total_splats,
            stats_elapsed_seconds,
        )
        logger.info(
            "LichtFeld cluster preview: max_cluster_analysis_splats=%s "
            "abort_if_splat_count_above_limit=%s",
            max_cluster_analysis_splats,
            abort_if_splat_count_above_limit,
        )
        if (
            abort_if_splat_count_above_limit
            and total_splats > max_cluster_analysis_splats
        ):
            message = (
                "Refused cluster analysis preview because "
                f"splat_count={total_splats} exceeds "
                f"max_cluster_analysis_splats={max_cluster_analysis_splats}. "
                "Disable the abort flag to run sampled approximate analysis instead."
            )
            logger.info("LichtFeld cluster preview: %s", message)
            return ClusterAnalysisSummary(
                distance_threshold=distance_threshold,
                min_cluster_size=min_cluster_size,
                total_splats=total_splats,
                analyzed_splats=0,
                total_clusters=0,
                largest_cluster_size=0,
                small_cluster_count=0,
                candidate_floating_cluster_count=0,
                candidate_floating_splat_count=0,
                approximate=False,
                refused=True,
                sampling_stride=1,
                message=message,
                used_native_sampling=False,
                stats_elapsed_seconds=stats_elapsed_seconds,
                read_means_elapsed_seconds=read_means_elapsed_seconds,
                sampling_elapsed_seconds=0.0,
                cloud_build_elapsed_seconds=0.0,
                clustering_elapsed_seconds=0.0,
            )

        logger.info(
            "LichtFeld cluster preview: before sampling total_splats=%s max_cluster_analysis_splats=%s",
            total_splats,
            max_cluster_analysis_splats,
        )
        sampling_started_at = perf_counter()
        if materialized_position_rows is not None:
            sampled_rows, sampling_stride = sample_position_rows(
                materialized_position_rows,
                max_cluster_analysis_splats,
            )
            used_native_sampling = False
        else:
            sampled_rows, sampling_stride, used_native_sampling = extract_sampled_position_rows(
                position_source,
                max_cluster_analysis_splats,
                total_splats=total_splats,
            )
        approximate = len(sampled_rows) != total_splats
        sampling_elapsed_seconds = _elapsed_seconds(sampling_started_at)
        logger.info(
            "LichtFeld cluster preview: after sampling analyzed_splats=%s total_splats=%s "
            "sampling_stride=%s approximate=%s native_sampling=%s elapsed=%.3fs",
            len(sampled_rows),
            total_splats,
            sampling_stride,
            approximate,
            used_native_sampling,
            sampling_elapsed_seconds,
        )

        logger.info(
            "LichtFeld cluster preview: before building GaussianCloud analyzed_splats=%s",
            len(sampled_rows),
        )
        cloud_build_started_at = perf_counter()
        cloud = build_gaussian_cloud_from_positions(sampled_rows)
        cloud_build_elapsed_seconds = _elapsed_seconds(cloud_build_started_at)
        logger.info(
            "LichtFeld cluster preview: after building GaussianCloud splat_count=%s elapsed=%.3fs",
            cloud.count(),
            cloud_build_elapsed_seconds,
        )

        logger.info(
            "LichtFeld cluster preview: before clustering approximate=%s sampling_stride=%s",
            approximate,
            sampling_stride,
        )
        clustering_started_at = perf_counter()
        clusters = analyze_clusters(
            cloud,
            distance_threshold=distance_threshold,
            min_cluster_size=1,
        )
        clustering_elapsed_seconds = _elapsed_seconds(clustering_started_at)
        logger.info(
            "LichtFeld cluster preview: after clustering total_clusters=%s elapsed=%.3fs",
            len(clusters),
            clustering_elapsed_seconds,
        )
        largest = largest_cluster(clusters)
        small_clusters = clusters_smaller_than(clusters, min_cluster_size)
        candidate_floating_clusters = [
            cluster
            for cluster in clusters_outside_largest(clusters)
            if cluster.count < min_cluster_size
        ]
        if approximate:
            message = (
                "Cluster analysis preview complete in approximate sampled mode."
            )
        else:
            message = "Cluster analysis preview complete."
        return ClusterAnalysisSummary(
            distance_threshold=distance_threshold,
            min_cluster_size=min_cluster_size,
            total_splats=total_splats,
            analyzed_splats=cloud.count(),
            total_clusters=len(clusters),
            largest_cluster_size=0 if largest is None else largest.count,
            small_cluster_count=len(small_clusters),
            candidate_floating_cluster_count=len(candidate_floating_clusters),
            candidate_floating_splat_count=sum(
                cluster.count for cluster in candidate_floating_clusters
            ),
            approximate=approximate,
            refused=False,
            sampling_stride=sampling_stride,
            message=message,
            used_native_sampling=used_native_sampling,
            stats_elapsed_seconds=stats_elapsed_seconds,
            read_means_elapsed_seconds=read_means_elapsed_seconds,
            sampling_elapsed_seconds=sampling_elapsed_seconds,
            cloud_build_elapsed_seconds=cloud_build_elapsed_seconds,
            clustering_elapsed_seconds=clustering_elapsed_seconds,
        )

    def analyze_voxel_clusters_preview(
        self,
        voxel_size: float,
        min_voxel_cluster_size: int = 1,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> VoxelClusterAnalysisSummary:
        if voxel_size <= 0.0:
            raise InvalidParameterError("voxel_size must be strictly positive.")
        if min_voxel_cluster_size < 1:
            raise InvalidParameterError("min_voxel_cluster_size must be at least 1.")
        if max_splats < 1:
            raise InvalidParameterError("max_splats must be at least 1.")

        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)

        logger.info("LichtFeld voxel preview: before reading means")
        read_means_started_at = perf_counter()
        position_source = resolve_position_source(model)
        read_means_elapsed_seconds = _elapsed_seconds(read_means_started_at)
        logger.info(
            "LichtFeld voxel preview: after reading means source_type=%s elapsed=%.3fs",
            type(position_source).__name__,
            read_means_elapsed_seconds,
        )

        total_splats = get_position_source_count(position_source)
        materialized_position_rows: list[tuple[float, float, float]] | None = None
        if total_splats is None:
            materialized_position_rows = _coerce_position_rows(position_source)
            total_splats = len(materialized_position_rows)

        logger.info(
            "LichtFeld voxel preview: total_splats=%s max_splats=%s abort_if_above_limit=%s voxel_size=%.4f min_voxel_cluster_size=%s",
            total_splats,
            max_splats,
            abort_if_above_limit,
            voxel_size,
            min_voxel_cluster_size,
        )
        if abort_if_above_limit and total_splats > max_splats:
            message = (
                "Refused voxel cluster preview because "
                f"splat_count={total_splats} exceeds max_splats={max_splats}. "
                "Disable the abort flag to run sampled approximate voxel analysis instead."
            )
            logger.info("LichtFeld voxel preview: %s", message)
            return VoxelClusterAnalysisSummary(
                voxel_size=voxel_size,
                min_voxel_cluster_size=min_voxel_cluster_size,
                total_splats=total_splats,
                analyzed_splats=0,
                occupied_voxels=0,
                total_voxel_clusters=0,
                largest_voxel_cluster_voxel_count=0,
                largest_voxel_cluster_estimated_splats=0,
                small_voxel_cluster_count=0,
                estimated_floating_splats=0,
                approximate=False,
                refused=True,
                sampling_stride=1,
                message=message,
                used_native_sampling=False,
                read_means_elapsed_seconds=read_means_elapsed_seconds,
                sampling_elapsed_seconds=0.0,
                voxel_analysis_elapsed_seconds=0.0,
            )

        logger.info("LichtFeld voxel preview: before sampling")
        sampling_started_at = perf_counter()
        if materialized_position_rows is not None:
            sampled_rows, sampling_stride = sample_position_rows(
                materialized_position_rows,
                max_splats,
            )
            used_native_sampling = False
        else:
            sampled_rows, sampling_stride, used_native_sampling = extract_sampled_position_rows(
                position_source,
                max_splats,
                total_splats=total_splats,
            )
        approximate = len(sampled_rows) != total_splats
        sampling_elapsed_seconds = _elapsed_seconds(sampling_started_at)
        logger.info(
            "LichtFeld voxel preview: after sampling analyzed_splats=%s total_splats=%s sampling_stride=%s approximate=%s native_sampling=%s elapsed=%.3fs",
            len(sampled_rows),
            total_splats,
            sampling_stride,
            approximate,
            used_native_sampling,
            sampling_elapsed_seconds,
        )

        logger.info("LichtFeld voxel preview: before voxel analysis")
        voxel_analysis_started_at = perf_counter()
        voxel_clusters = analyze_voxel_clusters(
            sampled_rows,
            voxel_size=voxel_size,
            min_voxel_cluster_size=1,
        )
        voxel_analysis_elapsed_seconds = _elapsed_seconds(voxel_analysis_started_at)
        logger.info(
            "LichtFeld voxel preview: after voxel analysis total_voxel_clusters=%s elapsed=%.3fs",
            len(voxel_clusters),
            voxel_analysis_elapsed_seconds,
        )

        largest = largest_voxel_cluster(voxel_clusters)
        small_clusters = voxel_clusters_smaller_than(voxel_clusters, min_voxel_cluster_size)
        floating_clusters = [
            cluster
            for cluster in voxel_clusters_outside_largest(voxel_clusters)
            if cluster.voxel_count < min_voxel_cluster_size
        ]
        if approximate:
            message = "Voxel cluster preview complete in approximate sampled mode."
        else:
            message = "Voxel cluster preview complete."
        return VoxelClusterAnalysisSummary(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            total_splats=total_splats,
            analyzed_splats=len(sampled_rows),
            occupied_voxels=sum(cluster.voxel_count for cluster in voxel_clusters),
            total_voxel_clusters=len(voxel_clusters),
            largest_voxel_cluster_voxel_count=0 if largest is None else largest.voxel_count,
            largest_voxel_cluster_estimated_splats=0
            if largest is None
            else largest.estimated_splat_count,
            small_voxel_cluster_count=len(small_clusters),
            estimated_floating_splats=sum(
                cluster.estimated_splat_count for cluster in floating_clusters
            ),
            approximate=approximate,
            refused=False,
            sampling_stride=sampling_stride,
            message=message,
            used_native_sampling=used_native_sampling,
            read_means_elapsed_seconds=read_means_elapsed_seconds,
            sampling_elapsed_seconds=sampling_elapsed_seconds,
            voxel_analysis_elapsed_seconds=voxel_analysis_elapsed_seconds,
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
        return self._soft_delete_native_selection_mask(
            scene,
            model,
            lichtfeld_module,
            native_selection_mask,
            selected_count,
            initial_count=initial_count,
        )

    def _soft_delete_native_selection_mask(
        self,
        scene: object,
        model: object,
        lichtfeld_module: object,
        native_selection_mask: object,
        selected_count: int,
        *,
        initial_count: int,
        workspace_session_snapshot: CleanupSession | None = None,
    ) -> ToolResult:
        soft_delete = getattr(model, "soft_delete", None)
        if not callable(soft_delete):
            raise AdapterUnavailableError(
                "Active LichtFeld combined model does not expose soft_delete for deletion."
            )
        logger.info(
            "LichtFeld soft_delete_selection: initial_count=%s selected_count=%s native_mask_type=%s native_mask_len=%s",
            initial_count,
            selected_count,
            type(native_selection_mask).__name__,
            _safe_length(native_selection_mask),
        )
        logger.info("LichtFeld soft_delete_selection: before model.soft_delete()")
        self._store_last_delete(
            native_selection_mask,
            selected_count,
            workspace_session_snapshot=workspace_session_snapshot,
        )
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

        apply_deleted_entry = self._resolve_apply_deleted_callable(scene, model)
        if apply_deleted_entry is not None:
            apply_deleted_label, apply_deleted = apply_deleted_entry
            self._log_native_selection_state(
                "apply_pending_delete: before pre-apply selection clear",
                scene,
                model,
            )
            self._prepare_native_selection_for_apply_deleted(
                scene,
                model,
                lichtfeld_module,
                context_label="apply_pending_delete",
            )
            self._log_native_selection_state(
                "apply_pending_delete: after pre-apply selection clear",
                scene,
                model,
            )
            self._log_native_selection_state(
                "apply_pending_delete: before apply_deleted()",
                scene,
                model,
            )
            logger.info(
                "LichtFeld apply_pending_delete: before %s",
                apply_deleted_label,
            )
            apply_deleted()
            model = self._refresh_model_after_apply_deleted(
                scene,
                model,
                context_label="apply_pending_delete",
            )
            self._log_native_selection_state(
                "apply_pending_delete: after apply_deleted()",
                scene,
                model,
            )
            logger.info(
                "LichtFeld apply_pending_delete: after %s remaining_count=%s",
                apply_deleted_label,
                self._read_current_model_splat_count(model),
            )
            self._last_finalized_delete_count = pending_count
            self._last_finalized_restore_message = (
                "The last LichtFeld delete was already finalized with apply_deleted(); "
                "undelete(mask) only works before apply_deleted()."
            )
            self._clear_last_delete()
            self._invalidate_cleanup_workspace()
        else:
            logger.info(
                "LichtFeld apply_pending_delete: model.apply_deleted() skipped; "
                "soft delete remains reversible"
            )

        self._log_native_selection_state(
            "apply_pending_delete: before selection reset",
            scene,
            model,
        )
        self._reset_native_selection_after_apply_deleted(
            scene,
            model,
            lichtfeld_module,
            context_label="apply_pending_delete",
        )
        self._log_native_selection_state(
            "apply_pending_delete: after selection reset",
            scene,
            model,
        )
        self._log_delete_cleanup_step(
            "scene.notify_changed()",
            lambda: self._notify_scene_changed(scene),
        )

        if apply_deleted_entry is not None:
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
            if self._last_finalized_restore_message is not None:
                raise AdapterUnavailableError(self._last_finalized_restore_message)
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
        restored_workspace = self._restore_cleanup_workspace_preview_state(
            scene,
            model,
            lichtfeld_module,
        )
        if restored_workspace is None:
            self._selection.clear_cache()
        self._log_delete_cleanup_step(
            "scene.notify_changed()",
            lambda: self._notify_scene_changed(scene),
        )
        if restored_workspace is None:
            self._clear_workspace_preview_state()
        restored_count = self._last_delete_count
        self._clear_last_delete()
        self._last_finalized_delete_count = 0
        self._last_finalized_restore_message = None
        return ToolResult(message=f"Restored {restored_count} deleted splats.")

    def _store_last_delete(
        self,
        native_mask: object,
        deleted_count: int,
        *,
        workspace_session_snapshot: CleanupSession | None = None,
    ) -> None:
        self._last_delete_mask = native_mask
        self._last_delete_count = deleted_count
        self._last_delete_workspace_session = workspace_session_snapshot
        self._last_finalized_delete_count = 0
        self._last_finalized_restore_message = None
        if workspace_session_snapshot is not None:
            logger.info(
                "LichtFeld cleanup workspace soft delete: Saved workspace preview state. "
                "saved_selected_count=%s",
                workspace_session_snapshot.workspace.selected_count,
            )

    def _clear_last_delete(self) -> None:
        self._last_delete_mask = None
        self._last_delete_count = 0
        self._last_delete_workspace_session = None
        self._pending_cleanup_apply_project_path = None

    def _has_reversible_soft_delete(self) -> bool:
        return self._last_delete_mask is not None and self._last_delete_count > 0

    def _invalidate_cleanup_workspace(self) -> None:
        self._cleanup_workspace_session = None
        self._last_cleanup_preview = None

    def _clear_workspace_preview_state(
        self,
        *,
        workspace_state: str = "active",
    ) -> None:
        session = self._cleanup_workspace_session
        if session is None:
            return
        workspace = session.workspace
        session.workspace = replace(
            workspace,
            candidate_selection_mask=(),
            preview_selected_indices=(),
            preview_selection_active=False,
            native_selection_handle=None,
            selected_count=0,
            selection_percentage=0.0,
            selection_source="no active cleanup preview",
            selection_mode="replace",
            native_selection_mask=None,
            native_selection_mask_size=None,
            workspace_state=workspace_state,
        )

    def _snapshot_cleanup_workspace_session(self, session: CleanupSession) -> CleanupSession:
        workspace = session.workspace
        return CleanupSession(
            workspace=replace(
                workspace,
                native_selection_mask=self._copy_native_selection_mask(
                    workspace.native_selection_mask
                ),
            ),
            sampled_gaussian_cloud=session.sampled_gaussian_cloud,
        )

    def _restore_cleanup_workspace_preview_state(
        self,
        scene: object,
        model: object,
        lichtfeld_module: object,
    ) -> CleanupWorkspace | None:
        snapshot_session = self._last_delete_workspace_session
        if snapshot_session is None:
            return None

        workspace = snapshot_session.workspace
        current_scene_generation = self._read_scene_generation(scene, model)
        current_splat_count = self._read_current_model_splat_count(model)
        current_model_splat_count = current_splat_count

        if get_scene_path(scene) != workspace.scene_profile.project_path:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="restore_scene_path_changed",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_model_splat_count,
            )
            self._invalidate_cleanup_workspace()
            self._last_delete_workspace_session = None
            return None
        if current_splat_count != workspace.scene_profile.total_splats:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="restore_scene_splat_count_changed",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_model_splat_count,
            )
            self._invalidate_cleanup_workspace()
            self._last_delete_workspace_session = None
            return None

        restored_native_mask = self._copy_native_selection_mask(workspace.native_selection_mask)
        restored_mask_size = self._native_mask_size(restored_native_mask)
        if restored_native_mask is None:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="restore_workspace_mask_missing",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_model_splat_count,
            )
            self._invalidate_cleanup_workspace()
            self._last_delete_workspace_session = None
            return None
        if restored_mask_size is None:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="restore_workspace_mask_size_unavailable",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_model_splat_count,
            )
            self._invalidate_cleanup_workspace()
            self._last_delete_workspace_session = None
            return None
        if restored_mask_size != current_splat_count:
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="restore_workspace_mask_size_mismatch",
                current_generation=current_scene_generation,
                current_splat_count=current_splat_count,
                current_model_splat_count=current_model_splat_count,
                workspace_mask_size=restored_mask_size,
            )
            self._invalidate_cleanup_workspace()
            self._last_delete_workspace_session = None
            return None

        restored_report = self._with_scene_generation(
            workspace.scene_analysis_report,
            current_scene_generation,
        )
        restored_workspace = replace(
            workspace,
            scene_analysis_report=restored_report,
            native_selection_mask=restored_native_mask,
            native_selection_mask_size=restored_mask_size,
            scene_generation=current_scene_generation,
            workspace_state="active",
        )
        self._cleanup_workspace_session = CleanupSession(
            workspace=restored_workspace,
            sampled_gaussian_cloud=snapshot_session.sampled_gaussian_cloud,
        )
        self._restore_native_selection_mask(scene, restored_native_mask)
        restored_selection_mask = self._selection.read_scene_selection_mask(
            scene,
            current_splat_count,
            lf_module=lichtfeld_module,
            allow_invalid_mask=True,
        )
        if restored_selection_mask is None:
            self._selection.clear_cache()
        else:
            self._selection.cache_mask(restored_selection_mask)

        analysis_state = self._last_scene_analysis
        if (
            analysis_state is not None
            and analysis_state.project_path == restored_workspace.scene_profile.project_path
            and analysis_state.total_splats == current_splat_count
        ):
            self._last_scene_analysis = self._retimestamp_analysis_state(
                analysis_state,
                current_scene_generation,
            )

        logger.info(
            "LichtFeld cleanup workspace restore: Workspace preview restored. "
            "restored_selected_count=%s",
            restored_workspace.selected_count,
        )
        return restored_workspace

    def _restore_native_selection_mask(
        self,
        scene: object,
        native_selection_mask: object,
    ) -> None:
        setter = getattr(scene, "set_selection_mask", None)
        if callable(setter):
            setter(native_selection_mask)
            return
        for attribute_name in ("selection_mask", "_selection_mask"):
            if hasattr(scene, attribute_name):
                setattr(scene, attribute_name, native_selection_mask)
                break
        try:
            restored_mask_values = [bool(value) for value in native_selection_mask]  # type: ignore[arg-type]
        except Exception:
            return
        if hasattr(scene, "last_selection_mask"):
            setattr(scene, "last_selection_mask", restored_mask_values)

    def _prepare_native_selection_for_apply_deleted(
        self,
        scene: object,
        model: object,
        lichtfeld_module: object,
        *,
        context_label: str,
    ) -> None:
        current_splat_count = self._read_current_model_splat_count(model)
        self._log_delete_cleanup_step(
            f"{context_label}: scene.clear_selection() pre-apply_deleted",
            lambda: self._selection.clear_selection_via_scene(scene),
        )
        self._log_delete_cleanup_step(
            f"{context_label}: lichtfeld.deselect_all() pre-apply_deleted",
            lambda: self._selection.deselect_all(lichtfeld_module),
        )
        try:
            self._selection.reset_scene_selection_mask_natively(
                scene,
                current_splat_count,
                lichtfeld_module,
                model=model,
            )
            logger.info(
                "LichtFeld %s: pre-apply native selection reset applied current_splat_count=%s",
                context_label,
                current_splat_count,
            )
        except AdapterUnavailableError as exc:
            logger.info(
                "LichtFeld %s: pre-apply native selection reset unavailable: %s",
                context_label,
                exc,
            )
        self._selection.clear_cache()
        self._log_delete_cleanup_step(
            f"{context_label}: scene.notify_changed() pre-apply_deleted",
            lambda: self._notify_scene_changed(scene),
        )

    @staticmethod
    def _resolve_apply_deleted_callable(
        scene: object,
        model: object,
    ) -> tuple[str, object] | None:
        for label, owner in (
            ("scene.apply_deleted()", scene),
            ("model.apply_deleted()", model),
        ):
            apply_deleted = getattr(owner, "apply_deleted", None)
            if callable(apply_deleted):
                return label, apply_deleted
        return None

    @staticmethod
    def _invalidate_scene_cache(scene: object) -> bool:
        invalidate_cache = getattr(scene, "invalidate_cache", None)
        if not callable(invalidate_cache):
            return False
        invalidate_cache()
        return True

    def _refresh_model_after_apply_deleted(
        self,
        scene: object,
        fallback_model: object,
        *,
        context_label: str,
    ) -> object:
        self._log_delete_cleanup_step(
            f"{context_label}: scene.invalidate_cache()",
            lambda: self._invalidate_scene_cache(scene),
        )
        try:
            return require_combined_model(scene)
        except AdapterUnavailableError as exc:
            logger.info(
                "LichtFeld %s: combined model refresh unavailable after apply_deleted: %s",
                context_label,
                exc,
            )
            return fallback_model

    def _reset_native_selection_after_apply_deleted(
        self,
        scene: object,
        model: object,
        lichtfeld_module: object,
        *,
        context_label: str,
    ) -> None:
        self._log_delete_cleanup_step(
            f"{context_label}: scene.clear_selection()",
            lambda: self._selection.clear_selection_via_scene(scene),
        )
        self._log_delete_cleanup_step(
            f"{context_label}: lichtfeld.deselect_all()",
            lambda: self._selection.deselect_all(lichtfeld_module),
        )
        self._log_delete_cleanup_step(
            f"{context_label}: scene.reset_selection_state()",
            lambda: self._selection.reset_selection_state(scene),
        )
        current_splat_count = self._read_current_model_splat_count(model)
        try:
            self._selection.reset_scene_selection_mask_natively(
                scene,
                current_splat_count,
                lichtfeld_module,
                model=model,
            )
            logger.info(
                "LichtFeld %s: explicit native selection reset applied current_splat_count=%s",
                context_label,
                current_splat_count,
            )
        except AdapterUnavailableError as exc:
            logger.info(
                "LichtFeld %s: explicit native selection reset unavailable: %s",
                context_label,
                exc,
            )
        self._selection.clear_cache()

    def _log_native_selection_state(
        self,
        label: str,
        scene: object,
        model: object,
    ) -> None:
        native_selection_mask = self._selection.read_native_selection_mask(scene)
        renderer_selection_mask = self._read_selection_owner_mask(
            scene,
            owner_attributes=("renderer", "get_renderer"),
        )
        pipeline_selection_mask = self._read_selection_owner_mask(
            scene,
            owner_attributes=("rendering_pipeline", "get_rendering_pipeline"),
        )
        logger.info(
            "LichtFeld %s: model_size=%s selection_tensor_size=%s selection_tensor_id=%s "
            "renderer_selection_tensor_size=%s renderer_selection_tensor_id=%s "
            "pipeline_selection_tensor_size=%s pipeline_selection_tensor_id=%s",
            label,
            self._read_current_model_splat_count(model),
            self._native_mask_size(native_selection_mask),
            self._native_mask_id(native_selection_mask),
            self._native_mask_size(renderer_selection_mask),
            self._native_mask_id(renderer_selection_mask),
            self._native_mask_size(pipeline_selection_mask),
            self._native_mask_id(pipeline_selection_mask),
        )

    @staticmethod
    def _read_selection_owner_mask(
        scene: object,
        *,
        owner_attributes: tuple[str, ...],
    ) -> object | None:
        owner = LichtfeldAdapter._read_owner_attribute(scene, owner_attributes)
        return LichtfeldAdapter._read_owner_attribute(
            owner,
            (
                "selection_mask",
                "selection_tensor",
                "preview_selection_tensor",
                "gpu_selection_mask",
                "gpu_selection_tensor",
                "cpu_selection_mask",
                "cpu_selection_tensor",
            ),
        )

    @staticmethod
    def _read_owner_attribute(
        owner: object | None,
        attribute_names: tuple[str, ...],
    ) -> object | None:
        if owner is None:
            return None
        for attribute_name in attribute_names:
            value = getattr(owner, attribute_name, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    continue
            if value is not None:
                return value
        return None

    def _require_cleanup_analysis_state(self) -> _SceneAnalysisState:
        analysis_state = self._last_scene_analysis
        if analysis_state is None:
            raise AdapterUnavailableError(
                "No previous scene analysis is available. Run Analyze Scene first."
            )
        return analysis_state

    def _require_cleanup_workspace(self) -> CleanupWorkspace:
        return self._require_cleanup_session().workspace

    def _require_cleanup_session(self) -> CleanupSession:
        session = self._cleanup_workspace_session
        if session is None:
            raise AdapterUnavailableError("No cleanup workspace is active. Open Cleanup Workspace first.")
        self._ensure_workspace_scene_matches(session.workspace)
        return session

    def _ensure_workspace_scene_matches(self, workspace: CleanupWorkspace) -> CleanupWorkspace:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        if get_scene_path(scene) != workspace.scene_profile.project_path:
            current_generation = None
            current_model_splat_count = None
            try:
                model = require_combined_model(scene)
                current_generation = self._read_scene_generation(scene, model)
                current_model_splat_count = self._read_current_model_splat_count(model)
            except Exception:
                pass
            self._log_cleanup_workspace_validation_failure(
                workspace,
                invalidation_reason="scene_path_changed",
                current_generation=current_generation,
                current_splat_count=current_model_splat_count,
                current_model_splat_count=current_model_splat_count,
            )
            self._invalidate_cleanup_workspace()
            raise AdapterUnavailableError(
                "Cleanup workspace no longer matches the active scene. Open Cleanup Workspace again."
            )
        return workspace

    @staticmethod
    def _analysis_state_from_workspace(workspace: CleanupWorkspace) -> _SceneAnalysisState:
        return _SceneAnalysisState(
            report=workspace.scene_analysis_report,
            sampled_rows=list(workspace.sampled_rows),
            sampled_indices=list(workspace.sampled_indices),
            project_path=workspace.scene_profile.project_path,
            total_splats=workspace.scene_profile.total_splats,
            approximate=workspace.approximate,
            scene_generation=workspace.scene_generation,
        )

    @staticmethod
    def _with_scene_generation(
        report: SceneAnalysisReport,
        scene_generation: object | None,
    ) -> SceneAnalysisReport:
        return replace(
            report,
            scene_stats={
                **report.scene_stats,
                "scene_generation": scene_generation,
            },
        )

    @classmethod
    def _retimestamp_analysis_state(
        cls,
        analysis_state: _SceneAnalysisState,
        scene_generation: object | None,
    ) -> _SceneAnalysisState:
        return _SceneAnalysisState(
            report=cls._with_scene_generation(analysis_state.report, scene_generation),
            sampled_rows=list(analysis_state.sampled_rows),
            sampled_indices=list(analysis_state.sampled_indices),
            project_path=analysis_state.project_path,
            total_splats=analysis_state.total_splats,
            approximate=analysis_state.approximate,
            scene_generation=scene_generation,
        )

    def _resolve_cleanup_analysis_state_for_workspace(
        self,
        params: CleanupParameters,
    ) -> _SceneAnalysisReuseDecision:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        project_path = get_scene_path(scene)
        scene_generation = self._read_scene_generation(scene, model)
        cached_state = self._last_scene_analysis
        if cached_state is None:
            return _SceneAnalysisReuseDecision(
                analysis_state=self._recompute_cleanup_analysis_from_scene(params),
                analysis_reused=False,
                sample_reused=False,
                reason="missing_analysis",
            )
        if project_path != cached_state.project_path:
            return _SceneAnalysisReuseDecision(
                analysis_state=self._recompute_cleanup_analysis_from_scene(params),
                analysis_reused=False,
                sample_reused=False,
                reason="scene_path_changed",
            )
        if self._scene_generation_changed(cached_state.scene_generation, scene_generation):
            return _SceneAnalysisReuseDecision(
                analysis_state=self._recompute_cleanup_analysis_from_scene(params),
                analysis_reused=False,
                sample_reused=False,
                reason="scene_generation_changed",
            )

        position_source = resolve_position_source(model)
        total_splats = self._read_splat_count_without_selection(model, position_source)
        if total_splats is not None and total_splats != cached_state.total_splats:
            return _SceneAnalysisReuseDecision(
                analysis_state=self._recompute_cleanup_analysis_from_scene(params),
                analysis_reused=False,
                sample_reused=False,
                reason="scene_splat_count_changed",
            )
        if self._analysis_requires_recomputation(cached_state, params):
            updated_state = self._recompute_cleanup_analysis_from_cached_sample(
                cached_state,
                params,
                scene_generation=scene_generation,
            )
            self._last_scene_analysis = updated_state
            return _SceneAnalysisReuseDecision(
                analysis_state=updated_state,
                analysis_reused=False,
                sample_reused=True,
                reason="analysis_parameters_changed",
            )
        return _SceneAnalysisReuseDecision(
            analysis_state=cached_state,
            analysis_reused=True,
            sample_reused=True,
            reason="cached_analysis_valid",
        )

    def _recompute_cleanup_analysis_from_scene(
        self,
        params: CleanupParameters,
    ) -> _SceneAnalysisState:
        self.analyze_scene(
            voxel_size=params.voxel_size,
            min_voxel_cluster_size=params.min_voxel_cluster_size,
        )
        analysis_state = self._last_scene_analysis
        if analysis_state is None:
            raise AdapterUnavailableError(
                "Cleanup workspace could not refresh scene analysis for the active scene."
            )
        return analysis_state

    def _recompute_cleanup_analysis_from_cached_sample(
        self,
        analysis_state: _SceneAnalysisState,
        params: CleanupParameters,
        *,
        scene_generation: object | None,
    ) -> _SceneAnalysisState:
        scene_stats = analysis_state.report.scene_stats
        context = SceneAnalysisContext(
            scene_name=str(scene_stats.get("scene_name", "unknown_scene")),
            project_path=analysis_state.project_path,
            positions=list(analysis_state.sampled_rows),
            total_splats=analysis_state.total_splats,
            analyzed_splats=len(analysis_state.sampled_rows),
            selected_splats=int(scene_stats.get("selected_splats", 0)),
            deleted_splats=int(scene_stats.get("deleted_splats", 0)),
            voxel_size=params.voxel_size,
            min_voxel_cluster_size=params.min_voxel_cluster_size,
            approximate=analysis_state.approximate,
            sampling_stride=int(scene_stats.get("sampling_stride", 1)),
            used_native_sampling=bool(scene_stats.get("used_native_sampling", False)),
            max_splats=int(scene_stats.get("max_splats", max(1, len(analysis_state.sampled_rows)))),
            aborted=bool(scene_stats.get("aborted", False)),
        )
        report = build_default_scene_analysis_engine().analyze(context)
        return self._retimestamp_analysis_state(
            _SceneAnalysisState(
                report=report,
                sampled_rows=list(analysis_state.sampled_rows),
                sampled_indices=list(analysis_state.sampled_indices),
                project_path=analysis_state.project_path,
                total_splats=analysis_state.total_splats,
                approximate=analysis_state.approximate,
            ),
            scene_generation,
        )

    @staticmethod
    def _analysis_requires_recomputation(
        analysis_state: _SceneAnalysisState,
        params: CleanupParameters,
    ) -> bool:
        scene_stats = analysis_state.report.scene_stats
        cached_voxel_size = float(scene_stats.get("voxel_size", params.voxel_size))
        cached_min_cluster_size = int(
            scene_stats.get("min_voxel_cluster_size", params.min_voxel_cluster_size)
        )
        return not math.isclose(
            cached_voxel_size,
            params.voxel_size,
            rel_tol=0.0,
            abs_tol=1e-9,
        ) or cached_min_cluster_size != params.min_voxel_cluster_size

    def _reusable_cleanup_session_for_scene(
        self,
        project_path: str,
    ) -> CleanupSession | None:
        session = self._cleanup_workspace_session
        if session is None:
            return None
        if session.workspace.scene_profile.project_path != project_path:
            return None
        return session

    @staticmethod
    def _normalize_cleanup_parameters(
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
        cluster_distance_threshold: float,
        outlier_distance: float,
        cleanup_aggressiveness: float,
        preset_name: str,
    ) -> CleanupParameters:
        if voxel_size <= 0.0:
            raise InvalidParameterError("voxel_size must be strictly positive.")
        if min_voxel_cluster_size < 1:
            raise InvalidParameterError("min_voxel_cluster_size must be at least 1.")
        if cluster_distance_threshold <= 0.0:
            raise InvalidParameterError("cluster_distance_threshold must be strictly positive.")
        if outlier_distance <= 0.0:
            raise InvalidParameterError("outlier_distance must be strictly positive.")
        if cleanup_aggressiveness < 0.0 or cleanup_aggressiveness > 1.0:
            raise InvalidParameterError("cleanup_aggressiveness must be between 0.0 and 1.0.")
        normalized_preset_name = str(preset_name).strip() or "Custom"
        return CleanupParameters(
            voxel_size=float(voxel_size),
            min_voxel_cluster_size=int(min_voxel_cluster_size),
            cluster_distance_threshold=float(cluster_distance_threshold),
            outlier_distance=float(outlier_distance),
            cleanup_aggressiveness=float(cleanup_aggressiveness),
            preset_name=normalized_preset_name,
        )

    def _build_cleanup_workspace_session(
        self,
        analysis_state: _SceneAnalysisState,
        params: CleanupParameters,
        *,
        existing_session: CleanupSession | None = None,
        analysis_reused: bool,
        sample_reused: bool,
    ) -> CleanupSession:
        lichtfeld_module = load_lichtfeld()
        scene = require_active_scene(lichtfeld_module)
        model = require_combined_model(scene)
        scene_path = get_scene_path(scene)
        if scene_path != analysis_state.project_path:
            self._invalidate_cleanup_workspace()
            raise AdapterUnavailableError(
                "Cleanup workspace no longer matches the active scene. Run Analyze Scene again."
            )

        total_workspace_start = perf_counter()
        sampled_gaussian_cloud = (
            existing_session.sampled_gaussian_cloud
            if existing_session is not None
            else build_gaussian_cloud_from_positions(list(analysis_state.sampled_rows))
        )

        candidate_update_start = perf_counter()
        build = self._build_cleanup_candidate_preview(
            analysis_state,
            params,
            sampled_gaussian_cloud=sampled_gaussian_cloud,
        )
        candidate_update_time = _elapsed_seconds(candidate_update_start)

        selection_start = perf_counter()
        if build.summary.approximate:
            self._apply_cleanup_candidate_selection_indices_only(
                scene,
                lichtfeld_module,
                build.selected_indices,
            )
        else:
            self._apply_cleanup_candidate_selection(
                scene,
                model,
                lichtfeld_module,
                build.selection_mask,
            )
        selection_update_time = _elapsed_seconds(selection_start)
        total_workspace_update_time = _elapsed_seconds(total_workspace_start)
        native_selection_mask = self._copy_native_selection_mask(
            self._selection.read_native_selection_mask(scene)
        )
        native_selection_mask_size = self._native_mask_size(native_selection_mask)

        selection_source = ", ".join(build.selection_sources) or "no cleanup candidates"
        selection_percentage = (
            0.0
            if analysis_state.total_splats <= 0
            else len(build.selected_indices) / analysis_state.total_splats
        )
        workspace = CleanupWorkspace(
            scene_analysis_report=analysis_state.report,
            cleanup_candidate_summary=build.summary,
            scene_profile=build_scene_profile(analysis_state.report),
            current_cleanup_parameters=params,
            sampled_rows=tuple(analysis_state.sampled_rows),
            sampled_indices=tuple(analysis_state.sampled_indices),
            candidate_selection_mask=tuple(build.selection_mask),
            preview_selected_indices=tuple(build.selected_indices),
            preview_selection_active=True,
            native_selection_handle=f"{analysis_state.project_path}#cleanup-preview",
            selected_count=len(build.selected_indices),
            selection_percentage=selection_percentage,
            selection_mode="replace",
            selection_source=selection_source,
            approximate=build.summary.approximate,
            analysis_reused=analysis_reused,
            candidate_update_time=candidate_update_time,
            workspace_update_time=total_workspace_update_time,
            selection_update_time=selection_update_time,
            total_workspace_update_time=total_workspace_update_time,
            estimated_sample_reuse=1.0 if sample_reused else 0.0,
            native_selection_mask=native_selection_mask,
            native_selection_mask_size=native_selection_mask_size,
            scene_generation=analysis_state.scene_generation,
            workspace_state="active",
        )
        logger.info(
            "LichtFeld cleanup workspace: analysis_reused=%s candidate_update_time=%.6fs "
            "selection_update_time=%.6fs total_workspace_update_time=%.6fs "
            "estimated_sample_reuse=%.2f quality_score=%s scene_health=%s "
            "estimated_affected_splats_total=%s selected_count=%s native_mask_available=%s",
            workspace.analysis_reused,
            workspace.candidate_update_time,
            workspace.selection_update_time,
            workspace.total_workspace_update_time,
            workspace.estimated_sample_reuse,
            workspace.scene_profile.quality_score,
            workspace.scene_profile.profile_label,
            workspace.cleanup_candidate_summary.estimated_affected_splats_total,
            workspace.selected_count,
            workspace.native_selection_mask is not None,
        )
        return CleanupSession(
            workspace=workspace,
            sampled_gaussian_cloud=sampled_gaussian_cloud,
        )

    def _clear_native_selection_preview(
        self,
        scene: object,
        model: object,
        lichtfeld_module: object,
    ) -> None:
        if self._selection.clear_selection_via_scene(scene):
            self._selection.clear_cache()
            notify_scene_changed(scene)
            return
        if self._selection.deselect_all(lichtfeld_module):
            self._selection.clear_cache()
            notify_scene_changed(scene)
            return
        expected_length = len(extract_position_rows(model))
        self._selection.clear_scene_selection_mask(
            scene,
            expected_length,
            lichtfeld_module,
            model=model,
        )
        self._selection.clear_cache()
        notify_scene_changed(scene)

    @staticmethod
    def _read_scene_generation(
        scene: object,
        model: object,
    ) -> object | None:
        for owner in (scene, model):
            for attribute_name in (
                "scene_content_stamp",
                "scene_content_generation",
                "content_stamp",
                "content_generation",
                "scene_generation",
                "content_version",
                "data_generation",
            ):
                value = getattr(owner, attribute_name, None)
                if callable(value):
                    try:
                        value = value()
                    except Exception:
                        continue
                if value is None:
                    continue
                if isinstance(value, (str, int, float, bool)):
                    return value
                try:
                    return int(value)
                except Exception:
                    return str(value)
        return None

    def _log_cleanup_workspace_validation_failure(
        self,
        workspace: CleanupWorkspace,
        *,
        invalidation_reason: str,
        current_generation: object | None,
        current_splat_count: int | None,
        current_model_splat_count: int | None,
        workspace_mask_size: int | None = None,
    ) -> None:
        logger.info(
            "LichtFeld cleanup workspace validity: workspace_generation=%s "
            "current_generation=%s workspace_splat_count=%s current_splat_count=%s "
            "workspace_mask_size=%s current_model_splat_count=%s invalidation_reason=%s",
            workspace.scene_generation,
            current_generation,
            workspace.scene_profile.total_splats,
            current_splat_count,
            workspace.native_selection_mask_size
            if workspace_mask_size is None
            else workspace_mask_size,
            current_model_splat_count,
            invalidation_reason,
        )

    @staticmethod
    def _scene_generation_changed(
        cached_generation: object | None,
        current_generation: object | None,
    ) -> bool:
        if cached_generation is None and current_generation is None:
            return False
        return cached_generation != current_generation

    @staticmethod
    def _read_splat_count_without_selection(
        model: object,
        position_source: object,
    ) -> int | None:
        num_points = getattr(model, "num_points", None)
        if callable(num_points):
            try:
                return int(num_points())
            except Exception:
                pass
        if num_points is not None:
            try:
                return int(num_points)
            except Exception:
                pass
        return get_position_source_count(position_source)

    def _read_current_model_splat_count(self, model: object) -> int:
        position_source = resolve_position_source(model)
        splat_count = self._read_splat_count_without_selection(model, position_source)
        if splat_count is None:
            raise AdapterUnavailableError(
                "Active LichtFeld combined model does not expose a reliable splat count for "
                "cleanup workspace soft delete."
            )
        return splat_count

    @staticmethod
    def _copy_native_selection_mask(native_selection_mask: object | None) -> object | None:
        if native_selection_mask is None:
            return None
        for method_name in ("clone", "copy"):
            method = getattr(native_selection_mask, method_name, None)
            if not callable(method):
                continue
            try:
                return method()
            except Exception:
                continue
        return native_selection_mask

    @staticmethod
    def _native_mask_size(native_selection_mask: object | None) -> int | None:
        if native_selection_mask is None:
            return None
        shape = getattr(native_selection_mask, "shape", None)
        if shape is not None:
            try:
                if len(shape) > 0:
                    return int(shape[0])
            except Exception:
                pass
        try:
            return len(native_selection_mask)  # type: ignore[arg-type]
        except Exception:
            return None

    @staticmethod
    def _native_mask_id(native_selection_mask: object | None) -> str:
        if native_selection_mask is None:
            return "none"
        return hex(id(native_selection_mask))

    def _apply_cleanup_candidate_selection(
        self,
        scene: object,
        model: object,
        lichtfeld_module: object,
        selection_mask: list[bool],
    ) -> None:
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

    def _apply_cleanup_candidate_selection_indices_only(
        self,
        scene: object,
        lichtfeld_module: object,
        selected_indices: list[int],
    ) -> None:
        self._selection.apply_native_selection(
            scene,
            selected_indices,
            lichtfeld_module,
        )
        self._selection.clear_cache()
        notify_scene_changed(scene)

    def _build_cleanup_candidate_preview(
        self,
        analysis_state: _SceneAnalysisState,
        params: CleanupParameters,
        *,
        sampled_gaussian_cloud,
    ) -> _CleanupCandidateBuild:
        report = analysis_state.report
        position_rows = analysis_state.sampled_rows
        (
            selection_mask,
            selection_sources,
            floating_groups,
            estimated_floating_splats,
            small_voxel_clusters,
            estimated_small_cluster_splats,
            sparse_regions,
            estimated_sparse_splats,
        ) = self._build_cleanup_candidate_mask(
            position_rows,
            sampled_gaussian_cloud=sampled_gaussian_cloud,
            voxel_size=params.voxel_size,
            min_voxel_cluster_size=params.min_voxel_cluster_size,
            cluster_distance_threshold=params.cluster_distance_threshold,
            outlier_distance=params.outlier_distance,
            cleanup_aggressiveness=params.cleanup_aggressiveness,
        )
        selected_indices = [
            analysis_state.sampled_indices[index]
            for index, selected in enumerate(selection_mask)
            if selected and index < len(analysis_state.sampled_indices)
        ]
        affected_splats_in_sample = sum(selection_mask)
        total_splats = int(report.scene_stats.get("total_splats", analysis_state.total_splats))
        analyzed_splats = int(report.scene_stats.get("analyzed_splats", len(position_rows)))
        approximate = bool(report.scene_stats.get("approximate", analysis_state.approximate))
        affected_percentage_of_sample = (
            0.0 if analyzed_splats <= 0 else affected_splats_in_sample / analyzed_splats
        )
        estimated_affected_splats_total = (
            int(round(affected_percentage_of_sample * total_splats))
            if approximate
            else affected_splats_in_sample
        )
        estimated_percentage_of_total = (
            0.0 if total_splats <= 0 else estimated_affected_splats_total / total_splats
        )
        warnings: list[str] = []
        recommendations: list[str] = []
        notes = ["Workspace selection preview.", "Scene remains unchanged."]
        if approximate:
            notes.append("Approximate sampled preview.")
        if floating_groups > 0:
            warnings.append(f"{floating_groups} floating voxel groups detected.")
            recommendations.append("Preview floating islands.")
        if "disconnected clusters" in selection_sources:
            warnings.append("Disconnected cleanup clusters detected.")
            recommendations.append("Inspect disconnected cleanup clusters.")
        if "distant outliers" in selection_sources:
            warnings.append("Distant outliers detected.")
            recommendations.append("Inspect distant outliers before cleanup.")
        if "sparse singleton regions" in selection_sources:
            recommendations.append("Scene appears sparse.")
        if estimated_affected_splats_total <= 0:
            recommendations.append("No cleanup required.")
        else:
            recommendations.append(
                f"Estimated cleanup in analyzed sample: {affected_percentage_of_sample * 100.0:.1f}%"
            )
            if approximate:
                recommendations.append(
                    f"Estimated cleanup extrapolated to full scene: {estimated_percentage_of_total * 100.0:.1f}%"
                )
        summary = CleanupCandidateSummary(
            scene_name=str(report.scene_stats.get("scene_name", "unknown_scene")),
            project_path=str(report.scene_stats.get("project_path", analysis_state.project_path)),
            total_splats=total_splats,
            analyzed_splats=analyzed_splats,
            quality_score=report.quality_score,
            analysis_time=report.analysis_time,
            approximate=approximate,
            report_only=True,
            candidate_group_count=(
                floating_groups
                + sparse_regions
                + (1 if "distant outliers" in selection_sources else 0)
            ),
            affected_splats_in_sample=affected_splats_in_sample,
            estimated_affected_splats_total=estimated_affected_splats_total,
            affected_percentage_of_sample=affected_percentage_of_sample,
            estimated_percentage_of_total=estimated_percentage_of_total,
            estimated_affected_splats=estimated_affected_splats_total,
            floating_voxel_groups=floating_groups,
            estimated_floating_splats=estimated_floating_splats,
            small_voxel_clusters=small_voxel_clusters,
            estimated_small_cluster_splats=estimated_small_cluster_splats,
            sparse_regions=sparse_regions,
            estimated_sparse_splats=estimated_sparse_splats,
            warnings=warnings,
            recommendations=recommendations,
            notes=notes,
        )
        return _CleanupCandidateBuild(
            summary=summary,
            selection_mask=selection_mask,
            selected_indices=selected_indices,
            selection_sources=selection_sources,
        )

    @staticmethod
    def _build_cleanup_candidate_mask(
        position_rows: list[tuple[float, float, float]],
        *,
        sampled_gaussian_cloud,
        voxel_size: float,
        min_voxel_cluster_size: int,
        cluster_distance_threshold: float,
        outlier_distance: float,
        cleanup_aggressiveness: float,
    ) -> tuple[list[bool], tuple[str, ...], int, int, int, int, int, int]:
        if not position_rows:
            return [], (), 0, 0, 0, 0, 0, 0

        voxel_counts: dict[tuple[int, int, int], int] = {}
        voxel_keys: list[tuple[int, int, int]] = []
        for x, y, z in position_rows:
            key = (
                math.floor(x / voxel_size),
                math.floor(y / voxel_size),
                math.floor(z / voxel_size),
            )
            voxel_keys.append(key)
            voxel_counts[key] = voxel_counts.get(key, 0) + 1

        components = LichtfeldAdapter._collect_voxel_components(set(voxel_counts))
        if not components:
            return [False] * len(position_rows), (), 0, 0, 0, 0, 0, 0

        largest_component = max(
            components,
            key=lambda keys: (
                sum(voxel_counts[key] for key in keys),
                len(keys),
            ),
        )
        floating_components = [keys for keys in components if keys is not largest_component]
        floating_keys = {
            key
            for keys in floating_components
            for key in keys
        }
        clusters = analyze_clusters(
            sampled_gaussian_cloud,
            distance_threshold=cluster_distance_threshold,
            min_cluster_size=1,
        )
        disconnected_clusters = clusters_outside_largest(clusters)
        disconnected_cluster_indices = {
            gaussian_id.value
            for cluster in disconnected_clusters
            for gaussian_id in cluster.gaussian_ids
            if gaussian_id.value < len(position_rows)
        }
        small_disconnected_clusters = [
            cluster
            for cluster in disconnected_clusters
            if cluster.count < max(1, min_voxel_cluster_size)
        ]
        sparse_threshold = 1 if cleanup_aggressiveness < 0.75 else 2
        sparse_keys = {
            key
            for key, count in voxel_counts.items()
            if count <= sparse_threshold and cleanup_aggressiveness >= 0.35
        }
        sparse_selected_flags = [key in sparse_keys for key in voxel_keys]
        distant_flags = LichtfeldAdapter._distant_outlier_flags(
            position_rows,
            voxel_size=voxel_size,
            outlier_distance=outlier_distance,
            cleanup_aggressiveness=cleanup_aggressiveness,
        )
        selection_mask = [
            (
                key in floating_keys
                or index in disconnected_cluster_indices
                or sparse_selected_flags[index]
                or distant_flags[index]
            )
            for index, key in enumerate(voxel_keys)
        ]
        sources: list[str] = []
        if floating_keys:
            sources.append("floating voxel clusters")
        if disconnected_cluster_indices:
            sources.append("disconnected clusters")
        if any(distant_flags):
            sources.append("distant outliers")
        if any(sparse_selected_flags):
            sources.append("sparse singleton regions")
        small_voxel_clusters = sum(
            1
            for keys in floating_components
            if len(keys) < max(1, min_voxel_cluster_size)
        )
        estimated_small_cluster_splats = sum(
            voxel_counts[key]
            for keys in floating_components
            if len(keys) < max(1, min_voxel_cluster_size)
            for key in keys
        )
        estimated_small_cluster_splats = max(
            estimated_small_cluster_splats,
            sum(cluster.count for cluster in small_disconnected_clusters),
        )
        small_voxel_clusters = max(
            small_voxel_clusters,
            len(small_disconnected_clusters),
        )
        estimated_floating_splats = sum(voxel_counts[key] for key in floating_keys)
        estimated_floating_splats = max(
            estimated_floating_splats,
            sum(cluster.count for cluster in disconnected_clusters),
        )
        sparse_regions = len(sparse_keys)
        estimated_sparse_splats = sum(
            1 for selected in sparse_selected_flags if selected
        )
        return (
            selection_mask,
            tuple(dict.fromkeys(sources)),
            len(floating_components),
            estimated_floating_splats,
            small_voxel_clusters,
            estimated_small_cluster_splats,
            sparse_regions,
            estimated_sparse_splats,
        )

    @staticmethod
    def _distant_outlier_flags(
        position_rows: list[tuple[float, float, float]],
        *,
        voxel_size: float,
        outlier_distance: float,
        cleanup_aggressiveness: float,
    ) -> list[bool]:
        if len(position_rows) < 5:
            return [False] * len(position_rows)

        xs = sorted(position[0] for position in position_rows)
        ys = sorted(position[1] for position in position_rows)
        zs = sorted(position[2] for position in position_rows)
        bounds: list[tuple[float, float]] = []
        for values in (xs, ys, zs):
            low = LichtfeldAdapter._percentile(values, 0.05)
            high = LichtfeldAdapter._percentile(values, 0.95)
            robust_span = max(high - low, voxel_size * 4.0, 1.0)
            margin = max(
                outlier_distance,
                robust_span * max(0.5, 1.5 - cleanup_aggressiveness),
            )
            bounds.append((low - margin, high + margin))

        flags: list[bool] = []
        for x, y, z in position_rows:
            flags.append(
                x < bounds[0][0]
                or x > bounds[0][1]
                or y < bounds[1][0]
                or y > bounds[1][1]
                or z < bounds[2][0]
                or z > bounds[2][1]
            )
        return flags

    @staticmethod
    def _collect_voxel_components(
        voxel_keys: set[tuple[int, int, int]],
    ) -> list[set[tuple[int, int, int]]]:
        components: list[set[tuple[int, int, int]]] = []
        visited: set[tuple[int, int, int]] = set()

        for start_key in voxel_keys:
            if start_key in visited:
                continue
            stack = [start_key]
            component: set[tuple[int, int, int]] = set()
            visited.add(start_key)
            while stack:
                current = stack.pop()
                component.add(current)
                for neighbor in LichtfeldAdapter._neighbor_voxel_keys(current):
                    if neighbor not in voxel_keys or neighbor in visited:
                        continue
                    visited.add(neighbor)
                    stack.append(neighbor)
            components.append(component)
        return components

    @staticmethod
    def _neighbor_voxel_keys(
        key: tuple[int, int, int],
    ) -> tuple[tuple[int, int, int], ...]:
        x, y, z = key
        return (
            (x - 1, y, z),
            (x + 1, y, z),
            (x, y - 1, z),
            (x, y + 1, z),
            (x, y, z - 1),
            (x, y, z + 1),
        )

    @staticmethod
    def _percentile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        index = max(0, min(len(values) - 1, int(round((len(values) - 1) * ratio))))
        return values[index]

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

__all__ = [
    "ClusterAnalysisSummary",
    "LichtfeldAdapter",
    "LichtfeldPluginAdapter",
    "VoxelClusterAnalysisSummary",
]
