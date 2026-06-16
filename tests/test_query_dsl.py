import inspect

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
from lichtfeld_mcp.core.query import Color, Density, Height, Opacity, Scale
from lichtfeld_mcp.errors import InvalidParameterError


def make_gaussian(
    raw_id: int,
    *,
    z: float,
    opacity: float = 1.0,
    color: RGBColor | None = None,
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    density: float | None = None,
) -> Gaussian:
    metadata: dict[str, object] = {}
    if density is not None:
        metadata["density"] = density
    return Gaussian(
        id=GaussianId(raw_id),
        position=Position3D(x=float(raw_id), y=0.0, z=z),
        rotation=Quaternion(),
        scale=Scale3D(*scale),
        opacity=opacity,
        color=color or RGBColor(255, 255, 255),
        spherical_harmonics=SphericalHarmonics(),
        metadata=metadata,
    )


def make_cloud() -> GaussianCloud:
    return GaussianCloud(
        gaussians=[
            make_gaussian(
                1,
                z=0.5,
                opacity=0.2,
                color=RGBColor(100, 100, 100),
                scale=(1.0, 1.0, 1.0),
                density=0.1,
            ),
            make_gaussian(
                2,
                z=1.5,
                opacity=0.5,
                color=RGBColor(110, 105, 95),
                scale=(2.0, 2.0, 2.0),
                density=0.4,
            ),
            make_gaussian(
                3,
                z=3.0,
                opacity=0.8,
                color=RGBColor(200, 140, 20),
                scale=(3.0, 3.0, 3.0),
                density=0.9,
            ),
        ]
    )


def test_query_dsl_supports_comparison_operators():
    cloud = make_cloud()

    assert cloud.query().where(Height > 2).ids() == [GaussianId(3)]
    assert cloud.query().where(Height >= 1.5).ids() == [GaussianId(2), GaussianId(3)]
    assert cloud.query().where(Height < 1.0).ids() == [GaussianId(1)]
    assert cloud.query().where(Height <= 1.5).ids() == [GaussianId(1), GaussianId(2)]


def test_query_dsl_supports_between_and_multiple_where():
    cloud = make_cloud()

    query = cloud.query().where(Height.between(2.0, 1.0)).where(Opacity > 0.4)

    assert query.count() == 1
    assert query.ids() == [GaussianId(2)]


def test_query_dsl_supports_logical_and_or_not():
    cloud = make_cloud()

    and_ids = cloud.query().where((Height > 2.0) & (Opacity > 0.5)).ids()
    or_ids = cloud.query().where((Height > 2.0) | Color.similar((100, 100, 100))).ids()
    not_ids = cloud.query().where(~Color.similar((100, 100, 100))).ids()

    assert and_ids == [GaussianId(3)]
    assert or_ids == [GaussianId(1), GaussianId(3)]
    assert not_ids == [GaussianId(2), GaussianId(3)]


def test_query_dsl_supports_first_count_ids_and_all():
    cloud = make_cloud()

    query = cloud.query().filter(Opacity.between(0.2, 0.8))

    assert query.count() == 3
    assert query.ids() == [GaussianId(1), GaussianId(2), GaussianId(3)]
    assert query.first() == cloud.get(GaussianId(1))
    assert len(query.all()) == 3


def test_query_dsl_returns_empty_results_when_nothing_matches():
    cloud = make_cloud()
    query = cloud.query().where((Height > 10.0) & (Opacity > 0.9))

    assert query.count() == 0
    assert query.ids() == []
    assert query.first() is None
    assert query.all() == []


def test_query_dsl_supports_color_tolerance_and_acceptance_examples():
    cloud = make_cloud()

    count = (
        cloud.query()
        .where(Height.between(1, 2))
        .where(Opacity > 0.4)
        .count()
    )
    ids = (
        cloud.query()
        .where((Height > 2) & Color.similar((200, 140, 20), tolerance=10))
        .ids()
    )

    assert count == 1
    assert ids == [GaussianId(3)]


def test_query_dsl_supports_scale_and_density_predicates():
    cloud = make_cloud()

    scale_ids = cloud.query().where(Scale.between(1.5, 2.5)).ids()
    density_ids = cloud.query().where(Density.between(0.3, 1.0)).ids()

    assert scale_ids == [GaussianId(2)]
    assert density_ids == [GaussianId(2), GaussianId(3)]


def test_query_modules_do_not_import_runtime_layers():
    from lichtfeld_mcp.core.query import predicates, expressions, query_builder

    modules = [predicates, expressions, query_builder]
    forbidden_tokens = [
        "lichtfeld_mcp.tools",
        "lichtfeld_mcp.services",
        "lichtfeld_mcp.adapters",
        "import mcp",
        "from mcp",
        "SceneService",
        "Lichtfeld",
    ]

    for module in modules:
        source = inspect.getsource(module)
        for token in forbidden_tokens:
            assert token not in source


def test_query_dsl_rejects_invalid_opacity_bounds():
    cloud = make_cloud()

    with pytest.raises(InvalidParameterError, match="min_opacity must be between 0.0 and 1.0"):
        cloud.query().where(Opacity.between(-0.1, 0.5)).count()
