# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for non-destructive voxel cluster analysis in LichtFeld."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_voxel_cluster_analysis_preview


ANALYZE_VOXEL_CLUSTERS_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.analyze_voxel_clusters."
    "LCHTMCP_OT_analyze_voxel_clusters"
)


class LCHTMCP_OT_analyze_voxel_clusters(Operator):
    """Run a non-destructive voxel cluster analysis preview."""

    label = "Analyze Voxel Clusters"
    description = "Preview floating voxel clusters without modifying the scene"

    def invoke(self, context, event: Event) -> set:
        """Execute the voxel cluster analysis preview."""
        success, message = run_voxel_cluster_analysis_preview()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: voxel cluster analysis finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: voxel cluster analysis failed: {message}")
        return {"CANCELLED"}
