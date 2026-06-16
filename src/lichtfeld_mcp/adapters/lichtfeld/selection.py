"""Selection-mask helpers for the LichtFeld plugin adapter."""

from __future__ import annotations

from dataclasses import dataclass, field

from lichtfeld_mcp.core.constraints import validate_color_tolerance, validate_rgb_color
from lichtfeld_mcp.core.requests import HeightRange
from lichtfeld_mcp.errors import AdapterUnavailableError, InvalidParameterError

from .utils import coerce_boolean_mask


@dataclass(slots=True)
class SelectionState:
    _cached_mask: list[bool] | None = field(default=None, repr=False)

    def cache_mask(self, mask: list[bool]) -> None:
        self._cached_mask = list(mask)

    def clear_cache(self) -> None:
        self._cached_mask = None

    def cached_mask(self, expected_length: int) -> list[bool] | None:
        if self._cached_mask is None:
            return None
        if len(self._cached_mask) != expected_length:
            return None
        return list(self._cached_mask)

    def current_selection_mask(self, scene: object, expected_length: int) -> list[bool] | None:
        mask = self.read_scene_selection_mask(scene, expected_length)
        if mask is not None:
            return mask
        return self.cached_mask(expected_length)

    def get_selected_count(self, scene: object, expected_length: int) -> int:
        mask = self.current_selection_mask(scene, expected_length)
        if mask is None:
            return 0
        return sum(mask)

    def build_height_mask(
        self,
        position_rows: list[tuple[float, float, float]],
        height_range: HeightRange,
    ) -> list[bool]:
        return [
            self._is_within_height_range(position[2], height_range)
            for position in position_rows
        ]

    def build_opacity_mask(
        self,
        opacities: list[float],
        min_opacity: float | None = None,
        max_opacity: float | None = None,
    ) -> list[bool]:
        normalized_min, normalized_max = self._normalize_opacity_range(
            min_opacity=min_opacity,
            max_opacity=max_opacity,
        )
        return [
            self._is_within_opacity_range(opacity, normalized_min, normalized_max)
            for opacity in opacities
        ]

    def build_color_mask(
        self,
        colors: list[tuple[float, float, float]],
        rgb: tuple[int, int, int],
        tolerance: int,
    ) -> list[bool]:
        target_rgb = validate_rgb_color(*rgb)
        normalized_tolerance = validate_color_tolerance(tolerance)
        return [
            abs(color[0] - target_rgb[0]) <= normalized_tolerance
            and abs(color[1] - target_rgb[1]) <= normalized_tolerance
            and abs(color[2] - target_rgb[2]) <= normalized_tolerance
            for color in colors
        ]

    def merge_height_mask(
        self,
        scene: object,
        height_mask: list[bool],
        mode: str,
    ) -> list[bool]:
        return self.merge_selection_mask(scene, height_mask, mode)

    def merge_selection_mask(
        self,
        scene: object,
        selection_mask: list[bool],
        mode: str,
    ) -> list[bool]:
        if mode == "replace":
            return list(selection_mask)
        current_mask = self.current_selection_mask(scene, len(selection_mask))
        if current_mask is None:
            current_mask = [False] * len(selection_mask)
        if mode == "add":
            return [current or selected for current, selected in zip(current_mask, selection_mask)]
        return [current and not selected for current, selected in zip(current_mask, selection_mask)]

    def apply_scene_selection_mask(self, scene: object, mask: list[bool]) -> None:
        setter = getattr(scene, "set_selection_mask", None)
        if not callable(setter):
            raise AdapterUnavailableError(
                "Active LichtFeld scene does not expose set_selection_mask for selection updates."
            )
        setter(mask)

    def clear_scene_selection_mask(self, scene: object, expected_length: int) -> None:
        cleared_mask = [False] * expected_length
        setter = getattr(scene, "set_selection_mask", None)
        if callable(setter):
            setter(cleared_mask)
            return
        for attribute_name in ("selection_mask", "_selection_mask", "last_selection_mask"):
            if hasattr(scene, attribute_name):
                setattr(scene, attribute_name, list(cleared_mask))
                return

    def read_scene_selection_mask(
        self,
        scene: object,
        expected_length: int,
    ) -> list[bool] | None:
        for attribute_name in (
            "get_selection_mask",
            "selection_mask",
            "_selection_mask",
            "last_selection_mask",
        ):
            candidate = getattr(scene, attribute_name, None)
            if callable(candidate):
                candidate = candidate()
            if candidate is None:
                continue
            mask = coerce_boolean_mask(candidate)
            if len(mask) != expected_length:
                continue
            return mask
        return None

    @staticmethod
    def _normalize_opacity_range(
        min_opacity: float | None,
        max_opacity: float | None,
    ) -> tuple[float | None, float | None]:
        if min_opacity is not None and not 0.0 <= min_opacity <= 1.0:
            raise InvalidParameterError("min_opacity must be between 0.0 and 1.0.")
        if max_opacity is not None and not 0.0 <= max_opacity <= 1.0:
            raise InvalidParameterError("max_opacity must be between 0.0 and 1.0.")
        if min_opacity is None or max_opacity is None:
            return min_opacity, max_opacity
        if min_opacity <= max_opacity:
            return min_opacity, max_opacity
        return max_opacity, min_opacity

    @staticmethod
    def _is_within_height_range(z_value: float, height_range: HeightRange) -> bool:
        if height_range.z_min is not None and z_value < height_range.z_min:
            return False
        if height_range.z_max is not None and z_value > height_range.z_max:
            return False
        return True

    @staticmethod
    def _is_within_opacity_range(
        opacity: float,
        min_opacity: float | None,
        max_opacity: float | None,
    ) -> bool:
        if min_opacity is not None and opacity < min_opacity:
            return False
        if max_opacity is not None and opacity > max_opacity:
            return False
        return True
