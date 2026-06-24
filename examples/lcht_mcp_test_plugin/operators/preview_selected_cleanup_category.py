# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for previewing the selected cleanup category."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_preview_selected_cleanup_category


PREVIEW_SELECTED_CLEANUP_CATEGORY_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.preview_selected_cleanup_category."
    "LCHTMCP_OT_preview_selected_cleanup_category"
)


class LCHTMCP_OT_preview_selected_cleanup_category(Operator):
    """Preview the selected cleanup category as a native selection."""

    label = "Preview Selected Category"
    description = "Preview only the selected cleanup category without modifying the scene"

    def invoke(self, context, event: Event) -> set:
        success, message = run_preview_selected_cleanup_category()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup category preview finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup category preview failed: {message}")
        return {"CANCELLED"}
