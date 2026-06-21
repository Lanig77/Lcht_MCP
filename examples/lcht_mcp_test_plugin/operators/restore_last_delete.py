# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for restoring the last reversible delete."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_restore_last_delete


RESTORE_LAST_DELETE_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.restore_last_delete."
    "LCHTMCP_OT_restore_last_delete"
)


class LCHTMCP_OT_restore_last_delete(Operator):
    """Restore the last reversible delete from the current session."""

    label = "Restore Last Delete"
    description = "Restore the last reversible soft delete"

    def invoke(self, context, event: Event) -> set:
        success, message = run_restore_last_delete()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: restore last delete finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: restore last delete failed: {message}")
        return {"CANCELLED"}
