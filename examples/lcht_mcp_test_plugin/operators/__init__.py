# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operators for the Lcht_MCP test plugin."""

from .diagnose_api import DIAGNOSE_API_OPERATOR_ID, LCHTMCP_OT_diagnose_api
from .diagnose_native_selection import (
    DIAGNOSE_NATIVE_SELECTION_OPERATOR_ID,
    LCHTMCP_OT_diagnose_native_selection,
)
from .diagnose_tensor_mask import (
    DIAGNOSE_TENSOR_MASK_OPERATOR_ID,
    LCHTMCP_OT_diagnose_tensor_mask,
)
from .run_safe_delete_test import (
    LCHTMCP_OT_run_safe_delete_test,
    RUN_SAFE_DELETE_TEST_OPERATOR_ID,
)
from .run_test import LCHTMCP_OT_run_test, RUN_TEST_OPERATOR_ID

__all__ = [
    "DIAGNOSE_API_OPERATOR_ID",
    "DIAGNOSE_NATIVE_SELECTION_OPERATOR_ID",
    "DIAGNOSE_TENSOR_MASK_OPERATOR_ID",
    "LCHTMCP_OT_diagnose_api",
    "LCHTMCP_OT_diagnose_native_selection",
    "LCHTMCP_OT_diagnose_tensor_mask",
    "LCHTMCP_OT_run_safe_delete_test",
    "LCHTMCP_OT_run_test",
    "RUN_SAFE_DELETE_TEST_OPERATOR_ID",
    "RUN_TEST_OPERATOR_ID",
]
