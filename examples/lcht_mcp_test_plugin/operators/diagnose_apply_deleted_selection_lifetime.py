# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for tracing selection ownership across apply_deleted()."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.diagnostics import run_apply_deleted_selection_lifetime_diagnostics


DIAGNOSE_APPLY_DELETED_SELECTION_LIFETIME_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators."
    "diagnose_apply_deleted_selection_lifetime."
    "LCHTMCP_OT_diagnose_apply_deleted_selection_lifetime"
)


class LCHTMCP_OT_diagnose_apply_deleted_selection_lifetime(Operator):
    """Trace native selection tensor ownership across a permanent cleanup apply."""

    label = "Diagnose Apply Deleted Selection Lifetime"
    description = (
        "Permanent operation on the current reversible cleanup delete. "
        "Logs native selection owners before and after apply_deleted()."
    )

    def invoke(self, context, event: Event) -> set:
        """Execute the apply-deleted selection lifetime diagnostic."""
        success, message = run_apply_deleted_selection_lifetime_diagnostics()
        if success:
            lf.log.info(
                "lcht_mcp_test_plugin: apply_deleted selection lifetime diagnostic finished: "
                f"{message}"
            )
            return {"FINISHED"}
        lf.log.error(
            "lcht_mcp_test_plugin: apply_deleted selection lifetime diagnostic failed: "
            f"{message}"
        )
        return {"CANCELLED"}
