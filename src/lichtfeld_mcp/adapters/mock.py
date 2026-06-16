"""Deterministic mock adapter used until Lichtfeld exposes a public API.

This adapter simulates operations on a Gaussian Splatting scene. It is deliberately
simple but it preserves the semantics expected from a real editor: open a project,
select splats, delete/crop, optimize, export and undo.
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from lichtfeld_mcp.adapters.base import LichtfeldAdapter
from lichtfeld_mcp.errors import ProjectNotOpenError, UnsupportedTargetError
from lichtfeld_mcp.schemas.common import (
    Box3D,
    ExportResult,
    HistoryEntry,
    MeasurementResult,
    OptimizationResult,
    ProjectInfo,
    SceneStats,
    SelectionResult,
    ToolResult,
    Vec3,
    normalize_path,
)


@dataclass
class MockSceneState:
    path: str
    name: str
    splat_count: int = 4_200_000
    selected_count: int = 0
    file_size_mb: float = 840.0
    bounds: Box3D = field(
        default_factory=lambda: Box3D(
            min=Vec3(x=-5.0, y=-5.0, z=-0.1), max=Vec3(x=5.0, y=5.0, z=4.0)
        )
    )
    sh_degree: int = 3
    opacity_mean: float = 0.73
    density_score: float = 0.82


class MockLichtfeldAdapter(LichtfeldAdapter):
    """In-memory adapter for development and demonstrations."""

    SUPPORTED_EXPORTS = {"ply", "spz", "splat", "json"}
    TARGET_RULES = {
        "quest3": {"max_splats": 2_000_000, "sh_degree": 2, "rules": ["cap_splats", "sh_degree_2", "enable_lod"]},
        "web": {"max_splats": 1_500_000, "sh_degree": 2, "rules": ["cap_splats", "quantize", "enable_lod"]},
        "mobile": {"max_splats": 900_000, "sh_degree": 1, "rules": ["aggressive_decimation", "quantize"]},
        "unreal": {"max_splats": 5_000_000, "sh_degree": 3, "rules": ["preserve_quality", "generate_metadata"]},
        "unity": {"max_splats": 3_000_000, "sh_degree": 2, "rules": ["balance_quality", "generate_metadata"]},
        "archive": {"max_splats": None, "sh_degree": 3, "rules": ["preserve_quality", "write_manifest"]},
    }

    def __init__(self) -> None:
        self._scene: MockSceneState | None = None
        self._snapshots: list[MockSceneState] = []
        self._history: list[HistoryEntry] = []

    def _require_scene(self) -> MockSceneState:
        if self._scene is None:
            raise ProjectNotOpenError("No Lichtfeld project is currently open.")
        return self._scene

    def _push_history(self, action: str, details: dict[str, object]) -> None:
        if self._scene is not None:
            self._snapshots.append(deepcopy(self._scene))
        self._history.append(HistoryEntry(index=len(self._history), action=action, details=details))

    def open_project(self, path: str) -> ProjectInfo:
        normalized = normalize_path(path)
        name = Path(normalized).stem or "untitled_scene"
        # Derive stable fake complexity from project name.
        seed = sum(ord(ch) for ch in name)
        splats = 1_500_000 + (seed % 6_000_000)
        size = round(splats / 5000.0, 2)
        self._scene = MockSceneState(path=normalized, name=name, splat_count=splats, file_size_mb=size)
        self._snapshots.clear()
        self._history.clear()
        self._push_history("open_project", {"path": normalized})
        return ProjectInfo(path=normalized, name=name, splat_count=splats, selected_count=0)

    def save_project(self) -> ToolResult:
        scene = self._require_scene()
        self._push_history("save_project", {"path": scene.path})
        return ToolResult(message=f"Project saved: {scene.path}")

    def close_project(self) -> ToolResult:
        scene = self._require_scene()
        name = scene.name
        self._push_history("close_project", {"name": name})
        self._scene = None
        return ToolResult(message=f"Project closed: {name}")

    def get_scene_stats(self) -> SceneStats:
        scene = self._require_scene()
        return SceneStats(
            project_name=scene.name,
            project_path=scene.path,
            splat_count=scene.splat_count,
            selected_count=scene.selected_count,
            file_size_mb=scene.file_size_mb,
            estimated_vram_mb=round(scene.splat_count * (32 + scene.sh_degree * 12) / 1_000_000, 2),
            bounds=scene.bounds,
            sh_degree=scene.sh_degree,
            opacity_mean=scene.opacity_mean,
            density_score=scene.density_score,
            history_length=len(self._history),
        )

    def select_by_box(self, box: Box3D, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        self._push_history("select_by_box", {"box": box.model_dump(), "mode": mode})
        selected = max(1, int(scene.splat_count * 0.18))
        scene.selected_count = self._apply_selection_mode(scene.selected_count, selected, mode, scene.splat_count)
        return SelectionResult(selected_count=scene.selected_count, selection_mode=mode, message="Box selection applied.")

    def select_by_height(self, z_min: float | None, z_max: float | None, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        self._push_history("select_by_height", {"z_min": z_min, "z_max": z_max, "mode": mode})
        selected = max(1, int(scene.splat_count * 0.25))
        scene.selected_count = self._apply_selection_mode(scene.selected_count, selected, mode, scene.splat_count)
        return SelectionResult(selected_count=scene.selected_count, selection_mode=mode, message="Height selection applied.")

    def select_by_color(self, r: int, g: int, b: int, tolerance: int = 20, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        self._push_history("select_by_color", {"r": r, "g": g, "b": b, "tolerance": tolerance, "mode": mode})
        selected = max(1, int(scene.splat_count * min(0.4, max(0.02, tolerance / 255.0))))
        scene.selected_count = self._apply_selection_mode(scene.selected_count, selected, mode, scene.splat_count)
        return SelectionResult(selected_count=scene.selected_count, selection_mode=mode, message="Color selection applied.")

    @staticmethod
    def _apply_selection_mode(current: int, selected: int, mode: str, total: int) -> int:
        if mode == "add":
            return min(total, current + selected)
        if mode == "subtract":
            return max(0, current - selected)
        return min(total, selected)

    def delete_selection(self) -> ToolResult:
        scene = self._require_scene()
        deleted = scene.selected_count
        self._push_history("delete_selection", {"deleted": deleted})
        scene.splat_count = max(0, scene.splat_count - deleted)
        scene.selected_count = 0
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        return ToolResult(message=f"Deleted {deleted:,} selected splats.")

    def crop_by_box(self, box: Box3D, keep_inside: bool = True) -> ToolResult:
        scene = self._require_scene()
        self._push_history("crop_by_box", {"box": box.model_dump(), "keep_inside": keep_inside})
        factor = 0.65 if keep_inside else 0.82
        before = scene.splat_count
        scene.splat_count = int(scene.splat_count * factor)
        scene.selected_count = 0
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        return ToolResult(message=f"Cropped scene from {before:,} to {scene.splat_count:,} splats.")

    def crop_by_height(self, z_min: float | None, z_max: float | None, keep_inside: bool = True) -> ToolResult:
        scene = self._require_scene()
        self._push_history("crop_by_height", {"z_min": z_min, "z_max": z_max, "keep_inside": keep_inside})
        factor = 0.72 if keep_inside else 0.88
        before = scene.splat_count
        scene.splat_count = int(scene.splat_count * factor)
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        return ToolResult(message=f"Height crop applied from {before:,} to {scene.splat_count:,} splats.")

    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult:
        scene = self._require_scene()
        key = target.lower().strip()
        if key not in self.TARGET_RULES:
            raise UnsupportedTargetError(f"Unsupported target '{target}'. Supported: {sorted(self.TARGET_RULES)}")
        rules = self.TARGET_RULES[key]
        cap = max_splats if max_splats is not None else rules["max_splats"]
        before = scene.splat_count
        self._push_history("optimize_for_target", {"target": key, "max_splats": cap})
        if cap is not None:
            scene.splat_count = min(scene.splat_count, int(cap))
        scene.sh_degree = int(rules["sh_degree"])
        scene.file_size_mb = round(scene.splat_count / 6500.0, 2)
        estimated_vram = round(scene.splat_count * (32 + scene.sh_degree * 12) / 1_000_000, 2)
        return OptimizationResult(
            target=key,
            before_splats=before,
            after_splats=scene.splat_count,
            sh_degree=scene.sh_degree,
            estimated_vram_mb=estimated_vram,
            applied_rules=list(rules["rules"]),
            message=f"Scene optimized for {key}.",
        )

    def export_scene(self, output_path: str, fmt: str, target: str | None = None) -> ExportResult:
        self._require_scene()
        fmt_clean = fmt.lower().lstrip(".")
        if fmt_clean not in self.SUPPORTED_EXPORTS:
            raise UnsupportedTargetError(f"Unsupported export format '{fmt}'. Supported: {sorted(self.SUPPORTED_EXPORTS)}")
        normalized = normalize_path(output_path)
        self._push_history("export_scene", {"output_path": normalized, "format": fmt_clean, "target": target})
        return ExportResult(output_path=normalized, format=fmt_clean, message=f"Export simulated to {normalized}")

    def measure_distance(self, a: Vec3, b: Vec3, unit: str = "m") -> MeasurementResult:
        self._require_scene()
        value = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
        self._push_history("measure_distance", {"a": a.model_dump(), "b": b.model_dump(), "unit": unit})
        return MeasurementResult(kind="distance", value=round(value, 4), unit=unit, message=f"Distance: {value:.4f} {unit}")

    def undo(self) -> ToolResult:
        if not self._snapshots:
            return ToolResult(ok=False, message="Nothing to undo.")
        self._scene = self._snapshots.pop()
        self._history.append(HistoryEntry(index=len(self._history), action="undo", details={}))
        return ToolResult(message="Undo applied.")

    def list_history(self) -> list[HistoryEntry]:
        return list(self._history)
