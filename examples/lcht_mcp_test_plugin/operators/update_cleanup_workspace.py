# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for refreshing the cleanup workspace preview."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_update_cleanup_workspace


UPDATE_CLEANUP_WORKSPACE_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.update_cleanup_workspace."
    "LCHTMCP_OT_update_cleanup_workspace"
)


class LCHTMCP_OT_update_cleanup_workspace(Operator):
    """Refresh the native cleanup preview from the latest workspace parameters."""

    label = "Update Preview"
    description = "Update the cleanup workspace preview without modifying the scene"

    def invoke(self, context, event: Event) -> set:
        success, message = run_update_cleanup_workspace()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup workspace updated: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup workspace update failed: {message}")
        return {"CANCELLED"}
