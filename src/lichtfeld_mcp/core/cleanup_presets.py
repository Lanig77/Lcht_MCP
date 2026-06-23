from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CleanupPresetDefinition:
    name: str
    voxel_size: float
    min_voxel_cluster_size: int
    outlier_distance: float
    cleanup_aggressiveness: float


CONSERVATIVE_CLEANUP_PRESET = CleanupPresetDefinition(
    name="Conservative",
    voxel_size=0.15,
    min_voxel_cluster_size=5,
    outlier_distance=3.5,
    cleanup_aggressiveness=0.25,
)
BALANCED_CLEANUP_PRESET = CleanupPresetDefinition(
    name="Balanced",
    voxel_size=0.25,
    min_voxel_cluster_size=10,
    outlier_distance=2.5,
    cleanup_aggressiveness=0.50,
)
AGGRESSIVE_CLEANUP_PRESET = CleanupPresetDefinition(
    name="Aggressive",
    voxel_size=0.40,
    min_voxel_cluster_size=20,
    outlier_distance=1.5,
    cleanup_aggressiveness=0.75,
)

_PRESETS = (
    CONSERVATIVE_CLEANUP_PRESET,
    BALANCED_CLEANUP_PRESET,
    AGGRESSIVE_CLEANUP_PRESET,
)


def iter_cleanup_presets() -> tuple[CleanupPresetDefinition, ...]:
    return _PRESETS


def get_cleanup_preset(name: str) -> CleanupPresetDefinition:
    normalized_name = str(name).strip().casefold()
    for preset in _PRESETS:
        if preset.name.casefold() == normalized_name:
            return preset
    raise KeyError(name)
