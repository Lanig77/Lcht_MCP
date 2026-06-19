# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for non-destructive cleanup candidate preview."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_preview_cleanup_candidates


PREVIEW_CLEANUP_CANDIDATES_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.preview_cleanup_candidates."
    "LCHTMCP_OT_preview_cleanup_candidates"
)


class LCHTMCP_OT_preview_cleanup_candidates(Operator):
    """Preview cleanup candidates without mutating the scene."""

    label = "Preview Cleanup Candidates"
    description = "Preview non-destructive cleanup candidates from scene analysis"

    def invoke(self, context, event: Event) -> set:
        """Execute the cleanup candidate preview."""
        success, message = run_preview_cleanup_candidates()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup preview finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup preview failed: {message}")
        return {"CANCELLED"}
