# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for running the guarded Lcht_MCP delete validation."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_safe_delete_test


RUN_SAFE_DELETE_TEST_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.run_safe_delete_test."
    "LCHTMCP_OT_run_safe_delete_test"
)


class LCHTMCP_OT_run_safe_delete_test(Operator):
    """Run the guarded LichtFeld delete validation flow."""

    label = "Run Safe Delete Test"
    description = "Run a guarded small-range delete validation in LichtFeld Studio"

    def invoke(self, context, event: Event) -> set:
        """Execute the guarded delete validation."""
        success, message = run_safe_delete_test()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: safe delete operator finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: safe delete operator failed: {message}")
        return {"CANCELLED"}
