# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for opening the interactive cleanup workspace."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_open_cleanup_workspace


OPEN_CLEANUP_WORKSPACE_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.open_cleanup_workspace."
    "LCHTMCP_OT_open_cleanup_workspace"
)


class LCHTMCP_OT_open_cleanup_workspace(Operator):
    """Open the cleanup workspace and build the first native preview."""

    label = "Open Cleanup Workspace"
    description = "Open the interactive cleanup workspace and build the first preview"

    def invoke(self, context, event: Event) -> set:
        success, message = run_open_cleanup_workspace()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup workspace opened: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup workspace failed: {message}")
        return {"CANCELLED"}
