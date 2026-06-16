"""Typed scene-domain request objects used internally by SceneAPI and adapters."""

from __future__ import annotations

from dataclasses import dataclass

from lichtfeld_mcp.core.constraints import (
    SelectionMode,
    normalize_height_range,
    validate_color_tolerance,
    validate_max_splats,
    validate_rgb_color,
    validate_selection_mode,
)
from lichtfeld_mcp.core.presets import normalize_export_format, normalize_target
from lichtfeld_mcp.core.validation import normalize_scene_path
from lichtfeld_mcp.schemas.common import Box3D, Vec3


@dataclass(frozen=True, slots=True)
class HeightRange:
    """Normalized height range for selection/crop operations."""

    z_min: float | None = None
    z_max: float | None = None

    def __post_init__(self) -> None:
        z_min, z_max = normalize_height_range(self.z_min, self.z_max)
        object.__setattr__(self, "z_min", z_min)
        object.__setattr__(self, "z_max", z_max)


@dataclass(frozen=True, slots=True)
class RGBColor:
    """Validated RGB triplet."""

    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        r, g, b = validate_rgb_color(self.r, self.g, self.b)
        object.__setattr__(self, "r", r)
        object.__setattr__(self, "g", g)
        object.__setattr__(self, "b", b)


@dataclass(frozen=True, slots=True)
class ColorSelectionRequest:
    """Validated color-based selection request."""

    color: RGBColor
    tolerance: int = 20
    mode: SelectionMode | str = "replace"

    def __post_init__(self) -> None:
        object.__setattr__(self, "tolerance", validate_color_tolerance(self.tolerance))
        object.__setattr__(self, "mode", validate_selection_mode(self.mode))

    @classmethod
    def from_rgb(
        cls,
        r: int,
        g: int,
        b: int,
        tolerance: int = 20,
        mode: SelectionMode | str = "replace",
    ) -> "ColorSelectionRequest":
        return cls(color=RGBColor(r=r, g=g, b=b), tolerance=tolerance, mode=mode)


@dataclass(frozen=True, slots=True)
class BoxSelectionRequest:
    """Validated box-based selection request."""

    box: Box3D
    mode: SelectionMode | str = "replace"

    def __post_init__(self) -> None:
        object.__setattr__(self, "box", _normalize_box(self.box))
        object.__setattr__(self, "mode", validate_selection_mode(self.mode))

    @classmethod
    def from_bounds(
        cls,
        min_x: float,
        min_y: float,
        min_z: float,
        max_x: float,
        max_y: float,
        max_z: float,
        mode: SelectionMode | str = "replace",
    ) -> "BoxSelectionRequest":
        return cls(
            box=Box3D(
                min=Vec3(x=min_x, y=min_y, z=min_z),
                max=Vec3(x=max_x, y=max_y, z=max_z),
            ),
            mode=mode,
        )


@dataclass(frozen=True, slots=True)
class OptimizationRequest:
    """Validated optimization request."""

    target: str
    max_splats: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", normalize_target(self.target))
        object.__setattr__(self, "max_splats", validate_max_splats(self.max_splats))


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """Validated export request."""

    output_path: str
    fmt: str = "ply"
    target: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "output_path",
            normalize_scene_path(self.output_path, label="output path"),
        )
        object.__setattr__(self, "fmt", normalize_export_format(self.fmt))
        normalized_target = normalize_target(self.target) if self.target is not None else None
        object.__setattr__(self, "target", normalized_target)


def _normalize_box(box: Box3D) -> Box3D:
    x0, x1 = sorted((box.min.x, box.max.x))
    y0, y1 = sorted((box.min.y, box.max.y))
    z0, z1 = sorted((box.min.z, box.max.z))
    return Box3D(
        min=Vec3(x=x0, y=y0, z=z0),
        max=Vec3(x=x1, y=y1, z=z1),
    )
