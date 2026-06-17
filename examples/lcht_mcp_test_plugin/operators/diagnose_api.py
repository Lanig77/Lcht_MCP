# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for diagnosing the active LichtFeld runtime API."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.diagnostics import run_lcht_mcp_diagnostics


DIAGNOSE_API_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.diagnose_api.LCHTMCP_OT_diagnose_api"
)


class LCHTMCP_OT_diagnose_api(Operator):
    """Run a safe runtime API diagnostic inside LichtFeld Studio."""

    label = "Diagnose LichtFeld API"
    description = "Inspect the active LichtFeld Studio Python API without mutating the scene"

    def invoke(self, context, event: Event) -> set:
        """Execute the runtime diagnostic."""
        success, message = run_lcht_mcp_diagnostics()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: diagnostic finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: diagnostic failed: {message}")
        return {"CANCELLED"}
