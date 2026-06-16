# Lichtfeld API contract proposal

The MCP server expects a minimal editor API. Lichtfeld Studio could expose it as Python, C++, CLI, local HTTP, or socket API.

## Required capabilities

```python
open_project(path: str) -> ProjectInfo
save_project() -> ToolResult
close_project() -> ToolResult
get_scene_stats() -> SceneStats
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

The LLM must never edit splats directly. It calls typed tools; Lichtfeld remains the authority for geometry, rendering, optimization, file I/O, and history.
