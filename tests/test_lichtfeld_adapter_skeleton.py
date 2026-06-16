import builtins
import importlib
import sys
from types import SimpleNamespace

import pytest

from lichtfeld_mcp.errors import AdapterUnavailableError


def test_importing_lichtfeld_adapter_module_does_not_import_lichtfeld(monkeypatch):
    original_import = builtins.__import__
    requested_lichtfeld_imports: list[str] = []

    def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "lichtfeld" or name.startswith("lichtfeld."):
            requested_lichtfeld_imports.append(name)
            raise AssertionError("lichtfeld should not be imported at module import time")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", tracking_import)
    sys.modules.pop("lichtfeld_mcp.adapters.lichtfeld", None)

    module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")

    assert hasattr(module, "LichtfeldPluginAdapter")
    assert requested_lichtfeld_imports == []


def test_open_project_without_lichtfeld_raises_adapter_unavailable_error(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name == "lichtfeld":
            raise ModuleNotFoundError("No module named 'lichtfeld'", name="lichtfeld")
        return original_import_module(name, package)

    monkeypatch.setattr(adapter_module.importlib, "import_module", fake_import_module)

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="LichtFeld Studio Python plugin API is not available",
    ):
        adapter.open_project("demo_scene.lfp")


class FakeTorchTensor:
    def __init__(self, values):
        self._values = values

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self._values


class FakeModel:
    sh_degree = 2

    def __init__(self, means, opacity=None):
        self._means = means
        self._opacity = opacity if opacity is not None else []

    def get_means(self):
        return self._means

    def get_opacity(self):
        return self._opacity


class FakeScene:
    def __init__(self, model, *, name="castle_demo", path="C:/data/castle_demo.lf"):
        self.name = name
        self.path = path
        self._model = model
        self.last_selection_mask = None
        self.notify_changed_calls = 0

    def combined_model(self):
        return self._model

    def set_selection_mask(self, mask):
        self.last_selection_mask = list(mask)

    def get_selection_mask(self):
        return self.last_selection_mask

    def notify_changed(self):
        self.notify_changed_calls += 1


class FakeSceneWithoutSelectionApi:
    def __init__(self, model):
        self._model = model

    def combined_model(self):
        return self._model


def test_get_stats_uses_active_lichtfeld_scene_and_computes_bounds(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_module = SimpleNamespace(
        scene=FakeScene(
            FakeModel(
                means=FakeTorchTensor(
                    [
                        [1.0, 2.0, 3.0],
                        [-4.0, 0.5, 8.0],
                        [2.5, -1.5, 1.0],
                    ]
                ),
                opacity=FakeTorchTensor([0.2, 0.6, 1.0]),
            )
        )
    )

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    stats = adapter.get_stats()

    assert stats.project_name == "castle_demo"
    assert stats.project_path == "C:/data/castle_demo.lf"
    assert stats.splat_count == 3
    assert stats.bounds.min.x == -4.0
    assert stats.bounds.min.y == -1.5
    assert stats.bounds.min.z == 1.0
    assert stats.bounds.max.x == 2.5
    assert stats.bounds.max.y == 2.0
    assert stats.bounds.max.z == 8.0
    assert stats.sh_degree == 2
    assert stats.opacity_mean == 0.6


def test_get_stats_raises_clear_error_when_no_active_scene_exists(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_module = SimpleNamespace(scene=None)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="No active LichtFeld scene is available",
    ):
        adapter.get_stats()


def test_get_stats_raises_clear_error_when_no_combined_model_exists(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_module = SimpleNamespace(scene=FakeScene(model=None))

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="No active LichtFeld combined model is available",
    ):
        adapter.get_stats()


def test_select_by_height_normalizes_range_and_applies_expected_mask(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.5],
                    [1.0, 1.0, 3.0],
                    [2.0, 2.0, 1.5],
                    [3.0, 3.0, 5.0],
                ]
            )
        )
    )
    fake_module = SimpleNamespace(scene=fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    result = adapter.select_by_height(4.0, 1.0)

    assert result.selected_count == 2
    assert result.selection_mode == "replace"
    assert fake_scene.last_selection_mask == [False, True, True, False]
    assert fake_scene.notify_changed_calls == 1
    assert adapter.get_stats().selected_count == 2


def test_select_by_height_raises_clear_error_when_selection_api_is_missing(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_module = SimpleNamespace(
        scene=FakeSceneWithoutSelectionApi(
            FakeModel(
                means=FakeTorchTensor(
                    [
                        [0.0, 0.0, 0.5],
                        [1.0, 1.0, 3.0],
                    ]
                )
            )
        )
    )

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="set_selection_mask",
    ):
        adapter.select_by_height(0.0, 2.0)
