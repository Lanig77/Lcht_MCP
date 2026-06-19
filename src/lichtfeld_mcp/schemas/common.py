"""Shared Pydantic models returned by the MCP tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Vec3(BaseModel):
    """Three-dimensional vector."""

    x: float = Field(description="X coordinate")
    y: float = Field(description="Y coordinate")
    z: float = Field(description="Z coordinate")


class Box3D(BaseModel):
    """Axis-aligned 3D selection or crop box."""

    min: Vec3
    max: Vec3


class ToolResult(BaseModel):
    """Generic tool result."""

    ok: bool = True
    message: str


class ProjectInfo(BaseModel):
    """Opened project metadata."""

    path: str
    name: str
    splat_count: int
    selected_count: int = 0


class SceneStats(BaseModel):
    """Synthetic or real statistics describing a Gaussian scene."""

    project_name: str
    project_path: str
    splat_count: int
    selected_count: int
    file_size_mb: float
    estimated_vram_mb: float
    bounds: Box3D
    sh_degree: int
    opacity_mean: float
    density_score: float
    history_length: int


class SelectionResult(BaseModel):
    """Selection operation result."""

    selected_count: int
    selection_mode: Literal["replace", "add", "subtract"]
    message: str


class CleanupSelectionPreviewResult(BaseModel):
    """Cleanup-selection preview result."""

    selected_count: int
    selection_percentage: float
    selection_mode: Literal["replace"]
    selection_source: str
    approximate: bool
    message: str


class ExportResult(BaseModel):
    """Export operation result."""

    output_path: str
    format: str
    message: str


class OptimizationResult(BaseModel):
    """Optimization operation result."""

    target: str
    before_splats: int
    after_splats: int
    sh_degree: int
    estimated_vram_mb: float
    applied_rules: list[str]
    message: str


class HistoryEntry(BaseModel):
    """History entry for undo/debug."""

    index: int
    action: str
    details: dict[str, object]


class MeasurementResult(BaseModel):
    """Simple measurement output."""

    kind: str
    value: float
    unit: str
    message: str
