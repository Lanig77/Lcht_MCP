"""Gaussian-model helpers for the LichtFeld plugin adapter."""

from __future__ import annotations

from lichtfeld_mcp.errors import AdapterUnavailableError, InvalidParameterError
from lichtfeld_mcp.schemas.common import Box3D, Vec3

from .utils import is_scalar, materialize_array


def extract_position_rows(model: object) -> list[tuple[float, float, float]]:
    means = None
    get_means = getattr(model, "get_means", None)
    if callable(get_means):
        means = get_means()
    elif hasattr(model, "means_raw"):
        means = getattr(model, "means_raw")
    if means is None:
        raise AdapterUnavailableError(
            "Active LichtFeld combined model does not expose gaussian positions."
        )
    return _coerce_position_rows(means)


def get_splat_count(position_rows: list[tuple[float, float, float]]) -> int:
    return len(position_rows)


def build_bounds(position_rows: list[tuple[float, float, float]]) -> Box3D:
    if not position_rows:
        origin = Vec3(x=0.0, y=0.0, z=0.0)
        return Box3D(min=origin, max=origin)
    xs = [row[0] for row in position_rows]
    ys = [row[1] for row in position_rows]
    zs = [row[2] for row in position_rows]
    return Box3D(
        min=Vec3(x=min(xs), y=min(ys), z=min(zs)),
        max=Vec3(x=max(xs), y=max(ys), z=max(zs)),
    )


def get_opacity_mean(model: object) -> float:
    try:
        values = extract_opacity_values(model)
    except AdapterUnavailableError:
        return 0.0
    if not values:
        return 0.0
    return round(sum(values) / len(values), 6)


def extract_opacity_values(model: object) -> list[float]:
    opacity = None
    get_opacity = getattr(model, "get_opacity", None)
    if callable(get_opacity):
        opacity = get_opacity()
    elif hasattr(model, "opacity"):
        opacity = getattr(model, "opacity")
    elif hasattr(model, "opacity_raw"):
        opacity = getattr(model, "opacity_raw")
    if opacity is None:
        raise AdapterUnavailableError(
            "Active LichtFeld combined model does not expose gaussian opacity values."
        )
    values = _flatten_scalars(opacity)
    for value in values:
        if not 0.0 <= value <= 1.0:
            raise InvalidParameterError("opacity values must be between 0.0 and 1.0.")
    return values


def extract_color_rows(model: object) -> list[tuple[float, float, float]]:
    colors = None
    for method_name in ("get_colors_rgb", "get_colors"):
        get_colors = getattr(model, method_name, None)
        if callable(get_colors):
            colors = get_colors()
            break
    if colors is None:
        for attribute_name in ("colors", "colors_raw", "rgb", "rgb_raw"):
            if hasattr(model, attribute_name):
                colors = getattr(model, attribute_name)
                break
    if colors is None:
        raise AdapterUnavailableError(
            "Active LichtFeld combined model does not expose gaussian color values."
        )
    return _normalize_color_rows(_coerce_triplet_rows(colors, "color"))


def get_sh_degree(model: object, scene: object) -> int:
    for owner in (model, scene):
        for attribute_name in ("sh_degree", "active_sh_degree"):
            value = getattr(owner, attribute_name, None)
            if isinstance(value, int):
                return value
    return 0


def _coerce_position_rows(values: object) -> list[tuple[float, float, float]]:
    return _coerce_triplet_rows(values, "position")


def _coerce_triplet_rows(values: object, label: str) -> list[tuple[float, float, float]]:
    materialized = materialize_array(values)
    if materialized is None:
        return []
    if isinstance(materialized, (list, tuple)):
        items = list(materialized)
    else:
        try:
            items = list(materialized)
        except TypeError as exc:
            raise AdapterUnavailableError(
                f"LichtFeld gaussian {label}s are not iterable."
            ) from exc
    if not items:
        return []
    if is_scalar(items[0]):
        if len(items) < 3:
            raise AdapterUnavailableError(
                f"LichtFeld gaussian {label} rows must expose at least three components."
            )
        return [_coerce_triplet_row(items, label)]
    return [_coerce_triplet_row(item, label) for item in items]


def _coerce_position_row(row: object) -> tuple[float, float, float]:
    return _coerce_triplet_row(row, "position")


def _coerce_triplet_row(row: object, label: str) -> tuple[float, float, float]:
    materialized = materialize_array(row)
    if isinstance(materialized, (list, tuple)):
        items = list(materialized)
    else:
        try:
            items = list(materialized)
        except TypeError as exc:
            raise AdapterUnavailableError(
                f"LichtFeld gaussian {label} rows are not iterable."
            ) from exc
    if len(items) < 3:
        raise AdapterUnavailableError(
            f"LichtFeld gaussian {label} rows must expose at least three components."
        )
    return (float(items[0]), float(items[1]), float(items[2]))


def _normalize_color_rows(
    color_rows: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    if not color_rows:
        return []
    color_values = [component for row in color_rows for component in row]
    if all(0.0 <= value <= 1.0 for value in color_values):
        return [
            (row[0] * 255.0, row[1] * 255.0, row[2] * 255.0)
            for row in color_rows
        ]
    if all(0.0 <= value <= 255.0 for value in color_values):
        return color_rows
    raise InvalidParameterError(
        "color values must be between 0.0 and 1.0 or between 0 and 255."
    )


def _flatten_scalars(value: object) -> list[float]:
    materialized = materialize_array(value)
    if materialized is None:
        return []
    if is_scalar(materialized):
        return [float(materialized)]
    if isinstance(materialized, (list, tuple)):
        items = list(materialized)
    else:
        try:
            items = list(materialized)
        except TypeError:
            return []
    flattened: list[float] = []
    for item in items:
        if is_scalar(item):
            flattened.append(float(item))
            continue
        flattened.extend(_flatten_scalars(item))
    return flattened
