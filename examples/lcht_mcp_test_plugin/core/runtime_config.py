# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-editable configuration for the LichtFeld test plugin."""

from __future__ import annotations

from dataclasses import dataclass, replace


SMOKE_Z_STEP = 0.05
SAFE_DELETE_Z_STEP = 0.01
MAX_SPLATS_STEP = 1_000
MAX_RATIO_STEP = 0.01
CLUSTER_DISTANCE_STEP = 0.05
CLUSTER_MIN_SIZE_STEP = 50
VOXEL_SIZE_STEP = 0.05
VOXEL_MIN_CLUSTER_SIZE_STEP = 10
CLUSTER_ANALYSIS_SPLATS_STEP = 10_000
CLUSTER_ANALYSIS_FAST_SPLATS = 10_000
CLUSTER_ANALYSIS_BALANCED_SPLATS = 25_000
CLUSTER_ANALYSIS_DETAILED_SPLATS = 100_000


@dataclass(slots=True)
class RuntimeConfig:
    """Mutable runtime settings for plugin-driven integration tests."""

    enable_safe_delete: bool = False
    confirm_safe_delete: bool = False
    smoke_test_min_z: float = 0.0
    smoke_test_max_z: float = 2.0
    safe_delete_min_z: float = 1.0
    safe_delete_max_z: float = 1.02
    max_deletable_splats: int = 50_000
    max_deletable_percentage: float = 0.05
    cluster_distance_threshold: float = 0.10
    cluster_min_cluster_size: int = 100
    max_cluster_analysis_splats: int = CLUSTER_ANALYSIS_BALANCED_SPLATS
    abort_if_splat_count_above_limit: bool = False
    voxel_size: float = 0.25
    voxel_min_cluster_size: int = 10
    last_scene_analysis_lines: tuple[str, ...] = ()


_runtime_config = RuntimeConfig()


def _round_z(value: float) -> float:
    return round(value, 4)


def _round_ratio(value: float) -> float:
    return round(value, 4)


def snapshot_runtime_config() -> RuntimeConfig:
    """Return a detached copy of the current runtime config."""
    return replace(_runtime_config)


def reset_runtime_config() -> None:
    """Restore the runtime config to its default values."""
    global _runtime_config
    _runtime_config = RuntimeConfig()


def set_scene_analysis_report_lines(lines: list[str]) -> None:
    """Store the most recent scene analysis report for panel display."""
    _runtime_config.last_scene_analysis_lines = tuple(lines)


def arm_safe_delete() -> None:
    """Enable safe delete while keeping confirmation explicit."""
    _runtime_config.enable_safe_delete = True
    _runtime_config.confirm_safe_delete = False


def confirm_safe_delete() -> None:
    """Set the explicit confirmation flag."""
    _runtime_config.confirm_safe_delete = True


def disarm_safe_delete() -> None:
    """Reset the safe delete flags to their default safe state."""
    _runtime_config.enable_safe_delete = False
    _runtime_config.confirm_safe_delete = False


def adjust_smoke_test_min_z(delta: float) -> None:
    """Adjust the smoke-test minimum height."""
    _runtime_config.smoke_test_min_z = _round_z(_runtime_config.smoke_test_min_z + delta)


def adjust_smoke_test_max_z(delta: float) -> None:
    """Adjust the smoke-test maximum height."""
    _runtime_config.smoke_test_max_z = _round_z(_runtime_config.smoke_test_max_z + delta)


def adjust_safe_delete_min_z(delta: float) -> None:
    """Adjust the safe-delete minimum height."""
    _runtime_config.safe_delete_min_z = _round_z(_runtime_config.safe_delete_min_z + delta)


def adjust_safe_delete_max_z(delta: float) -> None:
    """Adjust the safe-delete maximum height."""
    _runtime_config.safe_delete_max_z = _round_z(_runtime_config.safe_delete_max_z + delta)


def adjust_max_deletable_splats(delta: int) -> None:
    """Adjust the maximum deletable splat threshold."""
    _runtime_config.max_deletable_splats = max(
        0,
        _runtime_config.max_deletable_splats + delta,
    )


def adjust_max_deletable_percentage(delta: float) -> None:
    """Adjust the maximum deletable ratio threshold."""
    updated_ratio = _runtime_config.max_deletable_percentage + delta
    _runtime_config.max_deletable_percentage = _round_ratio(min(1.0, max(0.0, updated_ratio)))


def adjust_cluster_distance_threshold(delta: float) -> None:
    """Adjust the cluster analysis distance threshold."""
    updated_distance = _runtime_config.cluster_distance_threshold + delta
    _runtime_config.cluster_distance_threshold = _round_z(max(0.01, updated_distance))


def adjust_cluster_min_cluster_size(delta: int) -> None:
    """Adjust the cluster analysis minimum cluster size."""
    _runtime_config.cluster_min_cluster_size = max(
        1,
        _runtime_config.cluster_min_cluster_size + delta,
    )


def adjust_max_cluster_analysis_splats(delta: int) -> None:
    """Adjust the maximum splat count allowed for cluster analysis."""
    _runtime_config.max_cluster_analysis_splats = max(
        1,
        _runtime_config.max_cluster_analysis_splats + delta,
    )


def set_max_cluster_analysis_splats(value: int) -> None:
    """Set the maximum splat count allowed for cluster analysis."""
    _runtime_config.max_cluster_analysis_splats = max(1, value)


def adjust_voxel_size(delta: float) -> None:
    """Adjust the voxel preview voxel size."""
    updated_voxel_size = _runtime_config.voxel_size + delta
    _runtime_config.voxel_size = _round_z(max(0.01, updated_voxel_size))


def adjust_voxel_min_cluster_size(delta: int) -> None:
    """Adjust the voxel preview minimum voxel cluster size."""
    _runtime_config.voxel_min_cluster_size = max(
        1,
        _runtime_config.voxel_min_cluster_size + delta,
    )


def enable_cluster_analysis_abort() -> None:
    """Refuse cluster analysis when the active scene exceeds the configured limit."""
    _runtime_config.abort_if_splat_count_above_limit = True


def disable_cluster_analysis_abort() -> None:
    """Allow sampled approximate cluster analysis above the configured limit."""
    _runtime_config.abort_if_splat_count_above_limit = False
