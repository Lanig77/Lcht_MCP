from lichtfeld_mcp.adapters.mock import MockLichtfeldAdapter
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
