from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

from lichtfeld_mcp.core.cleanup_metrics import (
    CleanupSourceBreakdownEntry,
    cleanup_category_label,
    cleanup_category_order,
    extrapolate_cleanup_count,
    normalize_cleanup_categories,
)
from lichtfeld_mcp.core.scene_analysis import (
    AnalysisSeverity,
    CleanupCandidateSummary,
    SceneAnalysisReport,
)

if TYPE_CHECKING:
    from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud


@dataclass(frozen=True, slots=True)
class CleanupCategoryPreview:
    category: str
    label: str
    sample_indices: tuple[int, ...]
    preview_selected_indices: tuple[int, ...]
    estimated_full_scene_count: int
    estimated_full_scene_count_contribution: int | None = None
    score: float | None = None
    reason: str | None = None

    @property
    def selected_sample_count(self) -> int:
        return len(self.sample_indices)

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "label": self.label,
            "selected_sample_count": self.selected_sample_count,
            "preview_selected_splats": len(self.preview_selected_indices),
            "estimated_full_scene_count": self.estimated_full_scene_count,
            "estimated_full_scene_count_contribution": (
                self.estimated_full_scene_count_contribution
            ),
            "sample_indices": list(self.sample_indices),
            "preview_selected_indices": list(self.preview_selected_indices),
            "score": None if self.score is None else round(self.score, 6),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CleanupParameters:
    voxel_size: float
    min_voxel_cluster_size: int
    cluster_distance_threshold: float
    outlier_distance: float
    cleanup_aggressiveness: float
    preset_name: str = "Balanced"

    def to_dict(self) -> dict[str, object]:
        return {
            "preset": self.preset_name,
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
    cleanup_category_previews: tuple[CleanupCategoryPreview, ...] = ()
    active_cleanup_categories: tuple[str, ...] = ()
    selected_cleanup_category: str | None = None
    category_preview_mode: str = "workspace"
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
            "cleanup_preset": self.current_cleanup_parameters.preset_name,
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
            "cleanup_categories": [entry.to_dict() for entry in self.cleanup_category_previews],
            "all_categories": list(cleanup_category_order()),
            "active_visible_categories": list(self.active_cleanup_categories),
            "selected_category": self.selected_cleanup_category,
            "category_preview_mode": self.category_preview_mode,
            "category_preview_counts": {
                entry.category: {
                    "preview_selected_splats": len(entry.preview_selected_indices),
                    "estimated_full_scene_splats": entry.estimated_full_scene_count,
                }
                for entry in self.cleanup_category_previews
            },
            "category_source_breakdown": [
                entry.to_dict() for entry in self.cleanup_category_previews
            ],
            "estimated_affected_splats_total": (
                self.cleanup_candidate_summary.estimated_affected_splats_total
            ),
            "affected_splats_in_sample": self.cleanup_candidate_summary.affected_splats_in_sample,
            "affected_percentage_of_sample": round(
                self.cleanup_candidate_summary.affected_percentage_of_sample,
                6,
            ),
            "estimated_cleanup_percentage": round(
                self.cleanup_candidate_summary.estimated_percentage_of_total,
                6,
            ),
            "cleanup_intensity_score": round(
                self.cleanup_candidate_summary.cleanup_intensity_score,
                6,
            ),
            "selection_sources": list(self.cleanup_candidate_summary.selection_sources),
            "source_breakdown": [
                entry.to_dict() for entry in self.cleanup_candidate_summary.source_breakdown
            ],
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


@dataclass(frozen=True, slots=True)
class CleanupPresetComparisonEntry:
    preset_name: str
    cleanup_candidate_summary: CleanupCandidateSummary
    selection_sources: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "preset_name": self.preset_name,
            "cleanup_intensity_score": round(
                self.cleanup_candidate_summary.cleanup_intensity_score,
                6,
            ),
            "estimated_affected_splats_total": (
                self.cleanup_candidate_summary.estimated_affected_splats_total
            ),
            "estimated_cleanup_percentage": round(
                self.cleanup_candidate_summary.estimated_percentage_of_total,
                6,
            ),
            "preview_selected_splats": self.cleanup_candidate_summary.affected_splats_in_sample,
            "affected_splats_in_sample": self.cleanup_candidate_summary.affected_splats_in_sample,
            "affected_percentage_of_sample": round(
                self.cleanup_candidate_summary.affected_percentage_of_sample,
                6,
            ),
            "selection_sources": list(self.selection_sources),
            "source_breakdown": [
                entry.to_dict()
                for entry in self.cleanup_candidate_summary.source_breakdown
            ],
            "intensity_factors": {
                "aggressiveness": round(
                    self.cleanup_candidate_summary.aggressiveness_contribution,
                    6,
                ),
                "estimated_cleanup": round(
                    self.cleanup_candidate_summary.estimated_cleanup_contribution,
                    6,
                ),
                "floating_clusters": round(
                    self.cleanup_candidate_summary.floating_cluster_contribution,
                    6,
                ),
                "disconnected_clusters": round(
                    self.cleanup_candidate_summary.disconnected_cluster_contribution,
                    6,
                ),
                "distant_outliers": round(
                    self.cleanup_candidate_summary.outlier_contribution,
                    6,
                ),
                "sparse_regions": round(
                    self.cleanup_candidate_summary.sparse_region_contribution,
                    6,
                ),
            },
        }


@dataclass(frozen=True, slots=True)
class CleanupPresetComparisonReport:
    scene_name: str
    project_path: str
    approximate: bool
    analysis_reused: bool
    entries: tuple[CleanupPresetComparisonEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_name": self.scene_name,
            "project_path": self.project_path,
            "approximate": self.approximate,
            "analysis_reused": self.analysis_reused,
            "entries": [entry.to_dict() for entry in self.entries],
        }


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
        f"Preset: {params.preset_name}",
        (
            "Current Parameters: "
            f"voxel_size={params.voxel_size:.2f}, "
            f"min_cluster_size={params.min_voxel_cluster_size}, "
            f"cluster_distance={params.cluster_distance_threshold:.2f}, "
            f"outlier_distance={params.outlier_distance:.2f}, "
            f"cleanup_aggressiveness={params.cleanup_aggressiveness:.2f}"
        ),
        f"Cleanup intensity score: {summary.cleanup_intensity_score:.2f}",
        f"Estimated affected splats total: {summary.estimated_affected_splats_total:,}",
        f"Estimated cleanup percentage: {cleanup_percentage * 100.0:.2f}%",
        f"Preview selected splats: {workspace.selected_count:,}",
        f"Affected splats in sample: {summary.affected_splats_in_sample:,}",
        "Affected percentage of sample: "
        f"{summary.affected_percentage_of_sample * 100.0:.2f}%",
        f"Selection source: {workspace.selection_source}",
        f"Analysis reused: {'Yes' if workspace.analysis_reused else 'No'}",
        f"Update time: {workspace.total_workspace_update_time:.6f}s",
    ]
    preview_label = describe_cleanup_category_preview(workspace)
    if preview_label is not None:
        lines.append(f"Category Preview: {preview_label}")
        lines.append(
            "Active categories: "
            f"{', '.join(cleanup_category_label(category) for category in workspace.active_cleanup_categories)}"
        )
        lines.append("Non-destructive preview: native selection only")
        lines.append("Current limitation: category preview uses native selection, not color overlays.")
    _append_category_preview_lines(lines, current_cleanup_category_previews(workspace))
    _append_source_breakdown_lines(lines, summary.source_breakdown)
    if workspace.preview_selection_active and workspace.native_selection_mask is None:
        lines.append("Native workspace delete mask unavailable. Soft delete will refuse until it exists.")
    if not workspace.preview_selection_active:
        lines.append("Preview selection: inactive. Run Update Preview to rebuild it.")
    if workspace.approximate:
        lines.append("Approximate sampled selection preview.")
    return "\n".join(lines)


def format_cleanup_preset_comparison(report: CleanupPresetComparisonReport) -> str:
    mode_label = "Approximate sampled" if report.approximate else "Exact"
    lines = [
        "Preset Comparison",
        "Non-destructive comparison. Scene, soft delete state, and native selection stay unchanged.",
        f"Analysis reused: {'Yes' if report.analysis_reused else 'No'}",
        f"Analysis mode: {mode_label}",
    ]
    for entry in report.entries:
        summary = entry.cleanup_candidate_summary
        lines.append("")
        lines.append(f"{entry.preset_name}:")
        lines.append(f"Cleanup intensity score: {summary.cleanup_intensity_score:.2f}")
        lines.append(
            f"Preview selected splats: {summary.affected_splats_in_sample:,}"
        )
        lines.append(
            "Estimated cleanup percentage: "
            f"{summary.estimated_percentage_of_total * 100.0:.2f}%"
        )
        lines.append(
            "Intensity factors: "
            f"aggressiveness={summary.aggressiveness_contribution:.2f}, "
            f"cleanup={summary.estimated_cleanup_contribution:.2f}, "
            f"floating={summary.floating_cluster_contribution:.2f}, "
            f"disconnected={summary.disconnected_cluster_contribution:.2f}, "
            f"outliers={summary.outlier_contribution:.2f}, "
            f"sparse={summary.sparse_region_contribution:.2f}"
        )
        lines.append(
            f"Selection sources: {', '.join(entry.selection_sources) or 'no cleanup candidates'}"
        )
        _append_source_breakdown_lines(lines, summary.source_breakdown)
    return "\n".join(lines)


def format_cleanup_category_preview(workspace: CleanupWorkspace) -> str:
    mode_label = "Approximate sampled" if workspace.approximate else "Exact"
    category_label = describe_cleanup_category_preview(workspace) or "No active preview"
    preview_selected_splats = preview_selected_splats_for_current_scope(workspace)
    estimated_total = estimate_cleanup_preview_total(workspace)
    lines = [
        "Cleanup Category Preview",
        f"Category: {category_label}",
        f"Preview selected splats: {preview_selected_splats:,}",
        f"Estimated full-scene splats: {estimated_total:,}",
        f"Current preset: {workspace.current_cleanup_parameters.preset_name}",
        f"Analysis mode: {mode_label}",
        "Non-destructive preview: scene splats are unchanged",
        "Current limitation: native category isolation only; multi-color overlays are future work.",
    ]
    if workspace.active_cleanup_categories:
        lines.append(
            "Active categories: "
            f"{', '.join(cleanup_category_label(category) for category in workspace.active_cleanup_categories)}"
        )
    _append_category_preview_lines(lines, current_cleanup_category_previews(workspace))
    return "\n".join(lines)


def _append_source_breakdown_lines(
    lines: list[str],
    source_breakdown: tuple[CleanupSourceBreakdownEntry, ...],
) -> None:
    if not source_breakdown:
        return
    lines.append("Selection source breakdown:")
    for entry in source_breakdown:
        lines.append(
            "- "
            f"{entry.source}: sample={entry.selected_sample_count:,}, "
            f"estimated={entry.estimated_full_scene_count:,}"
        )


def active_cleanup_category_previews(
    workspace: CleanupWorkspace,
) -> tuple[CleanupCategoryPreview, ...]:
    if not workspace.cleanup_category_previews:
        return ()
    if not workspace.active_cleanup_categories:
        return workspace.cleanup_category_previews
    active = set(normalize_cleanup_categories(workspace.active_cleanup_categories))
    return tuple(
        entry for entry in workspace.cleanup_category_previews if entry.category in active
    )


def current_cleanup_category_previews(
    workspace: CleanupWorkspace,
) -> tuple[CleanupCategoryPreview, ...]:
    if workspace.selected_cleanup_category is not None:
        return tuple(
            entry
            for entry in workspace.cleanup_category_previews
            if entry.category == workspace.selected_cleanup_category
        )
    if workspace.category_preview_mode == "active":
        return active_cleanup_category_previews(workspace)
    if workspace.category_preview_mode == "workspace":
        return workspace.cleanup_category_previews
    return ()


def describe_cleanup_category_preview(workspace: CleanupWorkspace) -> str | None:
    if workspace.selected_cleanup_category is not None:
        return cleanup_category_label(workspace.selected_cleanup_category)
    if workspace.category_preview_mode == "active":
        return "All active categories"
    if workspace.category_preview_mode == "workspace":
        return "Workspace Cleanup Preview"
    if workspace.category_preview_mode == "cleared":
        return "Cleared"
    return None


def estimate_cleanup_preview_total(workspace: CleanupWorkspace) -> int:
    return sum(
        entry.estimated_full_scene_count
        for entry in current_cleanup_category_previews(workspace)
    )


def preview_selected_splats_for_current_scope(workspace: CleanupWorkspace) -> int:
    return sum(
        len(entry.preview_selected_indices)
        for entry in current_cleanup_category_previews(workspace)
    )


def _append_category_preview_lines(
    lines: list[str],
    category_previews: tuple[CleanupCategoryPreview, ...],
) -> None:
    if not category_previews:
        return
    lines.append("Cleanup category breakdown:")
    for entry in category_previews:
        lines.append(
            "- "
            f"{entry.label}: preview={len(entry.preview_selected_indices):,}, "
            f"estimated={entry.estimated_full_scene_count:,}"
        )


def build_cleanup_category_previews(
    *,
    category_sample_indices: Mapping[str, tuple[int, ...] | list[int]],
    category_preview_selected_indices: Mapping[str, tuple[int, ...] | list[int]],
    analyzed_splats: int,
    total_splats: int,
    approximate: bool,
    category_scores: Mapping[str, float] | None = None,
    category_reasons: Mapping[str, str] | None = None,
) -> tuple[CleanupCategoryPreview, ...]:
    previews: list[CleanupCategoryPreview] = []
    score_map = category_scores or {}
    reason_map = category_reasons or {}
    for category in cleanup_category_order():
        sample_indices = tuple(int(index) for index in category_sample_indices.get(category, ()))
        preview_selected_indices = tuple(
            int(index)
            for index in category_preview_selected_indices.get(category, ())
        )
        estimated_full_scene_count = extrapolate_cleanup_count(
            len(preview_selected_indices),
            analyzed_splats=analyzed_splats,
            total_splats=total_splats,
            approximate=approximate,
        )
        previews.append(
            CleanupCategoryPreview(
                category=category,
                label=cleanup_category_label(category),
                sample_indices=sample_indices,
                preview_selected_indices=preview_selected_indices,
                estimated_full_scene_count=estimated_full_scene_count,
                estimated_full_scene_count_contribution=estimated_full_scene_count,
                score=score_map.get(category),
                reason=reason_map.get(category),
            )
        )
    return tuple(previews)
