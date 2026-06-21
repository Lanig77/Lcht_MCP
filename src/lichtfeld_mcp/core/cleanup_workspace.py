from __future__ import annotations

from dataclasses import dataclass

from lichtfeld_mcp.core.scene_analysis import CleanupCandidateSummary, SceneAnalysisReport


@dataclass(frozen=True, slots=True)
class CleanupParameters:
    voxel_size: float
    min_voxel_cluster_size: int
    outlier_distance: float
    cleanup_aggressiveness: float

    def to_dict(self) -> dict[str, object]:
        return {
            "voxel_size": round(self.voxel_size, 6),
            "min_voxel_cluster_size": self.min_voxel_cluster_size,
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
    selected_count: int
    selection_percentage: float
    selection_mode: str
    selection_source: str
    approximate: bool
    workspace_update_time: float
    selection_update_time: float
    estimated_sample_reuse: float

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_analysis_report": self.scene_analysis_report.to_dict(),
            "cleanup_candidate_summary": self.cleanup_candidate_summary.to_dict(),
            "scene_profile": self.scene_profile.to_dict(),
            "current_cleanup_parameters": self.current_cleanup_parameters.to_dict(),
            "selected_count": self.selected_count,
            "selection_percentage": round(self.selection_percentage, 6),
            "selection_mode": self.selection_mode,
            "selection_source": self.selection_source,
            "approximate": self.approximate,
            "workspace_update_time": round(self.workspace_update_time, 6),
            "selection_update_time": round(self.selection_update_time, 6),
            "estimated_sample_reuse": round(self.estimated_sample_reuse, 6),
        }


@dataclass(slots=True)
class CleanupSession:
    project_path: str
    scene_analysis_report: SceneAnalysisReport
    sampled_rows: list[tuple[float, float, float]]
    sampled_indices: list[int]
    total_splats: int
    approximate: bool
    workspace: CleanupWorkspace


def build_scene_profile(report: SceneAnalysisReport) -> SceneProfile:
    scene_stats = report.scene_stats
    quality_score = int(report.quality_score)
    if quality_score >= 90:
        profile_label = "healthy"
    elif quality_score >= 75:
        profile_label = "watch"
    else:
        profile_label = "cleanup_recommended"
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
    cleanup_percentage = (
        summary.estimated_percentage_of_total
        if workspace.approximate
        else workspace.selection_percentage
    )
    lines = [
        "Cleanup Workspace",
        f"Scene profile: {workspace.scene_profile.profile_label}",
        f"Mode: {mode_label}",
        (
            "Parameters: "
            f"voxel_size={params.voxel_size:.2f}, "
            f"min_cluster_size={params.min_voxel_cluster_size}, "
            f"outlier_distance={params.outlier_distance:.2f}, "
            f"cleanup_aggressiveness={params.cleanup_aggressiveness:.2f}"
        ),
        f"Estimated affected splats: {summary.estimated_affected_splats_total:,}",
        f"Estimated cleanup percentage: {cleanup_percentage * 100.0:.2f}%",
        f"Selection count: {workspace.selected_count:,}",
        f"Selection source: {workspace.selection_source}",
    ]
    if workspace.approximate:
        lines.append("Approximate sampled selection preview.")
    return "\n".join(lines)

