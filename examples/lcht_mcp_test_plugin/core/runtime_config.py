# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-editable configuration for the LichtFeld test plugin."""

from __future__ import annotations

from dataclasses import dataclass, replace


CLEANUP_CATEGORY_FLOATING = "FLOATING_VOXEL_CLUSTERS"
CLEANUP_CATEGORY_DISCONNECTED = "DISCONNECTED_CLUSTERS"
CLEANUP_CATEGORY_OUTLIER = "DISTANT_OUTLIERS"
CLEANUP_CATEGORY_SPARSE = "SPARSE_SINGLETON_REGIONS"

_CLEANUP_CATEGORY_ORDER = (
    CLEANUP_CATEGORY_FLOATING,
    CLEANUP_CATEGORY_DISCONNECTED,
    CLEANUP_CATEGORY_OUTLIER,
    CLEANUP_CATEGORY_SPARSE,
)

_CLEANUP_CATEGORY_LABELS = {
    CLEANUP_CATEGORY_FLOATING: "floating voxel clusters",
    CLEANUP_CATEGORY_DISCONNECTED: "disconnected clusters",
    CLEANUP_CATEGORY_OUTLIER: "distant outliers",
    CLEANUP_CATEGORY_SPARSE: "sparse singleton regions",
}


SMOKE_Z_STEP = 0.05
SAFE_DELETE_Z_STEP = 0.01
MAX_SPLATS_STEP = 1_000
MAX_RATIO_STEP = 0.01
CLUSTER_DISTANCE_STEP = 0.05
CLUSTER_MIN_SIZE_STEP = 50
VOXEL_SIZE_STEP = 0.05
VOXEL_MIN_CLUSTER_SIZE_STEP = 10
OUTLIER_DISTANCE_STEP = 0.25
CLEANUP_AGGRESSIVENESS_STEP = 0.1
CLUSTER_ANALYSIS_SPLATS_STEP = 10_000
CLUSTER_ANALYSIS_FAST_SPLATS = 10_000
CLUSTER_ANALYSIS_BALANCED_SPLATS = 25_000
CLUSTER_ANALYSIS_DETAILED_SPLATS = 100_000
CONSERVATIVE_CLEANUP_PRESET = "Conservative"
BALANCED_CLEANUP_PRESET = "Balanced"
AGGRESSIVE_CLEANUP_PRESET = "Aggressive"
CUSTOM_CLEANUP_PRESET = "Custom"


@dataclass(frozen=True, slots=True)
class CleanupPresetSettings:
    voxel_size: float
    voxel_min_cluster_size: int
    cleanup_outlier_distance: float
    cleanup_aggressiveness: float


CLEANUP_PRESETS = {
    CONSERVATIVE_CLEANUP_PRESET: CleanupPresetSettings(
        voxel_size=0.15,
        voxel_min_cluster_size=5,
        cleanup_outlier_distance=3.5,
        cleanup_aggressiveness=0.25,
    ),
    BALANCED_CLEANUP_PRESET: CleanupPresetSettings(
        voxel_size=0.25,
        voxel_min_cluster_size=10,
        cleanup_outlier_distance=2.5,
        cleanup_aggressiveness=0.5,
    ),
    AGGRESSIVE_CLEANUP_PRESET: CleanupPresetSettings(
        voxel_size=0.40,
        voxel_min_cluster_size=20,
        cleanup_outlier_distance=1.5,
        cleanup_aggressiveness=0.75,
    ),
}


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
    cleanup_outlier_distance: float = 2.5
    cleanup_aggressiveness: float = 0.5
    cleanup_preset: str = BALANCED_CLEANUP_PRESET
    last_scene_analysis_lines: tuple[str, ...] = ()
    last_cleanup_preview_lines: tuple[str, ...] = ()
    last_cleanup_preview_summary: dict[str, object] | None = None
    last_cleanup_workspace_lines: tuple[str, ...] = ()
    last_cleanup_category_preview_lines: tuple[str, ...] = ()
    last_cleanup_preset_comparison_lines: tuple[str, ...] = ()
    active_cleanup_categories: tuple[str, ...] = _CLEANUP_CATEGORY_ORDER
    selected_cleanup_category: str | None = CLEANUP_CATEGORY_FLOATING


_runtime_config = RuntimeConfig()


def cleanup_category_order() -> tuple[str, ...]:
    return _CLEANUP_CATEGORY_ORDER


def cleanup_category_label(category: str) -> str:
    return _CLEANUP_CATEGORY_LABELS[normalize_cleanup_category(category)]


def normalize_cleanup_category(category: str) -> str:
    normalized = str(category).strip()
    if normalized in _CLEANUP_CATEGORY_LABELS:
        return normalized
    for candidate, label in _CLEANUP_CATEGORY_LABELS.items():
        if normalized.casefold() == candidate.casefold() or normalized.casefold() == label.casefold():
            return candidate
    raise ValueError(f"Unsupported cleanup category: {category!r}")


def normalize_cleanup_categories(categories: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for category in categories:
        normalized = normalize_cleanup_category(category)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _round_z(value: float) -> float:
    return round(value, 4)


def _round_ratio(value: float) -> float:
    return round(value, 4)


def _match_cleanup_preset_name(
    voxel_size: float,
    voxel_min_cluster_size: int,
    cleanup_outlier_distance: float,
    cleanup_aggressiveness: float,
) -> str:
    for preset_name, preset in CLEANUP_PRESETS.items():
        if (
            abs(voxel_size - preset.voxel_size) < 1e-6
            and voxel_min_cluster_size == preset.voxel_min_cluster_size
            and abs(cleanup_outlier_distance - preset.cleanup_outlier_distance) < 1e-6
            and abs(cleanup_aggressiveness - preset.cleanup_aggressiveness) < 1e-6
        ):
            return preset_name
    return CUSTOM_CLEANUP_PRESET


def _sync_cleanup_preset_from_parameters() -> None:
    _runtime_config.cleanup_preset = _match_cleanup_preset_name(
        _runtime_config.voxel_size,
        _runtime_config.voxel_min_cluster_size,
        _runtime_config.cleanup_outlier_distance,
        _runtime_config.cleanup_aggressiveness,
    )


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


def set_cleanup_preview_report_lines(lines: list[str]) -> None:
    """Store the most recent cleanup preview summary for panel display."""
    _runtime_config.last_cleanup_preview_lines = tuple(lines)


def set_cleanup_preview_summary(summary: dict[str, object] | None) -> None:
    """Store the structured cleanup preview summary for follow-up actions."""
    _runtime_config.last_cleanup_preview_summary = summary


def set_cleanup_workspace_report_lines(lines: list[str]) -> None:
    """Store the most recent cleanup workspace report for panel display."""
    _runtime_config.last_cleanup_workspace_lines = tuple(lines)


def set_cleanup_category_preview_lines(lines: list[str]) -> None:
    """Store the most recent cleanup category preview report for panel display."""
    _runtime_config.last_cleanup_category_preview_lines = tuple(lines)


def set_cleanup_preset_comparison_lines(lines: list[str]) -> None:
    """Store the most recent cleanup preset comparison report for panel display."""
    _runtime_config.last_cleanup_preset_comparison_lines = tuple(lines)


def sync_cleanup_category_state(
    categories: tuple[str, ...] | list[str],
    *,
    selected_category: str | None = None,
) -> None:
    """Store the active and selected cleanup categories from the workspace/UI."""
    normalized_categories = normalize_cleanup_categories(tuple(categories))
    normalized_selected_category = None
    if selected_category is not None:
        normalized_selected_category = normalize_cleanup_category(selected_category)
        if normalized_selected_category not in normalized_categories:
            normalized_selected_category = None
    _runtime_config.active_cleanup_categories = normalized_categories
    _runtime_config.selected_cleanup_category = normalized_selected_category


def toggle_cleanup_category_visibility(category: str) -> None:
    """Toggle category visibility and move selection to the toggled-on category."""
    normalized_category = normalize_cleanup_category(category)
    active = list(normalize_cleanup_categories(_runtime_config.active_cleanup_categories))
    if normalized_category in active:
        active = [entry for entry in active if entry != normalized_category]
    else:
        active.append(normalized_category)
    normalized_active = normalize_cleanup_categories(tuple(active))
    selected_category = _runtime_config.selected_cleanup_category
    if normalized_category in normalized_active:
        selected_category = normalized_category
    elif selected_category not in normalized_active:
        selected_category = normalized_active[0] if normalized_active else None
    sync_cleanup_category_state(
        normalized_active,
        selected_category=selected_category,
    )


def set_cleanup_preset(preset_name: str) -> None:
    """Apply a named cleanup preset to the runtime configuration."""
    preset = CLEANUP_PRESETS[preset_name]
    _runtime_config.voxel_size = preset.voxel_size
    _runtime_config.voxel_min_cluster_size = preset.voxel_min_cluster_size
    _runtime_config.cleanup_outlier_distance = preset.cleanup_outlier_distance
    _runtime_config.cleanup_aggressiveness = preset.cleanup_aggressiveness
    _runtime_config.cleanup_preset = preset_name


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
    _sync_cleanup_preset_from_parameters()


def adjust_voxel_min_cluster_size(delta: int) -> None:
    """Adjust the voxel preview minimum voxel cluster size."""
    _runtime_config.voxel_min_cluster_size = max(
        1,
        _runtime_config.voxel_min_cluster_size + delta,
    )
    _sync_cleanup_preset_from_parameters()


def adjust_cleanup_outlier_distance(delta: float) -> None:
    """Adjust the cleanup workspace outlier distance threshold."""
    updated = _runtime_config.cleanup_outlier_distance + delta
    _runtime_config.cleanup_outlier_distance = _round_z(max(0.1, updated))
    _sync_cleanup_preset_from_parameters()


def adjust_cleanup_aggressiveness(delta: float) -> None:
    """Adjust the cleanup workspace aggressiveness."""
    updated = _runtime_config.cleanup_aggressiveness + delta
    _runtime_config.cleanup_aggressiveness = _round_ratio(min(1.0, max(0.0, updated)))
    _sync_cleanup_preset_from_parameters()


def enable_cluster_analysis_abort() -> None:
    """Refuse cluster analysis when the active scene exceeds the configured limit."""
    _runtime_config.abort_if_splat_count_above_limit = True


def disable_cluster_analysis_abort() -> None:
    """Allow sampled approximate cluster analysis above the configured limit."""
    _runtime_config.abort_if_splat_count_above_limit = False
