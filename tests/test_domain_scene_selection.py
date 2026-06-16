from lichtfeld_mcp.core.gaussian import Gaussian, GaussianId, Position3D, RGBColor
from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud
from lichtfeld_mcp.core.scene import Scene


def make_scene() -> Scene:
    return Scene(
        gaussian_cloud=GaussianCloud(
            gaussians=[
                Gaussian(
                    id=GaussianId(1),
                    position=Position3D(x=0.0, y=0.0, z=0.0),
                    opacity=0.2,
                    color=RGBColor(100, 100, 100),
                ),
                Gaussian(
                    id=GaussianId(2),
                    position=Position3D(x=0.0, y=0.0, z=2.0),
                    opacity=0.7,
                    color=RGBColor(110, 105, 95),
                ),
                Gaussian(
                    id=GaussianId(3),
                    position=Position3D(x=0.0, y=0.0, z=4.0),
                    opacity=0.9,
                    color=RGBColor(200, 200, 200),
                ),
            ]
        )
    )


def test_scene_can_select_query_results():
    scene = make_scene()

    scene.select_query(scene.gaussians.query().by_height(min_z=1.0, max_z=3.0))

    assert scene.selection.ids() == [GaussianId(2)]
    assert scene.selection.count() == 1


def test_scene_select_by_height_selects_matching_gaussian_ids():
    scene = make_scene()

    scene.select_by_height(min_z=3.0, max_z=1.0)

    assert scene.selection.ids() == [GaussianId(2)]


def test_scene_select_by_opacity_selects_matching_gaussian_ids():
    scene = make_scene()

    scene.select_by_opacity(min_opacity=0.5, max_opacity=1.0)

    assert scene.selection.ids() == [GaussianId(2), GaussianId(3)]


def test_scene_select_by_color_selects_matching_gaussian_ids():
    scene = make_scene()

    scene.select_by_color(RGBColor(100, 100, 100), tolerance=10)

    assert scene.selection.ids() == [GaussianId(1), GaussianId(2)]


def test_empty_query_produces_empty_selection():
    scene = make_scene()
    scene.selection.select([GaussianId(1), GaussianId(2)])

    scene.select_query(scene.gaussians.query().by_height(min_z=10.0))

    assert scene.selection.ids() == []
    assert scene.selection.is_empty() is True
