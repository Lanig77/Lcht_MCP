from __future__ import annotations

from dataclasses import dataclass

from lichtfeld_mcp.core.constraints import (
    normalize_height_range,
    validate_color_tolerance,
    validate_rgb_color,
)
from lichtfeld_mcp.core.gaussian import RGBColor
from lichtfeld_mcp.errors import InvalidParameterError

from .expressions import ColorSimilarityExpression, ComparisonExpression, RangeExpression
from .operators import GT, GTE, LT, LTE


def _validate_opacity_bound(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    if not 0.0 <= value <= 1.0:
        raise InvalidParameterError(f"{name} must be between 0.0 and 1.0.")
    return value


def _normalize_scalar_range(
    lower: float | None,
    upper: float | None,
) -> tuple[float | None, float | None]:
    if lower is None or upper is None:
        return lower, upper
    if lower <= upper:
        return lower, upper
    return upper, lower


@dataclass(frozen=True, slots=True)
class ScalarPredicateField:
    field_name: str
    range_normalizer: callable | None = None
    value_validator: callable | None = None

    def between(
        self,
        lower: float | None,
        upper: float | None,
    ) -> RangeExpression:
        lower = self._validate_value(lower, f"min_{self.field_name}")
        upper = self._validate_value(upper, f"max_{self.field_name}")
        if self.range_normalizer is not None:
            lower, upper = self.range_normalizer(lower, upper)
        else:
            lower, upper = _normalize_scalar_range(lower, upper)
        return RangeExpression(field_name=self.field_name, lower=lower, upper=upper)

    def greater_than(self, value: float) -> ComparisonExpression:
        return self > value

    def greater_than_or_equal(self, value: float) -> ComparisonExpression:
        return self >= value

    def less_than(self, value: float) -> ComparisonExpression:
        return self < value

    def less_than_or_equal(self, value: float) -> ComparisonExpression:
        return self <= value

    def __gt__(self, value: float) -> ComparisonExpression:
        return ComparisonExpression(
            field_name=self.field_name,
            operator=GT,
            value=self._validate_value(value, self.field_name),
        )

    def __ge__(self, value: float) -> ComparisonExpression:
        return ComparisonExpression(
            field_name=self.field_name,
            operator=GTE,
            value=self._validate_value(value, self.field_name),
        )

    def __lt__(self, value: float) -> ComparisonExpression:
        return ComparisonExpression(
            field_name=self.field_name,
            operator=LT,
            value=self._validate_value(value, self.field_name),
        )

    def __le__(self, value: float) -> ComparisonExpression:
        return ComparisonExpression(
            field_name=self.field_name,
            operator=LTE,
            value=self._validate_value(value, self.field_name),
        )

    def _validate_value(self, value: float | None, label: str) -> float | None:
        if self.value_validator is None:
            return value
        return self.value_validator(value, label)


@dataclass(frozen=True, slots=True)
class ColorPredicateField:
    field_name: str = "color"

    def similar(
        self,
        rgb: tuple[int, int, int] | RGBColor,
        *,
        tolerance: int = 0,
    ) -> ColorSimilarityExpression:
        if isinstance(rgb, RGBColor):
            color = rgb
        else:
            r, g, b = validate_rgb_color(*rgb)
            color = RGBColor(r=r, g=g, b=b)
        return ColorSimilarityExpression(
            color=color,
            tolerance=validate_color_tolerance(tolerance),
        )


Height = ScalarPredicateField(
    field_name="height",
    range_normalizer=normalize_height_range,
)
Opacity = ScalarPredicateField(
    field_name="opacity",
    value_validator=_validate_opacity_bound,
)
Scale = ScalarPredicateField(field_name="scale")
Density = ScalarPredicateField(field_name="density")
Color = ColorPredicateField()
