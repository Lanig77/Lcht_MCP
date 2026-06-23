"""Low-level helpers for the LichtFeld plugin adapter."""

from __future__ import annotations

import importlib

from lichtfeld_mcp.errors import AdapterUnavailableError


def load_lichtfeld() -> object:
    try:
        return importlib.import_module("lichtfeld")
    except ModuleNotFoundError as exc:
        if exc.name not in {None, "lichtfeld"}:
            raise
        raise AdapterUnavailableError(
            "LichtFeld Studio Python plugin API is not available. "
            "Install or launch LichtFeld Studio with Python plugin support."
        ) from exc
    except ImportError as exc:
        raise AdapterUnavailableError(
            "LichtFeld Studio Python plugin API could not be imported: "
            f"{exc}."
        ) from exc


def require_active_scene(lichtfeld_module: object) -> object:
    get_scene = getattr(lichtfeld_module, "get_scene", None)
    if not callable(get_scene):
        raise AdapterUnavailableError(
            "LichtFeld Studio Python plugin API does not expose get_scene()."
        )
    try:
        scene = get_scene()
    except Exception as exc:
        raise AdapterUnavailableError(
            "LichtFeld Studio get_scene() failed to provide an active scene."
        ) from exc
    if scene is None:
        raise AdapterUnavailableError(
            "No active LichtFeld scene is available from lichtfeld.get_scene()."
        )
    combined_model = getattr(scene, "combined_model", None)
    if not callable(combined_model):
        raise AdapterUnavailableError(
            "Active LichtFeld scene is invalid: combined_model() is not available."
        )
    return scene


def require_combined_model(scene: object) -> object:
    combined_model = getattr(scene, "combined_model", None)
    if not callable(combined_model):
        raise AdapterUnavailableError(
            "Active LichtFeld scene is invalid: combined_model() is not available."
        )
    try:
        combined_model = combined_model()
    except Exception as exc:
        raise AdapterUnavailableError(
            "Active LichtFeld scene combined_model() failed."
        ) from exc
    if combined_model is None:
        raise AdapterUnavailableError(
            "No active LichtFeld combined model is available for statistics."
        )
    return combined_model


def materialize_array(value: object) -> object:
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
    return current


def is_scalar(value: object) -> bool:
    return isinstance(value, (int, float))


def coerce_boolean_mask(value: object) -> list[bool]:
    materialized = materialize_array(value)
    if materialized is None:
        return []
    if isinstance(materialized, (list, tuple)):
        items = list(materialized)
    else:
        try:
            items = list(materialized)
        except TypeError as exc:
            raise AdapterUnavailableError(
                "LichtFeld selection mask values are not iterable."
            ) from exc
    return [bool(item) for item in items]


def _tensor_template_candidates(
    scene: object | None,
    model: object | None,
    *,
    prefer_model_templates: bool = False,
) -> list[object]:
    candidates: list[object] = []
    owner_specs = (
        (
            (model, ("deleted", "get_deleted_mask", "has_deleted_mask")),
            (scene, ("selection_mask", "get_selection_mask")),
        )
        if prefer_model_templates
        else (
            (scene, ("selection_mask", "get_selection_mask")),
            (model, ("deleted", "get_deleted_mask", "has_deleted_mask")),
        )
    )
    for owner, names in owner_specs:
        if owner is None:
            continue
        for attribute_name in names:
            candidate = getattr(owner, attribute_name, None)
            if callable(candidate):
                try:
                    candidate = candidate()
                except Exception:
                    continue
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _is_tensor_template_candidate(candidate: object) -> bool:
    if isinstance(candidate, (list, tuple, set, frozenset, dict, str, bytes)):
        return False
    return any(hasattr(candidate, attribute_name) for attribute_name in ("clone", "fill", "tolist"))


def _clone_tensor_candidate(candidate: object) -> object | None:
    if not _is_tensor_template_candidate(candidate):
        return None
    for method_name in ("clone", "copy"):
        method = getattr(candidate, method_name, None)
        if not callable(method):
            continue
        return method()
    return None


def _populate_tensor_mask(target: object, normalized_mask: list[bool]) -> object:
    fill = getattr(target, "fill", None)
    if callable(fill):
        try:
            fill(False)
        except TypeError:
            fill(0)

    set_item = getattr(target, "__setitem__", None)
    if not callable(set_item):
        raise AdapterUnavailableError(
            "LichtFeld Tensor mask template does not support item assignment."
        )
    for index, value in enumerate(normalized_mask):
        set_item(index, bool(value))
    return target


def _build_mask_from_template(
    normalized_mask: list[bool],
    *,
    scene: object | None,
    model: object | None,
) -> object | None:
    for candidate in _tensor_template_candidates(scene, model):
        cloned = _clone_tensor_candidate(candidate)
        if cloned is None:
            continue
        try:
            populated = _populate_tensor_mask(cloned, normalized_mask)
        except (AdapterUnavailableError, IndexError, KeyError, TypeError, ValueError):
            continue
        candidate_mask = coerce_boolean_mask(populated)
        if len(candidate_mask) != len(normalized_mask):
            continue
        return populated
    return None


def _tensor_candidate_length(candidate: object) -> int | None:
    shape = getattr(candidate, "shape", None)
    if shape is not None:
        try:
            if len(shape) > 0:
                return int(shape[0])
        except Exception:
            pass
    try:
        return len(candidate)  # type: ignore[arg-type]
    except Exception:
        return None


def build_empty_lf_selection_mask(
    expected_length: int,
    lf_module: object,
    *,
    scene: object | None = None,
    model: object | None = None,
) -> object:
    # After apply_deleted(), scene.selection_mask can already be invalidated while
    # model.deleted has the current compacted size. Prefer the model-owned mask
    # template here so clearing selection does not clone a stale scene tensor.
    for candidate in _tensor_template_candidates(
        scene,
        model,
        prefer_model_templates=True,
    ):
        cloned = _clone_tensor_candidate(candidate)
        if cloned is None:
            continue
        fill = getattr(cloned, "fill", None)
        if not callable(fill):
            continue
        try:
            try:
                fill(False)
            except TypeError:
                fill(0)
        except Exception:
            continue
        if _tensor_candidate_length(cloned) != expected_length:
            continue
        return cloned

    raise AdapterUnavailableError(
        "LichtFeld Studio Python plugin API does not expose a current-size native selection "
        "mask template for clearing renderer selection state."
    )


def to_lf_selection_mask(
    mask: object,
    lf_module: object,
    *,
    scene: object | None = None,
    model: object | None = None,
) -> object:
    normalized_mask = coerce_boolean_mask(mask)
    template_mask = _build_mask_from_template(
        normalized_mask,
        scene=scene,
        model=model,
    )
    if template_mask is not None:
        return template_mask

    tensor_factory = getattr(lf_module, "Tensor", None)
    if callable(tensor_factory):
        for attempt in (
            lambda: tensor_factory(normalized_mask),
            lambda: tensor_factory(data=normalized_mask),
        ):
            try:
                return attempt()
            except TypeError:
                continue
            except Exception as exc:
                raise AdapterUnavailableError(
                    "LichtFeld Tensor conversion failed for selection mask."
                ) from exc

    tensor_factory = getattr(lf_module, "tensor", None)
    if callable(tensor_factory):
        try:
            return tensor_factory(normalized_mask)
        except Exception as exc:
            raise AdapterUnavailableError(
                "LichtFeld tensor() conversion failed for selection mask."
            ) from exc

    raise AdapterUnavailableError(
        "LichtFeld Studio Python plugin API does not expose a Tensor construction "
        "strategy compatible with selection masks."
    )


def not_implemented(method_name: str, **_: object) -> None:
    raise NotImplementedError(
        f"LichtFeld plugin adapter skeleton does not implement '{method_name}' yet."
    )
