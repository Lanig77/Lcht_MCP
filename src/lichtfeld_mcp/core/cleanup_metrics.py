from __future__ import annotations

from dataclasses import dataclass


CLEANUP_SOURCE_FLOATING = "floating voxel clusters"
CLEANUP_SOURCE_DISCONNECTED = "disconnected clusters"
CLEANUP_SOURCE_OUTLIER = "distant outliers"
CLEANUP_SOURCE_SPARSE = "sparse singleton regions"

_SOURCE_ORDER = (
    CLEANUP_SOURCE_FLOATING,
    CLEANUP_SOURCE_DISCONNECTED,
    CLEANUP_SOURCE_OUTLIER,
    CLEANUP_SOURCE_SPARSE,
)


@dataclass(frozen=True, slots=True)
class CleanupSourceBreakdownEntry:
    source: str
    selected_sample_count: int
    estimated_full_scene_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "selected_sample_count": self.selected_sample_count,
            "estimated_full_scene_count": self.estimated_full_scene_count,
        }


@dataclass(frozen=True, slots=True)
class CleanupIntensityMetrics:
    cleanup_intensity_score: float
    aggressiveness_contribution: float
    estimated_cleanup_contribution: float
    floating_cluster_contribution: float
    disconnected_cluster_contribution: float
    outlier_contribution: float
    sparse_region_contribution: float

    def to_dict(self) -> dict[str, object]:
        return {
            "cleanup_intensity_score": round(self.cleanup_intensity_score, 6),
            "aggressiveness_contribution": round(self.aggressiveness_contribution, 6),
            "estimated_cleanup_contribution": round(
                self.estimated_cleanup_contribution,
                6,
            ),
            "floating_cluster_contribution": round(
                self.floating_cluster_contribution,
                6,
            ),
            "disconnected_cluster_contribution": round(
                self.disconnected_cluster_contribution,
                6,
            ),
            "outlier_contribution": round(self.outlier_contribution, 6),
            "sparse_region_contribution": round(
                self.sparse_region_contribution,
                6,
            ),
        }


def cleanup_source_order() -> tuple[str, ...]:
    return _SOURCE_ORDER


def extrapolate_cleanup_count(
    sample_count: int,
    *,
    analyzed_splats: int,
    total_splats: int,
    approximate: bool,
) -> int:
    normalized_count = max(0, int(sample_count))
    if approximate and analyzed_splats > 0 and total_splats > 0:
        return max(
            0,
            int(round(normalized_count * (total_splats / analyzed_splats))),
        )
    return normalized_count


def build_cleanup_source_breakdown(
    *,
    source_sample_counts: dict[str, int],
    analyzed_splats: int,
    total_splats: int,
    approximate: bool,
) -> tuple[CleanupSourceBreakdownEntry, ...]:
    entries: list[CleanupSourceBreakdownEntry] = []
    for source in _SOURCE_ORDER:
        selected_sample_count = max(0, int(source_sample_counts.get(source, 0)))
        entries.append(
            CleanupSourceBreakdownEntry(
                source=source,
                selected_sample_count=selected_sample_count,
                estimated_full_scene_count=extrapolate_cleanup_count(
                    selected_sample_count,
                    analyzed_splats=analyzed_splats,
                    total_splats=total_splats,
                    approximate=approximate,
                ),
            )
        )
    return tuple(entries)


def compute_cleanup_intensity_metrics(
    *,
    cleanup_aggressiveness: float,
    estimated_cleanup_percentage: float,
    total_splats: int,
    source_breakdown: tuple[CleanupSourceBreakdownEntry, ...],
    floating_group_count: int,
    disconnected_group_count: int,
    sparse_region_count: int,
) -> CleanupIntensityMetrics:
    ratio_by_source = {
        entry.source: (
            0.0
            if total_splats <= 0
            else entry.estimated_full_scene_count / total_splats
        )
        for entry in source_breakdown
    }
    aggressiveness_contribution = round(
        max(0.0, min(1.0, cleanup_aggressiveness)) * 100.0,
        4,
    )
    estimated_cleanup_contribution = round(
        min(8.0, max(0.0, estimated_cleanup_percentage) * 180.0),
        4,
    )
    floating_cluster_contribution = round(
        min(
            4.0,
            max(0.0, ratio_by_source.get(CLEANUP_SOURCE_FLOATING, 0.0)) * 120.0
            + min(float(floating_group_count), 5.0) * 0.30,
        ),
        4,
    )
    disconnected_cluster_contribution = round(
        min(
            3.0,
            max(0.0, ratio_by_source.get(CLEANUP_SOURCE_DISCONNECTED, 0.0)) * 100.0
            + min(float(disconnected_group_count), 5.0) * 0.35,
        ),
        4,
    )
    outlier_ratio = max(0.0, ratio_by_source.get(CLEANUP_SOURCE_OUTLIER, 0.0))
    outlier_contribution = round(
        min(2.5, outlier_ratio * 140.0 + (0.5 if outlier_ratio > 0.0 else 0.0)),
        4,
    )
    sparse_region_contribution = round(
        min(
            2.5,
            max(0.0, ratio_by_source.get(CLEANUP_SOURCE_SPARSE, 0.0)) * 90.0
            + min(float(sparse_region_count), 4.0) * 0.25,
        ),
        4,
    )
    cleanup_intensity_score = round(
        aggressiveness_contribution
        + estimated_cleanup_contribution
        + floating_cluster_contribution
        + disconnected_cluster_contribution
        + outlier_contribution
        + sparse_region_contribution,
        4,
    )
    return CleanupIntensityMetrics(
        cleanup_intensity_score=cleanup_intensity_score,
        aggressiveness_contribution=aggressiveness_contribution,
        estimated_cleanup_contribution=estimated_cleanup_contribution,
        floating_cluster_contribution=floating_cluster_contribution,
        disconnected_cluster_contribution=disconnected_cluster_contribution,
        outlier_contribution=outlier_contribution,
        sparse_region_contribution=sparse_region_contribution,
    )
