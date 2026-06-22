from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lichtfeld_mcp.core.scene_analysis import (
    AnalysisSeverity,
    CleanupCandidateSummary,
    SceneAnalysisReport,
)

if TYPE_CHECKING:
    from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud


@dataclass(frozen=True, slots=True)
class CleanupParameters:
    voxel_size: float
    min_voxel_cluster_size: int
    cluster_distance_threshold: float
    outlier_distance: float
    cleanup_aggressiveness: float

    def to_dict(self) -> dict[str, object]:
        return {
            "voxel_size": round(self.voxel_size, 6),
            "min_voxel_cluster_size": self.min_voxel_cluster_size,
            "cluster_distance_threshold": round(self.cluster_distance_threshold, 6),
            "outlier_distance": round(self.outlier_distance, 6),
            "cleanup_aggressiveness": round(self.cleanup_aggressiveness, 6),
        }


@dataclass(frozen=True, slots=True)
class SceneProfile:
    scene_name: str
    project_path: str
    total_splats: int
    analyzed_splats: int
    quality_score: int
    profile_label: str
    approximate: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_name": self.scene_name,
            "project_path": self.project_path,
            "total_splats": self.total_splats,
            "analyzed_splats": self.analyzed_splats,
            "quality_score": self.quality_score,
            "profile_label": self.profile_label,
            "approximate": self.approximate,
        }


@dataclass(frozen=True, slots=True)
class CleanupWorkspace:
    scene_analysis_report: SceneAnalysisReport
    cleanup_candidate_summary: CleanupCandidateSummary
    scene_profile: SceneProfile
    current_cleanup_parameters: CleanupParameters
    sampled_rows: tuple[tuple[float, float, float], ...]
    sampled_indices: tuple[int, ...]
    candidate_selection_mask: tuple[bool, ...]
    preview_selected_indices: tuple[int, ...]
    preview_selection_active: bool
    native_selection_handle: str | None
    selected_count: int
    selection_percentage: float
    selection_mode: str
    selection_source: str
    approximate: bool
    analysis_reused: bool
    candidate_update_time: float
    workspace_update_time: float
    selection_update_time: float
    total_workspace_update_time: float
    estimated_sample_reuse: float
    native_selection_mask: object | None = None
    native_selection_mask_size: int | None = None
    scene_generation: object | None = None
    workspace_state: str = "active"

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_analysis_report": self.scene_analysis_report.to_dict(),
            "cleanup_candidate_summary": self.cleanup_candidate_summary.to_dict(),
            "scene_profile": self.scene_profile.to_dict(),
            "current_cleanup_parameters": self.current_cleanup_parameters.to_dict(),
            "scene_health": self.scene_profile.profile_label,
            "quality_score": self.scene_profile.quality_score,
            "sample_metadata": {
                "analyzed_splats": len(self.sampled_rows),
                "sampled_index_count": len(self.sampled_indices),
                "approximate": self.approximate,
            },
            "full_scene_metadata": {
                "total_splats": self.scene_profile.total_splats,
                "project_path": self.scene_profile.project_path,
                "scene_generation": self.scene_generation,
            },
            "workspace_state": self.workspace_state,
            "preview_selection_active": self.preview_selection_active,
            "native_selection_handle": self.native_selection_handle,
            "native_selection_mask_available": self.native_selection_mask is not None,
            "native_selection_mask_size": self.native_selection_mask_size,
            "selected_count": self.selected_count,
            "preview_selected_splats": self.selected_count,
            "selection_percentage": round(self.selection_percentage, 6),
            "selection_mode": self.selection_mode,
            "selection_source": self.selection_source,
            "estimated_affected_splats_total": (
                self.cleanup_candidate_summary.estimated_affected_splats_total
            ),
            "estimated_cleanup_percentage": round(
                self.cleanup_candidate_summary.estimated_percentage_of_total,
                6,
            ),
            "approximate": self.approximate,
            "analysis_reused": self.analysis_reused,
            "candidate_update_time": round(self.candidate_update_time, 6),
            "workspace_update_time": round(self.workspace_update_time, 6),
            "selection_update_time": round(self.selection_update_time, 6),
            "total_workspace_update_time": round(self.total_workspace_update_time, 6),
            "estimated_sample_reuse": round(self.estimated_sample_reuse, 6),
        }


@dataclass(slots=True)
class CleanupSession:
    workspace: CleanupWorkspace
    sampled_gaussian_cloud: "GaussianCloud"


_CLEANUP_NEEDS_REVIEW_THRESHOLD = 0.05


def determine_scene_health(report: SceneAnalysisReport) -> str:
    estimated_cleanup_ratio = float(report.scene_stats.get("estimated_percentage_of_total", 0.0))
    estimated_cleanup_count = int(report.scene_stats.get("estimated_affected_splats_total", 0))
    has_cleanup_signal = estimated_cleanup_count > 0 or estimated_cleanup_ratio > 0.0
    has_warning_results = any(
        result.severity is AnalysisSeverity.WARNING for result in report.results
    )
    has_critical_results = any(
        result.severity is AnalysisSeverity.CRITICAL for result in report.results
    )

    if has_critical_results:
        return "critical"
    if estimated_cleanup_ratio >= _CLEANUP_NEEDS_REVIEW_THRESHOLD:
        return "needs_cleanup"
    if report.warnings or has_warning_results or has_cleanup_signal:
        return "needs_review"
    return "healthy"


def build_scene_profile(report: SceneAnalysisReport) -> SceneProfile:
    scene_stats = report.scene_stats
    quality_score = int(report.quality_score)
    profile_label = determine_scene_health(report)
    return SceneProfile(
        scene_name=str(scene_stats.get("scene_name", "unknown_scene")),
        project_path=str(scene_stats.get("project_path", "")),
        total_splats=int(scene_stats.get("total_splats", 0)),
        analyzed_splats=int(scene_stats.get("analyzed_splats", 0)),
        quality_score=quality_score,
        profile_label=profile_label,
        approximate=bool(scene_stats.get("approximate", False)),
    )


def format_cleanup_workspace(workspace: CleanupWorkspace) -> str:
    summary = workspace.cleanup_candidate_summary
    params = workspace.current_cleanup_parameters
    mode_label = "Approximate sampled" if workspace.approximate else "Exact"
    scene_health = workspace.scene_profile.profile_label.replace("_", " ").title()
    cleanup_percentage = summary.estimated_percentage_of_total
    lines = [
        "Cleanup Workspace",
        f"Workspace State: {workspace.workspace_state.replace('_', ' ').title()}",
        "Scene Health:",
        scene_health,
        f"Quality score: {workspace.scene_profile.quality_score}",
        f"Analysis Mode: {mode_label}",
        "Workspace Active: Yes",
        (
            "Current Parameters: "
            f"voxel_size={params.voxel_size:.2f}, "
            f"min_cluster_size={params.min_voxel_cluster_size}, "
            f"cluster_distance={params.cluster_distance_threshold:.2f}, "
            f"outlier_distance={params.outlier_distance:.2f}, "
            f"cleanup_aggressiveness={params.cleanup_aggressiveness:.2f}"
        ),
        f"Estimated affected splats total: {summary.estimated_affected_splats_total:,}",
        f"Estimated cleanup percentage: {cleanup_percentage * 100.0:.2f}%",
        f"Preview selected splats: {workspace.selected_count:,}",
        f"Selection source: {workspace.selection_source}",
        f"Analysis reused: {'Yes' if workspace.analysis_reused else 'No'}",
        f"Update time: {workspace.total_workspace_update_time:.6f}s",
    ]
    if workspace.preview_selection_active and workspace.native_selection_mask is None:
        lines.append("Native workspace delete mask unavailable. Soft delete will refuse until it exists.")
    if not workspace.preview_selection_active:
        lines.append("Preview selection: inactive. Run Update Preview to rebuild it.")
    if workspace.approximate:
        lines.append("Approximate sampled selection preview.")
    return "\n".join(lines)
