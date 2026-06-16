from unittest.mock import Mock

from lichtfeld_mcp.schemas.common import ExportResult, MeasurementResult, OptimizationResult, ToolResult
from lichtfeld_mcp.tools import edit as edit_tools
from lichtfeld_mcp.tools import export as export_tools
from lichtfeld_mcp.tools import measure as measure_tools
from lichtfeld_mcp.tools import optimize as optimize_tools


def test_edit_tools_delegate_to_scene_service(monkeypatch):
    service = Mock()
    service.crop_by_box.return_value = ToolResult(message="Cropped by box.")
    service.crop_by_height.return_value = ToolResult(message="Cropped by height.")
    monkeypatch.setattr(edit_tools, "get_scene_service", lambda: service)

    assert edit_tools.crop_by_box(-1, -1, 0, 1, 1, 2, keep_inside=False)["message"] == "Cropped by box."
    assert edit_tools.crop_by_height(0, 2)["message"] == "Cropped by height."

    service.crop_by_box.assert_called_once_with(
        min_x=-1,
        min_y=-1,
        min_z=0,
        max_x=1,
        max_y=1,
        max_z=2,
        keep_inside=False,
    )
    service.crop_by_height.assert_called_once_with(z_min=0, z_max=2, keep_inside=True)


def test_export_optimize_and_measure_tools_delegate_to_scene_service(monkeypatch):
    service = Mock()
    service.export_scene.return_value = ExportResult(
        output_path="out/demo.spz",
        format="spz",
        message="Export simulated to out/demo.spz",
    )
    service.optimize_for_target.return_value = OptimizationResult(
        target="web",
        before_splats=1000,
        after_splats=500,
        sh_degree=2,
        estimated_vram_mb=1.2,
        applied_rules=["cap_splats"],
        message="Scene optimized for web.",
    )
    service.measure_distance.return_value = MeasurementResult(
        kind="distance",
        value=1.0,
        unit="cm",
        message="Distance: 1.0000 cm",
    )
    monkeypatch.setattr(export_tools, "get_scene_service", lambda: service)
    monkeypatch.setattr(optimize_tools, "get_scene_service", lambda: service)
    monkeypatch.setattr(measure_tools, "get_scene_service", lambda: service)

    assert export_tools.export_scene("out/demo.spz", fmt="spz", target="web")["format"] == "spz"
    assert optimize_tools.optimize_for_target("web", max_splats=500)["target"] == "web"
    assert measure_tools.measure_distance(0, 0, 0, 1, 0, 0, unit="cm")["unit"] == "cm"

    service.export_scene.assert_called_once_with(output_path="out/demo.spz", fmt="spz", target="web")
    service.optimize_for_target.assert_called_once_with(target="web", max_splats=500)
    service.measure_distance.assert_called_once_with(ax=0, ay=0, az=0, bx=1, by=0, bz=0, unit="cm")
