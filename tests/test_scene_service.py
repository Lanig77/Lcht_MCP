from unittest.mock import Mock

import pytest

from lichtfeld_mcp.core.scene_api import SceneAPI
from lichtfeld_mcp.services.scene_service import SceneService


@pytest.mark.parametrize(
    ("method_name", "args", "kwargs", "expected_api_args", "expected_api_kwargs"),
    [
        ("open_project", ("demo_scene.lfp",), {}, ("demo_scene.lfp",), {}),
        ("save_project", (), {}, (), {}),
        ("close_project", (), {}, (), {}),
        ("get_stats", (), {}, (), {}),
        (
            "analyze_scene",
            (),
            {
                "voxel_size": 0.5,
                "min_voxel_cluster_size": 5,
                "max_splats": 10_000,
                "abort_if_above_limit": True,
            },
            (),
            {
                "voxel_size": 0.5,
                "min_voxel_cluster_size": 5,
                "max_splats": 10_000,
                "abort_if_above_limit": True,
            },
        ),
        (
            "select_by_box",
            (),
            {"min_x": -1, "min_y": -1, "min_z": 0, "max_x": 1, "max_y": 1, "max_z": 2, "mode": "add"},
            (),
            {"min_x": -1, "min_y": -1, "min_z": 0, "max_x": 1, "max_y": 1, "max_z": 2, "mode": "add"},
        ),
        ("select_by_height", (), {"z_min": 0, "z_max": 2, "mode": "replace"}, (), {"z_min": 0, "z_max": 2, "mode": "replace"}),
        (
            "select_by_color",
            (),
            {"r": 10, "g": 20, "b": 30, "tolerance": 15, "mode": "subtract"},
            (),
            {"r": 10, "g": 20, "b": 30, "tolerance": 15, "mode": "subtract"},
        ),
        (
            "crop_by_box",
            (),
            {"min_x": -1, "min_y": -1, "min_z": 0, "max_x": 1, "max_y": 1, "max_z": 2, "keep_inside": False},
            (),
            {"min_x": -1, "min_y": -1, "min_z": 0, "max_x": 1, "max_y": 1, "max_z": 2, "keep_inside": False},
        ),
        ("crop_by_height", (), {"z_min": 0, "z_max": 1, "keep_inside": False}, (), {"z_min": 0, "z_max": 1, "keep_inside": False}),
        ("delete_selection", (), {}, (), {}),
        ("optimize_for_target", ("web",), {"max_splats": 1000}, (), {"target": "web", "max_splats": 1000}),
        ("export_scene", ("out/demo.spz",), {"fmt": "spz", "target": "web"}, (), {"output_path": "out/demo.spz", "fmt": "spz", "target": "web"}),
        (
            "measure_distance",
            (),
            {"ax": 0, "ay": 0, "az": 0, "bx": 1, "by": 1, "bz": 1, "unit": "cm"},
            (),
            {"ax": 0, "ay": 0, "az": 0, "bx": 1, "by": 1, "bz": 1, "unit": "cm"},
        ),
        ("undo", (), {}, (), {}),
        ("list_history", (), {}, (), {}),
    ],
)
def test_scene_service_delegates_to_scene_api(
    method_name: str,
    args: tuple,
    kwargs: dict[str, object],
    expected_api_args: tuple,
    expected_api_kwargs: dict[str, object],
) -> None:
    scene_api = Mock(spec=SceneAPI)
    service = SceneService(scene_api)
    expected = object()

    api_method_name = "get_scene_stats" if method_name == "get_stats" else method_name
    getattr(scene_api, api_method_name).return_value = expected

    result = getattr(service, method_name)(*args, **kwargs)

    assert result is expected
    getattr(scene_api, api_method_name).assert_called_once_with(*expected_api_args, **expected_api_kwargs)
