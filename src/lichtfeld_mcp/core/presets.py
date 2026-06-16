"""Shared scene presets and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass

from lichtfeld_mcp.errors import UnsupportedTargetError


@dataclass(frozen=True)
class OptimizationProfile:
    """Optimization preset applied to a scene target."""

    max_splats: int | None
    sh_degree: int
    rules: tuple[str, ...]


OPTIMIZATION_PROFILES: dict[str, OptimizationProfile] = {
    "quest3": OptimizationProfile(
        max_splats=2_000_000,
        sh_degree=2,
        rules=("cap_splats", "sh_degree_2", "enable_lod"),
    ),
    "web": OptimizationProfile(
        max_splats=1_500_000,
        sh_degree=2,
        rules=("cap_splats", "quantize", "enable_lod"),
    ),
    "mobile": OptimizationProfile(
        max_splats=900_000,
        sh_degree=1,
        rules=("aggressive_decimation", "quantize"),
    ),
    "unreal": OptimizationProfile(
        max_splats=5_000_000,
        sh_degree=3,
        rules=("preserve_quality", "generate_metadata"),
    ),
    "unity": OptimizationProfile(
        max_splats=3_000_000,
        sh_degree=2,
        rules=("balance_quality", "generate_metadata"),
    ),
    "archive": OptimizationProfile(
        max_splats=None,
        sh_degree=3,
        rules=("preserve_quality", "write_manifest"),
    ),
}

SUPPORTED_EXPORT_FORMATS = frozenset({"ply", "spz", "splat", "json"})


def normalize_target(target: str) -> str:
    """Normalize and validate an optimization target."""

    normalized = target.lower().strip()
    if normalized not in OPTIMIZATION_PROFILES:
        raise UnsupportedTargetError(
            f"Unsupported target '{target}'. Supported: {sorted(OPTIMIZATION_PROFILES)}"
        )
    return normalized


def get_optimization_profile(target: str) -> OptimizationProfile:
    """Return a validated optimization profile."""

    return OPTIMIZATION_PROFILES[normalize_target(target)]


def normalize_export_format(fmt: str) -> str:
    """Normalize and validate an export format."""

    normalized = fmt.lower().lstrip(".").strip()
    if normalized not in SUPPORTED_EXPORT_FORMATS:
        raise UnsupportedTargetError(
            f"Unsupported export format '{fmt}'. Supported: {sorted(SUPPORTED_EXPORT_FORMATS)}"
        )
    return normalized
