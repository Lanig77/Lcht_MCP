"""LichtFeld Studio plugin adapter package.

This package intentionally avoids importing ``lichtfeld`` at module import time so the
normal test suite can run without LichtFeld Studio installed.
"""

from __future__ import annotations

import importlib

from .adapter import ClusterAnalysisSummary, LichtfeldAdapter, LichtfeldPluginAdapter

_IMPORTLIB = importlib

__all__ = ["ClusterAnalysisSummary", "LichtfeldAdapter", "LichtfeldPluginAdapter"]
