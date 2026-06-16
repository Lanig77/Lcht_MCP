import pytest

from lichtfeld_mcp.adapters.mock import MockLichtfeldAdapter
from lichtfeld_mcp.errors import (
    InvalidParameterError,
    InvalidPathError,
    UnsupportedTargetError,
    UnsupportedUnitError,
)
from lichtfeld_mcp.schemas.common import Box3D, Vec3


def test_open_stats_select_delete_optimize_export():
    adapter = MockLichtfeldAdapter()
    project = adapter.open_project("demo_castle.lfp")
    assert project.splat_count > 0

    stats = adapter.get_scene_stats()
    assert stats.project_name == "demo_castle"
    assert stats.splat_count == project.splat_count

    result = adapter.select_by_box(Box3D(min=Vec3(x=-1, y=-1, z=0), max=Vec3(x=1, y=1, z=2)))
    assert result.selected_count > 0

    before = adapter.get_scene_stats().splat_count
    deleted = adapter.delete_selection()
    assert deleted.ok is True
    assert adapter.get_scene_stats().splat_count < before

    opt = adapter.optimize_for_target("quest3")
    assert opt.target == "quest3"
    assert opt.after_splats <= 2_000_000

    export = adapter.export_scene("out/demo.spz", "spz")
    assert export.format == "spz"


def test_undo_restores_previous_state():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")
    before = adapter.get_scene_stats().splat_count
    adapter.crop_by_height(0, 2)
    assert adapter.get_scene_stats().splat_count < before
    adapter.undo()
    assert adapter.get_scene_stats().splat_count == before


def test_mock_adapter_normalizes_export_format_directly():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")

    export = adapter.export_scene("out/demo.spz", ".SPZ")
    assert export.format == "spz"


def test_mock_adapter_rejects_unknown_target_directly():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")

    with pytest.raises(UnsupportedTargetError, match="Unsupported target"):
        adapter.optimize_for_target("desktop_vr")


def test_mock_adapter_normalizes_reversed_height_range_directly():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")

    adapter.crop_by_height(4, 1)

    history = adapter.list_history()
    assert history[-1].details["z_min"] == 1
    assert history[-1].details["z_max"] == 4


def test_mock_adapter_rejects_empty_export_path_directly():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")

    with pytest.raises(InvalidPathError, match="Output path must not be empty"):
        adapter.export_scene("   ", "spz")


def test_mock_adapter_normalizes_measurement_unit_directly():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")

    measurement = adapter.measure_distance(Vec3(x=0, y=0, z=0), Vec3(x=0, y=0, z=1), unit=" MM ")
    assert measurement.unit == "mm"


def test_mock_adapter_rejects_unsupported_measurement_unit_directly():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")

    with pytest.raises(UnsupportedUnitError, match="Unsupported measurement unit"):
        adapter.measure_distance(Vec3(x=0, y=0, z=0), Vec3(x=0, y=0, z=1), unit="ft")


def test_mock_adapter_rejects_invalid_color_parameters_directly():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")

    with pytest.raises(InvalidParameterError, match="g must be between 0 and 255"):
        adapter.select_by_color(0, 999, 0)

    with pytest.raises(InvalidParameterError, match="tolerance must be between 0 and 255"):
        adapter.select_by_color(0, 0, 0, tolerance=-1)


def test_mock_adapter_rejects_non_positive_max_splats_directly():
    adapter = MockLichtfeldAdapter()
    adapter.open_project("demo.lfp")

    with pytest.raises(InvalidParameterError, match="max_splats must be greater than 0"):
        adapter.optimize_for_target("web", max_splats=-5)
