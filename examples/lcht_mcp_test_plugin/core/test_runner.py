# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe smoke-test runner for the Lcht_MCP LichtFeld adapter."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import lichtfeld as lf


PLUGIN_NAME = "lcht_mcp_test_plugin"
MIN_Z = 0.0
MAX_Z = 2.0
DELETE_SELECTED = False
REPO_ROOT_HINT = Path.home() / "Documents" / "MCP GS" / "Lcht_MCP"
SELECTION_RANGES: tuple[tuple[str, float | None, float | None], ...] = (
    ("range_1", 0.0, 2.0),
    ("range_2", 0.90, 1.10),
    ("range_3", 1.00, 1.05),
    ("range_4_empty", None, None),
)


def _log_info(message: str) -> None:
    lf.log.info(f"{PLUGIN_NAME}: {message}")


def _log_error(message: str) -> None:
    lf.log.error(f"{PLUGIN_NAME}: {message}")


def _candidate_repo_roots() -> list[Path]:
    candidates: list[Path] = []
    environment_root = os.environ.get("LCHT_MCP_REPO_ROOT")
    if environment_root:
        candidates.append(Path(environment_root).expanduser())
    candidates.append(Path(__file__).resolve().parents[3])
    candidates.append(REPO_ROOT_HINT.expanduser())
    return candidates


def _configure_import_path() -> Path:
    for candidate in _candidate_repo_roots():
        src_path = candidate / "src"
        package_path = src_path / "lichtfeld_mcp"
        if not package_path.exists():
            continue
        normalized_src = str(src_path)
        if normalized_src not in sys.path:
            sys.path.insert(0, normalized_src)
        return candidate
    raise RuntimeError(
        "Could not locate the Lcht_MCP repository. "
        "Set LCHT_MCP_REPO_ROOT or update REPO_ROOT_HINT in core/test_runner.py."
    )


def _build_adapter():
    repository_root = _configure_import_path()
    from lichtfeld_mcp.adapters.lichtfeld import LichtfeldAdapter

    return LichtfeldAdapter(), repository_root


def _clear_selection() -> None:
    deselect_all = getattr(lf, "deselect_all", None)
    if callable(deselect_all):
        deselect_all()
        return

    get_scene = getattr(lf, "get_scene", None)
    if callable(get_scene):
        scene = get_scene()
        clear_selection = getattr(scene, "clear_selection", None) if scene is not None else None
        if callable(clear_selection):
            clear_selection()
            return

    raise RuntimeError("Could not clear the native LichtFeld selection.")


def _log_selection_report(
    *,
    min_z: float | None,
    max_z: float | None,
    selected_count: int,
    total_splats: int,
) -> None:
    percentage = 0.0 if total_splats <= 0 else (selected_count / total_splats) * 100.0
    _log_info("----------------------------------------")
    _log_info(f"Selection range: min_z={min_z} max_z={max_z}")
    _log_info(f"selected_count={selected_count}")
    _log_info(f"percentage_of_total={percentage:.6f}%")
    _log_info("----------------------------------------")


def run_lcht_mcp_test() -> tuple[bool, str]:
    """Run a safe adapter smoke test inside LichtFeld Studio."""
    _log_info(
        f"Starting safe adapter smoke test with MIN_Z={MIN_Z}, MAX_Z={MAX_Z}, "
        f"DELETE_SELECTED={DELETE_SELECTED}."
    )

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    try:
        stats = adapter.get_stats()
        _log_info(f"splat_count={stats.splat_count}")
        _log_info(f"bounding_box={stats.bounds}")
    except Exception as exc:
        message = f"get_stats failed: {exc}"
        _log_error(message)
        return False, message

    try:
        empty_min_z = stats.bounds.max.z + 1.0
        empty_max_z = stats.bounds.max.z + 2.0
        validation_ranges = (
            (SELECTION_RANGES[0][0], MIN_Z, MAX_Z),
            SELECTION_RANGES[1],
            SELECTION_RANGES[2],
            (SELECTION_RANGES[3][0], empty_min_z, empty_max_z),
        )

        for range_name, min_z, max_z in validation_ranges:
            _log_info(f"Running {range_name}: min_z={min_z}, max_z={max_z}")
            selection = adapter.select_by_height(z_min=min_z, z_max=max_z)
            _log_selection_report(
                min_z=min_z,
                max_z=max_z,
                selected_count=selection.selected_count,
                total_splats=stats.splat_count,
            )
            if selection.selected_count > 0:
                refreshed_stats = adapter.get_stats()
                if refreshed_stats.selected_count != selection.selected_count:
                    raise RuntimeError(
                        "Selection validation mismatch: "
                        f"SelectionResult.selected_count={selection.selected_count} "
                        f"but adapter.get_stats().selected_count={refreshed_stats.selected_count}."
                    )
                _log_info(
                    "validated selected_count via get_stats: "
                    f"{refreshed_stats.selected_count}"
                )
    except Exception as exc:
        message = f"select_by_height failed: {exc}"
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after failure.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after failure: {clear_exc}")
        return False, message

    try:
        _clear_selection()
        _log_info("Selection cleared before exit.")
    except Exception as exc:
        message = f"selection clear failed: {exc}"
        _log_error(message)
        return False, message

    message = "Validation complete. DELETE_SELECTED=False; selection cleared."
    _log_info(message)
    return True, message
