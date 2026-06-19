# Large Scene Guidelines

## Purpose

This document defines the permanent architectural rules for any feature that
operates on large Gaussian scenes.

Future user stories may simply state:

`Respect the Large Scene Guidelines.`

That phrase means the implementation must follow the principles below unless a
later architecture decision explicitly replaces them.

## Target scale

The system must be designed for production-scale datasets:

- typical production scenes: `1M-5M` gaussians
- high-end target: `10M` gaussians

The architecture must treat `10M` splats as a normal supported workload, not as
an exceptional edge case.

## Permanent rules

### Scalability

- Target up to `10M` gaussians.
- Never assume that all splats can be materialized as Python objects.
- Never assume that Python lists of millions of elements are acceptable by
  default.
- Python algorithms must remain bounded in memory and execution time.

### Bounded execution

Every analysis feature must support:

- configurable execution budget
- bounded mode
- sampled mode
- approximate results
- explicit abort mode

If a computation cannot finish within its configured execution budget, it
should reduce scope, return an approximate result, or abort clearly rather than
silently expanding work.

### Interactive workflows

Default execution should remain interactive.

Target:

- preview `< 5 seconds` whenever reasonably achievable

Heavy analysis is allowed, but it must be explicitly requested by the user and
must not be the default preview path.

### Algorithm choices

Prefer:

- voxel-based
- grid-based
- hierarchical
- multi-resolution
- coarse-to-fine

Avoid default point-to-point algorithms on millions of splats.

Algorithms that scale with individual pairwise point comparisons should not be
the default for production scenes unless they operate on a tightly bounded
subset.

### Native runtime handling

Whenever possible:

- operate on LichtFeld native tensors
- slice or sample before Python conversion
- avoid Python copies
- avoid Python lists of millions of elements

If data must cross from the native runtime into Python, the transfer should be
bounded first.

### UI and user communication

Every approximate result must clearly indicate:

- approximate
- sampled
- execution budget
- analyzed splats
- total splats

The UI and logs should make it obvious when a result is partial, bounded, or
budget-constrained.

### Destructive operations

Never execute destructive actions directly from approximate analyses.

The required workflow is always:

Preview

`↓`

Selection

`↓`

User validation

`↓`

Soft delete

`↓`

Apply

Approximate or sampled analysis may suggest a candidate region, but it must not
directly trigger deletion or final destructive changes.

### Native cleanup selection preview

Cleanup preview is the validation bridge between analysis and editing.

Rules:

- `Analyze Scene` may produce approximate cleanup candidates.
- `Preview Cleanup Selection` may convert those candidates into a native LichtFeld
  selection for inspection.
- selection preview must remain non-destructive and must not soft delete, hide, or
  apply deletion.
- approximate previews must be labeled clearly as sampled or estimated.
- the default preview path must stay bounded and avoid full-scene Python
  materialization.

This preserves the required workflow:

Analyze Scene

`->`

Cleanup Candidate Detection

`->`

Native Selection Preview

`->`

User validation

`->`

Soft delete

`->`

Restore or Apply Deleted

## Complexity expectations

Every future analysis algorithm should document:

- expected complexity
- expected memory behavior
- expected behavior on:
  - `1M` splats
  - `5M` splats
  - `10M` splats

This documentation does not need to be a formal proof, but it must be explicit
enough to justify why the algorithm is suitable as a default preview, an
optional heavy analysis, or both.

## Design guidance by layer

### Domain layer

- Keep domain algorithms backend-independent where practical.
- Prefer representations that can summarize large datasets without requiring one
  Python object per splat.
- Document whether a domain algorithm is intended for exact analysis,
  approximate analysis, or both.

### Adapter layer

- Push sampling, slicing, and filtering as close to the native backend as
  possible.
- Avoid converting full native tensors when only a bounded subset is needed.
- Expose clear metadata about approximation, analyzed count, total count, and
  timing.

### UI and plugin layer

- Default buttons should choose the fast safe preview path.
- Heavy or high-detail modes should be opt-in.
- Panel controls should surface execution limits so users understand the active
  budget.

## Checklist for new large-scene features

Before shipping a new large-scene analysis or cleanup workflow, confirm:

- the default mode is bounded
- the default mode is interactive enough for production use
- the feature can report approximate results honestly
- destructive actions are separated from approximate preview
- the implementation avoids full Python materialization when possible
- the algorithm behavior at `1M`, `5M`, and `10M` splats is documented
