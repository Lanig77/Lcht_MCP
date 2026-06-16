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


def test_delete_selected_records_history_entry_when_gaussians_are_removed():
    scene = make_scene()
    scene.selection.select([GaussianId(1), GaussianId(3)])

    deleted = scene.edit.delete_selected()

    assert deleted == 2
    assert scene.history.count() == 1
    entry = scene.history.entries()[0]
    assert entry.action == "delete_selected"
    assert entry.affected_ids == (GaussianId(1), GaussianId(3))
    assert entry.details["deleted_count"] == 2


def test_delete_selected_does_not_record_history_when_selection_is_empty():
    scene = make_scene()

    deleted = scene.edit.delete_selected()

    assert deleted == 0
    assert scene.history.is_empty() is True


def test_history_entry_contains_only_deleted_gaussian_ids():
    scene = make_scene()
    scene.selection.select([GaussianId(2), GaussianId(999)])

    deleted = scene.edit.delete_selected()

    assert deleted == 1
    entry = scene.history.entries()[0]
    assert entry.affected_ids == (GaussianId(2),)
