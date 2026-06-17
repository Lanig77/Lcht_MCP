import builtins
import importlib
import sys
from types import SimpleNamespace

import pytest

from lichtfeld_mcp.errors import AdapterUnavailableError, InvalidParameterError


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


class FakeLfTensor:
    def __init__(self, values=None, *, data=None):
        source = values if values is not None else data
        if source is None:
            source = []
        self._values = [bool(item) for item in source]

    def clone(self):
        return FakeLfTensor(self._values)

    def copy(self):
        return FakeLfTensor(self._values)

    def fill(self, value):
        self._values = [bool(value)] * len(self._values)

    def __setitem__(self, index, value):
        self._values[index] = bool(value)

    def tolist(self):
        return list(self._values)

    def __iter__(self):
        return iter(self._values)


class FakeModel:
    sh_degree = 2

    def __init__(self, means, opacity=None, colors=None):
        self._means_values = self._unwrap_values(means)
        self._opacity_values = self._unwrap_values(opacity if opacity is not None else [])
        self._colors_values = self._unwrap_values(colors) if colors is not None else None
        self.last_soft_delete_mask = None
        self.last_soft_delete_argument = None
        self.soft_delete_masks = []
        self.soft_delete_arguments = []
        self.apply_deleted_calls = 0

    def get_means(self):
        return FakeTorchTensor(self._means_values)

    def get_opacity(self):
        return FakeTorchTensor(self._opacity_values)

    def get_colors(self):
        if self._colors_values is None:
            return None
        return FakeTorchTensor(self._colors_values)

    def get_colors_rgb(self):
        return self.get_colors()

    def soft_delete(self, mask):
        self.last_soft_delete_argument = mask
        self.last_soft_delete_mask = list(mask)
        self.soft_delete_arguments.append(mask)
        self.soft_delete_masks.append(list(mask))

    def apply_deleted(self):
        self.apply_deleted_calls += 1
        if self.last_soft_delete_mask is None:
            return
        kept_rows = [
            row for row, selected in zip(self._means_values, self.last_soft_delete_mask) if not selected
        ]
        self._means_values = kept_rows
        if self._opacity_values:
            self._opacity_values = [
                value
                for value, selected in zip(self._opacity_values, self.last_soft_delete_mask)
                if not selected
            ]
        if self._colors_values:
            self._colors_values = [
                value
                for value, selected in zip(self._colors_values, self.last_soft_delete_mask)
                if not selected
            ]
        self.last_soft_delete_mask = None

    @staticmethod
    def _unwrap_values(values):
        if values is None:
            return []
        if isinstance(values, FakeTorchTensor):
            return [list(item) if isinstance(item, list) else item for item in values._values]
        return [list(item) if isinstance(item, list) else item for item in values]


class FakeScene:
    def __init__(self, model, *, name="castle_demo", path="C:/data/castle_demo.lf"):
        self.name = name
        self.path = path
        self._model = model
        self.last_selection_mask_argument = None
        mask_length = len(model._means_values) if model is not None else 0
        self.selection_mask = FakeLfTensor([False] * mask_length)
        self.last_selection_mask = list(self.selection_mask)
        self.notify_changed_calls = 0

    def combined_model(self):
        return self._model

    def set_selection_mask(self, mask):
        self.last_selection_mask_argument = mask
        self.selection_mask = mask
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


class FakeNativeSelectionApi:
    def __init__(self, scene, *, reject_indices: bool = False):
        self.scene = scene
        self.reject_indices = reject_indices
        self.deselect_all_calls = 0
        self.add_to_selection_calls: list[list[int]] = []

    def deselect_all(self):
        self.deselect_all_calls += 1
        cleared_mask = [False] * len(self.scene._model._means_values)
        self.scene.last_selection_mask = list(cleared_mask)
        self.scene.selection_mask = FakeLfTensor(cleared_mask)

    def add_to_selection(self, indices):
        if self.reject_indices:
            raise TypeError("expected native selection object, got Python indices")
        selected_indices = [int(index) for index in indices]
        self.add_to_selection_calls.append(selected_indices)
        mask = [False] * len(self.scene._model._means_values)
        for index in selected_indices:
            mask[index] = True
        self.scene.last_selection_mask = list(mask)
        self.scene.selection_mask = FakeLfTensor(mask)


def test_get_stats_uses_active_lichtfeld_scene_and_computes_bounds(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_module = SimpleNamespace(
        Tensor=FakeLfTensor,
        get_scene=lambda: FakeScene(
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
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: None)

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
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: FakeScene(model=None))

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
    native_selection = FakeNativeSelectionApi(fake_scene)
    fake_module = SimpleNamespace(
        Tensor=FakeLfTensor,
        add_to_selection=native_selection.add_to_selection,
        deselect_all=native_selection.deselect_all,
        get_scene=lambda: fake_scene,
    )

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    result = adapter.select_by_height(4.0, 1.0)

    assert result.selected_count == 2
    assert result.selection_mode == "replace"
    assert native_selection.deselect_all_calls == 1
    assert native_selection.add_to_selection_calls == [[1, 2]]
    assert fake_scene.last_selection_mask_argument is None
    assert fake_scene.last_selection_mask == [False, True, True, False]
    assert fake_scene.notify_changed_calls == 1
    assert adapter.get_stats().selected_count == 2


def test_select_by_height_raises_clear_error_when_selection_api_is_missing(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_module = SimpleNamespace(
        get_scene=lambda: FakeSceneWithoutSelectionApi(
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
        match="native selection API could not accept Python index lists",
    ):
        adapter.select_by_height(0.0, 2.0)


class FakeModelWithOpacityAttribute:
    sh_degree = 1

    def __init__(self, means, opacity):
        self._means_values = FakeModel._unwrap_values(means)
        self.opacity = FakeTorchTensor(FakeModel._unwrap_values(opacity))

    def get_means(self):
        return FakeTorchTensor(self._means_values)


class FakeModelWithColorAttribute:
    sh_degree = 1

    def __init__(self, means, colors, attribute_name="colors_raw"):
        self._means_values = FakeModel._unwrap_values(means)
        setattr(self, attribute_name, FakeTorchTensor(FakeModel._unwrap_values(colors)))

    def get_means(self):
        return FakeTorchTensor(self._means_values)


def test_delete_selection_uses_latest_known_mask_and_updates_stats(monkeypatch):
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
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    adapter.select_by_height(4.0, 1.0)
    native_mask = fake_scene.selection_mask

    deleted = adapter.delete_selection()
    stats = adapter.get_stats()

    assert deleted.ok is True
    assert deleted.message == "Deleted 2 selected splats."
    assert fake_scene._model.soft_delete_masks == [[False, True, True, False]]
    assert isinstance(fake_scene._model.last_soft_delete_argument, FakeLfTensor)
    assert fake_scene._model.last_soft_delete_argument is native_mask
    assert fake_scene._model.apply_deleted_calls == 1
    assert fake_scene.notify_changed_calls == 2
    assert isinstance(fake_scene.last_selection_mask_argument, FakeLfTensor)
    assert fake_scene.last_selection_mask == [False, False]
    assert adapter._cached_selection_mask is None
    assert stats.splat_count == 2
    assert stats.selected_count == 0
    assert stats.bounds.min.z == 0.5
    assert stats.bounds.max.z == 5.0


def test_delete_selection_returns_explicit_result_when_no_selection_exists(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.5],
                    [1.0, 1.0, 3.0],
                ]
            )
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    deleted = adapter.delete_selection()

    assert deleted.ok is False
    assert deleted.message == "No active selection available to delete."
    assert fake_scene._model.last_soft_delete_mask is None
    assert adapter._cached_selection_mask is None


def test_delete_selection_raises_clear_error_when_native_selection_mask_is_unavailable(monkeypatch):
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
    native_selection = FakeNativeSelectionApi(fake_scene)
    fake_module = SimpleNamespace(
        Tensor=FakeLfTensor,
        add_to_selection=native_selection.add_to_selection,
        deselect_all=native_selection.deselect_all,
        get_scene=lambda: fake_scene,
    )

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    adapter.select_by_height(4.0, 1.0)
    fake_scene.selection_mask = None

    with pytest.raises(
        AdapterUnavailableError,
        match="no native scene.selection_mask Tensor is available for deletion",
    ):
        adapter.delete_selection()

    assert fake_scene._model.last_soft_delete_argument is None


def test_select_by_opacity_uses_get_opacity_and_applies_expected_mask(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.5],
                    [1.0, 1.0, 3.0],
                    [2.0, 2.0, 1.5],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.5, 0.9]),
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    result = adapter.select_by_opacity(min_opacity=0.2, max_opacity=0.8)

    assert result.selected_count == 1
    assert result.selection_mode == "replace"
    assert result.message == "Opacity selection applied."
    assert isinstance(fake_scene.last_selection_mask_argument, FakeLfTensor)
    assert fake_scene.last_selection_mask == [False, True, False]
    assert fake_scene.notify_changed_calls == 1
    assert adapter.get_stats().selected_count == 1


def test_select_by_opacity_falls_back_to_opacity_attribute_and_normalizes_range(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModelWithOpacityAttribute(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.5],
                    [1.0, 1.0, 3.0],
                    [2.0, 2.0, 1.5],
                    [3.0, 3.0, 5.0],
                ]
            ),
            opacity=FakeTorchTensor([0.15, 0.4, 0.75, 0.95]),
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    result = adapter.select_by_opacity(min_opacity=0.8, max_opacity=0.2)

    assert result.selected_count == 2
    assert fake_scene.last_selection_mask == [False, True, True, False]
    assert adapter.get_stats().selected_count == 2


def test_select_by_opacity_rejects_invalid_requested_range(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor([[0.0, 0.0, 0.5]]),
            opacity=FakeTorchTensor([0.5]),
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(InvalidParameterError, match="min_opacity must be between 0.0 and 1.0"):
        adapter.select_by_opacity(min_opacity=-0.1, max_opacity=0.5)

    with pytest.raises(InvalidParameterError, match="max_opacity must be between 0.0 and 1.0"):
        adapter.select_by_opacity(min_opacity=0.1, max_opacity=1.1)


def test_select_by_opacity_rejects_invalid_model_opacity_values(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.5],
                    [1.0, 1.0, 3.0],
                ]
            ),
            opacity=FakeTorchTensor([0.2, 1.5]),
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(InvalidParameterError, match="opacity values must be between 0.0 and 1.0"):
        adapter.select_by_opacity(min_opacity=0.0, max_opacity=1.0)


def test_select_by_color_uses_get_colors_with_float_values_and_tolerance(monkeypatch):
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
            ),
            colors=FakeTorchTensor(
                [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.49, 0.51, 0.5],
                    [0.0, 0.0, 1.0],
                ]
            ),
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    result = adapter.select_by_color(128, 128, 128, tolerance=4)

    assert result.selected_count == 1
    assert result.selection_mode == "replace"
    assert result.message == "Color selection applied."
    assert isinstance(fake_scene.last_selection_mask_argument, FakeLfTensor)
    assert fake_scene.last_selection_mask == [False, False, True, False]
    assert fake_scene.notify_changed_calls == 1
    assert adapter.get_stats().selected_count == 1


def test_select_by_color_falls_back_to_color_attribute_with_int_values(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModelWithColorAttribute(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.5],
                    [1.0, 1.0, 3.0],
                    [2.0, 2.0, 1.5],
                ]
            ),
            colors=FakeTorchTensor(
                [
                    [10, 20, 30],
                    [12, 18, 28],
                    [200, 200, 200],
                ]
            ),
            attribute_name="rgb_raw",
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    result = adapter.select_by_color(10, 20, 30, tolerance=2)

    assert result.selected_count == 2
    assert fake_scene.last_selection_mask == [True, True, False]
    assert adapter.get_stats().selected_count == 2


def test_select_by_color_rejects_invalid_rgb_and_tolerance(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor([[0.0, 0.0, 0.5]]),
            colors=FakeTorchTensor([[1.0, 0.0, 0.0]]),
        )
    )
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(InvalidParameterError, match="r must be between 0 and 255"):
        adapter.select_by_color(300, 0, 0)

    with pytest.raises(InvalidParameterError, match="tolerance must be between 0 and 255"):
        adapter.select_by_color(0, 0, 0, tolerance=-1)


def test_get_stats_raises_clear_error_when_get_scene_fails(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module

    def fail_get_scene():
        raise RuntimeError("runtime unavailable")

    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=fail_get_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="get_scene\\(\\) failed to provide an active scene",
    ):
        adapter.get_stats()


def test_get_stats_raises_clear_error_when_scene_is_invalid(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: SimpleNamespace(name="invalid"))

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="Active LichtFeld scene is invalid: combined_model\\(\\) is not available",
    ):
        adapter.get_stats()


def test_select_by_height_raises_clear_error_when_tensor_conversion_is_unavailable(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeSceneWithoutSelectionApi(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.5],
                    [1.0, 1.0, 3.0],
                ]
            )
        )
    )
    native_selection = FakeNativeSelectionApi(fake_scene, reject_indices=True)
    fake_module = SimpleNamespace(
        add_to_selection=native_selection.add_to_selection,
        deselect_all=native_selection.deselect_all,
        get_scene=lambda: fake_scene,
    )

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    fake_scene.last_selection_mask = None

    with pytest.raises(
        AdapterUnavailableError,
        match="expected native selection object, got Python indices",
    ):
        adapter.select_by_height(0.0, 2.0)


def test_select_by_height_uses_model_deleted_tensor_when_scene_selection_mask_is_missing(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.5],
                    [1.0, 1.0, 3.0],
                    [2.0, 2.0, 1.5],
                ]
            )
        )
    )
    fake_scene.selection_mask = None
    fake_scene._model.deleted = FakeLfTensor([False, False, False])
    fake_module = SimpleNamespace(get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    result = adapter.select_by_height(1.0, 4.0)

    assert result.selected_count == 2
    assert isinstance(fake_scene.last_selection_mask_argument, FakeLfTensor)
    assert fake_scene.last_selection_mask == [False, True, True]
