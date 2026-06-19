"""Public adapter facade for the LichtFeld plugin integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter

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
from lichtfeld_mcp.core.scene_analysis import (
    CleanupCandidateSummary,
    SceneAnalysisContext,
    SceneAnalysisReport,
    build_cleanup_candidate_summary,
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
                else:
                    sampled_rows, sampling_stride, used_native_sampling = extract_sampled_position_rows(
                        position_source,
                        max_splats,
                        total_splats=total_splats,
                    )
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
        logger.info(
            "LichtFeld scene analysis complete: quality_score=%s warnings=%s "
            "recommendations=%s analysis_time=%.3fs",
            report.quality_score,
            len(report.warnings),
            len(report.recommendations),
            report.analysis_time,
        )
        return report

    def preview_cleanup_candidates(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> CleanupCandidateSummary:
        logger.info(
            "LichtFeld cleanup preview: starting voxel_size=%.4f min_voxel_cluster_size=%s "
            "max_splats=%s abort_if_above_limit=%s",
            voxel_size,
            min_voxel_cluster_size,
            max_splats,
            abort_if_above_limit,
        )
        report = self.analyze_scene(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            max_splats=max_splats,
            abort_if_above_limit=abort_if_above_limit,
        )
        summary = build_cleanup_candidate_summary(report)
        logger.info(
            "LichtFeld cleanup preview: candidate_groups=%s estimated_affected_splats=%s "
            "floating_voxel_groups=%s small_voxel_clusters=%s sparse_regions=%s",
            summary.candidate_group_count,
            summary.estimated_affected_splats,
            summary.floating_voxel_groups,
            summary.small_voxel_clusters,
            summary.sparse_regions,
        )
        logger.info("LichtFeld cleanup preview: preview report only")
        return summary

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
