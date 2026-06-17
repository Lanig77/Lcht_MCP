# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main panel for running the Lcht_MCP LichtFeld smoke test."""

import lichtfeld as lf

from ..core.runtime_config import snapshot_runtime_config
from ..operators.diagnose_api import DIAGNOSE_API_OPERATOR_ID
from ..operators.diagnose_native_selection import DIAGNOSE_NATIVE_SELECTION_OPERATOR_ID
from ..operators.diagnose_tensor_mask import DIAGNOSE_TENSOR_MASK_OPERATOR_ID
from ..operators.analyze_clusters import ANALYZE_CLUSTERS_OPERATOR_ID
from ..operators.runtime_controls import (
    ARM_SAFE_DELETE_OPERATOR_ID,
    CLUSTER_DISTANCE_DOWN_OPERATOR_ID,
    CLUSTER_DISTANCE_UP_OPERATOR_ID,
    CLUSTER_MIN_SIZE_DOWN_OPERATOR_ID,
    CLUSTER_MIN_SIZE_UP_OPERATOR_ID,
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
)
from ..operators.run_safe_delete_test import RUN_SAFE_DELETE_TEST_OPERATOR_ID
from ..operators.run_test import RUN_TEST_OPERATOR_ID
from ..operators.run_undo_validation import RUN_UNDO_VALIDATION_OPERATOR_ID


class LchtMcpTestPanel(lf.ui.Panel):
    """Panel for launching the Lcht_MCP test operator."""

    id = "lcht_mcp_test_plugin.test_panel"
    label = "Lcht MCP Test"
    space = lf.ui.PanelSpace.MAIN_PANEL_TAB
    order = 31

    def draw(self, layout):
        config = snapshot_runtime_config()
        theme = lf.ui.theme()
        scale = layout.get_dpi_scale()

        layout.text_colored(
            "Safe smoke test for the LichtFeld adapter.",
            theme.palette.text_dim,
        )
        layout.spacing()

        safe_delete_color = (
            (1.0, 0.4, 0.4, 1.0)
            if config.enable_safe_delete
            else (0.4, 1.0, 0.4, 1.0)
        )
        layout.text_colored(
            f"Enable Safe Delete: {'ON' if config.enable_safe_delete else 'OFF'}",
            safe_delete_color,
        )
        confirm_safe_delete_color = (
            (1.0, 0.4, 0.4, 1.0)
            if config.confirm_safe_delete
            else (0.4, 1.0, 0.4, 1.0)
        )
        layout.text_colored(
            f"Confirm Safe Delete: {'ON' if config.confirm_safe_delete else 'OFF'}",
            confirm_safe_delete_color,
        )
        layout.label(
            "Smoke Test Range: "
            f"{config.smoke_test_min_z:.2f} -> {config.smoke_test_max_z:.2f}"
        )
        layout.label(
            "Safe Delete Range: "
            f"{config.safe_delete_min_z:.2f} -> {config.safe_delete_max_z:.2f}"
        )
        layout.label(f"Max Deletable Splats: {config.max_deletable_splats}")
        layout.label(
            "Max Deletable Percentage: "
            f"{config.max_deletable_percentage * 100.0:.2f}%"
        )
        layout.label(
            "Cluster Distance Threshold: "
            f"{config.cluster_distance_threshold:.2f}"
        )
        layout.label(
            "Cluster Min Size: "
            f"{config.cluster_min_cluster_size}"
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

        if layout.button_styled("Arm Safe Delete##arm", "warning", (-1, 30 * scale)):
            lf.ui.ops.invoke(ARM_SAFE_DELETE_OPERATOR_ID)
        if layout.button_styled("Confirm Safe Delete##confirm", "warning", (-1, 30 * scale)):
            lf.ui.ops.invoke(CONFIRM_SAFE_DELETE_OPERATOR_ID)
        if layout.button_styled("Disarm Safe Delete##disarm", "secondary", (-1, 30 * scale)):
            lf.ui.ops.invoke(DISARM_SAFE_DELETE_OPERATOR_ID)

        layout.spacing()
        layout.label("Smoke Test Controls")
        if layout.button_styled("Smoke Min Z -##smoke_min_down", "secondary", (-1, 28 * scale)):
            lf.ui.ops.invoke(SMOKE_MIN_Z_DOWN_OPERATOR_ID)
        if layout.button_styled("Smoke Min Z +##smoke_min_up", "secondary", (-1, 28 * scale)):
            lf.ui.ops.invoke(SMOKE_MIN_Z_UP_OPERATOR_ID)
        if layout.button_styled("Smoke Max Z -##smoke_max_down", "secondary", (-1, 28 * scale)):
            lf.ui.ops.invoke(SMOKE_MAX_Z_DOWN_OPERATOR_ID)
        if layout.button_styled("Smoke Max Z +##smoke_max_up", "secondary", (-1, 28 * scale)):
            lf.ui.ops.invoke(SMOKE_MAX_Z_UP_OPERATOR_ID)

        layout.spacing()
        layout.label("Safe Delete Controls")
        if layout.button_styled(
            "Delete Min Z -##delete_min_down",
            "secondary",
            (-1, 28 * scale),
        ):
            lf.ui.ops.invoke(SAFE_DELETE_MIN_Z_DOWN_OPERATOR_ID)
        if layout.button_styled(
            "Delete Min Z +##delete_min_up",
            "secondary",
            (-1, 28 * scale),
        ):
            lf.ui.ops.invoke(SAFE_DELETE_MIN_Z_UP_OPERATOR_ID)
        if layout.button_styled(
            "Delete Max Z -##delete_max_down",
            "secondary",
            (-1, 28 * scale),
        ):
            lf.ui.ops.invoke(SAFE_DELETE_MAX_Z_DOWN_OPERATOR_ID)
        if layout.button_styled(
            "Delete Max Z +##delete_max_up",
            "secondary",
            (-1, 28 * scale),
        ):
            lf.ui.ops.invoke(SAFE_DELETE_MAX_Z_UP_OPERATOR_ID)
        if layout.button_styled("Max Splats -##splats_down", "secondary", (-1, 28 * scale)):
            lf.ui.ops.invoke(MAX_DELETABLE_SPLATS_DOWN_OPERATOR_ID)
        if layout.button_styled("Max Splats +##splats_up", "secondary", (-1, 28 * scale)):
            lf.ui.ops.invoke(MAX_DELETABLE_SPLATS_UP_OPERATOR_ID)
        if layout.button_styled("Max % -##ratio_down", "secondary", (-1, 28 * scale)):
            lf.ui.ops.invoke(MAX_DELETABLE_PERCENTAGE_DOWN_OPERATOR_ID)
        if layout.button_styled("Max % +##ratio_up", "secondary", (-1, 28 * scale)):
            lf.ui.ops.invoke(MAX_DELETABLE_PERCENTAGE_UP_OPERATOR_ID)

        layout.spacing()
        layout.label("Cluster Analysis Controls")
        if layout.button_styled(
            "Cluster Distance -##cluster_distance_down",
            "secondary",
            (-1, 28 * scale),
        ):
            lf.ui.ops.invoke(CLUSTER_DISTANCE_DOWN_OPERATOR_ID)
        if layout.button_styled(
            "Cluster Distance +##cluster_distance_up",
            "secondary",
            (-1, 28 * scale),
        ):
            lf.ui.ops.invoke(CLUSTER_DISTANCE_UP_OPERATOR_ID)
        if layout.button_styled(
            "Cluster Min Size -##cluster_min_size_down",
            "secondary",
            (-1, 28 * scale),
        ):
            lf.ui.ops.invoke(CLUSTER_MIN_SIZE_DOWN_OPERATOR_ID)
        if layout.button_styled(
            "Cluster Min Size +##cluster_min_size_up",
            "secondary",
            (-1, 28 * scale),
        ):
            lf.ui.ops.invoke(CLUSTER_MIN_SIZE_UP_OPERATOR_ID)

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
            "Analyze Clusters##analyze_clusters",
            "secondary",
            (-1, 34 * scale),
        ):
            lf.ui.ops.invoke(ANALYZE_CLUSTERS_OPERATOR_ID)
        if layout.button_styled(
            "Run Undo Validation##undo_validation",
            "warning",
            (-1, 34 * scale),
        ):
            lf.ui.ops.invoke(RUN_UNDO_VALIDATION_OPERATOR_ID)
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
