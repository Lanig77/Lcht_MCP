# Lichtfeld API contract proposal

The adapter layer consumed by `core.SceneAPI` expects a minimal editor API. Lichtfeld Studio could expose it as Python, C++, CLI, local HTTP, or socket API.

## Required capabilities

```python
open_project(path: str) -> ProjectInfo
save_project() -> ToolResult
close_project() -> ToolResult
get_scene_stats() -> SceneStats
analyze_scene(
    voxel_size: float,
    min_voxel_cluster_size: int,
    max_splats: int,
    abort_if_above_limit: bool,
) -> SceneAnalysisReport
preview_cleanup_candidates(
    voxel_size: float,
    min_voxel_cluster_size: int,
    max_splats: int,
    abort_if_above_limit: bool,
) -> CleanupCandidateSummary
open_cleanup_workspace(
    voxel_size: float,
    min_voxel_cluster_size: int,
    cluster_distance_threshold: float,
    outlier_distance: float,
    cleanup_aggressiveness: float,
) -> CleanupWorkspace
update_cleanup_workspace(
    voxel_size: float,
    min_voxel_cluster_size: int,
    cluster_distance_threshold: float,
    outlier_distance: float,
    cleanup_aggressiveness: float,
) -> CleanupWorkspace
get_cleanup_workspace() -> CleanupWorkspace | None
compare_cleanup_presets() -> CleanupPresetComparisonReport
set_active_cleanup_categories(
    categories: tuple[str, ...] | list[str],
    selected_category: str | None = None,
) -> CleanupWorkspace
preview_cleanup_category(category: str) -> CleanupWorkspace
preview_active_cleanup_categories() -> CleanupWorkspace
clear_cleanup_category_preview() -> ToolResult
soft_delete_cleanup_workspace_selection(
    max_deletable_splats: int | None,
    max_deletable_percentage: float | None,
) -> CleanupSoftDeleteResult
restore_last_delete() -> ToolResult
apply_cleanup_workspace_deleted() -> CleanupApplyDeletedResult
select_by_box(box: Box3D, mode: str) -> SelectionResult
select_by_height(z_min: float | None, z_max: float | None, mode: str) -> SelectionResult
select_by_color(r: int, g: int, b: int, tolerance: int, mode: str) -> SelectionResult
delete_selection() -> ToolResult
crop_by_box(box: Box3D, keep_inside: bool) -> ToolResult
crop_by_height(z_min: float | None, z_max: float | None, keep_inside: bool) -> ToolResult
optimize_for_target(target: str, max_splats: int | None) -> OptimizationResult
export_scene(output_path: str, fmt: str, target: str | None) -> ExportResult
measure_distance(a: Vec3, b: Vec3, unit: str) -> MeasurementResult
undo() -> ToolResult
list_history() -> list[HistoryEntry]
```

## Design principle

The LLM must never edit splats directly. It calls typed tools, the tools delegate to `core.SceneAPI`, and Lichtfeld remains the authority for geometry, rendering, optimization, file I/O, and history.

Cleanup category preview is explicitly non-destructive. The adapter may update
native selection state for:

- `FLOATING_VOXEL_CLUSTERS`
- `DISCONNECTED_CLUSTERS`
- `DISTANT_OUTLIERS`
- `SPARSE_SINGLETON_REGIONS`

but it must not soft-delete splats, apply deleted splats, or materialize the
full scene in Python just to show category visibility.
