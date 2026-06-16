from __future__ import annotations

from dataclasses import dataclass, field

from lichtfeld_mcp.core.constraints import validate_rgb_color
from lichtfeld_mcp.errors import InvalidParameterError


@dataclass(frozen=True, slots=True)
class GaussianId:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise InvalidParameterError("GaussianId must be non-negative.")


@dataclass(frozen=True, slots=True)
class Position3D:
    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class Quaternion:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0


@dataclass(frozen=True, slots=True)
class Scale3D:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        for axis, value in (("x", self.x), ("y", self.y), ("z", self.z)):
            if value <= 0.0:
                raise InvalidParameterError(f"Scale3D.{axis} must be strictly positive.")


@dataclass(frozen=True, slots=True)
class RGBColor:
    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        r, g, b = validate_rgb_color(self.r, self.g, self.b)
        object.__setattr__(self, "r", r)
        object.__setattr__(self, "g", g)
        object.__setattr__(self, "b", b)


@dataclass(frozen=True, slots=True)
class SphericalHarmonics:
    coefficients: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class BoundingBox:
    min: Position3D
    max: Position3D


@dataclass(frozen=True, slots=True)
class Gaussian:
    id: GaussianId
    position: Position3D
    rotation: Quaternion = field(default_factory=Quaternion)
    scale: Scale3D = field(default_factory=lambda: Scale3D(1.0, 1.0, 1.0))
    opacity: float = 1.0
    color: RGBColor = field(default_factory=lambda: RGBColor(255, 255, 255))
    spherical_harmonics: SphericalHarmonics = field(default_factory=SphericalHarmonics)
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise InvalidParameterError("Gaussian.opacity must be between 0.0 and 1.0.")
