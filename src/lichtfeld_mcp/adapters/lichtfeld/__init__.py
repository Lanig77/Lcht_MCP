"""LichtFeld Studio plugin adapter package.

This package intentionally avoids importing ``lichtfeld`` or the concrete adapter
module at package import time so the normal test suite can run without
LichtFeld Studio installed and without triggering adapter-side import cycles.
"""

from __future__ import annotations

import importlib
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .adapter import (
        ClusterAnalysisSummary,
        LichtfeldAdapter,
        LichtfeldPluginAdapter,
        VoxelClusterAnalysisSummary,
    )

__all__ = [
    "ClusterAnalysisSummary",
    "LichtfeldAdapter",
    "LichtfeldPluginAdapter",
    "VoxelClusterAnalysisSummary",
]

_IMPORTLIB = importlib


def __getattr__(name: str):
    if name == "importlib":
        return importlib
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(".adapter", __name__)
    return getattr(module, name)
