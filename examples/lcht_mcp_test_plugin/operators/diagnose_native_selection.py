# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for diagnosing the native LichtFeld selection API."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.diagnostics import run_native_selection_api_diagnostics


DIAGNOSE_NATIVE_SELECTION_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.diagnose_native_selection."
    "LCHTMCP_OT_diagnose_native_selection"
)


class LCHTMCP_OT_diagnose_native_selection(Operator):
    """Run a safe native selection API diagnostic inside LichtFeld Studio."""

    label = "Diagnose Native Selection API"
    description = "Try safe LichtFeld native selection entry points and restore selection state"

    def invoke(self, context, event: Event) -> set:
        """Execute the native selection diagnostic."""
        success, message = run_native_selection_api_diagnostics()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: native selection diagnostic finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: native selection diagnostic failed: {message}")
        return {"CANCELLED"}
