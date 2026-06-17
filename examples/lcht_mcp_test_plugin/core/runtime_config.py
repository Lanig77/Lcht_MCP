# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-editable configuration for the LichtFeld test plugin."""

from __future__ import annotations

from dataclasses import dataclass, replace


SMOKE_Z_STEP = 0.05
SAFE_DELETE_Z_STEP = 0.01
MAX_SPLATS_STEP = 1_000
MAX_RATIO_STEP = 0.01


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


_runtime_config = RuntimeConfig()


def _round_z(value: float) -> float:
    return round(value, 4)


def _round_ratio(value: float) -> float:
    return round(value, 4)


def snapshot_runtime_config() -> RuntimeConfig:
    """Return a detached copy of the current runtime config."""
    return replace(_runtime_config)


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
