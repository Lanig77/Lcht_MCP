# Gaussian Query DSL

## Overview

Lcht_MCP now includes a backend-independent Query DSL for Gaussian Splatting domain objects.

The goal is to describe selections in the domain layer without coupling query construction to a specific runtime backend. A query can be built once, evaluated in memory today, and later translated to backend-native selection mechanisms when available.

## Why a Query DSL

Before the DSL, selection logic mainly appeared as direct runtime operations such as height, opacity, or color selection on an active backend scene.

The Query DSL introduces a different level of abstraction:

- adapter selection methods are imperative and backend-facing
- domain queries are declarative and backend-independent
- predicates describe intent, but do not execute anything by themselves
- evaluation currently happens inside `GaussianCloud`

This separation lets the domain model stay stable even when backend integrations evolve.

## Two Query Layers

### Direct adapter selection methods

Adapter selection methods operate on a live engine scene. They are useful when the backend already exposes efficient selection primitives.

Examples:

- `select_by_height(...)`
- `select_by_opacity(...)`
- `select_by_color(...)`

Characteristics:

- immediate side effects on the active scene
- backend-specific implementation details
- may depend on masks, tensors, or engine APIs

### Domain-level `GaussianQuery` DSL

`GaussianQuery` lives entirely in the core domain model.

Characteristics:

- immutable query builder
- no dependency on MCP, tools, services, adapters, LichtFeld, Torch, or NumPy
- no side effects while building predicates
- evaluated against `GaussianCloud` data in memory

## Predicates

The current DSL exposes the following predicate entry points:

- `Height`
- `Opacity`
- `Color`
- `Scale`
- `Density`

These objects are immutable descriptors. They do not mutate a scene and they do not talk to a backend.

## Comparison Syntax

Supported examples:

```python
from lichtfeld_mcp.core.query import Color, Density, Height, Opacity, Scale

Height > 2
Height >= 2
Height < 2
Height <= 2
Height.between(1, 2)

Opacity.greater_than(0.5)
Opacity.between(0.2, 0.8)

Color.similar((200, 140, 20), tolerance=10)

Scale.between(1.0, 3.0)
Density.between(0.2, 0.9)
```

Notes:

- inverted height ranges are normalized by the domain constraints helpers
- opacity values are validated in the `0.0 .. 1.0` range
- `Color.similar(...)` expects RGB input in `0 .. 255`
- color tolerance is validated by the existing domain constraints
- `Scale` currently evaluates a basic average scale value
- `Density` currently reads a basic domain-level density value from gaussian metadata when present

## Logical Composition

Predicates can be composed with boolean-style operators:

- `&` for logical AND
- `|` for logical OR
- `~` for logical NOT

Examples:

```python
(Height > 2) & (Opacity > 0.5)
(Height > 2) | Color.similar((200, 140, 20), tolerance=10)
~Color.similar((100, 100, 100))
```

Each composition returns a new expression object. Existing expressions remain unchanged.

## `GaussianQuery`

`GaussianQuery` is the immutable query builder attached to a `GaussianCloud`.

Main methods:

- `where(predicate)`
- `filter(predicate)`
- `all()`
- `count()`
- `ids()`
- `first()`

Typical usage:

```python
query = (
    scene.gaussians.query()
    .where(Height.between(1, 2))
    .where(Opacity > 0.4)
)

matches = query.all()
count = query.count()
ids = query.ids()
first = query.first()
```

The builder also keeps compatibility helpers such as `by_height(...)`, `by_opacity(...)`, and `by_color(...)`, but the DSL-style `where(...)` API is the primary direction.

## `GaussianCloud.execute(query)`

Evaluation happens in the domain layer through `GaussianCloud.execute(query)`.

Current behavior:

- iterates over gaussians in memory
- evaluates each predicate expression against each gaussian
- returns matching `Gaussian` objects

No backend execution happens here. The query is resolved purely from domain data already present in the cloud.

## Examples

### Select by height and opacity

```python
from lichtfeld_mcp.core.query import Height, Opacity

count = (
    scene.gaussians.query()
    .where(Height.between(1, 2))
    .where(Opacity > 0.4)
    .count()
)
```

### Select by color tolerance

```python
from lichtfeld_mcp.core.query import Color

ids = (
    scene.gaussians.query()
    .where(Color.similar((200, 140, 20), tolerance=10))
    .ids()
)
```

### Combine AND, OR, and NOT

```python
from lichtfeld_mcp.core.query import Color, Height, Opacity

bright_high = (Height > 2) & (Opacity > 0.5)
high_or_warm = (Height > 2) | Color.similar((200, 140, 20), tolerance=10)
not_gray = ~Color.similar((100, 100, 100))

high_ids = scene.gaussians.query().where(bright_high).ids()
mixed_ids = scene.gaussians.query().where(high_or_warm).ids()
not_gray_ids = scene.gaussians.query().where(not_gray).ids()
```

### Retrieve `ids`, `count`, and `first`

```python
from lichtfeld_mcp.core.query import Density, Scale

query = (
    scene.gaussians.query()
    .where(Scale.between(1.5, 2.5))
    .where(Density.between(0.3, 1.0))
)

ids = query.ids()
count = query.count()
first = query.first()
```

## Current Limitations

- queries are evaluated in memory only
- there is no backend pushdown yet
- `Density` is currently basic and domain-level only
- `Scale` is currently evaluated through a simple average scale value
- there are no AI or semantic predicates yet

## Future Direction

The long-term direction is to keep the DSL as the stable querying language of the domain model, while allowing selected predicates to be translated to backend-native operations when possible.

For example, a future LichtFeld integration may translate compatible DSL predicates into selection masks instead of evaluating everything only in Python memory.
