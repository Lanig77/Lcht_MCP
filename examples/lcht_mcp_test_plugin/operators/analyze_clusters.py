# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for non-destructive cluster analysis in LichtFeld."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_cluster_analysis_preview


ANALYZE_CLUSTERS_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.analyze_clusters."
    "LCHTMCP_OT_analyze_clusters"
)


class LCHTMCP_OT_analyze_clusters(Operator):
    """Run a non-destructive cluster analysis preview."""

    label = "Analyze Clusters"
    description = "Preview disconnected Gaussian clusters without modifying the scene"

    def invoke(self, context, event: Event) -> set:
        """Execute the cluster analysis preview."""
        success, message = run_cluster_analysis_preview()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cluster analysis finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cluster analysis failed: {message}")
        return {"CANCELLED"}
