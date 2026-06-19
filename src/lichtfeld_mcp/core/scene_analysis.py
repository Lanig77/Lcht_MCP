from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from enum import Enum
import logging
import math
from time import perf_counter

from lichtfeld_mcp.core.gaussian import BoundingBox, Position3D
from lichtfeld_mcp.core.voxel_analysis import (
    analyze_voxel_clusters,
    largest_voxel_cluster,
    voxel_clusters_outside_largest,
)

logger = logging.getLogger(__name__)


class AnalysisSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    name: str
    severity: AnalysisSeverity
    summary: str
    details: dict[str, object]
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    score_impact: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "severity": self.severity.value,
            "summary": self.summary,
            "details": _serialize_value(self.details),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "score_impact": self.score_impact,
        }


@dataclass(frozen=True, slots=True)
class SceneAnalysisReport:
    scene_stats: dict[str, object]
    quality_score: int
    warnings: list[str]
    recommendations: list[str]
    analysis_time: float
    results: list[AnalysisResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_stats": _serialize_value(self.scene_stats),
            "quality_score": self.quality_score,
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "analysis_time": round(self.analysis_time, 6),
            "results": [result.to_dict() for result in self.results],
        }


@dataclass(frozen=True, slots=True)
class CleanupCandidateSummary:
    scene_name: str
    project_path: str
    total_splats: int
    quality_score: int
    analysis_time: float
    approximate: bool
    report_only: bool
    candidate_group_count: int
    estimated_affected_splats: int
    floating_voxel_groups: int
    estimated_floating_splats: int
    small_voxel_clusters: int
    estimated_small_cluster_splats: int
    sparse_regions: int
    estimated_sparse_splats: int
    warnings: list[str]
    recommendations: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_name": self.scene_name,
            "project_path": self.project_path,
            "total_splats": self.total_splats,
            "quality_score": self.quality_score,
            "analysis_time": round(self.analysis_time, 6),
            "approximate": self.approximate,
            "report_only": self.report_only,
            "candidate_group_count": self.candidate_group_count,
            "estimated_affected_splats": self.estimated_affected_splats,
            "floating_voxel_groups": self.floating_voxel_groups,
            "estimated_floating_splats": self.estimated_floating_splats,
            "small_voxel_clusters": self.small_voxel_clusters,
            "estimated_small_cluster_splats": self.estimated_small_cluster_splats,
            "sparse_regions": self.sparse_regions,
            "estimated_sparse_splats": self.estimated_sparse_splats,
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class SceneAnalysisContext:
    scene_name: str
    project_path: str
    positions: list[tuple[float, float, float]]
    total_splats: int
    analyzed_splats: int
    selected_splats: int
    deleted_splats: int
    voxel_size: float
    min_voxel_cluster_size: int
    approximate: bool
    sampling_stride: int
    used_native_sampling: bool
    max_splats: int
    aborted: bool = False


class SceneAnalysisModule:
    name = "analysis"

    def analyze(self, context: SceneAnalysisContext) -> AnalysisResult:
        raise NotImplementedError


class StatisticsAnalysis(SceneAnalysisModule):
    name = "statistics"

    def analyze(self, context: SceneAnalysisContext) -> AnalysisResult:
        warnings: list[str] = []
        recommendations: list[str] = []
        score_impact = 0
        severity = AnalysisSeverity.INFO
        summary = "Scene statistics captured."

        if context.selected_splats > 0:
            severity = AnalysisSeverity.WARNING
            score_impact = 6
            warnings.append(
                f"{_format_int(context.selected_splats)} splats are currently selected."
            )
            recommendations.append("Clear the active selection before cleanup preview.")
            summary = "Scene has an active selection."

        if context.deleted_splats > 0:
            warnings.append(
                f"{_format_int(context.deleted_splats)} splats are currently soft-deleted."
            )
            recommendations.append("Review pending deleted splats before exporting.")
            if severity is AnalysisSeverity.INFO:
                summary = "Scene contains pending soft-deleted splats."

        return AnalysisResult(
            name=self.name,
            severity=severity,
            summary=summary,
            details={
                "total_splats": context.total_splats,
                "deleted_splats": context.deleted_splats,
                "selected_splats": context.selected_splats,
            },
            warnings=warnings,
            recommendations=_unique_strings(recommendations),
            score_impact=score_impact,
        )


class VoxelConnectivityAnalysis(SceneAnalysisModule):
    name = "voxel_connectivity"

    def analyze(self, context: SceneAnalysisContext) -> AnalysisResult:
        if context.aborted:
            return _skipped_result(self.name)

        clusters = analyze_voxel_clusters(
            context.positions,
            voxel_size=context.voxel_size,
            min_voxel_cluster_size=1,
        )
        largest = largest_voxel_cluster(clusters)
        floating_clusters = voxel_clusters_outside_largest(clusters)
        floating_groups = len(floating_clusters)
        floating_splats = sum(cluster.estimated_splat_count for cluster in floating_clusters)
        small_clusters = [
            cluster
            for cluster in floating_clusters
            if cluster.voxel_count < context.min_voxel_cluster_size
        ]
        estimated_small_cluster_splats = sum(
            cluster.estimated_splat_count for cluster in small_clusters
        )
        floating_ratio = _safe_ratio(floating_splats, context.analyzed_splats)

        warnings: list[str] = []
        recommendations: list[str] = []
        severity = AnalysisSeverity.INFO
        score_impact = 0
        summary = "Scene appears fully connected."

        if floating_groups > 0:
            warnings.append(f"{floating_groups} floating voxel groups detected.")
            recommendations.append("Preview floating islands.")
            if floating_ratio > 0.05 or floating_groups >= 10:
                severity = AnalysisSeverity.CRITICAL
                score_impact = 24
                summary = "Large disconnected voxel regions detected."
            else:
                severity = AnalysisSeverity.WARNING
                score_impact = 12
                summary = "Small floating islands detected."
            recommendations.append(f"Estimated cleanup: {floating_ratio * 100.0:.1f}%")
        else:
            recommendations.append("No cleanup required.")

        return AnalysisResult(
            name=self.name,
            severity=severity,
            summary=summary,
            details={
                "connected": floating_groups == 0 and len(clusters) <= 1,
                "floating_voxel_groups": floating_groups,
                "estimated_floating_splats": floating_splats,
                "small_voxel_clusters": len(small_clusters),
                "estimated_small_cluster_splats": estimated_small_cluster_splats,
                "total_voxel_clusters": len(clusters),
                "largest_voxel_cluster_splats": 0 if largest is None else largest.estimated_splat_count,
            },
            warnings=warnings,
            recommendations=_unique_strings(recommendations),
            score_impact=score_impact,
        )


class BoundingBoxAnalysis(SceneAnalysisModule):
    name = "bounding_box"

    def analyze(self, context: SceneAnalysisContext) -> AnalysisResult:
        if context.aborted:
            return _skipped_result(self.name)

        bounds = _build_bounds(context.positions)
        span_x = bounds.max.x - bounds.min.x
        span_y = bounds.max.y - bounds.min.y
        span_z = bounds.max.z - bounds.min.z
        spans = (span_x, span_y, span_z)
        max_span = max(spans, default=0.0)

        distant_splats = _count_distant_splats(context.positions, context.voxel_size)
        warning_threshold = max(context.voxel_size * 400.0, 100.0)
        critical_threshold = max(context.voxel_size * 1200.0, 300.0)

        warnings: list[str] = []
        recommendations: list[str] = []
        severity = AnalysisSeverity.INFO
        score_impact = 0
        summary = "Bounding box looks normal."

        if distant_splats > 0:
            warnings.append(f"{_format_int(distant_splats)} distant splats detected.")
            recommendations.append("Preview extreme outliers before cleanup.")
            severity = AnalysisSeverity.WARNING
            score_impact = max(score_impact, 8)
            summary = "Bounding box includes distant outliers."

        if max_span >= critical_threshold:
            warnings.append(
                f"Bounding box span {_format_float(max_span)} exceeds the critical threshold."
            )
            recommendations.append("Bounding box unusually large.")
            severity = AnalysisSeverity.CRITICAL
            score_impact = max(score_impact, 22)
            summary = "Bounding box is unusually large."
        elif max_span >= warning_threshold:
            warnings.append(
                f"Bounding box span {_format_float(max_span)} exceeds the preview threshold."
            )
            recommendations.append("Bounding box unusually large.")
            if severity is AnalysisSeverity.INFO:
                severity = AnalysisSeverity.WARNING
                score_impact = max(score_impact, 10)
                summary = "Bounding box is larger than expected."

        return AnalysisResult(
            name=self.name,
            severity=severity,
            summary=summary,
            details={
                "distant_splats": distant_splats,
                "abnormal_scene_size": severity is not AnalysisSeverity.INFO and max_span >= warning_threshold,
                "bounds": bounds,
                "span": {
                    "x": round(span_x, 6),
                    "y": round(span_y, 6),
                    "z": round(span_z, 6),
                    "max": round(max_span, 6),
                },
            },
            warnings=warnings,
            recommendations=_unique_strings(recommendations),
            score_impact=score_impact,
        )


class DensityAnalysis(SceneAnalysisModule):
    name = "density"

    def analyze(self, context: SceneAnalysisContext) -> AnalysisResult:
        if context.aborted:
            return _skipped_result(self.name)

        voxel_counts = _build_voxel_counts(context.positions, context.voxel_size)
        occupied_voxels = len(voxel_counts)
        histogram = _density_histogram(voxel_counts.values())
        sparse_regions = _count_sparse_regions(voxel_counts)
        mean_density = _safe_ratio(context.analyzed_splats, occupied_voxels)
        singletons = int(histogram.get("1", 0))
        singleton_ratio = _safe_ratio(singletons, occupied_voxels)

        warnings: list[str] = []
        recommendations: list[str] = []
        severity = AnalysisSeverity.INFO
        score_impact = 0
        summary = "Density distribution looks healthy."

        if mean_density < 1.2 or singleton_ratio > 0.70:
            severity = AnalysisSeverity.CRITICAL
            score_impact = 18
            warnings.append("Scene appears extremely sparse.")
            recommendations.append("Scene appears sparse.")
            summary = "Density is critically sparse."
        elif mean_density < 1.8 or sparse_regions >= 8 or singleton_ratio > 0.45:
            severity = AnalysisSeverity.WARNING
            score_impact = 10
            warnings.append("Scene contains sparse voxel regions.")
            recommendations.append("Scene appears sparse.")
            summary = "Density is lower than expected."
        else:
            recommendations.append("Density looks healthy.")

        return AnalysisResult(
            name=self.name,
            severity=severity,
            summary=summary,
            details={
                "occupied_voxels": occupied_voxels,
                "density_histogram": histogram,
                "sparse_regions": sparse_regions,
                "estimated_sparse_splats": singletons,
                "mean_splats_per_voxel": round(mean_density, 6),
            },
            warnings=warnings,
            recommendations=_unique_strings(recommendations),
            score_impact=score_impact,
        )


@dataclass(slots=True)
class SceneAnalysisEngine:
    analyses: tuple[SceneAnalysisModule, ...] = (
        StatisticsAnalysis(),
        VoxelConnectivityAnalysis(),
        BoundingBoxAnalysis(),
        DensityAnalysis(),
    )

    def analyze(self, context: SceneAnalysisContext) -> SceneAnalysisReport:
        started_at = perf_counter()
        results: list[AnalysisResult] = []
        for analysis in self.analyses:
            logger.info("Scene analysis: before %s", _analysis_log_label(analysis.name))
            results.append(analysis.analyze(context))
        warnings = _unique_strings(
            warning
            for result in results
            for warning in result.warnings
        )
        recommendations = _unique_strings(
            recommendation
            for result in results
            for recommendation in result.recommendations
        )
        if not warnings:
            recommendations = _unique_strings(["Scene is healthy."] + recommendations)
        quality_score = max(0, min(100, 100 - sum(result.score_impact for result in results)))
        return SceneAnalysisReport(
            scene_stats={
                "scene_name": context.scene_name,
                "project_path": context.project_path,
                "total_splats": context.total_splats,
                "analyzed_splats": context.analyzed_splats,
                "selected_splats": context.selected_splats,
                "deleted_splats": context.deleted_splats,
                "voxel_size": context.voxel_size,
                "min_voxel_cluster_size": context.min_voxel_cluster_size,
                "approximate": context.approximate,
                "sampling_stride": context.sampling_stride,
                "used_native_sampling": context.used_native_sampling,
                "max_splats": context.max_splats,
                "aborted": context.aborted,
            },
            quality_score=quality_score,
            warnings=warnings,
            recommendations=recommendations,
            analysis_time=perf_counter() - started_at,
            results=results,
        )


def build_default_scene_analysis_engine() -> SceneAnalysisEngine:
    return SceneAnalysisEngine()


def format_scene_analysis_report(report: SceneAnalysisReport) -> str:
    scene_stats = report.scene_stats
    lines = [
        "Scene Analysis",
        f"Quality score: {report.quality_score}",
        f"Total splats: {_format_int(int(scene_stats['total_splats']))}",
        f"Analyzed splats: {_format_int(int(scene_stats['analyzed_splats']))}",
    ]
    if bool(scene_stats.get("approximate")):
        lines.append(
            "Mode: approximate sampled preview "
            f"(stride {scene_stats['sampling_stride']}, budget {_format_int(int(scene_stats['max_splats']))})"
        )
    elif bool(scene_stats.get("aborted")):
        lines.append(
            "Mode: aborted by execution budget "
            f"(budget {_format_int(int(scene_stats['max_splats']))})"
        )
    else:
        lines.append("Mode: exact preview")

    connectivity = _result_by_name(report.results, "voxel_connectivity")
    density = _result_by_name(report.results, "density")
    bounds = _result_by_name(report.results, "bounding_box")

    if connectivity is not None:
        lines.append(
            "Floating islands: "
            f"{_format_int(int(connectivity.details.get('floating_voxel_groups', 0)))}"
        )
        lines.append(
            "Estimated floating splats: "
            f"{_format_int(int(connectivity.details.get('estimated_floating_splats', 0)))}"
        )

    if bounds is not None:
        lines.append(
            "Bounding box: "
            + ("OK" if bounds.severity is AnalysisSeverity.INFO else bounds.summary)
        )

    if density is not None:
        lines.append(
            "Density: "
            + ("OK" if density.severity is AnalysisSeverity.INFO else density.summary)
        )

    if report.warnings:
        lines.append("")
        lines.append("Warnings")
        lines.extend(f"! {warning}" for warning in report.warnings)

    lines.append("")
    lines.append("Recommendations")
    for recommendation in report.recommendations:
        prefix = "OK:" if recommendation == "Scene is healthy." else "-"
        lines.append(f"{prefix} {recommendation}")
    return "\n".join(lines)


def build_cleanup_candidate_summary(
    report: SceneAnalysisReport,
) -> CleanupCandidateSummary:
    scene_stats = report.scene_stats
    connectivity = _result_by_name(report.results, "voxel_connectivity")
    density = _result_by_name(report.results, "density")

    floating_voxel_groups = int(
        0 if connectivity is None else connectivity.details.get("floating_voxel_groups", 0)
    )
    estimated_floating_splats = int(
        0 if connectivity is None else connectivity.details.get("estimated_floating_splats", 0)
    )
    small_voxel_clusters = int(
        0 if connectivity is None else connectivity.details.get("small_voxel_clusters", 0)
    )
    estimated_small_cluster_splats = int(
        0 if connectivity is None else connectivity.details.get("estimated_small_cluster_splats", 0)
    )
    sparse_regions = int(0 if density is None else density.details.get("sparse_regions", 0))
    estimated_sparse_splats = int(
        0 if density is None else density.details.get("estimated_sparse_splats", 0)
    )

    notes = ["Preview report only."]
    if bool(scene_stats.get("approximate")):
        notes.append("Approximate sampled preview.")
    if small_voxel_clusters > 0 and estimated_small_cluster_splats > 0:
        notes.append(
            "Small voxel cluster estimates may overlap with floating island estimates."
        )
    if estimated_sparse_splats > 0:
        notes.append("Sparse-region estimates are based on singleton voxels.")

    candidate_group_count = floating_voxel_groups + small_voxel_clusters + sparse_regions
    estimated_affected_splats = estimated_floating_splats + estimated_sparse_splats
    recommendations = list(report.recommendations)
    if candidate_group_count == 0 and "No cleanup required." not in recommendations:
        recommendations.append("No cleanup required.")

    return CleanupCandidateSummary(
        scene_name=str(scene_stats["scene_name"]),
        project_path=str(scene_stats["project_path"]),
        total_splats=int(scene_stats["total_splats"]),
        quality_score=report.quality_score,
        analysis_time=report.analysis_time,
        approximate=bool(scene_stats.get("approximate")),
        report_only=True,
        candidate_group_count=candidate_group_count,
        estimated_affected_splats=estimated_affected_splats,
        floating_voxel_groups=floating_voxel_groups,
        estimated_floating_splats=estimated_floating_splats,
        small_voxel_clusters=small_voxel_clusters,
        estimated_small_cluster_splats=estimated_small_cluster_splats,
        sparse_regions=sparse_regions,
        estimated_sparse_splats=estimated_sparse_splats,
        warnings=list(report.warnings),
        recommendations=_unique_strings(recommendations),
        notes=notes,
    )


def format_cleanup_candidate_summary(summary: CleanupCandidateSummary) -> str:
    lines = [
        "Cleanup Candidate Preview",
        f"Quality score context: {summary.quality_score}",
        f"Candidate groups: {_format_int(summary.candidate_group_count)}",
        f"Estimated affected splats: {_format_int(summary.estimated_affected_splats)}",
        f"Floating voxel groups: {_format_int(summary.floating_voxel_groups)}",
        f"Estimated floating splats: {_format_int(summary.estimated_floating_splats)}",
        f"Small voxel clusters: {_format_int(summary.small_voxel_clusters)}",
        f"Sparse regions: {_format_int(summary.sparse_regions)}",
        "Selection preview: report only",
    ]
    if summary.approximate:
        lines.append("Mode: approximate sampled preview")
    else:
        lines.append("Mode: exact preview")

    if summary.notes:
        lines.append("")
        lines.append("Notes")
        lines.extend(f"- {note}" for note in summary.notes)

    if summary.warnings:
        lines.append("")
        lines.append("Warnings")
        lines.extend(f"! {warning}" for warning in summary.warnings)

    lines.append("")
    lines.append("Suggested actions")
    for recommendation in summary.recommendations:
        lines.append(f"- {recommendation}")
    return "\n".join(lines)


def _skipped_result(name: str) -> AnalysisResult:
    return AnalysisResult(
        name=name,
        severity=AnalysisSeverity.WARNING,
        summary="Skipped because the execution budget refused sampled analysis.",
        details={"skipped": True},
        warnings=["Analysis skipped because the execution budget was exceeded."],
        recommendations=["Increase the analysis budget or allow sampled preview mode."],
        score_impact=14,
    )


def _result_by_name(results: list[AnalysisResult], name: str) -> AnalysisResult | None:
    for result in results:
        if result.name == name:
            return result
    return None


def _analysis_log_label(name: str) -> str:
    if name == "statistics":
        return "statistics analysis"
    if name == "voxel_connectivity":
        return "voxel analysis"
    if name == "bounding_box":
        return "bounding box analysis"
    if name == "density":
        return "density analysis"
    return f"{name} analysis"


def _serialize_value(value: object) -> object:
    if isinstance(value, AnalysisSeverity):
        return value.value
    if isinstance(value, BoundingBox):
        return asdict(value)
    if isinstance(value, Position3D):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value


def _build_bounds(positions: list[tuple[float, float, float]]) -> BoundingBox:
    if not positions:
        origin = Position3D(x=0.0, y=0.0, z=0.0)
        return BoundingBox(min=origin, max=origin)
    xs = [position[0] for position in positions]
    ys = [position[1] for position in positions]
    zs = [position[2] for position in positions]
    return BoundingBox(
        min=Position3D(x=min(xs), y=min(ys), z=min(zs)),
        max=Position3D(x=max(xs), y=max(ys), z=max(zs)),
    )


def _build_voxel_counts(
    positions: list[tuple[float, float, float]],
    voxel_size: float,
) -> dict[tuple[int, int, int], int]:
    counts: dict[tuple[int, int, int], int] = {}
    for x, y, z in positions:
        key = (
            math.floor(x / voxel_size),
            math.floor(y / voxel_size),
            math.floor(z / voxel_size),
        )
        counts[key] = counts.get(key, 0) + 1
    return counts


def _density_histogram(counts: object) -> dict[str, int]:
    histogram = Counter({"1": 0, "2-4": 0, "5-9": 0, "10-24": 0, "25+": 0})
    for count in counts:
        if count <= 1:
            histogram["1"] += 1
        elif count <= 4:
            histogram["2-4"] += 1
        elif count <= 9:
            histogram["5-9"] += 1
        elif count <= 24:
            histogram["10-24"] += 1
        else:
            histogram["25+"] += 1
    return dict(histogram)


def _count_sparse_regions(voxel_counts: dict[tuple[int, int, int], int]) -> int:
    sparse_keys = {key for key, count in voxel_counts.items() if count <= 1}
    if not sparse_keys:
        return 0

    visited: set[tuple[int, int, int]] = set()
    region_count = 0
    for start_key in sparse_keys:
        if start_key in visited:
            continue
        region_count += 1
        queue: deque[tuple[int, int, int]] = deque([start_key])
        visited.add(start_key)
        while queue:
            current = queue.popleft()
            for neighbor in _neighbor_keys(current):
                if neighbor not in sparse_keys or neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
    return region_count


def _neighbor_keys(key: tuple[int, int, int]) -> tuple[tuple[int, int, int], ...]:
    x, y, z = key
    return (
        (x - 1, y, z),
        (x + 1, y, z),
        (x, y - 1, z),
        (x, y + 1, z),
        (x, y, z - 1),
        (x, y, z + 1),
    )


def _count_distant_splats(
    positions: list[tuple[float, float, float]],
    voxel_size: float,
) -> int:
    if len(positions) < 5:
        return 0
    xs = sorted(position[0] for position in positions)
    ys = sorted(position[1] for position in positions)
    zs = sorted(position[2] for position in positions)
    bounds = []
    for values in (xs, ys, zs):
        low = _percentile(values, 0.05)
        high = _percentile(values, 0.95)
        robust_span = max(high - low, voxel_size * 4.0, 1.0)
        margin = robust_span * 2.5
        bounds.append((low - margin, high + margin))

    distant = 0
    for x, y, z in positions:
        if (
            x < bounds[0][0]
            or x > bounds[0][1]
            or y < bounds[1][0]
            or y > bounds[1][1]
            or z < bounds[2][0]
            or z > bounds[2][1]
        ):
            distant += 1
    return distant


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    index = max(0, min(len(values) - 1, int(round((len(values) - 1) * ratio))))
    return values[index]


def _format_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _format_float(value: float) -> str:
    return f"{value:.2f}"


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _unique_strings(values) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


__all__ = [
    "AnalysisResult",
    "AnalysisSeverity",
    "BoundingBoxAnalysis",
    "CleanupCandidateSummary",
    "DensityAnalysis",
    "SceneAnalysisContext",
    "SceneAnalysisEngine",
    "SceneAnalysisModule",
    "SceneAnalysisReport",
    "StatisticsAnalysis",
    "VoxelConnectivityAnalysis",
    "build_cleanup_candidate_summary",
    "build_default_scene_analysis_engine",
    "format_cleanup_candidate_summary",
    "format_scene_analysis_report",
]
