# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for non-destructive cleanup preset comparison."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.test_runner import run_compare_cleanup_presets


COMPARE_CLEANUP_PRESETS_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.compare_cleanup_presets."
    "LCHTMCP_OT_compare_cleanup_presets"
)


class LCHTMCP_OT_compare_cleanup_presets(Operator):
    """Compare cleanup presets using the current sampled analysis without mutating the scene."""

    label = "Compare Cleanup Presets"
    description = "Compare Conservative, Balanced and Aggressive cleanup presets without changing the scene"

    def invoke(self, context, event: Event) -> set:
        success, message = run_compare_cleanup_presets()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: cleanup preset comparison completed: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: cleanup preset comparison failed: {message}")
        return {"CANCELLED"}
