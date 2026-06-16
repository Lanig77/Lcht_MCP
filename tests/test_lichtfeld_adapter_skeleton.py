import builtins
import importlib
import sys

import pytest

from lichtfeld_mcp.errors import AdapterUnavailableError


def test_importing_lichtfeld_adapter_module_does_not_import_lichtfeld(monkeypatch):
    original_import = builtins.__import__
    requested_lichtfeld_imports: list[str] = []

    def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "lichtfeld" or name.startswith("lichtfeld."):
            requested_lichtfeld_imports.append(name)
            raise AssertionError("lichtfeld should not be imported at module import time")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", tracking_import)
    sys.modules.pop("lichtfeld_mcp.adapters.lichtfeld", None)

    module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")

    assert hasattr(module, "LichtfeldPluginAdapter")
    assert requested_lichtfeld_imports == []


def test_open_project_without_lichtfeld_raises_adapter_unavailable_error(monkeypatch):
    adapter_module = importlib.import_module("lichtfeld_mcp.adapters.lichtfeld")
    original_import_module = adapter_module.importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name == "lichtfeld":
            raise ModuleNotFoundError("No module named 'lichtfeld'", name="lichtfeld")
        return original_import_module(name, package)

    monkeypatch.setattr(adapter_module.importlib, "import_module", fake_import_module)

    adapter = adapter_module.LichtfeldPluginAdapter()

    with pytest.raises(
        AdapterUnavailableError,
        match="LichtFeld Studio Python plugin API is not available",
    ):
        adapter.open_project("demo_scene.lfp")
