from dataclasses import replace

import pytest

from lichtfeld_mcp.core.cleanup_workspace import (
    CleanupParameters,
    CleanupPresetComparisonEntry,
    CleanupPresetComparisonReport,
    CleanupWorkspace,
    build_cleanup_category_previews,
    build_scene_profile,
    format_cleanup_category_preview,
    format_cleanup_preset_comparison,
    format_cleanup_workspace,
)
from lichtfeld_mcp.core.cleanup_metrics import (
    CLEANUP_CATEGORY_DISCONNECTED,
    CLEANUP_CATEGORY_FLOATING,
    CLEANUP_CATEGORY_OUTLIER,
    CLEANUP_CATEGORY_SPARSE,
    CleanupSourceBreakdownEntry,
)
from lichtfeld_mcp.core.scene_analysis import (
    AnalysisResult,
    AnalysisSeverity,
    CleanupCandidateSummary,
    SceneAnalysisContext,
    SceneAnalysisReport,
    build_default_scene_analysis_engine,
)


def _report(
    *,
    severity: AnalysisSeverity = AnalysisSeverity.INFO,
    warnings: list[str] | None = None,
    estimated_affected_splats_total: int = 0,
    estimated_percentage_of_total: float = 0.0,
    quality_score: int = 100,
) -> SceneAnalysisReport:
    warning_messages = list(warnings or [])
    recommendations = ["No cleanup required."]
    if estimated_affected_splats_total > 0:
        recommendations = ["Preview floating islands."]
    return SceneAnalysisReport(
        scene_stats={
            "scene_name": "demo_scene",
            "project_path": "C:/data/demo_scene.lf",
            "total_splats": 1_000,
            "analyzed_splats": 250,
            "selected_splats": 0,
            "deleted_splats": 0,
            "voxel_size": 0.25,
            "min_voxel_cluster_size": 10,
            "approximate": True,
            "sampling_stride": 4,
            "used_native_sampling": True,
            "max_splats": 250,
            "aborted": False,
            "affected_splats_in_sample": 12 if estimated_affected_splats_total > 0 else 0,
            "estimated_affected_splats_total": estimated_affected_splats_total,
            "affected_percentage_of_sample": 0.048 if estimated_affected_splats_total > 0 else 0.0,
            "estimated_percentage_of_total": estimated_percentage_of_total,
        },
        quality_score=quality_score,
        warnings=warning_messages,
        recommendations=recommendations,
        analysis_time=0.1,
        results=[
            AnalysisResult(
                name="statistics",
                severity=AnalysisSeverity.INFO,
                summary="Scene statistics captured.",
                details={"total_splats": 1_000, "deleted_splats": 0, "selected_splats": 0},
            ),
            AnalysisResult(
                name="voxel_connectivity",
                severity=severity,
                summary="Scene appears fully connected.",
                details={
                    "floating_voxel_groups": 1 if severity is not AnalysisSeverity.INFO else 0,
                    "estimated_floating_splats": estimated_affected_splats_total,
                    "small_voxel_clusters": 0,
                    "estimated_small_cluster_splats": 0,
                },
                warnings=warning_messages,
                recommendations=recommendations,
            ),
        ],
    )


def _workspace(report: SceneAnalysisReport) -> CleanupWorkspace:
    summary = CleanupCandidateSummary(
        scene_name="demo_scene",
        project_path="C:/data/demo_scene.lf",
        total_splats=1_000,
        analyzed_splats=250,
        quality_score=report.quality_score,
        analysis_time=report.analysis_time,
        approximate=True,
        report_only=True,
        candidate_group_count=1,
        affected_splats_in_sample=12,
        estimated_affected_splats_total=48,
        affected_percentage_of_sample=0.048,
        estimated_percentage_of_total=0.048,
        estimated_affected_splats=48,
        floating_voxel_groups=1,
        estimated_floating_splats=48,
        small_voxel_clusters=0,
        estimated_small_cluster_splats=0,
        sparse_regions=1,
        estimated_sparse_splats=12,
        warnings=list(report.warnings),
        recommendations=list(report.recommendations),
        notes=["Workspace selection preview."],
        selection_sources=("floating voxel clusters", "sparse singleton regions"),
        source_breakdown=(
            CleanupSourceBreakdownEntry(
                source="floating voxel clusters",
                selected_sample_count=8,
                estimated_full_scene_count=32,
            ),
            CleanupSourceBreakdownEntry(
                source="disconnected clusters",
                selected_sample_count=2,
                estimated_full_scene_count=8,
            ),
            CleanupSourceBreakdownEntry(
                source="distant outliers",
                selected_sample_count=0,
                estimated_full_scene_count=0,
            ),
            CleanupSourceBreakdownEntry(
                source="sparse singleton regions",
                selected_sample_count=4,
                estimated_full_scene_count=16,
            ),
        ),
        cleanup_intensity_score=54.25,
        aggressiveness_contribution=50.0,
        estimated_cleanup_contribution=3.0,
        floating_cluster_contribution=0.5,
        disconnected_cluster_contribution=0.25,
        outlier_contribution=0.0,
        sparse_region_contribution=0.5,
    )
    category_previews = build_cleanup_category_previews(
        category_sample_indices={
            CLEANUP_CATEGORY_FLOATING: (0, 1),
            CLEANUP_CATEGORY_SPARSE: (2, 3),
        },
        category_preview_selected_indices={
            CLEANUP_CATEGORY_FLOATING: (0, 4),
            CLEANUP_CATEGORY_SPARSE: (8, 12),
        },
        analyzed_splats=250,
        total_splats=1_000,
        approximate=True,
        category_scores={
            CLEANUP_CATEGORY_FLOATING: 0.5,
            CLEANUP_CATEGORY_SPARSE: 0.5,
        },
        category_reasons={
            CLEANUP_CATEGORY_FLOATING: "Outside the dominant voxel component.",
            CLEANUP_CATEGORY_SPARSE: "Inside sparse singleton voxel regions.",
        },
    )
    return CleanupWorkspace(
        scene_analysis_report=report,
        cleanup_candidate_summary=summary,
        scene_profile=build_scene_profile(report),
        current_cleanup_parameters=CleanupParameters(
            voxel_size=0.25,
            min_voxel_cluster_size=10,
            cluster_distance_threshold=0.10,
            outlier_distance=2.5,
            cleanup_aggressiveness=0.5,
        ),
        sampled_rows=((0.0, 0.0, 0.0),),
        sampled_indices=(0,),
        candidate_selection_mask=(True,),
        preview_selected_indices=(0, 4, 8, 12),
        preview_selection_active=True,
        native_selection_handle="C:/data/demo_scene.lf#cleanup-preview",
        selected_count=4,
        selection_percentage=0.004,
        selection_mode="replace",
        selection_source="floating voxel clusters, sparse singleton regions",
        approximate=True,
        analysis_reused=True,
        candidate_update_time=0.01,
        workspace_update_time=0.02,
        selection_update_time=0.01,
        total_workspace_update_time=0.02,
        estimated_sample_reuse=1.0,
        cleanup_category_previews=category_previews,
        active_cleanup_categories=(CLEANUP_CATEGORY_FLOATING, CLEANUP_CATEGORY_SPARSE),
        selected_cleanup_category=CLEANUP_CATEGORY_FLOATING,
        category_preview_mode="single",
    )


def test_health_label_with_no_warnings_is_healthy():
    report = _report()

    profile = build_scene_profile(report)

    assert profile.profile_label == "healthy"


def test_health_label_with_warnings_is_needs_review():
    report = _report(
        severity=AnalysisSeverity.WARNING,
        warnings=["Scene contains sparse voxel regions."],
        estimated_affected_splats_total=12,
        estimated_percentage_of_total=0.012,
        quality_score=84,
    )

    profile = build_scene_profile(report)

    assert profile.profile_label == "needs_review"


def test_health_label_with_cleanup_candidates_is_needs_cleanup():
    report = _report(
        severity=AnalysisSeverity.WARNING,
        warnings=["Disconnected cleanup clusters detected."],
        estimated_affected_splats_total=120,
        estimated_percentage_of_total=0.12,
        quality_score=72,
    )

    profile = build_scene_profile(report)

    assert profile.profile_label == "needs_cleanup"


def test_cleanup_workspace_format_distinguishes_preview_selection_from_estimate():
    report = _report(
        severity=AnalysisSeverity.WARNING,
        warnings=["Scene contains sparse voxel regions."],
        estimated_affected_splats_total=48,
        estimated_percentage_of_total=0.048,
        quality_score=84,
    )

    formatted = format_cleanup_workspace(_workspace(report))

    assert "Scene Health:\nNeeds Review" in formatted
    assert "Quality score: 84" in formatted
    assert "Preset: Balanced" in formatted
    assert "Cleanup intensity score: 54.25" in formatted
    assert "Preview selected splats: 4" in formatted
    assert "Estimated affected splats total: 48" in formatted
    assert "Estimated cleanup percentage: 4.80%" in formatted
    assert "Affected splats in sample: 12" in formatted
    assert "Selection source breakdown:" in formatted
    assert "Selection count:" not in formatted
    assert "Estimated affected splats:" not in formatted
    assert "Current Scene Type:" not in formatted


@pytest.mark.parametrize(
    ("preset_name", "voxel_size", "min_voxel_cluster_size", "outlier_distance", "aggressiveness"),
    [
        ("Conservative", 0.15, 5, 3.5, 0.25),
        ("Balanced", 0.25, 10, 2.5, 0.50),
        ("Aggressive", 0.40, 20, 1.5, 0.75),
    ],
)
def test_cleanup_presets_serialize_correctly(
    preset_name: str,
    voxel_size: float,
    min_voxel_cluster_size: int,
    outlier_distance: float,
    aggressiveness: float,
):
    params = CleanupParameters(
        voxel_size=voxel_size,
        min_voxel_cluster_size=min_voxel_cluster_size,
        cluster_distance_threshold=0.10,
        outlier_distance=outlier_distance,
        cleanup_aggressiveness=aggressiveness,
        preset_name=preset_name,
    )

    assert params.to_dict() == {
        "preset": preset_name,
        "voxel_size": voxel_size,
        "min_voxel_cluster_size": min_voxel_cluster_size,
        "cluster_distance_threshold": 0.1,
        "outlier_distance": outlier_distance,
        "cleanup_aggressiveness": aggressiveness,
    }


def test_cleanup_workspace_dict_includes_preset():
    workspace = _workspace(_report())

    serialized = workspace.to_dict()

    assert serialized["cleanup_preset"] == "Balanced"
    assert serialized["current_cleanup_parameters"]["preset"] == "Balanced"
    assert serialized["cleanup_intensity_score"] == 54.25
    assert serialized["selection_sources"] == [
        "floating voxel clusters",
        "sparse singleton regions",
    ]
    assert serialized["source_breakdown"][0]["source"] == "floating voxel clusters"
    assert serialized["active_visible_categories"] == [
        CLEANUP_CATEGORY_FLOATING,
        CLEANUP_CATEGORY_SPARSE,
    ]
    assert serialized["selected_category"] == CLEANUP_CATEGORY_FLOATING
    assert serialized["category_preview_counts"][CLEANUP_CATEGORY_FLOATING][
        "preview_selected_splats"
    ] == 2


def test_cleanup_preset_comparison_format_highlights_non_destructive_intensity():
    report = CleanupPresetComparisonReport(
        scene_name="demo_scene",
        project_path="C:/data/demo_scene.lf",
        approximate=True,
        analysis_reused=True,
        entries=(
            CleanupPresetComparisonEntry(
                preset_name="Conservative",
                cleanup_candidate_summary=_workspace(_report()).cleanup_candidate_summary,
                selection_sources=("floating voxel clusters",),
            ),
        ),
    )

    formatted = format_cleanup_preset_comparison(report)

    assert "Preset Comparison" in formatted
    assert "Non-destructive comparison" in formatted
    assert "Cleanup intensity score: 54.25" in formatted


def test_cleanup_category_preview_format_highlights_non_destructive_limitations():
    formatted = format_cleanup_category_preview(_workspace(_report()))

    assert "Cleanup Category Preview" in formatted
    assert "Category: floating voxel clusters" in formatted
    assert "Preview selected splats: 2" in formatted
    assert "Estimated full-scene splats: 8" in formatted
    assert "- floating voxel clusters: preview=2, estimated=8" in formatted
    assert "- sparse singleton regions" not in formatted
    assert "Current limitation: native category isolation only" in formatted


@pytest.mark.parametrize(
    ("category", "expected_label", "expected_preview", "expected_estimated"),
    [
        (CLEANUP_CATEGORY_FLOATING, "floating voxel clusters", 2, 8),
        (CLEANUP_CATEGORY_DISCONNECTED, "disconnected clusters", 0, 0),
        (CLEANUP_CATEGORY_OUTLIER, "distant outliers", 0, 0),
        (CLEANUP_CATEGORY_SPARSE, "sparse singleton regions", 2, 8),
    ],
)
def test_cleanup_category_preview_header_metrics_match_selected_category(
    category: str,
    expected_label: str,
    expected_preview: int,
    expected_estimated: int,
):
    workspace = replace(
        _workspace(_report()),
        selected_cleanup_category=category,
        category_preview_mode="single",
    )

    formatted = format_cleanup_category_preview(workspace)

    assert f"Category: {expected_label}" in formatted
    assert f"Preview selected splats: {expected_preview}" in formatted
    assert f"Estimated full-scene splats: {expected_estimated}" in formatted


def test_cleanup_category_preview_all_active_uses_combined_label_and_count():
    workspace = replace(
        _workspace(_report()),
        selected_cleanup_category=None,
        category_preview_mode="active",
    )

    formatted = format_cleanup_category_preview(workspace)

    assert "Category: All active categories" in formatted
    assert "Preview selected splats: 4" in formatted
    assert "Estimated full-scene splats: 16" in formatted
    assert "- floating voxel clusters: preview=2, estimated=8" in formatted
    assert "- sparse singleton regions: preview=2, estimated=8" in formatted


def test_quality_score_decreases_when_warnings_exist():
    engine = build_default_scene_analysis_engine()
    healthy_report = engine.analyze(
        SceneAnalysisContext(
            scene_name="healthy_scene",
            project_path="C:/data/healthy_scene.lf",
            positions=[
                (0.0, 0.0, 0.0),
                (0.1, 0.0, 0.0),
                (0.2, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (1.1, 0.0, 0.0),
                (1.2, 0.0, 0.0),
            ],
            total_splats=6,
            analyzed_splats=6,
            selected_splats=0,
            deleted_splats=0,
            voxel_size=1.0,
            min_voxel_cluster_size=2,
            approximate=False,
            sampling_stride=1,
            used_native_sampling=False,
            max_splats=25_000,
        )
    )
    warning_report = engine.analyze(
        SceneAnalysisContext(
            scene_name="warning_scene",
            project_path="C:/data/warning_scene.lf",
            positions=[
                (0.0, 0.0, 0.0),
                (0.1, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (1.1, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (3.0, 0.0, 0.0),
            ],
            total_splats=6,
            analyzed_splats=6,
            selected_splats=0,
            deleted_splats=0,
            voxel_size=1.0,
            min_voxel_cluster_size=2,
            approximate=False,
            sampling_stride=1,
            used_native_sampling=False,
            max_splats=25_000,
        )
    )

    assert healthy_report.quality_score > warning_report.quality_score
    assert warning_report.quality_score <= 84
