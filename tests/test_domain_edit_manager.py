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


def test_delete_selected_removes_gaussians_from_cloud():
    scene = make_scene()
    scene.selection.select([GaussianId(1), GaussianId(3)])

    deleted = scene.edit.delete_selected()

    assert deleted == 2
    assert scene.gaussians.ids() == [GaussianId(2)]
    assert scene.gaussian_count() == 1


def test_delete_selected_clears_selection():
    scene = make_scene()
    scene.selection.select([GaussianId(2)])

    scene.edit.delete_selected()

    assert scene.selection.ids() == []
    assert scene.selection.is_empty() is True


def test_delete_selected_returns_zero_for_empty_selection():
    scene = make_scene()

    deleted = scene.edit.delete_selected()

    assert deleted == 0
    assert scene.gaussian_count() == 3


def test_delete_selected_ignores_missing_ids_and_returns_removed_count():
    scene = make_scene()
    scene.selection.select([GaussianId(2), GaussianId(999)])

    deleted = scene.edit.delete_selected()

    assert deleted == 1
    assert scene.gaussians.ids() == [GaussianId(1), GaussianId(3)]
