# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for resetting the cleanup workspace preview."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_reset_cleanup_workspace


RESET_CLEANUP_WORKSPACE_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.reset_cleanup_workspace."
    "LCHTMCP_OT_reset_cleanup_workspace"
)


class LCHTMCP_OT_reset_cleanup_workspace(Operator):
    """Clear the native cleanup preview and invalidate the workspace session."""

    label = "Reset Preview"
    description = "Reset the cleanup workspace preview without modifying splats"

    def invoke(self, context, event: Event) -> set:
        success, message = run_reset_cleanup_workspace()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup workspace reset: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup workspace reset failed: {message}")
        return {"CANCELLED"}
