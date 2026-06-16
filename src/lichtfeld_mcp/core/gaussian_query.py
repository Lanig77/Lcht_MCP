from __future__ import annotations

from dataclasses import dataclass

from lichtfeld_mcp.core.constraints import normalize_height_range, validate_color_tolerance
from lichtfeld_mcp.core.gaussian import Gaussian, GaussianId, RGBColor
from lichtfeld_mcp.errors import InvalidParameterError


@dataclass(frozen=True, slots=True)
class GaussianQuery:
    gaussians: tuple[Gaussian, ...] = ()

    def by_height(
        self,
        min_z: float | None = None,
        max_z: float | None = None,
    ) -> GaussianQuery:
        min_z, max_z = normalize_height_range(min_z, max_z)
        return GaussianQuery(
            tuple(
                gaussian
                for gaussian in self.gaussians
                if (min_z is None or gaussian.position.z >= min_z)
                and (max_z is None or gaussian.position.z <= max_z)
            )
        )

    def by_opacity(
        self,
        min_opacity: float | None = None,
        max_opacity: float | None = None,
    ) -> GaussianQuery:
        min_opacity = _validate_opacity_bound(min_opacity, "min_opacity")
        max_opacity = _validate_opacity_bound(max_opacity, "max_opacity")
        if min_opacity is not None and max_opacity is not None and min_opacity > max_opacity:
            min_opacity, max_opacity = max_opacity, min_opacity
        return GaussianQuery(
            tuple(
                gaussian
                for gaussian in self.gaussians
                if (min_opacity is None or gaussian.opacity >= min_opacity)
                and (max_opacity is None or gaussian.opacity <= max_opacity)
            )
        )

    def by_color(self, color: RGBColor, tolerance: int = 0) -> GaussianQuery:
        tolerance = validate_color_tolerance(tolerance)
        return GaussianQuery(
            tuple(
                gaussian
                for gaussian in self.gaussians
                if abs(gaussian.color.r - color.r) <= tolerance
                and abs(gaussian.color.g - color.g) <= tolerance
                and abs(gaussian.color.b - color.b) <= tolerance
            )
        )

    def result(self) -> list[Gaussian]:
        return list(self.gaussians)

    def ids(self) -> list[GaussianId]:
        return [gaussian.id for gaussian in self.gaussians]

    def count(self) -> int:
        return len(self.gaussians)


def _validate_opacity_bound(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    if not 0.0 <= value <= 1.0:
        raise InvalidParameterError(f"{name} must be between 0.0 and 1.0.")
    return value
