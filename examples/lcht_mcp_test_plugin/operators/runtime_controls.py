# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime control operators for the LichtFeld test plugin panel."""

from __future__ import annotations

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.runtime_config import (
    CLUSTER_ANALYSIS_BALANCED_SPLATS,
    CLUSTER_ANALYSIS_DETAILED_SPLATS,
    CLUSTER_ANALYSIS_FAST_SPLATS,
    CLUSTER_ANALYSIS_SPLATS_STEP,
    CLUSTER_DISTANCE_STEP,
    CLUSTER_MIN_SIZE_STEP,
    MAX_RATIO_STEP,
    MAX_SPLATS_STEP,
    SAFE_DELETE_Z_STEP,
    SMOKE_Z_STEP,
    adjust_max_cluster_analysis_splats,
    adjust_cluster_distance_threshold,
    adjust_cluster_min_cluster_size,
    adjust_max_deletable_percentage,
    adjust_max_deletable_splats,
    adjust_safe_delete_max_z,
    adjust_safe_delete_min_z,
    adjust_smoke_test_max_z,
    adjust_smoke_test_min_z,
    arm_safe_delete,
    disable_cluster_analysis_abort,
    enable_cluster_analysis_abort,
    confirm_safe_delete,
    disarm_safe_delete,
    set_max_cluster_analysis_splats,
    snapshot_runtime_config,
)


ARM_SAFE_DELETE_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_arm_safe_delete"
)
CONFIRM_SAFE_DELETE_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_confirm_safe_delete"
)
DISARM_SAFE_DELETE_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_disarm_safe_delete"
)
SMOKE_MIN_Z_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_smoke_min_z_down"
)
SMOKE_MIN_Z_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_smoke_min_z_up"
)
SMOKE_MAX_Z_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_smoke_max_z_down"
)
SMOKE_MAX_Z_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_smoke_max_z_up"
)
SAFE_DELETE_MIN_Z_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_safe_delete_min_z_down"
)
SAFE_DELETE_MIN_Z_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_safe_delete_min_z_up"
)
SAFE_DELETE_MAX_Z_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_safe_delete_max_z_down"
)
SAFE_DELETE_MAX_Z_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_safe_delete_max_z_up"
)
MAX_DELETABLE_SPLATS_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_max_deletable_splats_down"
)
MAX_DELETABLE_SPLATS_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_max_deletable_splats_up"
)
MAX_DELETABLE_PERCENTAGE_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_max_deletable_percentage_down"
)
MAX_DELETABLE_PERCENTAGE_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_max_deletable_percentage_up"
)
CLUSTER_DISTANCE_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_cluster_distance_down"
)
CLUSTER_DISTANCE_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_cluster_distance_up"
)
CLUSTER_MIN_SIZE_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_cluster_min_size_down"
)
CLUSTER_MIN_SIZE_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_cluster_min_size_up"
)
MAX_CLUSTER_ANALYSIS_SPLATS_DOWN_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_max_cluster_analysis_splats_down"
)
MAX_CLUSTER_ANALYSIS_SPLATS_UP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_max_cluster_analysis_splats_up"
)
ENABLE_CLUSTER_ANALYSIS_ABORT_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_enable_cluster_analysis_abort"
)
DISABLE_CLUSTER_ANALYSIS_ABORT_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_disable_cluster_analysis_abort"
)
SET_CLUSTER_ANALYSIS_FAST_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_set_cluster_analysis_fast"
)
SET_CLUSTER_ANALYSIS_BALANCED_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_set_cluster_analysis_balanced"
)
SET_CLUSTER_ANALYSIS_DETAILED_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.runtime_controls."
    "LCHTMCP_OT_set_cluster_analysis_detailed"
)


def _log_runtime_state(action: str) -> None:
    config = snapshot_runtime_config()
    lf.log.info(
        "lcht_mcp_test_plugin: "
        f"{action}. "
        f"enable_safe_delete={config.enable_safe_delete}, "
        f"confirm_safe_delete={config.confirm_safe_delete}, "
        f"smoke_test_range=({config.smoke_test_min_z:.4f}, {config.smoke_test_max_z:.4f}), "
        f"safe_delete_range=({config.safe_delete_min_z:.4f}, {config.safe_delete_max_z:.4f}), "
        f"max_deletable_splats={config.max_deletable_splats}, "
        f"max_deletable_percentage={config.max_deletable_percentage:.4f}, "
        f"cluster_distance_threshold={config.cluster_distance_threshold:.4f}, "
        f"cluster_min_cluster_size={config.cluster_min_cluster_size}, "
        f"max_cluster_analysis_splats={config.max_cluster_analysis_splats}, "
        "abort_if_splat_count_above_limit="
        f"{config.abort_if_splat_count_above_limit}"
    )


class _ConfigOperator(Operator):
    """Base operator for stateful panel controls."""

    action_label = "Updated runtime config"

    def invoke(self, context, event: Event) -> set:
        self._apply()
        _log_runtime_state(self.action_label)
        return {"FINISHED"}

    def _apply(self) -> None:
        raise NotImplementedError


class LCHTMCP_OT_arm_safe_delete(_ConfigOperator):
    """Arm safe delete without confirming it."""

    label = "Arm Safe Delete"
    description = "Enable the safe delete gate while leaving confirmation off"
    action_label = "Safe delete armed"

    def _apply(self) -> None:
        arm_safe_delete()


class LCHTMCP_OT_confirm_safe_delete(_ConfigOperator):
    """Confirm safe delete after it has been armed."""

    label = "Confirm Safe Delete"
    description = "Confirm the armed safe delete flow"
    action_label = "Safe delete confirmed"

    def _apply(self) -> None:
        confirm_safe_delete()


class LCHTMCP_OT_disarm_safe_delete(_ConfigOperator):
    """Return the delete controls to their safe default state."""

    label = "Disarm Safe Delete"
    description = "Clear both safe delete flags"
    action_label = "Safe delete disarmed"

    def _apply(self) -> None:
        disarm_safe_delete()


class LCHTMCP_OT_smoke_min_z_down(_ConfigOperator):
    label = "Smoke Min Z -"
    description = "Decrease the smoke test minimum Z"
    action_label = f"Decreased smoke test min Z by {SMOKE_Z_STEP:.2f}"

    def _apply(self) -> None:
        adjust_smoke_test_min_z(-SMOKE_Z_STEP)


class LCHTMCP_OT_smoke_min_z_up(_ConfigOperator):
    label = "Smoke Min Z +"
    description = "Increase the smoke test minimum Z"
    action_label = f"Increased smoke test min Z by {SMOKE_Z_STEP:.2f}"

    def _apply(self) -> None:
        adjust_smoke_test_min_z(SMOKE_Z_STEP)


class LCHTMCP_OT_smoke_max_z_down(_ConfigOperator):
    label = "Smoke Max Z -"
    description = "Decrease the smoke test maximum Z"
    action_label = f"Decreased smoke test max Z by {SMOKE_Z_STEP:.2f}"

    def _apply(self) -> None:
        adjust_smoke_test_max_z(-SMOKE_Z_STEP)


class LCHTMCP_OT_smoke_max_z_up(_ConfigOperator):
    label = "Smoke Max Z +"
    description = "Increase the smoke test maximum Z"
    action_label = f"Increased smoke test max Z by {SMOKE_Z_STEP:.2f}"

    def _apply(self) -> None:
        adjust_smoke_test_max_z(SMOKE_Z_STEP)


class LCHTMCP_OT_safe_delete_min_z_down(_ConfigOperator):
    label = "Delete Min Z -"
    description = "Decrease the safe delete minimum Z"
    action_label = f"Decreased safe delete min Z by {SAFE_DELETE_Z_STEP:.2f}"

    def _apply(self) -> None:
        adjust_safe_delete_min_z(-SAFE_DELETE_Z_STEP)


class LCHTMCP_OT_safe_delete_min_z_up(_ConfigOperator):
    label = "Delete Min Z +"
    description = "Increase the safe delete minimum Z"
    action_label = f"Increased safe delete min Z by {SAFE_DELETE_Z_STEP:.2f}"

    def _apply(self) -> None:
        adjust_safe_delete_min_z(SAFE_DELETE_Z_STEP)


class LCHTMCP_OT_safe_delete_max_z_down(_ConfigOperator):
    label = "Delete Max Z -"
    description = "Decrease the safe delete maximum Z"
    action_label = f"Decreased safe delete max Z by {SAFE_DELETE_Z_STEP:.2f}"

    def _apply(self) -> None:
        adjust_safe_delete_max_z(-SAFE_DELETE_Z_STEP)


class LCHTMCP_OT_safe_delete_max_z_up(_ConfigOperator):
    label = "Delete Max Z +"
    description = "Increase the safe delete maximum Z"
    action_label = f"Increased safe delete max Z by {SAFE_DELETE_Z_STEP:.2f}"

    def _apply(self) -> None:
        adjust_safe_delete_max_z(SAFE_DELETE_Z_STEP)


class LCHTMCP_OT_max_deletable_splats_down(_ConfigOperator):
    label = "Max Splats -"
    description = "Decrease the maximum deletable splat threshold"
    action_label = f"Decreased max deletable splats by {MAX_SPLATS_STEP}"

    def _apply(self) -> None:
        adjust_max_deletable_splats(-MAX_SPLATS_STEP)


class LCHTMCP_OT_max_deletable_splats_up(_ConfigOperator):
    label = "Max Splats +"
    description = "Increase the maximum deletable splat threshold"
    action_label = f"Increased max deletable splats by {MAX_SPLATS_STEP}"

    def _apply(self) -> None:
        adjust_max_deletable_splats(MAX_SPLATS_STEP)


class LCHTMCP_OT_max_deletable_percentage_down(_ConfigOperator):
    label = "Max % -"
    description = "Decrease the maximum deletable percentage threshold"
    action_label = f"Decreased max deletable percentage by {MAX_RATIO_STEP:.2f}"

    def _apply(self) -> None:
        adjust_max_deletable_percentage(-MAX_RATIO_STEP)


class LCHTMCP_OT_max_deletable_percentage_up(_ConfigOperator):
    label = "Max % +"
    description = "Increase the maximum deletable percentage threshold"
    action_label = f"Increased max deletable percentage by {MAX_RATIO_STEP:.2f}"

    def _apply(self) -> None:
        adjust_max_deletable_percentage(MAX_RATIO_STEP)


class LCHTMCP_OT_cluster_distance_down(_ConfigOperator):
    label = "Cluster Distance -"
    description = "Decrease the cluster distance threshold"
    action_label = f"Decreased cluster distance by {CLUSTER_DISTANCE_STEP:.2f}"

    def _apply(self) -> None:
        adjust_cluster_distance_threshold(-CLUSTER_DISTANCE_STEP)


class LCHTMCP_OT_cluster_distance_up(_ConfigOperator):
    label = "Cluster Distance +"
    description = "Increase the cluster distance threshold"
    action_label = f"Increased cluster distance by {CLUSTER_DISTANCE_STEP:.2f}"

    def _apply(self) -> None:
        adjust_cluster_distance_threshold(CLUSTER_DISTANCE_STEP)


class LCHTMCP_OT_cluster_min_size_down(_ConfigOperator):
    label = "Cluster Min Size -"
    description = "Decrease the cluster minimum size threshold"
    action_label = f"Decreased cluster min size by {CLUSTER_MIN_SIZE_STEP}"

    def _apply(self) -> None:
        adjust_cluster_min_cluster_size(-CLUSTER_MIN_SIZE_STEP)


class LCHTMCP_OT_cluster_min_size_up(_ConfigOperator):
    label = "Cluster Min Size +"
    description = "Increase the cluster minimum size threshold"
    action_label = f"Increased cluster min size by {CLUSTER_MIN_SIZE_STEP}"

    def _apply(self) -> None:
        adjust_cluster_min_cluster_size(CLUSTER_MIN_SIZE_STEP)


class LCHTMCP_OT_max_cluster_analysis_splats_down(_ConfigOperator):
    label = "Cluster Max Splats -"
    description = "Decrease the cluster analysis splat limit"
    action_label = f"Decreased cluster analysis splat limit by {CLUSTER_ANALYSIS_SPLATS_STEP}"

    def _apply(self) -> None:
        adjust_max_cluster_analysis_splats(-CLUSTER_ANALYSIS_SPLATS_STEP)


class LCHTMCP_OT_max_cluster_analysis_splats_up(_ConfigOperator):
    label = "Cluster Max Splats +"
    description = "Increase the cluster analysis splat limit"
    action_label = f"Increased cluster analysis splat limit by {CLUSTER_ANALYSIS_SPLATS_STEP}"

    def _apply(self) -> None:
        adjust_max_cluster_analysis_splats(CLUSTER_ANALYSIS_SPLATS_STEP)


class LCHTMCP_OT_enable_cluster_analysis_abort(_ConfigOperator):
    label = "Abort Above Limit"
    description = "Refuse cluster analysis above the configured splat limit"
    action_label = "Enabled cluster analysis abort-above-limit safety gate"

    def _apply(self) -> None:
        enable_cluster_analysis_abort()


class LCHTMCP_OT_disable_cluster_analysis_abort(_ConfigOperator):
    label = "Allow Sampled Mode"
    description = "Allow sampled approximate cluster analysis above the limit"
    action_label = "Disabled cluster analysis abort-above-limit safety gate"

    def _apply(self) -> None:
        disable_cluster_analysis_abort()


class LCHTMCP_OT_set_cluster_analysis_fast(_ConfigOperator):
    label = "Fast Preset"
    description = "Set cluster analysis to the fast 10,000 splat preset"
    action_label = f"Set cluster analysis preset to Fast ({CLUSTER_ANALYSIS_FAST_SPLATS})"

    def _apply(self) -> None:
        set_max_cluster_analysis_splats(CLUSTER_ANALYSIS_FAST_SPLATS)


class LCHTMCP_OT_set_cluster_analysis_balanced(_ConfigOperator):
    label = "Balanced Preset"
    description = "Set cluster analysis to the balanced 25,000 splat preset"
    action_label = (
        f"Set cluster analysis preset to Balanced ({CLUSTER_ANALYSIS_BALANCED_SPLATS})"
    )

    def _apply(self) -> None:
        set_max_cluster_analysis_splats(CLUSTER_ANALYSIS_BALANCED_SPLATS)


class LCHTMCP_OT_set_cluster_analysis_detailed(_ConfigOperator):
    label = "Detailed Preset"
    description = "Set cluster analysis to the detailed 100,000 splat preset"
    action_label = (
        f"Set cluster analysis preset to Detailed ({CLUSTER_ANALYSIS_DETAILED_SPLATS})"
    )

    def _apply(self) -> None:
        set_max_cluster_analysis_splats(CLUSTER_ANALYSIS_DETAILED_SPLATS)
