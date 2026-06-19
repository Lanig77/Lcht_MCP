import pytest
from pathlib import Path

from lichtfeld_mcp.adapters.mock import MockLichtfeldAdapter
from lichtfeld_mcp.core.scene_api import SceneAPI
from lichtfeld_mcp.errors import (
    InvalidParameterError,
    InvalidPathError,
    InvalidSelectionError,
    UnsupportedUnitError,
)


def test_scene_api_routes_scene_lifecycle_through_adapter():
    api = SceneAPI(MockLichtfeldAdapter())

    project = api.open_project("  demo_scene.lfp  ")
    assert project.name == "demo_scene"

    stats = api.get_scene_stats()
    assert stats.project_path == project.path
    report = api.analyze_scene(max_splats=5_000)
    assert report.scene_stats["total_splats"] == project.splat_count

    closed = api.close_project()
    assert closed.ok is True


def test_scene_api_normalizes_box_bounds_before_selection():
    adapter = MockLichtfeldAdapter()
    api = SceneAPI(adapter)
    api.open_project("demo_scene.lfp")

    result = api.select_by_box(5, 4, 3, -1, -2, -3)
    assert result.selected_count > 0

    last_entry = adapter.list_history()[-1]
    assert last_entry.action == "select_by_box"
    assert last_entry.details["box"] == {
        "min": {"x": -1.0, "y": -2.0, "z": -3.0},
        "max": {"x": 5.0, "y": 4.0, "z": 3.0},
    }


def test_scene_api_rejects_unknown_selection_mode():
    api = SceneAPI(MockLichtfeldAdapter())
    api.open_project("demo_scene.lfp")

    with pytest.raises(InvalidSelectionError, match="Unsupported selection mode"):
        api.select_by_height(z_min=0, z_max=2, mode="merge")


def test_scene_api_normalizes_reversed_height_range():
    adapter = MockLichtfeldAdapter()
    api = SceneAPI(adapter)
    api.open_project("demo_scene.lfp")

    api.select_by_height(z_min=5, z_max=1)

    history = adapter.list_history()
    assert history[-1].details["z_min"] == 1
    assert history[-1].details["z_max"] == 5


def test_scene_api_normalizes_target_and_export_format():
    adapter = MockLichtfeldAdapter()
    api = SceneAPI(adapter)
    api.open_project("demo_scene.lfp")

    optimization = api.optimize_for_target(" Quest3 ")
    export = api.export_scene("out/demo.spz", ".SPZ", target=" Unity ")

    assert optimization.target == "quest3"
    assert export.format == "spz"

    history = adapter.list_history()
    assert history[-2].details["target"] == "quest3"
    assert history[-1].details["target"] == "unity"


def test_scene_api_normalizes_output_path_and_measurement_unit():
    adapter = MockLichtfeldAdapter()
    api = SceneAPI(adapter)
    api.open_project("demo_scene.lfp")

    export = api.export_scene("  out/demo.spz  ", ".SPZ")
    measurement = api.measure_distance(0, 0, 0, 0, 0, 2, unit=" CM ")

    assert Path(export.output_path) == Path("out/demo.spz")
    assert measurement.unit == "cm"

    history = adapter.list_history()
    assert Path(str(history[-2].details["output_path"])) == Path("out/demo.spz")
    assert history[-1].details["unit"] == "cm"


def test_scene_api_rejects_empty_project_path():
    api = SceneAPI(MockLichtfeldAdapter())

    with pytest.raises(InvalidPathError, match="Project path must not be empty"):
        api.open_project("   ")


def test_scene_api_rejects_unsupported_measurement_unit():
    api = SceneAPI(MockLichtfeldAdapter())
    api.open_project("demo_scene.lfp")

    with pytest.raises(UnsupportedUnitError, match="Unsupported measurement unit"):
        api.measure_distance(0, 0, 0, 1, 1, 1, unit="inch")


def test_scene_api_rejects_invalid_color_parameters():
    api = SceneAPI(MockLichtfeldAdapter())
    api.open_project("demo_scene.lfp")

    with pytest.raises(InvalidParameterError, match="r must be between 0 and 255"):
        api.select_by_color(300, 0, 0)

    with pytest.raises(InvalidParameterError, match="tolerance must be between 0 and 255"):
        api.select_by_color(0, 0, 0, tolerance=999)


def test_scene_api_rejects_non_positive_max_splats():
    api = SceneAPI(MockLichtfeldAdapter())
    api.open_project("demo_scene.lfp")

    with pytest.raises(InvalidParameterError, match="max_splats must be greater than 0"):
        api.optimize_for_target("web", max_splats=0)
