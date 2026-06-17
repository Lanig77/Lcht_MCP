# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for validating delete plus undelete in LichtFeld."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_undo_validation


RUN_UNDO_VALIDATION_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.run_undo_validation."
    "LCHTMCP_OT_run_undo_validation"
)


class LCHTMCP_OT_run_undo_validation(Operator):
    """Run a guarded delete plus undelete validation flow."""

    label = "Run Undo Validation"
    description = "Delete a tiny selection and restore it immediately"

    def invoke(self, context, event: Event) -> set:
        """Execute the guarded undo validation."""
        success, message = run_undo_validation()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: undo validation operator finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: undo validation operator failed: {message}")
        return {"CANCELLED"}
