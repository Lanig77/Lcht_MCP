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
from .runtime_controls import (
    ARM_SAFE_DELETE_OPERATOR_ID,
    CONFIRM_SAFE_DELETE_OPERATOR_ID,
    DISARM_SAFE_DELETE_OPERATOR_ID,
    MAX_DELETABLE_PERCENTAGE_DOWN_OPERATOR_ID,
    MAX_DELETABLE_PERCENTAGE_UP_OPERATOR_ID,
    MAX_DELETABLE_SPLATS_DOWN_OPERATOR_ID,
    MAX_DELETABLE_SPLATS_UP_OPERATOR_ID,
    SAFE_DELETE_MAX_Z_DOWN_OPERATOR_ID,
    SAFE_DELETE_MAX_Z_UP_OPERATOR_ID,
    SAFE_DELETE_MIN_Z_DOWN_OPERATOR_ID,
    SAFE_DELETE_MIN_Z_UP_OPERATOR_ID,
    SMOKE_MAX_Z_DOWN_OPERATOR_ID,
    SMOKE_MAX_Z_UP_OPERATOR_ID,
    SMOKE_MIN_Z_DOWN_OPERATOR_ID,
    SMOKE_MIN_Z_UP_OPERATOR_ID,
    LCHTMCP_OT_arm_safe_delete,
    LCHTMCP_OT_confirm_safe_delete,
    LCHTMCP_OT_disarm_safe_delete,
    LCHTMCP_OT_max_deletable_percentage_down,
    LCHTMCP_OT_max_deletable_percentage_up,
    LCHTMCP_OT_max_deletable_splats_down,
    LCHTMCP_OT_max_deletable_splats_up,
    LCHTMCP_OT_safe_delete_max_z_down,
    LCHTMCP_OT_safe_delete_max_z_up,
    LCHTMCP_OT_safe_delete_min_z_down,
    LCHTMCP_OT_safe_delete_min_z_up,
    LCHTMCP_OT_smoke_max_z_down,
    LCHTMCP_OT_smoke_max_z_up,
    LCHTMCP_OT_smoke_min_z_down,
    LCHTMCP_OT_smoke_min_z_up,
)
from .run_safe_delete_test import (
    LCHTMCP_OT_run_safe_delete_test,
    RUN_SAFE_DELETE_TEST_OPERATOR_ID,
)
from .run_test import LCHTMCP_OT_run_test, RUN_TEST_OPERATOR_ID
from .run_undo_validation import (
    LCHTMCP_OT_run_undo_validation,
    RUN_UNDO_VALIDATION_OPERATOR_ID,
)

__all__ = [
    "ARM_SAFE_DELETE_OPERATOR_ID",
    "CONFIRM_SAFE_DELETE_OPERATOR_ID",
    "DIAGNOSE_API_OPERATOR_ID",
    "DIAGNOSE_NATIVE_SELECTION_OPERATOR_ID",
    "DIAGNOSE_TENSOR_MASK_OPERATOR_ID",
    "DISARM_SAFE_DELETE_OPERATOR_ID",
    "MAX_DELETABLE_PERCENTAGE_DOWN_OPERATOR_ID",
    "MAX_DELETABLE_PERCENTAGE_UP_OPERATOR_ID",
    "MAX_DELETABLE_SPLATS_DOWN_OPERATOR_ID",
    "MAX_DELETABLE_SPLATS_UP_OPERATOR_ID",
    "SAFE_DELETE_MAX_Z_DOWN_OPERATOR_ID",
    "SAFE_DELETE_MAX_Z_UP_OPERATOR_ID",
    "SAFE_DELETE_MIN_Z_DOWN_OPERATOR_ID",
    "SAFE_DELETE_MIN_Z_UP_OPERATOR_ID",
    "SMOKE_MAX_Z_DOWN_OPERATOR_ID",
    "SMOKE_MAX_Z_UP_OPERATOR_ID",
    "SMOKE_MIN_Z_DOWN_OPERATOR_ID",
    "SMOKE_MIN_Z_UP_OPERATOR_ID",
    "LCHTMCP_OT_arm_safe_delete",
    "LCHTMCP_OT_confirm_safe_delete",
    "LCHTMCP_OT_diagnose_api",
    "LCHTMCP_OT_diagnose_native_selection",
    "LCHTMCP_OT_diagnose_tensor_mask",
    "LCHTMCP_OT_disarm_safe_delete",
    "LCHTMCP_OT_max_deletable_percentage_down",
    "LCHTMCP_OT_max_deletable_percentage_up",
    "LCHTMCP_OT_max_deletable_splats_down",
    "LCHTMCP_OT_max_deletable_splats_up",
    "LCHTMCP_OT_run_safe_delete_test",
    "LCHTMCP_OT_run_test",
    "LCHTMCP_OT_run_undo_validation",
    "LCHTMCP_OT_safe_delete_max_z_down",
    "LCHTMCP_OT_safe_delete_max_z_up",
    "LCHTMCP_OT_safe_delete_min_z_down",
    "LCHTMCP_OT_safe_delete_min_z_up",
    "LCHTMCP_OT_smoke_max_z_down",
    "LCHTMCP_OT_smoke_max_z_up",
    "LCHTMCP_OT_smoke_min_z_down",
    "LCHTMCP_OT_smoke_min_z_up",
    "RUN_SAFE_DELETE_TEST_OPERATOR_ID",
    "RUN_TEST_OPERATOR_ID",
    "RUN_UNDO_VALIDATION_OPERATOR_ID",
]
