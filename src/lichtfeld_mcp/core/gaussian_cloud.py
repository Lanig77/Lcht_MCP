from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from lichtfeld_mcp.core.gaussian import BoundingBox, Gaussian, GaussianId, Position3D
from lichtfeld_mcp.errors import InvalidParameterError


@dataclass(slots=True)
class GaussianCloud:
    gaussians: list[Gaussian] = field(default_factory=list)
    splat_count: int = 0
    sh_degree: int = 0
    format_name: str | None = None
    _gaussians_by_id: dict[int, Gaussian] = field(init=False, default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for gaussian in self.gaussians:
            self._register(gaussian)
        if self.gaussians:
            self.splat_count = len(self.gaussians)

    def count(self) -> int:
        return len(self._gaussians_by_id) if self._gaussians_by_id else self.splat_count

    def ids(self) -> list[GaussianId]:
        return [gaussian.id for gaussian in self.gaussians]

    def is_empty(self) -> bool:
        return self.count() == 0

    def add(self, gaussian: Gaussian) -> None:
        self._register(gaussian)
        self.gaussians.append(gaussian)
        self.splat_count = len(self.gaussians)

    def remove_many(self, ids: Iterable[GaussianId]) -> int:
        selected_values = {gaussian_id.value for gaussian_id in ids}
        if not selected_values:
            return 0
        before = len(self.gaussians)
        self.gaussians = [
            gaussian for gaussian in self.gaussians if gaussian.id.value not in selected_values
        ]
        removed = before - len(self.gaussians)
        if removed == 0:
            return 0
        self._gaussians_by_id = {
            gaussian.id.value: gaussian for gaussian in self.gaussians
        }
        self.splat_count = len(self.gaussians)
        return removed

    def get(self, id: GaussianId) -> Gaussian | None:
        return self._gaussians_by_id.get(id.value)

    def bounding_box(self) -> BoundingBox | None:
        if not self.gaussians:
            return None
        min_x = min(gaussian.position.x for gaussian in self.gaussians)
        min_y = min(gaussian.position.y for gaussian in self.gaussians)
        min_z = min(gaussian.position.z for gaussian in self.gaussians)
        max_x = max(gaussian.position.x for gaussian in self.gaussians)
        max_y = max(gaussian.position.y for gaussian in self.gaussians)
        max_z = max(gaussian.position.z for gaussian in self.gaussians)
        return BoundingBox(
            min=Position3D(x=min_x, y=min_y, z=min_z),
            max=Position3D(x=max_x, y=max_y, z=max_z),
        )

    def query(self) -> GaussianQuery:
        return GaussianQuery(tuple(self.gaussians))

    def _register(self, gaussian: Gaussian) -> None:
        if gaussian.id.value in self._gaussians_by_id:
            raise InvalidParameterError(f"Duplicate GaussianId {gaussian.id.value}.")
        self._gaussians_by_id[gaussian.id.value] = gaussian


from lichtfeld_mcp.core.gaussian_query import GaussianQuery
