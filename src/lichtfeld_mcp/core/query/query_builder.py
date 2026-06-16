from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lichtfeld_mcp.core.gaussian import Gaussian, GaussianId, RGBColor
from lichtfeld_mcp.core.query.expressions import QueryExpression
from lichtfeld_mcp.core.query.predicates import Color, Height, Opacity

if TYPE_CHECKING:
    from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud


@dataclass(frozen=True, slots=True)
class GaussianQuery:
    cloud: "GaussianCloud"
    expressions: tuple[QueryExpression, ...] = ()

    def where(self, predicate: QueryExpression) -> "GaussianQuery":
        return GaussianQuery(
            cloud=self.cloud,
            expressions=self.expressions + (predicate,),
        )

    def filter(self, predicate: QueryExpression) -> "GaussianQuery":
        return self.where(predicate)

    def all(self) -> list[Gaussian]:
        return self.cloud.execute(self)

    def result(self) -> list[Gaussian]:
        return self.all()

    def count(self) -> int:
        return len(self.cloud.execute(self))

    def ids(self) -> list[GaussianId]:
        return [gaussian.id for gaussian in self.cloud.execute(self)]

    def first(self) -> Gaussian | None:
        results = self.cloud.execute(self)
        if not results:
            return None
        return results[0]

    def by_height(
        self,
        min_z: float | None = None,
        max_z: float | None = None,
    ) -> "GaussianQuery":
        return self.where(Height.between(min_z, max_z))

    def by_opacity(
        self,
        min_opacity: float | None = None,
        max_opacity: float | None = None,
    ) -> "GaussianQuery":
        return self.where(Opacity.between(min_opacity, max_opacity))

    def by_color(self, color: RGBColor, tolerance: int = 0) -> "GaussianQuery":
        return self.where(
            Color.similar((color.r, color.g, color.b), tolerance=tolerance)
        )
