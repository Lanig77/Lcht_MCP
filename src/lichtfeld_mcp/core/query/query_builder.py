from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lichtfeld_mcp.core.gaussian import Gaussian, GaussianId, RGBColor
from lichtfeld_mcp.core.history import HistoryEntry
from lichtfeld_mcp.core.query.actions import (
    DeleteAction,
    QueryAction,
    SetOpacityAction,
    TranslateAction,
)
from lichtfeld_mcp.core.query.expressions import QueryExpression
from lichtfeld_mcp.core.query.predicates import Color, Height, Opacity

if TYPE_CHECKING:
    from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud


@dataclass(frozen=True, slots=True)
class GaussianQuery:
    cloud: "GaussianCloud"
    expressions: tuple[QueryExpression, ...] = ()
    actions: tuple[QueryAction, ...] = ()

    def where(self, predicate: QueryExpression) -> "GaussianQuery":
        return GaussianQuery(
            cloud=self.cloud,
            expressions=self.expressions + (predicate,),
            actions=self.actions,
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

    def delete(self) -> "GaussianQuery":
        return self._with_action(DeleteAction())

    def translate(self, dx: float, dy: float, dz: float) -> "GaussianQuery":
        return self._with_action(TranslateAction(dx=dx, dy=dy, dz=dz))

    def set_opacity(self, value: float) -> "GaussianQuery":
        return self._with_action(SetOpacityAction(value=value))

    def execute(self) -> int:
        matches = self.cloud.execute(self)
        if not matches:
            return 0
        if not self.actions:
            return len(matches)
        before_state = self.cloud.snapshot(gaussian.id for gaussian in matches)
        current_matches = matches
        for action in self.actions:
            current_matches = action.apply(self.cloud, current_matches)
        after_state = self.cloud.snapshot(gaussian.id for gaussian in current_matches)
        self.cloud.record_history(
            HistoryEntry(
                action_type=self._history_action_type(),
                affected_ids=tuple(restore_point.gaussian.id for restore_point in before_state),
                before_state=before_state,
                after_state=after_state,
                metadata={
                    "actions": tuple(action.action_type for action in self.actions),
                    "affected_count": len(before_state),
                },
            )
        )
        return len(before_state)

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

    def _with_action(self, action: QueryAction) -> "GaussianQuery":
        return GaussianQuery(
            cloud=self.cloud,
            expressions=self.expressions,
            actions=self.actions + (action,),
        )

    def _history_action_type(self) -> str:
        if len(self.actions) == 1:
            return self.actions[0].action_type
        return "query_pipeline"
