"""LichtFeld Studio plugin adapter skeleton.

This module intentionally avoids importing ``lichtfeld`` at module import time so the
normal test suite can run without LichtFeld Studio installed.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from lichtfeld_mcp.adapters.base import LichtfeldAdapter as AdapterContract
from lichtfeld_mcp.core.requests import HeightRange
from lichtfeld_mcp.core.validation import normalize_scene_path
from lichtfeld_mcp.errors import AdapterUnavailableError
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
)


class LichtfeldPluginAdapter(AdapterContract):
    """Skeleton adapter for the LichtFeld Studio Python plugin API."""

    def open_project(self, path: str) -> ProjectInfo:
        normalized_path = normalize_scene_path(path, label="project path")
        self._load_lichtfeld()
        self._not_implemented(
            "open_project",
            normalized_path=normalized_path,
        )

    def save_project(self) -> ToolResult:
        self._load_lichtfeld()
        self._not_implemented("save_project")

    def close_project(self) -> ToolResult:
        self._load_lichtfeld()
        self._not_implemented("close_project")

    def get_stats(self) -> SceneStats:
        lichtfeld_module = self._load_lichtfeld()
        scene = self._require_active_scene(lichtfeld_module)
        model = self._require_combined_model(scene)
        means_rows = self._extract_position_rows(model)
        splat_count = len(means_rows)
        bounds = self._build_bounds(means_rows)
        project_path = self._get_scene_path(scene)
        project_name = self._get_scene_name(scene, project_path)
        sh_degree = self._get_sh_degree(model, scene)
        opacity_mean = self._get_opacity_mean(model)

        return SceneStats(
            project_name=project_name,
            project_path=project_path,
            splat_count=splat_count,
            selected_count=0,
            file_size_mb=0.0,
            estimated_vram_mb=round(splat_count * (32 + sh_degree * 12) / 1_000_000, 2),
            bounds=bounds,
            sh_degree=sh_degree,
            opacity_mean=opacity_mean,
            density_score=0.0,
            history_length=0,
        )

    def get_scene_stats(self) -> SceneStats:
        return self.get_stats()

    def select_by_box(self, box: Box3D, mode: str = "replace") -> SelectionResult:
        self._load_lichtfeld()
        self._not_implemented("select_by_box", box=box, mode=mode)

    def select_by_height(
        self,
        z_min: float | None,
        z_max: float | None,
        mode: str = "replace",
    ) -> SelectionResult:
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        self._load_lichtfeld()
        # Future LichtFeld mapping:
        # - scene.combined_model()
        # - model.get_means()
        # - build a boolean height mask from the means tensor
        # - scene.set_selection_mask(mask)
        # - scene.notify_changed()
        self._not_implemented(
            "select_by_height",
            z_min=height_range.z_min,
            z_max=height_range.z_max,
            mode=mode,
        )

    def select_by_color(
        self,
        r: int,
        g: int,
        b: int,
        tolerance: int = 20,
        mode: str = "replace",
    ) -> SelectionResult:
        self._load_lichtfeld()
        self._not_implemented(
            "select_by_color",
            r=r,
            g=g,
            b=b,
            tolerance=tolerance,
            mode=mode,
        )

    def delete_selection(self) -> ToolResult:
        self._load_lichtfeld()
        # Future LichtFeld mapping:
        # - scene.combined_model()
        # - model.soft_delete(mask)
        # - model.apply_deleted()
        # - scene.notify_changed()
        self._not_implemented("delete_selection")

    def crop_by_box(self, box: Box3D, keep_inside: bool = True) -> ToolResult:
        self._load_lichtfeld()
        self._not_implemented("crop_by_box", box=box, keep_inside=keep_inside)

    def crop_by_height(
        self,
        z_min: float | None,
        z_max: float | None,
        keep_inside: bool = True,
    ) -> ToolResult:
        height_range = HeightRange(z_min=z_min, z_max=z_max)
        self._load_lichtfeld()
        self._not_implemented(
            "crop_by_height",
            z_min=height_range.z_min,
            z_max=height_range.z_max,
            keep_inside=keep_inside,
        )

    def optimize_for_target(self, target: str, max_splats: int | None = None) -> OptimizationResult:
        self._load_lichtfeld()
        self._not_implemented("optimize_for_target", target=target, max_splats=max_splats)

    def export_scene(self, output_path: str, fmt: str, target: str | None = None) -> ExportResult:
        self._load_lichtfeld()
        self._not_implemented("export_scene", output_path=output_path, fmt=fmt, target=target)

    def measure_distance(self, a: Vec3, b: Vec3, unit: str = "m") -> MeasurementResult:
        self._load_lichtfeld()
        self._not_implemented("measure_distance", a=a, b=b, unit=unit)

    def undo(self) -> ToolResult:
        self._load_lichtfeld()
        # Future LichtFeld mapping:
        # - scene.combined_model()
        # - model.undelete(mask)
        # - scene.notify_changed()
        self._not_implemented("undo")

    def list_history(self) -> list[HistoryEntry]:
        self._load_lichtfeld()
        self._not_implemented("list_history")

    @staticmethod
    def _load_lichtfeld() -> object:
        try:
            return importlib.import_module("lichtfeld")
        except ModuleNotFoundError as exc:
            if exc.name not in {None, "lichtfeld"}:
                raise
            raise AdapterUnavailableError(
                "LichtFeld Studio Python plugin API is not available. "
                "Install or launch LichtFeld Studio with Python plugin support."
            ) from exc
        except ImportError as exc:
            raise AdapterUnavailableError(
                "LichtFeld Studio Python plugin API could not be imported: "
                f"{exc}."
            ) from exc

    @staticmethod
    def _require_active_scene(lichtfeld_module: object) -> object:
        for attribute_name in (
            "scene",
            "current_scene",
            "active_scene",
            "get_scene",
            "get_current_scene",
            "get_active_scene",
        ):
            candidate = getattr(lichtfeld_module, attribute_name, None)
            if callable(candidate):
                candidate = candidate()
            if candidate is not None:
                return candidate
        raise AdapterUnavailableError(
            "No active LichtFeld scene is available from the Python plugin API."
        )

    @staticmethod
    def _require_combined_model(scene: object) -> object:
        combined_model = getattr(scene, "combined_model", None)
        if callable(combined_model):
            combined_model = combined_model()
        if combined_model is None:
            raise AdapterUnavailableError(
                "No active LichtFeld combined model is available for statistics."
            )
        return combined_model

    @classmethod
    def _extract_position_rows(cls, model: object) -> list[tuple[float, float, float]]:
        means = None
        get_means = getattr(model, "get_means", None)
        if callable(get_means):
            means = get_means()
        elif hasattr(model, "means_raw"):
            means = getattr(model, "means_raw")
        if means is None:
            raise AdapterUnavailableError(
                "Active LichtFeld combined model does not expose gaussian positions."
            )
        return cls._coerce_position_rows(means)

    @classmethod
    def _coerce_position_rows(cls, values: object) -> list[tuple[float, float, float]]:
        materialized = cls._materialize_array(values)
        if materialized is None:
            return []
        if isinstance(materialized, (list, tuple)):
            items = list(materialized)
        else:
            try:
                items = list(materialized)
            except TypeError as exc:
                raise AdapterUnavailableError(
                    "LichtFeld gaussian positions are not iterable."
                ) from exc
        if not items:
            return []
        if cls._is_scalar(items[0]):
            if len(items) < 3:
                raise AdapterUnavailableError(
                    "LichtFeld gaussian position rows must expose at least three coordinates."
                )
            return [cls._coerce_position_row(items)]
        return [cls._coerce_position_row(item) for item in items]

    @classmethod
    def _coerce_position_row(cls, row: object) -> tuple[float, float, float]:
        materialized = cls._materialize_array(row)
        if isinstance(materialized, (list, tuple)):
            items = list(materialized)
        else:
            try:
                items = list(materialized)
            except TypeError as exc:
                raise AdapterUnavailableError(
                    "LichtFeld gaussian position rows are not iterable."
                ) from exc
        if len(items) < 3:
            raise AdapterUnavailableError(
                "LichtFeld gaussian position rows must expose at least three coordinates."
            )
        return (float(items[0]), float(items[1]), float(items[2]))

    @classmethod
    def _materialize_array(cls, value: object) -> object:
        current = value
        for method_name in ("detach", "cpu"):
            method = getattr(current, method_name, None)
            if callable(method):
                current = method()
        numpy_method = getattr(current, "numpy", None)
        if callable(numpy_method):
            current = numpy_method()
        tolist_method = getattr(current, "tolist", None)
        if callable(tolist_method):
            current = tolist_method()
        return current

    @staticmethod
    def _is_scalar(value: object) -> bool:
        return isinstance(value, (int, float))

    @staticmethod
    def _build_bounds(rows: list[tuple[float, float, float]]) -> Box3D:
        if not rows:
            origin = Vec3(x=0.0, y=0.0, z=0.0)
            return Box3D(min=origin, max=origin)
        xs = [row[0] for row in rows]
        ys = [row[1] for row in rows]
        zs = [row[2] for row in rows]
        return Box3D(
            min=Vec3(x=min(xs), y=min(ys), z=min(zs)),
            max=Vec3(x=max(xs), y=max(ys), z=max(zs)),
        )

    @staticmethod
    def _get_scene_path(scene: object) -> str:
        for attribute_name in ("path", "project_path", "file_path"):
            value = getattr(scene, attribute_name, None)
            if value:
                return str(value)
        return "<active_lichtfeld_scene>"

    @staticmethod
    def _get_scene_name(scene: object, project_path: str) -> str:
        for attribute_name in ("name", "project_name", "title"):
            value = getattr(scene, attribute_name, None)
            if value:
                return str(value)
        return Path(project_path).stem or "active_lichtfeld_scene"

    @classmethod
    def _get_opacity_mean(cls, model: object) -> float:
        get_opacity = getattr(model, "get_opacity", None)
        if not callable(get_opacity):
            return 0.0
        values = cls._flatten_scalars(get_opacity())
        if not values:
            return 0.0
        return round(sum(values) / len(values), 6)

    @staticmethod
    def _get_sh_degree(model: object, scene: object) -> int:
        for owner in (model, scene):
            for attribute_name in ("sh_degree", "active_sh_degree"):
                value = getattr(owner, attribute_name, None)
                if isinstance(value, int):
                    return value
        return 0

    @classmethod
    def _flatten_scalars(cls, value: object) -> list[float]:
        materialized = cls._materialize_array(value)
        if materialized is None:
            return []
        if cls._is_scalar(materialized):
            return [float(materialized)]
        if isinstance(materialized, (list, tuple)):
            items = list(materialized)
        else:
            try:
                items = list(materialized)
            except TypeError:
                return []
        flattened: list[float] = []
        for item in items:
            if cls._is_scalar(item):
                flattened.append(float(item))
            else:
                flattened.extend(cls._flatten_scalars(item))
        return flattened

    @staticmethod
    def _not_implemented(method_name: str, **_: object) -> None:
        raise NotImplementedError(
            f"LichtFeld plugin adapter skeleton does not implement '{method_name}' yet."
        )


LichtfeldAdapter = LichtfeldPluginAdapter

__all__ = ["LichtfeldAdapter", "LichtfeldPluginAdapter"]
