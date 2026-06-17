import inspect

from lichtfeld_mcp.core.cluster_analysis import (
    Cluster,
    analyze_clusters,
    clusters_outside_largest,
    clusters_smaller_than,
    largest_cluster,
)
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


def make_gaussian(raw_id: int, *, x: float, y: float, z: float) -> Gaussian:
    return Gaussian(
        id=GaussianId(raw_id),
        position=Position3D(x=x, y=y, z=z),
        rotation=Quaternion(),
        scale=Scale3D(1.0, 1.0, 1.0),
        opacity=1.0,
        color=RGBColor(255, 255, 255),
        spherical_harmonics=SphericalHarmonics(),
    )


def test_analyze_clusters_returns_empty_list_for_empty_cloud():
    assert analyze_clusters(GaussianCloud(), distance_threshold=1.0) == []
    assert largest_cluster([]) is None
    assert clusters_outside_largest([]) == []


def test_analyze_clusters_finds_single_cluster():
    cloud = GaussianCloud(
        gaussians=[
            make_gaussian(1, x=0.0, y=0.0, z=0.0),
            make_gaussian(2, x=0.4, y=0.0, z=0.0),
            make_gaussian(3, x=0.8, y=0.0, z=0.0),
        ]
    )

    clusters = analyze_clusters(cloud, distance_threshold=0.5)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert isinstance(cluster, Cluster)
    assert cluster.id == 0
    assert cluster.gaussian_ids == (GaussianId(1), GaussianId(2), GaussianId(3))
    assert cluster.count == 3
    assert cluster.bounding_box.min == Position3D(x=0.0, y=0.0, z=0.0)
    assert cluster.bounding_box.max == Position3D(x=0.8, y=0.0, z=0.0)
    assert abs(cluster.centroid.x - 0.4) < 1e-9
    assert abs(cluster.centroid.y - 0.0) < 1e-9
    assert abs(cluster.centroid.z - 0.0) < 1e-9


def test_analyze_clusters_finds_multiple_separated_clusters():
    cloud = GaussianCloud(
        gaussians=[
            make_gaussian(1, x=0.0, y=0.0, z=0.0),
            make_gaussian(2, x=0.3, y=0.0, z=0.0),
            make_gaussian(3, x=5.0, y=5.0, z=5.0),
            make_gaussian(4, x=5.2, y=5.0, z=5.0),
            make_gaussian(5, x=10.0, y=0.0, z=0.0),
        ]
    )

    clusters = analyze_clusters(cloud, distance_threshold=0.5)

    assert [cluster.count for cluster in clusters] == [2, 2, 1]
    assert [tuple(gaussian_id.value for gaussian_id in cluster.gaussian_ids) for cluster in clusters] == [
        (1, 2),
        (3, 4),
        (5,),
    ]


def test_analyze_clusters_can_filter_out_tiny_floating_clusters():
    cloud = GaussianCloud(
        gaussians=[
            make_gaussian(1, x=0.0, y=0.0, z=0.0),
            make_gaussian(2, x=0.2, y=0.0, z=0.0),
            make_gaussian(3, x=0.4, y=0.0, z=0.0),
            make_gaussian(4, x=8.0, y=8.0, z=8.0),
        ]
    )

    all_clusters = analyze_clusters(cloud, distance_threshold=0.3)
    filtered_clusters = analyze_clusters(cloud, distance_threshold=0.3, min_cluster_size=2)

    assert [cluster.count for cluster in all_clusters] == [3, 1]
    assert [cluster.count for cluster in filtered_clusters] == [3]


def test_largest_cluster_and_outside_helpers_work():
    cloud = GaussianCloud(
        gaussians=[
            make_gaussian(1, x=0.0, y=0.0, z=0.0),
            make_gaussian(2, x=0.3, y=0.0, z=0.0),
            make_gaussian(3, x=0.6, y=0.0, z=0.0),
            make_gaussian(4, x=5.0, y=5.0, z=5.0),
            make_gaussian(5, x=5.2, y=5.0, z=5.0),
            make_gaussian(6, x=9.0, y=9.0, z=9.0),
        ]
    )

    clusters = analyze_clusters(cloud, distance_threshold=0.5)
    largest = largest_cluster(clusters)
    smaller = clusters_smaller_than(clusters, 3)
    outside = clusters_outside_largest(clusters)

    assert largest is not None
    assert largest.count == 3
    assert tuple(gaussian_id.value for gaussian_id in largest.gaussian_ids) == (1, 2, 3)
    assert [cluster.count for cluster in smaller] == [2, 1]
    assert [cluster.count for cluster in outside] == [2, 1]


def test_clusters_smaller_than_handles_non_positive_threshold():
    cluster = Cluster(
        id=0,
        gaussian_ids=(GaussianId(1),),
        count=1,
        bounding_box=None,  # type: ignore[arg-type]
        centroid=Position3D(x=0.0, y=0.0, z=0.0),
    )
    assert clusters_smaller_than([cluster], 0) == []


def test_cluster_analysis_module_has_no_runtime_layer_dependencies():
    import lichtfeld_mcp.core.cluster_analysis as cluster_analysis_module

    source = inspect.getsource(cluster_analysis_module)
    forbidden_tokens = [
        "lichtfeld_mcp.tools",
        "lichtfeld_mcp.services",
        "lichtfeld_mcp.adapters",
        "import mcp",
        "from mcp",
        "LichtFeld",
    ]

    for token in forbidden_tokens:
        assert token not in source
