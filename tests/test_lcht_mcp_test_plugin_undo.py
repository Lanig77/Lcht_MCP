from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _install_plugin_stubs(monkeypatch):
    fake_lf = ModuleType("lichtfeld")
    fake_lf.log = SimpleNamespace(
        info=lambda message: None,
        error=lambda message: None,
    )
    fake_lf.ui = SimpleNamespace(
        Panel=type("Panel", (), {}),
        PanelSpace=SimpleNamespace(MAIN_PANEL_TAB="main"),
        theme=lambda: SimpleNamespace(palette=SimpleNamespace(text_dim=(0.0, 0.0, 0.0, 1.0))),
        ops=SimpleNamespace(invoke=lambda operator_id: None),
    )
    fake_lf.register_class = lambda cls: None
    fake_lf.unregister_class = lambda cls: None
    fake_lfs_plugins = ModuleType("lfs_plugins")
    fake_lfs_plugins_types = ModuleType("lfs_plugins.types")
    fake_lfs_plugins_types.Event = object
    fake_lfs_plugins_types.Operator = type("Operator", (), {})
    fake_lfs_plugins.types = fake_lfs_plugins_types

    for module_name in list(sys.modules):
        if module_name == "examples.lcht_mcp_test_plugin" or module_name.startswith(
            "examples.lcht_mcp_test_plugin."
        ):
            sys.modules.pop(module_name, None)

    monkeypatch.setitem(sys.modules, "lichtfeld", fake_lf)
    monkeypatch.setitem(sys.modules, "lfs_plugins", fake_lfs_plugins)
    monkeypatch.setitem(sys.modules, "lfs_plugins.types", fake_lfs_plugins_types)
    return fake_lf


class FakeUndoModel:
    def __init__(self, total_count: int):
        self.total_count = total_count
        self.deleted_count = 0


class FakeUndoScene:
    def __init__(self, model: FakeUndoModel):
        self._model = model
        self.notify_changed_calls = 0
        self.clear_selection_calls = 0

    def combined_model(self):
        return self._model

    def notify_changed(self):
        self.notify_changed_calls += 1

    def clear_selection(self):
        self.clear_selection_calls += 1


class FakeUndoAdapter:
    def __init__(self, scene: FakeUndoScene, *, selected_count: int):
        self.scene = scene
        self.selected_count = selected_count
        self.delete_calls = 0
        self.restore_calls = 0
        self.last_deleted_count = 0

    def get_stats(self):
        remaining_count = self.scene._model.total_count - self.scene._model.deleted_count
        return SimpleNamespace(
            splat_count=remaining_count,
            selected_count=self.selected_count,
        )

    def select_by_height(self, z_min: float, z_max: float):
        return SimpleNamespace(selected_count=self.selected_count)

    def delete_selection(self):
        self.delete_calls += 1
        self.last_deleted_count = self.selected_count
        self.scene._model.deleted_count += self.selected_count
        self.selected_count = 0
        return SimpleNamespace(ok=True, message="Deleted selected splats.")

    def restore_last_delete(self):
        self.restore_calls += 1
        self.scene._model.deleted_count -= self.last_deleted_count
        self.last_deleted_count = 0
        self.scene.notify_changed()
        return SimpleNamespace(ok=True, message="Restored selected splats.")


def _load_runner_modules(monkeypatch):
    _install_plugin_stubs(monkeypatch)
    runtime_config = importlib.import_module("examples.lcht_mcp_test_plugin.core.runtime_config")
    test_runner = importlib.import_module("examples.lcht_mcp_test_plugin.core.test_runner")
    runtime_config.reset_runtime_config()
    return runtime_config, test_runner


def test_run_undo_validation_returns_early_when_delete_flags_are_not_enabled(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.reset_runtime_config()
    monkeypatch.setattr(
        test_runner,
        "_build_adapter",
        lambda: (_ for _ in ()).throw(AssertionError("adapter should not be built")),
    )

    success, message = test_runner.run_undo_validation()

    assert success is True
    assert "ENABLE_SAFE_DELETE=False" in message


def test_run_undo_validation_restores_the_initial_splat_count(monkeypatch):
    runtime_config, test_runner = _load_runner_modules(monkeypatch)
    runtime_config.arm_safe_delete()
    runtime_config.confirm_safe_delete()

    fake_model = FakeUndoModel(total_count=100)
    fake_scene = FakeUndoScene(fake_model)
    fake_adapter = FakeUndoAdapter(fake_scene, selected_count=3)
    test_runner.lf.get_scene = lambda: fake_scene
    monkeypatch.setattr(test_runner, "_build_adapter", lambda: (fake_adapter, Path("C:/repo")))

    success, message = test_runner.run_undo_validation()

    assert success is True
    assert "restored" in message
    assert fake_adapter.delete_calls == 1
    assert fake_adapter.restore_calls == 1
    assert fake_scene.notify_changed_calls == 1
    assert fake_adapter.get_stats().splat_count == 100
    assert fake_adapter.get_stats().selected_count == 0
