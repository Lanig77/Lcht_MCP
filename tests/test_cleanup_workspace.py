import pytest

from lichtfeld_mcp.core.cleanup_workspace import (
    CleanupParameters,
    CleanupWorkspace,
    build_scene_profile,
    format_cleanup_workspace,
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
    assert "Preview selected splats: 4" in formatted
    assert "Estimated affected splats total: 48" in formatted
    assert "Estimated cleanup percentage: 4.80%" in formatted
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
