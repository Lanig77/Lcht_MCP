from __future__ import annotations

import importlib
import sys


def _clear_modules() -> None:
    module_names = {
        "lichtfeld_mcp.adapters.base",
        "lichtfeld_mcp.adapters.lichtfeld",
        "lichtfeld_mcp.adapters.lichtfeld.adapter",
        "lichtfeld_mcp.core",
        "lichtfeld_mcp.core.scene_analysis",
        "lichtfeld_mcp.core.scene_api",
        "lichtfeld_mcp.services.scene_service",
        "lichtfeld_mcp.tools.scene",
    }
    for module_name in module_names:
        sys.modules.pop(module_name, None)


def test_scene_analysis_import_paths_do_not_trigger_circular_imports():
    _clear_modules()

    base_module = importlib.import_module("lichtfeld_mcp.adapters.base")
    assert hasattr(base_module, "LichtfeldAdapter")

    lichtfeld_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    concrete_adapter = getattr(lichtfeld_module, "LichtfeldAdapter")
    assert concrete_adapter.__name__ == "LichtfeldAdapter"

    service_module = importlib.import_module("lichtfeld_mcp.services.scene_service")
    assert hasattr(service_module, "SceneService")

    tool_module = importlib.import_module("lichtfeld_mcp.tools.scene")
    assert hasattr(tool_module, "analyze_scene")
