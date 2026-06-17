# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main panel for running the Lcht_MCP LichtFeld smoke test."""

import lichtfeld as lf

from ..core.test_runner import DELETE_SELECTED, ENABLE_SAFE_DELETE, MAX_Z, MIN_Z
from ..operators.diagnose_api import DIAGNOSE_API_OPERATOR_ID
from ..operators.diagnose_native_selection import DIAGNOSE_NATIVE_SELECTION_OPERATOR_ID
from ..operators.diagnose_tensor_mask import DIAGNOSE_TENSOR_MASK_OPERATOR_ID
from ..operators.run_safe_delete_test import RUN_SAFE_DELETE_TEST_OPERATOR_ID
from ..operators.run_test import RUN_TEST_OPERATOR_ID


class LchtMcpTestPanel(lf.ui.Panel):
    """Panel for launching the Lcht_MCP test operator."""

    id = "lcht_mcp_test_plugin.test_panel"
    label = "Lcht MCP Test"
    space = lf.ui.PanelSpace.MAIN_PANEL_TAB
    order = 31

    def draw(self, layout):
        theme = lf.ui.theme()
        scale = layout.get_dpi_scale()

        layout.text_colored(
            "Safe smoke test for the LichtFeld adapter.",
            theme.palette.text_dim,
        )
        layout.spacing()

        layout.label(f"Height Range: {MIN_Z:.2f} -> {MAX_Z:.2f}")
        delete_color = (
            (1.0, 0.4, 0.4, 1.0)
            if DELETE_SELECTED
            else (0.4, 1.0, 0.4, 1.0)
        )
        layout.text_colored(
            f"Delete Selected: {'ON' if DELETE_SELECTED else 'OFF'}",
            delete_color,
        )
        safe_delete_color = (
            (1.0, 0.4, 0.4, 1.0)
            if ENABLE_SAFE_DELETE
            else (0.4, 1.0, 0.4, 1.0)
        )
        layout.text_colored(
            f"Enable Safe Delete: {'ON' if ENABLE_SAFE_DELETE else 'OFF'}",
            safe_delete_color,
        )
        layout.text_colored(
            "Check the LichtFeld log for splat_count, bounding_box and selected_count.",
            theme.palette.text_dim,
        )
        layout.text_colored(
            "Use Diagnose LichtFeld API to inspect the active runtime scene/model path.",
            theme.palette.text_dim,
        )
        layout.text_colored(
            "Use Diagnose Tensor Mask Construction to test native selection tensor creation.",
            theme.palette.text_dim,
        )
        layout.text_colored(
            "Use Diagnose Native Selection API to try index-based selection entry points.",
            theme.palette.text_dim,
        )
        layout.spacing()

        if layout.button_styled("Run Lcht MCP Test##run", "primary", (-1, 34 * scale)):
            lf.ui.ops.invoke(RUN_TEST_OPERATOR_ID)
        if layout.button_styled(
            "Run Safe Delete Test##safe_delete",
            "warning",
            (-1, 34 * scale),
        ):
            lf.ui.ops.invoke(RUN_SAFE_DELETE_TEST_OPERATOR_ID)
        if layout.button_styled(
            "Diagnose LichtFeld API##diagnose",
            "secondary",
            (-1, 34 * scale),
        ):
            lf.ui.ops.invoke(DIAGNOSE_API_OPERATOR_ID)
        if layout.button_styled(
            "Diagnose Tensor Mask Construction##tensor",
            "secondary",
            (-1, 34 * scale),
        ):
            lf.ui.ops.invoke(DIAGNOSE_TENSOR_MASK_OPERATOR_ID)
        if layout.button_styled(
            "Diagnose Native Selection API##native",
            "secondary",
            (-1, 34 * scale),
        ):
            lf.ui.ops.invoke(DIAGNOSE_NATIVE_SELECTION_OPERATOR_ID)
