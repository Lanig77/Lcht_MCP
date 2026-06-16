"""Scene-level helpers for the LichtFeld plugin adapter."""

from __future__ import annotations

from pathlib import Path

from lichtfeld_mcp.schemas.common import SceneStats

from .gaussian import build_bounds, get_opacity_mean, get_sh_degree, get_splat_count


def get_scene_path(scene: object) -> str:
    for attribute_name in ("path", "project_path", "file_path"):
        value = getattr(scene, attribute_name, None)
        if value:
            return str(value)
    return "<active_lichtfeld_scene>"


def get_scene_name(scene: object, project_path: str) -> str:
    for attribute_name in ("name", "project_name", "title"):
        value = getattr(scene, attribute_name, None)
        if value:
            return str(value)
    return Path(project_path).stem or "active_lichtfeld_scene"


def build_scene_stats(
    scene: object,
    model: object,
    position_rows: list[tuple[float, float, float]],
    *,
    selected_count: int,
) -> SceneStats:
    splat_count = get_splat_count(position_rows)
    project_path = get_scene_path(scene)
    project_name = get_scene_name(scene, project_path)
    sh_degree = get_sh_degree(model, scene)
    return SceneStats(
        project_name=project_name,
        project_path=project_path,
        splat_count=splat_count,
        selected_count=selected_count,
        file_size_mb=0.0,
        estimated_vram_mb=round(splat_count * (32 + sh_degree * 12) / 1_000_000, 2),
        bounds=build_bounds(position_rows),
        sh_degree=sh_degree,
        opacity_mean=get_opacity_mean(model),
        density_score=0.0,
        history_length=0,
    )


def notify_scene_changed(scene: object) -> None:
    notify_changed = getattr(scene, "notify_changed", None)
    if callable(notify_changed):
        notify_changed()
