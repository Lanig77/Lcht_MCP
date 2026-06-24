# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for previewing all active cleanup categories."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_preview_all_cleanup_categories


PREVIEW_ALL_CLEANUP_CATEGORIES_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.preview_all_cleanup_categories."
    "LCHTMCP_OT_preview_all_cleanup_categories"
)


class LCHTMCP_OT_preview_all_cleanup_categories(Operator):
    """Preview all active cleanup categories as a single native selection."""

    label = "Preview All Cleanup Categories"
    description = "Preview every active cleanup category without modifying the scene"

    def invoke(self, context, event: Event) -> set:
        success, message = run_preview_all_cleanup_categories()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup category preview finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup category preview failed: {message}")
        return {"CANCELLED"}
