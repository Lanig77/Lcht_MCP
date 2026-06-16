from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Callable


PLUGIN_NAME = "lcht_mcp_test_plugin"
BUTTON_LABEL = "Run Lcht MCP Test"
MIN_Z = 0.0
MAX_Z = 2.0
DELETE_SELECTED = False
REPO_ROOT_HINT = Path.home() / "Documents" / "MCP GS" / "Lcht_MCP"

_UI_HANDLE: object | None = None
_UI_UNREGISTER: Callable[[], None] | None = None


def _load_lichtfeld_module() -> Any | None:
    try:
        return importlib.import_module("lichtfeld")
    except Exception:
        return None


def _log(level: str, message: str) -> None:
    prefix = "[Lcht_MCP Plugin]"
    formatted = f"{prefix} {message}"
    lichtfeld_module = _load_lichtfeld_module()
    logger = getattr(getattr(lichtfeld_module, "log", None), level, None)
    if callable(logger):
        try:
            logger(formatted)
            return
        except Exception:
            pass
    print(formatted)


def _candidate_repo_roots() -> list[Path]:
    candidates: list[Path] = []
    environment_root = os.environ.get("LCHT_MCP_REPO_ROOT")
    if environment_root:
        candidates.append(Path(environment_root).expanduser())
    candidates.append(Path(__file__).resolve().parents[2])
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
        "Set the LCHT_MCP_REPO_ROOT environment variable or update REPO_ROOT_HINT "
        "in the plugin __init__.py file."
    )


def _build_adapter():
    repository_root = _configure_import_path()
    from lichtfeld_mcp.adapters.lichtfeld import LichtfeldAdapter

    return LichtfeldAdapter(), repository_root


def run_lcht_mcp_test(*_args: object, **_kwargs: object) -> None:
    _log(
        "info",
        f"Starting safe adapter smoke test with MIN_Z={MIN_Z}, MAX_Z={MAX_Z}, "
        f"DELETE_SELECTED={DELETE_SELECTED}.",
    )
    try:
        adapter, repository_root = _build_adapter()
        _log("info", f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        _log("error", f"Adapter setup failed: {exc}")
        return

    try:
        stats = adapter.get_stats()
        _log("info", f"splat_count={stats.splat_count}")
        _log("info", f"bounding_box={stats.bounds}")
    except Exception as exc:
        _log("error", f"get_stats failed: {exc}")

    try:
        _log("info", f"select_by_height range: min_z={MIN_Z}, max_z={MAX_Z}")
        selection = adapter.select_by_height(z_min=MIN_Z, z_max=MAX_Z)
        _log("info", f"selected_count={selection.selected_count}")
    except Exception as exc:
        _log("error", f"select_by_height failed: {exc}")

    if not DELETE_SELECTED:
        _log("info", "delete_selection skipped because DELETE_SELECTED=False.")
        return

    try:
        delete_result = adapter.delete_selection()
        _log(
            "info",
            f"delete_selection: ok={delete_result.ok} message={delete_result.message}",
        )
    except Exception as exc:
        _log("error", f"delete_selection failed: {exc}")


def _manual_run_message() -> None:
    _log(
        "info",
        "UI registration is not available. "
        "Run lcht_mcp_test_plugin.run_lcht_mcp_test() manually from the LichtFeld Python console.",
    )


def _register_ui() -> bool:
    global _UI_HANDLE, _UI_UNREGISTER

    lichtfeld_module = _load_lichtfeld_module()
    ui = getattr(lichtfeld_module, "ui", None)
    if ui is None:
        _manual_run_message()
        return False

    registration_attempts = [
        ("register_button", "unregister_button"),
        ("add_button", "remove_button"),
        ("register_action", "unregister_action"),
        ("add_action", "remove_action"),
        ("register_panel", "unregister_panel"),
    ]

    for register_name, unregister_name in registration_attempts:
        register = getattr(ui, register_name, None)
        if not callable(register):
            continue
        try:
            handle = register(BUTTON_LABEL, run_lcht_mcp_test)
        except TypeError:
            try:
                handle = register(name=BUTTON_LABEL, callback=run_lcht_mcp_test)
            except Exception:
                continue
        except Exception as exc:
            _log("error", f"UI registration via {register_name} failed: {exc}")
            continue

        unregister = getattr(ui, unregister_name, None)
        if callable(unregister):
            _UI_UNREGISTER = lambda remover=unregister, token=handle or BUTTON_LABEL: remover(token)
        else:
            _UI_UNREGISTER = None
        _UI_HANDLE = handle or BUTTON_LABEL
        _log("info", f"Registered '{BUTTON_LABEL}' via LichtFeld UI API ({register_name}).")
        return True

    _manual_run_message()
    return False


def on_load() -> None:
    _log("info", f"{PLUGIN_NAME} loaded.")
    try:
        _register_ui()
    except Exception as exc:
        _log("error", f"Plugin load failed during UI setup: {exc}")
        _manual_run_message()


def on_unload() -> None:
    global _UI_HANDLE, _UI_UNREGISTER

    if _UI_UNREGISTER is not None:
        try:
            _UI_UNREGISTER()
            _log("info", f"Unregistered '{BUTTON_LABEL}' from LichtFeld UI.")
        except Exception as exc:
            _log("error", f"UI cleanup failed: {exc}")
    _UI_HANDLE = None
    _UI_UNREGISTER = None
    _log("info", f"{PLUGIN_NAME} unloaded.")


__all__ = ["DELETE_SELECTED", "MAX_Z", "MIN_Z", "on_load", "on_unload", "run_lcht_mcp_test"]
