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


def not_implemented(method_name: str, **_: object) -> None:
    raise NotImplementedError(
        f"LichtFeld plugin adapter skeleton does not implement '{method_name}' yet."
    )
