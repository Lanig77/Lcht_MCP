# Cluster Analysis

## Purpose

`cluster_analysis` adds a backend-independent way to detect disconnected Gaussian
splat groups inside a `GaussianCloud`.

The feature is intended for cleanup and inspection workflows where we want to
reason about spatial structure in the domain layer before involving adapters,
services, or MCP tools.

## How it works

The analysis uses Gaussian positions only.

Two gaussians are considered connected when their Euclidean distance is less
than or equal to `distance_threshold`.

To avoid an `O(n^2)` all-pairs scan, the implementation builds a simple spatial
hash grid:

- each gaussian is assigned to a cell based on its position
- neighbor checks only inspect the current cell and adjacent cells
- connected components are then collected with a breadth-first traversal

The implementation is dependency-free and does not require NumPy, SciPy, or any
runtime backend.

## Cluster Output

Each detected `Cluster` contains:

- `id`
- `gaussian_ids`
- `count`
- `bounding_box`
- `centroid`

Helper functions also support common cleanup decisions:

- `largest_cluster(...)`
- `clusters_smaller_than(...)`
- `clusters_outside_largest(...)`

## Choosing `distance_threshold`

`distance_threshold` controls how aggressively nearby splats are grouped
together.

- a smaller threshold isolates tiny disconnected islands
- a larger threshold merges nearby fragments into broader components

The right value depends on scene scale and splat density.

## Use Cases

- remove floating splats or noise islands
- keep only the main object by preserving the largest cluster
- detect disconnected fragments before destructive cleanup

## Architectural Boundary

This module lives entirely in the domain layer.

It depends on:

- `GaussianCloud`
- `Gaussian`
- domain geometry value objects

It does not depend on:

- LichtFeld
- adapters
- services
- MCP tools
