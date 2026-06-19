# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Lcht_MCP test plugin for LichtFeld Studio."""

import lichtfeld as lf

from .operators.analyze_scene import LCHTMCP_OT_analyze_scene
from .operators.analyze_clusters import LCHTMCP_OT_analyze_clusters
from .operators.analyze_voxel_clusters import LCHTMCP_OT_analyze_voxel_clusters
from .operators.preview_cleanup_candidates import LCHTMCP_OT_preview_cleanup_candidates
from .panels.test_panel import LchtMcpTestPanel
from .operators.diagnose_api import LCHTMCP_OT_diagnose_api
from .operators.diagnose_native_selection import LCHTMCP_OT_diagnose_native_selection
from .operators.diagnose_tensor_mask import LCHTMCP_OT_diagnose_tensor_mask
from .operators.runtime_controls import (
    LCHTMCP_OT_cluster_distance_down,
    LCHTMCP_OT_cluster_distance_up,
    LCHTMCP_OT_cluster_min_size_down,
    LCHTMCP_OT_cluster_min_size_up,
    LCHTMCP_OT_disable_cluster_analysis_abort,
    LCHTMCP_OT_arm_safe_delete,
    LCHTMCP_OT_enable_cluster_analysis_abort,
    LCHTMCP_OT_max_cluster_analysis_splats_down,
    LCHTMCP_OT_max_cluster_analysis_splats_up,
    LCHTMCP_OT_confirm_safe_delete,
    LCHTMCP_OT_disarm_safe_delete,
    LCHTMCP_OT_max_deletable_percentage_down,
    LCHTMCP_OT_max_deletable_percentage_up,
    LCHTMCP_OT_max_deletable_splats_down,
    LCHTMCP_OT_max_deletable_splats_up,
    LCHTMCP_OT_safe_delete_max_z_down,
    LCHTMCP_OT_safe_delete_max_z_up,
    LCHTMCP_OT_safe_delete_min_z_down,
    LCHTMCP_OT_safe_delete_min_z_up,
    LCHTMCP_OT_set_cluster_analysis_balanced,
    LCHTMCP_OT_set_cluster_analysis_detailed,
    LCHTMCP_OT_set_cluster_analysis_fast,
    LCHTMCP_OT_smoke_max_z_down,
    LCHTMCP_OT_smoke_max_z_up,
    LCHTMCP_OT_smoke_min_z_down,
    LCHTMCP_OT_smoke_min_z_up,
    LCHTMCP_OT_voxel_min_cluster_size_down,
    LCHTMCP_OT_voxel_min_cluster_size_up,
    LCHTMCP_OT_voxel_size_down,
    LCHTMCP_OT_voxel_size_up,
)
from .operators.run_safe_delete_test import LCHTMCP_OT_run_safe_delete_test
from .operators.run_test import LCHTMCP_OT_run_test
from .operators.run_undo_validation import LCHTMCP_OT_run_undo_validation

_classes = [
    LchtMcpTestPanel,
    LCHTMCP_OT_analyze_scene,
    LCHTMCP_OT_analyze_clusters,
    LCHTMCP_OT_analyze_voxel_clusters,
    LCHTMCP_OT_preview_cleanup_candidates,
    LCHTMCP_OT_arm_safe_delete,
    LCHTMCP_OT_confirm_safe_delete,
    LCHTMCP_OT_disarm_safe_delete,
    LCHTMCP_OT_run_test,
    LCHTMCP_OT_run_safe_delete_test,
    LCHTMCP_OT_run_undo_validation,
    LCHTMCP_OT_diagnose_api,
    LCHTMCP_OT_diagnose_native_selection,
    LCHTMCP_OT_diagnose_tensor_mask,
    LCHTMCP_OT_smoke_min_z_down,
    LCHTMCP_OT_smoke_min_z_up,
    LCHTMCP_OT_smoke_max_z_down,
    LCHTMCP_OT_smoke_max_z_up,
    LCHTMCP_OT_safe_delete_min_z_down,
    LCHTMCP_OT_safe_delete_min_z_up,
    LCHTMCP_OT_safe_delete_max_z_down,
    LCHTMCP_OT_safe_delete_max_z_up,
    LCHTMCP_OT_max_deletable_splats_down,
    LCHTMCP_OT_max_deletable_splats_up,
    LCHTMCP_OT_max_deletable_percentage_down,
    LCHTMCP_OT_max_deletable_percentage_up,
    LCHTMCP_OT_cluster_distance_down,
    LCHTMCP_OT_cluster_distance_up,
    LCHTMCP_OT_cluster_min_size_down,
    LCHTMCP_OT_cluster_min_size_up,
    LCHTMCP_OT_max_cluster_analysis_splats_down,
    LCHTMCP_OT_max_cluster_analysis_splats_up,
    LCHTMCP_OT_set_cluster_analysis_fast,
    LCHTMCP_OT_set_cluster_analysis_balanced,
    LCHTMCP_OT_set_cluster_analysis_detailed,
    LCHTMCP_OT_voxel_size_down,
    LCHTMCP_OT_voxel_size_up,
    LCHTMCP_OT_voxel_min_cluster_size_down,
    LCHTMCP_OT_voxel_min_cluster_size_up,
    LCHTMCP_OT_enable_cluster_analysis_abort,
    LCHTMCP_OT_disable_cluster_analysis_abort,
]


def on_load():
    """Called when plugin loads."""
    for cls in _classes:
        lf.register_class(cls)
    lf.log.info("lcht_mcp_test_plugin loaded")


def on_unload():
    """Called when plugin unloads."""
    for cls in reversed(_classes):
        lf.unregister_class(cls)
    lf.log.info("lcht_mcp_test_plugin unloaded")


__all__ = [
    "LchtMcpTestPanel",
]
