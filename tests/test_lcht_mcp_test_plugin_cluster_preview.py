from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from test_lcht_mcp_test_plugin_undo import _load_runner_modules


class FakeClusterPreviewAdapter:
    def __init__(self):
        self.analysis_calls = 0

    def analyze_clusters_preview(self, *, distance_threshold: float, min_cluster_size: int):
        self.analysis_calls += 1
        return SimpleNamespace(
            total_splats=1000,
            total_clusters=4,
            largest_cluster_size=900,
            small_cluster_count=3,
            candidate_floating_cluster_count=2,
            candidate_floating_splat_count=40,
            distance_threshold=distance_threshold,
            min_cluster_size=min_cluster_size,
        )


def test_run_cluster_analysis_preview_uses_runtime_config_and_returns_success(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.adjust_cluster_distance_threshold(0.05)
    runtime_config.adjust_cluster_min_cluster_size(25)
    fake_adapter = FakeClusterPreviewAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_cluster_analysis_preview()

    assert success is True
    assert message == "Cluster analysis preview complete."
    assert fake_adapter.analysis_calls == 1
