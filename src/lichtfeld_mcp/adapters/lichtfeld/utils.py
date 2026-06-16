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
    for attribute_name in (
        "scene",
        "current_scene",
        "active_scene",
        "get_scene",
        "get_current_scene",
        "get_active_scene",
    ):
        candidate = getattr(lichtfeld_module, attribute_name, None)
        if callable(candidate):
            candidate = candidate()
        if candidate is not None:
            return candidate
    raise AdapterUnavailableError(
        "No active LichtFeld scene is available from the Python plugin API."
    )


def require_combined_model(scene: object) -> object:
    combined_model = getattr(scene, "combined_model", None)
    if callable(combined_model):
        combined_model = combined_model()
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
