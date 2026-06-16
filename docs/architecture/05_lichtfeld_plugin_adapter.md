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

- `src/lichtfeld_mcp/adapters/lichtfeld.py`

It exposes a concrete plugin-oriented adapter class aligned to the current runtime
contract.

Some operations are already implemented against the active LichtFeld plugin scene:

- `get_stats()`
- `select_by_height()`
- `delete_selection()`

Other methods are still placeholders, including:

- `open_project`
- `save_project`
- `close_project`
- `undo`

The class also satisfies the broader adapter contract so it can later plug into
`SceneAPI` without changing MCP-facing code.

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

### `delete_selection()`

`delete_selection()` uses the current selection mask and applies a first real deletion
flow against the LichtFeld model.

It currently:

- prefers the latest cached selection mask created by `select_by_height()`
- falls back to a scene-provided selection mask when the API exposes one
- calls `model.soft_delete(mask)`
- calls `model.apply_deleted()` when available
- clears the adapter-side cached selection mask
- clears the scene selection mask when possible
- calls `scene.notify_changed()` when available

The method still returns the existing `ToolResult` contract for compatibility with the
rest of the application.

## Active selection mask cache

The adapter keeps a lightweight in-memory cache of the latest known selection mask.

This cache exists for two reasons:

- it lets `delete_selection()` work immediately after `select_by_height()` even if the
scene API does not expose a readable selection mask
- it lets `get_stats()` report a meaningful `selected_count` when the current selection
is known by the adapter

The cache is cleared after `delete_selection()`.

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
```

## Current integration status

| operation | status | notes |
| --- | --- | --- |
| `get_stats()` | implemented | reads active scene/model, computes bounds and splat count defensively |
| `select_by_height()` | implemented | builds a boolean mask from Gaussian `z` positions |
| `delete_selection()` | implemented | uses `soft_delete(mask)` and `apply_deleted()` when available |
| `select_by_box()` | placeholder | not connected to LichtFeld yet |
| `select_by_color()` | placeholder | not connected to LichtFeld yet |
| `crop_by_height()` | placeholder | not connected to LichtFeld yet |
| `undo()` | placeholder | no real LichtFeld undelete flow wired yet |
| `open_project()` | placeholder | depends on whether the plugin API exposes project lifecycle controls |
| `save_project()` | placeholder | depends on whether the plugin API exposes project lifecycle controls |
| `close_project()` | placeholder | depends on whether the plugin API exposes project lifecycle controls |

## Current limitation

- no real undo via LichtFeld is implemented yet
- only height-based selection is implemented
- `open_project()` / `save_project()` / `close_project()` are still placeholders unless
the LichtFeld plugin API exposes those lifecycle operations cleanly
- the mock adapter remains the only functional backend in tests

This gives the project a safe next step toward a real LichtFeld integration without
breaking local development or CI.
