# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for non-destructive native cleanup selection preview."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_preview_cleanup_selection


PREVIEW_CLEANUP_CANDIDATES_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.preview_cleanup_candidates."
    "LCHTMCP_OT_preview_cleanup_candidates"
)


class LCHTMCP_OT_preview_cleanup_candidates(Operator):
    """Preview cleanup candidates as a native selection without mutating splats."""

    label = "Preview Cleanup Selection"
    description = "Preview non-destructive cleanup candidates as a native LichtFeld selection"

    def invoke(self, context, event: Event) -> set:
        """Execute the cleanup selection preview."""
        success, message = run_preview_cleanup_selection()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup selection preview finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup selection preview failed: {message}")
        return {"CANCELLED"}
