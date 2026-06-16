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

It exposes a concrete plugin-oriented adapter class with placeholder methods aligned
to the current runtime needs, including:

- `open_project`
- `get_stats`
- `select_by_height`
- `delete_selection`
- `undo`

The class also satisfies the broader adapter contract so it can later plug into
`SceneAPI` without changing MCP-facing code.

## Availability behavior

If LichtFeld is not installed or the plugin API cannot be imported, the adapter raises
`AdapterUnavailableError` with a clear message.

This is intentional. The repository should fail explicitly when the real backend is
requested, while still allowing the default mock-backed test suite to run normally.

## Planned mapping to the LichtFeld plugin API

The current skeleton documents the intended implementation path with internal comments.

Planned mapping:

- `scene.combined_model()` to access the active Gaussian model
- `model.get_means()` to read positions and derive masks or statistics
- `scene.set_selection_mask(mask)` to push selection state into the UI/runtime
- `model.soft_delete(mask)` to mark selected gaussians as deleted
- `model.undelete(mask)` to restore deleted gaussians for undo-like flows
- `model.apply_deleted()` to commit pending deletions
- `scene.notify_changed()` to refresh the scene after mutations

## Expected future flow

```text
MCP tools
  -> SceneService
  -> SceneAPI
  -> LichtfeldPluginAdapter
  -> LichtFeld Studio Plugin API
```

## Current limitation

- the adapter is a skeleton only
- tensor operations are not implemented yet
- the mock adapter remains the only functional backend in tests

This gives the project a safe next step toward a real LichtFeld integration without
breaking local development or CI.
