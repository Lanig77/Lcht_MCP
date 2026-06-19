# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for reversible cleanup preview soft delete."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_soft_delete_cleanup_preview


SOFT_DELETE_CLEANUP_PREVIEW_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.soft_delete_cleanup_preview."
    "LCHTMCP_OT_soft_delete_cleanup_preview"
)


class LCHTMCP_OT_soft_delete_cleanup_preview(Operator):
    """Soft-delete the last reliable cleanup preview without finalizing it."""

    label = "Soft Delete Cleanup Preview"
    description = "Reversible only. Does not call apply_deleted()."

    def invoke(self, context, event: Event) -> set:
        """Execute the reversible cleanup preview soft delete."""
        success, message = run_soft_delete_cleanup_preview()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup preview soft delete finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup preview soft delete failed: {message}")
        return {"CANCELLED"}
