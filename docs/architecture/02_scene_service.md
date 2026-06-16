# SceneService

## Purpose

`SceneService` is the facade between MCP tools and `core.SceneAPI`.

Its job is intentionally simple:

- expose business-oriented scene operations to tools;
- keep the tool layer free from core internals;
- provide one place where future application-level policies can be added.

## Why this layer exists

Without a service layer, tools would depend directly on `SceneAPI`.

That works in a small prototype, but it creates tighter coupling between:

- the MCP protocol surface;
- internal orchestration details;
- and future application policies.

`SceneService` reduces that coupling while keeping the public behavior unchanged.

## Current responsibilities

At the moment, `SceneService` is mostly a delegating facade over `SceneAPI`.

It exposes methods such as:

- `open_project`
- `save_project`
- `close_project`
- `get_stats`
- `select_by_box`
- `select_by_height`
- `select_by_color`
- `crop_by_box`
- `crop_by_height`
- `delete_selection`
- `optimize_for_target`
- `export_scene`
- `measure_distance`
- `undo`
- `list_history`

## Expected rules

- MCP tools call `SceneService`, not `SceneAPI` directly.
- `SceneService` does not implement engine-specific behavior.
- `SceneService` should stay readable and thin unless a true application concern appears.

## Relation to SceneAPI

The split is deliberate:

- `SceneService` is the facade presented to application surfaces such as MCP tools.
- `SceneAPI` is the core orchestration layer that validates and prepares operations for adapters.

This means new surfaces could be added later without talking directly to adapters or duplicating validation logic.
