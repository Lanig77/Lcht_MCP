# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for unified read-only scene analysis in LichtFeld."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_scene_analysis


ANALYZE_SCENE_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.analyze_scene."
    "LCHTMCP_OT_analyze_scene"
)


class LCHTMCP_OT_analyze_scene(Operator):
    """Run a unified read-only scene analysis."""

    label = "Analyze Scene"
    description = "Run a unified read-only scene quality analysis"

    def invoke(self, context, event: Event) -> set:
        """Execute the scene analysis."""
        success, message = run_scene_analysis()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: scene analysis finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: scene analysis failed: {message}")
        return {"CANCELLED"}
