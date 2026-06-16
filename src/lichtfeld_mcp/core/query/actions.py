from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from lichtfeld_mcp.core.gaussian import Gaussian, Position3D
from lichtfeld_mcp.errors import InvalidParameterError

if TYPE_CHECKING:
    from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud


class QueryAction:
    action_type = "query_action"

    def apply(
        self,
        cloud: "GaussianCloud",
        gaussians: list[Gaussian],
    ) -> list[Gaussian]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class DeleteAction(QueryAction):
    action_type = "delete"

    def apply(
        self,
        cloud: "GaussianCloud",
        gaussians: list[Gaussian],
    ) -> list[Gaussian]:
        cloud.remove_many(gaussian.id for gaussian in gaussians)
        return []


@dataclass(frozen=True, slots=True)
class TranslateAction(QueryAction):
    dx: float
    dy: float
    dz: float

    action_type = "translate"

    def apply(
        self,
        cloud: "GaussianCloud",
        gaussians: list[Gaussian],
    ) -> list[Gaussian]:
        updated_gaussians = [
            replace(
                gaussian,
                position=Position3D(
                    x=gaussian.position.x + self.dx,
                    y=gaussian.position.y + self.dy,
                    z=gaussian.position.z + self.dz,
                ),
            )
            for gaussian in gaussians
        ]
        cloud.replace_many(updated_gaussians)
        return updated_gaussians


@dataclass(frozen=True, slots=True)
class SetOpacityAction(QueryAction):
    value: float

    action_type = "set_opacity"

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise InvalidParameterError("opacity must be between 0.0 and 1.0.")

    def apply(
        self,
        cloud: "GaussianCloud",
        gaussians: list[Gaussian],
    ) -> list[Gaussian]:
        updated_gaussians = [
            replace(gaussian, opacity=self.value)
            for gaussian in gaussians
        ]
        cloud.replace_many(updated_gaussians)
        return updated_gaussians
