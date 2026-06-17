# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only runtime diagnostics for the LichtFeld Studio Python API."""

from __future__ import annotations

import inspect
from types import ModuleType

import lichtfeld as lf


LOG_PREFIX = "lcht_mcp_diag"
MAX_PROBE_DEPTH = 2
CANDIDATE_NAMES = (
    "scene",
    "current_scene",
    "active_scene",
    "app",
    "context",
    "session",
    "project",
    "scene_manager",
    "training_manager",
    "trainer",
    "command_center",
)
LIKELY_ACCESS_PATH_NAMES = (
    "combined_model",
    "model",
    "current_model",
    "gaussian_model",
    "trainer",
    "get_model",
    "get_scene",
    "get_trainer",
    "scene",
    "splats",
    "gaussians",
)
SAFE_NO_ARG_CALL_NAMES = frozenset(CANDIDATE_NAMES + LIKELY_ACCESS_PATH_NAMES)


def _log_info(message: str) -> None:
    lf.log.info(f"{LOG_PREFIX}: {message}")


def _log_error(message: str) -> None:
    lf.log.error(f"{LOG_PREFIX}: {message}")


def _type_name(value: object) -> str:
    if isinstance(value, ModuleType):
        return f"module:{value.__name__}"
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _public_attribute_names(value: object) -> list[str]:
    try:
        return sorted(name for name in dir(value) if not name.startswith("_"))
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        _log_error(f"dir({ _type_name(value) }) failed: {exc}")
        return []


def _log_public_attributes(label: str, value: object) -> None:
    names = _public_attribute_names(value)
    joined = ", ".join(names) if names else "<none>"
    _log_info(f"{label} public_attrs[{len(names)}]: {joined}")


def _should_probe_object(value: object) -> bool:
    if value is None or isinstance(value, (str, bytes, bool, int, float, complex)):
        return False
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return False
    if hasattr(value, "shape") or hasattr(value, "dtype"):
        return False
    return True


def _supports_safe_no_arg_call(callable_obj: object) -> tuple[bool, str]:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError) as exc:
        return False, f"signature_unavailable:{exc}"

    for parameter in signature.parameters.values():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if parameter.default is inspect.Parameter.empty:
            return False, f"requires_arg:{parameter.name}"
    return True, "ok"


def _safe_getattr(owner: object, path: str, attribute_name: str) -> tuple[bool, object]:
    try:
        value = getattr(owner, attribute_name)
    except AttributeError:
        return False, None
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        _log_error(f"{path}.{attribute_name} getattr failed: {exc}")
        return False, None
    return True, value


def _safe_probe_call(
    path: str,
    attribute_name: str,
    candidate: object,
    visited: set[int],
    depth: int,
) -> None:
    if attribute_name not in SAFE_NO_ARG_CALL_NAMES:
        _log_info(f"{path}.{attribute_name} call skipped: not in safe getter allowlist")
        return

    supported, reason = _supports_safe_no_arg_call(candidate)
    if not supported:
        _log_info(f"{path}.{attribute_name} call skipped: {reason}")
        return

    try:
        result = candidate()
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        _log_error(f"{path}.{attribute_name}() failed: {exc}")
        return

    _log_info(f"{path}.{attribute_name}() -> type={_type_name(result)}")
    if _should_probe_object(result):
        _probe_object(f"{path}.{attribute_name}()", result, visited, depth + 1)


def _probe_candidate_attribute(
    owner: object,
    path: str,
    attribute_name: str,
    visited: set[int],
    depth: int,
) -> None:
    exists, value = _safe_getattr(owner, path, attribute_name)
    if not exists:
        _log_info(f"{path}.{attribute_name}: missing")
        return

    is_callable = callable(value)
    _log_info(
        f"{path}.{attribute_name}: exists type={_type_name(value)} callable={is_callable}"
    )
    if is_callable:
        _safe_probe_call(path, attribute_name, value, visited, depth)
        return
    if _should_probe_object(value):
        _probe_object(f"{path}.{attribute_name}", value, visited, depth + 1)


def _probe_likely_members(path: str, value: object, visited: set[int], depth: int) -> None:
    public_names = set(_public_attribute_names(value))
    for attribute_name in LIKELY_ACCESS_PATH_NAMES:
        if attribute_name not in public_names:
            _log_info(f"{path}.{attribute_name}: missing")
            continue
        exists, member = _safe_getattr(value, path, attribute_name)
        if not exists:
            _log_info(f"{path}.{attribute_name}: present_in_dir but getattr_unavailable")
            continue
        is_callable = callable(member)
        _log_info(
            f"{path}.{attribute_name}: exists type={_type_name(member)} callable={is_callable}"
        )
        if is_callable:
            _safe_probe_call(path, attribute_name, member, visited, depth)
            continue
        if _should_probe_object(member):
            _probe_object(f"{path}.{attribute_name}", member, visited, depth + 1)


def _probe_object(path: str, value: object, visited: set[int], depth: int) -> None:
    if depth > MAX_PROBE_DEPTH:
        _log_info(f"{path}: depth limit reached")
        return

    object_id = id(value)
    if object_id in visited:
        _log_info(f"{path}: already visited type={_type_name(value)}")
        return
    visited.add(object_id)

    _log_info(f"{path}: type={_type_name(value)}")
    _log_public_attributes(path, value)
    _probe_likely_members(path, value, visited, depth)


def run_lcht_mcp_diagnostics() -> tuple[bool, str]:
    """Log the active LichtFeld Studio Python API surface without mutating state."""
    visited: set[int] = set()
    try:
        _log_info(f"lichtfeld module type={_type_name(lf)}")
        _log_public_attributes("lichtfeld", lf)
        _probe_object("lichtfeld", lf, visited, depth=0)
        for attribute_name in CANDIDATE_NAMES:
            _probe_candidate_attribute(lf, "lichtfeld", attribute_name, visited, depth=0)
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        message = f"diagnostic failed: {exc}"
        _log_error(message)
        return False, message

    message = "diagnostic completed"
    _log_info(message)
    return True, message
