import pytest

from lichtfeld_mcp.core.gaussian import (
    Gaussian,
    GaussianId,
    Position3D,
    Quaternion,
    RGBColor,
    Scale3D,
    SphericalHarmonics,
)
from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud
from lichtfeld_mcp.core.query import Color, Height, Opacity
from lichtfeld_mcp.core.scene import Scene
from lichtfeld_mcp.errors import InvalidParameterError


def make_gaussian(
    raw_id: int,
    *,
    x: float,
    z: float,
    opacity: float,
    color: RGBColor,
) -> Gaussian:
    return Gaussian(
        id=GaussianId(raw_id),
        position=Position3D(x=x, y=0.0, z=z),
        rotation=Quaternion(),
        scale=Scale3D(1.0, 1.0, 1.0),
        opacity=opacity,
        color=color,
        spherical_harmonics=SphericalHarmonics(),
        metadata={},
    )


def make_scene() -> Scene:
    return Scene(
        gaussian_cloud=GaussianCloud(
            gaussians=[
                make_gaussian(
                    1,
                    x=0.0,
                    z=0.5,
                    opacity=0.05,
                    color=RGBColor(120, 120, 120),
                ),
                make_gaussian(
                    2,
                    x=1.0,
                    z=1.5,
                    opacity=0.4,
                    color=RGBColor(180, 120, 30),
                ),
                make_gaussian(
                    3,
                    x=2.0,
                    z=3.0,
                    opacity=0.8,
                    color=RGBColor(190, 125, 35),
                ),
            ]
        )
    )


def test_query_delete_executes_and_undo_restores_deleted_gaussians():
    scene = make_scene()

    affected = scene.gaussians.query().where(Opacity < 0.1).delete().execute()

    assert affected == 1
    assert scene.gaussians.ids() == [GaussianId(2), GaussianId(3)]
    entry = scene.history.peek()
    assert entry is not None
    assert entry.action == "delete"
    assert entry.affected_ids == (GaussianId(1),)
    assert entry.after_state == ()

    restored = scene.edit.undo_last()

    assert restored is True
    assert scene.gaussians.ids() == [GaussianId(1), GaussianId(2), GaussianId(3)]
    assert scene.selection.ids() == []


def test_query_translate_updates_positions_and_records_history():
    scene = make_scene()

    affected = scene.gaussians.query().where(Height > 2).translate(0.0, 0.0, 1.0).execute()

    assert affected == 1
    assert scene.gaussians.get(GaussianId(3)).position.z == 4.0
    entry = scene.history.peek()
    assert entry is not None
    assert entry.action == "translate"
    assert entry.before_state[0].gaussian.position.z == 3.0
    assert entry.after_state[0].gaussian.position.z == 4.0

    restored = scene.edit.undo_last()

    assert restored is True
    assert scene.gaussians.get(GaussianId(3)).position.z == 3.0


def test_query_set_opacity_updates_values_and_undo_restores_previous_opacity():
    scene = make_scene()

    affected = (
        scene.gaussians.query()
        .where(Color.similar((180, 120, 30), tolerance=15))
        .set_opacity(0.25)
        .execute()
    )

    assert affected == 2
    assert scene.gaussians.get(GaussianId(2)).opacity == 0.25
    assert scene.gaussians.get(GaussianId(3)).opacity == 0.25
    entry = scene.history.peek()
    assert entry is not None
    assert entry.action == "set_opacity"
    assert entry.before_state[0].gaussian.opacity == 0.4
    assert entry.after_state[0].gaussian.opacity == 0.25

    restored = scene.edit.undo_last()

    assert restored is True
    assert scene.gaussians.get(GaussianId(2)).opacity == 0.4
    assert scene.gaussians.get(GaussianId(3)).opacity == 0.8


def test_query_multiple_actions_execute_as_one_immutable_pipeline():
    scene = make_scene()
    base_query = scene.gaussians.query().where(Height > 1)
    translated_query = base_query.translate(1.0, 0.0, 2.0)
    final_query = translated_query.set_opacity(0.4)

    assert base_query.actions == ()
    assert len(translated_query.actions) == 1
    assert len(final_query.actions) == 2

    affected = final_query.execute()

    assert affected == 2
    assert scene.gaussians.get(GaussianId(2)).position.x == 2.0
    assert scene.gaussians.get(GaussianId(2)).position.z == 3.5
    assert scene.gaussians.get(GaussianId(2)).opacity == 0.4
    assert scene.gaussians.get(GaussianId(3)).position.x == 3.0
    assert scene.gaussians.get(GaussianId(3)).position.z == 5.0
    assert scene.gaussians.get(GaussianId(3)).opacity == 0.4
    entry = scene.history.peek()
    assert entry is not None
    assert entry.action == "query_pipeline"
    assert entry.details["actions"] == ("translate", "set_opacity")

    restored = scene.edit.undo_last()

    assert restored is True
    assert scene.gaussians.get(GaussianId(2)).position.x == 1.0
    assert scene.gaussians.get(GaussianId(2)).position.z == 1.5
    assert scene.gaussians.get(GaussianId(2)).opacity == 0.4
    assert scene.gaussians.get(GaussianId(3)).position.x == 2.0
    assert scene.gaussians.get(GaussianId(3)).position.z == 3.0
    assert scene.gaussians.get(GaussianId(3)).opacity == 0.8


def test_query_set_opacity_rejects_invalid_values():
    scene = make_scene()

    with pytest.raises(InvalidParameterError, match="opacity must be between 0.0 and 1.0"):
        scene.gaussians.query().where(Height > 0).set_opacity(1.2)


def test_query_execute_without_matches_does_not_record_history():
    scene = make_scene()

    affected = scene.gaussians.query().where(Height > 10).delete().execute()

    assert affected == 0
    assert scene.history.is_empty() is True
