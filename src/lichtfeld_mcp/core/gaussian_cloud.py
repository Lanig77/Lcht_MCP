from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from lichtfeld_mcp.core.gaussian import BoundingBox, Gaussian, GaussianId, Position3D
from lichtfeld_mcp.core.history import GaussianRestorePoint, HistoryEntry, HistoryStack
from lichtfeld_mcp.core.query.expressions import (
    ColorSimilarityExpression,
    ComparisonExpression,
    LogicalExpression,
    NotExpression,
    QueryExpression,
    RangeExpression,
)
from lichtfeld_mcp.core.query.operators import AND, GT, GTE, LT, LTE, OR
from lichtfeld_mcp.errors import InvalidParameterError


@dataclass(slots=True)
class GaussianCloud:
    gaussians: list[Gaussian] = field(default_factory=list)
    splat_count: int = 0
    sh_degree: int = 0
    format_name: str | None = None
    _gaussians_by_id: dict[int, Gaussian] = field(init=False, default_factory=dict, repr=False)
    _history: HistoryStack | None = field(init=False, default=None, repr=False)
    _history_changed: Callable[[], None] | None = field(init=False, default=None, repr=False)

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

    def bind_history(
        self,
        history: HistoryStack | None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._history = history
        self._history_changed = on_change

    def snapshot(self, ids: Iterable[GaussianId]) -> tuple[GaussianRestorePoint, ...]:
        selected_values = {gaussian_id.value for gaussian_id in ids}
        if not selected_values:
            return ()
        return tuple(
            GaussianRestorePoint(index=index, gaussian=gaussian)
            for index, gaussian in enumerate(self.gaussians)
            if gaussian.id.value in selected_values
        )

    def restore_many(self, items: Iterable[tuple[int, Gaussian]]) -> int:
        restored = 0
        for index, gaussian in sorted(items, key=lambda item: item[0]):
            self._register(gaussian)
            insert_at = min(max(index, 0), len(self.gaussians))
            self.gaussians.insert(insert_at, gaussian)
            restored += 1
        if restored > 0:
            self.splat_count = len(self.gaussians)
        return restored

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

    def replace_many(self, gaussians: Iterable[Gaussian]) -> int:
        replacements = {gaussian.id.value: gaussian for gaussian in gaussians}
        if not replacements:
            return 0
        replaced = 0
        updated_gaussians: list[Gaussian] = []
        for gaussian in self.gaussians:
            replacement = replacements.get(gaussian.id.value)
            if replacement is None:
                updated_gaussians.append(gaussian)
                continue
            updated_gaussians.append(replacement)
            self._gaussians_by_id[gaussian.id.value] = replacement
            replaced += 1
        if replaced > 0:
            self.gaussians = updated_gaussians
            self.splat_count = len(self.gaussians)
        return replaced

    def get(self, id: GaussianId) -> Gaussian | None:
        return self._gaussians_by_id.get(id.value)

    def record_history(self, entry: HistoryEntry) -> None:
        if self._history is None:
            return
        self._history.push(entry)
        if self._history_changed is not None:
            self._history_changed()

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
        return GaussianQuery(cloud=self)

    def execute(self, query: GaussianQuery) -> list[Gaussian]:
        return [
            gaussian
            for gaussian in self.gaussians
            if all(self._matches(gaussian, expression) for expression in query.expressions)
        ]

    def _register(self, gaussian: Gaussian) -> None:
        if gaussian.id.value in self._gaussians_by_id:
            raise InvalidParameterError(f"Duplicate GaussianId {gaussian.id.value}.")
        self._gaussians_by_id[gaussian.id.value] = gaussian

    def _matches(self, gaussian: Gaussian, expression: QueryExpression) -> bool:
        if isinstance(expression, ComparisonExpression):
            value = self._resolve_scalar_value(gaussian, expression.field_name)
            if value is None:
                return False
            if expression.operator == GT:
                return value > expression.value
            if expression.operator == GTE:
                return value >= expression.value
            if expression.operator == LT:
                return value < expression.value
            if expression.operator == LTE:
                return value <= expression.value
            return False
        if isinstance(expression, RangeExpression):
            value = self._resolve_scalar_value(gaussian, expression.field_name)
            if value is None:
                return False
            if expression.lower is not None and value < expression.lower:
                return False
            if expression.upper is not None and value > expression.upper:
                return False
            return True
        if isinstance(expression, ColorSimilarityExpression):
            return (
                abs(gaussian.color.r - expression.color.r) <= expression.tolerance
                and abs(gaussian.color.g - expression.color.g) <= expression.tolerance
                and abs(gaussian.color.b - expression.color.b) <= expression.tolerance
            )
        if isinstance(expression, LogicalExpression):
            if expression.operator == AND:
                return self._matches(gaussian, expression.left) and self._matches(
                    gaussian,
                    expression.right,
                )
            if expression.operator == OR:
                return self._matches(gaussian, expression.left) or self._matches(
                    gaussian,
                    expression.right,
                )
            return False
        if isinstance(expression, NotExpression):
            return not self._matches(gaussian, expression.operand)
        return False

    @staticmethod
    def _resolve_scalar_value(gaussian: Gaussian, field_name: str) -> float | None:
        if field_name == "height":
            return gaussian.position.z
        if field_name == "opacity":
            return gaussian.opacity
        if field_name == "scale":
            return (gaussian.scale.x + gaussian.scale.y + gaussian.scale.z) / 3.0
        if field_name == "density":
            value = gaussian.metadata.get("density")
            if isinstance(value, (int, float)):
                return float(value)
            return None
        return None


from lichtfeld_mcp.core.gaussian_query import GaussianQuery
