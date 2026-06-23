"""Deterministic mock adapter used until Lichtfeld exposes a public API.

This adapter simulates operations on a Gaussian Splatting scene. It is deliberately
simple but it preserves the semantics expected from a real editor: open a project,
select splats, delete/crop, optimize, export and undo.
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path

from lichtfeld_mcp.adapters.base import LichtfeldAdapter
from lichtfeld_mcp.core.cleanup_metrics import (
    CLEANUP_SOURCE_DISCONNECTED,
    CLEANUP_SOURCE_FLOATING,
    CLEANUP_SOURCE_OUTLIER,
    CLEANUP_SOURCE_SPARSE,
    build_cleanup_source_breakdown,
    compute_cleanup_intensity_metrics,
)
from lichtfeld_mcp.core.cleanup_presets import iter_cleanup_presets
from lichtfeld_mcp.core.cleanup_workspace import (
    CleanupParameters,
    CleanupPresetComparisonEntry,
    CleanupPresetComparisonReport,
    CleanupSession,
    CleanupWorkspace,
    build_scene_profile,
)
from lichtfeld_mcp.core.constraints import validate_selection_mode
from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud
from lichtfeld_mcp.core.scene_analysis import (
    AnalysisResult,
    AnalysisSeverity,
    CleanupCandidateSummary,
    SceneAnalysisReport,
    build_cleanup_candidate_summary,
)
from lichtfeld_mcp.core.presets import get_optimization_profile
from lichtfeld_mcp.core.requests import (
    BoxSelectionRequest,
    ColorSelectionRequest,
    ExportRequest,
    HeightRange,
    OptimizationRequest,
)
from lichtfeld_mcp.core.validation import normalize_measurement_unit, normalize_scene_path
from lichtfeld_mcp.errors import ProjectNotOpenError
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


@dataclass
class MockSceneState:
    path: str
    name: str
    splat_count: int = 4_200_000
    selected_count: int = 0
    generation: int = 0
    file_size_mb: float = 840.0
    bounds: Box3D = field(
        default_factory=lambda: Box3D(
            min=Vec3(x=-5.0, y=-5.0, z=-0.1), max=Vec3(x=5.0, y=5.0, z=4.0)
        )
    )
    sh_degree: int = 3
    opacity_mean: float = 0.73
    density_score: float = 0.82


@dataclass(frozen=True)
class MockNativeSelectionMask:
    mask_size: int
    selected_count: int

    @property
    def shape(self) -> tuple[int]:
        return (self.mask_size,)


class MockLichtfeldAdapter(LichtfeldAdapter):
    """In-memory adapter for development and demonstrations."""

    def __init__(self) -> None:
        self._scene: MockSceneState | None = None
        self._snapshots: list[MockSceneState] = []
        self._history: list[HistoryEntry] = []
        self._last_scene_analysis: SceneAnalysisReport | None = None
        self._last_scene_analysis_generation: int | None = None
        self._last_scene_analysis_total_splats = 0
        self._last_scene_analysis_voxel_size: float | None = None
        self._last_scene_analysis_min_voxel_cluster_size: int | None = None
        self._last_cleanup_preview: CleanupCandidateSummary | None = None
        self._cleanup_workspace_session: CleanupSession | None = None
        self._pending_cleanup_apply_count = 0

    def _require_scene(self) -> MockSceneState:
        if self._scene is None:
            raise ProjectNotOpenError("No Lichtfeld project is currently open.")
        return self._scene

    def _resolve_workspace_analysis(
        self,
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
    ) -> tuple[SceneAnalysisReport, bool, bool]:
        scene = self._require_scene()
        cached_report = self._last_scene_analysis
        cached_scene_is_valid = (
            cached_report is not None
            and self._last_scene_analysis_generation == scene.generation
            and self._last_scene_analysis_total_splats == scene.splat_count
        )
        cached_params_match = (
            cached_scene_is_valid
            and self._last_scene_analysis_voxel_size == voxel_size
            and self._last_scene_analysis_min_voxel_cluster_size == min_voxel_cluster_size
        )
        if cached_params_match:
            return cached_report, True, True

        sample_reused = cached_scene_is_valid
        report = self.analyze_scene(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
        )
        return report, False, sample_reused

    def _push_history(self, action: str, details: dict[str, object]) -> None:
        if self._scene is not None:
            self._snapshots.append(deepcopy(self._scene))
        self._history.append(HistoryEntry(index=len(self._history), action=action, details=details))

    def _bump_scene_generation(self) -> None:
        if self._scene is None:
            return
        self._scene.generation += 1

    def open_project(self, path: str) -> ProjectInfo:
        normalized = normalize_scene_path(path, label="project path")
        name = Path(normalized).stem or "untitled_scene"
        # Derive stable fake complexity from project name.
        seed = sum(ord(ch) for ch in name)
        splats = 1_500_000 + (seed % 6_000_000)
        size = round(splats / 5000.0, 2)
        self._scene = MockSceneState(path=normalized, name=name, splat_count=splats, file_size_mb=size)
        self._snapshots.clear()
        self._history.clear()
        self._last_scene_analysis = None
        self._last_scene_analysis_generation = None
        self._last_scene_analysis_total_splats = 0
        self._last_scene_analysis_voxel_size = None
        self._last_scene_analysis_min_voxel_cluster_size = None
        self._last_cleanup_preview = None
        self._cleanup_workspace_session = None
        self._push_history("open_project", {"path": normalized})
        return ProjectInfo(path=normalized, name=name, splat_count=splats, selected_count=0)

    def save_project(self) -> ToolResult:
        scene = self._require_scene()
        self._push_history("save_project", {"path": scene.path})
        return ToolResult(message=f"Project saved: {scene.path}")

    def close_project(self) -> ToolResult:
        scene = self._require_scene()
        name = scene.name
        self._push_history("close_project", {"name": name})
        self._scene = None
        self._last_scene_analysis = None
        self._last_scene_analysis_generation = None
        self._last_scene_analysis_total_splats = 0
        self._last_scene_analysis_voxel_size = None
        self._last_scene_analysis_min_voxel_cluster_size = None
        self._last_cleanup_preview = None
        self._cleanup_workspace_session = None
        return ToolResult(message=f"Project closed: {name}")

    def get_scene_stats(self) -> SceneStats:
        scene = self._require_scene()
        return SceneStats(
            project_name=scene.name,
            project_path=scene.path,
            splat_count=scene.splat_count,
            selected_count=scene.selected_count,
            file_size_mb=scene.file_size_mb,
            estimated_vram_mb=round(scene.splat_count * (32 + scene.sh_degree * 12) / 1_000_000, 2),
            bounds=scene.bounds,
            sh_degree=scene.sh_degree,
            opacity_mean=scene.opacity_mean,
            density_score=scene.density_score,
            history_length=len(self._history),
        )

    def preview_cleanup_candidates(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> CleanupCandidateSummary:
        if self._last_scene_analysis is None:
            raise ProjectNotOpenError("No previous scene analysis is available. Run Analyze Scene first.")
        report = self._last_scene_analysis
        self._last_cleanup_preview = self._with_cleanup_metrics(
            build_cleanup_candidate_summary(report),
            cleanup_aggressiveness=0.5,
            selection_sources=(CLEANUP_SOURCE_FLOATING,),
        )
        return self._last_cleanup_preview

    def preview_cleanup_selection(self) -> CleanupSelectionPreviewResult:
        scene = self._require_scene()
        if self._last_scene_analysis is None:
            raise ProjectNotOpenError("No previous scene analysis is available. Run Analyze Scene first.")
        if self._last_cleanup_preview is None:
            raise ProjectNotOpenError(
                "No cleanup preview is available. Run Preview Cleanup Selection after Analyze Scene."
            )
        scene.selected_count = self._last_cleanup_preview.affected_splats_in_sample
        selection_source = "floating voxel clusters"
        if self._last_cleanup_preview.sparse_regions > 0:
            selection_source += ", sparse singleton regions"
        return CleanupSelectionPreviewResult(
            selected_count=scene.selected_count,
            selection_percentage=(
                0.0
                if scene.splat_count <= 0
                else scene.selected_count / scene.splat_count
            ),
            selection_mode="replace",
            selection_source=selection_source,
            approximate=self._last_cleanup_preview.approximate,
            message=(
                "Approximate sampled selection preview. "
                "Selected splats represent estimated cleanup regions. "
                "Run Detailed mode for a more precise preview."
                if self._last_cleanup_preview.approximate
                else "Exact cleanup selection preview."
            ),
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
        _, analysis_reused, sample_reused = self._resolve_workspace_analysis(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
        )
        workspace = self._build_cleanup_workspace(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            cluster_distance_threshold=cluster_distance_threshold,
            outlier_distance=outlier_distance,
            cleanup_aggressiveness=cleanup_aggressiveness,
            preset_name=preset_name,
            analysis_reused=analysis_reused,
            sample_reused=sample_reused,
        )
        self._cleanup_workspace_session = CleanupSession(
            workspace=workspace,
            sampled_gaussian_cloud=GaussianCloud(splat_count=len(workspace.sampled_rows)),
        )
        return workspace

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
        if self._cleanup_workspace_session is None:
            raise ProjectNotOpenError("No cleanup workspace is active. Open Cleanup Workspace first.")
        _, analysis_reused, sample_reused = self._resolve_workspace_analysis(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
        )
        workspace = self._build_cleanup_workspace(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            cluster_distance_threshold=cluster_distance_threshold,
            outlier_distance=outlier_distance,
            cleanup_aggressiveness=cleanup_aggressiveness,
            preset_name=preset_name,
            analysis_reused=analysis_reused,
            sample_reused=sample_reused,
        )
        self._cleanup_workspace_session.workspace = workspace
        return workspace

    def get_cleanup_workspace(self) -> CleanupWorkspace | None:
        if self._cleanup_workspace_session is None:
            return None
        return self._cleanup_workspace_session.workspace

    def invalidate_cleanup_workspace_preview(self) -> ToolResult:
        scene = self._require_scene()
        if self._cleanup_workspace_session is None:
            return ToolResult(message="Cleanup workspace preview was already inactive.")
        workspace = self._cleanup_workspace_session.workspace
        if not workspace.preview_selection_active:
            return ToolResult(message="Cleanup workspace preview was already inactive.")
        scene.selected_count = 0
        self._cleanup_workspace_session.workspace = replace(
            workspace,
            candidate_selection_mask=(),
            preview_selected_indices=(),
            preview_selection_active=False,
            native_selection_handle=None,
            selected_count=0,
            selection_percentage=0.0,
            selection_source="no active cleanup preview",
            native_selection_mask=None,
            native_selection_mask_size=None,
            workspace_state="active",
        )
        return ToolResult(
            message="Cleanup workspace preview invalidated. Run Update Preview to rebuild it."
        )

    def compare_cleanup_presets(self) -> CleanupPresetComparisonReport:
        scene = self._require_scene()
        if self._last_scene_analysis is None:
            raise ProjectNotOpenError("No previous scene analysis is available. Run Analyze Scene first.")
        entries: list[CleanupPresetComparisonEntry] = []
        for preset in iter_cleanup_presets():
            summary, selection_sources, _ = self._build_cleanup_workspace_summary(
                scene=scene,
                voxel_size=preset.voxel_size,
                min_voxel_cluster_size=preset.min_voxel_cluster_size,
                outlier_distance=preset.outlier_distance,
                cleanup_aggressiveness=preset.cleanup_aggressiveness,
            )
            entries.append(
                CleanupPresetComparisonEntry(
                    preset_name=preset.name,
                    cleanup_candidate_summary=summary,
                    selection_sources=selection_sources,
                )
            )
        return CleanupPresetComparisonReport(
            scene_name=scene.name,
            project_path=scene.path,
            approximate=bool(self._last_scene_analysis.scene_stats.get("approximate", False)),
            analysis_reused=True,
            entries=tuple(entries),
        )

    def reset_cleanup_workspace(self) -> ToolResult:
        scene = self._require_scene()
        scene.selected_count = 0
        self._cleanup_workspace_session = None
        self._last_cleanup_preview = None
        return ToolResult(message="Cleanup workspace reset. Native preview selection cleared.")

    def soft_delete_cleanup_workspace_selection(
        self,
        *,
        max_deletable_splats: int | None = None,
        max_deletable_percentage: float | None = None,
    ) -> CleanupSoftDeleteResult:
        scene = self._require_scene()
        if self._cleanup_workspace_session is None:
            raise ProjectNotOpenError("No cleanup workspace is active. Open Cleanup Workspace first.")
        workspace = self._cleanup_workspace_session.workspace
        if workspace.workspace_state == "soft_deleted" or not workspace.preview_selection_active:
            raise ProjectNotOpenError(
                "No cleanup workspace preview selection is available. Update Preview first."
            )
        if workspace.scene_generation != scene.generation:
            raise ProjectNotOpenError(
                "Cleanup workspace no longer matches the current scene generation. "
                "Open Cleanup Workspace again."
            )
        if workspace.scene_profile.total_splats != scene.splat_count:
            raise ProjectNotOpenError(
                "Cleanup workspace no longer matches the current scene splat count. "
                "Open Cleanup Workspace again."
            )
        if workspace.native_selection_mask is None:
            raise ProjectNotOpenError(
                "Cleanup workspace preview exists, but no workspace-owned native selection mask "
                "is available for soft delete."
            )
        if workspace.native_selection_mask_size != scene.splat_count:
            raise ProjectNotOpenError(
                "Cleanup workspace native selection mask size does not match the current scene "
                "splat count."
            )
        selected_count = workspace.selected_count
        if selected_count <= 0:
            raise ProjectNotOpenError("Cleanup workspace preview selection is empty.")
        selected_ratio = 0.0 if scene.splat_count <= 0 else selected_count / scene.splat_count
        if max_deletable_splats is not None and selected_count > max_deletable_splats:
            raise ProjectNotOpenError(
                "Cleanup workspace soft delete refused: "
                f"selected_count={selected_count} exceeds max_deletable_splats="
                f"{max_deletable_splats}."
            )
        if (
            max_deletable_percentage is not None
            and selected_ratio > max_deletable_percentage
        ):
            raise ProjectNotOpenError(
                "Cleanup workspace soft delete refused: "
                f"selected_percentage={selected_ratio:.6f} exceeds "
                f"max_deletable_percentage={max_deletable_percentage:.6f}."
            )
        deleted = min(scene.splat_count, selected_count)
        self._push_history("soft_delete_cleanup_workspace_selection", {"deleted": deleted})
        scene.selected_count = 0
        self._cleanup_workspace_session.workspace = replace(
            workspace,
            candidate_selection_mask=(),
            preview_selected_indices=(),
            preview_selection_active=False,
            native_selection_handle=None,
            selected_count=0,
            selection_percentage=0.0,
            selection_source="no active cleanup preview",
            native_selection_mask=None,
            native_selection_mask_size=None,
            workspace_state="soft_deleted",
        )
        self._pending_cleanup_apply_count = deleted
        return CleanupSoftDeleteResult(
            soft_deleted_count=deleted,
            total_splats=scene.splat_count,
            percentage=(0.0 if scene.splat_count <= 0 else deleted / scene.splat_count),
            restore_available=True,
            message=(
                f"Soft-deleted {deleted:,} cleanup workspace splats. "
                "Reversible until apply_deleted() is called."
            ),
        )

    def soft_delete_current_cleanup_selection(self) -> CleanupSoftDeleteResult:
        return self.soft_delete_cleanup_workspace_selection()

    def soft_delete_cleanup_candidates(self) -> ToolResult:
        scene = self._require_scene()
        if self._last_cleanup_preview is None:
            raise ProjectNotOpenError(
                "No cleanup preview is available. Run Preview Cleanup Selection first."
            )
        if self._last_cleanup_preview.approximate:
            raise ProjectNotOpenError(
                "Cleanup preview is approximate-only; no reliable native selection is available."
            )
        deleted = min(scene.splat_count, self._last_cleanup_preview.estimated_affected_splats)
        if deleted <= 0:
            raise ProjectNotOpenError("Cleanup preview did not identify any reliable cleanup candidates.")
        self._push_history("soft_delete_cleanup_candidates", {"deleted": deleted})
        scene.splat_count -= deleted
        scene.selected_count = 0
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        self._bump_scene_generation()
        self._last_cleanup_preview = None
        self._pending_cleanup_apply_count = deleted
        return ToolResult(
            message=(
                f"Soft-deleted {deleted:,} cleanup candidate splats. "
                "Reversible until apply_deleted() is called."
            )
        )

    def apply_cleanup_candidates(self) -> ToolResult:
        scene = self._require_scene()
        if self._pending_cleanup_apply_count <= 0:
            raise ProjectNotOpenError(
                "No confirmed cleanup soft delete is available. "
                "Run Soft Delete Cleanup Preview after Preview Cleanup Selection."
            )
        deleted = min(scene.splat_count, self._pending_cleanup_apply_count)
        self._push_history("apply_cleanup_candidates", {"deleted": deleted})
        self._pending_cleanup_apply_count = 0
        return ToolResult(
            message=f"Permanently applied cleanup of {deleted:,} soft-deleted splats."
        )

    def apply_cleanup_workspace_deleted(self) -> CleanupApplyDeletedResult:
        scene = self._require_scene()
        if self._cleanup_workspace_session is None:
            raise ProjectNotOpenError("No cleanup workspace is active. Open Cleanup Workspace first.")
        workspace = self._cleanup_workspace_session.workspace
        if workspace.workspace_state != "soft_deleted":
            raise ProjectNotOpenError(
                "No cleanup workspace soft delete is available. "
                "Run Soft Delete Cleanup Workspace Selection first."
            )
        if self._pending_cleanup_apply_count <= 0:
            raise ProjectNotOpenError(
                "No reversible cleanup workspace soft delete is available to apply."
            )
        if workspace.scene_generation != scene.generation:
            self._cleanup_workspace_session = None
            raise ProjectNotOpenError(
                "Cleanup workspace no longer matches the current scene generation. "
                "Open Cleanup Workspace again."
            )
        if workspace.scene_profile.total_splats != scene.splat_count:
            self._cleanup_workspace_session = None
            raise ProjectNotOpenError(
                "Cleanup workspace no longer matches the current scene splat count. "
                "Open Cleanup Workspace again."
            )

        initial_splat_count = scene.splat_count
        soft_deleted_count = min(scene.splat_count, self._pending_cleanup_apply_count)
        self._push_history("apply_cleanup_workspace_deleted", {"deleted": soft_deleted_count})
        scene.splat_count -= soft_deleted_count
        scene.selected_count = 0
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        self._pending_cleanup_apply_count = 0
        self._bump_scene_generation()
        self._cleanup_workspace_session = None
        return CleanupApplyDeletedResult(
            initial_splat_count=initial_splat_count,
            soft_deleted_count=soft_deleted_count,
            permanently_deleted_count=soft_deleted_count,
            final_splat_count=scene.splat_count,
            restore_available=False,
            workspace_state="invalidated",
            message=f"Permanently applied cleanup of {soft_deleted_count:,} soft-deleted splats.",
        )

    def analyze_scene(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> SceneAnalysisReport:
        scene = self._require_scene()
        approximate = scene.splat_count > max_splats and not abort_if_above_limit
        aborted = scene.splat_count > max_splats and abort_if_above_limit
        results = [
            AnalysisResult(
                name="statistics",
                severity=AnalysisSeverity.INFO,
                summary="Scene statistics captured.",
                details={
                    "total_splats": scene.splat_count,
                    "deleted_splats": 0,
                    "selected_splats": scene.selected_count,
                },
            ),
            AnalysisResult(
                name="voxel_connectivity",
                severity=AnalysisSeverity.INFO,
                summary="Scene appears fully connected.",
                details={
                    "connected": True,
                    "floating_voxel_groups": 0,
                    "estimated_floating_splats": 0,
                    "small_voxel_clusters": 0,
                    "estimated_small_cluster_splats": 0,
                },
                recommendations=["No cleanup required."],
            ),
            AnalysisResult(
                name="bounding_box",
                severity=AnalysisSeverity.INFO,
                summary="Bounding box looks normal.",
                details={"distant_splats": 0, "abnormal_scene_size": False},
            ),
            AnalysisResult(
                name="density",
                severity=AnalysisSeverity.INFO,
                summary="Density distribution looks healthy.",
                details={
                    "occupied_voxels": max(1, min(max_splats, scene.splat_count) // max(1, min_voxel_cluster_size)),
                    "density_histogram": {"1": 0, "2-4": 0, "5-9": 0, "10-24": 1, "25+": 0},
                    "sparse_regions": 0,
                    "estimated_sparse_splats": 0,
                },
                recommendations=["Density looks healthy."],
            ),
        ]
        if aborted:
            results = [
                AnalysisResult(
                    name="statistics",
                    severity=AnalysisSeverity.WARNING,
                    summary="Scene analysis aborted by execution budget.",
                    details={
                        "total_splats": scene.splat_count,
                        "deleted_splats": 0,
                        "selected_splats": scene.selected_count,
                    },
                    warnings=["Analysis skipped because the execution budget was exceeded."],
                    recommendations=["Increase the analysis budget or allow sampled preview mode."],
                    score_impact=14,
                )
            ]

        warnings = [
            warning
            for result in results
            for warning in result.warnings
        ]
        recommendations = [
            recommendation
            for result in results
            for recommendation in result.recommendations
        ] or ["Scene is healthy."]
        report = SceneAnalysisReport(
            scene_stats={
                "scene_name": scene.name,
                "project_path": scene.path,
                "total_splats": scene.splat_count,
                "analyzed_splats": min(scene.splat_count, max_splats),
                "selected_splats": scene.selected_count,
                "deleted_splats": 0,
                "voxel_size": voxel_size,
                "min_voxel_cluster_size": min_voxel_cluster_size,
                "approximate": approximate,
                "sampling_stride": max(1, math.ceil(scene.splat_count / max_splats)),
                "used_native_sampling": False,
                "max_splats": max_splats,
                "aborted": aborted,
                "scene_generation": scene.generation,
            },
            quality_score=max(0, 100 - sum(result.score_impact for result in results)),
            warnings=warnings,
            recommendations=recommendations,
            analysis_time=0.0,
            results=results,
        )
        self._last_scene_analysis = report
        self._last_scene_analysis_generation = scene.generation
        self._last_scene_analysis_total_splats = scene.splat_count
        self._last_scene_analysis_voxel_size = voxel_size
        self._last_scene_analysis_min_voxel_cluster_size = min_voxel_cluster_size
        self._cleanup_workspace_session = None
        return report

    def _build_cleanup_workspace(
        self,
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
        cluster_distance_threshold: float,
        outlier_distance: float,
        cleanup_aggressiveness: float,
        preset_name: str,
        analysis_reused: bool,
        sample_reused: bool,
    ) -> CleanupWorkspace:
        scene = self._require_scene()
        if self._last_scene_analysis is None:
            raise ProjectNotOpenError("No previous scene analysis is available. Run Analyze Scene first.")
        summary, selection_source_parts, selected_count = self._build_cleanup_workspace_summary(
            scene=scene,
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            outlier_distance=outlier_distance,
            cleanup_aggressiveness=cleanup_aggressiveness,
        )
        scene.selected_count = selected_count
        selection_percentage = 0.0 if scene.splat_count <= 0 else selected_count / scene.splat_count
        selection_source = ", ".join(selection_source_parts)
        self._last_cleanup_preview = summary
        workspace_report = replace(
            self._last_scene_analysis,
            scene_stats={
                **self._last_scene_analysis.scene_stats,
                "estimated_affected_splats_total": summary.estimated_affected_splats_total,
                "estimated_percentage_of_total": summary.estimated_percentage_of_total,
            },
            warnings=list(summary.warnings) or list(self._last_scene_analysis.warnings),
        )
        return CleanupWorkspace(
            scene_analysis_report=workspace_report,
            cleanup_candidate_summary=summary,
            scene_profile=build_scene_profile(workspace_report),
            current_cleanup_parameters=CleanupParameters(
                voxel_size=voxel_size,
                min_voxel_cluster_size=min_voxel_cluster_size,
                cluster_distance_threshold=cluster_distance_threshold,
                outlier_distance=outlier_distance,
                cleanup_aggressiveness=cleanup_aggressiveness,
                preset_name=preset_name,
            ),
            sampled_rows=tuple((0.0, 0.0, 0.0) for _ in range(min(summary.analyzed_splats, 32))),
            sampled_indices=tuple(range(min(summary.analyzed_splats, 32))),
            candidate_selection_mask=tuple(True for _ in range(selected_count)),
            preview_selected_indices=tuple(range(selected_count)),
            preview_selection_active=True,
            native_selection_handle=f"{scene.path}#cleanup-preview",
            selected_count=selected_count,
            selection_percentage=selection_percentage,
            selection_mode="replace",
            selection_source=selection_source,
            approximate=summary.approximate,
            analysis_reused=analysis_reused,
            candidate_update_time=0.01,
            workspace_update_time=0.01,
            selection_update_time=0.01,
            total_workspace_update_time=0.01,
            estimated_sample_reuse=1.0 if sample_reused else 0.0,
            native_selection_mask=MockNativeSelectionMask(
                mask_size=scene.splat_count,
                selected_count=selected_count,
            ),
            native_selection_mask_size=scene.splat_count,
            scene_generation=scene.generation,
            workspace_state="active",
        )

    def _build_cleanup_workspace_summary(
        self,
        *,
        scene: MockSceneState,
        voxel_size: float,
        min_voxel_cluster_size: int,
        outlier_distance: float,
        cleanup_aggressiveness: float,
    ) -> tuple[CleanupCandidateSummary, tuple[str, ...], int]:
        base_summary = build_cleanup_candidate_summary(self._last_scene_analysis)
        estimated_total = max(
            0,
            min(
                scene.splat_count,
                int(round(base_summary.estimated_affected_splats_total * (0.5 + cleanup_aggressiveness))),
            ),
        )
        selected_count = (
            max(0, min(scene.splat_count, estimated_total // 4))
            if base_summary.approximate
            else estimated_total
        )
        selection_source_parts = [
            CLEANUP_SOURCE_FLOATING,
            CLEANUP_SOURCE_DISCONNECTED,
        ]
        if cleanup_aggressiveness >= 0.5:
            selection_source_parts.append(CLEANUP_SOURCE_SPARSE)
        if outlier_distance <= 2.5:
            selection_source_parts.append(CLEANUP_SOURCE_OUTLIER)
        summary = CleanupCandidateSummary(
            scene_name=base_summary.scene_name,
            project_path=base_summary.project_path,
            total_splats=base_summary.total_splats,
            analyzed_splats=base_summary.analyzed_splats,
            quality_score=base_summary.quality_score,
            analysis_time=base_summary.analysis_time,
            approximate=base_summary.approximate,
            report_only=True,
            candidate_group_count=base_summary.candidate_group_count,
            affected_splats_in_sample=max(base_summary.affected_splats_in_sample, selected_count),
            estimated_affected_splats_total=max(
                base_summary.estimated_affected_splats_total,
                estimated_total,
            ),
            affected_percentage_of_sample=base_summary.affected_percentage_of_sample,
            estimated_percentage_of_total=(
                0.0 if scene.splat_count <= 0 else estimated_total / scene.splat_count
            ),
            estimated_affected_splats=max(base_summary.estimated_affected_splats, estimated_total),
            floating_voxel_groups=base_summary.floating_voxel_groups,
            estimated_floating_splats=base_summary.estimated_floating_splats,
            small_voxel_clusters=base_summary.small_voxel_clusters,
            estimated_small_cluster_splats=base_summary.estimated_small_cluster_splats,
            sparse_regions=base_summary.sparse_regions,
            estimated_sparse_splats=base_summary.estimated_sparse_splats,
            warnings=list(base_summary.warnings),
            recommendations=list(base_summary.recommendations),
            notes=list(base_summary.notes) + ["Workspace selection preview."],
        )
        return (
            self._with_cleanup_metrics(
                summary,
                cleanup_aggressiveness=cleanup_aggressiveness,
                selection_sources=tuple(selection_source_parts),
            ),
            tuple(selection_source_parts),
            selected_count,
        )

    @staticmethod
    def _with_cleanup_metrics(
        summary: CleanupCandidateSummary,
        *,
        cleanup_aggressiveness: float,
        selection_sources: tuple[str, ...],
    ) -> CleanupCandidateSummary:
        source_sample_counts = {
            CLEANUP_SOURCE_FLOATING: (
                max(summary.affected_splats_in_sample // 2, 0)
                if CLEANUP_SOURCE_FLOATING in selection_sources
                else 0
            ),
            CLEANUP_SOURCE_DISCONNECTED: (
                min(summary.affected_splats_in_sample, max(summary.small_voxel_clusters * 25, 0))
                if CLEANUP_SOURCE_DISCONNECTED in selection_sources
                else 0
            ),
            CLEANUP_SOURCE_OUTLIER: (
                max(summary.affected_splats_in_sample // 6, 0)
                if CLEANUP_SOURCE_OUTLIER in selection_sources
                else 0
            ),
            CLEANUP_SOURCE_SPARSE: (
                min(summary.affected_splats_in_sample, max(summary.estimated_sparse_splats, 0))
                if CLEANUP_SOURCE_SPARSE in selection_sources
                else 0
            ),
        }
        source_breakdown = build_cleanup_source_breakdown(
            source_sample_counts=source_sample_counts,
            analyzed_splats=summary.analyzed_splats,
            total_splats=summary.total_splats,
            approximate=summary.approximate,
        )
        intensity_metrics = compute_cleanup_intensity_metrics(
            cleanup_aggressiveness=cleanup_aggressiveness,
            estimated_cleanup_percentage=summary.estimated_percentage_of_total,
            total_splats=summary.total_splats,
            source_breakdown=source_breakdown,
            floating_group_count=summary.floating_voxel_groups,
            disconnected_group_count=(1 if CLEANUP_SOURCE_DISCONNECTED in selection_sources else 0),
            sparse_region_count=summary.sparse_regions,
        )
        return replace(
            summary,
            selection_sources=selection_sources,
            source_breakdown=source_breakdown,
            cleanup_intensity_score=intensity_metrics.cleanup_intensity_score,
            aggressiveness_contribution=intensity_metrics.aggressiveness_contribution,
            estimated_cleanup_contribution=intensity_metrics.estimated_cleanup_contribution,
            floating_cluster_contribution=intensity_metrics.floating_cluster_contribution,
            disconnected_cluster_contribution=(
                intensity_metrics.disconnected_cluster_contribution
            ),
            outlier_contribution=intensity_metrics.outlier_contribution,
            sparse_region_contribution=intensity_metrics.sparse_region_contribution,
        )

    def select_by_box(self, box: Box3D, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        request = BoxSelectionRequest(box=box, mode=mode)
        self._push_history("select_by_box", {"box": request.box.model_dump(), "mode": request.mode})
        selected = max(1, int(scene.splat_count * 0.18))
        scene.selected_count = self._apply_selection_mode(
            scene.selected_count,
            selected,
            request.mode,
            scene.splat_count,
        )
        return SelectionResult(
            selected_count=scene.selected_count,
            selection_mode=request.mode,
            message="Box selection applied.",
        )

    def select_by_height(self, z_min: float | None, z_max: float | None, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        normalized_mode = validate_selection_mode(mode)
        self._push_history(
            "select_by_height",
            {"z_min": height_range.z_min, "z_max": height_range.z_max, "mode": normalized_mode},
        )
        selected = max(1, int(scene.splat_count * 0.25))
        scene.selected_count = self._apply_selection_mode(
            scene.selected_count,
            selected,
            normalized_mode,
            scene.splat_count,
        )
        return SelectionResult(
            selected_count=scene.selected_count,
            selection_mode=normalized_mode,
            message="Height selection applied.",
        )

    def select_by_color(self, r: int, g: int, b: int, tolerance: int = 20, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        request = ColorSelectionRequest.from_rgb(r=r, g=g, b=b, tolerance=tolerance, mode=mode)
        self._push_history(
            "select_by_color",
            {
                "r": request.color.r,
                "g": request.color.g,
                "b": request.color.b,
                "tolerance": request.tolerance,
                "mode": request.mode,
            },
        )
        selected = max(1, int(scene.splat_count * min(0.4, max(0.02, request.tolerance / 255.0))))
        scene.selected_count = self._apply_selection_mode(
            scene.selected_count,
            selected,
            request.mode,
            scene.splat_count,
        )
        return SelectionResult(
            selected_count=scene.selected_count,
            selection_mode=request.mode,
            message="Color selection applied.",
        )

    @staticmethod
    def _apply_selection_mode(current: int, selected: int, mode: str, total: int) -> int:
        if mode == "add":
            return min(total, current + selected)
        if mode == "subtract":
            return max(0, current - selected)
        return min(total, selected)

    def delete_selection(self) -> ToolResult:
        scene = self._require_scene()
        deleted = scene.selected_count
        self._push_history("delete_selection", {"deleted": deleted})
        scene.splat_count = max(0, scene.splat_count - deleted)
        scene.selected_count = 0
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        self._bump_scene_generation()
        return ToolResult(message=f"Deleted {deleted:,} selected splats.")

    def crop_by_box(self, box: Box3D, keep_inside: bool = True) -> ToolResult:
        scene = self._require_scene()
        request = BoxSelectionRequest(box=box)
        self._push_history("crop_by_box", {"box": request.box.model_dump(), "keep_inside": keep_inside})
        factor = 0.65 if keep_inside else 0.82
        before = scene.splat_count
        scene.splat_count = int(scene.splat_count * factor)
        scene.selected_count = 0
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        self._bump_scene_generation()
        return ToolResult(message=f"Cropped scene from {before:,} to {scene.splat_count:,} splats.")

    def crop_by_height(self, z_min: float | None, z_max: float | None, keep_inside: bool = True) -> ToolResult:
        scene = self._require_scene()
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        self._push_history(
            "crop_by_height",
            {"z_min": height_range.z_min, "z_max": height_range.z_max, "keep_inside": keep_inside},
        )
        factor = 0.72 if keep_inside else 0.88
        before = scene.splat_count
        scene.splat_count = int(scene.splat_count * factor)
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        self._bump_scene_generation()
        return ToolResult(message=f"Height crop applied from {before:,} to {scene.splat_count:,} splats.")

    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult:
        scene = self._require_scene()
        request = OptimizationRequest(target=target, max_splats=max_splats)
        profile = get_optimization_profile(request.target)
        cap = request.max_splats if request.max_splats is not None else profile.max_splats
        before = scene.splat_count
        self._push_history("optimize_for_target", {"target": request.target, "max_splats": cap})
        if cap is not None:
            scene.splat_count = min(scene.splat_count, int(cap))
        scene.sh_degree = profile.sh_degree
        scene.file_size_mb = round(scene.splat_count / 6500.0, 2)
        self._bump_scene_generation()
        estimated_vram = round(scene.splat_count * (32 + scene.sh_degree * 12) / 1_000_000, 2)
        return OptimizationResult(
            target=request.target,
            before_splats=before,
            after_splats=scene.splat_count,
            sh_degree=scene.sh_degree,
            estimated_vram_mb=estimated_vram,
            applied_rules=list(profile.rules),
            message=f"Scene optimized for {request.target}.",
        )

    def export_scene(self, output_path: str, fmt: str, target: str | None = None) -> ExportResult:
        self._require_scene()
        request = ExportRequest(output_path=output_path, fmt=fmt, target=target)
        self._push_history(
            "export_scene",
            {"output_path": request.output_path, "format": request.fmt, "target": request.target},
        )
        return ExportResult(
            output_path=request.output_path,
            format=request.fmt,
            message=f"Export simulated to {request.output_path}",
        )

    def measure_distance(self, a: Vec3, b: Vec3, unit: str = "m") -> MeasurementResult:
        self._require_scene()
        normalized_unit = normalize_measurement_unit(unit)
        value = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
        self._push_history("measure_distance", {"a": a.model_dump(), "b": b.model_dump(), "unit": normalized_unit})
        return MeasurementResult(
            kind="distance",
            value=round(value, 4),
            unit=normalized_unit,
            message=f"Distance: {value:.4f} {normalized_unit}",
        )

    def undo(self) -> ToolResult:
        if not self._snapshots:
            return ToolResult(ok=False, message="Nothing to undo.")
        self._scene = self._snapshots.pop()
        self._history.append(HistoryEntry(index=len(self._history), action="undo", details={}))
        return ToolResult(message="Undo applied.")

    def list_history(self) -> list[HistoryEntry]:
        return list(self._history)
