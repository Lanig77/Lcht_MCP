"""Selection-mask helpers for the LichtFeld plugin adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect

from lichtfeld_mcp.core.constraints import validate_color_tolerance, validate_rgb_color
from lichtfeld_mcp.core.requests import HeightRange
from lichtfeld_mcp.errors import AdapterUnavailableError, InvalidParameterError

from .utils import coerce_boolean_mask, to_lf_selection_mask


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

    def current_selection_mask(
        self,
        scene: object,
        expected_length: int,
        *,
        lf_module: object | None = None,
    ) -> list[bool] | None:
        mask = self.cached_mask(expected_length)
        if mask is not None:
            return mask
        return self.read_scene_selection_mask(
            scene,
            expected_length,
            lf_module=lf_module,
            allow_invalid_mask=True,
        )

    def get_selected_count(
        self,
        scene: object,
        expected_length: int,
        *,
        lf_module: object | None = None,
    ) -> int:
        mask = self.current_selection_mask(
            scene,
            expected_length,
            lf_module=lf_module,
        )
        if mask is None:
            return 0
        return sum(mask)

    def read_native_selection_mask(self, scene: object) -> object | None:
        for attribute_name in ("selection_mask", "_selection_mask", "get_selection_mask"):
            candidate = getattr(scene, attribute_name, None)
            if callable(candidate):
                try:
                    candidate = candidate()
                except Exception:
                    continue
            if candidate is None:
                continue
            if isinstance(candidate, (list, tuple)):
                continue
            return candidate
        return None

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

    def selected_indices(self, selection_mask: list[bool]) -> list[int]:
        return [index for index, selected in enumerate(selection_mask) if selected]

    def apply_native_selection(
        self,
        scene: object,
        indices: list[int],
        lf_module: object,
    ) -> None:
        errors: list[str] = []
        cleared = self._clear_native_selection(scene, lf_module, errors)

        if not indices:
            if cleared:
                return
            raise self._native_selection_error(scene, lf_module, errors)

        set_selection = getattr(scene, "set_selection", None)
        if callable(set_selection):
            for label, payload in (
                ("scene.set_selection(list)", list(indices)),
                ("scene.set_selection(tuple)", tuple(indices)),
            ):
                try:
                    set_selection(payload)
                    return
                except Exception as exc:
                    errors.append(f"{label}: {exc}")

        add_to_selection = getattr(lf_module, "add_to_selection", None)
        if callable(add_to_selection):
            if not cleared:
                errors.append(
                    "lichtfeld.add_to_selection skipped because selection could not be cleared first"
                )
            else:
                for label, payload in (
                    ("lichtfeld.add_to_selection(list)", list(indices)),
                    ("lichtfeld.add_to_selection(tuple)", tuple(indices)),
                ):
                    try:
                        add_to_selection(payload)
                        return
                    except Exception as exc:
                        errors.append(f"{label}: {exc}")

        raise self._native_selection_error(scene, lf_module, errors)

    def apply_scene_selection_mask(
        self,
        scene: object,
        mask: list[bool],
        lf_module: object,
        model: object | None = None,
    ) -> None:
        setter = getattr(scene, "set_selection_mask", None)
        if not callable(setter):
            raise AdapterUnavailableError(
                "Active LichtFeld scene does not expose set_selection_mask for selection updates."
            )
        setter(to_lf_selection_mask(mask, lf_module, scene=scene, model=model))

    def clear_scene_selection_mask(
        self,
        scene: object,
        expected_length: int,
        lf_module: object,
        model: object | None = None,
    ) -> None:
        cleared_mask = [False] * expected_length
        setter = getattr(scene, "set_selection_mask", None)
        if callable(setter):
            setter(
                to_lf_selection_mask(
                    cleared_mask,
                    lf_module,
                    scene=scene,
                    model=model,
                )
            )
            return
        for attribute_name in ("selection_mask", "_selection_mask", "last_selection_mask"):
            if hasattr(scene, attribute_name):
                setattr(scene, attribute_name, list(cleared_mask))
                return

    def clear_selection_via_scene(self, scene: object) -> bool:
        clear_selection = getattr(scene, "clear_selection", None)
        if not callable(clear_selection):
            return False
        clear_selection()
        return True

    def deselect_all(self, lf_module: object) -> bool:
        deselect_all = getattr(lf_module, "deselect_all", None)
        if not callable(deselect_all):
            return False
        deselect_all()
        return True

    def reset_selection_state(self, scene: object) -> bool:
        reset_selection_state = getattr(scene, "reset_selection_state", None)
        if not callable(reset_selection_state):
            return False
        reset_selection_state()
        return True

    def read_scene_selection_mask(
        self,
        scene: object,
        expected_length: int,
        *,
        lf_module: object | None = None,
        allow_invalid_mask: bool = False,
    ) -> list[bool] | None:
        has_selection = self._has_active_selection(scene, lf_module=lf_module)
        if has_selection is False:
            return None
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
            try:
                mask = coerce_boolean_mask(candidate)
            except AdapterUnavailableError:
                if allow_invalid_mask:
                    return None
                raise
            if len(mask) != expected_length:
                continue
            return mask
        return None

    def _has_active_selection(
        self,
        scene: object,
        *,
        lf_module: object | None = None,
    ) -> bool | None:
        for owner in (lf_module, scene):
            if owner is None:
                continue
            has_selection = getattr(owner, "has_selection", None)
            if not callable(has_selection):
                continue
            try:
                return bool(has_selection())
            except Exception:
                continue
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

    @staticmethod
    def _callable_signature(value: object) -> str:
        try:
            return str(inspect.signature(value))
        except (TypeError, ValueError):
            return "<signature unavailable>"

    def _clear_native_selection(
        self,
        scene: object,
        lf_module: object,
        errors: list[str],
    ) -> bool:
        cleared = False
        try:
            cleared = self.clear_selection_via_scene(scene) or cleared
        except Exception as exc:
            errors.append(f"scene.clear_selection(): {exc}")

        try:
            cleared = self.deselect_all(lf_module) or cleared
        except Exception as exc:
            errors.append(f"lichtfeld.deselect_all(): {exc}")

        return cleared

    def _native_selection_error(
        self,
        scene: object,
        lf_module: object,
        errors: list[str],
    ) -> AdapterUnavailableError:
        set_selection = getattr(scene, "set_selection", None)
        add_to_selection = getattr(lf_module, "add_to_selection", None)
        details = "; ".join(errors) if errors else "no compatible native selection entry point found"
        return AdapterUnavailableError(
            "LichtFeld native selection API could not accept Python index lists. "
            f"scene.set_selection signature={self._callable_signature(set_selection)}; "
            f"lichtfeld.add_to_selection signature={self._callable_signature(add_to_selection)}. "
            f"Failures: {details}. Run Diagnose Native Selection API for runtime details."
        )
