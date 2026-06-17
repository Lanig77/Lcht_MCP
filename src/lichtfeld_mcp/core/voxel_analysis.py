from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Iterable

from lichtfeld_mcp.core.gaussian import BoundingBox, Position3D
from lichtfeld_mcp.errors import InvalidParameterError


@dataclass(frozen=True, slots=True)
class VoxelCluster:
    id: int
    voxel_count: int
    estimated_splat_count: int
    bounding_box: BoundingBox
    centroid: Position3D


def analyze_voxel_clusters(
    positions: Iterable[Position3D | tuple[float, float, float]],
    voxel_size: float,
    min_voxel_cluster_size: int = 1,
) -> list[VoxelCluster]:
    if voxel_size <= 0.0:
        raise InvalidParameterError("voxel_size must be strictly positive.")
    if min_voxel_cluster_size < 1:
        raise InvalidParameterError("min_voxel_cluster_size must be at least 1.")

    voxel_map = _build_voxel_map(positions, voxel_size)
    if not voxel_map:
        return []

    visited: set[tuple[int, int, int]] = set()
    clusters: list[VoxelCluster] = []
    cluster_id = 0

    for start_key in voxel_map:
        if start_key in visited:
            continue
        component_keys = _collect_voxel_component(
            start_key=start_key,
            voxel_map=voxel_map,
            visited=visited,
        )
        if len(component_keys) < min_voxel_cluster_size:
            continue
        clusters.append(
            _build_voxel_cluster(
                cluster_id=cluster_id,
                voxel_map=voxel_map,
                component_keys=component_keys,
            )
        )
        cluster_id += 1
    return clusters


def largest_voxel_cluster(clusters: list[VoxelCluster]) -> VoxelCluster | None:
    if not clusters:
        return None
    return max(
        clusters,
        key=lambda cluster: (cluster.estimated_splat_count, cluster.voxel_count, -cluster.id),
    )


def voxel_clusters_smaller_than(clusters: list[VoxelCluster], size: int) -> list[VoxelCluster]:
    if size <= 0:
        return []
    return [cluster for cluster in clusters if cluster.voxel_count < size]


def voxel_clusters_outside_largest(clusters: list[VoxelCluster]) -> list[VoxelCluster]:
    largest = largest_voxel_cluster(clusters)
    if largest is None:
        return []
    return [cluster for cluster in clusters if cluster.id != largest.id]


@dataclass(slots=True)
class _VoxelStats:
    count: int
    sum_x: float
    sum_y: float
    sum_z: float
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float


def _build_voxel_map(
    positions: Iterable[Position3D | tuple[float, float, float]],
    voxel_size: float,
) -> dict[tuple[int, int, int], _VoxelStats]:
    voxel_map: dict[tuple[int, int, int], _VoxelStats] = {}
    for position in positions:
        x, y, z = _coerce_position(position)
        key = _voxel_key(x, y, z, voxel_size)
        stats = voxel_map.get(key)
        if stats is None:
            voxel_map[key] = _VoxelStats(
                count=1,
                sum_x=x,
                sum_y=y,
                sum_z=z,
                min_x=x,
                min_y=y,
                min_z=z,
                max_x=x,
                max_y=y,
                max_z=z,
            )
            continue
        stats.count += 1
        stats.sum_x += x
        stats.sum_y += y
        stats.sum_z += z
        if x < stats.min_x:
            stats.min_x = x
        if y < stats.min_y:
            stats.min_y = y
        if z < stats.min_z:
            stats.min_z = z
        if x > stats.max_x:
            stats.max_x = x
        if y > stats.max_y:
            stats.max_y = y
        if z > stats.max_z:
            stats.max_z = z
    return voxel_map


def _collect_voxel_component(
    *,
    start_key: tuple[int, int, int],
    voxel_map: dict[tuple[int, int, int], _VoxelStats],
    visited: set[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    component_keys: list[tuple[int, int, int]] = []
    queue: deque[tuple[int, int, int]] = deque([start_key])
    visited.add(start_key)
    voxel_map_keys = voxel_map.keys()

    while queue:
        current_key = queue.popleft()
        component_keys.append(current_key)
        for neighbor_key in _neighbor_keys(current_key):
            if neighbor_key in visited or neighbor_key not in voxel_map_keys:
                continue
            visited.add(neighbor_key)
            queue.append(neighbor_key)
    return component_keys


def _build_voxel_cluster(
    *,
    cluster_id: int,
    voxel_map: dict[tuple[int, int, int], _VoxelStats],
    component_keys: list[tuple[int, int, int]],
) -> VoxelCluster:
    first_stats = voxel_map[component_keys[0]]
    total_splats = 0
    sum_x = 0.0
    sum_y = 0.0
    sum_z = 0.0
    min_x = first_stats.min_x
    min_y = first_stats.min_y
    min_z = first_stats.min_z
    max_x = first_stats.max_x
    max_y = first_stats.max_y
    max_z = first_stats.max_z

    for key in component_keys:
        stats = voxel_map[key]
        total_splats += stats.count
        sum_x += stats.sum_x
        sum_y += stats.sum_y
        sum_z += stats.sum_z
        if stats.min_x < min_x:
            min_x = stats.min_x
        if stats.min_y < min_y:
            min_y = stats.min_y
        if stats.min_z < min_z:
            min_z = stats.min_z
        if stats.max_x > max_x:
            max_x = stats.max_x
        if stats.max_y > max_y:
            max_y = stats.max_y
        if stats.max_z > max_z:
            max_z = stats.max_z

    return VoxelCluster(
        id=cluster_id,
        voxel_count=len(component_keys),
        estimated_splat_count=total_splats,
        bounding_box=BoundingBox(
            min=Position3D(x=min_x, y=min_y, z=min_z),
            max=Position3D(x=max_x, y=max_y, z=max_z),
        ),
        centroid=Position3D(
            x=sum_x / total_splats,
            y=sum_y / total_splats,
            z=sum_z / total_splats,
        ),
    )


def _coerce_position(position: Position3D | tuple[float, float, float]) -> tuple[float, float, float]:
    if isinstance(position, Position3D):
        return (position.x, position.y, position.z)
    return (float(position[0]), float(position[1]), float(position[2]))


def _voxel_key(x: float, y: float, z: float, voxel_size: float) -> tuple[int, int, int]:
    return (
        math.floor(x / voxel_size),
        math.floor(y / voxel_size),
        math.floor(z / voxel_size),
    )


def _neighbor_keys(key: tuple[int, int, int]) -> tuple[tuple[int, int, int], ...]:
    x, y, z = key
    return (
        (x - 1, y, z),
        (x + 1, y, z),
        (x, y - 1, z),
        (x, y + 1, z),
        (x, y, z - 1),
        (x, y, z + 1),
    )


__all__ = [
    "VoxelCluster",
    "analyze_voxel_clusters",
    "largest_voxel_cluster",
    "voxel_clusters_outside_largest",
    "voxel_clusters_smaller_than",
]
