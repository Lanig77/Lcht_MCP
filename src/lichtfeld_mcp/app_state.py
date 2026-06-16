"""Application state and adapter factory."""

from __future__ import annotations

import os

from lichtfeld_mcp.adapters.base import LichtfeldAdapter
from lichtfeld_mcp.adapters.mock import MockLichtfeldAdapter
from lichtfeld_mcp.core.scene_api import SceneAPI


_adapter: LichtfeldAdapter | None = None
_scene_api: SceneAPI | None = None


def get_adapter() -> LichtfeldAdapter:
    """Return a singleton adapter.

    Environment variable LICHTFELD_ADAPTER currently supports:
    - mock: deterministic local simulator

    Future implementations can add:
    - cli: call Lichtfeld Studio command line
    - python: use a native Python SDK
    - socket: communicate with a running Lichtfeld Studio process
    """

    global _adapter
    if _adapter is not None:
        return _adapter

    adapter_name = os.getenv("LICHTFELD_ADAPTER", "mock").lower().strip()
    if adapter_name == "mock":
        _adapter = MockLichtfeldAdapter()
        return _adapter

    raise RuntimeError(f"Unsupported LICHTFELD_ADAPTER={adapter_name!r}. Use 'mock' for now.")


def get_scene_api() -> SceneAPI:
    """Return a singleton scene API facade."""

    global _scene_api
    if _scene_api is None:
        _scene_api = SceneAPI(get_adapter())
    return _scene_api
