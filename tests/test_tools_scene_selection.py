from unittest.mock import Mock

from lichtfeld_mcp.core.scene_analysis import SceneAnalysisReport
from lichtfeld_mcp.schemas.common import (
    Box3D,
    HistoryEntry,
    ProjectInfo,
    SceneStats,
    SelectionResult,
    ToolResult,
    Vec3,
)
from lichtfeld_mcp.tools import scene as scene_tools
from lichtfeld_mcp.tools import selection as selection_tools


def test_scene_tools_delegate_to_scene_service(monkeypatch):
    service = Mock()
    service.open_project.return_value = ProjectInfo(
        path="demo_scene.lfp",
        name="demo_scene",
        splat_count=123,
        selected_count=0,
    )
    service.get_stats.return_value = SceneStats(
        project_name="demo_scene",
        project_path="demo_scene.lfp",
        splat_count=123,
        selected_count=4,
        file_size_mb=1.5,
        estimated_vram_mb=2.5,
        bounds=Box3D(min=Vec3(x=0, y=0, z=0), max=Vec3(x=1, y=1, z=1)),
        sh_degree=2,
        opacity_mean=0.5,
        density_score=0.7,
        history_length=2,
    )
    service.analyze_scene.return_value = SceneAnalysisReport(
        scene_stats={
            "scene_name": "demo_scene",
            "project_path": "demo_scene.lfp",
            "total_splats": 123,
            "analyzed_splats": 123,
            "selected_splats": 4,
            "deleted_splats": 0,
            "voxel_size": 0.25,
            "min_voxel_cluster_size": 10,
            "approximate": False,
            "sampling_stride": 1,
            "used_native_sampling": False,
            "max_splats": 25_000,
            "aborted": False,
        },
        quality_score=95,
        warnings=[],
        recommendations=["Scene is healthy."],
        analysis_time=0.1,
        results=[],
    )
    service.undo.return_value = ToolResult(message="Undo applied.")
    service.list_history.return_value = [HistoryEntry(index=0, action="open_project", details={})]
    service.save_project.return_value = ToolResult(message="saved")
    service.close_project.return_value = ToolResult(message="closed")
    monkeypatch.setattr(scene_tools, "get_scene_service", lambda: service)

    assert scene_tools.open_project("demo_scene.lfp")["name"] == "demo_scene"
    assert scene_tools.get_scene_stats()["project_name"] == "demo_scene"
    assert scene_tools.analyze_scene()["quality_score"] == 95
    assert scene_tools.undo()["message"] == "Undo applied."
    assert scene_tools.list_history()[0]["action"] == "open_project"
    assert scene_tools.save_project()["message"] == "saved"
    assert scene_tools.close_project()["message"] == "closed"

    service.open_project.assert_called_once_with("demo_scene.lfp")
    service.get_stats.assert_called_once_with()
    service.analyze_scene.assert_called_once_with(
        voxel_size=0.25,
        min_voxel_cluster_size=10,
        max_splats=25_000,
        abort_if_above_limit=False,
    )
    service.undo.assert_called_once_with()
    service.list_history.assert_called_once_with()
    service.save_project.assert_called_once_with()
    service.close_project.assert_called_once_with()


def test_selection_tools_delegate_to_scene_service(monkeypatch):
    service = Mock()
    service.select_by_box.return_value = SelectionResult(
        selected_count=10,
        selection_mode="add",
        message="Box selection applied.",
    )
    service.select_by_height.return_value = SelectionResult(
        selected_count=5,
        selection_mode="replace",
        message="Height selection applied.",
    )
    service.select_by_color.return_value = SelectionResult(
        selected_count=2,
        selection_mode="subtract",
        message="Color selection applied.",
    )
    service.delete_selection.return_value = ToolResult(message="Deleted 2 selected splats.")
    monkeypatch.setattr(selection_tools, "get_scene_service", lambda: service)

    assert selection_tools.select_by_box(-1, -1, 0, 1, 1, 2, mode="add")["selection_mode"] == "add"
    assert selection_tools.select_by_height(0, 2)["selected_count"] == 5
    assert selection_tools.select_by_color(10, 20, 30, tolerance=15, mode="subtract")["selection_mode"] == "subtract"
    assert selection_tools.delete_selection()["message"] == "Deleted 2 selected splats."

    service.select_by_box.assert_called_once_with(
        min_x=-1,
        min_y=-1,
        min_z=0,
        max_x=1,
        max_y=1,
        max_z=2,
        mode="add",
    )
    service.select_by_height.assert_called_once_with(z_min=0, z_max=2, mode="replace")
    service.select_by_color.assert_called_once_with(
        r=10,
        g=20,
        b=30,
        tolerance=15,
        mode="subtract",
    )
    service.delete_selection.assert_called_once_with()
