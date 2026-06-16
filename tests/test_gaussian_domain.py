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
from lichtfeld_mcp.core.gaussian_query import GaussianQuery
from lichtfeld_mcp.errors import InvalidParameterError


def make_gaussian(
    raw_id: int,
    *,
    x: float,
    y: float,
    z: float,
    opacity: float = 1.0,
    color: RGBColor | None = None,
) -> Gaussian:
    return Gaussian(
        id=GaussianId(raw_id),
        position=Position3D(x=x, y=y, z=z),
        rotation=Quaternion(),
        scale=Scale3D(1.0, 1.0, 1.0),
        opacity=opacity,
        color=color or RGBColor(255, 255, 255),
        spherical_harmonics=SphericalHarmonics(),
    )


def test_gaussian_id_rejects_negative_values():
    with pytest.raises(InvalidParameterError, match="GaussianId must be non-negative"):
        GaussianId(-1)


def test_scale3d_rejects_non_positive_values():
    with pytest.raises(InvalidParameterError, match="Scale3D.x must be strictly positive"):
        Scale3D(0.0, 1.0, 1.0)

    with pytest.raises(InvalidParameterError, match="Scale3D.z must be strictly positive"):
        Scale3D(1.0, 1.0, -1.0)


def test_rgb_color_rejects_invalid_channels():
    with pytest.raises(InvalidParameterError, match="g must be between 0 and 255"):
        RGBColor(0, 300, 0)


def test_gaussian_rejects_invalid_opacity():
    with pytest.raises(InvalidParameterError, match="Gaussian.opacity must be between 0.0 and 1.0"):
        make_gaussian(1, x=0, y=0, z=0, opacity=1.5)


def test_gaussian_cloud_count_ids_get_and_is_empty():
    cloud = GaussianCloud()
    assert cloud.is_empty() is True
    assert cloud.count() == 0
    assert cloud.ids() == []

    gaussian = make_gaussian(1, x=0, y=0, z=0)
    cloud.add(gaussian)

    assert cloud.is_empty() is False
    assert cloud.count() == 1
    assert cloud.ids() == [GaussianId(1)]
    assert cloud.get(GaussianId(1)) == gaussian
    assert cloud.get(GaussianId(999)) is None


def test_gaussian_cloud_rejects_duplicate_ids():
    gaussian = make_gaussian(1, x=0, y=0, z=0)
    with pytest.raises(InvalidParameterError, match="Duplicate GaussianId 1"):
        GaussianCloud(gaussians=[gaussian, gaussian])


def test_gaussian_cloud_bounding_box_for_empty_and_multiple_gaussians():
    assert GaussianCloud().bounding_box() is None

    cloud = GaussianCloud(
        gaussians=[
            make_gaussian(1, x=-1.0, y=2.0, z=3.0),
            make_gaussian(2, x=4.0, y=-5.0, z=0.5),
            make_gaussian(3, x=2.0, y=1.0, z=7.0),
        ]
    )
    box = cloud.bounding_box()

    assert box is not None
    assert box.min == Position3D(x=-1.0, y=-5.0, z=0.5)
    assert box.max == Position3D(x=4.0, y=2.0, z=7.0)


def test_gaussian_query_by_height_and_opacity():
    cloud = GaussianCloud(
        gaussians=[
            make_gaussian(1, x=0, y=0, z=0.0, opacity=0.2),
            make_gaussian(2, x=0, y=0, z=2.0, opacity=0.7),
            make_gaussian(3, x=0, y=0, z=4.0, opacity=0.9),
        ]
    )

    assert cloud.query().by_height(min_z=3.0, max_z=1.0).ids() == [GaussianId(2)]
    assert cloud.query().by_opacity(min_opacity=0.5, max_opacity=1.0).ids() == [GaussianId(2), GaussianId(3)]


def test_gaussian_query_by_color_with_tolerance():
    cloud = GaussianCloud(
        gaussians=[
            make_gaussian(1, x=0, y=0, z=0, color=RGBColor(100, 100, 100)),
            make_gaussian(2, x=0, y=0, z=1, color=RGBColor(110, 105, 95)),
            make_gaussian(3, x=0, y=0, z=2, color=RGBColor(200, 200, 200)),
        ]
    )

    ids = cloud.query().by_color(RGBColor(100, 100, 100), tolerance=10).ids()
    assert ids == [GaussianId(1), GaussianId(2)]


def test_gaussian_query_is_immutable_style():
    cloud = GaussianCloud(
        gaussians=[
            make_gaussian(1, x=0, y=0, z=0.0, opacity=0.2),
            make_gaussian(2, x=0, y=0, z=2.0, opacity=0.7),
        ]
    )

    original = cloud.query()
    filtered = original.by_height(min_z=1.0)

    assert isinstance(original, GaussianQuery)
    assert original.count() == 2
    assert filtered.count() == 1
    assert original is not filtered


def test_gaussian_query_validates_opacity_ranges_and_tolerance():
    query = GaussianCloud(gaussians=[make_gaussian(1, x=0, y=0, z=0.0)]).query()

    with pytest.raises(InvalidParameterError, match="min_opacity must be between 0.0 and 1.0"):
        query.by_opacity(min_opacity=2.0)

    with pytest.raises(InvalidParameterError, match="tolerance must be between 0 and 255"):
        query.by_color(RGBColor(255, 255, 255), tolerance=-1)


def test_gaussian_domain_modules_do_not_import_runtime_layers():
    modules = [
        inspect.getmodule(Gaussian),
        inspect.getmodule(GaussianCloud),
        inspect.getmodule(GaussianQuery),
    ]

    forbidden_tokens = [
        "lichtfeld_mcp.tools",
        "lichtfeld_mcp.services",
        "lichtfeld_mcp.adapters",
        "import mcp",
        "from mcp",
        "SceneService",
        "SceneAPI",
        "Lichtfeld",
    ]

    for module in modules:
        source = inspect.getsource(module)
        for token in forbidden_tokens:
            assert token not in source
