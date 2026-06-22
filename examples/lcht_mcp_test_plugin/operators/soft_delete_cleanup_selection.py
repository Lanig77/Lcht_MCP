# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for reversible soft delete from the cleanup workspace."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_soft_delete_cleanup_selection


SOFT_DELETE_CLEANUP_SELECTION_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.soft_delete_cleanup_selection."
    "LCHTMCP_OT_soft_delete_cleanup_selection"
)


class LCHTMCP_OT_soft_delete_cleanup_selection(Operator):
    """Soft-delete the current cleanup workspace selection without apply_deleted()."""

    label = "Soft Delete Cleanup Workspace Selection"
    description = "Soft-delete the current cleanup workspace selection without apply_deleted()"

    def invoke(self, context, event: Event) -> set:
        success, message = run_soft_delete_cleanup_selection()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup workspace soft delete finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup workspace soft delete failed: {message}")
        return {"CANCELLED"}
