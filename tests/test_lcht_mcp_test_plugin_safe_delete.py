from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace

from lichtfeld_mcp.core.cleanup_workspace import (
    CleanupParameters,
    CleanupWorkspace,
    SceneProfile,
)

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


class FakeCleanupWorkspaceSoftDeleteAdapter:
    def __init__(
        self,
        *,
        should_raise: str | None = None,
        workspace: CleanupWorkspace | None = None,
    ):
        self.soft_delete_current_cleanup_selection_calls = 0
        self.restore_last_delete_calls = 0
        self.apply_deleted_calls = 0
        self.should_raise = should_raise
        self.current_workspace = workspace

    def get_cleanup_workspace(self):
        return self.current_workspace

    def soft_delete_current_cleanup_selection(self):
        self.soft_delete_current_cleanup_selection_calls += 1
        if self.should_raise is not None:
            raise RuntimeError(self.should_raise)
        if self.current_workspace is not None:
            self.current_workspace = replace(
                self.current_workspace,
                candidate_selection_mask=(),
                preview_selected_indices=(),
                preview_selection_active=False,
                native_selection_handle=None,
                selected_count=0,
                selection_percentage=0.0,
                selection_source="no active cleanup preview",
            )
        return SimpleNamespace(
            ok=True,
            soft_deleted_count=12,
            total_splats=1_000,
            percentage=0.012,
            restore_available=True,
            message=(
                "Soft-deleted 12 cleanup workspace splats. "
                "Reversible until apply_deleted() is called."
            ),
        )

    def restore_last_delete(self):
        self.restore_last_delete_calls += 1
        return SimpleNamespace(ok=True, message="Restored 12 deleted splats.")


def _workspace(selected_count: int) -> CleanupWorkspace:
    return CleanupWorkspace(
        scene_analysis_report=SimpleNamespace(
            to_dict=lambda: {"scene_stats": {"project_path": "C:/repo/demo_scene.lf"}},
        ),
        cleanup_candidate_summary=SimpleNamespace(
            estimated_affected_splats_total=12,
            estimated_percentage_of_total=0.012,
            approximate=True,
            to_dict=lambda: {"estimated_affected_splats_total": 12},
        ),
        scene_profile=SceneProfile(
            scene_name="demo_scene",
            project_path="C:/repo/demo_scene.lf",
            total_splats=1_000,
            analyzed_splats=250,
            quality_score=90,
            profile_label="healthy",
            approximate=True,
        ),
        current_cleanup_parameters=CleanupParameters(
            voxel_size=0.25,
            min_voxel_cluster_size=10,
            outlier_distance=2.5,
            cleanup_aggressiveness=0.5,
        ),
        sampled_rows=((0.0, 0.0, 0.0),),
        sampled_indices=(0,),
        candidate_selection_mask=(True,),
        preview_selected_indices=(0,) if selected_count > 0 else (),
        preview_selection_active=selected_count > 0,
        native_selection_handle="C:/repo/demo_scene.lf#cleanup-preview" if selected_count > 0 else None,
        selected_count=selected_count,
        selection_percentage=(selected_count / 1_000),
        selection_mode="replace",
        selection_source="floating voxel clusters",
        approximate=True,
        workspace_update_time=0.01,
        selection_update_time=0.01,
        estimated_sample_reuse=1.0,
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
                "No confirmed cleanup soft delete is available. "
                "Run Soft Delete Cleanup Preview after Preview Cleanup Selection."
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


def test_run_soft_delete_cleanup_selection_refuses_without_workspace(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    fake_adapter = FakeCleanupWorkspaceSoftDeleteAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_soft_delete_cleanup_selection()

    assert success is False
    assert "No cleanup workspace is active" in message
    assert fake_adapter.soft_delete_current_cleanup_selection_calls == 0
    assert fake_adapter.apply_deleted_calls == 0


def test_run_soft_delete_cleanup_selection_refuses_when_selected_count_is_zero(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    fake_adapter = FakeCleanupWorkspaceSoftDeleteAdapter(workspace=_workspace(0))
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_soft_delete_cleanup_selection()

    assert success is False
    assert "selected_count == 0" in message
    assert fake_adapter.soft_delete_current_cleanup_selection_calls == 0


def test_run_soft_delete_cleanup_selection_refuses_when_threshold_is_exceeded(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    fake_adapter = FakeCleanupWorkspaceSoftDeleteAdapter(workspace=_workspace(60_000))
    fake_adapter.current_workspace = replace(
        fake_adapter.current_workspace,
        scene_profile=SceneProfile(
            scene_name="demo_scene",
            project_path="C:/repo/demo_scene.lf",
            total_splats=100_000,
            analyzed_splats=250,
            quality_score=90,
            profile_label="healthy",
            approximate=True,
        ),
        selection_percentage=0.6,
    )
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_soft_delete_cleanup_selection()

    assert success is False
    assert "SAFE_DELETE_MAX_COUNT" in message or "SAFE_DELETE_MAX_RATIO" in message
    assert fake_adapter.soft_delete_current_cleanup_selection_calls == 0


def test_run_soft_delete_cleanup_selection_succeeds_without_apply_deleted(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    fake_adapter = FakeCleanupWorkspaceSoftDeleteAdapter(workspace=_workspace(12))
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_soft_delete_cleanup_selection()

    assert success is True
    assert "Soft-deleted 12 cleanup workspace splats." in message
    assert fake_adapter.soft_delete_current_cleanup_selection_calls == 1
    assert fake_adapter.apply_deleted_calls == 0
    assert runtime_config.snapshot_runtime_config().last_cleanup_workspace_lines


def test_run_restore_last_delete_succeeds_after_workspace_soft_delete(monkeypatch):
    _, test_runner = _load_runner_modules(monkeypatch)
    fake_adapter = FakeCleanupWorkspaceSoftDeleteAdapter()
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_restore_last_delete()

    assert success is True
    assert "Restored 12 deleted splats." == message
    assert fake_adapter.restore_last_delete_calls == 1


def test_run_apply_confirmed_cleanup_refuses_without_pending_cleanup_soft_delete(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()
    fake_adapter = FakeConfirmedCleanupAdapter(should_raise=True)
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_apply_confirmed_cleanup()

    assert success is False
    assert "Run Soft Delete Cleanup Preview after Preview Cleanup Selection" in message
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
