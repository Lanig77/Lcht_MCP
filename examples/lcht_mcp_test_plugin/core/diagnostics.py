# SPDX-FileCopyrightText: 2025 Lcht_MCP Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only runtime diagnostics for the LichtFeld Studio Python API."""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import sys
from types import ModuleType

import lichtfeld as lf


LOG_PREFIX = "lcht_mcp_diag"
MAX_PROBE_DEPTH = 2
MAX_REPR_LENGTH = 200
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
TENSOR_METHOD_NAMES = (
    "clone",
    "copy",
    "to",
    "cpu",
    "numpy",
    "fill",
    "zeros",
    "ones",
    "from_list",
    "from_numpy",
    "astype",
    "bool",
    "__setitem__",
)
NATIVE_SELECTION_NAMES = (
    "add_to_selection",
    "deselect_all",
    "selection",
    "has_selection",
)
SELECTION_GRAPH_ATTRIBUTE_NAMES = (
    "get_scene",
    "scene",
    "current_scene",
    "active_scene",
    "combined_model",
    "model",
    "current_model",
    "gaussian_model",
    "selection_mask",
    "get_selection_mask",
    "selection",
    "selection_manager",
    "get_selection_manager",
    "scene_manager",
    "get_scene_manager",
    "renderer",
    "get_renderer",
    "rendering_pipeline",
    "get_rendering_pipeline",
    "pipeline",
    "tensor_manager",
    "get_tensor_manager",
    "selection_tensor",
    "selection_buffer",
    "selection_visualizer",
    "selection_visualization",
    "gpu_selection",
    "gpu_selection_mask",
    "gpu_selection_buffer",
    "cpu_selection",
    "cpu_selection_mask",
    "cpu_selection_buffer",
    "deleted",
    "get_deleted_mask",
    "deleted_mask",
)
MAX_SELECTION_SNAPSHOT_DEPTH = 3


@dataclass(slots=True)
class SelectionSnapshotEntry:
    path: str
    type_name: str
    object_id: int
    refcount: int | None
    size: int | None
    alias_of: str | None
    clone_method: str | None
    clone_size: int | None
    clone_error: str | None
    stale_size: bool


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


def _safe_repr(value: object) -> str:
    try:
        text = repr(value)
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        return f"<repr failed: {exc}>"
    if len(text) > MAX_REPR_LENGTH:
        return f"{text[:MAX_REPR_LENGTH]}..."
    return text


def _safe_signature(value: object) -> str:
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError) as exc:
        return f"<signature unavailable: {exc}>"


def _log_callable_details(label: str, value: object) -> None:
    if value is None:
        _log_info(f"{label}: missing")
        return
    _log_info(
        f"{label}: type={_type_name(value)} callable={callable(value)} "
        f"signature={_safe_signature(value)} repr={_safe_repr(value)}"
    )


def _safe_scalar_metadata(label: str, value: object) -> None:
    shape = getattr(value, "shape", None)
    if shape is not None:
        _log_info(f"{label} shape={shape}")
    count = getattr(value, "count", None)
    if callable(count):
        try:
            _log_info(f"{label} count()={count()}")
        except Exception as exc:  # pragma: no cover - defensive runtime probe
            _log_error(f"{label} count() failed: {exc}")
    elif count is not None and not callable(count):
        _log_info(f"{label} count={count}")
    try:
        _log_info(f"{label} len={len(value)}")
    except Exception:
        pass


def _safe_refcount(value: object) -> int | None:
    try:
        return max(0, sys.getrefcount(value) - 1)
    except Exception:
        return None


def _safe_size(value: object) -> int | None:
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            if len(shape) > 0:
                return int(shape[0])
        except Exception:
            pass
    try:
        return len(value)  # type: ignore[arg-type]
    except Exception:
        return None


def _is_selection_tensor_path(path: str) -> bool:
    normalized = path.lower()
    return any(
        token in normalized
        for token in (
            "selection_mask",
            "selection_tensor",
            "selection_buffer",
            "gpu_selection",
            "cpu_selection",
            "deleted_mask",
            ".deleted",
        )
    )


def _is_selection_tensor_like(path: str, value: object) -> bool:
    if _is_selection_tensor_path(path):
        return True
    if hasattr(value, "shape") and any(
        hasattr(value, attribute_name) for attribute_name in ("clone", "copy", "fill")
    ):
        return True
    return False


def _probe_clone_state(value: object) -> tuple[str | None, int | None, str | None]:
    for method_name in ("clone", "copy"):
        method = getattr(value, method_name, None)
        if not callable(method):
            continue
        try:
            cloned = method()
        except Exception as exc:  # pragma: no cover - defensive runtime probe
            return method_name, None, str(exc)
        return method_name, _safe_size(cloned), None
    return None, None, None


def _log_tensor_capabilities(label: str, value: object) -> None:
    for method_name in TENSOR_METHOD_NAMES:
        exists = hasattr(value, method_name)
        if not exists:
            _log_info(f"{label}.{method_name}: missing")
            continue
        member = getattr(value, method_name)
        _log_info(
            f"{label}.{method_name}: exists type={_type_name(member)} callable={callable(member)}"
        )


def _log_tensor_details(label: str, value: object) -> None:
    _log_info(f"{label}: type={_type_name(value)} repr={_safe_repr(value)}")
    _log_public_attributes(label, value)
    _safe_scalar_metadata(label, value)
    _log_tensor_capabilities(label, value)


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


def _safe_get_scene() -> object | None:
    get_scene = getattr(lf, "get_scene", None)
    if not callable(get_scene):
        _log_info("lichtfeld.get_scene: missing or not callable")
        return None
    try:
        scene = get_scene()
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        _log_error(f"lichtfeld.get_scene() failed: {exc}")
        return None
    _log_info(f"lichtfeld.get_scene() -> type={_type_name(scene)}")
    return scene


def _safe_get_model(scene: object | None) -> object | None:
    if scene is None:
        return None
    combined_model = getattr(scene, "combined_model", None)
    if not callable(combined_model):
        _log_info("scene.combined_model: missing or not callable")
        return None
    try:
        model = combined_model()
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        _log_error(f"scene.combined_model() failed: {exc}")
        return None
    _log_info(f"scene.combined_model() -> type={_type_name(model)}")
    return model


def _infer_model_splat_count(model: object | None) -> int | None:
    if model is None:
        return None
    splat_count = getattr(model, "splat_count", None)
    if isinstance(splat_count, int):
        return splat_count

    for attribute_name in ("get_means", "means", "means_raw", "get_deleted_mask", "deleted"):
        exists, value = _safe_getattr(model, "model", attribute_name)
        if not exists:
            continue
        if callable(value):
            supported, _ = _supports_safe_no_arg_call(value)
            if not supported:
                continue
            try:
                value = value()
            except Exception:
                continue
        size = _safe_size(value)
        if size is not None:
            return size
    return None


def _capture_selection_snapshot_entry(
    path: str,
    value: object,
    model_splat_count: int | None,
    aliases: dict[int, str],
) -> SelectionSnapshotEntry:
    size = _safe_size(value)
    alias_of = aliases.get(id(value))
    if alias_of is None:
        aliases[id(value)] = path

    clone_method = None
    clone_size = None
    clone_error = None
    if _is_selection_tensor_like(path, value):
        clone_method, clone_size, clone_error = _probe_clone_state(value)

    stale_size = (
        _is_selection_tensor_like(path, value)
        and model_splat_count is not None
        and size is not None
        and size != model_splat_count
    )
    return SelectionSnapshotEntry(
        path=path,
        type_name=_type_name(value),
        object_id=id(value),
        refcount=_safe_refcount(value),
        size=size,
        alias_of=alias_of,
        clone_method=clone_method,
        clone_size=clone_size,
        clone_error=clone_error,
        stale_size=stale_size,
    )


def _log_selection_snapshot_entry(label: str, entry: SelectionSnapshotEntry) -> None:
    alias_text = entry.alias_of or "-"
    _log_info(
        f"{label}: {entry.path} type={entry.type_name} "
        f"id=0x{entry.object_id:x} refcount={entry.refcount} "
        f"size={entry.size} alias_of={alias_text}"
    )
    if entry.clone_method is not None and entry.clone_error is None:
        _log_info(
            f"{label}: {entry.path} {entry.clone_method}() "
            f"ok clone_size={entry.clone_size}"
        )
    if entry.clone_method is not None and entry.clone_error is not None:
        _log_error(
            f"{label}: {entry.path} {entry.clone_method}() failed: {entry.clone_error}"
        )
    if entry.stale_size:
        _log_error(
            f"{label}: stale_selection_owner path={entry.path} "
            f"tensor_size={entry.size}"
        )


def _iter_selection_graph_children(owner: object, path: str) -> list[tuple[str, object]]:
    children: list[tuple[str, object]] = []
    for attribute_name in SELECTION_GRAPH_ATTRIBUTE_NAMES:
        exists, value = _safe_getattr(owner, path, attribute_name)
        if not exists:
            continue
        child_path = f"{path}.{attribute_name}"
        if callable(value):
            supported, reason = _supports_safe_no_arg_call(value)
            if not supported:
                _log_info(f"{child_path}() skipped: {reason}")
                continue
            try:
                value = value()
            except Exception as exc:  # pragma: no cover - defensive runtime probe
                _log_error(f"{child_path}() failed: {exc}")
                continue
            children.append((f"{child_path}()", value))
            continue
        children.append((child_path, value))
    return children


def _collect_selection_lifetime_snapshot(
    label: str,
    scene: object | None,
    model: object | None,
) -> dict[str, SelectionSnapshotEntry]:
    model_splat_count = _infer_model_splat_count(model)
    _log_info(f"{label}: model_splat_count={model_splat_count}")
    queue: list[tuple[int, str, object | None]] = [
        (0, "lichtfeld", lf),
        (0, "scene", scene),
        (0, "model", model),
    ]
    aliases: dict[int, str] = {}
    visited_paths: set[str] = set()
    snapshot: dict[str, SelectionSnapshotEntry] = {}

    while queue:
        depth, path, value = queue.pop(0)
        if value is None or path in visited_paths:
            continue
        visited_paths.add(path)

        entry = _capture_selection_snapshot_entry(path, value, model_splat_count, aliases)
        snapshot[path] = entry
        _log_selection_snapshot_entry(label, entry)

        if depth >= MAX_SELECTION_SNAPSHOT_DEPTH:
            continue
        if _is_selection_tensor_like(path, value):
            continue

        for child_path, child_value in _iter_selection_graph_children(value, path):
            if child_path in visited_paths:
                continue
            queue.append((depth + 1, child_path, child_value))

    stale_owner = _first_stale_owner(snapshot)
    if stale_owner is not None:
        _log_error(f"{label}: first_stale_owner={stale_owner}")
    invalid_clone_owner = _first_invalid_clone_owner(snapshot)
    if invalid_clone_owner is not None:
        _log_error(f"{label}: first_invalid_clone_owner={invalid_clone_owner}")
    return snapshot


def _first_stale_owner(snapshot: dict[str, SelectionSnapshotEntry]) -> str | None:
    for path, entry in snapshot.items():
        if entry.stale_size:
            return path
    return None


def _first_invalid_clone_owner(snapshot: dict[str, SelectionSnapshotEntry]) -> str | None:
    for path, entry in snapshot.items():
        if entry.clone_error is not None:
            return path
    return None


def _log_selection_lifetime_diff(
    label: str,
    before: dict[str, SelectionSnapshotEntry],
    after: dict[str, SelectionSnapshotEntry],
) -> None:
    before_paths = set(before)
    after_paths = set(after)
    for path in sorted(before_paths - after_paths):
        _log_info(f"{label}: removed_owner={path}")
    for path in sorted(after_paths - before_paths):
        _log_info(f"{label}: added_owner={path}")
    for path in sorted(before_paths & after_paths):
        previous = before[path]
        current = after[path]
        if previous.object_id != current.object_id:
            _log_info(
                f"{label}: owner_identity_changed path={path} "
                f"before=0x{previous.object_id:x} after=0x{current.object_id:x}"
            )
        if previous.size != current.size:
            _log_info(
                f"{label}: owner_size_changed path={path} "
                f"before={previous.size} after={current.size}"
            )
        if previous.clone_error != current.clone_error:
            _log_info(
                f"{label}: owner_clone_state_changed path={path} "
                f"before={previous.clone_error!r} after={current.clone_error!r}"
            )


def _log_tensor_runtime_diagnostics(scene: object | None, model: object | None) -> None:
    tensor_type = getattr(lf, "Tensor", None)
    if tensor_type is None:
        _log_info("lichtfeld.Tensor: missing")
    else:
        _log_info(
            "lichtfeld.Tensor: "
            f"type={_type_name(tensor_type)} repr={_safe_repr(tensor_type)} "
            f"signature={_safe_signature(tensor_type)}"
        )
        _log_public_attributes("lichtfeld.Tensor", tensor_type)
        _log_tensor_capabilities("lichtfeld.Tensor", tensor_type)

    if scene is not None and hasattr(scene, "selection_mask"):
        _log_tensor_details("scene.selection_mask", getattr(scene, "selection_mask"))

    if model is not None and hasattr(model, "deleted"):
        _log_tensor_details("model.deleted", getattr(model, "deleted"))

    if model is not None:
        get_means = getattr(model, "get_means", None)
        if callable(get_means):
            try:
                means = get_means()
            except Exception as exc:  # pragma: no cover - defensive runtime probe
                _log_error(f"model.get_means() failed: {exc}")
            else:
                _log_tensor_details("model.get_means()", means)


def _log_native_selection_runtime_diagnostics(scene: object | None) -> None:
    for attribute_name in NATIVE_SELECTION_NAMES:
        _log_callable_details(f"lichtfeld.{attribute_name}", getattr(lf, attribute_name, None))
        value = getattr(lf, attribute_name, None)
        if value is not None and not callable(value):
            _log_public_attributes(f"lichtfeld.{attribute_name}", value)

    if scene is None:
        return

    for attribute_name in ("set_selection", "clear_selection", "selection", "selection_groups"):
        value = getattr(scene, attribute_name, None)
        _log_callable_details(f"scene.{attribute_name}", value)
        if value is not None and not callable(value):
            _log_public_attributes(f"scene.{attribute_name}", value)


def _restore_native_selection_state(
    scene: object,
    original_scene_selection: object | None,
    original_top_selection: object | None,
    had_selection: bool | None,
) -> None:
    set_selection = getattr(scene, "set_selection", None)
    clear_selection = getattr(scene, "clear_selection", None)
    deselect_all = getattr(lf, "deselect_all", None)

    if callable(set_selection):
        for candidate in (original_scene_selection, original_top_selection):
            if candidate is None:
                continue
            try:
                set_selection(candidate)
                _log_info("native selection restore via scene.set_selection(...) succeeded")
                return
            except Exception as exc:  # pragma: no cover - defensive runtime probe
                _log_error(f"scene.set_selection(restore) failed: {exc}")

    if had_selection is False:
        if callable(clear_selection):
            clear_selection()
            _log_info("native selection cleared via scene.clear_selection()")
            return
        if callable(deselect_all):
            deselect_all()
            _log_info("native selection cleared via lichtfeld.deselect_all()")
            return

    raise RuntimeError("could not restore original native selection state")


def _configure_repo_import_path() -> None:
    from .test_runner import _configure_import_path

    _configure_import_path()


def _build_tensor_clone(mask: list[bool], template: object) -> object:
    clone = None
    for method_name in ("clone", "copy"):
        method = getattr(template, method_name, None)
        if callable(method):
            clone = method()
            break
    if clone is None:
        raise RuntimeError("template does not support clone() or copy()")

    fill = getattr(clone, "fill", None)
    if callable(fill):
        try:
            fill(False)
        except TypeError:
            fill(0)

    set_item = getattr(clone, "__setitem__", None)
    if not callable(set_item):
        raise RuntimeError("template clone does not support __setitem__")
    for index, value in enumerate(mask):
        set_item(index, bool(value))
    return clone


def run_tensor_mask_construction_diagnostics() -> tuple[bool, str]:
    """Try safe tensor-mask construction strategies and restore the scene afterwards."""
    try:
        _configure_repo_import_path()
        from lichtfeld_mcp.adapters.lichtfeld.utils import coerce_boolean_mask, to_lf_selection_mask
    except Exception as exc:
        message = f"adapter helper import failed: {exc}"
        _log_error(message)
        return False, message

    scene = _safe_get_scene()
    model = _safe_get_model(scene)
    if scene is None:
        message = "no active scene available for tensor-mask diagnostics"
        _log_error(message)
        return False, message

    original_selection = getattr(scene, "selection_mask", None)
    original_mask = coerce_boolean_mask(original_selection) if original_selection is not None else []
    mask_length = len(original_mask)
    if mask_length == 0 and model is not None and hasattr(model, "deleted"):
        original_mask = coerce_boolean_mask(getattr(model, "deleted"))
        mask_length = len(original_mask)
    if mask_length == 0:
        message = "could not determine selection mask length from scene.selection_mask or model.deleted"
        _log_error(message)
        return False, message

    trial_mask = [False] * mask_length
    if mask_length > 0:
        trial_mask[0] = True
    _log_info(f"trial_mask length={mask_length} selected_count={sum(trial_mask)}")

    strategies: list[tuple[str, object]] = []
    if original_selection is not None:
        strategies.append(("scene.selection_mask clone", original_selection))
    if model is not None and hasattr(model, "deleted"):
        strategies.append(("model.deleted clone", getattr(model, "deleted")))

    success = False
    for strategy_name, template in strategies:
        try:
            candidate = _build_tensor_clone(trial_mask, template)
            _log_info(f"{strategy_name}: tensor clone strategy constructed type={_type_name(candidate)}")
            scene.set_selection_mask(candidate)
            _log_info(f"{strategy_name}: scene.set_selection_mask(...) succeeded")
            success = True
            break
        except Exception as exc:  # pragma: no cover - defensive runtime probe
            _log_error(f"{strategy_name}: failed: {exc}")

    for strategy_name, builder in (
        (
            "adapter.to_lf_selection_mask",
            lambda: to_lf_selection_mask(trial_mask, lf, scene=scene, model=model),
        ),
        ("lichtfeld.Tensor(mask)", lambda: lf.Tensor(trial_mask)),
        ("lichtfeld.Tensor(data=mask)", lambda: lf.Tensor(data=trial_mask)),
    ):
        try:
            candidate = builder()
            _log_info(f"{strategy_name}: constructed type={_type_name(candidate)}")
            scene.set_selection_mask(candidate)
            _log_info(f"{strategy_name}: scene.set_selection_mask(...) succeeded")
            success = True
            break
        except Exception as exc:  # pragma: no cover - defensive runtime probe
            _log_error(f"{strategy_name}: failed: {exc}")

    try:
        if original_selection is not None:
            scene.set_selection_mask(original_selection)
            _log_info("original scene.selection_mask restored")
        else:
            restored = to_lf_selection_mask(original_mask, lf, scene=scene, model=model)
            scene.set_selection_mask(restored)
            _log_info("original selection state rebuilt and restored")
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        _log_error(f"restore failed: {exc}")
        return False, f"restore failed: {exc}"

    if not success:
        return False, "no tensor mask construction strategy succeeded"
    return True, "tensor mask diagnostic completed"


def run_native_selection_api_diagnostics() -> tuple[bool, str]:
    """Try native selection entry points with a tiny selection and then restore state."""
    scene = _safe_get_scene()
    model = _safe_get_model(scene)
    if scene is None or model is None:
        message = "active scene/model unavailable for native selection diagnostics"
        _log_error(message)
        return False, message

    _log_native_selection_runtime_diagnostics(scene)

    try:
        from lichtfeld_mcp.adapters.lichtfeld.gaussian import extract_position_rows
    except Exception as exc:
        message = f"could not import gaussian helpers: {exc}"
        _log_error(message)
        return False, message

    position_rows = extract_position_rows(model)
    if not position_rows:
        message = "no splats available for native selection diagnostics"
        _log_error(message)
        return False, message

    original_scene_selection = getattr(scene, "selection", None)
    original_top_selection = getattr(lf, "selection", None)
    has_selection = getattr(lf, "has_selection", None)
    had_selection: bool | None = None
    if callable(has_selection):
        try:
            had_selection = bool(has_selection())
        except Exception as exc:  # pragma: no cover - defensive runtime probe
            _log_error(f"lichtfeld.has_selection() failed: {exc}")

    trial_indices = [0]
    _log_info(f"native trial_indices={trial_indices}")

    attempts: list[tuple[str, callable]] = []
    clear_selection = getattr(scene, "clear_selection", None)
    deselect_all = getattr(lf, "deselect_all", None)
    set_selection = getattr(scene, "set_selection", None)
    add_to_selection = getattr(lf, "add_to_selection", None)

    if callable(clear_selection):
        attempts.append(("scene.clear_selection()", clear_selection))
    if callable(deselect_all):
        attempts.append(("lichtfeld.deselect_all()", deselect_all))
    if callable(set_selection):
        attempts.append(("scene.set_selection([0])", lambda: set_selection(list(trial_indices))))
        attempts.append(("scene.set_selection((0,))", lambda: set_selection(tuple(trial_indices))))
    if callable(add_to_selection):
        attempts.append(("lichtfeld.add_to_selection([0])", lambda: add_to_selection(list(trial_indices))))
        attempts.append(("lichtfeld.add_to_selection((0,))", lambda: add_to_selection(tuple(trial_indices))))

    success = False
    for label, attempt in attempts:
        try:
            attempt()
            _log_info(f"{label}: succeeded")
            success = True
        except Exception as exc:  # pragma: no cover - defensive runtime probe
            _log_error(f"{label}: failed: {exc}")

    try:
        _restore_native_selection_state(
            scene,
            original_scene_selection,
            original_top_selection,
            had_selection,
        )
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        _log_error(f"native selection restore failed: {exc}")
        return False, f"native selection restore failed: {exc}"

    if not success:
        return False, "no native selection API strategy succeeded"
    return True, "native selection diagnostic completed"


def run_apply_deleted_selection_lifetime_diagnostics() -> tuple[bool, str]:
    """Trace selection-owner state across a permanent cleanup apply."""
    try:
        _configure_repo_import_path()
        from .runtime_config import snapshot_runtime_config
        from .test_runner import _build_adapter
    except Exception as exc:
        message = f"diagnostic setup failed: {exc}"
        _log_error(message)
        return False, message

    config = snapshot_runtime_config()
    _log_info(
        "Starting apply_deleted selection lifetime diagnostic with "
        f"ENABLE_SAFE_DELETE={config.enable_safe_delete}, "
        f"CONFIRM_SAFE_DELETE={config.confirm_safe_delete}."
    )
    if not config.enable_safe_delete:
        message = (
            "Apply-deleted selection lifetime diagnostic is disabled because "
            "ENABLE_SAFE_DELETE=False."
        )
        _log_error(message)
        return False, message
    if not config.confirm_safe_delete:
        message = (
            "Apply-deleted selection lifetime diagnostic is armed but not confirmed because "
            "CONFIRM_SAFE_DELETE=False."
        )
        _log_error(message)
        return False, message

    try:
        adapter, repository_root = _build_adapter()
        _log_info(f"LichtfeldAdapter instantiated from {repository_root}.")
    except Exception as exc:
        message = f"adapter setup failed: {exc}"
        _log_error(message)
        return False, message

    apply_cleanup_workspace_deleted = getattr(
        adapter,
        "apply_cleanup_workspace_deleted",
        None,
    )
    if not callable(apply_cleanup_workspace_deleted):
        message = "LichtfeldAdapter does not expose apply_cleanup_workspace_deleted()."
        _log_error(message)
        return False, message

    scene_before = _safe_get_scene()
    model_before = _safe_get_model(scene_before)
    before_snapshot = _collect_selection_lifetime_snapshot(
        "before apply_cleanup_workspace_deleted()",
        scene_before,
        model_before,
    )

    try:
        result = apply_cleanup_workspace_deleted()
    except Exception as exc:
        scene_after_failure = _safe_get_scene()
        model_after_failure = _safe_get_model(scene_after_failure)
        _collect_selection_lifetime_snapshot(
            "after failed apply_cleanup_workspace_deleted()",
            scene_after_failure,
            model_after_failure,
        )
        message = f"apply_cleanup_workspace_deleted() failed: {exc}"
        _log_error(message)
        return False, message

    scene_after = _safe_get_scene()
    model_after = _safe_get_model(scene_after)
    after_snapshot = _collect_selection_lifetime_snapshot(
        "after apply_cleanup_workspace_deleted()",
        scene_after,
        model_after,
    )
    _log_selection_lifetime_diff(
        "apply_deleted lifetime diff",
        before_snapshot,
        after_snapshot,
    )

    reacquired_scene = _safe_get_scene()
    reacquired_model = _safe_get_model(reacquired_scene)
    reacquired_snapshot = _collect_selection_lifetime_snapshot(
        "after reacquiring scene/model",
        reacquired_scene,
        reacquired_model,
    )
    _log_selection_lifetime_diff(
        "reacquired lifetime diff",
        after_snapshot,
        reacquired_snapshot,
    )

    stale_owner = _first_stale_owner(after_snapshot) or _first_stale_owner(reacquired_snapshot)
    invalid_clone_owner = _first_invalid_clone_owner(after_snapshot) or _first_invalid_clone_owner(
        reacquired_snapshot
    )
    if stale_owner is not None or invalid_clone_owner is not None:
        parts: list[str] = []
        if invalid_clone_owner is not None:
            parts.append(f"invalid clone owner={invalid_clone_owner}")
        if stale_owner is not None:
            parts.append(f"stale size owner={stale_owner}")
        message = "Detected stale native selection ownership after apply_deleted(): " + "; ".join(
            parts
        )
        _log_error(message)
        return False, message

    if not getattr(result, "ok", True):
        message = getattr(result, "message", "Permanent cleanup apply did not succeed.")
        _log_error(message)
        return False, message

    message = (
        "apply_deleted selection lifetime diagnostic completed without stale selection owners"
    )
    _log_info(message)
    return True, message


def run_lcht_mcp_diagnostics() -> tuple[bool, str]:
    """Log the active LichtFeld Studio Python API surface without mutating state."""
    visited: set[int] = set()
    try:
        _log_info(f"lichtfeld module type={_type_name(lf)}")
        _log_public_attributes("lichtfeld", lf)
        _probe_object("lichtfeld", lf, visited, depth=0)
        for attribute_name in CANDIDATE_NAMES:
            _probe_candidate_attribute(lf, "lichtfeld", attribute_name, visited, depth=0)
        scene = _safe_get_scene()
        model = _safe_get_model(scene)
        _log_tensor_runtime_diagnostics(scene, model)
        _log_native_selection_runtime_diagnostics(scene)
    except Exception as exc:  # pragma: no cover - defensive runtime probe
        message = f"diagnostic failed: {exc}"
        _log_error(message)
        return False, message

    message = "diagnostic completed"
    _log_info(message)
    return True, message
