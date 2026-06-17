# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Lcht_MCP test plugin for LichtFeld Studio."""

import lichtfeld as lf

from .panels.test_panel import LchtMcpTestPanel
from .operators.diagnose_api import LCHTMCP_OT_diagnose_api
from .operators.run_test import LCHTMCP_OT_run_test

_classes = [LchtMcpTestPanel, LCHTMCP_OT_run_test, LCHTMCP_OT_diagnose_api]


def on_load():
    """Called when plugin loads."""
    for cls in _classes:
        lf.register_class(cls)
    lf.log.info("lcht_mcp_test_plugin loaded")


def on_unload():
    """Called when plugin unloads."""
    for cls in reversed(_classes):
        lf.unregister_class(cls)
    lf.log.info("lcht_mcp_test_plugin unloaded")


__all__ = [
    "LchtMcpTestPanel",
]
