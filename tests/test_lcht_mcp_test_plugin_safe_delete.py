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


class FakeCleanupPreviewSoftDeleteAdapter:
    def __init__(self, *, should_raise: bool = False):
        self.soft_delete_cleanup_candidates_calls = 0
        self.apply_deleted_calls = 0
        self.should_raise = should_raise

    def soft_delete_cleanup_candidates(self):
        self.soft_delete_cleanup_candidates_calls += 1
        if self.should_raise:
            raise RuntimeError(
                "Cleanup preview is approximate-only; no reliable native selection is available."
            )
        return SimpleNamespace(
            ok=True,
            message=(
                "Soft-deleted 12 selected splats. "
                "Reversible until apply_deleted() is called."
            ),
        )


class FakeConfirmedCleanupAdapter:
    def __init__(self, *, should_raise: bool = False):
        self.apply_cleanup_candidates_calls = 0
        self.apply_deleted_calls = 0
        self.should_raise = should_raise
        self.current_splat_count = 100

    def get_stats(self):
        return SimpleNamespace(splat_count=self.current_splat_count)

    def apply_cleanup_candidates(self):
        self.apply_cleanup_candidates_calls += 1
        if self.should_raise:
            raise RuntimeError(
                "No confirmed cleanup soft delete is available. Run Soft Delete Cleanup Preview first."
            )
        self.apply_deleted_calls += 1
        self.current_splat_count -= 12
        return SimpleNamespace(
            ok=True,
            message="Permanently applied cleanup of 12 soft-deleted splats.",
        )


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


def test_run_soft_delete_cleanup_preview_refuses_when_no_preview_exists(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()

    fake_adapter = FakeCleanupPreviewSoftDeleteAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_soft_delete_cleanup_preview()

    assert success is False
    assert "No cleanup preview is available" in message
    assert fake_adapter.soft_delete_cleanup_candidates_calls == 0
    assert fake_adapter.apply_deleted_calls == 0


def test_run_soft_delete_cleanup_preview_refuses_when_preview_is_approximate(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    runtime_config.set_cleanup_preview_summary(
        {
            "total_splats": 1_000,
            "estimated_affected_splats": 12,
            "approximate": True,
        }
    )

    fake_adapter = FakeCleanupPreviewSoftDeleteAdapter(should_raise=True)
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_soft_delete_cleanup_preview()

    assert success is False
    assert "approximate-only" in message
    assert fake_adapter.soft_delete_cleanup_candidates_calls == 1
    assert fake_adapter.apply_deleted_calls == 0


def test_run_soft_delete_cleanup_preview_succeeds_without_apply_deleted(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    runtime_config.set_cleanup_preview_summary(
        {
            "total_splats": 1_000,
            "estimated_affected_splats": 12,
            "approximate": False,
        }
    )

    fake_adapter = FakeCleanupPreviewSoftDeleteAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_soft_delete_cleanup_preview()

    assert success is True
    assert "Soft-deleted 12 selected splats." in message
    assert fake_adapter.soft_delete_cleanup_candidates_calls == 1
    assert fake_adapter.apply_deleted_calls == 0


def test_run_apply_confirmed_cleanup_returns_early_without_confirmation(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    monkeypatch.setattr(
        test_runner,
        "_build_adapter",
        lambda: (_ for _ in ()).throw(AssertionError("adapter should not be built")),
    )

    success, message = test_runner.run_apply_confirmed_cleanup()

    assert success is True
    assert "CONFIRM_SAFE_DELETE=False" in message


def test_run_apply_confirmed_cleanup_refuses_without_pending_cleanup_soft_delete(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    fake_adapter = FakeConfirmedCleanupAdapter(should_raise=True)
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_apply_confirmed_cleanup()

    assert success is False
    assert "Run Soft Delete Cleanup Preview first" in message
    assert fake_adapter.apply_cleanup_candidates_calls == 1
    assert fake_adapter.apply_deleted_calls == 0


def test_run_apply_confirmed_cleanup_succeeds_with_single_apply_deleted(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    fake_adapter = FakeConfirmedCleanupAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_apply_confirmed_cleanup()

    assert success is True
    assert message == "Permanently applied cleanup of 12 soft-deleted splats."
    assert fake_adapter.apply_cleanup_candidates_calls == 1
    assert fake_adapter.apply_deleted_calls == 1
