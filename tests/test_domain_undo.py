from lichtfeld_mcp.core.gaussian import Gaussian, GaussianId, Position3D
from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud
from lichtfeld_mcp.core.scene import Scene


def make_scene() -> Scene:
    return Scene(
        gaussian_cloud=GaussianCloud(
            gaussians=[
                Gaussian(id=GaussianId(1), position=Position3D(x=0.0, y=0.0, z=0.0)),
                Gaussian(id=GaussianId(2), position=Position3D(x=1.0, y=0.0, z=0.0)),
                Gaussian(id=GaussianId(3), position=Position3D(x=2.0, y=0.0, z=0.0)),
            ]
        )
    )


def test_delete_selected_records_restore_points_for_undo():
    scene = make_scene()
    scene.selection.select([GaussianId(1), GaussianId(3)])

    deleted = scene.edit.delete_selected()

    assert deleted == 2
    entry = scene.history.entries()[0]
    assert [restore_point.index for restore_point in entry.restore_points] == [0, 2]
    assert [restore_point.gaussian.id for restore_point in entry.restore_points] == [
        GaussianId(1),
        GaussianId(3),
    ]


def test_undo_last_restores_deleted_gaussians():
    scene = make_scene()
    scene.selection.select([GaussianId(1), GaussianId(3)])
    scene.edit.delete_selected()

    restored = scene.edit.undo_last()

    assert restored is True
    assert scene.gaussians.ids() == [GaussianId(1), GaussianId(2), GaussianId(3)]
    assert scene.gaussian_count() == 3
    assert scene.selection.is_empty() is True
    assert scene.history.is_empty() is True


def test_undo_last_returns_false_when_history_is_empty():
    scene = make_scene()

    restored = scene.edit.undo_last()

    assert restored is False
    assert scene.gaussians.ids() == [GaussianId(1), GaussianId(2), GaussianId(3)]


def test_undo_last_restores_only_latest_delete_selected_entry():
    scene = make_scene()
    scene.selection.select([GaussianId(1)])
    scene.edit.delete_selected()
    scene.selection.select([GaussianId(3)])
    scene.edit.delete_selected()

    restored = scene.edit.undo_last()

    assert restored is True
    assert scene.gaussians.ids() == [GaussianId(2), GaussianId(3)]
    assert scene.history.count() == 1
    assert scene.selection.ids() == []
