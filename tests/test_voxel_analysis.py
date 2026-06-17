import inspect

from lichtfeld_mcp.core.gaussian import Position3D
from lichtfeld_mcp.core.voxel_analysis import (
    VoxelCluster,
    analyze_voxel_clusters,
    largest_voxel_cluster,
    voxel_clusters_outside_largest,
    voxel_clusters_smaller_than,
)


def test_analyze_voxel_clusters_returns_empty_list_for_empty_positions():
    assert analyze_voxel_clusters([], voxel_size=1.0) == []
    assert largest_voxel_cluster([]) is None
    assert voxel_clusters_outside_largest([]) == []


def test_analyze_voxel_clusters_finds_single_connected_voxel_cluster():
    clusters = analyze_voxel_clusters(
        [
            (0.1, 0.1, 0.1),
            (0.2, 0.1, 0.1),
            (1.1, 0.1, 0.1),
        ],
        voxel_size=1.0,
    )

    assert len(clusters) == 1
    cluster = clusters[0]
    assert isinstance(cluster, VoxelCluster)
    assert cluster.id == 0
    assert cluster.voxel_count == 2
    assert cluster.estimated_splat_count == 3
    assert cluster.bounding_box.min == Position3D(x=0.1, y=0.1, z=0.1)
    assert cluster.bounding_box.max == Position3D(x=1.1, y=0.1, z=0.1)
    assert abs(cluster.centroid.x - ((0.1 + 0.2 + 1.1) / 3.0)) < 1e-9


def test_analyze_voxel_clusters_finds_multiple_separated_clusters():
    clusters = analyze_voxel_clusters(
        [
            (0.0, 0.0, 0.0),
            (0.2, 0.0, 0.0),
            (5.0, 5.0, 5.0),
            (5.2, 5.0, 5.0),
            (10.0, 0.0, 0.0),
        ],
        voxel_size=1.0,
    )

    assert [cluster.estimated_splat_count for cluster in clusters] == [2, 2, 1]
    assert [cluster.voxel_count for cluster in clusters] == [1, 1, 1]


def test_analyze_voxel_clusters_can_filter_small_voxel_components():
    all_clusters = analyze_voxel_clusters(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (8.0, 8.0, 8.0),
        ],
        voxel_size=1.0,
        min_voxel_cluster_size=1,
    )
    filtered_clusters = analyze_voxel_clusters(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (8.0, 8.0, 8.0),
        ],
        voxel_size=1.0,
        min_voxel_cluster_size=2,
    )

    assert [cluster.voxel_count for cluster in all_clusters] == [3, 1]
    assert [cluster.voxel_count for cluster in filtered_clusters] == [3]


def test_voxel_cluster_helpers_work():
    clusters = analyze_voxel_clusters(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (5.0, 5.0, 5.0),
            (6.0, 5.0, 5.0),
            (9.0, 9.0, 9.0),
        ],
        voxel_size=1.0,
    )

    largest = largest_voxel_cluster(clusters)
    smaller = voxel_clusters_smaller_than(clusters, 3)
    outside = voxel_clusters_outside_largest(clusters)

    assert largest is not None
    assert largest.voxel_count == 3
    assert [cluster.voxel_count for cluster in smaller] == [2, 1]
    assert [cluster.voxel_count for cluster in outside] == [2, 1]


def test_voxel_clusters_smaller_than_handles_non_positive_threshold():
    cluster = VoxelCluster(
        id=0,
        voxel_count=1,
        estimated_splat_count=2,
        bounding_box=None,  # type: ignore[arg-type]
        centroid=Position3D(x=0.0, y=0.0, z=0.0),
    )
    assert voxel_clusters_smaller_than([cluster], 0) == []


def test_voxel_analysis_module_has_no_runtime_layer_dependencies():
    import lichtfeld_mcp.core.voxel_analysis as voxel_analysis_module

    source = inspect.getsource(voxel_analysis_module)
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
