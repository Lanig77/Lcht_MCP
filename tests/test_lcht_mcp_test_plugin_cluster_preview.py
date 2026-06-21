from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from lichtfeld_mcp.core.scene_analysis import (
    AnalysisResult,
    AnalysisSeverity,
    CleanupCandidateSummary,
    SceneAnalysisReport,
)
from lichtfeld_mcp.core.cleanup_workspace import (
    CleanupParameters,
    CleanupWorkspace,
    SceneProfile,
)
from lichtfeld_mcp.schemas.common import CleanupSelectionPreviewResult
from test_lcht_mcp_test_plugin_undo import _load_runner_modules


class FakeClusterPreviewAdapter:
    def __init__(self):
        self.analysis_calls = 0
        self.last_kwargs = None
        self.voxel_analysis_calls = 0
        self.last_voxel_kwargs = None
        self.cleanup_selection_preview_calls = 0
        self.open_cleanup_workspace_calls = 0
        self.update_cleanup_workspace_calls = 0
        self.reset_cleanup_workspace_calls = 0

    def analyze_clusters_preview(
        self,
        *,
        distance_threshold: float,
        min_cluster_size: int,
        max_cluster_analysis_splats: int,
        abort_if_splat_count_above_limit: bool,
    ):
        self.analysis_calls += 1
        self.last_kwargs = {
            "distance_threshold": distance_threshold,
            "min_cluster_size": min_cluster_size,
            "max_cluster_analysis_splats": max_cluster_analysis_splats,
            "abort_if_splat_count_above_limit": abort_if_splat_count_above_limit,
        }
        return SimpleNamespace(
            total_splats=1000,
            analyzed_splats=1000,
            total_clusters=4,
            largest_cluster_size=900,
            small_cluster_count=3,
            candidate_floating_cluster_count=2,
            candidate_floating_splat_count=40,
            distance_threshold=distance_threshold,
            min_cluster_size=min_cluster_size,
            approximate=False,
            refused=False,
            sampling_stride=1,
            message="Cluster analysis preview complete.",
            used_native_sampling=True,
            stats_elapsed_seconds=0.1,
            read_means_elapsed_seconds=0.2,
            sampling_elapsed_seconds=0.3,
            cloud_build_elapsed_seconds=0.4,
            clustering_elapsed_seconds=0.5,
        )

    def analyze_voxel_clusters_preview(
        self,
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
        max_splats: int,
        abort_if_above_limit: bool,
    ):
        self.voxel_analysis_calls += 1
        self.last_voxel_kwargs = {
            "voxel_size": voxel_size,
            "min_voxel_cluster_size": min_voxel_cluster_size,
            "max_splats": max_splats,
            "abort_if_above_limit": abort_if_above_limit,
        }
        return SimpleNamespace(
            total_splats=1000,
            analyzed_splats=500,
            occupied_voxels=120,
            total_voxel_clusters=6,
            largest_voxel_cluster_voxel_count=80,
            largest_voxel_cluster_estimated_splats=420,
            small_voxel_cluster_count=4,
            estimated_floating_splats=37,
            approximate=True,
            refused=False,
            sampling_stride=2,
            message="Voxel cluster preview complete in approximate sampled mode.",
            used_native_sampling=True,
            read_means_elapsed_seconds=0.1,
            sampling_elapsed_seconds=0.2,
            voxel_analysis_elapsed_seconds=0.3,
        )

    def analyze_scene(
        self,
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
        max_splats: int,
        abort_if_above_limit: bool,
    ):
        self.scene_analysis_calls = getattr(self, "scene_analysis_calls", 0) + 1
        self.last_scene_analysis_kwargs = {
            "voxel_size": voxel_size,
            "min_voxel_cluster_size": min_voxel_cluster_size,
            "max_splats": max_splats,
            "abort_if_above_limit": abort_if_above_limit,
        }
        return SceneAnalysisReport(
            scene_stats={
                "scene_name": "demo_scene",
                "project_path": "C:/repo/demo_scene.lf",
                "total_splats": 1_998_000,
                "analyzed_splats": 25_000,
                "selected_splats": 0,
                "deleted_splats": 0,
                "voxel_size": voxel_size,
                "min_voxel_cluster_size": min_voxel_cluster_size,
                "approximate": True,
                "sampling_stride": 80,
                "used_native_sampling": True,
                "max_splats": max_splats,
                "aborted": False,
            },
            quality_score=93,
            warnings=[],
            recommendations=["Scene is healthy.", "Preview floating islands."],
            analysis_time=0.42,
            results=[
                AnalysisResult(
                    name="statistics",
                    severity=AnalysisSeverity.INFO,
                    summary="Scene statistics captured.",
                    details={
                        "total_splats": 1_998_000,
                        "deleted_splats": 0,
                        "selected_splats": 0,
                    },
                ),
                AnalysisResult(
                    name="voxel_connectivity",
                    severity=AnalysisSeverity.WARNING,
                    summary="Small floating islands detected.",
                    details={
                        "connected": False,
                        "floating_voxel_groups": 2,
                        "estimated_floating_splats": 412,
                    },
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
                    details={"occupied_voxels": 1200, "density_histogram": {}, "sparse_regions": 0},
                ),
            ],
        )

    def preview_cleanup_candidates(
        self,
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
        max_splats: int,
        abort_if_above_limit: bool,
    ):
        self.cleanup_preview_calls = getattr(self, "cleanup_preview_calls", 0) + 1
        self.last_cleanup_preview_kwargs = {
            "voxel_size": voxel_size,
            "min_voxel_cluster_size": min_voxel_cluster_size,
            "max_splats": max_splats,
            "abort_if_above_limit": abort_if_above_limit,
        }
        return CleanupCandidateSummary(
            scene_name="demo_scene",
            project_path="C:/repo/demo_scene.lf",
            total_splats=1_998_000,
            analyzed_splats=25_000,
            quality_score=93,
            analysis_time=0.42,
            approximate=True,
            report_only=True,
            candidate_group_count=3,
            affected_splats_in_sample=512,
            estimated_affected_splats_total=40_919,
            affected_percentage_of_sample=0.02048,
            estimated_percentage_of_total=0.02047997997997998,
            estimated_affected_splats=40_919,
            floating_voxel_groups=2,
            estimated_floating_splats=412,
            small_voxel_clusters=1,
            estimated_small_cluster_splats=100,
            sparse_regions=0,
            estimated_sparse_splats=100,
            warnings=["2 floating voxel groups detected."],
            recommendations=[
                "Preview floating islands.",
                "Estimated cleanup in analyzed sample: 2.0%",
                "Estimated cleanup extrapolated to full scene: 2.0%",
            ],
            notes=["Preview report only.", "Approximate sampled preview."],
        )

    def preview_cleanup_selection(self):
        self.cleanup_selection_preview_calls += 1
        return CleanupSelectionPreviewResult(
            selected_count=512,
            selection_percentage=512 / 1_998_000,
            selection_mode="replace",
            selection_source="floating voxel clusters, disconnected clusters",
            approximate=True,
            message=(
                "Approximate sampled selection preview. "
                "Selected splats represent estimated cleanup regions. "
                "Run Detailed mode for a more precise preview."
            ),
        )

    def open_cleanup_workspace(
        self,
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
        outlier_distance: float,
        cleanup_aggressiveness: float,
    ):
        self.open_cleanup_workspace_calls += 1
        self.last_open_cleanup_workspace_kwargs = {
            "voxel_size": voxel_size,
            "min_voxel_cluster_size": min_voxel_cluster_size,
            "outlier_distance": outlier_distance,
            "cleanup_aggressiveness": cleanup_aggressiveness,
        }
        return self._workspace(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            outlier_distance=outlier_distance,
            cleanup_aggressiveness=cleanup_aggressiveness,
            selected_count=512,
        )

    def update_cleanup_workspace(
        self,
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
        outlier_distance: float,
        cleanup_aggressiveness: float,
    ):
        self.update_cleanup_workspace_calls += 1
        self.last_update_cleanup_workspace_kwargs = {
            "voxel_size": voxel_size,
            "min_voxel_cluster_size": min_voxel_cluster_size,
            "outlier_distance": outlier_distance,
            "cleanup_aggressiveness": cleanup_aggressiveness,
        }
        return self._workspace(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            outlier_distance=outlier_distance,
            cleanup_aggressiveness=cleanup_aggressiveness,
            selected_count=640,
        )

    def reset_cleanup_workspace(self):
        self.reset_cleanup_workspace_calls += 1
        return SimpleNamespace(ok=True, message="Cleanup workspace reset. Native preview selection cleared.")

    def _workspace(
        self,
        *,
        voxel_size: float,
        min_voxel_cluster_size: int,
        outlier_distance: float,
        cleanup_aggressiveness: float,
        selected_count: int,
    ) -> CleanupWorkspace:
        report = self.analyze_scene(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            max_splats=25_000,
            abort_if_above_limit=False,
        )
        summary = self.preview_cleanup_candidates(
            voxel_size=voxel_size,
            min_voxel_cluster_size=min_voxel_cluster_size,
            max_splats=25_000,
            abort_if_above_limit=False,
        )
        return CleanupWorkspace(
            scene_analysis_report=report,
            cleanup_candidate_summary=summary,
            scene_profile=SceneProfile(
                scene_name="demo_scene",
                project_path="C:/repo/demo_scene.lf",
                total_splats=1_998_000,
                analyzed_splats=25_000,
                quality_score=93,
                profile_label="healthy",
                approximate=True,
            ),
            current_cleanup_parameters=CleanupParameters(
                voxel_size=voxel_size,
                min_voxel_cluster_size=min_voxel_cluster_size,
                outlier_distance=outlier_distance,
                cleanup_aggressiveness=cleanup_aggressiveness,
            ),
            selected_count=selected_count,
            selection_percentage=selected_count / 1_998_000,
            selection_mode="replace",
            selection_source="floating voxel clusters, disconnected clusters",
            approximate=True,
            workspace_update_time=0.012,
            selection_update_time=0.004,
            estimated_sample_reuse=1.0,
        )


def test_run_cluster_analysis_preview_uses_runtime_config_and_returns_success(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.adjust_cluster_distance_threshold(0.05)
    runtime_config.adjust_cluster_min_cluster_size(25)
    runtime_config.adjust_max_cluster_analysis_splats(20_000)
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_cluster_analysis_preview()

    assert success is True
    assert message == "Cluster analysis preview complete."
    assert fake_adapter.analysis_calls == 1
    assert fake_adapter.last_kwargs == {
        "distance_threshold": 0.15,
        "min_cluster_size": 125,
        "max_cluster_analysis_splats": 45_000,
        "abort_if_splat_count_above_limit": False,
    }


def test_cluster_analysis_preset_operators_update_runtime_limit(monkeypatch):
    runtime_config, _ = _load_runner_modules(monkeypatch)
    runtime_controls = __import__(
        "examples.lcht_mcp_test_plugin.operators.runtime_controls",
        fromlist=["runtime_controls"],
    )

    runtime_controls.LCHTMCP_OT_set_cluster_analysis_fast().invoke(None, None)
    assert runtime_config.snapshot_runtime_config().max_cluster_analysis_splats == 10_000

    runtime_controls.LCHTMCP_OT_set_cluster_analysis_balanced().invoke(None, None)
    assert runtime_config.snapshot_runtime_config().max_cluster_analysis_splats == 25_000

    runtime_controls.LCHTMCP_OT_set_cluster_analysis_detailed().invoke(None, None)
    assert runtime_config.snapshot_runtime_config().max_cluster_analysis_splats == 100_000


def test_run_voxel_cluster_analysis_preview_uses_runtime_config_and_returns_success(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.adjust_voxel_size(0.10)
    runtime_config.adjust_voxel_min_cluster_size(15)
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_voxel_cluster_analysis_preview()

    assert success is True
    assert message == "Voxel cluster preview complete in approximate sampled mode."
    assert fake_adapter.voxel_analysis_calls == 1
    assert fake_adapter.last_voxel_kwargs == {
        "voxel_size": 0.35,
        "min_voxel_cluster_size": 25,
        "max_splats": 25_000,
        "abort_if_above_limit": False,
    }


def test_run_scene_analysis_uses_runtime_config_and_returns_success(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.adjust_voxel_size(0.10)
    runtime_config.adjust_voxel_min_cluster_size(15)
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_scene_analysis()

    assert success is True
    assert message == "Scene analysis complete. Quality score: 93"
    assert fake_adapter.scene_analysis_calls == 1
    assert fake_adapter.last_scene_analysis_kwargs == {
        "voxel_size": 0.35,
        "min_voxel_cluster_size": 25,
        "max_splats": 25_000,
        "abort_if_above_limit": False,
    }


def test_run_preview_cleanup_candidates_returns_actionable_summary(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.adjust_voxel_size(0.10)
    runtime_config.adjust_voxel_min_cluster_size(15)
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_preview_cleanup_candidates()

    assert success is True
    assert message == "Cleanup preview complete. Candidate groups: 3"
    assert fake_adapter.cleanup_preview_calls == 1
    assert fake_adapter.last_cleanup_preview_kwargs == {
        "voxel_size": 0.35,
        "min_voxel_cluster_size": 25,
        "max_splats": 25_000,
        "abort_if_above_limit": False,
    }
    assert runtime_config.snapshot_runtime_config().last_cleanup_preview_lines
    assert runtime_config.snapshot_runtime_config().last_cleanup_preview_summary == {
        "scene_name": "demo_scene",
        "project_path": "C:/repo/demo_scene.lf",
        "total_splats": 1_998_000,
        "analyzed_splats": 25_000,
        "quality_score": 93,
        "analysis_time": 0.42,
        "approximate": True,
        "report_only": True,
        "candidate_group_count": 3,
        "affected_splats_in_sample": 512,
        "estimated_affected_splats_total": 40_919,
        "affected_percentage_of_sample": 0.02048,
        "estimated_percentage_of_total": 0.02048,
        "estimated_affected_splats": 40_919,
        "floating_voxel_groups": 2,
        "estimated_floating_splats": 412,
        "small_voxel_clusters": 1,
        "estimated_small_cluster_splats": 100,
        "sparse_regions": 0,
        "estimated_sparse_splats": 100,
        "warnings": ["2 floating voxel groups detected."],
        "recommendations": [
            "Preview floating islands.",
            "Estimated cleanup in analyzed sample: 2.0%",
            "Estimated cleanup extrapolated to full scene: 2.0%",
        ],
        "notes": ["Preview report only.", "Approximate sampled preview."],
    }


def test_run_preview_cleanup_selection_builds_native_selection_preview(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.adjust_voxel_size(0.10)
    runtime_config.adjust_voxel_min_cluster_size(15)
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_preview_cleanup_selection()

    assert success is True
    assert "Approximate sampled selection preview." in message
    assert fake_adapter.cleanup_preview_calls == 1
    assert fake_adapter.cleanup_selection_preview_calls == 1


def test_run_open_cleanup_workspace_returns_interactive_workspace_summary(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.adjust_voxel_size(0.10)
    runtime_config.adjust_voxel_min_cluster_size(15)
    runtime_config.adjust_cleanup_outlier_distance(0.50)
    runtime_config.adjust_cleanup_aggressiveness(0.20)
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_open_cleanup_workspace()

    assert success is True
    assert message == "Cleanup workspace opened."
    assert fake_adapter.open_cleanup_workspace_calls == 1
    assert fake_adapter.last_open_cleanup_workspace_kwargs == {
        "voxel_size": 0.35,
        "min_voxel_cluster_size": 25,
        "outlier_distance": 3.0,
        "cleanup_aggressiveness": 0.7,
    }
    assert runtime_config.snapshot_runtime_config().last_cleanup_workspace_summary is not None


def test_run_update_cleanup_workspace_reuses_latest_workspace_session(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.set_cleanup_workspace_summary({"active": True})
    runtime_config.adjust_cleanup_outlier_distance(-0.25)
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_update_cleanup_workspace()

    assert success is True
    assert message == "Cleanup workspace updated."
    assert fake_adapter.update_cleanup_workspace_calls == 1


def test_run_reset_cleanup_workspace_clears_workspace_summary(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.set_cleanup_workspace_summary({"active": True})
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_reset_cleanup_workspace()

    assert success is True
    assert "Cleanup workspace reset" in message
    assert fake_adapter.reset_cleanup_workspace_calls == 1
    assert runtime_config.snapshot_runtime_config().last_cleanup_workspace_summary is None
