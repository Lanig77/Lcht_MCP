from dataclasses import dataclass, field

from .camera_set import CameraSet
from .capabilities import Capabilities
from .edit_manager import EditManager
from .export_manager import ExportManager
from .gaussian_cloud import GaussianCloud
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
    statistics: Statistics = field(default_factory=Statistics)
    metadata: Metadata = field(default_factory=Metadata)
    capabilities: Capabilities = field(default_factory=Capabilities)
