# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operator entry point for diagnosing LichtFeld tensor mask construction."""

import lichtfeld as lf
from lfs_plugins.types import Event, Operator

from ..core.diagnostics import run_tensor_mask_construction_diagnostics


DIAGNOSE_TENSOR_MASK_OPERATOR_ID = (
    "lfs_plugins.lcht_mcp_test_plugin.operators.diagnose_tensor_mask."
    "LCHTMCP_OT_diagnose_tensor_mask"
)


class LCHTMCP_OT_diagnose_tensor_mask(Operator):
    """Run a safe tensor-mask construction diagnostic inside LichtFeld Studio."""

    label = "Diagnose Tensor Mask Construction"
    description = "Try safe LichtFeld selection-mask tensor construction strategies"

    def invoke(self, context, event: Event) -> set:
        """Execute the tensor-mask diagnostic."""
        success, message = run_tensor_mask_construction_diagnostics()
        if success:
            lf.log.info(f"lcht_mcp_test_plugin: tensor diagnostic finished: {message}")
            return {"FINISHED"}
        lf.log.error(f"lcht_mcp_test_plugin: tensor diagnostic failed: {message}")
        return {"CANCELLED"}
