# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for permanently applying confirmed cleanup."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_apply_confirmed_cleanup


APPLY_CONFIRMED_CLEANUP_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.apply_confirmed_cleanup."
    "LCHTMCP_OT_apply_confirmed_cleanup"
)


class LCHTMCP_OT_apply_confirmed_cleanup(Operator):
    """Permanently apply a cleanup workspace soft delete."""

    label = "Apply Deleted Cleanup Permanently"
    description = (
        "Permanent operation. Cannot be restored through Restore Last Delete after apply."
    )

    def invoke(self, context, event: Event) -> set:
        """Execute the permanent cleanup apply."""
        success, message = run_apply_confirmed_cleanup()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: confirmed cleanup apply finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: confirmed cleanup apply failed: {message}")
        return {"CANCELLED"}
