from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from test_lcht_mcp_test_plugin_undo import _load_runner_modules


class FakeClusterPreviewAdapter:
    def __init__(self):
        self.analysis_calls = 0
        self.last_kwargs = None
        self.voxel_analysis_calls = 0
        self.last_voxel_kwargs = None

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
