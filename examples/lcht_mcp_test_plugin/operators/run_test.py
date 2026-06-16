# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for running the Lcht_MCP smoke test."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_lcht_mcp_test


RUN_TEST_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.run_test.LCHTMCP_OT_run_test"
)


class LCHTMCP_OT_run_test(Operator):
    """Run the Lcht_MCP adapter smoke test."""

    label = "Run Lcht MCP Test"
    description = "Run a safe LichtFeld adapter smoke test"

    def invoke(self, context, event: Event) -> set:
        """Execute the smoke test."""
        success, message = run_lcht_mcp_test()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: operator finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: operator failed: {message}")
        return {"CANCELLED"}
