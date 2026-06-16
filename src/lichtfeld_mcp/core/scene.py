from dataclasses import dataclass, field

from .camera_set import CameraSet
from .capabilities import Capabilities
from .edit_manager import EditManager
from .export_manager import ExportManager
from .gaussian import BoundingBox, RGBColor
from .gaussian_cloud import GaussianCloud
from .gaussian_query import GaussianQuery
from .history import HistoryStack
from .measurement_manager import MeasurementManager
from .metadata import Metadata
from .selection_manager import SelectionManager
from .statistics import Statistics


@dataclass(slots=True)
class Scene:
    gaussian_cloud: GaussianCloud = field(default_factory=GaussianCloud)
    camera_set: CameraSet = field(default_factory=CameraSet)
    selection_manager: SelectionManager = field(default_factory=SelectionManager)
    edit_manager: EditManager = field(default_factory=EditManager)
    measurement_manager: MeasurementManager = field(default_factory=MeasurementManager)
    export_manager: ExportManager = field(default_factory=ExportManager)
    history_stack: HistoryStack = field(default_factory=HistoryStack)
    statistics: Statistics = field(default_factory=Statistics)
    metadata: Metadata = field(default_factory=Metadata)
    capabilities: Capabilities = field(default_factory=Capabilities)

    def __post_init__(self) -> None:
        self.gaussians.bind_history(
            self.history,
            on_change=self.edit_manager._sync_history_state,
        )
        self.edit_manager.attach(self.gaussians, self.selection, self.history)

    @property
    def gaussians(self) -> GaussianCloud:
        return self.gaussian_cloud

    @property
    def edit(self) -> EditManager:
        return self.edit_manager

    @property
    def history(self) -> HistoryStack:
        return self.history_stack

    @property
    def selection(self) -> SelectionManager:
        return self.selection_manager

    def is_empty(self) -> bool:
        return self.gaussians.is_empty()

    def gaussian_count(self) -> int:
        return self.gaussians.count()

    def bounding_box(self) -> BoundingBox | None:
        return self.gaussians.bounding_box()

    def select_query(self, query: GaussianQuery) -> None:
        self.selection.clear()
        self.selection.select(query.ids())

    def select_by_height(
        self,
        min_z: float | None = None,
        max_z: float | None = None,
    ) -> None:
        self.select_query(self.gaussians.query().by_height(min_z=min_z, max_z=max_z))

    def select_by_opacity(
        self,
        min_opacity: float | None = None,
        max_opacity: float | None = None,
    ) -> None:
        self.select_query(
            self.gaussians.query().by_opacity(min_opacity=min_opacity, max_opacity=max_opacity)
        )

    def select_by_color(self, color: RGBColor, tolerance: int = 0) -> None:
        self.select_query(self.gaussians.query().by_color(color=color, tolerance=tolerance))
