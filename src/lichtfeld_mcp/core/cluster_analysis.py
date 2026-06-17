from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

from lichtfeld_mcp.core.gaussian import BoundingBox, GaussianId, Position3D
from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud
from lichtfeld_mcp.errors import InvalidParameterError


@dataclass(frozen=True, slots=True)
class Cluster:
    id: int
    gaussian_ids: tuple[GaussianId, ...]
    count: int
    bounding_box: BoundingBox
    centroid: Position3D


def analyze_clusters(
    cloud: GaussianCloud,
    distance_threshold: float,
    min_cluster_size: int = 1,
) -> list[Cluster]:
    if distance_threshold <= 0.0:
        raise InvalidParameterError("distance_threshold must be strictly positive.")
    if min_cluster_size < 1:
        raise InvalidParameterError("min_cluster_size must be at least 1.")
    if cloud.is_empty():
        return []

    cell_size = distance_threshold
    threshold_squared = distance_threshold * distance_threshold
    gaussians = cloud.gaussians
    coordinates = [
        (gaussian.position.x, gaussian.position.y, gaussian.position.z)
        for gaussian in gaussians
    ]
    cell_keys = [_cell_key_from_coordinates(x, y, z, cell_size) for x, y, z in coordinates]
    grid = _build_spatial_grid(cell_keys)
    visited = [False] * len(gaussians)
    clusters: list[Cluster] = []
    cluster_id = 0

    for start_index in range(len(gaussians)):
        if visited[start_index]:
            continue
        component_indices = _collect_component(
            start_index=start_index,
            coordinates=coordinates,
            cell_keys=cell_keys,
            grid=grid,
            visited=visited,
            threshold_squared=threshold_squared,
        )
        if len(component_indices) < min_cluster_size:
            continue
        cluster = _build_cluster(
            cluster_id=cluster_id,
            gaussians=gaussians,
            component_indices=component_indices,
        )
        clusters.append(cluster)
        cluster_id += 1
    return clusters


def largest_cluster(clusters: list[Cluster]) -> Cluster | None:
    if not clusters:
        return None
    return max(clusters, key=lambda cluster: (cluster.count, -cluster.id))


def clusters_smaller_than(clusters: list[Cluster], size: int) -> list[Cluster]:
    if size <= 0:
        return []
    return [cluster for cluster in clusters if cluster.count < size]


def clusters_outside_largest(clusters: list[Cluster]) -> list[Cluster]:
    largest = largest_cluster(clusters)
    if largest is None:
        return []
    return [cluster for cluster in clusters if cluster.id != largest.id]


def _build_spatial_grid(
    cell_keys: list[tuple[int, int, int]],
) -> dict[tuple[int, int, int], list[int]]:
    grid: dict[tuple[int, int, int], list[int]] = {}
    for index, key in enumerate(cell_keys):
        grid.setdefault(key, []).append(index)
    return grid


def _collect_component(
    *,
    start_index: int,
    coordinates: list[tuple[float, float, float]],
    cell_keys: list[tuple[int, int, int]],
    grid: dict[tuple[int, int, int], list[int]],
    visited: list[bool],
    threshold_squared: float,
) -> list[int]:
    component_indices: list[int] = []
    queue: deque[int] = deque([start_index])
    visited[start_index] = True
    grid_get = grid.get

    while queue:
        current_index = queue.popleft()
        component_indices.append(current_index)
        current_coordinates = coordinates[current_index]
        cell_x, cell_y, cell_z = cell_keys[current_index]
        for neighbor_x in range(cell_x - 1, cell_x + 2):
            for neighbor_y in range(cell_y - 1, cell_y + 2):
                for neighbor_z in range(cell_z - 1, cell_z + 2):
                    for neighbor_index in grid_get((neighbor_x, neighbor_y, neighbor_z), ()):
                        if visited[neighbor_index]:
                            continue
                        if _distance_squared(
                            current_coordinates,
                            coordinates[neighbor_index],
                        ) > threshold_squared:
                            continue
                        visited[neighbor_index] = True
                        queue.append(neighbor_index)
    return component_indices


def _build_cluster(
    *,
    cluster_id: int,
    gaussians,
    component_indices: list[int],
) -> Cluster:
    first_gaussian = gaussians[component_indices[0]]
    min_x = max_x = first_gaussian.position.x
    min_y = max_y = first_gaussian.position.y
    min_z = max_z = first_gaussian.position.z
    sum_x = 0.0
    sum_y = 0.0
    sum_z = 0.0
    gaussian_ids: list[GaussianId] = []
    for index in component_indices:
        gaussian = gaussians[index]
        position = gaussian.position
        x = position.x
        y = position.y
        z = position.z
        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y
        if z < min_z:
            min_z = z
        if z > max_z:
            max_z = z
        sum_x += x
        sum_y += y
        sum_z += z
        gaussian_ids.append(gaussian.id)
    count = len(component_indices)
    centroid = Position3D(
        x=sum_x / count,
        y=sum_y / count,
        z=sum_z / count,
    )
    return Cluster(
        id=cluster_id,
        gaussian_ids=tuple(gaussian_ids),
        count=count,
        bounding_box=BoundingBox(
            min=Position3D(x=min_x, y=min_y, z=min_z),
            max=Position3D(x=max_x, y=max_y, z=max_z),
        ),
        centroid=centroid,
    )


def _cell_key(position: Position3D, cell_size: float) -> tuple[int, int, int]:
    return _cell_key_from_coordinates(position.x, position.y, position.z, cell_size)


def _cell_key_from_coordinates(
    x: float,
    y: float,
    z: float,
    cell_size: float,
) -> tuple[int, int, int]:
    return (
        math.floor(x / cell_size),
        math.floor(y / cell_size),
        math.floor(z / cell_size),
    )


def _distance_squared(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx * dx + dy * dy + dz * dz


__all__ = [
    "Cluster",
    "analyze_clusters",
    "clusters_outside_largest",
    "clusters_smaller_than",
    "largest_cluster",
]
