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
        _log_info(f"select_by_height range: min_z={MIN_Z}, max_z={MAX_Z}")
        selection = adapter.select_by_height(z_min=MIN_Z, z_max=MAX_Z)
        _log_info(f"selected_count={selection.selected_count}")
    except Exception as exc:
        message = f"select_by_height failed: {exc}"
        _log_error(message)
        return False, message

    if not DELETE_SELECTED:
        message = "delete_selection skipped because DELETE_SELECTED=False."
        _log_info(message)
        return True, message

    try:
        delete_result = adapter.delete_selection()
        message = f"delete_selection: ok={delete_result.ok} message={delete_result.message}"
        _log_info(message)
        return delete_result.ok, message
    except Exception as exc:
        message = f"delete_selection failed: {exc}"
        _log_error(message)
        return False, message
