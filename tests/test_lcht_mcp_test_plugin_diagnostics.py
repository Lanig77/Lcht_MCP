from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

from test_lcht_mcp_test_plugin_undo import _install_plugin_stubs


class FakeDiagnosticMeans:
    def __init__(self, count: int):
        self._count = count

    @property
    def shape(self) -> tuple[int, int]:
        return (self._count, 3)

    def __len__(self) -> int:
        return self._count


class FakeDiagnosticTensor:
    def __init__(self, size: int, *, valid: bool = True):
        self._size = size
        self._valid = valid

    @property
    def shape(self) -> tuple[int]:
        return (self._size,)

    def clone(self) -> "FakeDiagnosticTensor":
        if not self._valid:
            raise RuntimeError("Cannot clone invalid tensor")
        return FakeDiagnosticTensor(self._size, valid=self._valid)

    def copy(self) -> "FakeDiagnosticTensor":
        return self.clone()

    def __len__(self) -> int:
        return self._size


class FakeDiagnosticModel:
    def __init__(self, count: int):
        self.count = count
        self.deleted = FakeDiagnosticTensor(count)

    def get_means(self) -> FakeDiagnosticMeans:
        return FakeDiagnosticMeans(self.count)


class FakeDiagnosticRenderer:
    def __init__(self, selection_tensor: FakeDiagnosticTensor):
        self.selection_tensor = selection_tensor


class FakeDiagnosticScene:
    def __init__(self, model: FakeDiagnosticModel, selection_tensor: FakeDiagnosticTensor):
        self._model = model
        self.selection_mask = selection_tensor
        self.renderer = FakeDiagnosticRenderer(selection_tensor)
        self.rendering_pipeline = SimpleNamespace(selection_tensor=selection_tensor)

    def combined_model(self) -> FakeDiagnosticModel:
        return self._model


class FakeDiagnosticAdapter:
    def __init__(self, scene: FakeDiagnosticScene, *, keep_stale_renderer_tensor: bool):
        self.scene = scene
        self.keep_stale_renderer_tensor = keep_stale_renderer_tensor

    def apply_cleanup_workspace_deleted(self):
        self.scene._model.count = 2
        self.scene._model.deleted = FakeDiagnosticTensor(2)
        self.scene.selection_mask = FakeDiagnosticTensor(2)
        if self.keep_stale_renderer_tensor:
            stale_tensor = self.scene.renderer.selection_tensor
            stale_tensor._valid = False
            self.scene.rendering_pipeline.selection_tensor = stale_tensor
        else:
            fresh_tensor = FakeDiagnosticTensor(2)
            self.scene.renderer.selection_tensor = fresh_tensor
            self.scene.rendering_pipeline.selection_tensor = fresh_tensor
        return SimpleNamespace(ok=True, message="Applied cleanup.")


def _load_diagnostics_modules(monkeypatch):
    fake_lf = _install_plugin_stubs(monkeypatch)
    info_logs: list[str] = []
    error_logs: list[str] = []
    fake_lf.log = SimpleNamespace(
        info=lambda message: info_logs.append(message),
        error=lambda message: error_logs.append(message),
    )

    runtime_config = importlib.import_module("examples.lcht_mcp_test_plugin.core.runtime_config")
    test_runner = importlib.import_module("examples.lcht_mcp_test_plugin.core.test_runner")
    diagnostics = importlib.import_module("examples.lcht_mcp_test_plugin.core.diagnostics")
    runtime_config.reset_runtime_config()
    return fake_lf, info_logs, error_logs, runtime_config, test_runner, diagnostics


def test_apply_deleted_selection_lifetime_diagnostic_reports_stale_renderer_owner(monkeypatch):
    fake_lf, _info_logs, error_logs, runtime_config, test_runner, diagnostics = (
        _load_diagnostics_modules(monkeypatch)
    )
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()

    scene = FakeDiagnosticScene(FakeDiagnosticModel(4), FakeDiagnosticTensor(4))
    adapter = FakeDiagnosticAdapter(scene, keep_stale_renderer_tensor=True)
    fake_lf.get_scene = lambda: scene

    monkeypatch.setattr(diagnostics, "_configure_repo_import_path", lambda: None)
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (adapter, Path("C:/repo")))

    success, message = diagnostics.run_apply_deleted_selection_lifetime_diagnostics()

    assert success is False
    assert "scene.renderer.selection_tensor" in message
    assert any("Cannot clone invalid tensor" in log_line for log_line in error_logs)
    assert any(
        "stale_selection_owner path=scene.renderer.selection_tensor" in log_line
        for log_line in error_logs
    )


def test_apply_deleted_selection_lifetime_diagnostic_succeeds_when_selection_state_is_clean(
    monkeypatch,
):
    fake_lf, _info_logs, error_logs, runtime_config, test_runner, diagnostics = (
        _load_diagnostics_modules(monkeypatch)
    )
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()

    scene = FakeDiagnosticScene(FakeDiagnosticModel(4), FakeDiagnosticTensor(4))
    adapter = FakeDiagnosticAdapter(scene, keep_stale_renderer_tensor=False)
    fake_lf.get_scene = lambda: scene

    monkeypatch.setattr(diagnostics, "_configure_repo_import_path", lambda: None)
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (adapter, Path("C:/repo")))

    success, message = diagnostics.run_apply_deleted_selection_lifetime_diagnostics()

    assert success is True
    assert "without stale selection owners" in message
    assert not any("stale_selection_owner" in log_line for log_line in error_logs)
    assert not any("Cannot clone invalid tensor" in log_line for log_line in error_logs)
