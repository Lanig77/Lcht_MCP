# LichtFeld Plugin Adapter

## Purpose

`Lcht_MCP` now includes a real-backend adapter skeleton for the LichtFeld Studio
Python plugin API.

The goal of this adapter is not to replace the mock backend yet. It prepares the
integration seam for a real engine while keeping the repository testable on machines
where LichtFeld is not installed.

## Key rule

The adapter must not import `lichtfeld` at module import time.

That rule keeps these flows safe:

- importing `lichtfeld_mcp.adapters.lichtfeld`
- running unit tests on CI
- developing the MCP and domain layers without a local LichtFeld installation

The plugin package is imported lazily only inside adapter methods that need it.

## Current shape

The skeleton lives in:

- `src/lichtfeld_mcp/adapters/lichtfeld/`

It exposes a concrete plugin-oriented adapter class aligned to the current runtime
contract.

Some operations are already implemented against the active LichtFeld plugin scene:

- `get_stats()`
- `analyze_scene()`
- `preview_cleanup_candidates()`
- `preview_cleanup_selection()`
- `select_by_height()`
- `select_by_opacity()`
- `select_by_color()`
- `delete_selection()`

Other methods are still placeholders, including:

- `open_project`
- `save_project`
- `close_project`
- `undo`

The class also satisfies the broader adapter contract so it can later plug into
`SceneAPI` without changing MCP-facing code.

## Scene analysis and cleanup workflow

The adapter now supports a read-only analysis pipeline that feeds a native cleanup
preview workflow:

1. `analyze_scene()` samples or scans scene positions within a bounded execution budget
2. `open_cleanup_workspace()` creates a workspace session from the latest
   `SceneAnalysisReport`
3. `update_cleanup_workspace()` reuses the same sampled analysis inputs while
   rebuilding the candidate summary and native selection preview from updated
   cleanup parameters
4. `reset_cleanup_workspace()` clears the preview selection and invalidates the
   active workspace session
5. `preview_cleanup_candidates()` and `preview_cleanup_selection()` remain available
   as compatibility helpers over the same non-destructive cleanup logic
6. `soft_delete_cleanup_workspace_selection()` consumes the workspace-owned native
   preview mask for a reversible cleanup soft delete
7. `restore_last_delete()` reverses that workspace soft delete while it is still
   pending
8. `apply_cleanup_workspace_deleted()` is the only cleanup workspace operation that
   may call `model.apply_deleted()` to permanently finalize the workspace soft delete

This keeps analysis, preview, and destructive editing as separate stages.

### Native cleanup selection preview

`preview_cleanup_selection()` is a visualization and validation tool. It must never:

- delete splats
- soft delete splats
- hide splats
- call `apply_deleted()`

Instead it reuses the latest cached analysis and cleanup preview state, clears the
current native selection, rebuilds a new selection, and refreshes the viewport.

Selection sources currently include:

- floating voxel clusters
- disconnected clusters
- distant outliers
- sparse singleton regions

When the latest analysis is sampled, the preview is explicitly labeled as approximate.
The selected splats then represent sampled cleanup regions rather than an exact
full-scene selection.

### Cleanup workspace

The cleanup workspace is the new interactive layer between scene analysis and any
future delete flow.

The adapter now persists a `CleanupSession` object as the editing-session owner.

The session owns:

- the latest `SceneProfile`
- the latest `SceneAnalysisReport`
- the latest `CleanupCandidateSummary`
- the sampled `GaussianCloud` reused for parameter updates
- the current cleanup parameters
- the current native selection handle and preview mask state
- the current cleanup workspace lifecycle state (`active` or `soft_deleted`)
- the current selection statistics and update timings

The workspace rendered to the plugin UI is the session snapshot for the current
preview state.

The workspace snapshot stores:

- the latest `SceneAnalysisReport`
- the latest `CleanupCandidateSummary`
- the latest `SceneProfile`
- the current cleanup parameters

The workspace is invalidated when:

- another scene becomes active
- `analyze_scene()` is run again
- `apply_deleted()` finalizes a pending cleanup delete
- the user explicitly resets the workspace

Interactive parameters currently include:

- `voxel_size`
- `min_voxel_cluster_size`
- `cluster_distance_threshold`
- `outlier_distance`
- `cleanup_aggressiveness`

The adapter rebuilds the selection preview from cached sampled positions whenever
possible. The session also reuses the sampled `GaussianCloud` so parameter changes
do not rebuild the full scene analysis or the sampled cloud on every update.

Each update logs:

- `analysis_reused`
- `candidate_update_time`
- `selection_update_time`
- `total_workspace_update_time`

This keeps parameter iteration interactive on large scenes while preserving a
single source of truth for later soft delete, restore, and permanent apply flows.

### Cleanup category preview

The workspace now also stores category-isolated preview data for the current
sampled cleanup analysis:

- `FLOATING_VOXEL_CLUSTERS`
- `DISCONNECTED_CLUSTERS`
- `DISTANT_OUTLIERS`
- `SPARSE_SINGLETON_REGIONS`

Each category preview owns:

- sample-local indices for the current workspace sample
- native preview indices for the current approximate or exact selection path
- preview-selected counts
- estimated full-scene counts
- an optional score and reason string for UI/log display

The category preview path reuses the current `CleanupWorkspace` sample and does
not rerun full-scene analysis. When the workspace is stale because the scene
generation or splat count changed, the adapter refuses the preview and requires
the user to reopen the workspace.

The current visual path is deliberately limited to native selection updates.
Color-coded overlays remain future work until the native LichtFeld runtime
exposes a stable multi-color overlay API.

## Availability behavior

If LichtFeld is not installed or the plugin API cannot be imported, the adapter raises
`AdapterUnavailableError` with a clear message.

This is intentional. The repository should fail explicitly when the real backend is
requested, while still allowing the default mock-backed test suite to run normally.

## Planned mapping to the LichtFeld plugin API

The current adapter already uses parts of the intended plugin mapping and keeps the
rest documented with internal comments.

Planned mapping:

- `scene.combined_model()` to access the active Gaussian model
- `model.get_means()` to read positions and derive masks or statistics
- `scene.set_selection_mask(mask)` to push selection state into the UI/runtime
- `model.soft_delete(mask)` to mark selected gaussians as deleted
- `model.undelete(mask)` to restore deleted gaussians for undo-like flows
- `model.apply_deleted()` to commit pending deletions
- `scene.notify_changed()` to refresh the scene after mutations

## Implemented operations

### `get_stats()`

`get_stats()` lazily loads the LichtFeld plugin module, retrieves the active scene,
calls `scene.combined_model()`, and reads Gaussian positions from `model.get_means()`
or `model.means_raw`.

From those positions it currently derives:

- `splat_count`
- scene bounds (`Box3D`)
- `selected_count` when a selection mask is known
- `sh_degree` when available on the model or scene
- `opacity_mean` when `model.get_opacity()` is available

Tensor handling is defensive:

- torch-like tensors with `detach()`, `cpu()`, and `numpy()` are supported
- numpy-like arrays or plain Python lists are supported
- no hard dependency on `torch` or `numpy` is introduced at import time

### `select_by_height()`

`select_by_height()` uses the active scene/model and builds a boolean selection mask
from the Gaussian `z` positions.

It currently:

- normalizes inverted height ranges through the existing `HeightRange` request object
- reads positions from `get_means()` or `means_raw`
- creates a boolean mask for splats whose `z` coordinate is within the normalized range
- applies that mask with `scene.set_selection_mask(mask)`
- calls `scene.notify_changed()` when available

The adapter returns the existing `SelectionResult` contract so the MCP-facing layers
remain unchanged.

### `select_by_opacity()`

`select_by_opacity()` uses the active scene/model and builds a boolean selection mask
from Gaussian opacity values.

It currently:

- reads opacity values from `model.get_opacity()`
- falls back to `model.opacity` or `model.opacity_raw` when needed
- validates requested opacity bounds in the `0.0..1.0` range
- normalizes inverted opacity ranges when both bounds are provided
- creates a boolean mask for splats whose opacity is within the normalized range
- applies that mask with `scene.set_selection_mask(mask)`
- caches the mask and calls `scene.notify_changed()` when available

### `select_by_color()`

`select_by_color()` uses the active scene/model and builds a boolean selection mask
from per-splat color values.

It currently:

- reads colors from `model.get_colors()`
- falls back to `model.colors`, `model.colors_raw`, `model.rgb`, or `model.rgb_raw`
- validates the input RGB triplet in the `0..255` range
- validates `tolerance` in the `0..255` range
- compares each color channel independently against the requested RGB target
- applies that mask with `scene.set_selection_mask(mask)`
- caches the mask and calls `scene.notify_changed()` when available

Color handling is normalized before comparison:

- adapter input is always RGB `0..255`
- model colors expressed as floats `0.0..1.0` are scaled to `0..255`
- model colors already expressed as `0..255` are compared directly
- `tolerance` is applied per channel, not as Euclidean color distance

### `delete_selection()`

`delete_selection()` uses the current selection mask and applies a first real deletion
flow against the LichtFeld model.

It currently:

- prefers the latest cached selection mask created by selection operations
- falls back to a scene-provided selection mask when the API exposes one
- calls `model.soft_delete(mask)`
- calls `model.apply_deleted()` when available
- clears the adapter-side cached selection mask
- clears the scene selection mask when possible
- calls `scene.notify_changed()` when available

The method still returns the existing `ToolResult` contract for compatibility with the
rest of the application.

## Selection data sources

The currently implemented selection operations read different model data:

- `select_by_height()`: Gaussian means / `z` position from `get_means()` or `means_raw`
- `select_by_opacity()`: opacity from `get_opacity()`, `opacity`, or `opacity_raw`
- `select_by_color()`: colors from `get_colors()`, `colors`, `colors_raw`, `rgb`, or `rgb_raw`

## Active selection mask cache

The adapter keeps a lightweight in-memory cache of the latest known selection mask.

This cache exists for two reasons:

- it lets `delete_selection()` work immediately after `select_by_height()`,
`select_by_opacity()`, or `select_by_color()` even if the scene API does not expose a
readable selection mask
- it lets `get_stats()` report a meaningful `selected_count` when the current selection
is known by the adapter

The cache is cleared after `delete_selection()`.

## Mask lifecycle

The current selection flow follows the same lifecycle across implemented selectors:

1. read the relevant Gaussian attribute from the active model
2. build a boolean mask in Python
3. push that mask to the scene with `scene.set_selection_mask(mask)`
4. cache the active mask inside the adapter
5. call `scene.notify_changed()` when available
6. later, `delete_selection()` consumes the cached mask or a scene-provided current mask
7. after deletion, the adapter clears both the cache and the visible scene selection

The cleanup preview flow adds one more non-destructive branch:

1. `analyze_scene()` captures bounded scene analysis metadata
2. `open_cleanup_workspace()` caches a workspace session without mutating splats
3. `update_cleanup_workspace()` refreshes the native preview selection from the
   cached analysis sample and current parameters
4. `reset_cleanup_workspace()` clears the preview selection and closes the session
5. later edit workflows may choose to reuse that validated selection for soft delete

## No-selection behavior

When `delete_selection()` cannot find any active selection, it currently returns an
explicit non-success result:

- `ToolResult(ok=False, message="No active selection available to delete.")`

This keeps the behavior explicit without requiring a hard failure for a common editor
state.

## Expected future flow

```text
MCP tools
  -> SceneService
  -> SceneAPI
  -> LichtfeldPluginAdapter
  -> LichtFeld Studio Plugin API

Cleanup now follows the staged architecture below:

```text
Analyze Scene
  -> Open Cleanup Workspace
  -> Update Preview
  -> Soft Delete Cleanup Workspace Selection
  -> Restore Last Delete
  -> Apply Deleted Cleanup Permanently
```
```

## Current integration status

| operation | status | notes |
| --- | --- | --- |
| `get_stats()` | implemented | reads active scene/model, computes bounds and splat count defensively |
| `select_by_height()` | implemented | builds a boolean mask from Gaussian `z` positions |
| `select_by_opacity()` | implemented | reads opacity values and applies a replace-style mask |
| `select_by_color()` | implemented | supports RGB `0..255` input and float/int model colors |
| `delete_selection()` | implemented | uses `soft_delete(mask)` and `apply_deleted()` when available |
| `select_by_box()` | placeholder | not connected to LichtFeld yet |
| `crop_by_height()` | placeholder | not connected to LichtFeld yet |
| `undo()` | placeholder | no real LichtFeld undelete flow wired yet |
| `open_project()` | placeholder | depends on whether the plugin API exposes project lifecycle controls |
| `save_project()` | placeholder | depends on whether the plugin API exposes project lifecycle controls |
| `close_project()` | placeholder | depends on whether the plugin API exposes project lifecycle controls |

## Current limitation

- no real undo via LichtFeld is implemented yet
- `open_project()` / `save_project()` / `close_project()` are still placeholders unless
the LichtFeld plugin API exposes those lifecycle operations cleanly
- remaining selection gaps include:
  - scale selection
  - density selection
  - bounding box selection
  - semantic / AI-assisted selection
- the mock adapter remains the only functional backend in tests

This gives the project a safe next step toward a real LichtFeld integration without
breaking local development or CI.
