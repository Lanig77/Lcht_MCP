# Gaussian Domain Model

## Overview

`Lcht_MCP` is now structured around a backend-agnostic Gaussian Splatting domain model.

The important shift is that the repository is no longer only an MCP server prototype. It now contains a core domain that can describe, query, select, and edit Gaussian data independently from:

- MCP transport concerns
- tool wiring
- service orchestration
- adapter implementations
- any concrete backend such as Lichtfeld

This domain layer is intended to become the long-term center of the framework.

## Main domain objects

### Scene

`Scene` is the aggregate root of the domain model.

It owns the main domain components and exposes small domain-level helpers such as:

- `is_empty()`
- `gaussian_count()`
- `bounding_box()`
- `select_query(...)`
- `select_by_height(...)`
- `select_by_opacity(...)`
- `select_by_color(...)`

### GaussianCloud

`GaussianCloud` is the main typed container for Gaussian primitives.

It stores `Gaussian` instances and exposes operations such as:

- `count()`
- `ids()`
- `is_empty()`
- `add(...)`
- `get(...)`
- `remove_many(...)`
- `bounding_box()`
- `query()`

### Gaussian

`Gaussian` represents one Gaussian primitive with typed value objects:

- `GaussianId`
- `Position3D`
- `Quaternion`
- `Scale3D`
- `RGBColor`
- `SphericalHarmonics`

This gives the domain a stable representation that does not depend on any engine-specific API.

### GaussianQuery

`GaussianQuery` is an immutable-style query helper over `GaussianCloud`.

It supports filtered views such as:

- `by_height(...)`
- `by_opacity(...)`
- `by_color(...)`

And result accessors such as:

- `result()`
- `ids()`
- `count()`

### SelectionManager

`SelectionManager` stores the currently selected `GaussianId` values.

It deduplicates selected IDs, preserves deterministic order in `ids()`, and exposes:

- `select(...)`
- `clear()`
- `ids()`
- `count()`
- `is_empty()`
- `contains(...)`

### EditManager

`EditManager` is the current domain edit entry point.

Today it exposes:

- `delete_selected()`

It operates on the selected Gaussian IDs and removes them from the `GaussianCloud`.

### HistoryStack

`HistoryStack` stores lightweight typed history entries.

At the moment it is used to record domain edit operations such as `delete_selected`, including:

- `action`
- `affected_ids`
- `details`

Undo restoration is not implemented yet.

### Capabilities

`Capabilities` is a domain-level description of what a scene or backend may support.

It gives the model a place to represent feature availability without leaking runtime or adapter concerns into the rest of the domain.

## Current domain flow

The current domain interaction flow is:

```text
Scene
  -> GaussianCloud
  -> GaussianQuery
  -> SelectionManager
  -> EditManager
  -> HistoryStack
```

A typical path looks like this:

1. `Scene` owns a `GaussianCloud`.
2. `GaussianCloud.query()` creates a `GaussianQuery`.
3. The query returns matching `GaussianId` values.
4. `Scene.selection` stores the selected IDs.
5. `Scene.edit.delete_selected()` removes selected gaussians.
6. `Scene.history` records the operation.

## Examples

### Create a Scene

```python
from lichtfeld_mcp.core.scene import Scene

scene = Scene()

assert scene.is_empty() is True
assert scene.gaussian_count() == 0
```

### Add gaussians

```python
from lichtfeld_mcp.core.gaussian import Gaussian, GaussianId, Position3D

scene.gaussians.add(
    Gaussian(id=GaussianId(1), position=Position3D(x=0.0, y=0.0, z=0.0))
)
scene.gaussians.add(
    Gaussian(id=GaussianId(2), position=Position3D(x=0.0, y=0.0, z=2.0))
)
```

### Select by height

```python
scene.select_by_height(min_z=1.0, max_z=3.0)

selected_ids = scene.selection.ids()
```

### Delete selected

```python
deleted = scene.edit.delete_selected()

assert deleted >= 0
```

### Inspect history

```python
entries = scene.history.entries()

if entries:
    last_entry = entries[-1]
    print(last_entry.action)
    print(last_entry.affected_ids)
```

## Architectural boundaries

The domain layer has no dependency on:

- MCP
- tool modules
- services
- adapters
- Lichtfeld

That separation is intentional.

The backend adapters remain separate and are still the integration boundary for real engines or the current mock implementation.

## Current status

- the Gaussian domain model is now real and typed
- `Scene` owns domain state and helpers
- selection and delete operations exist at the domain level
- lightweight edit history exists
- undo restoration is not implemented yet

This gives the project a clean foundation for future engine integrations and higher-level application flows.
