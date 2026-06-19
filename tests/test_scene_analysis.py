from lichtfeld_mcp.core.scene_analysis import (
    AnalysisSeverity,
    SceneAnalysisContext,
    build_cleanup_candidate_summary,
    build_default_scene_analysis_engine,
    format_cleanup_candidate_summary,
    format_scene_analysis_report,
)


def test_scene_analysis_engine_builds_unified_report():
    engine = build_default_scene_analysis_engine()
    context = SceneAnalysisContext(
        scene_name="demo_scene",
        project_path="C:/data/demo_scene.lf",
        positions=[
            (0.0, 0.0, 0.0),
            (0.1, 0.0, 0.0),
            (0.2, 0.0, 0.0),
            (0.3, 0.0, 0.0),
            (5.0, 5.0, 5.0),
            (5.1, 5.0, 5.0),
            (25.0, 25.0, 25.0),
        ],
        total_splats=1_000,
        analyzed_splats=7,
        selected_splats=0,
        deleted_splats=0,
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        approximate=True,
        sampling_stride=10,
        used_native_sampling=True,
        max_splats=25_000,
    )

    report = engine.analyze(context)

    assert report.scene_stats["scene_name"] == "demo_scene"
    assert report.quality_score < 100
    assert len(report.results) == 4

    connectivity = next(result for result in report.results if result.name == "voxel_connectivity")
    assert connectivity.severity is AnalysisSeverity.CRITICAL
    assert connectivity.details["floating_voxel_groups"] == 2
    assert connectivity.details["estimated_floating_splats"] == 3
    assert "Preview floating islands." in report.recommendations


def test_format_scene_analysis_report_renders_readable_summary():
    engine = build_default_scene_analysis_engine()
    context = SceneAnalysisContext(
        scene_name="healthy_scene",
        project_path="C:/data/healthy_scene.lf",
        positions=[
            (0.0, 0.0, 0.0),
            (0.1, 0.0, 0.0),
            (0.2, 0.1, 0.0),
            (0.3, 0.1, 0.0),
        ],
        total_splats=4,
        analyzed_splats=4,
        selected_splats=0,
        deleted_splats=0,
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        approximate=False,
        sampling_stride=1,
        used_native_sampling=False,
        max_splats=25_000,
    )

    report = engine.analyze(context)
    formatted = format_scene_analysis_report(report)

    assert "Scene Analysis" in formatted
    assert "Quality score:" in formatted
    assert "Bounding box: OK" in formatted
    assert "Recommendations" in formatted


def test_cleanup_candidate_summary_is_generated_from_scene_analysis_report():
    engine = build_default_scene_analysis_engine()
    context = SceneAnalysisContext(
        scene_name="cleanup_scene",
        project_path="C:/data/cleanup_scene.lf",
        positions=[
            (0.0, 0.0, 0.0),
            (0.1, 0.0, 0.0),
            (0.2, 0.0, 0.0),
            (5.0, 5.0, 5.0),
            (5.1, 5.0, 5.0),
            (25.0, 25.0, 25.0),
        ],
        total_splats=1_000,
        analyzed_splats=6,
        selected_splats=0,
        deleted_splats=0,
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        approximate=True,
        sampling_stride=20,
        used_native_sampling=True,
        max_splats=25_000,
    )

    report = engine.analyze(context)
    summary = build_cleanup_candidate_summary(report)
    formatted = format_cleanup_candidate_summary(summary)

    assert summary.report_only is True
    assert summary.approximate is True
    assert summary.candidate_group_count >= 1
    assert summary.estimated_affected_splats >= 1
    assert summary.analyzed_splats == 6
    assert "Cleanup Candidate Preview" in formatted
    assert "Analyzed splats: 6" in formatted
    assert "Affected splats in analyzed sample:" in formatted
    assert "Estimated affected splats total:" in formatted
    assert "Affected percentage of sample:" in formatted
    assert "Estimated percentage of total:" in formatted
    assert "Selection preview: report only" in formatted


def test_cleanup_candidate_percentages_are_coherent_for_approximate_reports():
    engine = build_default_scene_analysis_engine()
    context = SceneAnalysisContext(
        scene_name="approx_scene",
        project_path="C:/data/approx_scene.lf",
        positions=[
            (0.0, 0.0, 0.0),
            (0.1, 0.0, 0.0),
            (0.2, 0.0, 0.0),
            (5.0, 5.0, 5.0),
            (10.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
        ],
        total_splats=600,
        analyzed_splats=6,
        selected_splats=0,
        deleted_splats=0,
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        approximate=True,
        sampling_stride=100,
        used_native_sampling=True,
        max_splats=25_000,
    )

    report = engine.analyze(context)
    summary = build_cleanup_candidate_summary(report)

    assert summary.affected_splats_in_sample == 3
    assert summary.estimated_affected_splats_total == 300
    assert summary.affected_percentage_of_sample == 0.5
    assert summary.estimated_percentage_of_total == 0.5
    assert "Estimated cleanup in analyzed sample: 50.0%" in summary.recommendations
    assert "Estimated cleanup extrapolated to full scene: 50.0%" in summary.recommendations


def test_scene_analysis_report_displays_unambiguous_cleanup_estimates():
    engine = build_default_scene_analysis_engine()
    context = SceneAnalysisContext(
        scene_name="report_scene",
        project_path="C:/data/report_scene.lf",
        positions=[
            (0.0, 0.0, 0.0),
            (0.1, 0.0, 0.0),
            (0.2, 0.0, 0.0),
            (5.0, 5.0, 5.0),
        ],
        total_splats=400,
        analyzed_splats=4,
        selected_splats=0,
        deleted_splats=0,
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        approximate=True,
        sampling_stride=100,
        used_native_sampling=True,
        max_splats=25_000,
    )

    report = engine.analyze(context)
    formatted = format_scene_analysis_report(report)

    assert "Affected splats in analyzed sample:" in formatted
    assert "Estimated affected splats total:" in formatted
    assert "Affected percentage of sample:" in formatted
    assert "Estimated percentage of total:" in formatted
    assert "Estimated cleanup in analyzed sample:" in formatted
