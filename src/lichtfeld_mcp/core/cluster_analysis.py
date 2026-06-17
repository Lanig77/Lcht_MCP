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
    positions = [gaussian.position for gaussian in gaussians]
    grid = _build_spatial_grid(positions, cell_size)
    visited = [False] * len(gaussians)
    clusters: list[Cluster] = []
    cluster_id = 0

    for start_index, gaussian in enumerate(gaussians):
        if visited[start_index]:
            continue
        component_indices = _collect_component(
            start_index=start_index,
            positions=positions,
            grid=grid,
            visited=visited,
            cell_size=cell_size,
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
    positions: list[Position3D],
    cell_size: float,
) -> dict[tuple[int, int, int], list[int]]:
    grid: dict[tuple[int, int, int], list[int]] = {}
    for index, position in enumerate(positions):
        key = _cell_key(position, cell_size)
        grid.setdefault(key, []).append(index)
    return grid


def _collect_component(
    *,
    start_index: int,
    positions: list[Position3D],
    grid: dict[tuple[int, int, int], list[int]],
    visited: list[bool],
    cell_size: float,
    threshold_squared: float,
) -> list[int]:
    component_indices: list[int] = []
    queue: deque[int] = deque([start_index])
    visited[start_index] = True

    while queue:
        current_index = queue.popleft()
        component_indices.append(current_index)
        current_position = positions[current_index]
        cell_x, cell_y, cell_z = _cell_key(current_position, cell_size)
        for neighbor_x in range(cell_x - 1, cell_x + 2):
            for neighbor_y in range(cell_y - 1, cell_y + 2):
                for neighbor_z in range(cell_z - 1, cell_z + 2):
                    for neighbor_index in grid.get((neighbor_x, neighbor_y, neighbor_z), []):
                        if visited[neighbor_index]:
                            continue
                        if _distance_squared(
                            current_position,
                            positions[neighbor_index],
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
    cluster_gaussians = [gaussians[index] for index in component_indices]
    min_x = min(gaussian.position.x for gaussian in cluster_gaussians)
    min_y = min(gaussian.position.y for gaussian in cluster_gaussians)
    min_z = min(gaussian.position.z for gaussian in cluster_gaussians)
    max_x = max(gaussian.position.x for gaussian in cluster_gaussians)
    max_y = max(gaussian.position.y for gaussian in cluster_gaussians)
    max_z = max(gaussian.position.z for gaussian in cluster_gaussians)
    count = len(cluster_gaussians)
    centroid = Position3D(
        x=sum(gaussian.position.x for gaussian in cluster_gaussians) / count,
        y=sum(gaussian.position.y for gaussian in cluster_gaussians) / count,
        z=sum(gaussian.position.z for gaussian in cluster_gaussians) / count,
    )
    return Cluster(
        id=cluster_id,
        gaussian_ids=tuple(gaussian.id for gaussian in cluster_gaussians),
        count=count,
        bounding_box=BoundingBox(
            min=Position3D(x=min_x, y=min_y, z=min_z),
            max=Position3D(x=max_x, y=max_y, z=max_z),
        ),
        centroid=centroid,
    )


def _cell_key(position: Position3D, cell_size: float) -> tuple[int, int, int]:
    return (
        math.floor(position.x / cell_size),
        math.floor(position.y / cell_size),
        math.floor(position.z / cell_size),
    )


def _distance_squared(a: Position3D, b: Position3D) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    dz = a.z - b.z
    return dx * dx + dy * dy + dz * dz


__all__ = [
    "Cluster",
    "analyze_clusters",
    "clusters_outside_largest",
    "clusters_smaller_than",
    "largest_cluster",
]
