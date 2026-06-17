from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from test_lcht_mcp_test_plugin_undo import _load_runner_modules


class FakeSafeDeleteAdapter:
    def __init__(self):
        self.get_stats_calls = 0
        self.remaining_count = 100

    def get_stats(self):
        self.get_stats_calls += 1
        return SimpleNamespace(
            splat_count=self.remaining_count,
            bounds=SimpleNamespace(min=SimpleNamespace(z=0.0), max=SimpleNamespace(z=2.0)),
        )

    def select_by_height(self, z_min: float, z_max: float):
        return SimpleNamespace(selected_count=3)

    def delete_selection(self):
        self.remaining_count -= 3
        return SimpleNamespace(ok=True, message="Deleted 3 selected splats.")


def test_run_safe_delete_test_skips_post_delete_stats_when_verification_is_disabled(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()

    fake_adapter = FakeSafeDeleteAdapter()
    test_runner.lf.deselect_all = lambda: None
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_safe_delete_test()

    assert success is True
    assert message == "Safe delete validation complete."
    assert fake_adapter.get_stats_calls == 1
