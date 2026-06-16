import inspect

from lichtfeld_mcp.core.camera_set import CameraSet
from lichtfeld_mcp.core.capabilities import Capabilities
from lichtfeld_mcp.core.edit_manager import EditManager
from lichtfeld_mcp.core.export_manager import ExportManager
from lichtfeld_mcp.core.gaussian_cloud import GaussianCloud
from lichtfeld_mcp.core.measurement_manager import MeasurementManager
from lichtfeld_mcp.core.metadata import Metadata
from lichtfeld_mcp.core.scene import Scene
from lichtfeld_mcp.core.selection_manager import SelectionManager
from lichtfeld_mcp.core.statistics import Statistics


def test_scene_instantiates_with_defaults():
    scene = Scene()

    assert isinstance(scene.gaussian_cloud, GaussianCloud)
    assert isinstance(scene.camera_set, CameraSet)
    assert isinstance(scene.selection_manager, SelectionManager)
    assert isinstance(scene.edit_manager, EditManager)
    assert isinstance(scene.measurement_manager, MeasurementManager)
    assert isinstance(scene.export_manager, ExportManager)
    assert isinstance(scene.statistics, Statistics)
    assert isinstance(scene.metadata, Metadata)
    assert isinstance(scene.capabilities, Capabilities)
    assert scene.gaussian_cloud.splat_count == 0
    assert scene.selection_manager.selection_mode == "replace"
    assert scene.measurement_manager.unit == "m"


def test_scene_accepts_explicit_domain_components():
    scene = Scene(
        gaussian_cloud=GaussianCloud(splat_count=42, sh_degree=3),
        metadata=Metadata(project_name="demo_scene"),
        capabilities=Capabilities(supports_export=True),
    )

    assert scene.gaussian_cloud.splat_count == 42
    assert scene.gaussian_cloud.sh_degree == 3
    assert scene.metadata.project_name == "demo_scene"
    assert scene.capabilities.supports_export is True


def test_domain_modules_do_not_import_runtime_layers():
    modules = [
        inspect.getmodule(Scene),
        inspect.getmodule(GaussianCloud),
        inspect.getmodule(CameraSet),
        inspect.getmodule(SelectionManager),
        inspect.getmodule(EditManager),
        inspect.getmodule(MeasurementManager),
        inspect.getmodule(ExportManager),
        inspect.getmodule(Metadata),
        inspect.getmodule(Statistics),
        inspect.getmodule(Capabilities),
    ]

    forbidden_tokens = [
        "lichtfeld_mcp.tools",
        "lichtfeld_mcp.services",
        "lichtfeld_mcp.adapters",
        "import mcp",
        "from mcp",
        "SceneService",
        "Lichtfeld",
    ]

    for module in modules:
        source = inspect.getsource(module)
        for token in forbidden_tokens:
            assert token not in source
