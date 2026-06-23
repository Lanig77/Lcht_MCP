import builtins
from dataclasses import replace
import importlib
import logging
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

    @property
    def shape(self):
        if not isinstance(self._values, list):
            return ()
        if not self._values:
            return (0,)
        first_row = self._values[0]
        if isinstance(first_row, list):
            return (len(self._values), len(first_row))
        return (len(self._values),)

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self._values

    def __len__(self):
        return len(self._values)

    def __getitem__(self, item):
        return FakeTorchTensor(self._values[item])


class FakeSliceSamplingTensor(FakeTorchTensor):
    def __init__(self, values, *, sampled: bool = False):
        super().__init__(values)
        self._sampled = sampled

    def numpy(self):
        if not self._sampled:
            raise AssertionError("full tensor should not be materialized for sampled preview")
        return self._values

    def __getitem__(self, item):
        return FakeSliceSamplingTensor(self._values[item], sampled=True)


class FakeLargeSampledTensor:
    def __init__(self, total_count: int, *, outlier_indices: set[int] | None = None):
        self._total_count = total_count
        self._outlier_indices = set(outlier_indices or ())

    @property
    def shape(self):
        return (self._total_count, 3)

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        raise AssertionError("full tensor should not be materialized for sampled preview")

    def __len__(self):
        return self._total_count

    def __getitem__(self, item):
        if isinstance(item, slice):
            start = 0 if item.start is None else int(item.start)
            stop = self._total_count if item.stop is None else min(int(item.stop), self._total_count)
            step = 1 if item.step is None else int(item.step)
            rows = [self._row_for_index(index) for index in range(start, stop, step)]
            return FakeSliceSamplingTensor(rows, sampled=True)
        if isinstance(item, int):
            if item < 0 or item >= self._total_count:
                raise IndexError(item)
            return self._row_for_index(item)
        raise TypeError("FakeLargeSampledTensor only supports integer and slice indexing")

    def _row_for_index(self, index: int):
        if index in self._outlier_indices:
            return [10.0, 0.0, 0.0]
        return [0.0, 0.0, 0.0] if index % 2 == 0 else [0.1, 0.0, 0.0]


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

    def __len__(self):
        return len(self._values)


class NonIterableSelectionMask:
    def detach(self):
        return self

    def cpu(self):
        return self


class FakeModel:
    sh_degree = 2

    def __init__(self, means, opacity=None, colors=None):
        self._means_values = self._unwrap_values(means)
        self._opacity_values = self._unwrap_values(opacity if opacity is not None else [])
        self._colors_values = self._unwrap_values(colors) if colors is not None else None
        self.last_soft_delete_mask = None
        self.last_soft_delete_argument = None
        self.last_undelete_argument = None
        self.soft_delete_masks = []
        self.soft_delete_arguments = []
        self.undelete_arguments = []
        self.undelete_calls = 0
        self.apply_deleted_calls = 0
        self._pre_delete_snapshot = None
        self._soft_deleted_mask = None
        self._pending_restore = False

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
        self._pre_delete_snapshot = {
            "means": self._copy_values(self._means_values),
            "opacity": self._copy_values(self._opacity_values),
            "colors": self._copy_values(self._colors_values),
        }
        self._soft_deleted_mask = list(mask)
        self.last_soft_delete_argument = mask
        self.last_soft_delete_mask = list(mask)
        self.soft_delete_arguments.append(mask)
        self.soft_delete_masks.append(list(mask))

    def undelete(self, mask):
        self.undelete_calls += 1
        self.last_undelete_argument = mask
        self.undelete_arguments.append(mask)
        if self._soft_deleted_mask is None:
            return
        if list(mask) != self._soft_deleted_mask:
            raise AssertionError("undelete should receive the original delete mask")
        self._pending_restore = True

    def apply_deleted(self):
        self.apply_deleted_calls += 1
        if self._pending_restore:
            if self._pre_delete_snapshot is None:
                return
            self._means_values = self._copy_values(self._pre_delete_snapshot["means"])
            self._opacity_values = self._copy_values(self._pre_delete_snapshot["opacity"])
            self._colors_values = self._copy_values(self._pre_delete_snapshot["colors"])
            self._pre_delete_snapshot = None
            self._soft_deleted_mask = None
            self._pending_restore = False
            self.last_soft_delete_mask = None
            return
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
        self._soft_deleted_mask = None

    def get_deleted_mask(self):
        return FakeLfTensor([False] * len(self._means_values))

    @staticmethod
    def _unwrap_values(values):
        if values is None:
            return []
        if isinstance(values, FakeTorchTensor):
            return [list(item) if isinstance(item, list) else item for item in values._values]
        return [list(item) if isinstance(item, list) else item for item in values]

    @staticmethod
    def _copy_values(values):
        if values is None:
            return None
        return [list(item) if isinstance(item, list) else item for item in values]


class FakeScene:
    def __init__(self, model, *, name="castle_demo", path="C:/data/castle_demo.lf"):
        self.name = name
        self.path = path
        self.generation = 0
        self.content_generation = 0
        self._model = model
        self.last_selection_mask_argument = None
        mask_length = len(model._means_values) if model is not None else 0
        self._selection_mask = FakeLfTensor([False] * mask_length)
        self.last_selection_mask = list(self._selection_mask)
        self.notify_changed_calls = 0
        self.clear_selection_calls = 0
        self.reset_selection_state_calls = 0

    @property
    def selection_mask(self):
        return self._selection_mask

    @selection_mask.setter
    def selection_mask(self, value):
        self._selection_mask = value

    def combined_model(self):
        return self._model

    def set_selection_mask(self, mask):
        self.last_selection_mask_argument = mask
        self.selection_mask = mask
        self.last_selection_mask = list(mask)

    def get_selection_mask(self):
        return self.last_selection_mask

    def clear_selection(self):
        self.clear_selection_calls += 1
        mask_length = len(self._model._means_values) if self._model is not None else 0
        cleared_mask = FakeLfTensor([False] * mask_length)
        self.selection_mask = cleared_mask
        self.last_selection_mask = list(cleared_mask)

    def reset_selection_state(self):
        self.reset_selection_state_calls += 1
        self.selection_mask = None
        self.last_selection_mask_argument = None
        self.last_selection_mask = None

    def notify_changed(self):
        self.notify_changed_calls += 1


class ExplodingSelectionScene(FakeScene):
    def __init__(self, model, *, name="castle_demo", path="C:/data/castle_demo.lf"):
        self.selection_mask_reads = 0
        super().__init__(model, name=name, path=path)

    @property
    def selection_mask(self):
        self.selection_mask_reads += 1
        raise RuntimeError("Analyze Scene should not access scene.selection_mask.")

    @selection_mask.setter
    def selection_mask(self, value):
        self._selection_mask = value

    def get_selection_mask(self):
        raise RuntimeError("Analyze Scene should not access scene.get_selection_mask().")


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


class StickySelectionScene(FakeScene):
    def clear_selection(self):
        self.clear_selection_calls += 1

    def reset_selection_state(self):
        self.reset_selection_state_calls += 1


class StickyNativeSelectionApi(FakeNativeSelectionApi):
    def deselect_all(self):
        self.deselect_all_calls += 1


class SceneApplyDeletedModel(FakeModel):
    def __init__(self, means, opacity=None, colors=None):
        super().__init__(means, opacity=opacity, colors=colors)
        self.scene = None

    def apply_deleted(self):
        if self.scene is not None:
            last_selection_mask = getattr(self.scene, "last_selection_mask", None)
            if last_selection_mask and any(last_selection_mask):
                self.scene.runtime_warnings.append("selection_not_cleared_before_apply_deleted")
            if getattr(self.scene.renderer, "selection_tensor", None) is not None:
                self.scene.runtime_warnings.append("Cannot clone invalid tensor")
        super().apply_deleted()
        if self.scene is not None:
            selection_tensor = getattr(self.scene.rendering_pipeline, "selection_tensor", None)
            if selection_tensor is not None and len(selection_tensor) != len(self._means_values):
                self.scene.runtime_warnings.append(
                    "Ignoring selection_mask with stale size: "
                    f"model has {len(self._means_values)} tensor has {len(selection_tensor)}"
                )


class SceneApplyDeletedScene(FakeScene):
    def __init__(self, model, *, name="castle_demo", path="C:/data/castle_demo.lf"):
        super().__init__(model, name=name, path=path)
        self.apply_deleted_calls = 0
        self.invalidate_cache_calls = 0
        self.runtime_warnings: list[str] = []
        self.renderer = SimpleNamespace(selection_tensor=self._selection_mask)
        self.rendering_pipeline = SimpleNamespace(selection_tensor=self._selection_mask)
        if hasattr(model, "scene"):
            model.scene = self

    @property
    def selection_mask(self):
        return self._selection_mask

    @selection_mask.setter
    def selection_mask(self, value):
        self._selection_mask = value
        if hasattr(self, "renderer"):
            self.renderer.selection_tensor = value
        if hasattr(self, "rendering_pipeline"):
            self.rendering_pipeline.selection_tensor = value

    def apply_deleted(self):
        self.apply_deleted_calls += 1
        self.renderer.selection_tensor = None
        self.rendering_pipeline.selection_tensor = None
        return self._model.apply_deleted()

    def invalidate_cache(self):
        self.invalidate_cache_calls += 1


def _bump_preview_generation_on_notify_changed(scene: FakeScene) -> None:
    original_notify_changed = scene.notify_changed

    def notify_changed() -> None:
        scene.generation += 1
        original_notify_changed()

    scene.notify_changed = notify_changed


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


def test_get_stats_succeeds_when_selection_mask_is_not_iterable(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [1.0, 2.0, 3.0],
                    [-4.0, 0.5, 8.0],
                ]
            )
        )
    )
    fake_scene.selection_mask = NonIterableSelectionMask()
    fake_scene.has_selection = lambda: False
    fake_module = SimpleNamespace(
        Tensor=FakeLfTensor,
        get_scene=lambda: fake_scene,
        has_selection=lambda: False,
    )

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    stats = adapter.get_stats()

    assert stats.splat_count == 2
    assert stats.selected_count == 0


def test_analyze_clusters_preview_builds_gaussian_cloud_snapshot_and_returns_summary(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [5.2, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    summary = adapter.analyze_clusters_preview(distance_threshold=0.5, min_cluster_size=2)

    assert summary.total_splats == 5
    assert summary.analyzed_splats == 5
    assert summary.total_clusters == 3
    assert summary.largest_cluster_size == 2
    assert summary.small_cluster_count == 1
    assert summary.candidate_floating_cluster_count == 1
    assert summary.candidate_floating_splat_count == 1
    assert summary.approximate is False
    assert summary.refused is False
    assert summary.sampling_stride == 1
    assert summary.message == "Cluster analysis preview complete."
    assert summary.used_native_sampling is False
    assert summary.stats_elapsed_seconds >= 0.0
    assert summary.read_means_elapsed_seconds >= 0.0
    assert summary.sampling_elapsed_seconds >= 0.0
    assert summary.cloud_build_elapsed_seconds >= 0.0
    assert summary.clustering_elapsed_seconds >= 0.0


def test_analyze_clusters_preview_refuses_safely_above_limit_by_default(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module

    class FakeLargeMeansTensor:
        shape = (200_000, 3)

        def detach(self):
            return self

        def cpu(self):
            return self

        def __len__(self):
            return 200_000

        def __getitem__(self, item):
            raise AssertionError("sampling should not run in refusal mode")

        def numpy(self):
            raise AssertionError("full tensor should not be materialized in refusal mode")

    fake_scene = FakeScene(FakeModel(means=FakeTorchTensor([[0.0, 0.0, 0.0]])))
    fake_scene._model.get_means = lambda: FakeLargeMeansTensor()
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    summary = adapter.analyze_clusters_preview(
        distance_threshold=0.5,
        min_cluster_size=100,
        max_cluster_analysis_splats=100_000,
        abort_if_splat_count_above_limit=True,
    )

    assert summary.total_splats == 200_000
    assert summary.analyzed_splats == 0
    assert summary.total_clusters == 0
    assert summary.approximate is False
    assert summary.refused is True
    assert "Refused cluster analysis preview" in summary.message
    assert summary.stats_elapsed_seconds >= 0.0


def test_analyze_clusters_preview_uses_sampled_approximate_mode_by_default_above_limit(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [5.1, 5.0, 5.0],
                    [5.2, 5.0, 5.0],
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
    summary = adapter.analyze_clusters_preview(
        distance_threshold=0.5,
        min_cluster_size=2,
        max_cluster_analysis_splats=3,
    )

    assert summary.total_splats == 6
    assert summary.analyzed_splats == 3
    assert summary.total_clusters == 2
    assert summary.largest_cluster_size == 2
    assert summary.small_cluster_count == 1
    assert summary.candidate_floating_cluster_count == 1
    assert summary.candidate_floating_splat_count == 1
    assert summary.approximate is True
    assert summary.refused is False
    assert summary.sampling_stride == 2
    assert "approximate sampled mode" in summary.message
    assert summary.used_native_sampling is True


def test_analyze_clusters_preview_uses_sampled_approximate_mode_when_abort_is_disabled(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [5.1, 5.0, 5.0],
                    [5.2, 5.0, 5.0],
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
    summary = adapter.analyze_clusters_preview(
        distance_threshold=0.5,
        min_cluster_size=2,
        max_cluster_analysis_splats=3,
        abort_if_splat_count_above_limit=False,
    )

    assert summary.total_splats == 6
    assert summary.analyzed_splats == 3
    assert summary.total_clusters == 2
    assert summary.largest_cluster_size == 2
    assert summary.small_cluster_count == 1
    assert summary.candidate_floating_cluster_count == 1
    assert summary.candidate_floating_splat_count == 1
    assert summary.approximate is True
    assert summary.refused is False
    assert summary.sampling_stride == 2
    assert "approximate sampled mode" in summary.message
    assert summary.used_native_sampling is True


def test_analyze_clusters_preview_samples_before_full_python_materialization(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeSliceSamplingTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [5.1, 5.0, 5.0],
                    [5.2, 5.0, 5.0],
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
    summary = adapter.analyze_clusters_preview(
        distance_threshold=0.5,
        min_cluster_size=2,
        max_cluster_analysis_splats=3,
    )

    assert summary.total_splats == 6
    assert summary.analyzed_splats == 3
    assert summary.approximate is True
    assert summary.used_native_sampling is True


def test_analyze_voxel_clusters_preview_returns_summary(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [5.1, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    summary = adapter.analyze_voxel_clusters_preview(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=4,
        abort_if_above_limit=False,
    )

    assert summary.total_splats == 6
    assert summary.analyzed_splats == 3
    assert summary.occupied_voxels >= 2
    assert summary.total_voxel_clusters >= 1
    assert summary.largest_voxel_cluster_voxel_count >= 1
    assert summary.largest_voxel_cluster_estimated_splats >= 1
    assert summary.small_voxel_cluster_count >= 0
    assert summary.estimated_floating_splats >= 0
    assert summary.approximate is True
    assert summary.refused is False
    assert "approximate sampled mode" in summary.message
    assert summary.used_native_sampling is True


def test_analyze_scene_returns_unified_report(monkeypatch, caplog):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    adapter_impl_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld.adapter")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [5.2, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    caplog.set_level("INFO")
    splat_count_calls: list[str] = []
    original_splat_count_reader = adapter._read_splat_count_without_selection

    def tracked_splat_count_reader(model, position_source):
        splat_count_calls.append(type(position_source).__name__)
        return original_splat_count_reader(model, position_source)

    monkeypatch.setattr(
        adapter,
        "get_stats",
        lambda *, include_selection=True: (_ for _ in ()).throw(
            AssertionError("Analyze Scene should not call get_stats().")
        ),
    )
    monkeypatch.setattr(
        adapter_impl_module,
        "build_scene_stats",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Analyze Scene should not call build_scene_stats().")
        ),
    )
    monkeypatch.setattr(
        adapter,
        "_read_splat_count_without_selection",
        tracked_splat_count_reader,
    )
    report = adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=4,
        abort_if_above_limit=False,
    )

    assert report.scene_stats["scene_name"] == "castle_demo"
    assert report.scene_stats["project_path"] == "C:/data/castle_demo.lf"
    assert report.scene_stats["total_splats"] == 6
    assert report.scene_stats["analyzed_splats"] == 3
    assert report.scene_stats["approximate"] is True
    assert splat_count_calls == ["FakeTorchTensor"]
    assert len(report.results) == 4
    assert any(result.name == "voxel_connectivity" for result in report.results)
    assert "LichtFeld scene analysis: total_splats=6 analyzed_splats=3" in caplog.text
    assert "LichtFeld scene analysis complete: quality_score=" in caplog.text
    assert "analyze_scene entered" not in caplog.text
    assert "after get_lf_module" not in caplog.text
    assert "before engine.run()" not in caplog.text


def test_analyze_scene_succeeds_when_no_active_selection_exists(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = ExplodingSelectionScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                ]
            )
        )
    )
    fake_scene._model.deleted = NonIterableSelectionMask()
    fake_scene.has_selection = lambda: (_ for _ in ()).throw(
        AssertionError("Analyze Scene should not inspect scene.has_selection().")
    )
    fake_module = SimpleNamespace(
        Tensor=FakeLfTensor,
        get_scene=lambda: fake_scene,
        has_selection=lambda: (_ for _ in ()).throw(
            AssertionError("Analyze Scene should not inspect lichtfeld.has_selection().")
        ),
    )

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    report = adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )

    assert report.scene_stats["total_splats"] == 3
    assert report.scene_stats["selected_splats"] == 0
    assert report.scene_stats["approximate"] is False
    assert fake_scene.selection_mask_reads == 0


def test_analyze_scene_re_raises_stage_name_when_get_means_fails(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    adapter_impl_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld.adapter")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
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
    monkeypatch.setattr(
        adapter_impl_module,
        "resolve_position_source",
        lambda model: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="analyze_scene failed at get_means: boom",
    ):
        adapter.analyze_scene()


def test_preview_cleanup_candidates_generates_report_only_summary_without_scene_mutation(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = ExplodingSelectionScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [5.2, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            )
        )
    )
    fake_scene._model.deleted = NonIterableSelectionMask()
    fake_module = SimpleNamespace(
        Tensor=FakeLfTensor,
        get_scene=lambda: fake_scene,
        has_selection=lambda: (_ for _ in ()).throw(
            AssertionError("Cleanup preview should not inspect lichtfeld.has_selection().")
        ),
    )

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=3,
        abort_if_above_limit=False,
    )
    summary = adapter.preview_cleanup_candidates(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=3,
        abort_if_above_limit=False,
    )

    assert summary.report_only is True
    assert summary.approximate is True
    assert summary.candidate_group_count >= 1
    assert fake_scene.selection_mask_reads == 0
    assert fake_scene.notify_changed_calls == 0
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_preview_cleanup_selection_refuses_without_previous_analysis(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(FakeModel(means=FakeTorchTensor([[0.0, 0.0, 0.0]])))
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="Run Analyze Scene first",
    ):
        adapter.preview_cleanup_selection()


def test_preview_cleanup_selection_refuses_without_cleanup_preview(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )

    with pytest.raises(
        AdapterUnavailableError,
        match="Run Preview Cleanup Selection after Analyze Scene",
    ):
        adapter.preview_cleanup_selection()


def test_preview_cleanup_selection_builds_native_selection_without_scene_mutation(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.preview_cleanup_candidates(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )

    result = adapter.preview_cleanup_selection()

    assert result.selected_count == 2
    assert result.selection_mode == "replace"
    assert "floating voxel clusters" in result.selection_source
    assert "disconnected clusters" in result.selection_source
    assert result.approximate is False
    assert native_selection.deselect_all_calls == 1
    assert native_selection.add_to_selection_calls == [[2, 3]]
    assert fake_scene.last_selection_mask == [False, False, True, True]
    assert fake_scene.notify_changed_calls == 1
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0
    assert len(fake_scene._model._means_values) == 4


def test_preview_cleanup_selection_replaces_existing_native_selection_on_repeat(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.preview_cleanup_candidates(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.preview_cleanup_selection()

    fake_scene._model._means_values = [
        [0.0, 0.0, 0.0],
        [0.1, 0.0, 0.0],
        [0.2, 0.0, 0.0],
        [10.0, 0.0, 0.0],
    ]

    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.preview_cleanup_candidates(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    result = adapter.preview_cleanup_selection()

    assert result.selected_count == 1
    assert native_selection.deselect_all_calls == 2
    assert native_selection.add_to_selection_calls[-1] == [3]
    assert fake_scene.last_selection_mask == [False, False, False, True]
    assert fake_scene.notify_changed_calls == 2
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_preview_cleanup_selection_supports_large_sampled_scenes_without_full_materialization(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    total_splats = 100
    fake_scene = FakeScene(
        FakeModel(
            means=FakeLargeSampledTensor(total_splats, outlier_indices={75}),
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
    report = adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=4,
        abort_if_above_limit=False,
    )
    summary = adapter.preview_cleanup_candidates(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=4,
        abort_if_above_limit=False,
    )
    result = adapter.preview_cleanup_selection()

    assert report.scene_stats["approximate"] is True
    assert summary.approximate is True
    assert result.approximate is True
    assert result.selected_count == 1
    assert result.selection_percentage == pytest.approx(0.01)
    assert "Approximate sampled selection preview." in result.message
    assert "Run Detailed mode for a more precise preview." in result.message
    assert native_selection.deselect_all_calls == 1
    assert native_selection.add_to_selection_calls == [[75]]
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_open_cleanup_workspace_reuses_latest_analysis_and_builds_native_selection(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    report = adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )

    workspace = adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    assert workspace.scene_analysis_report is report
    assert workspace.scene_profile.profile_label in {"needs_cleanup", "critical"}
    assert workspace.current_cleanup_parameters.outlier_distance == pytest.approx(2.5)
    assert workspace.current_cleanup_parameters.cleanup_aggressiveness == pytest.approx(0.5)
    assert workspace.current_cleanup_parameters.cluster_distance_threshold == pytest.approx(0.10)
    assert workspace.selected_count == 2
    assert "floating voxel clusters" in workspace.selection_source
    assert "disconnected clusters" in workspace.selection_source
    assert workspace.analysis_reused is True
    assert workspace.estimated_sample_reuse == pytest.approx(1.0)
    assert isinstance(workspace.native_selection_mask, FakeLfTensor)
    assert workspace.native_selection_mask_size == 4
    assert workspace.scene_generation == 0
    assert workspace.workspace_state == "active"
    assert native_selection.deselect_all_calls == 1
    assert native_selection.add_to_selection_calls == [[2, 3]]
    assert fake_scene.notify_changed_calls == 1
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_update_cleanup_workspace_refreshes_selection_without_reanalyzing_scene(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    adapter_impl_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld.adapter")
    original_import_module = adapter_module.importlib.import_module
    original_build_cloud = adapter_impl_module.build_gaussian_cloud_from_positions
    build_cloud_calls = 0
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    def counting_build_cloud(position_rows):
        nonlocal build_cloud_calls
        build_cloud_calls += 1
        return original_build_cloud(position_rows)

    monkeypatch.setattr(
        adapter_impl_module,
        "build_gaussian_cloud_from_positions",
        counting_build_cloud,
    )

    adapter = adapter_module.LichtfeldPluginAdapter()
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        cluster_distance_threshold=0.10,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.2,
    )

    updated = adapter.update_cleanup_workspace(
        voxel_size=2.0,
        min_voxel_cluster_size=2,
        cluster_distance_threshold=0.50,
        outlier_distance=15.0,
        cleanup_aggressiveness=0.9,
    )

    assert updated.current_cleanup_parameters.voxel_size == pytest.approx(2.0)
    assert updated.current_cleanup_parameters.cluster_distance_threshold == pytest.approx(0.50)
    assert updated.current_cleanup_parameters.cleanup_aggressiveness == pytest.approx(0.9)
    assert updated.analysis_reused is False
    assert updated.candidate_update_time >= 0.0
    assert updated.total_workspace_update_time >= updated.selection_update_time
    assert build_cloud_calls == 1
    assert "sparse singleton regions" in updated.selection_source
    assert native_selection.deselect_all_calls == 2
    assert fake_scene.notify_changed_calls == 2
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_update_cleanup_workspace_does_not_invalidate_workspace_when_preview_generation_changes(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            )
        )
    )
    _bump_preview_generation_on_notify_changed(fake_scene)
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    opened = adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    updated = adapter.update_cleanup_workspace(
        voxel_size=2.0,
        min_voxel_cluster_size=2,
        outlier_distance=15.0,
        cleanup_aggressiveness=0.9,
    )

    assert fake_scene.generation == 2
    assert opened.scene_generation == 0
    assert updated.scene_generation == 0
    assert adapter.get_cleanup_workspace() is not None
    assert adapter.get_cleanup_workspace().workspace_state == "active"


def test_preview_selection_refresh_does_not_invalidate_workspace(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            )
        )
    )
    _bump_preview_generation_on_notify_changed(fake_scene)
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.preview_cleanup_candidates(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)

    preview = adapter.preview_cleanup_selection()
    deleted = adapter.soft_delete_cleanup_workspace_selection()

    assert fake_scene.generation >= 2
    assert preview.selected_count == 2
    assert deleted.ok is True


def test_parameter_change_does_not_invalidate_workspace(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            )
        )
    )
    _bump_preview_generation_on_notify_changed(fake_scene)
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.2,
    )

    updated = adapter.update_cleanup_workspace(
        voxel_size=2.0,
        min_voxel_cluster_size=2,
        cluster_distance_threshold=0.50,
        outlier_distance=15.0,
        cleanup_aggressiveness=0.9,
    )
    deleted = adapter.soft_delete_cleanup_workspace_selection()

    assert updated.current_cleanup_parameters.voxel_size == pytest.approx(2.0)
    assert updated.current_cleanup_parameters.cluster_distance_threshold == pytest.approx(0.50)
    assert updated.current_cleanup_parameters.cleanup_aggressiveness == pytest.approx(0.9)
    assert deleted.ok is True


def test_analyze_open_update_soft_delete_succeeds_after_non_destructive_preview_generation_changes(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
        )
    )
    _bump_preview_generation_on_notify_changed(fake_scene)
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.update_cleanup_workspace(
        voxel_size=2.0,
        min_voxel_cluster_size=2,
        outlier_distance=15.0,
        cleanup_aggressiveness=0.9,
    )

    result = adapter.soft_delete_cleanup_workspace_selection()

    assert fake_scene.generation >= 3
    assert fake_scene.content_generation == 0
    assert result.ok is True
    assert result.soft_deleted_count >= 0


def test_open_cleanup_workspace_reuses_latest_scene_analysis_when_valid(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    adapter_impl_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld.adapter")
    original_import_module = adapter_module.importlib.import_module
    original_build_engine = adapter_impl_module.build_default_scene_analysis_engine
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )

    engine_build_calls = 0

    def counting_build_engine():
        nonlocal engine_build_calls
        engine_build_calls += 1
        return original_build_engine()

    monkeypatch.setattr(
        adapter_impl_module,
        "build_default_scene_analysis_engine",
        counting_build_engine,
    )

    workspace = adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        cluster_distance_threshold=0.10,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    assert workspace.analysis_reused is True
    assert engine_build_calls == 0


def test_open_cleanup_workspace_recomputes_when_scene_generation_changes(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    adapter_impl_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld.adapter")
    original_import_module = adapter_module.importlib.import_module
    original_build_engine = adapter_impl_module.build_default_scene_analysis_engine
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            )
        )
    )
    fake_scene.content_generation = 1
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    fake_scene.content_generation = 2

    engine_build_calls = 0

    def counting_build_engine():
        nonlocal engine_build_calls
        engine_build_calls += 1
        return original_build_engine()

    monkeypatch.setattr(
        adapter_impl_module,
        "build_default_scene_analysis_engine",
        counting_build_engine,
    )

    workspace = adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        cluster_distance_threshold=0.10,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    assert workspace.analysis_reused is False
    assert workspace.scene_analysis_report.scene_stats["scene_generation"] == 2
    assert engine_build_calls == 1


def test_reset_cleanup_workspace_clears_native_selection_without_scene_mutation(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    clear_selection_calls_before_reset = fake_scene.clear_selection_calls
    result = adapter.reset_cleanup_workspace()

    assert result.ok is True
    assert fake_scene.clear_selection_calls == clear_selection_calls_before_reset + 1
    assert fake_scene.last_selection_mask == [False, False, False, False]
    assert fake_scene.notify_changed_calls == 2
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_update_cleanup_workspace_refuses_after_scene_reload(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    fake_scene.path = "C:/data/other_scene.lf"

    with pytest.raises(
        AdapterUnavailableError,
        match="Open Cleanup Workspace again",
    ):
        adapter.update_cleanup_workspace(
            voxel_size=1.0,
            min_voxel_cluster_size=2,
            outlier_distance=2.5,
            cleanup_aggressiveness=0.5,
        )
    assert adapter.get_cleanup_workspace() is None


def test_analyze_scene_invalidates_existing_cleanup_workspace(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    adapter.analyze_scene(voxel_size=0.5, min_voxel_cluster_size=1, max_splats=10)

    assert adapter.get_cleanup_workspace() is None


def test_soft_delete_current_cleanup_selection_refuses_without_workspace(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(FakeModel(means=FakeTorchTensor([[0.0, 0.0, 0.0]])))
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="No cleanup workspace is active",
    ):
        adapter.soft_delete_current_cleanup_selection()


def test_soft_delete_current_cleanup_selection_refuses_without_preview_selection(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.reset_cleanup_workspace()

    with pytest.raises(
        AdapterUnavailableError,
        match="No cleanup workspace is active",
    ):
        adapter.soft_delete_current_cleanup_selection()


def test_soft_delete_current_cleanup_selection_refuses_when_selected_count_is_zero(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=99.0,
        cleanup_aggressiveness=0.0,
    )
    adapter._cleanup_workspace_session.workspace = replace(  # type: ignore[union-attr]
        adapter._cleanup_workspace_session.workspace,
        selected_count=0,
    )
    fake_scene.clear_selection()

    with pytest.raises(
        AdapterUnavailableError,
        match="preview selection is empty",
    ):
        adapter.soft_delete_current_cleanup_selection()


def test_soft_delete_cleanup_workspace_selection_consumes_workspace_owned_mask(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    workspace = adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    assert isinstance(workspace.native_selection_mask, FakeLfTensor)
    workspace_mask = workspace.native_selection_mask
    workspace_mask_values = list(workspace_mask)

    fake_scene.selection_mask = FakeLfTensor([True, False, False, False])
    fake_scene.last_selection_mask = [True, False, False, False]

    result = adapter.soft_delete_cleanup_workspace_selection()

    assert result.ok is True
    assert fake_scene._model.last_soft_delete_argument is workspace_mask
    assert fake_scene._model.last_soft_delete_mask == workspace_mask_values
    assert fake_scene._model.last_soft_delete_mask == [False, False, True, True]
    assert fake_scene._model.apply_deleted_calls == 0


def test_soft_delete_cleanup_workspace_selection_refuses_when_workspace_is_stale(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    fake_scene.content_generation = 1

    with pytest.raises(
        AdapterUnavailableError,
        match="current scene generation",
    ):
        adapter.soft_delete_cleanup_workspace_selection()


def test_soft_delete_cleanup_workspace_selection_refuses_when_scene_splat_count_changes(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    fake_scene._model._means_values.append([20.0, 0.0, 0.0])

    with pytest.raises(
        AdapterUnavailableError,
        match="current scene splat count",
    ):
        adapter.soft_delete_cleanup_workspace_selection()

    assert adapter.get_cleanup_workspace() is None
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_soft_delete_cleanup_workspace_selection_refuses_when_workspace_belongs_to_previous_scene(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    fake_scene.path = "C:/data/reloaded_scene.lf"

    with pytest.raises(
        AdapterUnavailableError,
        match="active scene",
    ):
        adapter.soft_delete_cleanup_workspace_selection()

    assert adapter.get_cleanup_workspace() is None
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_soft_delete_cleanup_workspace_selection_refuses_when_native_mask_size_mismatches(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter._cleanup_workspace_session.workspace = replace(  # type: ignore[union-attr]
        adapter._cleanup_workspace_session.workspace,
        native_selection_mask_size=3,
    )

    with pytest.raises(
        AdapterUnavailableError,
        match="mask size",
    ):
        adapter.soft_delete_cleanup_workspace_selection()


def test_soft_delete_cleanup_workspace_selection_refuses_when_threshold_is_exceeded(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    with pytest.raises(
        AdapterUnavailableError,
        match="max_deletable_splats",
    ):
        adapter.soft_delete_cleanup_workspace_selection(max_deletable_splats=1)


def test_soft_delete_current_cleanup_selection_soft_deletes_without_apply_deleted_and_can_restore(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    workspace = adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    workspace_native_mask_values = list(workspace.native_selection_mask)

    result = adapter.soft_delete_current_cleanup_selection()
    assert fake_scene._model.apply_deleted_calls == 0
    assert adapter._cleanup_workspace_session is not None
    assert adapter._cleanup_workspace_session.workspace.preview_selection_active is False
    assert adapter._cleanup_workspace_session.workspace.workspace_state == "soft_deleted"
    assert adapter._cleanup_workspace_session.workspace.native_selection_mask is None
    assert adapter._cleanup_workspace_session.workspace.native_selection_mask_size is None
    restored = adapter.restore_last_delete()
    restored_workspace = adapter.get_cleanup_workspace()
    stats = adapter.get_stats()

    assert result.ok is True
    assert result.soft_deleted_count == workspace.selected_count
    assert result.total_splats == 4
    assert result.restore_available is True
    assert fake_scene._model.soft_delete_masks == [[False, False, True, True]]
    assert restored.ok is True
    assert restored_workspace is not None
    assert restored_workspace.workspace_state == "active"
    assert restored_workspace.preview_selection_active is True
    assert restored_workspace.selected_count == workspace.selected_count
    assert restored_workspace.preview_selected_indices == workspace.preview_selected_indices
    assert restored_workspace.candidate_selection_mask == workspace.candidate_selection_mask
    assert restored_workspace.selection_source == workspace.selection_source
    assert restored_workspace.native_selection_mask is not None
    assert list(restored_workspace.native_selection_mask) == workspace_native_mask_values
    assert fake_scene.last_selection_mask == workspace_native_mask_values
    assert stats.splat_count == 4
    assert stats.selected_count == workspace.selected_count


def test_soft_delete_current_cleanup_selection_is_safe_when_repeated(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    first = adapter.soft_delete_current_cleanup_selection()

    assert first.ok is True
    with pytest.raises(
        AdapterUnavailableError,
        match="No cleanup workspace preview selection is available",
    ):
        adapter.soft_delete_current_cleanup_selection()


def test_cleanup_workspace_can_be_restored_and_updated_after_soft_delete(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    opened = adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    deleted = adapter.soft_delete_current_cleanup_selection()
    restored = adapter.restore_last_delete()
    updated = adapter.update_cleanup_workspace(
        voxel_size=2.0,
        min_voxel_cluster_size=2,
        outlier_distance=15.0,
        cleanup_aggressiveness=0.9,
    )
    reset_result = adapter.reset_cleanup_workspace()

    assert deleted.ok is True
    assert restored.ok is True
    assert updated.selected_count >= 0
    assert updated.preview_selection_active is True
    assert updated.current_cleanup_parameters.voxel_size == pytest.approx(2.0)
    assert opened.scene_profile.project_path == updated.scene_profile.project_path
    assert reset_result.ok is True
    assert adapter.get_cleanup_workspace() is None


def test_cleanup_workspace_restore_does_not_recompute_analysis_or_candidates(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_current_cleanup_selection()
    monkeypatch.setattr(
        adapter,
        "analyze_scene",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("analyze_scene should not run during restore")),
    )
    monkeypatch.setattr(
        adapter,
        "_build_cleanup_candidate_preview",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cleanup workspace should not rebuild during restore")
        ),
    )

    restored = adapter.restore_last_delete()
    restored_workspace = adapter.get_cleanup_workspace()

    assert restored.ok is True
    assert restored_workspace is not None
    assert restored_workspace.preview_selection_active is True


def test_cleanup_workspace_restore_allows_soft_delete_again_without_reopening(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    workspace = adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    first_deleted = adapter.soft_delete_current_cleanup_selection()
    restored = adapter.restore_last_delete()
    second_deleted = adapter.soft_delete_current_cleanup_selection()

    assert first_deleted.ok is True
    assert restored.ok is True
    assert second_deleted.ok is True
    assert second_deleted.soft_deleted_count == workspace.selected_count
    assert fake_scene._model.soft_delete_masks == [
        [False, False, True, True],
        [False, False, True, True],
    ]
    assert adapter._cleanup_workspace_session is not None
    assert adapter._cleanup_workspace_session.workspace.workspace_state == "soft_deleted"


def test_cleanup_workspace_restore_allows_apply_after_second_soft_delete(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    adapter.soft_delete_current_cleanup_selection()
    restored = adapter.restore_last_delete()
    second_deleted = adapter.soft_delete_current_cleanup_selection()
    applied = adapter.apply_cleanup_workspace_deleted()

    assert restored.ok is True
    assert second_deleted.ok is True
    assert applied.ok is True
    assert applied.restore_available is False
    assert applied.workspace_state == "invalidated"
    assert fake_scene._model.apply_deleted_calls == 2
    assert adapter.get_cleanup_workspace() is None


def test_cleanup_workspace_reuses_sampled_analysis_on_large_scene_updates(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(FakeModel(means=FakeTorchTensor([[0.0, 0.0, 0.0]])))
    fake_scene._model.get_means = lambda: FakeLargeSampledTensor(
        250_000,
        outlier_indices={0, 25_000, 50_000},
    )
    fake_scene.set_selection = lambda payload: setattr(
        fake_scene,
        "last_selection_payload",
        list(payload),
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
    adapter.analyze_scene(
        voxel_size=0.25,
        min_voxel_cluster_size=10,
        max_splats=25_000,
        abort_if_above_limit=False,
    )

    opened = adapter.open_cleanup_workspace(
        voxel_size=0.25,
        min_voxel_cluster_size=10,
        cluster_distance_threshold=0.10,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    updated = adapter.update_cleanup_workspace(
        voxel_size=0.30,
        min_voxel_cluster_size=12,
        cluster_distance_threshold=0.20,
        outlier_distance=2.0,
        cleanup_aggressiveness=0.8,
    )

    assert opened.approximate is True
    assert opened.analysis_reused is True
    assert updated.approximate is True
    assert updated.analysis_reused is False
    assert updated.selected_count >= 0
    assert fake_scene._model.last_soft_delete_argument is None
    assert fake_scene._model.apply_deleted_calls == 0


def test_soft_delete_cleanup_candidates_refuses_when_no_preview_exists(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(FakeModel(means=FakeTorchTensor([[0.0, 0.0, 0.0]])))
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="No cleanup preview is available",
    ):
        adapter.soft_delete_cleanup_candidates()


def test_soft_delete_cleanup_candidates_refuses_when_preview_is_approximate(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [0.2, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [5.2, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=3,
        abort_if_above_limit=False,
    )
    preview = adapter.preview_cleanup_candidates(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=3,
    )

    assert preview.approximate is True
    with pytest.raises(
        AdapterUnavailableError,
        match="approximate-only",
    ):
        adapter.soft_delete_cleanup_candidates()


def test_soft_delete_cleanup_candidates_soft_deletes_without_apply_deleted_and_can_restore(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    preview = adapter.preview_cleanup_candidates(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
    )
    deleted = adapter.soft_delete_cleanup_candidates()
    assert fake_scene._model.apply_deleted_calls == 0
    restored = adapter.restore_last_delete()
    stats = adapter.get_stats()

    assert preview.approximate is False
    assert preview.estimated_affected_splats == 2
    assert deleted.ok is True
    assert "Soft-deleted 2 selected splats." in deleted.message
    assert fake_scene._model.soft_delete_masks == [[False, False, True, True]]
    assert restored.ok is True
    assert stats.splat_count == 4
    assert stats.selected_count == 0


def test_apply_cleanup_workspace_deleted_refuses_without_workspace(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(FakeModel(means=FakeTorchTensor([[0.0, 0.0, 0.0]])))
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="No cleanup workspace is active",
    ):
        adapter.apply_cleanup_workspace_deleted()


def test_apply_cleanup_workspace_deleted_refuses_without_soft_delete(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )

    with pytest.raises(
        AdapterUnavailableError,
        match="Soft Delete Cleanup Workspace Selection first",
    ):
        adapter.apply_cleanup_workspace_deleted()


def test_apply_cleanup_workspace_deleted_refuses_when_restore_is_unavailable(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_cleanup_workspace_selection()
    adapter._clear_last_delete()

    with pytest.raises(
        AdapterUnavailableError,
        match="No reversible cleanup workspace soft delete is available",
    ):
        adapter.apply_cleanup_workspace_deleted()


def test_apply_cleanup_workspace_deleted_permanently_applies_workspace_soft_delete(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_cleanup_workspace_selection()

    result = adapter.apply_cleanup_workspace_deleted()
    stats = adapter.get_stats()

    assert result.ok is True
    assert result.initial_splat_count == 4
    assert result.soft_deleted_count == 2
    assert result.permanently_deleted_count == 2
    assert result.final_splat_count == 2
    assert result.restore_available is False
    assert result.workspace_state == "invalidated"
    assert result.message == "Permanently applied cleanup of 2 soft-deleted splats."
    assert fake_scene._model.apply_deleted_calls == 1
    assert adapter._last_delete_mask is None
    assert adapter._last_delete_count == 0
    assert adapter.get_cleanup_workspace() is None
    assert stats.splat_count == 2
    assert stats.selected_count == 0

    with pytest.raises(
        AdapterUnavailableError,
        match="No reversible soft delete is available. The last cleanup was permanently applied.",
    ):
        adapter.restore_last_delete()


def test_apply_cleanup_workspace_deleted_resets_stale_native_selection_mask_to_current_size(
    monkeypatch,
    caplog,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = StickySelectionScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
        )
    )
    native_selection = StickyNativeSelectionApi(fake_scene)
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_cleanup_workspace_selection()

    with caplog.at_level(logging.INFO):
        result = adapter.apply_cleanup_workspace_deleted()

    stats = adapter.get_stats()

    assert result.ok is True
    assert isinstance(fake_scene.selection_mask, FakeLfTensor)
    assert len(fake_scene.selection_mask) == 2
    assert list(fake_scene.selection_mask) == [False, False]
    assert isinstance(fake_scene.last_selection_mask_argument, FakeLfTensor)
    assert list(fake_scene.last_selection_mask_argument) == [False, False]
    assert fake_scene.last_selection_mask == [False, False]
    assert adapter._cached_selection_mask is None
    assert stats.splat_count == 2
    assert stats.selected_count == 0
    assert any(
        "cleanup workspace apply: after selection reset" in record.message
        and "model_size=2" in record.message
        and "selection_tensor_size=2" in record.message
        for record in caplog.records
    )


def test_open_cleanup_workspace_after_apply_deleted_uses_current_size_native_mask_and_soft_delete_succeeds(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = StickySelectionScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
        )
    )
    native_selection = StickyNativeSelectionApi(fake_scene)
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_cleanup_workspace_selection()
    applied = adapter.apply_cleanup_workspace_deleted()

    reopened = adapter.open_cleanup_workspace(
        voxel_size=0.01,
        min_voxel_cluster_size=1,
        outlier_distance=0.05,
        cleanup_aggressiveness=0.5,
    )
    deleted_again = adapter.soft_delete_cleanup_workspace_selection()

    assert applied.ok is True
    assert reopened.scene_profile.total_splats == 2
    assert reopened.native_selection_mask_size == 2
    assert reopened.selected_count >= 1
    assert deleted_again.ok is True
    assert deleted_again.soft_deleted_count == reopened.selected_count


def test_apply_cleanup_workspace_deleted_uses_scene_apply_deleted_to_clear_renderer_selection_lifecycle(
    monkeypatch,
):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = SceneApplyDeletedScene(
        SceneApplyDeletedModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_cleanup_workspace_selection()

    applied = adapter.apply_cleanup_workspace_deleted()
    reopened = adapter.open_cleanup_workspace(
        voxel_size=0.01,
        min_voxel_cluster_size=1,
        outlier_distance=0.05,
        cleanup_aggressiveness=0.5,
    )
    deleted_again = adapter.soft_delete_cleanup_workspace_selection()

    assert applied.ok is True
    assert fake_scene.apply_deleted_calls == 1
    assert fake_scene._model.apply_deleted_calls == 1
    assert fake_scene.invalidate_cache_calls >= 1
    assert fake_scene.runtime_warnings == []
    assert isinstance(fake_scene.renderer.selection_tensor, FakeLfTensor)
    assert len(fake_scene.renderer.selection_tensor) == 2
    assert isinstance(fake_scene.rendering_pipeline.selection_tensor, FakeLfTensor)
    assert len(fake_scene.rendering_pipeline.selection_tensor) == 2
    assert reopened.native_selection_mask_size == 2
    assert deleted_again.ok is True


def test_apply_cleanup_workspace_deleted_refuses_when_workspace_is_stale(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_cleanup_workspace_selection()
    fake_scene.content_generation = 1

    with pytest.raises(
        AdapterUnavailableError,
        match="current scene generation",
    ):
        adapter.apply_cleanup_workspace_deleted()

    assert adapter.get_cleanup_workspace() is None


def test_apply_cleanup_workspace_deleted_does_not_recompute_analysis(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_cleanup_workspace_selection()
    monkeypatch.setattr(
        adapter,
        "analyze_scene",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("analyze_scene should not run during apply")),
    )

    result = adapter.apply_cleanup_workspace_deleted()

    assert result.ok is True


def test_apply_cleanup_workspace_deleted_does_not_recompute_cleanup_candidates(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.soft_delete_cleanup_workspace_selection()
    monkeypatch.setattr(
        adapter,
        "_build_cleanup_candidate_preview",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cleanup candidates should not rebuild during apply")
        ),
    )

    result = adapter.apply_cleanup_workspace_deleted()

    assert result.ok is True


def test_apply_cleanup_candidates_refuses_without_pending_cleanup_soft_delete(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(FakeModel(means=FakeTorchTensor([[0.0, 0.0, 0.0]])))
    fake_module = SimpleNamespace(Tensor=FakeLfTensor, get_scene=lambda: fake_scene)

    monkeypatch.setattr(
        adapter_module.importlib,
        "import_module",
        lambda name, package=None: fake_module if name == "lichtfeld" else original_import_module(name, package),
    )

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="Run Soft Delete Cleanup Preview after Preview Cleanup Selection",
    ):
        adapter.apply_cleanup_candidates()


def test_apply_cleanup_candidates_permanently_finalizes_confirmed_cleanup(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module
    fake_scene = FakeScene(
        FakeModel(
            means=FakeTorchTensor(
                [
                    [0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [5.0, 5.0, 5.0],
                    [10.0, 0.0, 0.0],
                ]
            ),
            opacity=FakeTorchTensor([0.1, 0.2, 0.3, 0.4]),
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
    adapter.analyze_scene(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
        abort_if_above_limit=False,
    )
    adapter.preview_cleanup_candidates(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        max_splats=10,
    )
    soft_deleted = adapter.soft_delete_cleanup_candidates()
    applied = adapter.apply_cleanup_candidates()
    stats = adapter.get_stats()

    assert soft_deleted.ok is True
    assert applied.ok is True
    assert applied.message == "Permanently applied cleanup of 2 soft-deleted splats."
    assert fake_scene._model.apply_deleted_calls == 1
    assert fake_scene.reset_selection_state_calls == 2
    assert stats.splat_count == 2
    assert stats.selected_count == 0

    with pytest.raises(
        AdapterUnavailableError,
        match="already finalized with apply_deleted",
    ):
        adapter.restore_last_delete()

    with pytest.raises(
        AdapterUnavailableError,
        match="Run Soft Delete Cleanup Preview after Preview Cleanup Selection",
    ):
        adapter.apply_cleanup_candidates()


def test_apply_pending_delete_invalidates_existing_cleanup_workspace(monkeypatch):
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
    adapter.analyze_scene(voxel_size=1.0, min_voxel_cluster_size=2, max_splats=10)
    adapter.open_cleanup_workspace(
        voxel_size=1.0,
        min_voxel_cluster_size=2,
        outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    )
    adapter.select_by_height(4.0, 1.0)
    adapter.soft_delete_selection()

    result = adapter.apply_pending_delete()

    assert result.ok is True
    assert adapter.get_cleanup_workspace() is None


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
    native_selection = FakeNativeSelectionApi(fake_scene)
    fake_module = SimpleNamespace(
        Tensor=FakeLfTensor,
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
    native_mask = fake_scene.selection_mask

    deleted = adapter.delete_selection()
    stats = adapter.get_stats()

    assert deleted.ok is True
    assert deleted.message == "Deleted 2 selected splats."
    assert fake_scene._model.soft_delete_masks == [[False, True, True, False]]
    assert isinstance(fake_scene._model.last_soft_delete_argument, FakeLfTensor)
    assert fake_scene._model.last_soft_delete_argument is native_mask
    assert fake_scene._model.apply_deleted_calls == 1
    assert fake_scene.clear_selection_calls >= 2
    assert native_selection.deselect_all_calls >= 3
    assert fake_scene.reset_selection_state_calls >= 2
    assert fake_scene.notify_changed_calls >= 3
    assert isinstance(fake_scene.last_selection_mask_argument, FakeLfTensor)
    assert list(fake_scene.last_selection_mask_argument) == [False, False]
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


def test_restore_last_delete_uses_original_native_mask_and_restores_stats(monkeypatch):
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
    native_mask = fake_scene.selection_mask
    soft_deleted = adapter.soft_delete_selection()

    restored = adapter.restore_last_delete()
    stats = adapter.get_stats()

    assert soft_deleted.ok is True
    assert "Soft-deleted" in soft_deleted.message
    assert restored.ok is True
    assert restored.message == "Restored 2 deleted splats."
    assert fake_scene._model.undelete_calls == 1
    assert fake_scene._model.last_undelete_argument is native_mask
    assert fake_scene._model.apply_deleted_calls == 1
    assert fake_scene.reset_selection_state_calls == 2
    assert fake_scene.notify_changed_calls == 3
    assert stats.splat_count == 4
    assert stats.selected_count == 0

    with pytest.raises(
        AdapterUnavailableError,
        match="No previous LichtFeld soft delete is available to restore",
    ):
        adapter.restore_last_delete()


def test_restore_last_delete_fails_cleanly_when_no_previous_delete_exists(monkeypatch):
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

    with pytest.raises(
        AdapterUnavailableError,
        match="No previous LichtFeld soft delete is available to restore",
    ):
        adapter.restore_last_delete()


def test_restore_last_delete_after_apply_deleted_reports_finalization_limitation(monkeypatch):
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
    deleted = adapter.select_by_height(4.0, 1.0)
    assert deleted.selected_count == 2
    destructive_delete = adapter.delete_selection()

    assert destructive_delete.ok is True
    assert destructive_delete.message == "Deleted 2 selected splats."

    with pytest.raises(
        AdapterUnavailableError,
        match="already finalized with apply_deleted",
    ):
        adapter.restore_last_delete()


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
