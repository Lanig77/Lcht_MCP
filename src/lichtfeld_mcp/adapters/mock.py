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
from lichtfeld_mcp.core.constraints import validate_selection_mode
from lichtfeld_mcp.core.scene_analysis import (
    AnalysisResult,
    AnalysisSeverity,
    CleanupCandidateSummary,
    SceneAnalysisReport,
    build_cleanup_candidate_summary,
)
from lichtfeld_mcp.core.presets import get_optimization_profile
from lichtfeld_mcp.core.requests import (
    BoxSelectionRequest,
    ColorSelectionRequest,
    ExportRequest,
    HeightRange,
    OptimizationRequest,
)
from lichtfeld_mcp.core.validation import normalize_measurement_unit, normalize_scene_path
from lichtfeld_mcp.errors import ProjectNotOpenError
from lichtfeld_mcp.schemas.common import (
    Box3D,
    CleanupSelectionPreviewResult,
    ExportResult,
    HistoryEntry,
    MeasurementResult,
    OptimizationResult,
    ProjectInfo,
    SceneStats,
    SelectionResult,
    ToolResult,
    Vec3,
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

    def __init__(self) -> None:
        self._scene: MockSceneState | None = None
        self._snapshots: list[MockSceneState] = []
        self._history: list[HistoryEntry] = []
        self._last_scene_analysis: SceneAnalysisReport | None = None
        self._last_cleanup_preview: CleanupCandidateSummary | None = None
        self._pending_cleanup_apply_count = 0

    def _require_scene(self) -> MockSceneState:
        if self._scene is None:
            raise ProjectNotOpenError("No Lichtfeld project is currently open.")
        return self._scene

    def _push_history(self, action: str, details: dict[str, object]) -> None:
        if self._scene is not None:
            self._snapshots.append(deepcopy(self._scene))
        self._history.append(HistoryEntry(index=len(self._history), action=action, details=details))

    def open_project(self, path: str) -> ProjectInfo:
        normalized = normalize_scene_path(path, label="project path")
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

    def preview_cleanup_candidates(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> CleanupCandidateSummary:
        if self._last_scene_analysis is None:
            raise ProjectNotOpenError("No previous scene analysis is available. Run Analyze Scene first.")
        report = self._last_scene_analysis
        self._last_cleanup_preview = build_cleanup_candidate_summary(report)
        return self._last_cleanup_preview

    def preview_cleanup_selection(self) -> CleanupSelectionPreviewResult:
        scene = self._require_scene()
        if self._last_scene_analysis is None:
            raise ProjectNotOpenError("No previous scene analysis is available. Run Analyze Scene first.")
        if self._last_cleanup_preview is None:
            raise ProjectNotOpenError(
                "No cleanup preview is available. Run Preview Cleanup Selection after Analyze Scene."
            )
        scene.selected_count = self._last_cleanup_preview.affected_splats_in_sample
        selection_source = "floating voxel clusters"
        if self._last_cleanup_preview.sparse_regions > 0:
            selection_source += ", sparse singleton regions"
        return CleanupSelectionPreviewResult(
            selected_count=scene.selected_count,
            selection_percentage=(
                0.0
                if scene.splat_count <= 0
                else scene.selected_count / scene.splat_count
            ),
            selection_mode="replace",
            selection_source=selection_source,
            approximate=self._last_cleanup_preview.approximate,
            message=(
                "Approximate sampled selection preview. "
                "Selected splats represent estimated cleanup regions. "
                "Run Detailed mode for a more precise preview."
                if self._last_cleanup_preview.approximate
                else "Exact cleanup selection preview."
            ),
        )

    def soft_delete_cleanup_candidates(self) -> ToolResult:
        scene = self._require_scene()
        if self._last_cleanup_preview is None:
            raise ProjectNotOpenError(
                "No cleanup preview is available. Run Preview Cleanup Selection first."
            )
        if self._last_cleanup_preview.approximate:
            raise ProjectNotOpenError(
                "Cleanup preview is approximate-only; no reliable native selection is available."
            )
        deleted = min(scene.splat_count, self._last_cleanup_preview.estimated_affected_splats)
        if deleted <= 0:
            raise ProjectNotOpenError("Cleanup preview did not identify any reliable cleanup candidates.")
        self._push_history("soft_delete_cleanup_candidates", {"deleted": deleted})
        scene.splat_count -= deleted
        scene.selected_count = 0
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        self._last_cleanup_preview = None
        self._pending_cleanup_apply_count = deleted
        return ToolResult(
            message=(
                f"Soft-deleted {deleted:,} cleanup candidate splats. "
                "Reversible until apply_deleted() is called."
            )
        )

    def apply_cleanup_candidates(self) -> ToolResult:
        scene = self._require_scene()
        if self._pending_cleanup_apply_count <= 0:
            raise ProjectNotOpenError(
                "No confirmed cleanup soft delete is available. "
                "Run Soft Delete Cleanup Preview after Preview Cleanup Selection."
            )
        deleted = min(scene.splat_count, self._pending_cleanup_apply_count)
        self._push_history("apply_cleanup_candidates", {"deleted": deleted})
        self._pending_cleanup_apply_count = 0
        return ToolResult(
            message=f"Permanently applied cleanup of {deleted:,} soft-deleted splats."
        )

    def analyze_scene(
        self,
        voxel_size: float = 0.25,
        min_voxel_cluster_size: int = 10,
        max_splats: int = 25_000,
        abort_if_above_limit: bool = False,
    ) -> SceneAnalysisReport:
        scene = self._require_scene()
        approximate = scene.splat_count > max_splats and not abort_if_above_limit
        aborted = scene.splat_count > max_splats and abort_if_above_limit
        results = [
            AnalysisResult(
                name="statistics",
                severity=AnalysisSeverity.INFO,
                summary="Scene statistics captured.",
                details={
                    "total_splats": scene.splat_count,
                    "deleted_splats": 0,
                    "selected_splats": scene.selected_count,
                },
            ),
            AnalysisResult(
                name="voxel_connectivity",
                severity=AnalysisSeverity.INFO,
                summary="Scene appears fully connected.",
                details={
                    "connected": True,
                    "floating_voxel_groups": 0,
                    "estimated_floating_splats": 0,
                    "small_voxel_clusters": 0,
                    "estimated_small_cluster_splats": 0,
                },
                recommendations=["No cleanup required."],
            ),
            AnalysisResult(
                name="bounding_box",
                severity=AnalysisSeverity.INFO,
                summary="Bounding box looks normal.",
                details={"distant_splats": 0, "abnormal_scene_size": False},
            ),
            AnalysisResult(
                name="density",
                severity=AnalysisSeverity.INFO,
                summary="Density distribution looks healthy.",
                details={
                    "occupied_voxels": max(1, min(max_splats, scene.splat_count) // max(1, min_voxel_cluster_size)),
                    "density_histogram": {"1": 0, "2-4": 0, "5-9": 0, "10-24": 1, "25+": 0},
                    "sparse_regions": 0,
                    "estimated_sparse_splats": 0,
                },
                recommendations=["Density looks healthy."],
            ),
        ]
        if aborted:
            results = [
                AnalysisResult(
                    name="statistics",
                    severity=AnalysisSeverity.WARNING,
                    summary="Scene analysis aborted by execution budget.",
                    details={
                        "total_splats": scene.splat_count,
                        "deleted_splats": 0,
                        "selected_splats": scene.selected_count,
                    },
                    warnings=["Analysis skipped because the execution budget was exceeded."],
                    recommendations=["Increase the analysis budget or allow sampled preview mode."],
                    score_impact=14,
                )
            ]

        warnings = [
            warning
            for result in results
            for warning in result.warnings
        ]
        recommendations = [
            recommendation
            for result in results
            for recommendation in result.recommendations
        ] or ["Scene is healthy."]
        report = SceneAnalysisReport(
            scene_stats={
                "scene_name": scene.name,
                "project_path": scene.path,
                "total_splats": scene.splat_count,
                "analyzed_splats": min(scene.splat_count, max_splats),
                "selected_splats": scene.selected_count,
                "deleted_splats": 0,
                "voxel_size": voxel_size,
                "min_voxel_cluster_size": min_voxel_cluster_size,
                "approximate": approximate,
                "sampling_stride": max(1, math.ceil(scene.splat_count / max_splats)),
                "used_native_sampling": False,
                "max_splats": max_splats,
                "aborted": aborted,
            },
            quality_score=max(0, 100 - sum(result.score_impact for result in results)),
            warnings=warnings,
            recommendations=recommendations,
            analysis_time=0.0,
            results=results,
        )
        self._last_scene_analysis = report
        return report

    def select_by_box(self, box: Box3D, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        request = BoxSelectionRequest(box=box, mode=mode)
        self._push_history("select_by_box", {"box": request.box.model_dump(), "mode": request.mode})
        selected = max(1, int(scene.splat_count * 0.18))
        scene.selected_count = self._apply_selection_mode(
            scene.selected_count,
            selected,
            request.mode,
            scene.splat_count,
        )
        return SelectionResult(
            selected_count=scene.selected_count,
            selection_mode=request.mode,
            message="Box selection applied.",
        )

    def select_by_height(self, z_min: float | None, z_max: float | None, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        normalized_mode = validate_selection_mode(mode)
        self._push_history(
            "select_by_height",
            {"z_min": height_range.z_min, "z_max": height_range.z_max, "mode": normalized_mode},
        )
        selected = max(1, int(scene.splat_count * 0.25))
        scene.selected_count = self._apply_selection_mode(
            scene.selected_count,
            selected,
            normalized_mode,
            scene.splat_count,
        )
        return SelectionResult(
            selected_count=scene.selected_count,
            selection_mode=normalized_mode,
            message="Height selection applied.",
        )

    def select_by_color(self, r: int, g: int, b: int, tolerance: int = 20, mode: str = "replace") -> SelectionResult:
        scene = self._require_scene()
        request = ColorSelectionRequest.from_rgb(r=r, g=g, b=b, tolerance=tolerance, mode=mode)
        self._push_history(
            "select_by_color",
            {
                "r": request.color.r,
                "g": request.color.g,
                "b": request.color.b,
                "tolerance": request.tolerance,
                "mode": request.mode,
            },
        )
        selected = max(1, int(scene.splat_count * min(0.4, max(0.02, request.tolerance / 255.0))))
        scene.selected_count = self._apply_selection_mode(
            scene.selected_count,
            selected,
            request.mode,
            scene.splat_count,
        )
        return SelectionResult(
            selected_count=scene.selected_count,
            selection_mode=request.mode,
            message="Color selection applied.",
        )

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
        request = BoxSelectionRequest(box=box)
        self._push_history("crop_by_box", {"box": request.box.model_dump(), "keep_inside": keep_inside})
        factor = 0.65 if keep_inside else 0.82
        before = scene.splat_count
        scene.splat_count = int(scene.splat_count * factor)
        scene.selected_count = 0
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        return ToolResult(message=f"Cropped scene from {before:,} to {scene.splat_count:,} splats.")

    def crop_by_height(self, z_min: float | None, z_max: float | None, keep_inside: bool = True) -> ToolResult:
        scene = self._require_scene()
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        self._push_history(
            "crop_by_height",
            {"z_min": height_range.z_min, "z_max": height_range.z_max, "keep_inside": keep_inside},
        )
        factor = 0.72 if keep_inside else 0.88
        before = scene.splat_count
        scene.splat_count = int(scene.splat_count * factor)
        scene.file_size_mb = round(scene.splat_count / 5000.0, 2)
        return ToolResult(message=f"Height crop applied from {before:,} to {scene.splat_count:,} splats.")

    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult:
        scene = self._require_scene()
        request = OptimizationRequest(target=target, max_splats=max_splats)
        profile = get_optimization_profile(request.target)
        cap = request.max_splats if request.max_splats is not None else profile.max_splats
        before = scene.splat_count
        self._push_history("optimize_for_target", {"target": request.target, "max_splats": cap})
        if cap is not None:
            scene.splat_count = min(scene.splat_count, int(cap))
        scene.sh_degree = profile.sh_degree
        scene.file_size_mb = round(scene.splat_count / 6500.0, 2)
        estimated_vram = round(scene.splat_count * (32 + scene.sh_degree * 12) / 1_000_000, 2)
        return OptimizationResult(
            target=request.target,
            before_splats=before,
            after_splats=scene.splat_count,
            sh_degree=scene.sh_degree,
            estimated_vram_mb=estimated_vram,
            applied_rules=list(profile.rules),
            message=f"Scene optimized for {request.target}.",
        )

    def export_scene(self, output_path: str, fmt: str, target: str | None = None) -> ExportResult:
        self._require_scene()
        request = ExportRequest(output_path=output_path, fmt=fmt, target=target)
        self._push_history(
            "export_scene",
            {"output_path": request.output_path, "format": request.fmt, "target": request.target},
        )
        return ExportResult(
            output_path=request.output_path,
            format=request.fmt,
            message=f"Export simulated to {request.output_path}",
        )

    def measure_distance(self, a: Vec3, b: Vec3, unit: str = "m") -> MeasurementResult:
        self._require_scene()
        normalized_unit = normalize_measurement_unit(unit)
        value = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
        self._push_history("measure_distance", {"a": a.model_dump(), "b": b.model_dump(), "unit": normalized_unit})
        return MeasurementResult(
            kind="distance",
            value=round(value, 4),
            unit=normalized_unit,
            message=f"Distance: {value:.4f} {normalized_unit}",
        )

    def undo(self) -> ToolResult:
        if not self._snapshots:
            return ToolResult(ok=False, message="Nothing to undo.")
        self._scene = self._snapshots.pop()
        self._history.append(HistoryEntry(index=len(self._history), action="undo", details={}))
        return ToolResult(message="Undo applied.")

    def list_history(self) -> list[HistoryEntry]:
        return list(self._history)
