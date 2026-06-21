# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe smoke-test runner for the Lcht_MCP LichtFeld adapter."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import lichtfeld as lf

from .runtime_config import (
    set_cleanup_preview_report_lines,
    set_cleanup_preview_summary,
    set_cleanup_workspace_report_lines,
    set_cleanup_workspace_summary,
    set_scene_analysis_report_lines,
    snapshot_runtime_config,
)


PLUGIN_NAME = "lcht_mcp_test_plugin"
DELETE_SELECTED = False
VERIFY_STATS_AFTER_DELETE = False
REPO_ROOT_HINT = Path.home() / "Documents" / "MCP GS" / "Lcht_MCP"
SELECTION_RANGES: tuple[tuple[str, float | None, float | None], ...] = (
    ("range_1", 0.0, 2.0),
    ("range_2", 0.90, 1.10),
    ("range_3", 1.00, 1.05),
    ("range_4_empty", None, None),
)
_CACHED_ADAPTER = None
_CACHED_REPOSITORY_ROOT: Path | None = None


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
    global _CACHED_ADAPTER, _CACHED_REPOSITORY_ROOT
    if _CACHED_ADAPTER is not None and _CACHED_REPOSITORY_ROOT is not None:
        return _CACHED_ADAPTER, _CACHED_REPOSITORY_ROOT
    repository_root = _configure_import_path()
    from lichtfeld_mcp.adapters.lichtfeld import LichtfeldAdapter

    _CACHED_ADAPTER = LichtfeldAdapter()
    _CACHED_REPOSITORY_ROOT = repository_root
    return _CACHED_ADAPTER, _CACHED_REPOSITORY_ROOT


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


def _selected_percentage(selected_count: int, total_splats: int) -> float:
    if total_splats <= 0:
        return 0.0
    return selected_count / total_splats


def _cleanup_workspace_kwargs(config) -> dict[str, object]:
    return {
        "voxel_size": config.voxel_size,
        "min_voxel_cluster_size": config.voxel_min_cluster_size,
        "outlier_distance": config.cleanup_outlier_distance,
        "cleanup_aggressiveness": config.cleanup_aggressiveness,
    }


def _materialize_sequence(value: object) -> list[object] | None:
    current = value
    for method_name in ("detach", "cpu"):
        method = getattr(current, method_name, None)
        if callable(method):
            current = method()
    numpy_method = getattr(current, "numpy", None)
    if callable(numpy_method):
        current = numpy_method()
    tolist_method = getattr(current, "tolist", None)
    if callable(tolist_method):
        current = tolist_method()
    try:
        return list(current)
    except TypeError:
        return None


def _log_soft_delete_runtime_state() -> None:
    try:
        get_scene = getattr(lf, "get_scene", None)
        if not callable(get_scene):
            _log_info("Soft delete state inspection skipped: lichtfeld.get_scene() is unavailable.")
            return
        scene = get_scene()
        if scene is None:
            _log_info("Soft delete state inspection skipped: no active scene.")
            return
        combined_model = getattr(scene, "combined_model", None)
        if not callable(combined_model):
            _log_info("Soft delete state inspection skipped: combined_model() is unavailable.")
            return
        model = combined_model()
        if model is None:
            _log_info("Soft delete state inspection skipped: no combined model.")
            return

        has_deleted_mask = getattr(model, "has_deleted_mask", None)
        if callable(has_deleted_mask):
            try:
                _log_info(f"model.has_deleted_mask()={has_deleted_mask()}")
            except Exception as exc:
                _log_info(f"model.has_deleted_mask() failed: {exc}")

        deleted_mask = getattr(model, "deleted", None)
        if deleted_mask is None:
            _log_info("model.deleted is unavailable.")
            return
        deleted_items = _materialize_sequence(deleted_mask)
        if deleted_items is None:
            _log_info(f"model.deleted type={type(deleted_mask).__name__}; deleted_count unavailable.")
            return
        deleted_count = sum(bool(item) for item in deleted_items)
        _log_info(
            f"model.deleted type={type(deleted_mask).__name__} deleted_count={deleted_count}"
        )
    except Exception as exc:
        _log_info(f"Soft delete state inspection failed: {exc}")


def _restore_deleted_splats(adapter) -> None:
    restore_last_delete = getattr(adapter, "restore_last_delete", None)
    if not callable(restore_last_delete):
        raise RuntimeError("LichtFeldAdapter does not expose restore_last_delete() for undo validation.")
    restore_result = restore_last_delete()
    _log_info(f"restore_last_delete ok={restore_result.ok} message={restore_result.message}")
    if not restore_result.ok:
        raise RuntimeError(restore_result.message)


def run_scene_analysis() -> tuple[bool, str]:
    """Run a unified read-only scene analysis report on the active LichtFeld scene."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting scene analysis with "
        f"voxel_size={config.voxel_size:.4f}, "
        f"min_voxel_cluster_size={config.voxel_min_cluster_size}, "
        f"max_cluster_analysis_splats={config.max_cluster_analysis_splats}, "
        "abort_if_splat_count_above_limit="
        f"{config.abort_if_splat_count_above_limit}."
    )

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Scene analysis adapter setup failed: {exc}"
        _log_error(message)
        set_scene_analysis_report_lines([message])
        return False, message

    analyze_scene = getattr(adapter, "analyze_scene", None)
    if not callable(analyze_scene):
        message = "LichtfeldAdapter does not expose analyze_scene()."
        _log_error(message)
        set_scene_analysis_report_lines([message])
        return False, message

    try:
        from lichtfeld_mcp.core.scene_analysis import format_scene_analysis_report
    except Exception as exc:
        message = f"Scene analysis formatter import failed: {exc}"
        _log_error(message)
        set_scene_analysis_report_lines([message])
        return False, message

    try:
        report = analyze_scene(
            voxel_size=config.voxel_size,
            min_voxel_cluster_size=config.voxel_min_cluster_size,
            max_splats=config.max_cluster_analysis_splats,
            abort_if_above_limit=config.abort_if_splat_count_above_limit,
        )
    except Exception as exc:
        message = f"Scene analysis failed: {exc}"
        _log_error(message)
        set_scene_analysis_report_lines([message])
        return False, message

    formatted_report = format_scene_analysis_report(report)
    report_lines = formatted_report.splitlines()
    set_scene_analysis_report_lines(report_lines)
    set_cleanup_preview_report_lines([])
    set_cleanup_preview_summary(None)
    set_cleanup_workspace_report_lines([])
    set_cleanup_workspace_summary(None)
    for line in report_lines:
        _log_info(line)
    _log_info(f"analysis_time_seconds={report.analysis_time:.3f}")
    _log_info(f"Scene analysis complete. Quality score: {report.quality_score}")
    return True, f"Scene analysis complete. Quality score: {report.quality_score}"


def run_preview_cleanup_candidates() -> tuple[bool, str]:
    """Run a non-destructive cleanup candidate preview from scene analysis."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting cleanup candidate preview with "
        f"voxel_size={config.voxel_size:.4f}, "
        f"min_voxel_cluster_size={config.voxel_min_cluster_size}, "
        f"max_cluster_analysis_splats={config.max_cluster_analysis_splats}, "
        "abort_if_splat_count_above_limit="
        f"{config.abort_if_splat_count_above_limit}."
    )

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Cleanup preview adapter setup failed: {exc}"
        _log_error(message)
        set_cleanup_preview_report_lines([message])
        set_cleanup_preview_summary(None)
        return False, message

    preview_cleanup_candidates = getattr(adapter, "preview_cleanup_candidates", None)
    if not callable(preview_cleanup_candidates):
        message = "LichtfeldAdapter does not expose preview_cleanup_candidates()."
        _log_error(message)
        set_cleanup_preview_report_lines([message])
        set_cleanup_preview_summary(None)
        return False, message

    try:
        from lichtfeld_mcp.core.scene_analysis import format_cleanup_candidate_summary
    except Exception as exc:
        message = f"Cleanup preview formatter import failed: {exc}"
        _log_error(message)
        set_cleanup_preview_report_lines([message])
        set_cleanup_preview_summary(None)
        return False, message

    try:
        summary = preview_cleanup_candidates(
            voxel_size=config.voxel_size,
            min_voxel_cluster_size=config.voxel_min_cluster_size,
            max_splats=config.max_cluster_analysis_splats,
            abort_if_above_limit=config.abort_if_splat_count_above_limit,
        )
    except Exception as exc:
        message = f"Cleanup preview failed: {exc}"
        _log_error(message)
        set_cleanup_preview_report_lines([message])
        set_cleanup_preview_summary(None)
        return False, message

    formatted_summary = format_cleanup_candidate_summary(summary)
    summary_lines = formatted_summary.splitlines()
    set_cleanup_preview_report_lines(summary_lines)
    set_cleanup_preview_summary(summary.to_dict())
    for line in summary_lines:
        _log_info(line)
    _log_info(f"analysis_time_seconds={summary.analysis_time:.3f}")
    _log_info(
        "Cleanup preview complete. "
        f"Candidate groups: {summary.candidate_group_count}"
    )
    return True, f"Cleanup preview complete. Candidate groups: {summary.candidate_group_count}"


def run_preview_cleanup_selection() -> tuple[bool, str]:
    """Build and display a native cleanup selection preview without mutating splats."""
    success, message = run_preview_cleanup_candidates()
    if not success:
        return success, message

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Cleanup selection preview adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    preview_cleanup_selection = getattr(adapter, "preview_cleanup_selection", None)
    if not callable(preview_cleanup_selection):
        message = "LichtfeldAdapter does not expose preview_cleanup_selection()."
        _log_error(message)
        return False, message

    try:
        result = preview_cleanup_selection()
    except Exception as exc:
        message = f"Cleanup selection preview failed: {exc}"
        _log_error(message)
        return False, message

    _log_info("Selection Preview")
    _log_info(f"selected splats={result.selected_count}")
    _log_info(f"selection percentage={result.selection_percentage * 100.0:.6f}%")
    _log_info(f"selection mode={result.selection_mode}")
    _log_info(f"selection source={result.selection_source}")
    _log_info(f"selection approximation={'approximate' if result.approximate else 'exact'}")
    _log_info(result.message)
    return True, result.message


def run_open_cleanup_workspace() -> tuple[bool, str]:
    """Open an interactive cleanup workspace and build the first native preview."""
    config = snapshot_runtime_config()
    _log_info(
        "Opening cleanup workspace with "
        f"voxel_size={config.voxel_size:.4f}, "
        f"min_voxel_cluster_size={config.voxel_min_cluster_size}, "
        f"outlier_distance={config.cleanup_outlier_distance:.4f}, "
        f"cleanup_aggressiveness={config.cleanup_aggressiveness:.4f}."
    )

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Cleanup workspace adapter setup failed: {exc}"
        _log_error(message)
        set_cleanup_workspace_report_lines([message])
        set_cleanup_workspace_summary(None)
        return False, message

    open_cleanup_workspace = getattr(adapter, "open_cleanup_workspace", None)
    if not callable(open_cleanup_workspace):
        message = "LichtfeldAdapter does not expose open_cleanup_workspace()."
        _log_error(message)
        set_cleanup_workspace_report_lines([message])
        set_cleanup_workspace_summary(None)
        return False, message

    try:
        from lichtfeld_mcp.core.cleanup_workspace import format_cleanup_workspace
    except Exception as exc:
        message = f"Cleanup workspace formatter import failed: {exc}"
        _log_error(message)
        set_cleanup_workspace_report_lines([message])
        set_cleanup_workspace_summary(None)
        return False, message

    try:
        workspace = open_cleanup_workspace(**_cleanup_workspace_kwargs(config))
    except Exception as exc:
        message = f"Cleanup workspace failed: {exc}"
        _log_error(message)
        set_cleanup_workspace_report_lines([message])
        set_cleanup_workspace_summary(None)
        return False, message

    formatted_workspace = format_cleanup_workspace(workspace)
    workspace_lines = formatted_workspace.splitlines()
    set_cleanup_workspace_report_lines(workspace_lines)
    set_cleanup_workspace_summary(workspace.to_dict())
    set_cleanup_preview_report_lines([])
    set_cleanup_preview_summary(workspace.cleanup_candidate_summary.to_dict())
    for line in workspace_lines:
        _log_info(line)
    _log_info(f"workspace_update_time={workspace.workspace_update_time:.6f}")
    _log_info(f"selection_update_time={workspace.selection_update_time:.6f}")
    _log_info(f"estimated_sample_reuse={workspace.estimated_sample_reuse:.2f}")
    return True, "Cleanup workspace opened."


def run_update_cleanup_workspace() -> tuple[bool, str]:
    """Refresh the cleanup workspace preview from the latest sampled analysis."""
    config = snapshot_runtime_config()
    _log_info(
        "Updating cleanup workspace with "
        f"voxel_size={config.voxel_size:.4f}, "
        f"min_voxel_cluster_size={config.voxel_min_cluster_size}, "
        f"outlier_distance={config.cleanup_outlier_distance:.4f}, "
        f"cleanup_aggressiveness={config.cleanup_aggressiveness:.4f}."
    )

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Cleanup workspace adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    update_cleanup_workspace = getattr(adapter, "update_cleanup_workspace", None)
    if not callable(update_cleanup_workspace):
        message = "LichtfeldAdapter does not expose update_cleanup_workspace()."
        _log_error(message)
        return False, message

    try:
        from lichtfeld_mcp.core.cleanup_workspace import format_cleanup_workspace
    except Exception as exc:
        message = f"Cleanup workspace formatter import failed: {exc}"
        _log_error(message)
        return False, message

    try:
        workspace = update_cleanup_workspace(**_cleanup_workspace_kwargs(config))
    except Exception as exc:
        message = f"Cleanup workspace update failed: {exc}"
        _log_error(message)
        return False, message

    formatted_workspace = format_cleanup_workspace(workspace)
    workspace_lines = formatted_workspace.splitlines()
    set_cleanup_workspace_report_lines(workspace_lines)
    set_cleanup_workspace_summary(workspace.to_dict())
    set_cleanup_preview_summary(workspace.cleanup_candidate_summary.to_dict())
    for line in workspace_lines:
        _log_info(line)
    _log_info(f"workspace_update_time={workspace.workspace_update_time:.6f}")
    _log_info(f"selection_update_time={workspace.selection_update_time:.6f}")
    _log_info(f"estimated_sample_reuse={workspace.estimated_sample_reuse:.2f}")
    return True, "Cleanup workspace updated."


def run_reset_cleanup_workspace() -> tuple[bool, str]:
    """Clear the native cleanup preview selection and invalidate the active workspace."""
    _log_info("Resetting cleanup workspace preview.")
    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Cleanup workspace adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    reset_cleanup_workspace = getattr(adapter, "reset_cleanup_workspace", None)
    if not callable(reset_cleanup_workspace):
        message = "LichtfeldAdapter does not expose reset_cleanup_workspace()."
        _log_error(message)
        return False, message

    try:
        result = reset_cleanup_workspace()
    except Exception as exc:
        message = f"Cleanup workspace reset failed: {exc}"
        _log_error(message)
        return False, message

    set_cleanup_workspace_report_lines([])
    set_cleanup_workspace_summary(None)
    set_cleanup_preview_report_lines([])
    set_cleanup_preview_summary(None)
    _log_info(result.message)
    return result.ok, result.message


def run_soft_delete_cleanup_selection() -> tuple[bool, str]:
    """Soft-delete the current cleanup workspace selection without permanent apply."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting cleanup workspace soft delete with "
        f"ENABLE_SAFE_DELETE={config.enable_safe_delete}, "
        f"CONFIRM_SAFE_DELETE={config.confirm_safe_delete}, "
        "thresholds=("
        f"max_count={config.max_deletable_splats}, "
        f"max_ratio={config.max_deletable_percentage:.6f})."
    )

    if not config.enable_safe_delete:
        message = (
            "Cleanup workspace soft delete is disabled because ENABLE_SAFE_DELETE=False. "
            "No destructive action was performed."
        )
        _log_info(message)
        return True, message

    if not config.confirm_safe_delete:
        message = (
            "Cleanup workspace soft delete is armed but not confirmed because "
            "ENABLE_SAFE_DELETE=True and CONFIRM_SAFE_DELETE=False. "
            "No destructive action was performed."
        )
        _log_info(message)
        return True, message

    workspace_summary = config.last_cleanup_workspace_summary
    if workspace_summary is None:
        message = "No cleanup workspace is active. Open Cleanup Workspace first."
        _log_error(message)
        return False, message

    selected_count = int(workspace_summary.get("selected_count", 0))
    total_splats = int(
        workspace_summary.get(
            "scene_profile",
            {},
        ).get("total_splats", workspace_summary.get("total_splats", 0))
        if isinstance(workspace_summary.get("scene_profile"), dict)
        else workspace_summary.get("total_splats", 0)
    )
    selected_ratio = _selected_percentage(selected_count, total_splats)
    _log_info(f"initial_splat_count={total_splats}")
    _log_info(f"selected_count={selected_count}")
    _log_info(f"selected_percentage={selected_ratio * 100.0:.6f}%")

    if selected_count <= 0:
        message = "Cleanup workspace soft delete refused: selected_count == 0."
        _log_error(message)
        return False, message
    if selected_count > config.max_deletable_splats:
        message = (
            "Cleanup workspace soft delete refused: "
            f"selected_count={selected_count} exceeds "
            f"SAFE_DELETE_MAX_COUNT={config.max_deletable_splats}."
        )
        _log_error(message)
        return False, message
    if selected_ratio > config.max_deletable_percentage:
        message = (
            "Cleanup workspace soft delete refused: "
            f"selected_ratio={selected_ratio:.6f} exceeds "
            f"SAFE_DELETE_MAX_RATIO={config.max_deletable_percentage:.6f}."
        )
        _log_error(message)
        return False, message

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Cleanup workspace soft delete adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    soft_delete_current_cleanup_selection = getattr(
        adapter,
        "soft_delete_current_cleanup_selection",
        None,
    )
    if not callable(soft_delete_current_cleanup_selection):
        message = "LichtfeldAdapter does not expose soft_delete_current_cleanup_selection()."
        _log_error(message)
        return False, message

    try:
        result = soft_delete_current_cleanup_selection()
    except Exception as exc:
        message = f"Cleanup workspace soft delete failed: {exc}"
        _log_error(message)
        return False, message

    _log_info(f"soft_delete ok={result.ok}")
    _log_info(f"restore available={result.restore_available}")
    _log_info(
        "Cleanup workspace soft delete complete. "
        "Reversible only. Does not call apply_deleted(). "
        "Use Restore Last Delete to undo."
    )
    set_cleanup_workspace_report_lines([])
    set_cleanup_workspace_summary(None)
    return result.ok, result.message


def run_restore_last_delete() -> tuple[bool, str]:
    """Restore the last reversible delete without applying permanent changes."""
    _log_info("Starting restore_last_delete.")
    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Restore last delete adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    restore_last_delete = getattr(adapter, "restore_last_delete", None)
    if not callable(restore_last_delete):
        message = "LichtfeldAdapter does not expose restore_last_delete()."
        _log_error(message)
        return False, message

    try:
        result = restore_last_delete()
    except Exception as exc:
        message = f"Restore last delete failed: {exc}"
        _log_error(message)
        return False, message

    _log_info(result.message)
    return result.ok, result.message


def run_soft_delete_cleanup_preview() -> tuple[bool, str]:
    """Soft-delete the last reliable cleanup preview without finalizing deletion."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting cleanup preview soft delete with "
        f"ENABLE_SAFE_DELETE={config.enable_safe_delete}, "
        f"CONFIRM_SAFE_DELETE={config.confirm_safe_delete}, "
        "thresholds=("
        f"max_count={config.max_deletable_splats}, "
        f"max_ratio={config.max_deletable_percentage:.6f})."
    )

    if not config.enable_safe_delete:
        message = (
            "Cleanup preview soft delete is disabled because ENABLE_SAFE_DELETE=False. "
            "No destructive action was performed."
        )
        _log_info(message)
        return True, message

    if not config.confirm_safe_delete:
        message = (
            "Cleanup preview soft delete is armed but not confirmed because "
            "ENABLE_SAFE_DELETE=True and CONFIRM_SAFE_DELETE=False. "
            "No destructive action was performed."
        )
        _log_info(message)
        return True, message

    preview_summary = config.last_cleanup_preview_summary
    if preview_summary is None:
        message = "No cleanup preview is available. Run Preview Cleanup Selection first."
        _log_error(message)
        return False, message

    estimated_affected_splats = int(
        preview_summary.get(
            "estimated_affected_splats_total",
            preview_summary.get("estimated_affected_splats", 0),
        )
    )
    total_splats = int(preview_summary.get("total_splats", 0))
    selected_ratio = _selected_percentage(estimated_affected_splats, total_splats)
    _log_info(f"preview_candidate_splats={estimated_affected_splats}")
    _log_info(f"preview_total_splats={total_splats}")
    _log_info(f"preview_candidate_ratio={selected_ratio * 100.0:.6f}%")

    if estimated_affected_splats <= 0:
        message = "Cleanup preview refused: estimated_affected_splats == 0."
        _log_error(message)
        return False, message
    if estimated_affected_splats > config.max_deletable_splats:
        message = (
            "Cleanup preview soft delete refused: "
            f"estimated_affected_splats={estimated_affected_splats} exceeds "
            f"SAFE_DELETE_MAX_COUNT={config.max_deletable_splats}."
        )
        _log_error(message)
        return False, message
    if selected_ratio > config.max_deletable_percentage:
        message = (
            "Cleanup preview soft delete refused: "
            f"selected_ratio={selected_ratio:.6f} exceeds "
            f"SAFE_DELETE_MAX_RATIO={config.max_deletable_percentage:.6f}."
        )
        _log_error(message)
        return False, message

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Cleanup preview soft delete adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    soft_delete_cleanup_candidates = getattr(adapter, "soft_delete_cleanup_candidates", None)
    if not callable(soft_delete_cleanup_candidates):
        message = "LichtfeldAdapter does not expose soft_delete_cleanup_candidates()."
        _log_error(message)
        return False, message

    try:
        result = soft_delete_cleanup_candidates()
    except Exception as exc:
        message = f"Cleanup preview soft delete failed: {exc}"
        _log_error(message)
        return False, message

    _log_info(
        "Cleanup preview soft delete complete. "
        "Reversible only. Does not call apply_deleted()."
    )
    _log_info(f"cleanup_preview_soft_delete ok={result.ok} message={result.message}")
    return result.ok, result.message


def run_apply_confirmed_cleanup() -> tuple[bool, str]:
    """Permanently apply a previously confirmed cleanup soft delete."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting confirmed cleanup apply with "
        f"ENABLE_SAFE_DELETE={config.enable_safe_delete}, "
        f"CONFIRM_SAFE_DELETE={config.confirm_safe_delete}."
    )

    if not config.enable_safe_delete:
        message = (
            "Confirmed cleanup apply is disabled because ENABLE_SAFE_DELETE=False. "
            "No permanent action was performed."
        )
        _log_info(message)
        return True, message

    if not config.confirm_safe_delete:
        message = (
            "Confirmed cleanup apply is armed but not confirmed because "
            "ENABLE_SAFE_DELETE=True and CONFIRM_SAFE_DELETE=False. "
            "No permanent action was performed."
        )
        _log_info(message)
        return True, message

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Confirmed cleanup apply adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    apply_cleanup_candidates = getattr(adapter, "apply_cleanup_candidates", None)
    if not callable(apply_cleanup_candidates):
        message = "LichtfeldAdapter does not expose apply_cleanup_candidates()."
        _log_error(message)
        return False, message

    get_stats = getattr(adapter, "get_stats", None)
    if not callable(get_stats):
        message = "LichtfeldAdapter does not expose get_stats() for confirmed cleanup logging."
        _log_error(message)
        return False, message

    try:
        initial_stats = get_stats()
        initial_splat_count = initial_stats.splat_count
        _log_info(f"initial_splat_count={initial_splat_count}")
        result = apply_cleanup_candidates()
        final_stats = get_stats()
    except Exception as exc:
        message = f"Confirmed cleanup apply failed: {exc}"
        _log_error(message)
        return False, message

    final_splat_count = final_stats.splat_count
    permanent_deleted_count = initial_splat_count - final_splat_count
    soft_deleted_count = permanent_deleted_count
    _log_info(f"soft_deleted_count={soft_deleted_count}")
    _log_info(f"final_splat_count={final_splat_count}")
    _log_info(f"permanent_deleted_count={permanent_deleted_count}")
    _log_info(
        "Confirmed cleanup apply complete. "
        "Permanent cleanup is no longer restorable."
    )
    _log_info(f"confirmed_cleanup_apply ok={result.ok} message={result.message}")
    return result.ok, result.message


def run_cluster_analysis_preview() -> tuple[bool, str]:
    """Run a non-destructive cluster analysis summary on the active LichtFeld scene."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting sampled cluster analysis preview with "
        f"distance_threshold={config.cluster_distance_threshold:.4f}, "
        f"min_cluster_size={config.cluster_min_cluster_size}, "
        f"max_cluster_analysis_splats={config.max_cluster_analysis_splats}, "
        "abort_if_splat_count_above_limit="
        f"{config.abort_if_splat_count_above_limit}."
    )

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Cluster analysis adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    analyze_clusters_preview = getattr(adapter, "analyze_clusters_preview", None)
    if not callable(analyze_clusters_preview):
        message = "LichtfeldAdapter does not expose analyze_clusters_preview()."
        _log_error(message)
        return False, message

    try:
        summary = analyze_clusters_preview(
            distance_threshold=config.cluster_distance_threshold,
            min_cluster_size=config.cluster_min_cluster_size,
            max_cluster_analysis_splats=config.max_cluster_analysis_splats,
            abort_if_splat_count_above_limit=config.abort_if_splat_count_above_limit,
        )
    except Exception as exc:
        message = f"Cluster analysis preview failed: {exc}"
        _log_error(message)
        return False, message

    if summary.refused:
        _log_info(summary.message)
        return True, summary.message

    _log_info(f"total_splats={summary.total_splats}")
    _log_info(f"analyzed_splats={summary.analyzed_splats}")
    _log_info(f"used_native_sampling={summary.used_native_sampling}")
    if summary.approximate:
        sampling_ratio = (
            0.0
            if summary.total_splats <= 0
            else summary.analyzed_splats / summary.total_splats
        )
        _log_info(
            "approximate_analysis=True "
            f"sampling_stride={summary.sampling_stride} "
            f"sampling_ratio={sampling_ratio:.6f}"
        )
    else:
        _log_info("approximate_analysis=False")
    _log_info(f"total_clusters={summary.total_clusters}")
    _log_info(f"largest_cluster_size={summary.largest_cluster_size}")
    _log_info(f"clusters_smaller_than_threshold={summary.small_cluster_count}")
    _log_info(
        "candidate_floating_clusters="
        f"{summary.candidate_floating_cluster_count}"
    )
    _log_info(
        "candidate_floating_splats="
        f"{summary.candidate_floating_splat_count}"
    )
    _log_info(
        "timings_seconds="
        f"get_stats:{summary.stats_elapsed_seconds:.3f} "
        f"read_means:{summary.read_means_elapsed_seconds:.3f} "
        f"sampling:{summary.sampling_elapsed_seconds:.3f} "
        f"gaussian_cloud:{summary.cloud_build_elapsed_seconds:.3f} "
        f"clustering:{summary.clustering_elapsed_seconds:.3f}"
    )
    message = summary.message
    _log_info(message)
    return True, message


def run_voxel_cluster_analysis_preview() -> tuple[bool, str]:
    """Run a non-destructive voxel occupancy analysis on the active LichtFeld scene."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting voxel cluster analysis preview with "
        f"voxel_size={config.voxel_size:.4f}, "
        f"min_voxel_cluster_size={config.voxel_min_cluster_size}, "
        f"max_cluster_analysis_splats={config.max_cluster_analysis_splats}, "
        "abort_if_splat_count_above_limit="
        f"{config.abort_if_splat_count_above_limit}."
    )

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Voxel cluster analysis adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    analyze_voxel_clusters_preview = getattr(adapter, "analyze_voxel_clusters_preview", None)
    if not callable(analyze_voxel_clusters_preview):
        message = "LichtfeldAdapter does not expose analyze_voxel_clusters_preview()."
        _log_error(message)
        return False, message

    try:
        summary = analyze_voxel_clusters_preview(
            voxel_size=config.voxel_size,
            min_voxel_cluster_size=config.voxel_min_cluster_size,
            max_splats=config.max_cluster_analysis_splats,
            abort_if_above_limit=config.abort_if_splat_count_above_limit,
        )
    except Exception as exc:
        message = f"Voxel cluster analysis preview failed: {exc}"
        _log_error(message)
        return False, message

    if summary.refused:
        _log_info(summary.message)
        return True, summary.message

    _log_info(f"total_splats={summary.total_splats}")
    _log_info(f"analyzed_splats={summary.analyzed_splats}")
    _log_info(f"occupied_voxels={summary.occupied_voxels}")
    _log_info(f"used_native_sampling={summary.used_native_sampling}")
    if summary.approximate:
        sampling_ratio = (
            0.0
            if summary.total_splats <= 0
            else summary.analyzed_splats / summary.total_splats
        )
        _log_info(
            "approximate_analysis=True "
            f"sampling_stride={summary.sampling_stride} "
            f"sampling_ratio={sampling_ratio:.6f}"
        )
    else:
        _log_info("approximate_analysis=False")
    _log_info(f"total_voxel_clusters={summary.total_voxel_clusters}")
    _log_info(
        "largest_voxel_cluster="
        f"voxels:{summary.largest_voxel_cluster_voxel_count} "
        f"estimated_splats:{summary.largest_voxel_cluster_estimated_splats}"
    )
    _log_info(f"small_voxel_clusters={summary.small_voxel_cluster_count}")
    _log_info(f"estimated_floating_splats={summary.estimated_floating_splats}")
    _log_info(
        "timings_seconds="
        f"read_means:{summary.read_means_elapsed_seconds:.3f} "
        f"sampling:{summary.sampling_elapsed_seconds:.3f} "
        f"voxel_analysis:{summary.voxel_analysis_elapsed_seconds:.3f}"
    )
    message = summary.message
    _log_info(message)
    return True, message


def run_lcht_mcp_test() -> tuple[bool, str]:
    """Run a safe adapter smoke test inside LichtFeld Studio."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting safe adapter smoke test with "
        f"MIN_Z={config.smoke_test_min_z}, MAX_Z={config.smoke_test_max_z}, "
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
            (SELECTION_RANGES[0][0], config.smoke_test_min_z, config.smoke_test_max_z),
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


def run_safe_delete_test() -> tuple[bool, str]:
    """Run a guarded destructive validation flow inside LichtFeld Studio."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting safe delete test with "
        f"ENABLE_SAFE_DELETE={config.enable_safe_delete}, "
        f"CONFIRM_SAFE_DELETE={config.confirm_safe_delete}, "
        f"range=({config.safe_delete_min_z}, {config.safe_delete_max_z}), "
        "thresholds=("
        f"max_count={config.max_deletable_splats}, "
        f"max_ratio={config.max_deletable_percentage:.6f})."
    )

    if not config.enable_safe_delete:
        message = (
            "Safe delete test is disabled because ENABLE_SAFE_DELETE=False. "
            "No destructive action was performed."
        )
        _log_info(message)
        return True, message

    if not config.confirm_safe_delete:
        message = (
            "Safe delete test is armed but not confirmed because "
            "ENABLE_SAFE_DELETE=True and CONFIRM_SAFE_DELETE=False. "
            "No destructive action was performed."
        )
        _log_info(message)
        return True, message

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Safe delete adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    try:
        initial_stats = adapter.get_stats()
        initial_splat_count = initial_stats.splat_count
        _log_info(f"initial_splat_count={initial_splat_count}")
        _log_info(f"bounding_box={initial_stats.bounds}")
    except Exception as exc:
        message = f"Safe delete get_stats failed: {exc}"
        _log_error(message)
        return False, message

    try:
        selection = adapter.select_by_height(
            z_min=config.safe_delete_min_z,
            z_max=config.safe_delete_max_z,
        )
        selected_percentage = _selected_percentage(
            selection.selected_count,
            initial_splat_count,
        )
        _log_info(f"selected_count={selection.selected_count}")
        _log_info(f"percentage_of_total={selected_percentage * 100.0:.6f}%")
    except Exception as exc:
        message = f"Safe delete select_by_height failed: {exc}"
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after safe delete selection failure.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after safe delete failure: {clear_exc}")
        return False, message

    try:
        if selection.selected_count == 0:
            raise RuntimeError("Safe delete refused: selected_count == 0.")
        if selection.selected_count > config.max_deletable_splats:
            raise RuntimeError(
                "Safe delete refused: "
                f"selected_count={selection.selected_count} exceeds "
                f"SAFE_DELETE_MAX_COUNT={config.max_deletable_splats}."
            )
        if selected_percentage > config.max_deletable_percentage:
            raise RuntimeError(
                "Safe delete refused: "
                f"selected_ratio={selected_percentage:.6f} exceeds "
                f"SAFE_DELETE_MAX_RATIO={config.max_deletable_percentage:.6f}."
            )
    except Exception as exc:
        message = str(exc)
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after safe delete guard refusal.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after guard refusal: {clear_exc}")
        return False, message

    try:
        delete_result = adapter.delete_selection()
        _log_info(f"delete_selection ok={delete_result.ok} message={delete_result.message}")
    except Exception as exc:
        message = f"Safe delete delete_selection failed: {exc}"
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after delete failure.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after delete failure: {clear_exc}")
        return False, message

    if VERIFY_STATS_AFTER_DELETE:
        try:
            final_stats = adapter.get_stats()
            final_splat_count = final_stats.splat_count
            deleted_count = initial_splat_count - final_splat_count
            _log_info(f"final_splat_count={final_splat_count}")
            _log_info(f"deleted_count={deleted_count}")
        except Exception as exc:
            message = f"Safe delete post-delete get_stats failed: {exc}"
            _log_error(message)
            try:
                _clear_selection()
                _log_info("Selection cleared after post-delete stats failure.")
            except Exception as clear_exc:
                _log_error(f"Failed to clear selection after post-delete stats failure: {clear_exc}")
            return False, message
    else:
        expected_final_count = initial_splat_count - selection.selected_count
        _log_info(
            "Skipping post-delete get_stats because VERIFY_STATS_AFTER_DELETE=False. "
            f"expected_final_count={expected_final_count}"
        )

    try:
        _clear_selection()
        _log_info("Selection cleared before safe delete exit.")
    except Exception as exc:
        message = f"Safe delete selection clear failed: {exc}"
        _log_error(message)
        return False, message

    message = "Safe delete validation complete."
    _log_info(message)
    return True, message


def run_undo_validation() -> tuple[bool, str]:
    """Delete and immediately restore a tiny selection to validate undelete."""
    config = snapshot_runtime_config()
    _log_info(
        "Starting undo validation with "
        f"ENABLE_SAFE_DELETE={config.enable_safe_delete}, "
        f"CONFIRM_SAFE_DELETE={config.confirm_safe_delete}, "
        f"range=({config.safe_delete_min_z}, {config.safe_delete_max_z}), "
        "thresholds=("
        f"max_count={config.max_deletable_splats}, "
        f"max_ratio={config.max_deletable_percentage:.6f})."
    )

    if not config.enable_safe_delete:
        message = (
            "Undo validation is disabled because ENABLE_SAFE_DELETE=False. "
            "No destructive action was performed."
        )
        _log_info(message)
        return True, message

    if not config.confirm_safe_delete:
        message = (
            "Undo validation is armed but not confirmed because "
            "ENABLE_SAFE_DELETE=True and CONFIRM_SAFE_DELETE=False. "
            "No destructive action was performed."
        )
        _log_info(message)
        return True, message

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"Undo validation adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    try:
        initial_stats = adapter.get_stats()
        initial_splat_count = initial_stats.splat_count
        _log_info(f"initial_splat_count={initial_splat_count}")
        _log_info(f"initial_selected_count={initial_stats.selected_count}")
    except Exception as exc:
        message = f"Undo validation get_stats failed: {exc}"
        _log_error(message)
        return False, message

    try:
        selection = adapter.select_by_height(
            z_min=config.safe_delete_min_z,
            z_max=config.safe_delete_max_z,
        )
        selected_percentage = _selected_percentage(
            selection.selected_count,
            initial_splat_count,
        )
        _log_info(f"selected_count={selection.selected_count}")
        _log_info(f"selected_percentage={selected_percentage * 100.0:.6f}%")
    except Exception as exc:
        message = f"Undo validation select_by_height failed: {exc}"
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after undo validation selection failure.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after undo validation failure: {clear_exc}")
        return False, message

    try:
        if selection.selected_count == 0:
            raise RuntimeError("Undo validation refused: selected_count == 0.")
        if selection.selected_count > config.max_deletable_splats:
            raise RuntimeError(
                "Undo validation refused: "
                f"selected_count={selection.selected_count} exceeds "
                f"SAFE_DELETE_MAX_COUNT={config.max_deletable_splats}."
            )
        if selected_percentage > config.max_deletable_percentage:
            raise RuntimeError(
                "Undo validation refused: "
                f"selected_ratio={selected_percentage:.6f} exceeds "
                f"SAFE_DELETE_MAX_RATIO={config.max_deletable_percentage:.6f}."
            )
    except Exception as exc:
        message = str(exc)
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after undo validation guard refusal.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after undo guard refusal: {clear_exc}")
        return False, message

    try:
        soft_delete_selection = getattr(adapter, "soft_delete_selection", None)
        if not callable(soft_delete_selection):
            raise RuntimeError(
                "LichtFeldAdapter does not expose soft_delete_selection() for undo validation."
            )
        soft_delete_result = soft_delete_selection()
        _log_info(
            f"soft_delete_selection ok={soft_delete_result.ok} message={soft_delete_result.message}"
        )
        if not soft_delete_result.ok:
            raise RuntimeError(soft_delete_result.message)
    except Exception as exc:
        message = f"Undo validation soft_delete_selection failed: {exc}"
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after undo validation soft delete failure.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after undo soft delete failure: {clear_exc}")
        return False, message

    try:
        soft_deleted_stats = adapter.get_stats()
        soft_deleted_count = initial_splat_count - soft_deleted_stats.splat_count
        _log_info(f"post_soft_delete_splat_count={soft_deleted_stats.splat_count}")
        if soft_deleted_stats.splat_count == initial_splat_count:
            _log_info(
                "Soft delete did not change splat_count; inspecting native deleted state if available."
            )
            _log_soft_delete_runtime_state()
        else:
            _log_info(f"soft_deleted_count={soft_deleted_count}")
    except Exception as exc:
        message = f"Undo validation post-soft-delete get_stats failed: {exc}"
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after undo validation post-soft-delete failure.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after undo post-soft-delete failure: {clear_exc}")
        return False, message

    try:
        _restore_deleted_splats(adapter)
        restored_stats = adapter.get_stats()
        _log_info(f"final_splat_count={restored_stats.splat_count}")
        _log_info(f"final_selected_count={restored_stats.selected_count}")
        if restored_stats.splat_count != initial_splat_count:
            raise RuntimeError(
                "Undo validation failed: "
                f"final_splat_count={restored_stats.splat_count} does not match "
                f"initial_splat_count={initial_splat_count}."
            )
    except Exception as exc:
        message = f"Undo validation restore failed: {exc}"
        _log_error(message)
        try:
            _clear_selection()
            _log_info("Selection cleared after undo validation restore failure.")
        except Exception as clear_exc:
            _log_error(f"Failed to clear selection after undo restore failure: {clear_exc}")
        return False, message

    try:
        _clear_selection()
        _log_info("Selection cleared before undo validation exit.")
    except Exception as exc:
        message = f"Undo validation selection clear failed: {exc}"
        _log_error(message)
        return False, message

    message = "Undo validation complete. Original splat count restored."
    _log_info(message)
    return True, message
